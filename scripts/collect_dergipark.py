#!/usr/bin/env python3
"""Collect open-access Kahramanmaraş dialect articles and PDFs via OpenAlex API
(avoiding DergiPark's CAPTCHA-gated search endpoint while fetching open-access
DergiPark/institutional article pages & PDFs directly), and extract UTF-8 text locally.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import pymupdf
import httpx
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "dergipark"
PDF_DIR = RAW_DIR / "pdfs"
TEXT_DIR = RAW_DIR / "texts"
MANIFEST_PATH = RAW_DIR / "manifest.json"

OPENALEX_QUERIES = [
    "Kahramanmaraş ağzı",
    "Kahramanmaraş ağızları",
    "Maraş ağzı",
    "Kahramanmaraş Derleme Sözlüğü",
    "Türkoğlu ağzı",
    "Çağlayancerit ağzı",
    "Elbistan ağzı",
    "Afşin ağzı",
    "Andırın ağzı",
    "Göksun ağzı",
    "Pazarcık ağzı",
    "Kahramanmaraş deyimler atasözleri",
]

REGION_PATTERNS = [
    ("merkez", [r"\bmerkez\b", r"\bonikişubat\b", r"\bdulkadiroğlu\b"]),
    ("turkoglu", [r"\btürkoğlu\b", r"\bturkoglu\b"]),
    ("caglayancerit", [r"\bçağlayancerit\b", r"\bcaglayancerit\b"]),
    ("elbistan", [r"\belbistan\b"]),
    ("afsin", [r"\bafşin\b", r"\bafsin\b"]),
    ("andirin", [r"\bandırın\b", r"\bandirin\b"]),
    ("goksun", [r"\bgöksun\b", r"\bgoksun\b"]),
    ("pazarcik", [r"\bpazarcık\b", r"\bpazarcik\b"]),
    ("ekinozu", [r"\bekinözü\b", r"\bekinozu\b"]),
    ("nurhak", [r"\bnurhak\b"]),
]

RELEVANCE_POS = [
    "kahramanmaraş",
    "maraş",
    "ağzı",
    "ağız",
    "ağızları",
    "derleme sözlüğü",
    "söz varlığı",
    "deyim",
    "atasöz",
    "arkaik",
    "türkoğlu",
    "elbistan",
    "çağlayancerit",
    "afşin",
    "andırın",
    "göksun",
    "pazarcık",
    "ekinözü",
    "ses bilgisi",
    "şekil bilgisi",
    "sözcük",
    "sözlük",
    "halk",
    "folklor",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


def slugify(text: str, max_len: int = 80) -> str:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = text.translate(tr_map).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:max_len].strip("-")) or "article"


def detect_region(text: str) -> str:
    low = text.lower()
    for region, patterns in REGION_PATTERNS:
        if any(re.search(pat, low) for pat in patterns):
            return region
    return "general"


def score_relevance(title: str) -> int:
    t = title.lower()
    score = 0
    has_maras = any(
        k in t
        for k in (
            "maraş",
            "türkoğlu",
            "çağlayancerit",
            "elbistan",
            "afşin",
            "andırın",
            "göksun",
            "pazarcık",
            "ekinözü",
            "nurhak",
        )
    )
    has_lang = any(
        k in t
        for k in (
            "ağz",
            "ağız",
            "söz varlığ",
            "derleme",
            "deyim",
            "atasöz",
            "sözcük",
            "arkaik",
            "şekil",
            "ünlü",
            "ünsüz",
            "ses bil",
            "folklor",
            "mani",
            "masal",
            "türkü",
        )
    )
    if has_maras:
        score += 10
    if has_lang:
        score += 10
    for kw in RELEVANCE_POS:
        if kw in t:
            score += 2
    if not has_maras:
        score -= 20
    if not has_lang:
        score -= 12
    # Avoid non-linguistic papers (e.g. museum bronze lamps, botany, wood architecture)
    if any(bad in t for bad in ("bronz", "bitki", "takson", "müze", "deprem", "toprak", "iklim", "ekonomi")):
        score -= 15
    return score


def is_blocked(resp: httpx.Response) -> bool:
    if resp.status_code in (403, 429, 503):
        return True
    low = resp.text[:4000].lower()
    return any(tok in low for tok in ("cf-browser-verification", "captcha", "g-recaptcha", "turnstile", "arama doğrulama"))


def discover_via_openalex(client: httpx.Client) -> list[dict]:
    found: dict[str, dict] = {}
    for q in OPENALEX_QUERIES:
        try:
            r = client.get(
                f"https://api.openalex.org/works?search={quote_plus(q)}&per-page=20",
                timeout=20,
            )
            if r.status_code != 200:
                print(f"[WARN] OpenAlex HTTP {r.status_code} for {q}")
                continue
            for w in r.json().get("results", []):
                title = (w.get("title") or "").strip()
                if not title:
                    continue
                rel = score_relevance(title)
                if rel < 12:
                    continue
                oa_id = w.get("id", title)
                loc = w.get("primary_location") or {}
                best_oa = w.get("best_oa_location") or {}
                pdf_url = loc.get("pdf_url") or best_oa.get("pdf_url")
                landing = loc.get("landing_page_url") or best_oa.get("landing_page_url") or w.get("doi")
                if not pdf_url and isinstance(landing, str) and "/download/article-file/" in landing:
                    pdf_url = landing
                # Also inspect all locations for a direct PDF or DergiPark URL
                if not pdf_url:
                    for al in w.get("locations") or []:
                        if al.get("pdf_url"):
                            pdf_url = al["pdf_url"]
                            break
                        if not landing and al.get("landing_page_url"):
                            landing = al["landing_page_url"]

                journal = ((loc.get("source") or {}).get("display_name")) or ((best_oa.get("source") or {}).get("display_name"))
                authors = [
                    (a.get("author") or {}).get("display_name")
                    for a in (w.get("authorships") or [])
                    if (a.get("author") or {}).get("display_name")
                ]
                prev = found.get(oa_id)
                if not prev or rel > prev["relevance_score"] or (pdf_url and not prev.get("pdf_url")):
                    found[oa_id] = {
                        "openalex_id": oa_id,
                        "title": title,
                        "year": w.get("publication_year"),
                        "journal": journal,
                        "authors": authors,
                        "doi": w.get("doi"),
                        "landing_url": landing,
                        "pdf_url": pdf_url,
                        "query": q,
                        "relevance_score": rel,
                    }
            time.sleep(0.3)
        except Exception as exc:
            print(f"[ERR] OpenAlex {q}: {exc}")

    items = list(found.values())
    items.sort(key=lambda x: (1 if x.get("pdf_url") else 0, x["relevance_score"]), reverse=True)
    return items[:25]


def resolve_pdf_from_landing(client: httpx.Client, url: str) -> tuple[str | None, str]:
    try:
        resp = client.get(url, timeout=25)
        if is_blocked(resp) or resp.status_code != 200:
            return None, f"landing_http_{resp.status_code}"
        if resp.content.startswith(b"%PDF"):
            return str(resp.url), "direct_pdf"
        soup = BeautifulSoup(resp.text, "lxml")
        meta_pdf = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta_pdf and meta_pdf.get("content"):
            return urljoin(str(resp.url), meta_pdf["content"].strip()), "meta_pdf"
        for sel in ('a[href*="/download/article-file/"]', 'a[href$=".pdf"]', 'a[href*=".pdf?"]'):
            a = soup.select_one(sel)
            if a and a.get("href"):
                return urljoin(str(resp.url), a["href"]), "html_link"
        return None, "no_pdf_link_on_landing"
    except Exception as exc:
        return None, f"landing_err: {exc}"


def download_item(client: httpx.Client, item: dict, idx: int) -> dict:
    rec = {**item, "region": detect_region(item["title"]), "status": "pending"}
    pdf_url = item.get("pdf_url")

    # If pdf_url is actually a DergiPark landing page (/tr/pub/...), resolve the real download URL
    if pdf_url and "/tr/pub/" in pdf_url and "/download/article-file/" not in pdf_url:
        resolved, note = resolve_pdf_from_landing(client, pdf_url)
        rec["resolve_note"] = note
        pdf_url = resolved

    if not pdf_url and item.get("landing_url"):
        resolved, note = resolve_pdf_from_landing(client, item["landing_url"])
        rec["resolve_note"] = note
        pdf_url = resolved

    if not pdf_url:
        rec["status"] = rec.get("resolve_note", "no_pdf_url")
        return rec

    rec["resolved_pdf_url"] = pdf_url
    try:
        resp = client.get(pdf_url, timeout=45)
        rec["pdf_http_status"] = resp.status_code
        if resp.status_code != 200:
            rec["status"] = f"pdf_http_{resp.status_code}"
            return rec
        if not resp.content.startswith(b"%PDF"):
            # Maybe pdf_url was a landing page that redirected to HTML
            soup = BeautifulSoup(resp.text, "lxml")
            a = soup.select_one('a[href*="/download/article-file/"], a[href$=".pdf"]')
            if a and a.get("href"):
                real_u = urljoin(str(resp.url), a["href"])
                resp = client.get(real_u, timeout=45)
                rec["resolved_pdf_url"] = real_u
            if not resp.content.startswith(b"%PDF"):
                rec["status"] = "not_a_pdf"
                return rec

        slug = f"{idx:02d}_{slugify(item['title'], 60)}"
        pdf_path = PDF_DIR / f"{slug}.pdf"
        pdf_path.write_bytes(resp.content)
        rec["slug"] = slug
        rec["pdf_path"] = str(pdf_path.relative_to(BASE_DIR))
        rec["pdf_bytes"] = len(resp.content)
        rec["status"] = "downloaded"
        return rec
    except Exception as exc:
        rec["status"] = f"download_err: {exc}"
        return rec


def extract_pdfs_locally() -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    articles = manifest.get("articles", [])
    by_slug = {a.get("slug"): a for a in articles if a.get("slug")}

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    total_pages = 0
    for pdf_path in pdf_files:
        slug = pdf_path.stem
        txt_path = TEXT_DIR / f"{slug}.txt"
        doc = pymupdf.open(pdf_path)
        pages = []
        for i, page in enumerate(doc, start=1):
            txt = page.get_text("text")
            pages.append(f"\n--- PAGE {i} ---\n{txt}")
        full_text = "".join(pages)
        txt_path.write_text(full_text, encoding="utf-8")
        total_pages += len(doc)
        if slug in by_slug:
            by_slug[slug]["text_path"] = str(txt_path.relative_to(BASE_DIR))
            by_slug[slug]["pages"] = len(doc)
            by_slug[slug]["chars"] = len(full_text)
        doc.close()

    manifest["extracted_pdfs"] = len(pdf_files)
    manifest["total_pages"] = total_pages
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted {len(pdf_files)} PDFs ({total_pages} pages) into {TEXT_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract-only", action="store_true", help="Only extract already downloaded PDFs locally")
    args = parser.parse_args()

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    if args.extract_only:
        extract_pdfs_locally()
        return

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        candidates = discover_via_openalex(client)
        print(f"Discovered {len(candidates)} candidate articles via OpenAlex")
        results = []
        for idx, item in enumerate(candidates, start=1):
            print(f"[{idx}/{len(candidates)}] {item['title'][:72]}...")
            rec = download_item(client, item, idx)
            results.append(rec)
            print(f"   -> {rec['status']} ({rec.get('region', '-')})")
            time.sleep(0.8)

    manifest = {
        "discovery": "OpenAlex API + direct open-access PDF download",
        "queries": OPENALEX_QUERIES,
        "candidates_found": len(candidates),
        "downloaded": sum(1 for r in results if r["status"] == "downloaded"),
        "articles": results,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved DergiPark/academic manifest: {manifest['downloaded']}/{len(candidates)} PDFs downloaded.")


if __name__ == "__main__":
    main()

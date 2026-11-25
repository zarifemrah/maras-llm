#!/usr/bin/env python3
"""Collect Kahramanmaraş dialect glossaries, idioms, and sample dialogues
from open regional cultural sites and Turkish Wiktionary.
Discovers URLs dynamically via site search/API/sitemaps rather than guessing paths.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
GLOSS_DIR = BASE_DIR / "data" / "raw" / "glossaries"
HTML_DIR = GLOSS_DIR / "html"
OUT_JSONL = GLOSS_DIR / "maras_glossaries.jsonl"
MANIFEST_PATH = GLOSS_DIR / "manifest.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

SITES = [
    {"name": "marasavucumda", "base": "https://marasavucumda.com"},
    {"name": "ansiklopedi46", "base": "https://ansiklopedi46.com.tr"},
    {"name": "marasmanset", "base": "https://www.marasmanset.com"},
]

SEARCH_TERMS = ["maraş ağzı", "kahramanmaraş ağzı", "maraş şivesi", "sözlük", "yöresel kelimeler"]


def is_blocked(resp: httpx.Response) -> bool:
    if resp.status_code in (403, 429, 503):
        return True
    low = resp.text[:4000].lower()
    return any(tok in low for tok in ("cf-browser-verification", "just a moment", "captcha", "turnstile"))


def slugify(url: str) -> str:
    s = re.sub(r"https?://", "", url)
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    return s[:90]


def discover_site_urls(client: httpx.Client, site: dict, manifest_site: dict) -> list[str]:
    base = site["base"]
    urls: dict[str, int] = {}

    def score_link(u: str, text: str) -> int:
        comb = f"{u} {text}".lower()
        sc = 0
        for kw in ("agzi", "ağzı", "sive", "şive", "sozluk", "sözlük", "kelime", "deyim", "atasoz", "yoresel", "yöresel", "maras"):
            if kw in comb:
                sc += 2
        if any(bad in comb for bad in ("/tag/", "/category/", "/author/", "/page/", ".jpg", ".png", "wp-login")):
            sc -= 5
        return sc

    # 1. Try WordPress REST API if available
    for q in ("maraş ağzı", "sözlük", "kelimeler", "şive"):
        try:
            r = client.get(f"{base}/wp-json/wp/v2/posts?search={quote_plus(q)}&per_page=10", timeout=15)
            manifest_site["probes"].append({"url": str(r.url), "status": r.status_code})
            if r.status_code == 200 and r.text.strip().startswith("["):
                for post in r.json():
                    link = post.get("link")
                    title = post.get("title", {}).get("rendered", "")
                    if link and score_link(link, title) >= 2:
                        urls[link] = max(urls.get(link, 0), score_link(link, title))
        except Exception as exc:
            manifest_site["probes"].append({"wp_api_error": str(exc)})

    # 2. Try HTML search & homepage links
    probe_pages = [base] + [f"{base}/?s={quote_plus(q)}" for q in ("maraş ağzı", "yöresel kelimeler")]
    for purl in probe_pages:
        try:
            r = client.get(purl, timeout=20)
            manifest_site["probes"].append({"url": purl, "status": r.status_code})
            if is_blocked(r) or r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = urljoin(base, a["href"]).split("#")[0]
                if not href.startswith(base):
                    continue
                txt = " ".join(a.get_text(" ", strip=True).split())
                sc = score_link(href, txt)
                if sc >= 4:
                    urls[href] = max(urls.get(href, 0), sc)
            time.sleep(0.5)
        except Exception as exc:
            manifest_site["probes"].append({"url": purl, "error": str(exc)})

    ranked = sorted(urls.items(), key=lambda kv: kv[1], reverse=True)
    return [u for u, _ in ranked[:12]]


def parse_entries_from_html(html: str, source_url: str, site_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    container = soup.select_one("article, .entry-content, .post-content, .content, main") or soup.body or soup
    entries: list[dict] = []

    # 1. Table rows (Term | Meaning | Example)
    for tr in container.find_all("tr"):
        cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if len(cells) >= 2 and len(cells[0]) <= 50 and cells[0].lower() not in {"kelime", "sözcük", "madde"}:
            entries.append({
                "kind": "lexicon",
                "term": cells[0],
                "meaning": cells[1],
                "examples": cells[2:] if len(cells) > 2 else [],
                "region": "general",
                "source": f"web:{site_name}",
                "url": source_url,
            })

    # 2. List items & paragraphs with "Term: Meaning" or "Term - Meaning"
    pair_re = re.compile(r"^([A-Za-zÇĞİÖŞÜçğıöşüâîû'’/\-\s]{2,45}?)\s*(?::|–|—|-)\s+(.{4,350})$")
    for el in container.find_all(["li", "p", "div"]):
        if el.name == "div" and el.find(["p", "li", "table"]):
            continue
        txt = " ".join(el.get_text(" ", strip=True).split())
        if len(txt) < 6 or len(txt) > 500:
            continue
        m = pair_re.match(txt)
        if m:
            term, meaning = m.group(1).strip(" •-*"), m.group(2).strip()
            if len(term.split()) <= 4 and not term.lower().startswith(("not", "kaynak", "örnek", "http")):
                entries.append({
                    "kind": "lexicon",
                    "term": term,
                    "meaning": meaning,
                    "examples": [],
                    "region": "general",
                    "source": f"web:{site_name}",
                    "url": source_url,
                })
                continue
        # Dialogue / example sentences in quotes or Maraş markers
        if any(mk in txt.lower() for mk in ("nootiin", "bayak", "edem", "gari", "gardaş", "heç", "bıldır", "örnek:")):
            entries.append({
                "kind": "text",
                "raw_text": txt,
                "region": "general",
                "source": f"web:{site_name}",
                "url": source_url,
            })
    return entries


def collect_wiktionary(client: httpx.Client, manifest: dict) -> list[dict]:
    entries: list[dict] = []
    api = "https://tr.wiktionary.org/w/api.php"
    try:
        # Search pages mentioning Kahramanmaraş ağzı
        r = client.get(
            api,
            params={
                "action": "query",
                "list": "search",
                "srsearch": '"Kahramanmaraş ağzı" OR "Maraş ağzı"',
                "srlimit": 25,
                "format": "json",
            },
            timeout=20,
        )
        manifest["wiktionary"] = {"search_status": r.status_code}
        if r.status_code != 200:
            return entries
        hits = r.json().get("query", {}).get("search", [])
        manifest["wiktionary"]["hits"] = len(hits)
        titles = [h["title"] for h in hits if ":" not in h["title"]][:25]
        if titles:
            pr = client.get(
                api,
                params={
                    "action": "query",
                    "prop": "extracts",
                    "explaintext": 1,
                    "titles": "|".join(titles),
                    "format": "json",
                },
                timeout=20,
            )
            if pr.status_code == 200:
                pages = pr.json().get("query", {}).get("pages", {}).values()
                for pg in pages:
                    title = pg.get("title", "")
                    extract = pg.get("extract", "")
                    if title and extract:
                        entries.append({
                            "kind": "lexicon",
                            "term": title,
                            "meaning": " ".join(extract.split())[:300],
                            "examples": [],
                            "region": "general",
                            "source": "web:tr.wiktionary",
                            "url": f"https://tr.wiktionary.org/wiki/{quote_plus(title)}",
                        })
    except Exception as exc:
        manifest["wiktionary"] = {"error": str(exc)}
    return entries


def main() -> None:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {"sites": {}}
    all_entries: list[dict] = []

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        for site in SITES:
            sname = site["name"]
            s_info = {"base": site["base"], "probes": [], "fetched_pages": []}
            urls = discover_site_urls(client, site, s_info)
            for u in urls:
                try:
                    resp = client.get(u, timeout=20)
                    blocked = is_blocked(resp)
                    s_info["fetched_pages"].append({"url": u, "status": resp.status_code, "blocked": blocked})
                    if blocked or resp.status_code != 200:
                        continue
                    (HTML_DIR / f"{slugify(u)}.html").write_text(resp.text, encoding="utf-8")
                    parsed = parse_entries_from_html(resp.text, u, sname)
                    all_entries.extend(parsed)
                    time.sleep(0.7)
                except Exception as exc:
                    s_info["fetched_pages"].append({"url": u, "error": str(exc)})
            manifest["sites"][sname] = s_info

        wikt_entries = collect_wiktionary(client, manifest)
        all_entries.extend(wikt_entries)

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for e in all_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    manifest["total_entries"] = len(all_entries)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Glossary collector finished: {len(all_entries)} entries saved to {OUT_JSONL}")


if __name__ == "__main__":
    main()

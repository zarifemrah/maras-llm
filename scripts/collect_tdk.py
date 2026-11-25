#!/usr/bin/env python3
"""Collect Kahramanmaraş entries from TDK Derleme Sözlüğü:
1. Search GitHub for open community JSON/CSV dumps of Derleme Sözlüğü and filter to Maraş & districts.
2. Probe sozluk.gov.tr public JSON endpoints for Derleme Sözlüğü with Kahramanmaraş seed words.
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
TDK_DIR = BASE_DIR / "data" / "raw" / "tdk"
OUT_JSONL = TDK_DIR / "maras_derleme.jsonl"
MANIFEST_PATH = TDK_DIR / "manifest.json"

MARAS_KEYWORDS = [
    "kahramanmaraş",
    "k.maraş",
    "k. maraş",
    "maraş",
    "elbistan",
    "afşin",
    "andırın",
    "göksun",
    "pazarcık",
    "türkoğlu",
    "çağlayancerit",
    "ekinözü",
    "nurhak",
]

SEED_WORDS = [
    "bayak",
    "bıldır",
    "arıstak",
    "ağnanmak",
    "böğsümek",
    "hanek",
    "horanta",
    "bibi",
    "cere",
    "cılbıt",
    "bünelek",
    "meke",
    "dene",
    "ökle",
    "dıkıl",
    "köbe",
    "şelek",
    "kamalak",
    "potuk",
    "kepez",
    "söve",
    "tere",
    "cıngıl",
    "gadan",
    "edem",
    "nootiin",
    "garavaş",
    "çeten",
    "itil",
    "möcü",
    "mucuk",
    "heman",
    "bösbütün",
    "gari",
    "döl",
    "sini",
    "teşt",
    "helke",
    "külek",
    "peşkir",
    "yağlık",
    "çit",
    "yazma",
    "yufka",
    "kömbe",
    "tarhana",
    "ekşili",
    "firik",
    "sömelek",
    "hapısa",
    "bastık",
    "samsa",
    "kelle",
    "paça",
    "şıra",
    "kavut",
    "hedik",
    "göce",
    "dövme",
    "yarma",
    "bulgur",
    "çökelek",
    "tulum",
    "keş",
    "börek",
    "şırdan",
    "mumbar",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

REGION_MAP = [
    ("merkez", ["merkez", "onikişubat", "dulkadiroğlu"]),
    ("elbistan", ["elbistan"]),
    ("afsin", ["afşin", "afsin"]),
    ("andirin", ["andırın", "andirin"]),
    ("goksun", ["göksun", "goksun"]),
    ("pazarcik", ["pazarcık", "pazarcik"]),
    ("turkoglu", ["türkoğlu", "turkoglu"]),
    ("caglayancerit", ["çağlayancerit", "caglayancerit"]),
    ("ekinozu", ["ekinözü", "ekinozu"]),
    ("nurhak", ["nurhak"]),
]


def detect_region(text: str) -> str:
    low = text.lower()
    for reg, keys in REGION_MAP:
        if any(k in low for k in keys):
            return reg
    return "general"


def matches_maras(text: str) -> bool:
    low = text.lower()
    return any(re.search(rf"(?<![a-zçğıöşü]){re.escape(k)}", low) for k in MARAS_KEYWORDS)


def search_github_dumps(client: httpx.Client, manifest: dict) -> list[dict]:
    records: list[dict] = []
    gh_headers = {**HEADERS, "Accept": "application/vnd.github+json"}
    queries = ["derleme+sozlugu", "tdk+derleme", "derleme_sozlugu"]
    seen_repos: set[str] = set()
    repo_candidates: list[dict] = []

    for q in queries:
        try:
            r = client.get(
                f"https://api.github.com/search/repositories?q={q}&per_page=10",
                headers=gh_headers,
                timeout=20,
            )
            manifest["github_searches"].append({"query": q, "status": r.status_code})
            if r.status_code != 200:
                continue
            for item in r.json().get("items", []):
                full_name = item.get("full_name", "")
                if full_name and full_name not in seen_repos:
                    seen_repos.add(full_name)
                    repo_candidates.append(
                        {
                            "full_name": full_name,
                            "default_branch": item.get("default_branch", "main"),
                            "size": item.get("size", 0),
                            "description": item.get("description", ""),
                        }
                    )
            time.sleep(0.6)
        except Exception as exc:
            manifest["github_searches"].append({"query": q, "error": str(exc)})

    for repo in repo_candidates[:12]:
        fn = repo["full_name"]
        br = repo["default_branch"]
        try:
            tr = client.get(
                f"https://api.github.com/repos/{fn}/git/trees/{br}?recursive=1",
                headers=gh_headers,
                timeout=20,
            )
            if tr.status_code != 200:
                continue
            tree = tr.json().get("tree", [])
            data_files = [
                f for f in tree
                if f.get("type") == "blob"
                and f.get("size", 0) > 10_000
                and f.get("size", 0) < 60_000_000
                and Path(f["path"]).suffix.lower() in {".json", ".jsonl", ".csv", ".tsv"}
                and any(tok in f["path"].lower() for tok in ("derleme", "sozluk", "tdk", "data", "kelime", "maras"))
            ]
            for df in data_files[:3]:
                raw_url = f"https://raw.githubusercontent.com/{fn}/{br}/{df['path']}"
                resp = client.get(raw_url, timeout=45)
                if resp.status_code != 200:
                    continue
                extracted = parse_dump_bytes(resp.content, df["path"], f"github:{fn}/{df['path']}")
                manifest["github_files_checked"].append(
                    {"url": raw_url, "bytes": len(resp.content), "maras_matches": len(extracted)}
                )
                records.extend(extracted)
            time.sleep(0.5)
        except Exception as exc:
            manifest["github_files_checked"].append({"repo": fn, "error": str(exc)})
    return records


def parse_dump_bytes(content: bytes, filename: str, source_tag: str) -> list[dict]:
    out: list[dict] = []
    text = content.decode("utf-8", errors="replace")
    ext = Path(filename).suffix.lower()

    if ext == ".jsonl":
        for line in text.splitlines():
            if not line.strip() or not matches_maras(line):
                continue
            try:
                obj = json.loads(line)
                out.append(normalize_dict_record(obj, source_tag))
            except Exception:
                continue
    elif ext == ".json":
        try:
            data = json.loads(text)
            items = data if isinstance(data, list) else (
                data.get("data") or data.get("words") or data.get("items") or list(data.values())
            )
            if isinstance(items, list):
                for obj in items:
                    if isinstance(obj, dict):
                        blob = json.dumps(obj, ensure_ascii=False)
                        if matches_maras(blob):
                            out.append(normalize_dict_record(obj, source_tag))
        except Exception:
            pass
    elif ext in {".csv", ".tsv"}:
        delim = "\t" if ext == ".tsv" else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delim)
        for row in reader:
            blob = " ".join(str(v) for v in row.values() if v)
            if matches_maras(blob):
                out.append(normalize_dict_record(row, source_tag))
    return [r for r in out if r.get("term") and r.get("meaning")]


def normalize_dict_record(obj: dict, source_tag: str) -> dict:
    term = (
        obj.get("madde")
        or obj.get("kelime")
        or obj.get("word")
        or obj.get("term")
        or obj.get("sozcuk")
        or ""
    )
    meaning = (
        obj.get("anlam")
        or obj.get("meaning")
        or obj.get("aciklama")
        or obj.get("tanim")
        or ""
    )
    if not meaning and isinstance(obj.get("anlamlarListe"), list):
        meaning = "; ".join(str(a.get("anlam", "")) for a in obj["anlamlarListe"] if isinstance(a, dict))
    location = (
        obj.get("yore")
        or obj.get("il")
        or obj.get("ilce")
        or obj.get("sehir")
        or obj.get("region")
        or obj.get("derleme_yeri")
        or ""
    )
    example = obj.get("ornek") or obj.get("example") or ""
    blob = f"{location} {meaning} {example}"
    return {
        "term": str(term).strip(),
        "meaning": str(meaning).strip(),
        "examples": [str(example).strip()] if str(example).strip() else [],
        "location_raw": str(location).strip(),
        "region": detect_region(blob),
        "source": source_tag,
    }


def probe_sozluk_gov_tr(client: httpx.Client, manifest: dict) -> list[dict]:
    records: list[dict] = []
    endpoints = [
        ("derleme", "https://sozluk.gov.tr/derleme?ara={term}"),
        ("lehceler", "https://sozluk.gov.tr/lehceler?ara={term}"),
    ]

    # First check homepage & endpoint discovery
    working_template = None
    for name, tmpl in endpoints:
        try:
            test_url = tmpl.format(term="bayak")
            resp = client.get(test_url, timeout=15)
            manifest["sozluk_probes"].append({"endpoint": name, "status": resp.status_code, "sample": resp.text[:250]})
            if resp.status_code == 200 and resp.text.strip().startswith(("[", "{")) and "error" not in resp.text[:80].lower():
                working_template = (name, tmpl)
                break
        except Exception as exc:
            manifest["sozluk_probes"].append({"endpoint": name, "error": str(exc)})

    if not working_template:
        # Inspect main HTML/JS for derleme endpoint
        try:
            home = client.get("https://sozluk.gov.tr/", timeout=15)
            manifest["sozluk_home_status"] = home.status_code
            js_urls = re.findall(r'src="([^"]+\.js[^"]*)"', home.text)
            for j in js_urls[:6]:
                full_j = j if j.startswith("http") else f"https://sozluk.gov.tr/{j.lstrip('/')}"
                jr = client.get(full_j, timeout=15)
                found_eps = re.findall(r'["\']/?(derleme[^"\']*|tarama[^"\']*)["\']', jr.text)
                if found_eps:
                    manifest["discovered_js_endpoints"] = list(set(found_eps))[:10]
        except Exception as exc:
            manifest["sozluk_home_error"] = str(exc)
        return records

    ep_name, tmpl = working_template
    # Collect any extra terms from already-extracted texts or glossaries if present
    terms = list(dict.fromkeys(SEED_WORDS))
    for term in terms:
        try:
            resp = client.get(tmpl.format(term=term), timeout=15)
            if resp.status_code in (403, 429):
                manifest["sozluk_rate_limited"] = True
                break
            if resp.status_code != 200:
                continue
            data = resp.json()
            if isinstance(data, list):
                for entry in data:
                    blob = json.dumps(entry, ensure_ascii=False)
                    if matches_maras(blob):
                        rec = normalize_dict_record(entry, f"sozluk.gov.tr/{ep_name}")
                        if not rec["term"]:
                            rec["term"] = term
                        if rec["meaning"]:
                            records.append(rec)
            time.sleep(0.35)
        except Exception:
            continue
    return records


def main() -> None:
    TDK_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "github_searches": [],
        "github_files_checked": [],
        "sozluk_probes": [],
        "seed_words_count": len(SEED_WORDS),
    }

    all_records: list[dict] = []
    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        gh_records = search_github_dumps(client, manifest)
        all_records.extend(gh_records)
        tdk_records = probe_sozluk_gov_tr(client, manifest)
        all_records.extend(tdk_records)

    # Deduplicate by (term.lower(), meaning[:60].lower())
    seen = set()
    unique: list[dict] = []
    for r in all_records:
        key = (r["term"].lower(), r["meaning"][:60].lower())
        if key not in seen and r["term"] and r["meaning"]:
            seen.add(key)
            unique.append(r)

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in unique:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest["total_unique_records"] = len(unique)
    manifest["from_github"] = len(gh_records)
    manifest["from_sozluk_gov_tr"] = len(tdk_records)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"TDK collector finished: {len(unique)} Kahramanmaraş records saved to {OUT_JSONL}")


if __name__ == "__main__":
    main()

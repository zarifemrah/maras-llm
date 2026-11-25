#!/usr/bin/env python3
"""Parse, normalize, deduplicate, and inventory all collected Kahramanmaraş dialect
sources into data/processed/:
  - lexicon.jsonl
  - dialect_texts.jsonl
  - grammar_notes.md
  - inventory_report.md
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DP_TEXTS = BASE_DIR / "data" / "raw" / "dergipark" / "texts"
RAW_DP_MANIFEST = BASE_DIR / "data" / "raw" / "dergipark" / "manifest.json"
RAW_TDK_JSONL = BASE_DIR / "data" / "raw" / "tdk" / "maras_derleme.jsonl"
RAW_GLOSS_JSONL = BASE_DIR / "data" / "raw" / "glossaries" / "maras_glossaries.jsonl"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

PHONETIC_BASE_MAP = str.maketrans({
    "ā": "a", "ă": "a", "á": "a", "â": "a", "ä": "a", "ã": "a", "å": "a",
    "Ā": "A", "Ă": "A", "Á": "A", "Â": "A",
    "ē": "e", "ĕ": "e", "ė": "e", "é": "e", "è": "e", "ê": "e", "ě": "e",
    "Ē": "E", "Ė": "E", "É": "E",
    "ī": "i", "ĭ": "i", "î": "i", "ì": "i",
    "í": "ı", "Í": "I",
    "ō": "o", "ŏ": "o", "ó": "o", "ô": "o", "õ": "o", "ṑ": "o", "ṓ": "o",
    "Ō": "O", "Ó": "O", "Ṓ": "O",
    "ȫ": "ö", "Ȫ": "Ö",
    "ū": "u", "ŭ": "u", "ú": "u", "û": "u",
    "ǖ": "ü", "ǚ": "ü",
    "ḳ": "k", "ḵ": "k", "Ḳ": "K", "Ḵ": "K", "κ": "k",
    "ḫ": "h", "ḥ": "h", "Ḫ": "H",
    "ŋ": "n", "ñ": "n", "ŉ": "n",
    "ǥ": "g",
    "ż": "z", "ẕ": "z",
    "Ģ": "Ş",
    "„": "'", "‟": "'",
    "’": "'", "‘": "'", "“": "\"", "”": "\"",
})

# Specific box-drawing / symbol substitutions observed in 03_ (Kirik 2025 Turkoğlu PDF)
KIRIK_03_MAP = str.maketrans({
    "ļ": "l",
    "└": "n",
    "╧": "k",
    "─": "ğ",
    "┌": "ğ",
    "╒": "ğ",
    "Ω": " ",
    "┬": "i",
    "║": "ü",
    "╦": "z",
    "♠": "ı",
    "ñ": "n",
    "£": "ok",
})


def normalize_midword_caps(s: str) -> str:
    # Academic transcriptions sometimes use mid-word K/F/T/P/C/B/D for half-voiced stops
    return re.sub(r"(?<=[a-zçğıöşü])([KFTPCBDG])(?=[a-zçğıöşü])", lambda m: m.group(1).lower(), s)


def normalize_turkoglu_03(text: str) -> str:
    s = text.replace("£", "ok").replace("®", "a")
    s = s.translate(KIRIK_03_MAP)
    s = s.translate(PHONETIC_BASE_MAP)
    # In 03_, ġ is voiced g (ġadın -> gadın)
    s = s.replace("ġ", "g").replace("Ġ", "G")
    s = normalize_midword_caps(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_afsin_15(text: str) -> str:
    # In 15_, Ģ is ş, Ġ is İ, and ġ is Ş at start of ALL-CAPS/sentence-initial standard words,
    # otherwise voiced g in dialect words (ġızım -> gızım).
    s = text.replace("Ģ", "ş")
    s = re.sub(r"\b([A-ZÇĞIİÖŞÜ]{1,}[A-ZÇĞIİÖŞÜġ]*?)ġ([A-ZÇĞIİÖŞÜġ]*)\b", lambda m: f"{m.group(1)}Ş{m.group(2)}", s)
    s = re.sub(r"(?:(?<=^)|(?<=\.\s)|(?<=:\s))ġ(indiki|ey|iir|imdi|öyle|\.)", lambda m: "Ş" + m.group(1), s)
    s = s.replace("ġ", "g")
    s = s.replace("Ġ", "İ")
    s = s.translate(PHONETIC_BASE_MAP)
    s = normalize_midword_caps(s)
    s = re.sub(r"[\uf000-\uf0ff]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_general_dialect(text: str) -> str:
    s = text.translate(PHONETIC_BASE_MAP)
    s = s.replace("ġ", "g").replace("Ġ", "G")
    s = re.sub(r"[:ː]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_line_pages(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        l = raw.strip()
        if not l or l.startswith("--- PAGE "):
            continue
        if re.fullmatch(r"\d{1,4}", l) or re.fullmatch(r"\[\d{1,4}\]", l) or re.fullmatch(r"\|\s*\d+\s*\|", l):
            continue
        if re.fullmatch(r"[ivxlcdm]+", l.lower()):
            continue
        lines.append(l)
    return lines


def strip_page_refs(text: str) -> str:
    s = re.sub(r"\(s\.\s*\d+(?:-\d+)?\)", "", text)
    s = re.sub(r"\(\d+-\d+\)", "", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;")
    return s


def parse_telli_katkilar(path: Path, source_tag: str) -> tuple[list[dict], list[dict]]:
    """Parse 04_ and 07_ (Telli & Aslan 2023 Katkılar-1 and Katkılar-2)."""
    lines = clean_line_pages(path.read_text(encoding="utf-8"))
    # Merge wrapped lines carefully while stopping at KAYNAKÇA / KAYNAKLAR
    merged: list[str] = []
    entry_start_re = re.compile(r"^[a-zçğıöşüâîû'’\-\s]{2,45}:\s+.+")
    for l in lines:
        if re.match(r"^(KAYNAKÇA|KAYNAKLAR|SONUÇ)\b", l, re.I):
            if l.upper().startswith("KAYNAK"):
                break
        if any(hdr in l for hdr in ("Edebî Eleştiri Dergisi", "ASYA STUDIES", "Burak Telli", "Büşranur Aslan")):
            continue
        if entry_start_re.match(l):
            merged.append(l)
        elif merged and not re.match(r"^\d+\.\d+\.", l):
            # Continuation line for previous entry if previous line didn't end with page ref or looks wrapped
            if not merged[-1].endswith(")") or not re.search(r"\(s\.\s*\d+\)\s*$", merged[-1]):
                merged[-1] = f"{merged[-1]} {l}"

    lexicon: list[dict] = []
    for item in merged:
        m = re.match(r"^([^:]{2,45}):\s+(.+)$", item)
        if not m:
            continue
        term = m.group(1).strip().strip("\"'“”•-*")
        meaning = strip_page_refs(m.group(2))
        if len(term.split()) > 5 or len(meaning) < 3 or len(meaning) > 450:
            continue
        if any(bad in term.lower() for bad in ("atıf", "citation", "doi", "http", "orcid", "öz", "abstract", "anahtar", "heading", "keyword", "giriş")):
            continue
        if any(bad in meaning.lower() for bad in ("keywords:", "orcid:", "compilation dictionary", "geliş tarihi")):
            continue
        lexicon.append({
            "term": term,
            "normalized_term": normalize_general_dialect(term),
            "meaning": meaning,
            "examples": [],
            "region": "general",
            "source": source_tag,
        })
    return lexicon, []


def parse_kirik_turkoglu_03(path: Path) -> tuple[list[dict], list[dict]]:
    """Parse 03_ (Kirik 2025 Türkoğlu) structured entries + [Türkoğlu...] example sentences."""
    lines = clean_line_pages(path.read_text(encoding="utf-8"))
    lexicon: list[dict] = []
    texts: list[dict] = []

    pos_re = re.compile(
        r"^(.{2,45}?)\s+(i\.|sf\.|zf\.|f\.|ünl\.|bağ\.|ed\.|zm\.)\s*(?:mec\.\s*)?(.+)$"
    )
    ex_re = re.compile(r"^(.+?)\s*\[(Türkoğlu[^\]]*)\]\s*$")

    current_entry: dict | None = None
    in_kaynak = False
    for l in lines:
        if re.match(r"^(KAYNAKÇA|KAYNAKLAR)\b", l, re.I):
            in_kaynak = True
        if in_kaynak:
            continue
        if any(h in l for h in ("Bingöl Üniversitesi", "Esra KİRİK", "Kirik, E. (2025)")):
            continue

        em = ex_re.match(l)
        if em:
            raw_ex = em.group(1).strip()
            loc = em.group(2).strip()
            norm_ex = normalize_turkoglu_03(raw_ex)
            if len(norm_ex) >= 12 and not any(
                meta in norm_ex.lower() for meta in ("belirtilerek", "gösterilmiştir", "sözcüğün", "derleme sözlüğü", "mahallelerinden")
            ):
                texts.append({
                    "raw_text": raw_ex,
                    "normalized_text": norm_ex,
                    "standard_tr_gloss": "",
                    "region": "turkoglu",
                    "source": f"dergipark:kirik-2025 ({loc})",
                })
                if current_entry is not None:
                    current_entry["examples"].append(norm_ex)
            continue

        pm = pos_re.match(l)
        if pm:
            term_raw = pm.group(1).strip().strip("\"'“”•-*")
            if len(term_raw.split()) <= 4 and not any(c.isdigit() for c in term_raw):
                meaning = re.sub(r"^\d+\.\s*", "", pm.group(3)).strip()
                current_entry = {
                    "term": term_raw,
                    "normalized_term": normalize_turkoglu_03(term_raw),
                    "meaning": normalize_turkoglu_03(meaning),
                    "examples": [],
                    "region": "turkoglu",
                    "source": "dergipark:kirik-2025-turkoglu",
                }
                lexicon.append(current_entry)
                continue

        # Second numbered sense like "2. f. mec. ..."
        m2 = re.match(r"^(\d+)\.\s+(?:i\.|sf\.|zf\.|f\.|ünl\.)\s*(?:mec\.\s*)?(.+)$", l)
        if m2 and current_entry is not None:
            current_entry["meaning"] += f"; {m2.group(1)}. {normalize_turkoglu_03(m2.group(2))}"

    return lexicon, texts


def parse_eski_turkce_06(path: Path) -> list[dict]:
    """Parse 06_ (Esma Türkoğlu 2024) entries: 'x (ET) / y (KA): ... Kahramanmaraş ağzında \"...\"'."""
    lines = clean_line_pages(path.read_text(encoding="utf-8"))
    # Join into paragraphs split on entries matching '(ET) /'
    entries_raw: list[str] = []
    for l in lines:
        if re.match(r"^(KAYNAKÇA|KAYNAKLAR|SONUÇ)\b", l, re.I) and l.upper().startswith("KAYNAK"):
            break
        if any(h in l for h in ("Cihanşümul Akademi", "Journal of Cihanşümul")):
            continue
        if "(ET) /" in l or "(ET)/" in l:
            entries_raw.append(l)
        elif entries_raw and not re.match(r"^\d+\.\d+\.", l):
            entries_raw[-1] = f"{entries_raw[-1]} {l}"

    lexicon: list[dict] = []
    pat = re.compile(r"^.{1,35}?\(ET\)\s*/\s*([^(]{1,35}?)\s*\(KA\)\s*:\s*(.+)$")
    for raw in entries_raw:
        m = pat.match(raw)
        if not m:
            continue
        ka_term = m.group(1).strip()
        body = m.group(2)
        ka_m = re.search(r"Kahramanmaraş ağzında\s*[“\"]([^”\"]+)[”\"]", body)
        if ka_m:
            meaning = ka_m.group(1).strip()
        else:
            meaning = re.sub(r"\([^)]*\d{4}[^)]*\)", "", body).strip()[:180]
        if ka_term and meaning:
            lexicon.append({
                "term": ka_term,
                "normalized_term": normalize_general_dialect(ka_term),
                "meaning": normalize_general_dialect(meaning),
                "examples": [],
                "region": "general",
                "source": "dergipark:turkoglu-2024-eski-turkce",
            })
    return lexicon


def parse_afsin_15(path: Path) -> tuple[list[dict], list[dict]]:
    """Parse 15_ (Kaya 2017 Afşin thesis) EK 1: METİNLER and EK 2: SÖZLÜK."""
    lines = path.read_text(encoding="utf-8").splitlines()
    metin_start = None
    sozluk_start = None
    for i, l in enumerate(lines):
        s = l.strip()
        if s in ("EK 1: METĠNLER", "EK 1: METİNLER") and i > 1000:
            metin_start = i
        elif s in ("EK 2: SÖZLÜK", "EK 2: SÖZÜK") and i > 5000:
            sozluk_start = i

    lexicon: list[dict] = []
    texts: list[dict] = []

    if sozluk_start:
        s_lines = []
        for raw in lines[sozluk_start + 1 :]:
            l = raw.strip()
            if not l or l.startswith("--- PAGE ") or re.fullmatch(r"\d{1,4}", l) or re.fullmatch(r"-[A-ZÇĞIİÖŞÜ]-", l):
                continue
            s_lines.append(l)
        merged: list[str] = []
        for l in s_lines:
            if ":" in l and len(l.split(":", 1)[0].strip()) <= 35:
                merged.append(l)
            elif merged:
                merged[-1] = f"{merged[-1]} {l}"
        for item in merged:
            term_raw, mean_raw = item.split(":", 1)
            term_raw = term_raw.strip()
            mean_clean = strip_page_refs(normalize_afsin_15(mean_raw))
            if len(term_raw) >= 2 and len(mean_clean) >= 2 and len(term_raw.split()) <= 4:
                lexicon.append({
                    "term": term_raw,
                    "normalized_term": normalize_afsin_15(term_raw),
                    "meaning": mean_clean,
                    "examples": [],
                    "region": "afsin",
                    "source": "emu:kaya-2017-afsin",
                })

    if metin_start and sozluk_start:
        # Group into narrative chunks by speaker/story (-1-, -2-, ...) and extract clean prose sentences
        story_buf: list[str] = []
        current_loc = "Afşin"
        stories: list[tuple[str, str]] = []
        for raw in lines[metin_start + 1 : sozluk_start]:
            l = raw.strip()
            if not l or l.startswith("--- PAGE ") or re.fullmatch(r"\d{1,4}", l):
                continue
            if re.fullmatch(r"-\d{1,3}-", l):
                if story_buf:
                    stories.append((current_loc, " ".join(story_buf)))
                    story_buf = []
                continue
            if l.startswith("Anlatan:") or re.fullmatch(r"\d{1,3}\s*ya[şġĢ]", l, re.I):
                continue
            if l.startswith("Derleme yeri:"):
                current_loc = normalize_afsin_15(l.split(":", 1)[1].strip()) or "Afşin"
                continue
            story_buf.append(l)
        if story_buf:
            stories.append((current_loc, " ".join(story_buf)))

        for loc, raw_story in stories:
            norm_story = normalize_afsin_15(raw_story)
            # Split into natural 1-3 sentence chunks (between 40 and 320 chars)
            sents = re.split(r"(?<=[.!?])\s+", norm_story)
            raw_sents = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", raw_story).strip())
            buf_n: list[str] = []
            buf_r: list[str] = []
            for idx, s in enumerate(sents):
                s = s.strip()
                r = raw_sents[idx].strip() if idx < len(raw_sents) else s
                if len(s) < 12:
                    continue
                buf_n.append(s)
                buf_r.append(r)
                joined = " ".join(buf_n)
                if len(joined) >= 110:
                    if len(joined) <= 450:
                        texts.append({
                            "raw_text": " ".join(buf_r),
                            "normalized_text": joined,
                            "standard_tr_gloss": "",
                            "region": "afsin",
                            "source": f"emu:kaya-2017-afsin ({loc})",
                        })
                    buf_n, buf_r = [], []
            if buf_n and 40 <= len(" ".join(buf_n)) <= 450:
                texts.append({
                    "raw_text": " ".join(buf_r),
                    "normalized_text": " ".join(buf_n),
                    "standard_tr_gloss": "",
                    "region": "afsin",
                    "source": f"emu:kaya-2017-afsin ({loc})",
                })

    return lexicon, texts


def parse_gultekin_09(path: Path) -> list[dict]:
    """Extract attested multi-word Kahramanmaraş example phrases from Gültekin 2005."""
    txt = path.read_text(encoding="utf-8")
    texts: list[dict] = []
    for m in re.finditer(r"([a-zçğıöşüâîûŋġķėāōūī\s,'’-]{8,70})\((KA[HSY])\)", txt):
        phrase = m.group(1).strip(" ,;:")
        tag = m.group(2)
        norm = normalize_general_dialect(phrase)
        if len(norm.split()) >= 2 and len(norm) >= 10:
            texts.append({
                "raw_text": phrase,
                "normalized_text": norm,
                "standard_tr_gloss": "",
                "region": "merkez" if tag == "KAH" else "general",
                "source": f"dergipark:gultekin-2005 ({tag})",
            })
    return texts


def parse_glossaries() -> tuple[list[dict], list[dict]]:
    lexicon: list[dict] = []
    texts: list[dict] = []
    if not RAW_GLOSS_JSONL.exists():
        return lexicon, texts
    for line in RAW_GLOSS_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("kind") == "lexicon":
            term = obj.get("term", "").strip()
            meaning = obj.get("meaning", "").strip()
            if not term or not meaning or len(term) > 55 or len(term.split()) > 6:
                continue
            # Filter obvious blog navigation/noise or Latin taxonomy lines
            if any(bad in term.lower() for bad in ("ara:", "etiket", "kategori", "yorum", "paylaş", "http")):
                continue
            if re.search(r"\b[A-Z]{4,}\s+[A-Z]{4,}\b", f"{term} {meaning}"):
                continue
            # Extract inline example if marked with " - " or " – " inside meaning
            examples = list(obj.get("examples") or [])
            ex_split = re.split(r"\s+[-–]\s+(?=[A-ZÇĞİÖŞÜ\"'“\-])", meaning, maxsplit=1)
            clean_meaning = ex_split[0].strip()
            if len(ex_split) == 2 and len(ex_split[1].strip()) >= 8:
                ex_txt = ex_split[1].strip()
                examples.append(ex_txt)
                texts.append({
                    "raw_text": ex_txt,
                    "normalized_text": normalize_general_dialect(ex_txt),
                    "standard_tr_gloss": f"{term}: {clean_meaning}",
                    "region": obj.get("region", "general"),
                    "source": obj.get("source", "web:glossary"),
                })
            lexicon.append({
                "term": term,
                "normalized_term": normalize_general_dialect(term),
                "meaning": clean_meaning,
                "examples": examples,
                "region": obj.get("region", "general"),
                "source": obj.get("source", "web:glossary"),
            })
        elif obj.get("kind") == "text":
            raw_t = obj.get("raw_text", "").strip()
            if re.search(r"\b[A-Z]{4,}\s+[A-Z]{4,}\b", raw_t):
                continue
            if len(raw_t.split()) < 3 and not any(
                mk in raw_t.lower() for mk in ("nootiin", "bayak", "edem", "gardaş", "heç", "bıldır", "heri")
            ):
                continue
            if 10 <= len(raw_t) <= 450:
                texts.append({
                    "raw_text": raw_t,
                    "normalized_text": normalize_general_dialect(raw_t),
                    "standard_tr_gloss": "",
                    "region": obj.get("region", "general"),
                    "source": obj.get("source", "web:glossary"),
                })
    return lexicon, texts


def parse_ansiklopedi46_lugat() -> tuple[list[dict], list[dict]]:
    """Parse Kahramanmaraş Merkez vocabulary (Lügatçemiz / Özturan 2009) and
    Kılıç (2008) Merkez sample narrative from ansiklopedi46_com_tr_kahramanmaras_agzi.html.
    """
    html_path = BASE_DIR / "data" / "raw" / "glossaries" / "html" / "ansiklopedi46_com_tr_kahramanmaras_agzi.html"
    if not html_path.exists():
        return [], []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    for t in soup(["script", "style", "nav", "footer", "header"]):
        t.decompose()
    main = soup.select_one("article, .entry-content, main") or soup.body
    lines = [l.strip() for l in main.get_text("\n").splitlines() if l.strip()]

    lexicon: list[dict] = []
    texts: list[dict] = []

    # 1. Extract Kılıç 2008 Merkez oral text sentences if present
    in_kilic = False
    kilic_buf: list[str] = []
    for l in lines:
        if "Aşağıda ağızdan derlenmiş olan metin" in l:
            in_kilic = True
            continue
        if in_kilic:
            if l.startswith("Lügatçemiz"):
                break
            kilic_buf.append(l)
    if kilic_buf:
        raw_kilic = " ".join(kilic_buf).strip("“”\" ")
        raw_kilic = re.sub(r"\(Kılıç,\s*2008:\d+\)", "", raw_kilic).strip()
        norm_kilic = normalize_general_dialect(raw_kilic.replace("ñ", "n"))
        for sent in re.split(r"(?<=[.!?])\s+", norm_kilic):
            if len(sent) >= 30:
                texts.append({
                    "raw_text": sent,
                    "normalized_text": sent,
                    "standard_tr_gloss": "",
                    "region": "merkez",
                    "source": "web:ansiklopedi46-kilic-2008",
                })

    # 2. Extract Kahramanmaraş Ağzının Kelime Haznesi entries (term:\ndefinition)
    start_idx = None
    end_idx = len(lines)
    for i, l in enumerate(lines):
        if "Aşağıda Kahramanmaraş ağzında kullanılan bazı kelimelere yer verilmiştir" in l:
            start_idx = i + 1
        elif start_idx and l.startswith("Kullanılan Çevriyazı İşaretleri"):
            end_idx = i
            break

    if start_idx is not None:
        i = start_idx
        while i < end_idx:
            cur = lines[i]
            if cur.endswith(":") and len(cur) <= 42 and i + 1 < end_idx:
                term_raw = cur[:-1].strip()
                meaning_raw = lines[i + 1].strip()
                # Join wrapped lines until next 'Term:'
                j = i + 2
                while j < end_idx and not (lines[j].endswith(":") and len(lines[j]) <= 42):
                    meaning_raw = f"{meaning_raw} {lines[j].strip()}"
                    j += 1
                norm_term = normalize_general_dialect(term_raw.replace("ñ", "n"))
                norm_mean = normalize_general_dialect(meaning_raw.replace("ñ", "n"))
                if len(norm_term) >= 2 and len(norm_mean) >= 2 and len(norm_term.split()) <= 4:
                    lexicon.append({
                        "term": term_raw,
                        "normalized_term": norm_term,
                        "meaning": norm_mean,
                        "examples": [],
                        "region": "merkez",
                        "source": "web:ansiklopedi46-merkez",
                    })
                i = j
            else:
                i += 1
    return lexicon, texts


def deduplicate_lexicon(items: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for it in items:
        nt = it["normalized_term"].strip()
        mn = it["meaning"].strip()
        if not nt or not mn or len(nt) < 2 or len(mn) < 2:
            continue
        key = (nt.lower(), mn[:45].lower())
        if key not in merged:
            merged[key] = it
        else:
            prev = merged[key]
            for ex in it.get("examples", []):
                if ex not in prev["examples"]:
                    prev["examples"].append(ex)
            if it["source"] not in prev["source"]:
                prev["source"] = f"{prev['source']}; {it['source']}"
    return list(merged.values())


def deduplicate_texts(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        nt = it["normalized_text"].strip()
        if len(nt) < 6:
            continue
        key = nt.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def write_grammar_notes() -> None:
    content = """# Kahramanmaraş Merkez Ağzı — Ses ve Şekil Bilgisi Özeti (Kılıç 2008 & Özturan 2009)

Bu rehber, Kahramanmaraş Merkez ağzına ait birincil çalışmalardan (Kılıç 2008; Özturan 2009; Gültekin 2005; Kirik 2022-2026) derlenen temel ses, ek ve sözcük kurallarını günlük okunabilir Türkçe sohbet yazımına uyarlar.

## 1. Fiil Çekimleri (Merkez Kimliği)
* **Şimdiki Zaman (`-i / -im / -in / -ik / -siz / -iler`):**
  * Standart `-yor` ve genel Anadolu `-iyo` ekleri yerine Merkez'de **`-i`** eki esastır:
  * 1. tekil (`-im / -mim`): *dinlim, bilmim, söylemim, gidim, gelim, bahim, saymim*.
  * 2. tekil (`-in / -iin / -min`): *nootin, neydin, oturin, gelin, gedin, bahin, alışin*.
  * 3. tekil (`-i / -mi`): *darali, öfkeleni, yaği, oli, geli, gidi, vuri, söyli, anami, biti, eri, sıhıli*.
  * 1. çoğul (`-ik / -mik`): *atamik, gonuşik, çalışmik, edik, gidik, yapik*.
  * 2. çoğul (`-siz / -misiz`): *getmisiz (gitmiyorsunuz), adeleşip durisiz, gelmissiz*.
  * 3. çoğul (`-iler / -ilar`): *yapiler, yatiler, geliler, diyiler*.
  * Geçmiş/hikâye: *bilmidik, satidi, gonuşimiş*; Şart: *erise, kopisa, disen, sevisen*.
* **Gelecek Zaman (`-ıcı / -ici`):**
  * Merkez'de *-(y)AcAk* yanında çok yaygın olarak **`-ıcı / -ici`** kullanılır: *notucum (ne yapacağım), edicim, gelicik, sorucun, verici, alıcık, notucuk, çalışıcık, dönecim*.
* **`-r-l- -> -ll-` Benzeşmesi:**
  * *veriller (verirler), gedeller (giderler), deller (derler), alıllar, toplanıllar, beklellerdi*.
* **Öğrenilen Geçmiş Zaman (`-ık / -ik`):**
  * *yapıksın (yapmışsın), öğreniksin, küsügsün*.
* **1. Çoğul (`-(y)Ik`) ve İstek (`-(y)Ak`):**
  * *giderik, yaparık, baharık, yerik*; istek: *gidek, çay içek, bahak, sorak, notak*.
* **Zarf-Fiiller, Koşaç ve Hal Ekleri:**
  * `-ken -> -kana / -kene`: *çıharhana, iş dutarkana, otururkana, gelirkene*.
  * `-ınca -> -ıncı / -ışın`: *eve gelinci, işden çıhıncı, sohagda görüşün, eve gelişin*.
  * `-arak -> -aragdan / -eregden`: *goşaragdan, güleregden*.
  * `-ce/-ca -> -cene / -cana`: *eyicene, gözelcene*.
  * Yer ek-fiili: *burdiyem, evdiyem, odamdiyem, bahçediyedik*.
  * Sınırlama (`+ça/+çe`): *akşamaça, sabahaça, oriyeçe, geleneçe*.
  * Yönelme daralması: *buriye, oriye, neriye, oynamiye, gonuşmiye*.
  * Vasıta (`-(I)nAn`): *suyunan, sütünen, sözünen, elimizinen, ayağnan, gaşınan*.

## 2. Ses Özellikleri ve Söz Varlığı
* **Düzleşme (Düzlük-Yuvarlaklık):** *yamır (yağmur), hamır, çamır, pambık, avıç, yavrım*.
* **Kelime İçi `k -> h`:** *bahım (bakayım/bakalım), arhadaş, yohuş, dıhılmak, çıhın, vahıt, çoh, yoh, yosa, galhar, sıhılısa, ahşam*.
* **Ötümlüleşme ve Benzeşmesizlik:** *gardaş, gişi, gız, goy-, gat-, gal-, gapı, dut-, daş, dezze, gendi, gonuş-, gaç-; çalışdırır, isdedi, sınıfdan, sabahcı, esgi, eşgi*.
* **Benzeşme ve Göçüşmeler:** *onnar, bunnar, annamadım, günnük, yorgunnuk, gomşular; melmeket, samırsak, eşgili, baldırcan, ireli, cılbak*.
* **Karakteristik Merkez Kelime ve Kalıpları:** *eyi (iyi), eyilik, eyicene, accıg / azcık, bahele, boon (bugün), onüçün (onun için), buadar / oadar / şuadar, hemi de, dedi kine, soora / sona, kelli (sonra), diyal / değel, yoheri! (gerçekten mi!), kele, tavatır (çok güzel/abartılı), şor (söz), barabar, habar, madanız, motur, doktur, ezen, ecele, tene, güccük, döşşek, süllüm (merdiven), püsük (kedi), saho (ceket), salık (haber), sındı (makas), şo, yekinmek, zırpadak, amma, he, yav, edem, ede, gadan alım, aba, bibi, emmi, bayak / debiyak, bıldır, horanta, hanek, dinelmek, böğsümek, ağnanmak, arıstak, çimmek, malamat, nizah, ığdırık, adeleşmek, cıncık, çomça, mırhız, lavlavı, gartaşık, bon, kıyak, peh, tama, ola, hele*.
"""
    (PROCESSED_DIR / "grammar_notes.md").write_text(content, encoding="utf-8")


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    all_lex: list[dict] = []
    all_txt: list[dict] = []

    # 1. Glossaries + Ansiklopedi46 Merkez Lügatçemiz
    g_lex, g_txt = parse_glossaries()
    all_lex.extend(g_lex)
    all_txt.extend(g_txt)

    a_lex, a_txt = parse_ansiklopedi46_lugat()
    all_lex.extend(a_lex)
    all_txt.extend(a_txt)

    # 2. TDK (if present)
    if RAW_TDK_JSONL.exists():
        for l in RAW_TDK_JSONL.read_text(encoding="utf-8").splitlines():
            if l.strip():
                obj = json.loads(l)
                all_lex.append({
                    "term": obj["term"],
                    "normalized_term": normalize_general_dialect(obj["term"]),
                    "meaning": obj["meaning"],
                    "examples": obj.get("examples", []),
                    "region": obj.get("region", "general"),
                    "source": obj.get("source", "tdk"),
                })

    # 3. DergiPark / Institutional PDFs
    pdf_files_parsed = []
    for p in sorted(RAW_DP_TEXTS.glob("*.txt")):
        name = p.name
        if name.startswith("04_"):
            lx, tx = parse_telli_katkilar(p, "dergipark:telli-aslan-2023-1")
            all_lex.extend(lx)
            all_txt.extend(tx)
            pdf_files_parsed.append((name, len(lx), len(tx)))
        elif name.startswith("07_"):
            lx, tx = parse_telli_katkilar(p, "dergipark:telli-aslan-2023-2")
            all_lex.extend(lx)
            all_txt.extend(tx)
            pdf_files_parsed.append((name, len(lx), len(tx)))
        elif name.startswith("03_"):
            lx, tx = parse_kirik_turkoglu_03(p)
            all_lex.extend(lx)
            all_txt.extend(tx)
            pdf_files_parsed.append((name, len(lx), len(tx)))
        elif name.startswith("06_"):
            lx = parse_eski_turkce_06(p)
            all_lex.extend(lx)
            pdf_files_parsed.append((name, len(lx), 0))
        elif name.startswith("09_"):
            tx = parse_gultekin_09(p)
            all_txt.extend(tx)
            pdf_files_parsed.append((name, 0, len(tx)))
        elif name.startswith("15_"):
            lx, tx = parse_afsin_15(p)
            all_lex.extend(lx)
            all_txt.extend(tx)
            pdf_files_parsed.append((name, len(lx), len(tx)))

    lex_dedup = deduplicate_lexicon(all_lex)
    txt_dedup = deduplicate_texts(all_txt)

    with (PROCESSED_DIR / "lexicon.jsonl").open("w", encoding="utf-8") as f:
        for row in lex_dedup:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with (PROCESSED_DIR / "dialect_texts.jsonl").open("w", encoding="utf-8") as f:
        for row in txt_dedup:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_grammar_notes()

    # Build inventory report
    dp_manifest = json.loads(RAW_DP_MANIFEST.read_text(encoding="utf-8")) if RAW_DP_MANIFEST.exists() else {}
    lex_by_src = Counter(r["source"].split(";")[0] for r in lex_dedup)
    lex_by_reg = Counter(r["region"] for r in lex_dedup)
    txt_by_src = Counter(r["source"].split(" (")[0] for r in txt_dedup)
    txt_by_reg = Counter(r["region"] for r in txt_dedup)

    # Pick diverse samples
    sample_lex = []
    for src_prefix in ("web:marasavucumda", "dergipark:telli-aslan", "dergipark:kirik-2025", "dergipark:turkoglu-2024", "emu:kaya-2017"):
        picked = [r for r in lex_dedup if r["source"].startswith(src_prefix)][:4]
        sample_lex.extend(picked)

    sample_txt = []
    for src_prefix in ("web:marasavucumda", "dergipark:gultekin-2005", "dergipark:kirik-2025", "emu:kaya-2017"):
        picked = [r for r in txt_dedup if r["source"].startswith(src_prefix)][:4]
        sample_txt.extend(picked)

    lines = [
        "# Kahramanmaraş Ağzı — Phase 1 Corpus Inventory Report",
        "",
        "## 1. Collection Summary",
        f"- **Academic PDFs downloaded:** {dp_manifest.get('downloaded', 0)} / {dp_manifest.get('candidates_found', 0)} discovered via OpenAlex (`{dp_manifest.get('total_pages', 0)}` total pages extracted)",
        f"- **Unique Lexicon Entries (`lexicon.jsonl`):** **{len(lex_dedup)}**",
        f"- **Authentic Dialect Texts & Examples (`dialect_texts.jsonl`):** **{len(txt_dedup)}**",
        "- **TDK `sozluk.gov.tr` status:** `derleme.php` timed out and `/derleme` now serves an SPA frontend; GitHub open dumps had no Derleme Sözlüğü export.",
        "- **DergiPark note:** `/tr/search` presented an `Arama Doğrulama` verification page so search scraping was skipped; open-access articles were discovered via OpenAlex API and downloaded directly.",
        "- **Skipped PDFs during lexicon parsing:** `10_asyatik-turkiye-de-yasam...` (1875 travelogue, non-dialect) and `13_mine-kilic...` (book review with broken custom font encoding). Phonetic-grammar papers (`01_`, `02_`, `05_`) are retained in `data/raw/dergipark/texts/` as grammar references.",
        "",
        "## 2. Breakdown by Source & Region",
        "### Lexicon Entries by Primary Source",
    ]
    for k, v in lex_by_src.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("\n### Lexicon Entries by Region")
    for k, v in lex_by_reg.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("\n### Dialect Texts by Source")
    for k, v in txt_by_src.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("\n### Dialect Texts by Region")
    for k, v in txt_by_reg.most_common():
        lines.append(f"- `{k}`: {v}")

    lines.append("\n## 3. Sample Lexicon Entries (20)")
    for r in sample_lex[:20]:
        lines.append(f"- **{r['normalized_term']}** (`{r['region']}`, *{r['source']}*): {r['meaning']}")

    lines.append("\n## 4. Sample Authentic Dialect Sentences & Excerpts")
    for r in sample_txt[:16]:
        lines.append(f"- **[{r['region']}]** {r['normalized_text']} *(raw: `{r['raw_text'][:90]}`)*")

    lines.append(
        "\n## 5. Recommended Phase 2 Options\n"
        "1. **Build the Chat Dataset (`data/chat/{train,valid,test}.jsonl`):** Convert the authentic texts + lexicon into ~800–1,500 natural Kahramanmaraş Merkez multi-turn chat dialogues grounded strictly in `lexicon.jsonl` and `grammar_notes.md`, with a sample for your native speaker spot-check.\n"
        "2. **Optional Extra Authentic Text:** If you download YÖK Tez PDFs manually (e.g., Esra Kırık's *Kahramanmaraş Merkez İlçe Ağzı*) into `data/raw/yok_tez/`, we can parse their *Metinler* section directly into `dialect_texts.jsonl` before generating Phase 2 chat pairs.\n"
        "3. **Prototype MLX QLoRA:** Run `configs/lora_qwen35_9b.yaml` first for fast iteration, then train the final adapter with `configs/lora_gemma3_12b.yaml`."
    )

    (PROCESSED_DIR / "inventory_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Built inventory: {len(lex_dedup)} lexicon entries, {len(txt_dedup)} dialect texts.")


if __name__ == "__main__":
    main()

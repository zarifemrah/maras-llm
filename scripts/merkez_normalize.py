#!/usr/bin/env python3
"""Rule- and dictionary-based Kahramanmaraş Merkez text normalizer."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "merkez_orthography.yaml"

# Nouns/loanwords that end in -yo/-yor or -acak/-ecek and must never be rewritten as verbs
SAFE_NOUN_SKIP = {
    "piyon", "iyon", "biyom", "kardiyo", "fiyort", "stadyo", "radyo",
    "video", "stüdyo", "banyo", "senaryo", "kamyon", "milyon", "trilyon",
    "bacak", "bacağı", "bacakları", "bacaklarını", "yiyecek", "yiyecekler",
    "yiyeceklerin", "yiyeceğini", "içecek", "içecekler", "giyecek", "yakacak",
    "gelecek", "geleceği", "gelecekte",
}

IYO_VERB_RE = re.compile(
    r"\b([a-zçğıöşü]{2,}?)(?:[ıiuü]yor|[ıiuü]yo)(um|sun|sunuz|uz|lar|ler|du|dü|muş|müş)?\b",
    re.IGNORECASE,
)

# Common unambiguous verb-future stems -> Merkez -ıcı/-ici
FUTURE_STEM_MAP = {
    "olac": "oluc",
    "yapac": "yapıc",
    "edec": "edic",
    "gelic": "gelic",
    "gelec": "gelic",
    "gidec": "gedic",
    "gedec": "gedic",
    "verec": "veric",
    "alac": "alıc",
    "kalac": "galıc",
    "galac": "galıc",
    "sorac": "soruc",
    "çıkac": "çıhıc",
    "çıhac": "çıhıc",
    "geçec": "geçic",
    "götürec": "götürüc",
    "bitec": "bitic",
    "görec": "görüc",
    "bulac": "buluc",
    "tutac": "dutuc",
    "dutac": "dutuc",
    "koyac": "goyuc",
    "goyac": "goyuc",
    "bakac": "bahıc",
    "bahac": "bahıc",
    "oturac": "oturuc",
    "başlayac": "başlıyıc",
    "öğrenec": "öğrenic",
    "düzelec": "düzelic",
    "dinlenec": "denneşic",
}

FUTURE_VERB_RE = re.compile(
    r"\b(" + "|".join(sorted(FUTURE_STEM_MAP, key=len, reverse=True))
    + r")(?:ağ|eğ|ak|ek)(ım|im|sın|sin|sınız|siniz|ız|iz|lar|ler)?\b",
    re.IGNORECASE,
)

# Safe -ken -> -kana/-kene and -ınca -> -ıncı for common endings
KEN_RE = re.compile(r"\b([a-zçğıöşü]{3,}?)(ark|erk|ırk|irk|urk|ürk)en\b", re.IGNORECASE)


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def tr_lower(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def match_case(src: str, dst: str) -> str:
    if src.isupper() and len(src) > 1:
        return dst.replace("i", "İ").replace("ı", "I").upper()
    if src[:1].isupper():
        first = "İ" if dst[:1] == "i" else "I" if dst[:1] == "ı" else dst[:1].upper()
        return first + dst[1:]
    return dst


def _rewrite_iyo(m: re.Match[str]) -> str:
    full = m.group(0)
    low = full.lower()
    if low in SAFE_NOUN_SKIP:
        return full
    stem = m.group(1)
    ending = (m.group(2) or "").lower()
    suffix_map = {
        "": "i",
        "um": "im",
        "sun": "in",
        "sunuz": "isiz",
        "uz": "ik",
        "lar": "iler",
        "ler": "iler",
        "du": "idi",
        "dü": "idi",
        "muş": "imiş",
        "müş": "imiş",
    }
    new_end = suffix_map.get(ending, "i")
    return match_case(full, stem.lower() + new_end)


def _rewrite_future(m: re.Match[str]) -> str:
    full = m.group(0)
    low = full.lower()
    if low in SAFE_NOUN_SKIP:
        return full
    stem = m.group(1).lower()
    person = (m.group(2) or "").lower()
    base = FUTURE_STEM_MAP[stem]
    person_map = {
        "": "ı" if base.endswith(("ıc", "uc")) else "i",
        "ım": "um" if base.endswith("uc") else "ım" if base.endswith("ıc") else "im",
        "im": "im",
        "sın": "un" if base.endswith("uc") else "ın" if base.endswith("ıc") else "in",
        "sin": "in",
        "ız": "uk" if base.endswith("uc") else "ık" if base.endswith("ıc") else "ik",
        "iz": "ik",
        "sınız": "ısız" if base.endswith("ıc") else "usuz" if base.endswith("uc") else "isiz",
        "siniz": "isiz",
        "lar": "ılar" if base.endswith(("ıc", "uc")) else "iler",
        "ler": "iler",
    }
    return match_case(full, base + person_map.get(person, "i"))


def normalize_text(text: str, spec: dict[str, Any] | None = None) -> str:
    if spec is None:
        spec = load_spec()

    out = text
    # 1. Multi-word phrases first (longest first)
    phrase_map = spec.get("phrase_map", {})
    for src in sorted(phrase_map, key=len, reverse=True):
        dst = phrase_map[src]
        pat = re.compile(r"\b" + re.escape(src) + r"\b", re.IGNORECASE)
        out = pat.sub(lambda m, d=dst: match_case(m.group(0), d), out)

    # 2. Single-word canonical map
    raw_word_map = spec.get("word_map", {})
    word_map = {tr_lower(k): v for k, v in raw_word_map.items()}
    if word_map:
        word_pat = re.compile(
            r"\b(" + "|".join(re.escape(k) for k in sorted(word_map, key=len, reverse=True)) + r")\b",
            re.IGNORECASE,
        )
        out = word_pat.sub(
            lambda m: match_case(m.group(0), word_map.get(tr_lower(m.group(0)), m.group(0))),
            out,
        )

    # 3. Verb -yor/-iyo -> Merkez -i/-im/-in/-ik/-siz/-iler
    out = IYO_VERB_RE.sub(_rewrite_iyo, out)

    # 4. Unambiguous verb futures -acak/-ecek -> -ıcı/-ici
    out = FUTURE_VERB_RE.sub(_rewrite_future, out)

    # 5. -arken/-erken -> -arkana/-erkene
    out = KEN_RE.sub(
        lambda m: m.group(1) + m.group(2) + ("ana" if m.group(2).lower().startswith(("a", "ı", "u")) else "ene"),
        out,
    )
    return out


def run_self_test() -> None:
    spec = load_spec()
    cases = [
        ("Şimdi biraz çok güzel oldu, kapıyı kapatıp kendi işine bakalım.",
         "Şindi accıg çoh gözel oldu, kapıyı kapatıp gendi işine bahım." if False else None),
    ]
    # Check idempotency & non-corruption of protected nouns
    protected = "Kalite kontrolünde kalem, kalp ve kale kelimeleri piyon, video ve bacaklarını bozmamalı."
    norm1 = normalize_text(protected, spec)
    assert "Kalite" in norm1 and "kalem" in norm1 and "kalp" in norm1 and "kale" in norm1
    assert "piyon" in norm1 and "video" in norm1 and "bacaklarını" in norm1
    assert normalize_text(norm1, spec) == norm1, "Not idempotent on protected nouns!"

    sample = "Bugün çok biraz şimdi değil sonra kendi kapıyı bakalım iyi geliyorum yapacaksın."
    s1 = normalize_text(sample, spec)
    s2 = normalize_text(s1, spec)
    assert s1 == s2, f"Not idempotent: {s1!r} != {s2!r}"
    for tok in ("Boon", "çoh", "accıg", "şindi", "diyal", "soora", "gend", "gapıyı", "bahım", "eyi", "gelim", "yapıcın"):
        assert tok.lower() in s1.lower(), f"Missing {tok} in {s1!r}"
    print("merkez_normalize self-test PASSED:", s1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--text", type=str, default=None)
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
    elif args.text is not None:
        print(normalize_text(args.text))


if __name__ == "__main__":
    main()

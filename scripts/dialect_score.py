#!/usr/bin/env python3
"""Score Kahramanmaraş Merkez dialect consistency and standard-Turkish leakage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "merkez_orthography.yaml"

BANNED_CHARS_RE = re.compile(r"[ŋñḳḵḫėāēīōūȫǖĢĠġ╧└─┌╒Ω┬║╦♠£]")
THINK_RE = re.compile(r"</?think>", re.IGNORECASE)

IYO_RE = re.compile(
    r"\b(?!(?:piyon|iyon|biyom|kardiyo|fiyort|stadyo|radyo|video|stüdyo|banyo|senaryo|kamyon|milyon|trilyon)[a-zçğıöşü]*\b)"
    r"[a-zçğıöşü]+(?:iyo|ıyo|uyo|üyo)"
    r"(?:r[a-zçğıöşü]*|m|n|k|z|lar|ler|sa|se|sun|sunuz|du|dü|muş|müş)?\b",
    re.IGNORECASE,
)

MERKEZ_FEATURE_RE = re.compile(
    r"\b("
    r"eyi\w*|bahım|bahele|boon|onüçün|buadar|oadar|şuadar|burdiyem|evdiyem|"
    r"yamır|hamır|çamır|pambık|noot\w*|notu\w*|notak|notim|neydin|"
    r"yoheri|tavatır|barabar|vahıt|şindi|soora|yosa|diyal|kelli|"
    r"arhadaş\w*|eyicene|gözelcene|süllüm|püsük|saho|salık|sındı|şor|"
    r"dedi kine|hemi de|accıg|melmeket|samırsak|eşgili|baldırcan|"
    r"gendi\w*|gapı\w*|gardaş\w*|gomşu\w*|onnar\w*|bunnar\w*|çoh|yoh|heç|gimi|"
    r"edem|ede|gadan|horanta\w*|hanek\w*|hele|bah|goy\w*|gal\w*|dut\w*|"
    r"valla|yav|peh|tama|ola|bayak\w*|bıldır|mırhız|lavlavı|cıncık|çomça|"
    r"ığdırık|adeleş\w*|malamat|nizah|dinel\w*|denneş\w*|ağnan\w*|böğsü\w*|çim\w*|"
    r"[a-zçğıöşü]+(?:ıcı|ici)(?:m|n|k|z)?|"
    r"[a-zçğıöşü]+(?:llar|ller|llardı|llerdi)|"
    r"[a-zçğıöşü]+(?:kana|kene|ıncı|inci|uncu|üncü|ışın|işin|uşun|üşün)|"
    r"[a-zçğıöşü]+(?:ınan|inen|unan|ünen|ynan|ynen)"
    r")\b",
    re.IGNORECASE,
)


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def score_assistant_turn(
    text: str,
    spec: dict[str, Any] | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    if spec is None:
        spec = load_spec()

    words = re.findall(r"[a-zçğıöşü]+", text.lower())
    word_count = len(words)

    forbidden_words = [w.lower() for w in spec.get("forbidden_standard_words", [])]
    forbidden_re = re.compile(r"\b(" + "|".join(re.escape(w) for w in forbidden_words) + r")\b", re.IGNORECASE)
    drift_words = [w.lower() for w in spec.get("drift_words", [])]
    drift_re = re.compile(r"\b(" + "|".join(re.escape(w) for w in drift_words) + r")\b", re.IGNORECASE)

    leaks: list[str] = []
    leaks.extend(f"std:{m.group(0)}" for m in forbidden_re.finditer(text))
    leaks.extend(f"iyo:{m.group(0)}" for m in IYO_RE.finditer(text))
    leaks.extend(f"drift:{m.group(0)}" for m in drift_re.finditer(text))

    if category == "sozluk_deyim":
        districts = spec.get("non_merkez_districts", [])
        if districts:
            dist_re = re.compile(r"\b(" + "|".join(re.escape(d) for d in districts) + r")\b", re.IGNORECASE)
            leaks.extend(f"district:{m.group(0)}" for m in dist_re.finditer(text))

    if BANNED_CHARS_RE.search(text):
        leaks.append("banned_chars")
    if THINK_RE.search(text):
        leaks.append("think_tag")

    merkez_hits = len(MERKEZ_FEATURE_RE.findall(text))
    leak_count = len(leaks)
    leak_rate = round(100.0 * leak_count / max(word_count, 1), 2)
    passed = leak_count == 0 and merkez_hits >= 1

    return {
        "word_count": word_count,
        "leak_count": leak_count,
        "leak_rate_per_100_words": leak_rate,
        "leaks": leaks,
        "merkez_feature_hits": merkez_hits,
        "passed": passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    spec = load_spec()
    total_turns = 0
    passed_turns = 0
    total_words = 0
    total_leaks = 0
    leak_counter: Counter[str] = Counter()

    for p in args.files:
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            cat = obj.get("_category")
            for m in obj.get("messages", []):
                if m.get("role") == "assistant":
                    res = score_assistant_turn(m["content"], spec=spec, category=cat)
                    total_turns += 1
                    total_words += res["word_count"]
                    total_leaks += res["leak_count"]
                    if res["passed"]:
                        passed_turns += 1
                    for lk in res["leaks"]:
                        leak_counter[lk.lower()] += 1

    summary = {
        "total_assistant_turns": total_turns,
        "passed_turns": passed_turns,
        "pass_pct": round(100.0 * passed_turns / max(total_turns, 1), 2),
        "total_words": total_words,
        "total_leaks": total_leaks,
        "leak_rate_per_100_words": round(100.0 * total_leaks / max(total_words, 1), 3),
        "top_leaks": leak_counter.most_common(15),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

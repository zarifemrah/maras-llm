#!/usr/bin/env python3
"""Validate chat training/review JSONL files against the Kahramanmaraş Merkez
style guide and cross-check grounded vocabulary against data/processed/lexicon.jsonl.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from dialect_score import load_spec, score_assistant_turn

BASE_DIR = Path(__file__).resolve().parent.parent
LEXICON_PATH = BASE_DIR / "data" / "processed" / "lexicon.jsonl"
SPEC = load_spec()

CANONICAL_SYSTEM_PROMPT = SPEC["system_prompt"].strip()

BANNED_CHARS_RE = re.compile(r"[ŋñḳḵḫėāēīōūȫǖĢĠġ╧└─┌╒Ω┬║╦♠£]")
DRIFT_RE = re.compile(r"\b(gari|nörüyon|nörüyonuz|haçan|uşağum|aciycak|oturiyin)\b", re.IGNORECASE)
IYO_RE = re.compile(
    r"\b(?!(?:piyon|iyon|biyom|kardiyo|fiyort)[a-zçğıöşü]*\b)"
    r"[a-zçğıöşü]+(?:iyo|ıyo|uyo|üyo)"
    r"(?:r[a-zçğıöşü]*|m|n|k|z|lar|ler|sa|se|sun|sunuz|du|dü|muş|müş)?\b",
    re.IGNORECASE,
)
BAKALIM_RE = re.compile(r"\b(bakalım|bakayım)\b", re.IGNORECASE)
IYI_RE = re.compile(r"\b(iyi|iyilik|iyidir|iyisin|iyisiniz|iyiyim|iyice)\b", re.IGNORECASE)
THINK_RE = re.compile(r"</?think>", re.IGNORECASE)

MERKEZ_FEATURE_RE = re.compile(
    r"\b("
    r"eyi\w*|bahım|bahele|boon|onüçün|buadar|oadar|şuadar|burdiyem|evdiyem|"
    r"yamır|hamır|çamır|pambık|noot\w*|notu\w*|notak|notim|neydin|"
    r"yoheri|tavatır|barabar|vahıt|şindi|sona|soora|yosa|diyal|değel|kelli|"
    r"arhadaş\w*|eyicene|gözelcene|süllüm|püsük|saho|salık|sındı|şor|"
    r"dedi kine|hemi de|accıg|azcık|melmeket|samırsak|eşgili|baldırcan|"
    r"[a-zçğıöşü]+(?:ıcı|ici)(?:m|n|k|z)?|"
    r"[a-zçğıöşü]+(?:llar|ller|llardı|llerdi)|"
    r"[a-zçğıöşü]+(?:kana|kene|ıncı|inci|uncu|üncü|ışın|işin|uşun|üşün)|"
    r"[a-zçğıöşü]+(?:ınan|inen|unan|ünen|ynan|ynen)"
    r")\b",
    re.IGNORECASE,
)

CORE_MERKEZ_TOKEN_RE = re.compile(
    r"\b("
    r"edem|ede|gardaş\w*|gadan|horanta\w*|hanek\w*|hele|bah|çoh|yoh|heç|gimi|"
    r"goy\w*|gal\w*|dut\w*|gapı\w*|valla|yav|peh|tama|ola|bayak\w*|bıldır|"
    r"mırhız|lavlavı|cıncık|çomça|ığdırık|adeleş\w*|malamat|nizah|dinel\w*|"
    r"denneş\w*|ağnan\w*|böğsü\w*|çim\w*"
    r")\b",
    re.IGNORECASE,
)

USER_DIALECT_TOKEN_RE = re.compile(
    r"\b("
    r"edem|ede|gardaş\w*|çoh|yoh|heç|noot\w*|neydin|bah|gimi|yaği|geli|gidi|"
    r"oli|bayak\w*|bıldır|horanta\w*|hanek\w*|boon|eyi\w*"
    r")\b",
    re.IGNORECASE,
)


def load_lexicon_tokens() -> set[str]:
    tokens: set[str] = set()
    if not LEXICON_PATH.exists():
        return tokens
    for line in LEXICON_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        term = obj.get("normalized_term", "").strip().lower().rstrip("-")
        if len(term) >= 3:
            tokens.add(term)
            for w in term.split():
                w = w.rstrip("-")
                if len(w) >= 3:
                    tokens.add(w)
    # Add core Merkez grammatical/discourse anchors from grammar_notes
    tokens.update({
        "edem", "nootiin", "neydin", "nootin", "notucum", "notucuk", "notak",
        "bahım", "bahele", "boon", "accıg", "eyi", "eyilik", "yoheri", "tavatır",
        "süllüm", "püsük", "bayak", "bayaktan", "debiyak", "bıldır",
        "heri", "peh", "heç", "tama", "ola", "hele", "gardaş", "gadan", "horanta",
        "hanek", "dene", "dıkıl", "dinel", "denneş", "ağnan", "böğsü", "arıstak",
        "çim", "malamat", "nizah", "ığdırık", "şor", "heykat", "adeleş",
        "cıncık", "çomça", "mırhız", "lavlavı", "gartaşık", "gabiş", "ölgün",
        "bon", "kıyak", "bibi", "aba", "emmi", "gimi", "temam", "onnar", "bunnar",
    })
    return tokens


def validate_files(paths: list[Path]) -> tuple[int, list[str], dict]:
    lex_tokens = load_lexicon_tokens()
    errors: list[str] = []
    warnings: list[str] = []

    total = 0
    total_turns = 0
    char_lengths: list[int] = []
    categories: Counter[str] = Counter()
    seen_first_prompts: dict[str, str] = {}
    matched_lex_terms: set[str] = set()
    merkez_feature_hits = 0
    multi_turn_examples = 0
    dialect_user_prompt_count = 0
    assistant_openers: Counter[str] = Counter()

    for path in paths:
        if not path.exists():
            errors.append(f"Missing file: {path}")
            continue
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            loc = f"{path.name}:{lineno}"
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"{loc}: Invalid JSON ({exc})")
                continue

            if not isinstance(obj, dict) or "messages" not in obj:
                errors.append(f"{loc}: Missing 'messages' key")
                continue

            msgs = obj["messages"]
            if not isinstance(msgs, list) or len(msgs) < 3:
                errors.append(f"{loc}: 'messages' must have at least 3 turns (system, user, assistant)")
                continue

            if msgs[0].get("role") != "system" or msgs[0].get("content") != CANONICAL_SYSTEM_PROMPT:
                errors.append(f"{loc}: messages[0] must match canonical SYSTEM_PROMPT exactly")
                continue

            expected_roles = ["user" if i % 2 == 1 else "assistant" for i in range(1, len(msgs))]
            actual_roles = [m.get("role") for m in msgs[1:]]
            if actual_roles != expected_roles or actual_roles[-1] != "assistant":
                errors.append(f"{loc}: Roles must strictly alternate user/assistant and end on assistant (got {actual_roles})")
                continue

            conv_chars = 0
            bad_turn = False
            conv_merkez_hits = 0
            conv_core_hits = 0
            for idx, m in enumerate(msgs):
                content = m.get("content")
                if not isinstance(content, str) or not content.strip():
                    errors.append(f"{loc}: Empty content at message index {idx}")
                    bad_turn = True
                    break
                conv_chars += len(content)
                if BANNED_CHARS_RE.search(content):
                    found = set(BANNED_CHARS_RE.findall(content))
                    errors.append(f"{loc}: Banned phonetic/box char(s) {found} in message {idx}")
                    bad_turn = True
                if THINK_RE.search(content):
                    errors.append(f"{loc}: <think> tag found in message {idx}")
                    bad_turn = True
                if m["role"] == "assistant":
                    dm = DRIFT_RE.search(content)
                    if dm:
                        errors.append(f"{loc}: Non-Maraş drift token '{dm.group(0)}' in assistant message {idx}")
                        bad_turn = True
                    im = IYO_RE.search(content)
                    if im:
                        errors.append(f"{loc}: Generic -iyo form '{im.group(0)}' in assistant message {idx} (use Maraş -i/-im/-in/-ik)")
                        bad_turn = True
                    bm = BAKALIM_RE.search(content)
                    if bm:
                        errors.append(f"{loc}: Standard '{bm.group(0)}' in assistant message {idx} (use 'bahım')")
                        bad_turn = True
                    ym = IYI_RE.search(content)
                    if ym:
                        errors.append(f"{loc}: Unshifted '{ym.group(0)}' in assistant message {idx} (use 'eyi*')")
                        bad_turn = True
                    dscore = score_assistant_turn(content, spec=SPEC, category=obj.get("_category"))
                    if dscore["leak_count"] > 0:
                        errors.append(f"{loc}: Standard/drift leaks {dscore['leaks']} in assistant message {idx}")
                        bad_turn = True
                    f_hits = len(MERKEZ_FEATURE_RE.findall(content))
                    c_hits = len(CORE_MERKEZ_TOKEN_RE.findall(content))
                    conv_merkez_hits += f_hits
                    conv_core_hits += c_hits
                    # Cross-check lexicon grounding
                    words = re.findall(r"[a-zçğıöşü]+", content.lower())
                    for w in words:
                        if w in lex_tokens:
                            matched_lex_terms.add(w)
                        elif len(w) >= 5:
                            for lt in lex_tokens:
                                if len(lt) >= 4 and w.startswith(lt):
                                    matched_lex_terms.add(lt)
                                    break
            if bad_turn:
                continue

            if conv_merkez_hits + conv_core_hits < 1:
                errors.append(f"{loc}: Assistant text lacks any Merkez dialect feature or core anchor token")
                continue

            if conv_chars < 60 or conv_chars > 3200:
                errors.append(f"{loc}: Conversation char length {conv_chars} out of [60, 3200] bounds")
                continue

            first_user = re.sub(r"\s+", " ", msgs[1]["content"].strip().lower())
            if first_user in seen_first_prompts:
                errors.append(f"{loc}: Duplicate first user prompt (already seen at {seen_first_prompts[first_user]})")
                continue
            seen_first_prompts[first_user] = loc

            qa_turns = (len(msgs) - 1) // 2
            if qa_turns >= 2:
                multi_turn_examples += 1
            if MERKEZ_FEATURE_RE.search(msgs[1]["content"]) or USER_DIALECT_TOKEN_RE.search(msgs[1]["content"]):
                dialect_user_prompt_count += 1
            opener_match = re.search(r"[a-zçğıöşü]+", msgs[2]["content"].lower())
            if opener_match:
                assistant_openers[opener_match.group(0)] += 1

            merkez_feature_hits += conv_merkez_hits
            cat = obj.get("_category", "uncategorized")
            categories[cat] += 1
            char_lengths.append(conv_chars)
            total += 1
            total_turns += qa_turns

    stats = {
        "valid_examples": total,
        "total_qa_turns": total_turns,
        "multi_turn_examples": multi_turn_examples,
        "multi_turn_pct": round(100.0 * multi_turn_examples / total, 1) if total else 0.0,
        "dialect_user_prompt_count": dialect_user_prompt_count,
        "dialect_user_prompt_pct": round(100.0 * dialect_user_prompt_count / total, 1) if total else 0.0,
        "categories": dict(categories),
        "avg_chars": round(sum(char_lengths) / len(char_lengths), 1) if char_lengths else 0,
        "max_chars": max(char_lengths) if char_lengths else 0,
        "min_chars": min(char_lengths) if char_lengths else 0,
        "grounded_lexicon_terms_count": len(matched_lex_terms),
        "merkez_feature_hits": merkez_feature_hits,
        "avg_merkez_hits_per_example": round(merkez_feature_hits / total, 2) if total else 0.0,
        "top_assistant_openers": assistant_openers.most_common(10),
        "sample_grounded_terms": sorted(matched_lex_terms)[:25],
        "errors": len(errors),
        "warnings": len(warnings),
    }
    return total, errors, stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path, help="Chat JSONL files to validate")
    args = parser.parse_args()

    total, errors, stats = validate_files(args.files)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if errors:
        print("\nErrors:", file=sys.stderr)
        for e in errors[:50]:
            print(f" - {e}", file=sys.stderr)
        sys.exit(1)
    if total == 0:
        print("No valid examples found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

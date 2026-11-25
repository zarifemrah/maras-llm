#!/usr/bin/env python3
"""Merge, validate, deduplicate, and stratify-split data/chat/batches/*.jsonl into
mlx-lm-ready train.jsonl (85%), valid.jsonl (10%), and test.jsonl (5%).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from validate_chat_dataset import validate_files

BASE_DIR = Path(__file__).resolve().parent.parent
BATCHES_DIR = BASE_DIR / "data" / "chat" / "batches"
DEFAULT_OUT_DIR = BASE_DIR / "data" / "chat"


def explode_dialogue_turns(msgs: list[dict]) -> list[list[dict]]:
    """Split a multi-turn dialogue into one sample per assistant turn so mask_prompt trains on all turns."""
    samples: list[list[dict]] = []
    for idx in range(2, len(msgs), 2):
        if msgs[idx].get("role") == "assistant":
            samples.append(msgs[: idx + 1])
    return samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batches-dir", type=Path, default=BATCHES_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--explode-turns", action="store_true", help="Emit one sample per assistant turn")
    args = parser.parse_args()

    batch_files = sorted(args.batches_dir.glob("*.jsonl"))
    if not batch_files:
        print(f"No .jsonl files found in {args.batches_dir}", file=sys.stderr)
        sys.exit(1)

    total, errors, stats = validate_files(batch_files)
    if errors:
        print("Validation failed; aborting split build:", file=sys.stderr)
        for e in errors[:30]:
            print(f" - {e}", file=sys.stderr)
        sys.exit(1)

    by_cat: dict[str, list[dict]] = defaultdict(list)
    seen_prompts: set[str] = set()
    for bf in batch_files:
        for raw in bf.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            obj = json.loads(raw)
            prompt_key = re.sub(r"\s+", " ", obj["messages"][1]["content"].strip().lower())
            if prompt_key in seen_prompts:
                continue
            seen_prompts.add(prompt_key)
            cat = obj.get("_category", "uncategorized")
            by_cat[cat].append({
                "messages": obj["messages"],
                "_category": cat,
                "_source_batch": bf.name,
            })

    rng = random.Random(args.seed)
    train_rows, valid_rows, test_rows = [], [], []
    for cat in sorted(by_cat):
        items = by_cat[cat]
        rng.shuffle(items)
        n = len(items)
        n_test = max(1, round(n * 0.05)) if n >= 5 else 0
        n_valid = max(1, round(n * 0.10)) if n >= 3 else 0
        if n_test + n_valid >= n:
            n_test = 0
            n_valid = max(0, n - 1)
        test_rows.extend(items[:n_test])
        valid_rows.extend(items[n_test : n_test + n_valid])
        train_rows.extend(items[n_test + n_valid :])

    rng.shuffle(train_rows)
    rng.shuffle(valid_rows)
    rng.shuffle(test_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    meta_rows = []
    for split_name, rows in (("train", train_rows), ("valid", valid_rows), ("test", test_rows)):
        out_path = args.output_dir / f"{split_name}.jsonl"
        out_count = 0
        with out_path.open("w", encoding="utf-8") as f:
            for r in rows:
                turn_seqs = explode_dialogue_turns(r["messages"]) if args.explode_turns else [r["messages"]]
                for seq in turn_seqs:
                    f.write(json.dumps({"messages": seq}, ensure_ascii=False) + "\n")
                    meta_rows.append({
                        "split": split_name,
                        "index": out_count,
                        "category": r["_category"],
                        "source_batch": r["_source_batch"],
                    })
                    out_count += 1

    meta_path = args.output_dir / "metadata.jsonl"
    with meta_path.open("w", encoding="utf-8") as f:
        for m in meta_rows:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    split_counts = {
        s: sum(1 for m in meta_rows if m["split"] == s)
        for s in ("train", "valid", "test")
    }
    summary = {
        "batches": [b.name for b in batch_files],
        "validated_total": total,
        "explode_turns": args.explode_turns,
        "train": split_counts["train"],
        "valid": split_counts["valid"],
        "test": split_counts["test"],
        "output_dir": str(args.output_dir),
        "grounded_lexicon_terms_count": stats["grounded_lexicon_terms_count"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

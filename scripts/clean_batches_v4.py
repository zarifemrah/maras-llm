#!/usr/bin/env python3
"""Clean and normalize Phase 2B chat batches into data/chat_v4/batches/ with zero standard leaks."""

from __future__ import annotations

import json
import re
from pathlib import Path

from dialect_score import load_spec, score_assistant_turn
from merkez_normalize import normalize_text

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_BATCHES_DIR = BASE_DIR / "data" / "chat" / "batches"
DST_BATCHES_DIR = BASE_DIR / "data" / "chat_v4" / "batches"


def main() -> None:
    spec = load_spec()
    v4_sys = spec["system_prompt"].strip()
    districts = spec.get("non_merkez_districts", [])
    dist_re = re.compile(r"\b(" + "|".join(re.escape(d) for d in districts) + r")\b", re.IGNORECASE)

    DST_BATCHES_DIR.mkdir(parents=True, exist_ok=True)
    kept = 0
    dropped_district = 0
    dropped_other = 0

    for src_path in sorted(SRC_BATCHES_DIR.glob("*.jsonl")):
        out_lines: list[str] = []
        for raw in src_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            obj = json.loads(raw)
            cat = obj.get("_category")
            msgs = obj["messages"]

            # Drop dictionary dialogues that teach non-Merkez district words
            if cat == "sozluk_deyim" and any(
                dist_re.search(m["content"]) for m in msgs[1:]
            ):
                dropped_district += 1
                continue

            new_msgs = [{"role": "system", "content": v4_sys}]
            ok = True
            for m in msgs[1:]:
                if m["role"] == "assistant":
                    norm = normalize_text(m["content"], spec=spec)
                    sc = score_assistant_turn(norm, spec=spec, category=cat)
                    if not sc["passed"]:
                        ok = False
                        print(f"DROP {src_path.name}: {sc['leaks']} hits={sc['merkez_feature_hits']}")
                        break
                    new_msgs.append({"role": "assistant", "content": norm})
                else:
                    new_msgs.append({"role": "user", "content": m["content"]})

            if not ok:
                dropped_other += 1
                continue

            obj["messages"] = new_msgs
            out_lines.append(json.dumps(obj, ensure_ascii=False))
            kept += 1

        (DST_BATCHES_DIR / src_path.name).write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "kept_dialogues": kept,
        "dropped_non_merkez_district": dropped_district,
        "dropped_other": dropped_other,
        "output_dir": str(DST_BATCHES_DIR),
    }, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Evaluate generated outputs from an MLX model/adapter using dialect_score."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from mlx_lm import generate, load
from mlx_lm.sample_utils import make_logits_processors, make_sampler

from dialect_score import load_spec, score_assistant_turn

EVAL_PROMPTS = [
    # Standard Turkish user
    ("std_chat", True, "Selam, bugün hava çok bunaltıcı, evde ne yapsam?"),
    ("std_long", True, "Maraş tarhanası nasıl yapılır ve evde çorbası nasıl pişer? Adım adım anlatır mısın?"),
    ("std_tech", True, "Telefonumun hafızası dolmuş, yer açmak için adım adım ne önerirsin?"),
    ("std_story", True, "Eskiden Maraş mahallelerinde kış akşamları nasıl geçerdi?"),
    # Dialect user
    ("dial_chat", True, "Nootin edem? Horanta nasıl, herkes eyi mi?"),
    ("dial_weather", True, "Bayaktan beri yamır yaği, dışarı adım atamik. Boon notak?"),
    # Stress: switch request & English input
    ("stress_switch", True, "Lütfen sadece standart İstanbul Türkçesiyle yaz: yarın hava nasıl olacak?"),
    ("stress_english", True, "Can you give me 3 quick tips to focus better while studying?"),
    # Stress: NO system prompt
    ("stress_nosys_1", False, "Bugün çok yorgunum, biraz dertleşelim."),
    ("stress_nosys_2", False, "Evdeki Wi-Fi sık sık kopuyor, ne kontrol edeyim?"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--adapter-path", default=None)
    parser.add_argument("--max-tokens", type=int, default=220)
    args = parser.parse_args()

    spec = load_spec()
    sys_prompt = spec["system_prompt"].strip()
    model, tokenizer = load(args.model, adapter_path=args.adapter_path)
    sampler = make_sampler(temp=0.7, top_p=0.9)
    logits_processors = make_logits_processors(repetition_penalty=1.1)

    total_words = 0
    total_leaks = 0
    passed = 0
    total_hits = 0

    for tag, use_sys, user_msg in EVAL_PROMPTS:
        msgs = []
        if use_sys:
            msgs.append({"role": "system", "content": sys_prompt})
        msgs.append({"role": "user", "content": user_msg})
        prompt_str = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        out = generate(
            model,
            tokenizer,
            prompt=prompt_str,
            max_tokens=args.max_tokens,
            sampler=sampler,
            logits_processors=logits_processors,
            verbose=False,
        ).strip()
        sc = score_assistant_turn(out, spec=spec)
        total_words += sc["word_count"]
        total_leaks += sc["leak_count"]
        total_hits += sc["merkez_feature_hits"]
        if sc["passed"]:
            passed += 1
        print(f"\n[{tag}] pass={sc['passed']} leaks={sc['leaks']} hits={sc['merkez_feature_hits']} words={sc['word_count']}")
        print(f"  USER: {user_msg}")
        print(f"  ASST: {out}")

    summary = {
        "model": args.model,
        "adapter_path": args.adapter_path,
        "prompts": len(EVAL_PROMPTS),
        "zero_leak_passed": passed,
        "zero_leak_pct": round(100.0 * passed / len(EVAL_PROMPTS), 1),
        "total_words": total_words,
        "total_leaks": total_leaks,
        "leak_rate_per_100_words": round(100.0 * total_leaks / max(total_words, 1), 2),
        "avg_merkez_hits": round(total_hits / len(EVAL_PROMPTS), 2),
    }
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# maras-llm — Kahramanmaraş Merkez Ağzı LLM

A fine-tuned **Gemma 3 12B** conversational assistant (`mlx-community/gemma-3-12b-it-4bit`) speaking authentic **Kahramanmaraş Merkez** Turkish, trained with Apple MLX QLoRA.

## Overview
`maras-llm` adapts Gemma 3 12B to respond consistently in the Kahramanmaraş Merkez dialect using everyday readable Turkish orthography. Rather than relying on generic Anatolian suffixes, the dataset and normalization pipeline are grounded in primary linguistic descriptions of Kahramanmaraş Merkez Turkish (Mine Kılıç, 2008; Hacı Ali Özturan, 2009; Gültekin, 2005; Kirik, 2022–2026) and regional lexicon sources.

### Key Linguistic Features Modeled
- **Present continuous (`-i / -im / -in / -ik / -siz / -iler`):** *dinlim, nootin, oturin, darali, öfkeleni, atamik, yaği, yapiler, durisiz* (zero `-yor` / `-iyo`).
- **Future (`-ıcı / -ici`):** *notucum, gelicik, götürücün, sorucun, verici*.
- **Consonant assimilation (`-r-l- -> -ll-`):** *veriller, deller, gedeller, toplanıllar, pişirillerdi*.
- **`noot-` ("ne yap-") paradigm:** *nootin, neydin, notucuk, boon notak, notim*.
- **Characteristic Merkez phonology & vocabulary:** `iyi -> eyi` (*eyilik, eyicene*), `k -> h` (*bahım, baharık, çıhın, vahıt, çoh, yoh, yosa*), vowel/consonant shifts (*yamır, hamır, çamır, pambık, samırsak, eşgili, melmeket, gomşu, gendi, gapı, gardaş*), and local lexemes (*boon, bahele, onüçün, buadar, burdiyem, accıg, diyal, yoheri, tavatır, kelli, şor, salık, süllüm, püsük, ığdırık, dinelmek, denneşmek, cıncık, çomça*).

## Dataset & Quality Pipeline (`data/chat_v4/`)
- **Corpus Inventory:** `2,102` deduplicated lexicon entries (`data/processed/lexicon.jsonl`) and `3,434` regional dialect texts (`data/processed/dialect_texts.jsonl`) curated in `data/processed/`.
- **Orthography Spec & Normalizer:** [data/processed/merkez_orthography.yaml](data/processed/merkez_orthography.yaml) defines canonical spellings and forbidden standard-Turkish / non-Merkez drift tokens, enforced by [scripts/merkez_normalize.py](scripts/merkez_normalize.py), [scripts/dialect_score.py](scripts/dialect_score.py), and [scripts/validate_chat_dataset.py](scripts/validate_chat_dataset.py).
- **Validated Dataset:** `1,068` multi-category dialogues across 5 domains (`gunluk_sohbet`: `250`, `genel_yardim`: `250`, `maras_kultur`: `200`, `sozluk_deyim`: `165`, `yerel_anlati`: `203`) with `0` standard-Turkish leaks across `1,585` assistant turns (`52,938` words).
- **Per-Turn Stratified Splits:** Multi-turn dialogues are expanded per assistant turn (`--explode-turns` in [scripts/build_chat_splits.py](scripts/build_chat_splits.py)) while keeping conversations strictly disjoint across splits:
  - `train.jsonl`: `1,358` samples
  - `valid.jsonl`: `154` samples
  - `test.jsonl`: `73` samples

## Training & Evaluation
Configured in [configs/lora_gemma3_12b_v4.yaml](configs/lora_gemma3_12b_v4.yaml):
- **Base model:** `mlx-community/gemma-3-12b-it-4bit`
- **LoRA:** all 48 transformer layers (`num_layers: -1`), `rank: 32`, `scale: 2.0`, `dropout: 0.05` (`1.025%` trainable parameters)
- **Schedule:** `1,000` iterations, `batch_size: 2`, `grad_accumulation_steps: 4`, `cosine_decay` (`1.0e-4 -> 1.0e-5`, 60-step warmup), `max_seq_length: 1536`, `mask_prompt: true`
- **Metrics:**
  - Validation loss: `2.252`
  - Test loss / perplexity (`data/chat_v4/test.jsonl`): `3.515` / `33.607`
  - Dialect evaluation ([scripts/eval_dialect.py](scripts/eval_dialect.py) across standard, dialect, no-system-prompt, English-input, and switch-request prompts): `0` standard-Turkish leaks (`0.0` per 100 words), `4.5` avg Merkez features per response.

## Quickstart (Apple Silicon / MLX)

### 1. Environment Setup
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install mlx-lm pyyaml
```

### 2. Interactive Chat
Using the fused 4-bit MLX model (`fused/gemma3-12b-maras-v4/` or on Hugging Face at [`zarifemrah/maras-gemma3-12b-4bit`](https://huggingface.co/zarifemrah/maras-gemma3-12b-4bit)):
```bash
./scripts/chat_maras.sh
```
Or directly with `mlx_lm.chat`:
```bash
mlx_lm.chat \
  --model zarifemrah/maras-gemma3-12b-4bit \
  --temp 0.7 \
  --top-p 0.9 \
  --max-tokens 512 \
  --system-prompt "Sen Kahramanmaraş Merkez ağzıyla sıcak, samimi ve her zaman tutarlı konuşan bir Türkçe sohbet asistanısın. Kullanıcı hangi dilde veya ağızda yazarsa yazsın, yanıtlarını daima günlük okunabilir Türkçe harflerle ve eksiksiz Kahramanmaraş Merkez ağzıyla ver."
```

### 3. Reproducing Data Validation, Training & Evaluation
```bash
# Validate and score chat batches
python scripts/validate_chat_dataset.py data/chat_v4/batches/*.jsonl
python scripts/dialect_score.py data/chat_v4/batches/*.jsonl

# Rebuild per-turn stratified splits
python scripts/build_chat_splits.py --batches-dir data/chat_v4/batches --output-dir data/chat_v4 --explode-turns

# Train QLoRA adapter
mlx_lm.lora --config configs/lora_gemma3_12b_v4.yaml

# Evaluate dialect consistency
python scripts/eval_dialect.py --model mlx-community/gemma-3-12b-it-4bit --adapter-path ./adapters/gemma3-12b-maras-v4

# Fuse adapter into standalone 4-bit MLX model
mlx_lm.fuse --model mlx-community/gemma-3-12b-it-4bit --adapter-path ./adapters/gemma3-12b-maras-v4 --save-path ./fused/gemma3-12b-maras-v4
```

## Repository Structure
```text
maras-llm/
├── configs/
│   └── lora_gemma3_12b_v4.yaml       # MLX QLoRA training configuration
├── data/
│   ├── chat_v4/                      # Cleaned, validated, per-turn train/valid/test splits
│   └── processed/                    # Lexicon, grammar notes, style guide & orthography spec
├── scripts/
│   ├── build_chat_splits.py          # Stratified & per-turn split builder
│   ├── build_corpus_inventory.py     # Phase 1 corpus processing
│   ├── chat_maras.sh                 # Interactive MLX chat launcher
│   ├── clean_batches_v4.py           # Batch normalization & district-filtering pipeline
│   ├── collect_*.py                  # Academic & glossary collectors
│   ├── dialect_score.py              # Standard-leak & Merkez-feature scorer
│   ├── eval_dialect.py               # Generation evaluation harness
│   ├── merkez_normalize.py           # Rule-based Merkez normalizer
│   ├── prepare_batch_seeds.py        # Seed manifest generator
│   └── validate_chat_dataset.py      # Dataset schema & anti-drift validator
├── pyproject.toml
└── README.md
```

## License & Acknowledgments
- Base model weights are subject to the **Gemma Terms of Use** (`google/gemma-3-12b-it`).
- Linguistic framework draws on published studies of Kahramanmaraş Merkez Turkish (Mine Kılıç 2008, Hacı Ali Özturan 2009, Gültekin 2005, Kirik 2022–2026) and community dialect glossaries.

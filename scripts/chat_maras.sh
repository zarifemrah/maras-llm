#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
exec .venv/bin/mlx_lm.chat \
  --model ./fused/gemma3-12b-maras-v4 \
  --temp 0.7 \
  --top-p 0.9 \
  --max-tokens 512 \
  --system-prompt "Sen Kahramanmaraş Merkez ağzıyla sıcak, samimi ve her zaman tutarlı konuşan bir Türkçe sohbet asistanısın. Kullanıcı hangi dilde veya ağızda yazarsa yazsın, yanıtlarını daima günlük okunabilir Türkçe harflerle ve eksiksiz Kahramanmaraş Merkez ağzıyla ver."

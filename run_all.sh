#!/usr/bin/env bash
# Reproducible end-to-end eval. Deterministic (seeded) up to the human labels.
# Usage:
#   ./run_all.sh                      # offline analysis on out/gold_labels.json
#   ./run_all.sh --mock               # full pipeline on synthetic labels (no key)
#   JUDGE=deepseek/deepseek-chat-v3.1 ./run_all.sh --llm   # + live judge/baseline
set -euo pipefail
cd "$(dirname "$0")"
LABELS="out/gold_labels.json"
JUDGE="${JUDGE:-deepseek/deepseek-chat-v3.1}"
SYS="${SYS:-deepseek/deepseek-chat-v3.1}"

if [[ "${1:-}" == "--mock" ]]; then
  python3 scripts/make_mock_labels.py
  LABELS="out/gold_labels.mock.json"
  MOCK=1 python3 scripts/run_llm.py
  MOCK=1 python3 scripts/compare_baseline.py --labels "$LABELS"
fi

echo "== 1. corpus =="
[[ -f data/corpus.json ]] || python3 scripts/fetch_corpus.py
echo "== 2. sample + label tool =="
python3 scripts/build_gold_sample.py
python3 scripts/build_label_tool.py

[[ -f "$LABELS" ]] || { echo "!! no labels at $LABELS — label with eval/label.html and export."; exit 1; }

echo "== 3. offline analysis =="
python3 scripts/analyze.py --labels "$LABELS"
python3 scripts/difficulty_analysis.py || echo "  (skip difficulty: videos_dataset not found)"
python3 scripts/failure_taxonomy.py --labels "$LABELS"

if [[ "${1:-}" == "--llm" ]]; then
  echo "== 4. live LLM: judge + baseline =="
  python3 scripts/run_llm.py --judge-model "$JUDGE" --system-model "$SYS"
  python3 scripts/validate_judge.py --labels "$LABELS" --judge-model "$JUDGE"
  python3 scripts/compare_baseline.py --labels "$LABELS" --system-model "$SYS"
fi

echo "== 5. charts + report =="
python3 scripts/make_charts.py
python3 scripts/build_report.py
echo "✓ done -> out/REPORT.md"

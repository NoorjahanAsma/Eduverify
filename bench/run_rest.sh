#!/bin/bash
# Stage 2+3 (replaces the tail of run_all.sh): local 7B main arm first, then ablations on the two subsets where they can matter.
# OCR findings are advisory (warnings never change the verdict), so an OCR ablation would be identical to the full pipeline and is omitted.
cd "$(dirname "$0")/.." || exit 1
set -a; . ./.env; set +a
PY=.venv/bin/python
curl -s -m 5 localhost:11434/api/tags >/dev/null || { nohup ollama serve >/tmp/ollama_serve.log 2>&1 & sleep 8; }
$PY -u bench/run.py --run local7b --gen ollama:qwen2.5-coder:7b --conditions code,verified
$PY -u bench/run.py --run groq120 --gen groq:openai/gpt-oss-120b --subsets chart_absent,diagram_rel --conditions verified_no_rules,verified_no_vlm,verified_no_judge,verified_no_repair

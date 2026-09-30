#!/bin/bash
# Full pilot: Groq generator arm (with ablations), then local 7B generator arm. Resumable; re-run to continue after rate limits.
cd "$(dirname "$0")/.." || exit 1
set -a; . ./.env; set +a
PY=.venv/bin/python
$PY -u bench/run.py --run groq120 --gen groq:openai/gpt-oss-120b --conditions code,verified
$PY -u bench/run.py --run groq120 --gen groq:openai/gpt-oss-120b --conditions verified_no_rules,verified_no_ocr,verified_no_vlm,verified_no_judge,verified_no_repair
$PY -u bench/run.py --run local7b --gen ollama:qwen2.5-coder:7b --conditions code,verified

# Benchmark harness (pilot)

30 items, built deterministically by `prepare_data.py` (seed 0):
- 15 charts from ChartQA test tables (source = the table; ground truth = the table).
- 15 diagrams from AI2D (foodChainsWebs 8, lifeCycles 7). Source = the label list only; ground truth = AI2D's directed arrows between labeled blobs. Edges must come from the model's domain knowledge, so edge errors here measure conceptual hallucination.

Conditions
- `direct`: a text-to-image model draws the image (`direct_gen.py`; SDXL on Colab, Gemini or Grok when keys exist). Scored only by reader VLM read-back.
- `code`: LLM writes the spec, deterministic renderer draws it, no checks, no repair.
- `verified`: `code` + rule checks + OCR + VLM read-back + up to 2 repairs; abstains when errors remain.

Metrics: exact-match rate among shown items, exact over all items, silent-error rate (shown but wrong, over all items), coverage, primary recall/edge-F1, image-level read-back exactness.
Caveats: (1) the read-back reader is the same VLM family used inside `verified`, so image-level scores for verified/code are a reader-agreement check, not an independent ground truth; spec-vs-GT is the primary metric for them. (2) Ground truth for diagrams inherits AI2D annotation errors. (3) Single generator, single seed = pilot only.

Run: `python bench/run.py --run NAME --conditions code,verified --gen ollama:qwen2.5-coder:7b --reader ollama:qwen3-vl:8b`, then `python bench/summarize.py NAME`. Resumable.

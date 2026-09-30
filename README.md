# eduverify

The LLM proposes a structured spec (IR). Everything else is deterministic: schema and number checks, rendering with vector text, OCR/VLM read-back, and a pass / repair / abstain verdict.

```
eduverify render examples/chart.json -o out/            # IR -> image + manifest
eduverify verify examples/chart.json --source src.txt   # rule checks only
eduverify generate "Water cycle diagram" --provider ollama --model qwen3-vl:8b -o out/
```
Providers: `ollama` (local), `gemini` (GEMINI_API_KEY), `grok` (XAI_API_KEY). Keys are read from the environment only.

## Run the demo

Setup (once):
```
cd eduverify
source .venv/bin/activate      # or: pip install -e .
```

**1. A pass**
```
eduverify render examples/chart.json -o out/chart
open out/chart/visual.png
```
Prints `verdict: pass` (exit 0) and writes `visual.png`, `visual.svg` and `report.json`.

**2. An abstain**
```
eduverify render examples/diagram.json --source examples/source.txt -o out/diagram
```
Prints `verdict: abstain` (exit 1) and writes no image. The diagram labels are not in `examples/source.txt`, so each one is reported as `label_not_in_source`. The tool refuses to ship a visual it cannot verify. Fix the spec or the source and rerun to get a pass.

**3. Rule checks only** (instant)
```
eduverify verify examples/chart.json
```

**4. Full run from a request** (needs a model)
```
ollama pull qwen3-vl:8b-instruct
eduverify generate "Water cycle diagram" --kind diagram --provider ollama --model qwen3-vl:8b-instruct -o out/gen
```
Use the `-instruct` model: the plain `qwen3-vl:8b` is a thinking model and returns empty output here. Add `--vlm ollama:qwen3-vl:8b-instruct` to `render` for the image read-back check. OCR read-back needs `tesseract` (`brew install tesseract`); use `--no-ocr` to skip it.

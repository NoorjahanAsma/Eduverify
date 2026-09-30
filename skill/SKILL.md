---
name: eduverify
description: Create accurate educational charts, diagrams and infographics from source text or data, with no invented numbers or labels. You write a JSON spec; eduverify checks it and renders it. Use for teaching visuals that must be faithful to a source. Not for decorative images, photos or free-form illustration.
---

# eduverify

Never draw the image yourself and never invent values. Write a JSON spec, verify it, then render it.

## 1. Write the spec

Save it as `spec.json`. Pick one `kind`; fields marked `?` are optional.

- **chart**: `{"kind":"chart","chart_type":"bar|line|pie|scatter","title":"...","categories":["A","B"],"series":[{"name":"...","values":[1,2],"source_span?":"..."}],"x_label?":"","y_label?":"","unit?":"%","percent?":true}`
  - `categories` are the x labels or pie slices. For bar, line and pie, each series needs exactly one value per category and category labels must be unique. Scatter is exempt from the length rule. A pie needs exactly one series with non-negative values.
  - Set `percent: true` when the values are percentages; they should sum to about 100.
- **diagram**: `{"kind":"diagram","title":"...","direction?":"TB|LR","nodes":[{"id":"a","label":"...","source_span?":"..."}],"edges":[{"src":"a","dst":"b","label?":"","source_span?":"..."}]}`
  - Node ids must be unique, and every `src` and `dst` must be an existing node `id`. With a source, each arrow must be stated in it.
- **infographic**: `{"kind":"infographic","title":"...","sections":[{"heading":"...","facts":[{"text":"...","source_span?":"..."}]}]}`

Working examples are in `examples/chart.json` and `examples/diagram.json`. The full schema is in `src/eduverify/ir.py`.

**Grounding.** When source text exists, save it to `source.txt`. Put a short verbatim quote in each `source_span`, and use only numbers and labels that appear in the source. If the source lacks something the user asked for, leave it out and say so. Do not fill the gap.

## 2. Check, then render

1. `eduverify verify spec.json --source source.txt` runs the rule checks only and is fast. Fix any `error` lines first. Omit `--source` if there is no source text.
2. `eduverify render spec.json --source source.txt -o out/` renders the image and runs the full checks.
   - Add `--vlm ollama:qwen3-vl:8b` for a VLM image read-back.
   - Add `--no-ocr` to skip OCR.

Both commands exit 0 only on success, so you can rely on the exit code as well as the printed text.

## 3. Read the verdict

The output is `verdict: pass` or `verdict: abstain`, followed by one issue per line.

- **pass**: use `out/visual.png`, or `out/visual.svg` for vector output. `out/report.json` has the full report.
- **abstain**: at least one check failed. Edit the spec using the error lines and rerun `render`. Retry at most 2 times, the same limit as `generate --repairs`.
- **Warnings** are advisory, for example OCR misreading rotated axis labels. Errors are not.

## 4. If it still abstains

Do not ship the image. Tell the user which claims or values could not be verified, quoting the error lines, and ask for a better source or corrected data.

## Whole request in one step

To have a model draft and repair the spec itself, run `eduverify generate "<request>" --source source.txt --provider ollama --model <model> -o out/`. Add `--kind` to force a kind. The same pass, abstain and exit-code rules apply.

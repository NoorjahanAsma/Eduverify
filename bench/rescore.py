"""Recompute scores for an existing run from saved specs (and, with --reread, saved or fresh reader output) after a scorer or ground-truth fix.
Usage: python bench/rescore.py RUN [--reread]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import run as B
from eduverify import load_ir

RUN = sys.argv[1]; reread = "--reread" in sys.argv
root = Path(__file__).parent.parent / "results" / RUN
items = {json.loads(l)["id"]: json.loads(l) for l in open(Path(__file__).parent / "items.jsonl")}
reader = B.llm_of(json.loads((root / "config.json").read_text())["reader"]) if reread else None
recs = [json.loads(l) for l in open(root / "results.jsonl")]
for r in recs:
    item = items[r["id"]]; d = root / r["cond"] / r["id"]
    ir = None
    if (d / "ir.json").exists():
        ir = load_ir((d / "ir.json").read_text())
    elif (d / "report.json").exists() and json.loads((d / "report.json").read_text()).get("ir"):
        ir = load_ir(json.loads((d / "report.json").read_text())["ir"])
    if ir is not None:
        key = "ir_score" if r["status"] == "shown" else "ir_score_if_shown"
        r[key] = B.score_ir(item, ir)
    if reread and r["status"] == "shown" and r["cond"] != "direct" and item["kind"] == "chart":
        r["image_score"] = B.score_image(item, d / "visual.png", reader, d)
    elif r["status"] == "shown" and (d / "reader.json").exists():
        rd = json.loads((d / "reader.json").read_text())
        import metrics as M
        r["image_score"] = M.score_chart(M.chart_cells_from_points(rd), item["gt"]) if item["kind"] == "chart" else M.score_diagram(rd.get("nodes", []), rd.get("edges", []), item["gt"])
(root / "results.jsonl").rename(root / "results.pre_rescore.jsonl")
(root / "results.jsonl").write_text("\n".join(json.dumps(r, default=str) for r in recs) + "\n")
print("rescored", len(recs), "records")

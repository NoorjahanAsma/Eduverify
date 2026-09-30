"""Aggregate results/<run>/results.jsonl into a per-condition, per-kind table."""
import json, sys
from collections import defaultdict
from pathlib import Path

run = sys.argv[1]
rows = [json.loads(l) for l in open(Path(__file__).parent.parent / "results" / run / "results.jsonl")]
g = defaultdict(list)
for r in rows:
    g[(r["cond"], r.get("subset") or r["kind"])].append(r)


def mean(x):
    x = [v for v in x if v is not None]
    return sum(x) / len(x) if x else float("nan")


print(f"{'cond':9} {'subset':13} {'n':>3} {'shown':>5} {'cover':>5} {'exact|shown':>11} {'exact|all':>9} {'silent_err':>10} {'halluc|all':>10} {'F1/recall':>9} {'img_exact':>9}")
for (c, k), rs in sorted(g.items()):
    n = len(rs); shown = [r for r in rs if r["status"] == "shown"]
    src = "ir_score" if c != "direct" else "image_score"
    sc = [r.get(src, {}) for r in shown]
    ex = [s.get("exact") for s in sc if "exact" in s]
    kd = "diagram" if k.startswith("diagram") else "chart"
    prim = [s.get("edge_f1" if kd == "diagram" else "recall") for s in sc if "exact" in s]
    hall = sum(1 for s in sc if (s.get("hallucinated_edges", 0) + s.get("hallucinated_nodes", 0) + s.get("hallucinated_cells", 0)) > 0)
    img = [r["image_score"].get("exact") for r in shown if "exact" in r.get("image_score", {})]
    print(f"{c:9} {k:13} {n:3d} {len(shown):5d} {len(shown)/n:5.2f} {mean(ex):11.2f} {sum(1 for e in ex if e)/n:9.2f} {sum(1 for e in ex if not e)/n:10.2f} {hall/n:10.2f} {mean(prim):9.2f} {mean(img):9.2f}")

"""Benchmark runner. Conditions: direct (external images), code (spec->render, no checks), verified (full pipeline).
Primary metric = spec-vs-ground-truth (no reader involved). Image-level read-back score is added for every shown image
using a fixed reader VLM (used as the only score for `direct`).
Usage: python bench/run.py --run r1 --conditions code,verified --gen ollama:qwen2.5-coder:7b --reader ollama:qwen3-vl:8b"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import metrics as M
from eduverify.generate import propose
from eduverify.llm import get_llm
from eduverify.pipeline import generate_and_run
from eduverify.render import render
from eduverify.verify import readback

ROOT = Path(__file__).parent


def llm_of(spec):
    prov, _, model = spec.partition(":")
    return get_llm(prov, model or None)


def score_ir(item, ir):
    if item["kind"] == "chart":
        return M.score_chart(M.chart_cells_from_ir(ir), item["gt"])
    return M.score_diagram([n.label for n in ir.nodes], [(next(n.label for n in ir.nodes if n.id == e.src), next(n.label for n in ir.nodes if n.id == e.dst))
                                                       for e in ir.edges if any(n.id == e.src for n in ir.nodes) and any(n.id == e.dst for n in ir.nodes)], item["gt"])


def score_image(item, png, reader, save_to=None):
    try:
        if item["kind"] == "chart":
            pts = readback.read_chart(png, reader)
            if save_to:
                (save_to / "reader.json").write_text(json.dumps(pts))
            return M.score_chart(M.chart_cells_from_points(pts), item["gt"])
        d = readback.read_diagram(png, reader)
        if save_to:
            (save_to / "reader.json").write_text(json.dumps(d))
        return M.score_diagram(d.get("nodes", []), d.get("edges", []), item["gt"])
    except Exception as ex:
        return dict(reader_error=f"{type(ex).__name__}: {ex}"[:200])


def run_item(item, cond, gen, reader, out, judge=None):
    t0 = time.time(); d = out / cond / item["id"]; d.mkdir(parents=True, exist_ok=True)
    rec = dict(id=item["id"], kind=item["kind"], subset=item.get("subset"), cond=cond, status="shown")
    png = None
    if cond == "direct":
        png = ROOT / "direct_images" / f"{item['id']}.png"
        if not png.exists():
            rec["status"] = "missing_image"; return rec
    elif cond == "code":
        try:
            ir = propose(gen, item["request"], item["source"], item["kind"])
        except ValueError as ex:
            rec.update(status="gen_failed", error=str(ex)[:200]); return rec
        rd = render(ir, d); png = rd.png
        rec["ir_score"] = score_ir(item, ir); (d / "ir.json").write_text(ir.model_dump_json(indent=1))
    elif cond.startswith("verified"):
        ab = cond[len("verified_"):] if "_" in cond else ""
        rep = generate_and_run(item["request"], gen, d, item["source"], item["kind"], vlm=None if ab == "no_vlm" else reader,
                               max_repairs=0 if ab == "no_repair" else 2, judge=None if ab == "no_judge" else judge,
                               ocr=ab != "no_ocr", use_rules=ab != "no_rules")
        rec.update(iterations=rep.iterations, issues=[str(i) for i in rep.issues])
        if rep.verdict != "pass":
            rec["status"] = "abstain"; rec["ir_score_if_shown"] = score_ir(item, rep.ir) if rep.ir else None; return rec
        png = rep.rendered.png; rec["ir_score"] = score_ir(item, rep.ir); (d / "ir.json").write_text(rep.ir.model_dump_json(indent=1))
    rec["image_score"] = score_image(item, png, reader, d if cond != "direct" else None)
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--run", required=True); a.add_argument("--conditions", default="code,verified")
    a.add_argument("--gen", default="ollama:qwen2.5-coder:7b"); a.add_argument("--reader", default="ollama:qwen3-vl:8b-instruct")
    a.add_argument("--judge", default=None, help="provider:model for edge-direction judging (default: same as --reader)"); a.add_argument("--limit", type=int); a.add_argument("--subsets", default="chart_full,diagram_thin,chart_absent,diagram_rel")
    a = a.parse_args()
    items = [json.loads(l) for l in open(ROOT / "items.jsonl")]
    items = [i for i in items if i.get("subset") in a.subsets.split(",")]
    if a.limit:  # first N of each subset
        items = [i for sub in a.subsets.split(",") for i in [x for x in items if x.get("subset") == sub][: a.limit]]
    out = ROOT.parent / "results" / a.run; out.mkdir(parents=True, exist_ok=True)
    log = out / "results.jsonl"
    done = {(r["id"], r["cond"]) for r in map(json.loads, log.read_text().splitlines())} if log.exists() else set()
    gen, reader = llm_of(a.gen), llm_of(a.reader)
    judge = llm_of(a.judge) if a.judge else reader
    (out / "config.json").write_text(json.dumps(vars(a), indent=1))
    for item in items:
        for cond in a.conditions.split(","):
            if (item["id"], cond) in done:
                continue
            rec = None
            for attempt in range(12):  # server down (e.g. Ollama quit): wait and retry the same item instead of skipping the rest of the run
                try:
                    rec = run_item(item, cond, gen, reader, out, judge)
                    break
                except Exception as ex:
                    print(item["id"], cond, "ERROR", f"{type(ex).__name__}: {ex}"[:150], flush=True)
                    if "ConnectError" not in type(ex).__name__ and "Connection refused" not in str(ex):
                        break  # not an outage: skip the item; a rerun will resume it
                    time.sleep(60)
            if rec is None:
                continue
            rec["gen_calls"] = len(gen.calls); rec["gen"] = a.gen; rec["reader"] = a.reader; rec["judge"] = a.judge or a.reader
            with log.open("a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
            print(item["id"], cond, rec["status"], rec.get("ir_score", {}).get("exact"), flush=True)


if __name__ == "__main__":
    main()

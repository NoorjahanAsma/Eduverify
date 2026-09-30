"""Read-back verification: does the rendered image still say what the IR says?"""
from __future__ import annotations
import json, re, shutil, subprocess
from pathlib import Path
from . import Issue
from .rules import _norm
from ..ir import ChartIR, DiagramIR


def _tesseract(png: Path, psm: str) -> str:
    return subprocess.run(["tesseract", str(png), "-", "--psm", psm], capture_output=True, text=True).stdout


def ocr_text(png: Path) -> str | None:
    """Full-page pass plus overlapping 2x horizontal bands: tesseract skips text inside boxed shapes on a full page."""
    if not shutil.which("tesseract"):
        return None
    out = [_tesseract(png, "11")]
    try:
        from PIL import Image
        import tempfile
        im = Image.open(png).convert("L")
        with tempfile.TemporaryDirectory() as d:
            for y in range(0, max(im.height - 80, 1), 60):
                band = im.crop((0, y, im.width, min(im.height, y + 140)))
                f = Path(d) / "band.png"
                band.resize((band.width * 2, band.height * 2), Image.LANCZOS).save(f)
                out.append(_tesseract(f, "6"))
    except Exception:
        pass
    return "\n".join(out)


def ocr_check(png: Path, expected: list[str]) -> list[Issue]:
    txt = ocr_text(png)
    if txt is None:
        return [Issue("warning", "no_ocr", "tesseract not installed; text read-back skipped")]
    hay = _norm(txt)
    hay_tokens = set(re.findall(r"[a-z0-9.%]+", hay))
    iss = []
    for e in expected:
        toks = re.findall(r"[a-z0-9.%]+", _norm(e))
        if not toks:
            continue
        hit = sum(t in hay_tokens or t in hay for t in toks) / len(toks)
        if hit < 0.6:
            iss.append(Issue("warning", "ocr_missing", f"text not recovered by OCR: {e[:60]!r} ({hit:.0%})"))
    return iss


def _json(s: str):
    s = re.sub(r"^```(?:json)?|```$", "", s.strip(), flags=re.M).strip()
    m = re.search(r"[\[{].*[\]}]", s, re.S)
    return json.loads(m.group(0) if m else s)


CHART_Q = ('Read every data point in this chart. Return only JSON: {"points": [{"label": "x-axis or slice label", "series": "legend name or empty", "value": number}]}. '
           "Use the numbers printed on or read from the chart. Do not guess values you cannot see.")
DIAGRAM_Q = ('Read this diagram. Return only JSON: {"nodes": ["exact box text", ..], "edges": [["source box text", "target box text"], ..]} '
             "with one edge per arrow, from the tail of the arrow to its head.")


def read_chart(png, llm) -> list[dict]:
    return _json(llm.chat(CHART_Q, images=[png])).get("points", [])


def read_diagram(png, llm) -> dict:
    return _json(llm.chat(DIAGRAM_Q, images=[png]))


def vlm_check(ir, png: Path, llm) -> list[Issue]:
    """Ask a VLM to re-extract the content from the image and diff it against the IR."""
    try:
        if isinstance(ir, ChartIR):
            pts = read_chart(png, llm)
            iss = []
            for s in ir.series:
                tol = max(0.02 * max((abs(v) for v in s.values), default=1), 1e-9)
                for cat, v in zip(ir.categories, s.values):
                    cand = [q for q in pts if _norm(str(q.get("label", ""))) == _norm(cat)
                            and (len(ir.series) == 1 or _norm(str(q.get("series", ""))) == _norm(s.name))]
                    if not cand:
                        iss.append(Issue("warning", "vlm_point_missing", f"{s.name}/{cat}: not read back")); continue
                    got = cand[0].get("value")
                    if not isinstance(got, (int, float)) or abs(got - v) > tol:
                        iss.append(Issue("error", "vlm_value_mismatch", f"{s.name}/{cat}: image read back as {got}, spec says {v:g}"))
            return iss
        if isinstance(ir, DiagramIR):
            got = read_diagram(png, llm)
            lab = {n.id: _norm(n.label) for n in ir.nodes}
            want = {(lab[e.src], lab[e.dst]) for e in ir.edges if e.src in lab and e.dst in lab}
            have = {(_norm(a), _norm(b)) for a, b in got.get("edges", [])}
            iss = []
            for a, b in sorted(want - have):
                iss.append(Issue("warning", "vlm_edge_missing", f"arrow {a!r} -> {b!r} not read back"))
            for a, b in sorted(have - want):
                iss.append(Issue("error", "vlm_edge_extra", f"image shows arrow {a!r} -> {b!r} that is not in the spec"))
            return iss
    except Exception as ex:  # VLM output is untrusted; never crash the pipeline
        return [Issue("warning", "vlm_failed", f"read-back failed: {type(ex).__name__}: {ex}")]
    return []

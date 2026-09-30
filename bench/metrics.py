"""Scoring against ground truth. IR-level (spec) and image-level (VLM read-back) share the same functions."""
from __future__ import annotations
import re


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _close(a, b) -> bool:
    return isinstance(a, (int, float)) and abs(a - b) <= max(0.01 * abs(b), 0.051)


def chart_cells_from_ir(ir) -> dict[str, dict[str, float]]:
    return {s.name: {norm(c): v for c, v in zip(ir.categories, s.values)} for s in ir.series}


def chart_cells_from_points(points) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for p in points:
        if isinstance(p.get("value"), (int, float)):
            out.setdefault(str(p.get("series", "")), {})[norm(p.get("label", ""))] = float(p["value"])
    return out


def _score_chart_once(pred: dict[str, dict[str, float]], gt: dict) -> dict:
    gcells = {n: {norm(c): v for c, v in zip(gt["categories"], vals) if v is not None} for n, vals in gt["series"].items()}
    n_gt = sum(len(v) for v in gcells.values())
    gcat = {norm(c) for c in gt["categories"]}
    left = dict(pred); matched = wrong = extra = 0
    for gname, gc in gcells.items():  # align each GT series to the best remaining predicted series
        best, bk = -1, None
        for pn, pc in left.items():
            m = sum(c in pc and _close(pc[c], v) for c, v in gc.items())
            if m > best:
                best, bk = m, pn
        if bk is None:
            continue
        pc = left.pop(bk)
        for c, v in gc.items():
            if c in pc and _close(pc[c], v):
                matched += 1
        wrong += sum(1 for c, pv in pc.items() if c in gc and not _close(pv, gc[c]))
        extra += sum(1 for c in pc if c not in gc)  # includes categories the source marks as missing (NaN)
    extra += sum(len(pc) for pc in left.values())  # whole series that do not exist in the ground truth
    n_pred = matched + wrong + extra
    return dict(recall=matched / n_gt if n_gt else 0.0, precision=matched / n_pred if n_pred else 0.0,
                hallucinated_cells=wrong + extra, exact=matched == n_gt and wrong + extra == 0)


def score_chart(pred: dict[str, dict[str, float]], gt: dict) -> dict:
    """Score against the table as given and against its transpose (rows as series), keep the better reading:
    a grouped chart of a multi-column table is legitimate in either orientation."""
    a = _score_chart_once(pred, gt)
    if len(gt["series"]) > 1:
        tcats = list(gt["series"].keys())
        tseries = {c: [(gt["series"][s][i] if i < len(gt["series"][s]) else None) for s in tcats] for i, c in enumerate(gt["categories"])}
        b = _score_chart_once(pred, dict(categories=tcats, series=tseries))
        if (b["exact"], b["recall"], -b["hallucinated_cells"]) > (a["exact"], a["recall"], -a["hallucinated_cells"]):
            return b
    return a


def score_diagram(nodes, edges, gt: dict) -> dict:
    pn = {norm(n) for n in nodes}; gn = {norm(n) for n in gt["nodes"]}
    pe = {(norm(a), norm(b)) for a, b in edges}; ge = {(norm(a), norm(b)) for a, b in gt["edges"]}

    def prf(p, g):
        tp = len(p & g)
        pr, rc = (tp / len(p) if p else 0.0), (tp / len(g) if g else 0.0)
        return pr, rc, (2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    _, _, nf = prf(pn, gn); ep, er, ef = prf(pe, ge)
    return dict(node_f1=nf, edge_precision=ep, edge_recall=er, edge_f1=ef, hallucinated_nodes=len(pn - gn),
                hallucinated_edges=len(pe - ge), exact=pn == gn and pe == ge)

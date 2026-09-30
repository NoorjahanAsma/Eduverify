"""Deterministic checks on the IR. No LLM, no tokens."""
from __future__ import annotations
import re
from . import Issue
from ..ir import ChartIR, DiagramIR, InfographicIR

_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def numbers(text: str) -> set[float]:
    out = set()
    for m in _NUM.findall(text):
        try:
            out.add(float(m.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def _spans(items, source: str | None) -> list[Issue]:
    issues = []
    if source is None:
        return issues
    ns = _norm(source)
    src_tokens = set(re.findall(r"[a-z0-9.]+", ns))
    for label, span in items:
        # verbatim quote, or (for tables the model re-orders) >= 90% of the span's tokens present in the source
        toks = re.findall(r"[a-z0-9.]+", _norm(span)) if span else []
        if span and _norm(span) not in ns and (not toks or sum(t in src_tokens for t in toks) / len(toks) < 0.9):
            issues.append(Issue("error", "span_not_in_source", f"{label}: quoted span not found in source: {span[:60]!r}"))
    return issues


def check(ir, source: str | None = None) -> list[Issue]:
    return {ChartIR: _chart, DiagramIR: _diagram, InfographicIR: _infographic}[type(ir)](ir, source)


def parse_table(source: str) -> list[list[str]] | None:
    """Rows of a markdown pipe table found in the source (header row first), or None."""
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in source.splitlines() if ln.strip().startswith("|")]
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) or c == "" for c in r)]
    return rows if len(rows) >= 2 else None


def _row_check(ir: ChartIR, source: str) -> list[Issue]:
    """When the source is a table, each plotted (category, value) must sit in that category's row (catches swapped values)."""
    tab = parse_table(source)
    if not tab:
        return []
    iss = []
    body = tab[1:]
    for s in ir.series:
        for cat, v in zip(ir.categories, s.values):
            ctoks = set(re.findall(r"[a-z0-9]+", _norm(cat)))
            rows = [r for r in body if ctoks and len(ctoks & set(re.findall(r"[a-z0-9]+", _norm(r[0])))) / len(ctoks) >= 0.5]
            if not rows:
                continue  # category grounding is reported by the category rule
            if not any(abs(v - k) < 1e-9 for r in rows for c in r[1:] for k in numbers(c)):
                iss.append(Issue("error", "value_in_wrong_row", f"{s.name}/{cat}: value {v:g} is not in the source row for {cat!r}"))
    return iss


def _chart(ir: ChartIR, source):
    iss: list[Issue] = []
    if not ir.series:
        return [Issue("error", "no_series", "chart has no series")]
    if ir.chart_type != "scatter":
        for s in ir.series:
            if len(s.values) != len(ir.categories):
                iss.append(Issue("error", "length_mismatch", f"series {s.name!r} has {len(s.values)} values for {len(ir.categories)} categories"))
    if ir.chart_type == "pie":
        if len(ir.series) != 1:
            iss.append(Issue("error", "pie_series", "pie chart needs exactly one series"))
        vals = ir.series[0].values
        if any(v < 0 for v in vals):
            iss.append(Issue("error", "negative_pie", "pie values must be non-negative"))
        if ir.percent and abs(sum(vals) - 100) > 0.6:
            iss.append(Issue("error", "pie_sum", f"percent values sum to {sum(vals):g}, expected 100"))
    if len(set(ir.categories)) != len(ir.categories):
        iss.append(Issue("error", "dup_category", "duplicate category labels"))
    if ir.chart_type != "pie" and not (ir.y_label or ir.unit):
        iss.append(Issue("warning", "no_axis_label", "y axis has no label or unit"))
    if source is not None:
        stoks = set(re.findall(r"[a-z0-9]+", _norm(source)))
        for c in ir.categories:
            toks = re.findall(r"[a-z0-9]+", _norm(c))
            if toks and sum(t in stoks for t in toks) / len(toks) < 0.5:
                iss.append(Issue("error", "category_not_in_source", f"category {c!r} does not appear in source"))
        known = numbers(source)
        for s in ir.series:
            for v in s.values:
                if not any(abs(v - k) < 1e-9 for k in known):
                    iss.append(Issue("error", "value_not_in_source", f"{s.name}: value {v:g} does not appear in source"))
    if source is not None:
        iss += _row_check(ir, source)
    iss += _spans([(f"series {s.name}", s.source_span) for s in ir.series], source)
    return iss


def _diagram(ir: DiagramIR, source):
    iss: list[Issue] = []
    ids = [n.id for n in ir.nodes]
    if len(set(ids)) != len(ids):
        iss.append(Issue("error", "dup_node_id", "duplicate node ids"))
    labels = [_norm(n.label) for n in ir.nodes]
    if len(set(labels)) != len(labels):
        iss.append(Issue("warning", "dup_label", "two nodes share a label"))
    idset = set(ids)
    for e in ir.edges:
        for end in (e.src, e.dst):
            if end not in idset:
                iss.append(Issue("error", "dangling_edge", f"edge {e.src}->{e.dst} references unknown node {end!r}"))
    used = {e.src for e in ir.edges} | {e.dst for e in ir.edges}
    for n in ir.nodes:
        if n.id not in used and len(ir.nodes) > 1:
            iss.append(Issue("warning", "orphan_node", f"node {n.id!r} has no edges"))
    if source is not None:
        ns = _norm(source)
        for n in ir.nodes:
            if _norm(n.label) not in ns and not n.source_span:
                iss.append(Issue("error", "label_not_in_source", f"node label {n.label!r} not found in source and no quoted span"))
    if source is not None:
        iss += _relations(ir, source)
    iss += _spans([(f"node {n.id}", n.source_span) for n in ir.nodes] + [(f"edge {e.src}->{e.dst}", e.source_span) for e in ir.edges], source)
    return iss


def _mentions(seg: str, label: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(_norm(label)) + r"(?![a-z0-9])", _norm(seg)) is not None


def _relations(ir: DiagramIR, source: str) -> list[Issue]:
    """If the source states relations (a sentence mentioning two node labels), every drawn edge must be stated
    and every stated relation must be drawn (either direction). Direction itself is not checked here."""
    segs = [x for x in re.split(r"[.;\n]", source) if x.strip()]
    label = {n.id: n.label for n in ir.nodes}
    stated = set()
    for seg in segs:
        hit = [i for i, l in label.items() if _mentions(seg, l)]
        for a in hit:
            for b in hit:
                if a < b:
                    stated.add(frozenset((a, b)))
    if not stated:
        return []  # thin source: nothing to check edges against
    iss, drawn = [], set()
    for e in ir.edges:
        pair = frozenset((e.src, e.dst))
        drawn.add(pair)
        if pair not in stated:
            iss.append(Issue("error", "edge_unsupported", f"arrow {label.get(e.src, e.src)} -> {label.get(e.dst, e.dst)} is not stated in the source"))
    for pair in stated - drawn:
        a, b = sorted(pair)
        iss.append(Issue("error", "relation_missing", f"source relates {label[a]} and {label[b]} but no arrow connects them"))
    return iss


def _infographic(ir: InfographicIR, source):
    iss: list[Issue] = []
    if not ir.sections:
        return [Issue("error", "no_sections", "infographic has no sections")]
    known = numbers(source) if source is not None else None
    for s in ir.sections:
        if not s.facts:
            iss.append(Issue("warning", "empty_section", f"section {s.heading!r} has no facts"))
        for f in s.facts:
            if known is not None:
                for v in numbers(f.text):
                    if not any(abs(v - k) < 1e-9 for k in known):
                        iss.append(Issue("error", "number_not_in_source", f"{s.heading}: number {v:g} in {f.text[:50]!r} not in source"))
            if len(f.text) > 200:
                iss.append(Issue("warning", "long_fact", f"fact longer than 200 chars in {s.heading!r}"))
    iss += _spans([(f"fact in {s.heading}", f.source_span) for s in ir.sections for f in s.facts], source)
    return iss

"""Edge-direction check against the source. Rules can tell that two labels are related in the source, but not which way
the arrow should point, because direction depends on the arrow's meaning (energy flow, sequence, cause). A judge model
answers one narrow yes/no question per drawn arrow, using only the source sentences that mention both endpoints."""
from __future__ import annotations
import json, re
from . import Issue
from .rules import _mentions, _norm

Q = """You check one arrow in a diagram against a source text.
ARROW RULE (what an arrow means): {rule}
SOURCE SENTENCES: {sents}
QUESTION: Given only the source sentences and the arrow rule, should the diagram contain an arrow from "{a}" to "{b}" (tail at "{a}", head at "{b}")? Think about which item the arrow rule puts at the tail.
Answer with JSON only: {{"answer": "yes"}} or {{"answer": "no"}}."""


def _ask(judge, prompt) -> str | None:
    raw = judge.chat(prompt, json_mode=True)
    m = re.search(r"\{.*?\}", raw, re.S)
    try:
        return str(json.loads(m.group(0)).get("answer", "")).strip().lower() if m else None
    except Exception:
        return None


def check_edges(ir, source: str, request: str, judge) -> list[Issue]:
    segs = [x.strip() for x in re.split(r"[.;\n]", source) if x.strip()]
    label = {n.id: n.label for n in ir.nodes}
    iss = []
    for e in ir.edges:
        if e.src not in label or e.dst not in label:
            continue
        a, b = label[e.src], label[e.dst]
        rel = [s for s in segs if _mentions(s, a) and _mentions(s, b)]
        if not rel:
            continue  # nothing in the source about this pair; the rule check reports it
        rule = next((s for s in re.split(r"(?<=[.!?])\s+", request) if re.search(r"arrow", s, re.I)), "arrows follow the source")
        ans = _ask(judge, Q.format(rule=rule, sents=" | ".join(rel), a=a, b=b))
        if ans == "no":
            iss.append(Issue("error", "edge_direction", f"arrow {a} -> {b}: source sentence {rel[0]!r} with the arrow rule implies the opposite direction; swap src and dst for this edge"))
        elif ans not in ("yes", "no"):
            iss.append(Issue("warning", "edge_direction_unjudged", f"judge gave no clear answer for {a} -> {b}"))
    return iss

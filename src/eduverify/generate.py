"""LLM -> IR. The LLM only proposes structured JSON; it never draws."""
from __future__ import annotations
import json, re
from .ir import load_ir

SYSTEM = """You produce a JSON spec for an educational visual. Output only JSON.
Rules: use only facts and numbers from SOURCE when SOURCE is given; never invent values.
If a value is not in SOURCE, omit it. For each series/node/edge/fact copy a short verbatim quote into source_span when SOURCE is given.
Pick kind = chart | diagram | infographic to fit the request. Keep labels short (<= 5 words); node ids are short ascii.
An edge runs from src (arrow tail) to dst (arrowhead). Follow the request's statement of what arrows mean when choosing which node is src."""


EXAMPLES = """chart: {"kind":"chart","chart_type":"bar|line|pie|scatter","title":"..","categories":["A","B"],"series":[{"name":"..","values":[1,2],"source_span":"<verbatim quote from SOURCE, or null>"}],"x_label":"","y_label":"..","unit":"","percent":false}
diagram: {"kind":"diagram","title":"..","nodes":[{"id":"a","label":"..","source_span":"<verbatim quote from SOURCE, or null>"}],"edges":[{"src":"a","dst":"b","label":"","source_span":"<verbatim quote from SOURCE, or null>"}],"direction":"TB|LR"}
infographic: {"kind":"infographic","title":"..","sections":[{"heading":"..","facts":[{"text":"..","source_span":"<verbatim quote from SOURCE, or null>"}]}]}"""


def _extract(s: str) -> dict:
    s = re.sub(r"^```(?:json)?|```$", "", s.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", s, re.S)
    return json.loads(m.group(0) if m else s)


def propose(llm, request: str, source: str | None = None, kind: str | None = None, feedback: list[str] | None = None, retries: int = 2, previous: str | None = None):
    schema = EXAMPLES  # compact worked examples beat the full JSON schema for small models
    prompt = f"REQUEST: {request}\n" + (f"KIND: {kind}\n" if kind else "") + (f"SOURCE:\n{source}\n" if source else "SOURCE: none (use well-established textbook facts only)\n")
    if feedback:
        prompt += (f"\nYOUR PREVIOUS SPEC:\n{previous}\n" if previous else "") + "\nThat spec failed these checks. Return a corrected full spec that fixes every listed error and keeps everything else:\n" + "\n".join(feedback) + "\n"
    prompt += f"\nOUTPUT FORMAT (pick the kind that fits; fields shown are the only ones allowed):\n{schema}\n"
    err = None
    for _ in range(retries + 1):
        raw = llm.chat(prompt + (f"\nPrevious output was invalid: {err}\n" if err else ""), system=SYSTEM, json_mode=True)
        try:
            return load_ir(_extract(raw))
        except Exception as ex:
            err = str(ex)[:400]
    raise ValueError(f"could not obtain a valid spec after {retries + 1} tries: {err}")

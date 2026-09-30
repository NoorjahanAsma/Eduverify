from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from .render import render, Rendered
from .verify import Issue
from .verify import rules, readback, entail
from .generate import propose


@dataclass
class Report:
    ir: object
    rendered: Rendered | None
    issues: list[Issue] = field(default_factory=list)
    verdict: str = "pass"  # pass | abstain
    iterations: int = 1
    llm_calls: list[dict] = field(default_factory=list)

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == "error"]

    def to_dict(self):
        return dict(verdict=self.verdict, iterations=self.iterations, issues=[i.__dict__ for i in self.issues],
                    png=str(self.rendered.png) if self.rendered else None, svg=str(self.rendered.svg) if self.rendered else None,
                    ir=self.ir.model_dump() if self.ir else None, llm_calls=self.llm_calls)


def run(ir, out_dir, source: str | None = None, vlm=None, ocr: bool = True, stem: str = "visual", judge=None, request: str = "", use_rules: bool = True) -> Report:
    """Verify + render an existing IR. Verdict is 'pass' only when no errors remain."""
    issues = rules.check(ir, source) if use_rules else []
    if judge is not None and source and type(ir).__name__ == "DiagramIR" and not any(i.severity == "error" for i in issues):
        issues += entail.check_edges(ir, source, request, judge)
    if any(i.severity == "error" for i in issues):
        return Report(ir, None, issues, "abstain")
    rd = render(ir, out_dir, stem)
    if ocr:
        issues += readback.ocr_check(rd.png, rd.expected_text)
    if vlm is not None:
        issues += readback.vlm_check(ir, rd.png, vlm)
    rep = Report(ir, rd, issues, "abstain" if any(i.severity == "error" for i in issues) else "pass")
    if vlm is not None:
        rep.llm_calls = vlm.calls
    return rep


def generate_and_run(request: str, llm, out_dir, source: str | None = None, kind: str | None = None,
                     vlm=None, max_repairs: int = 2, ocr: bool = True, judge=None, use_rules: bool = True) -> Report:
    """LLM proposes IR -> verify -> repair loop -> pass or abstain (never silently ship an unverified visual)."""
    feedback = None
    prev = None
    rep = None
    for it in range(1, max_repairs + 2):
        try:
            ir = propose(llm, request, source, kind, feedback, previous=prev)
        except ValueError as ex:
            rep = Report(None, None, [Issue("error", "no_valid_spec", str(ex))], "abstain", it)
            break
        rep = run(ir, out_dir, source, vlm, ocr, judge=judge, request=request, use_rules=use_rules)
        rep.iterations = it
        if rep.verdict == "pass":
            break
        feedback = [str(i) for i in rep.errors]
        prev = rep.ir.model_dump_json() if rep.ir else None
    rep.llm_calls = llm.calls + (vlm.calls if vlm and vlm is not llm else []) + (judge.calls if judge else [])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "report.json").write_text(json.dumps(rep.to_dict(), indent=2, default=str))
    return rep

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from ..ir import ChartIR, DiagramIR, InfographicIR


@dataclass
class Rendered:
    png: Path
    svg: Path
    expected_text: list[str] = field(default_factory=list)  # every string drawn, for read-back


def render(ir, out_dir: str | Path, stem: str = "visual") -> Rendered:
    from .chart import render_chart
    from .diagram import render_diagram
    from .infographic import render_infographic
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    fn = {ChartIR: render_chart, DiagramIR: render_diagram, InfographicIR: render_infographic}[type(ir)]
    return fn(ir, out, stem)

from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import textwrap
from . import Rendered

matplotlib.rcParams["svg.fonttype"] = "none"


def _fmt(v: float) -> str:
    return f"{v:g}"


def _overlap(ax, fig) -> bool:
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    boxes = [t.get_window_extent(r) for t in ax.get_xticklabels() if t.get_text()]
    return any(a.x1 > b.x0 for a, b in zip(boxes, boxes[1:]))


def _fit_tick_labels(fig, ax):
    """Never ship overlapping category labels: try horizontal, then rotate progressively."""
    for rot in (0, 30, 45, 60):
        plt.setp(ax.get_xticklabels(), rotation=rot, ha="right" if rot else "center", rotation_mode="anchor")
        fig.tight_layout()
        if not _overlap(ax, fig):
            return


def render_chart(ir, out, stem) -> Rendered:
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=200)
    expected = [ir.title]
    cats = ir.categories
    ylabel = ir.y_label + (f" ({ir.unit})" if ir.unit and ir.y_label else "")
    if ir.chart_type == "pie":
        s = ir.series[0]
        ax.pie(s.values, labels=cats, autopct=lambda p: f"{p:.1f}%", startangle=90)
        ax.axis("equal")
        expected += cats
    elif ir.chart_type == "scatter":
        for s in ir.series:
            ax.scatter(cats and [float(c) for c in cats] or range(len(s.values)), s.values, label=s.name)
        expected += [s.name for s in ir.series]
    else:
        x = np.arange(len(cats))
        n = len(ir.series)
        w = 0.8 / n
        for i, s in enumerate(ir.series):
            if ir.chart_type == "bar":
                bars = ax.bar(x + (i - (n - 1) / 2) * w, s.values, w, label=s.name)
                ax.bar_label(bars, labels=[_fmt(v) for v in s.values], fontsize=8)
            else:
                ax.plot(x, s.values, marker="o", label=s.name)
                for xi, v in zip(x, s.values):
                    ax.annotate(_fmt(v), (xi, v), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=8)
        ax.set_xticks(x); ax.set_xticklabels([textwrap.fill(c, 14) for c in cats])
        _fit_tick_labels(fig, ax)
        expected += cats + [_fmt(v) for s in ir.series for v in s.values]
        if n > 1:
            expected += [s.name for s in ir.series]
    if ir.chart_type != "pie":
        ax.set_xlabel(ir.x_label); ax.set_ylabel(ylabel)
        expected += [t for t in (ir.x_label, ylabel) if t]
        if len(ir.series) > 1 or ir.chart_type == "scatter":
            ax.legend()
        ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(ir.title)
    fig.tight_layout()
    png, svg = out / f"{stem}.png", out / f"{stem}.svg"
    fig.savefig(png); fig.savefig(svg); plt.close(fig)
    return Rendered(png, svg, expected)

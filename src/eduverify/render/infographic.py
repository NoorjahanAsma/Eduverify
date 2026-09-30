from __future__ import annotations
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from . import Rendered

matplotlib.rcParams["svg.fonttype"] = "none"
COLORS = ["#1a73e8", "#188038", "#e37400", "#a142f4", "#d93025", "#00796b"]


def render_infographic(ir, out, stem) -> Rendered:
    expected = [ir.title]
    heights = [0.9 + 0.55 * sum(len(textwrap.wrap(f.text, 62)) for f in s.facts) for s in ir.sections]
    total = 1.4 + sum(heights)
    fig, ax = plt.subplots(figsize=(7.5, total), dpi=200)
    ax.set_xlim(0, 10); ax.set_ylim(0, total); ax.axis("off")
    y = total - 0.4
    ax.text(5, y, ir.title, ha="center", va="top", fontsize=16, weight="bold")
    y -= 1.0
    for k, (s, h) in enumerate(zip(ir.sections, heights)):
        c = COLORS[k % len(COLORS)]
        ax.add_patch(FancyBboxPatch((0.3, y - h + 0.2), 9.4, h - 0.2, boxstyle="round,pad=0.05", fc="#f8f9fa", ec=c, lw=1.5))
        ax.text(0.6, y - 0.1, s.heading, va="top", fontsize=12, weight="bold", color=c)
        expected.append(s.heading)
        yy = y - 0.75
        for f in s.facts:
            lines = textwrap.wrap(f.text, 62)
            ax.text(0.7, yy, "• " + "\n  ".join(lines), va="top", fontsize=9)
            expected.append(f.text)
            yy -= 0.55 * len(lines)
        y -= h
    png, svg = out / f"{stem}.png", out / f"{stem}.svg"
    fig.savefig(png, bbox_inches="tight"); fig.savefig(svg, bbox_inches="tight"); plt.close(fig)
    return Rendered(png, svg, expected)

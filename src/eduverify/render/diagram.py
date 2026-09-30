"""Deterministic diagram layout: measured text boxes, layered layout, ring layout for cycles.
Coordinates are in inches so box sizes match the drawn text exactly."""
from __future__ import annotations
import math, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from . import Rendered

matplotlib.rcParams["svg.fonttype"] = "none"
FS, PADX, PADY, GAP_X, GAP_Y = 10, 0.16, 0.12, 0.55, 0.85


def _wrap(s: str, width: int = 16) -> str:
    return "\n".join(textwrap.wrap(s, width)) or s


def _measure(labels: dict[str, str]) -> dict[str, tuple[float, float]]:
    fig = plt.figure(dpi=100)
    r = fig.canvas.get_renderer()
    out = {}
    for k, s in labels.items():
        bb = fig.text(0, 0, s, fontsize=FS, ha="center", va="center").get_window_extent(r)
        out[k] = (bb.width / 100 + 2 * PADX, bb.height / 100 + 2 * PADY)
    plt.close(fig)
    return out


def _split_back_edges(ids, edges):
    """DFS; returns set of edge indices that close a cycle."""
    adj = {i: [] for i in ids}
    for k, e in enumerate(edges):
        if e.src in adj and e.dst in adj:
            adj[e.src].append((e.dst, k))
    state, back = {}, set()

    def dfs(u):
        state[u] = 1
        for v, k in adj[u]:
            if state.get(v) == 1:
                back.add(k)
            elif v not in state:
                dfs(v)
        state[u] = 2
    indeg = {i: 0 for i in ids}
    for e in edges:
        if e.dst in indeg:
            indeg[e.dst] += 1
    for i in [i for i in ids if indeg[i] == 0] + list(ids):
        if i not in state:
            dfs(i)
    return back


def _is_ring(ids, edges) -> bool:
    if len(ids) < 3 or len(edges) != len(ids):
        return False
    return all(sum(e.src == i for e in edges) == 1 and sum(e.dst == i for e in edges) == 1 for i in ids)


def _ring_order(ids, edges):
    nxt = {e.src: e.dst for e in edges}
    order, cur = [ids[0]], nxt[ids[0]]
    while cur != ids[0] and len(order) <= len(ids):
        order.append(cur); cur = nxt[cur]
    return order if len(order) == len(ids) else None


def layout(ir, size):
    ids = [n.id for n in ir.nodes]
    if _is_ring(ids, ir.edges):
        order = _ring_order(ids, ir.edges)
        if order:
            wmax = max(size[i][0] for i in ids); hmax = max(size[i][1] for i in ids)
            n = len(order)
            # radius so neighbouring boxes on the ring never overlap
            r = max((wmax + GAP_X) / (2 * math.sin(math.pi / n)), (hmax + GAP_Y) / 2 + hmax, 1.2)
            rx, ry = r * 1.25, r
            return {i: (rx * math.sin(2 * math.pi * k / n), ry * math.cos(2 * math.pi * k / n)) for k, i in enumerate(order)}, set()
    back = _split_back_edges(ids, ir.edges)
    layer = {i: 0 for i in ids}
    fwd = [(e.src, e.dst) for k, e in enumerate(ir.edges) if k not in back and e.src in layer and e.dst in layer]
    for _ in range(len(ids)):
        for a, b in fwd:
            layer[b] = max(layer[b], layer[a] + 1)
    rows: dict[int, list[str]] = {}
    for i in ids:
        rows.setdefault(layer[i], []).append(i)
    lr = ir.direction == "LR"
    pos, depth_off = {}, 0.0
    al: dict[str, float] = {}
    preds = {i: [a for a, b in fwd if b == i] for i in ids}
    for d in sorted(rows):
        row = rows[d]
        if d > 0:
            row = sorted(row, key=lambda i: (sum(al[q] for q in preds[i] if q in al) / max(1, sum(q in al for q in preds[i])) if any(q in al for q in preds[i]) else 0.0))
        # main axis = along the row; cross axis = across layers
        along = [size[i][1 if lr else 0] for i in row]
        total = sum(along) + GAP_X * (len(row) - 1) * (0.7 if lr else 1)
        cross = max(size[i][0 if lr else 1] for i in row)
        p = -total / 2
        for i, a in zip(row, along):
            c = p + a / 2; p += a + GAP_X * (0.7 if lr else 1); al[i] = c
            pos[i] = (depth_off + cross / 2, -c) if lr else (c, -(depth_off + cross / 2))
        depth_off += cross + (GAP_Y + 0.6 if lr else GAP_Y)
    return pos, back


def render_diagram(ir, out, stem) -> Rendered:
    label = {n.id: _wrap(n.label) for n in ir.nodes}
    size = _measure(label)
    pos, back = layout(ir, size)
    nb = len(back)
    x0 = min(pos[i][0] - size[i][0] / 2 for i in pos) - 0.4; x1 = max(pos[i][0] + size[i][0] / 2 for i in pos) + 0.4 + (0.2 * nb + 0.3 if nb and ir.direction == 'TB' else 0)
    y0 = min(pos[i][1] - size[i][1] / 2 for i in pos) - 0.4 - (0.2 * nb + 0.3 if nb and ir.direction == 'LR' else 0); y1 = max(pos[i][1] + size[i][1] / 2 for i in pos) + 0.7
    fig = plt.figure(figsize=(max(x1 - x0, 3.2), max(y1 - y0, 2)), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis("off")
    ax.text((x0 + x1) / 2, y1 - 0.2, ir.title, ha="center", va="center", fontsize=12, weight="bold")
    boxes = {}
    for i, (x, y) in pos.items():
        w, h = size[i]
        b = FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc="#e8f0fe", ec="#1a3c8f", lw=1.2, zorder=2)
        ax.add_patch(b); boxes[i] = b
        ax.text(x, y, label[i], ha="center", va="center", fontsize=FS, zorder=3)
    pairs = {(e.src, e.dst) for e in ir.edges}
    lr = ir.direction == "LR"
    nback = 0
    for k, e in enumerate(ir.edges):
        if e.src not in pos or e.dst not in pos:
            continue
        (sx, sy), (tx, ty) = pos[e.src], pos[e.dst]
        lab_xy = ((sx + tx) / 2, (sy + ty) / 2)
        if k in back:
            nback += 1
            if lr:
                ch = y0 + 0.25 + 0.2 * nback
                pts = [(sx, sy - size[e.src][1] / 2), (sx, ch), (tx, ch), (tx, ty - size[e.dst][1] / 2)]
            else:
                ch = x1 - 0.25 - 0.2 * nback
                pts = [(sx + size[e.src][0] / 2, sy), (ch, sy), (ch, ty), (tx + size[e.dst][0] / 2, ty)]
            for (ax_, ay_), (bx_, by_) in zip(pts[:-2], pts[1:-1]):
                ax.plot([ax_, bx_], [ay_, by_], color="#333", lw=1.3, zorder=1)
            ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=14, lw=1.3, color="#333", shrinkA=0, shrinkB=0, zorder=1))
            lab_xy = ((pts[1][0] + pts[2][0]) / 2, (pts[1][1] + pts[2][1]) / 2)
        else:
            rad = 0.25 if (e.dst, e.src) in pairs else 0.0
            ax.add_patch(FancyArrowPatch(pos[e.src], pos[e.dst], patchA=boxes[e.src], patchB=boxes[e.dst], arrowstyle="-|>", mutation_scale=14,
                                         lw=1.3, color="#333", connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2, zorder=1))
        if e.label:
            ax.text(*lab_xy, e.label, ha="center", va="center", fontsize=8, color="#7a1f1f", bbox=dict(fc="white", ec="none", pad=1.2), zorder=4)
    png, svg = out / f"{stem}.png", out / f"{stem}.svg"
    fig.savefig(png); fig.savefig(svg); plt.close(fig)
    return Rendered(png, svg, [ir.title] + [n.label for n in ir.nodes] + [e.label for e in ir.edges if e.label])

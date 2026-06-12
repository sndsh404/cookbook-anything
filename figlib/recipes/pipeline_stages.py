"""pipeline_stages: sequential processes (build steps, ETL). Stage boxes in a
row, artifact labels riding the arrows between them. One idea: the order.
"""
from __future__ import annotations

from . import CEILINGS, arrow, bare_axes, node_box

BOX_W, BOX_H, GAP = 1.9, 0.65, 1.15


def render(payload, model):
    if len(payload.nodes) > CEILINGS["pipeline_stages"]:
        raise ValueError(f"pipeline_stages ceiling is {CEILINGS['pipeline_stages']} (F-09)")
    n = len(payload.nodes)
    fig_w = max(4.0, n * (BOX_W + GAP) - GAP + 0.8)
    fig_h = 2.1
    fig, ax = bare_axes(fig_w, fig_h)

    centers = {}
    y = 0.65
    for i, node in enumerate(payload.nodes):
        x = 0.4 + i * (BOX_W + GAP)
        node_box(ax, x, y, BOX_W, BOX_H, node.label, node.role)
        centers[node.id] = (x + BOX_W / 2, y + BOX_H / 2)

    by_pair = {(e.source, e.target): e for e in payload.edges}
    for i in range(n - 1):
        a, b = payload.nodes[i], payload.nodes[i + 1]
        e = by_pair.get((a.id, b.id))
        p1, p2 = centers[a.id], centers[b.id]
        arrow(ax, (p1[0] + BOX_W / 2, p1[1]), (p2[0] - BOX_W / 2, p2[1]),
              dashed=bool(e and e.unverified), label=e.label if e else "")

    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    return fig

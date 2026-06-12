"""dataflow: how a request or datum moves through the system. Ordered nodes
left to right, directed labeled arrows. One idea: the path.
"""
from __future__ import annotations

from . import CEILINGS, arrow, bare_axes, node_box

BOX_W, BOX_H, GAP = 2.0, 0.6, 1.0


def render(payload, model):
    if len(payload.nodes) > CEILINGS["dataflow"]:
        raise ValueError(f"dataflow ceiling is {CEILINGS['dataflow']} nodes (F-09)")
    n = len(payload.nodes)
    fig_w = max(4.0, n * (BOX_W + GAP) - GAP + 0.8)
    fig_h = 2.0
    fig, ax = bare_axes(fig_w, fig_h)

    centers = {}
    y = 0.7
    for i, node in enumerate(payload.nodes):
        x = 0.4 + i * (BOX_W + GAP)
        node_box(ax, x, y, BOX_W, BOX_H, node.label, node.role)
        centers[node.id] = (x + BOX_W / 2, y + BOX_H / 2)

    for e in payload.edges:
        if e.source in centers and e.target in centers:
            p1, p2 = centers[e.source], centers[e.target]
            sgn = 1 if p2[0] > p1[0] else -1
            arrow(ax, (p1[0] + sgn * BOX_W / 2, p1[1]),
                  (p2[0] - sgn * BOX_W / 2, p2[1]),
                  dashed=e.unverified, label=e.label)

    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    return fig

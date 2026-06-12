"""dependency_graph: what imports/uses what. Nodes layered by dependency
depth (dependencies left, dependents right), curved arrows. Beyond 25 nodes
the planner must cluster or split; this recipe refuses rather than cram.
"""
from __future__ import annotations

from collections import defaultdict

from . import CEILINGS, arrow, bare_axes, node_box

BOX_W, BOX_H = 2.1, 0.5
COL_GAP, ROW_GAP = 1.2, 0.28


def render(payload, model):
    if len(payload.nodes) > CEILINGS["dependency_graph"]:
        raise ValueError(
            f"dependency_graph ceiling is {CEILINGS['dependency_graph']} nodes; "
            "cluster or split (F-09)")

    ids = [n.id for n in payload.nodes]
    deps = defaultdict(set)  # node -> nodes it depends on (edge source->target)
    for e in payload.edges:
        if e.source in ids and e.target in ids:
            deps[e.source].add(e.target)

    # level = longest dependency chain below the node
    level: dict[str, int] = {}

    def depth(nid, seen=()):
        if nid in level:
            return level[nid]
        if nid in seen:
            return 0  # cycle: break honestly
        d = 1 + max((depth(t, seen + (nid,)) for t in deps.get(nid, ())), default=-1)
        level[nid] = d
        return d

    for nid in ids:
        depth(nid)

    cols = defaultdict(list)
    for n in payload.nodes:
        cols[level[n.id]].append(n)
    n_cols = max(cols) + 1
    max_rows = max(len(v) for v in cols.values())
    fig_w = max(4.0, n_cols * (BOX_W + COL_GAP) + 0.6)
    fig_h = max(2.2, max_rows * (BOX_H + ROW_GAP) + 1.0)
    fig, ax = bare_axes(fig_w, fig_h)

    centers = {}
    for ci in sorted(cols):
        members = cols[ci]
        x = 0.4 + ci * (BOX_W + COL_GAP)
        total = len(members) * (BOX_H + ROW_GAP) - ROW_GAP
        y0 = (fig_h - total) / 2
        for ri, n in enumerate(members):
            y = y0 + (len(members) - 1 - ri) * (BOX_H + ROW_GAP)
            node_box(ax, x, y, BOX_W, BOX_H, n.label, n.role, fontsize=9)
            centers[n.id] = (x + BOX_W / 2, y + BOX_H / 2)

    for e in payload.edges:
        if e.source in centers and e.target in centers:
            p1, p2 = centers[e.source], centers[e.target]
            sgn = 1 if p2[0] > p1[0] else -1
            arrow(ax, (p1[0] + sgn * BOX_W / 2, p1[1]),
                  (p2[0] - sgn * BOX_W / 2, p2[1]),
                  dashed=e.unverified, rad=0.15)

    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    return fig

"""architecture_box: the page-one figure. Components clustered into rounded
groups, dependencies as arrows between clusters. One idea: the system's shape.
"""
from __future__ import annotations

from collections import OrderedDict

from . import CEILINGS, arrow, bare_axes, node_box, role_colors, trunc
from style import PALETTE

BOX_W, BOX_H, GAP = 2.2, 0.52, 0.18
CLUSTER_PAD = 0.3


def render(payload, model):
    if len(payload.nodes) > CEILINGS["architecture_box"]:
        raise ValueError(
            f"architecture_box ceiling is {CEILINGS['architecture_box']} nodes; "
            f"got {len(payload.nodes)}: cluster or split (F-09)")

    clusters: "OrderedDict[str, list]" = OrderedDict()
    for n in payload.nodes:
        clusters.setdefault(n.cluster or "core", []).append(n)

    n_cl = len(clusters)
    max_rows = max(len(v) for v in clusters.values())
    cl_w = BOX_W + 2 * CLUSTER_PAD
    cl_gap = 0.9
    fig_w = max(4.0, n_cl * (cl_w + cl_gap) + 0.5)
    fig_h = max(2.4, max_rows * (BOX_H + GAP) + 1.6)
    fig, ax = bare_axes(fig_w, fig_h)

    centers = {}  # node id -> (x, y)
    cluster_tops = {}
    for ci, (cname, members) in enumerate(clusters.items()):
        cx0 = 0.4 + ci * (cl_w + cl_gap)
        rows = len(members)
        height = rows * (BOX_H + GAP) - GAP + 2 * CLUSTER_PAD
        cy0 = (fig_h - 1.0 - height) / 2 + 0.3
        # cluster frame
        from matplotlib.patches import FancyBboxPatch
        ax.add_patch(FancyBboxPatch(
            (cx0, cy0), cl_w, height, boxstyle="round,pad=0.06,rounding_size=0.12",
            linewidth=1.0, edgecolor=PALETTE["muted"], facecolor="none", zorder=1))
        ax.text(cx0 + cl_w / 2, cy0 + height + 0.16, trunc(cname, 24),
                ha="center", va="bottom", fontsize=10.5, color=PALETTE["ink"],
                fontweight="bold")
        cluster_tops[cname] = (cx0 + cl_w / 2, cy0 + height)
        for ri, n in enumerate(members):
            bx = cx0 + CLUSTER_PAD
            by = cy0 + height - CLUSTER_PAD - (ri + 1) * (BOX_H + GAP) + GAP
            node_box(ax, bx, by, BOX_W, BOX_H, n.label, n.role)
            centers[n.id] = (bx + BOX_W / 2, by + BOX_H / 2)

    for e in payload.edges:
        if e.source in centers and e.target in centers:
            p1, p2 = centers[e.source], centers[e.target]
            # exit the box on the side facing the target
            if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]):
                dx = BOX_W / 2 if p2[0] > p1[0] else -BOX_W / 2
                a, b = (p1[0] + dx, p1[1]), (p2[0] - dx, p2[1])
            else:
                dy = BOX_H / 2 if p2[1] > p1[1] else -BOX_H / 2
                a, b = (p1[0], p1[1] + dy), (p2[0], p2[1] - dy)
            arrow(ax, a, b, dashed=e.unverified, label=e.label, rad=0.12)

    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    return fig

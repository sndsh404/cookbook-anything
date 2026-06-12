"""The house recipe library (DESIGN 6.3). Freeform matplotlib is how slop
happens; the figure stage selects from this closed registry. Every recipe is
a function (payload, model) -> Figure with the house style baked in and the
one-idea rule enforced by its layout ceiling.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from constants import ANNOT_LW, CEILINGS, FILLS, PALETTE  # noqa: F401


def role_colors(role: str) -> tuple[str, str]:
    """(edge/text color, fill) for a node role."""
    return {
        "accent": (PALETTE["accent"], FILLS["accent_fill"]),
        "good": (PALETTE["good"], FILLS["good_fill"]),
        "warn": (PALETTE["warn"], FILLS["warn_fill"]),
    }.get(role, (PALETTE["ink"], FILLS["muted_fill"]))


def trunc(s: str, n: int = 26) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def node_box(ax, x, y, w, h, label, role="", fontsize=9.5):
    edge, fill = role_colors(role)
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
        linewidth=ANNOT_LW, edgecolor=edge, facecolor=fill, zorder=2))
    ax.text(x + w / 2, y + h / 2, trunc(label), ha="center", va="center",
            fontsize=fontsize, color=edge if role else PALETTE["ink"], zorder=3)


def arrow(ax, p1, p2, dashed=False, label="", color=None, rad=0.0, label_offset=0.12):
    color = color or (PALETTE["muted"] if dashed else PALETTE["ink"])
    ax.add_patch(FancyArrowPatch(
        p1, p2, arrowstyle="-|>", mutation_scale=11,
        linewidth=ANNOT_LW, linestyle=(0, (4, 3)) if dashed else "solid",
        color=color, connectionstyle=f"arc3,rad={rad}", zorder=1,
        shrinkA=2, shrinkB=2))
    if label:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + label_offset
        ax.text(mx, my, trunc(label, 22), ha="center", va="bottom",
                fontsize=9, color=PALETTE["muted"], zorder=3)


def bare_axes(fig_w: float, fig_h: float):
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_axis_off()
    ax.set_aspect("equal")
    return fig, ax


def registry():
    from . import (architecture_box, annotated_code, dataflow,
                   dependency_graph, pipeline_stages, quantity)
    return {
        "architecture_box": architecture_box.render,
        "dataflow": dataflow.render,
        "dependency_graph": dependency_graph.render,
        "pipeline_stages": pipeline_stages.render,
        "annotated_code": annotated_code.render,
        "quantity": quantity.render,
    }

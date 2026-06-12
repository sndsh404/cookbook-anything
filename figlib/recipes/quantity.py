"""quantity: numbers worth seeing. Sorted horizontal bars, direct value
labels at bar ends (no legend, ever), unit on the axis. Every number carries
a span reference, verified by figcheck. One idea: the comparison.
"""
from __future__ import annotations

import matplotlib.pyplot as plt

from . import CEILINGS, trunc
from style import DATA_LW, PALETTE

BAR_H = 0.5


def render(payload, model):
    qs = sorted(payload.quantities, key=lambda q: q.value, reverse=True)
    if len(qs) > CEILINGS["quantity"]:
        raise ValueError(f"quantity ceiling is {CEILINGS['quantity']} bars (F-09)")
    if not qs:
        raise ValueError("quantity: no quantities in payload")

    fig_h = max(1.6, len(qs) * (BAR_H + 0.25) + 0.9)
    fig, ax = plt.subplots(figsize=(6.2, fig_h))
    ys = range(len(qs), 0, -1)
    accent_idx = 0  # the largest value is the point of the figure
    colors = [PALETTE["accent"] if i == accent_idx else PALETTE["muted"]
              for i in range(len(qs))]
    ax.barh(list(ys), [q.value for q in qs], height=BAR_H, color=colors,
            edgecolor="none", zorder=2)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([trunc(q.label, 28) for q in qs], fontsize=9)
    vmax = max(q.value for q in qs)
    for y, q in zip(ys, qs):
        ax.text(q.value + vmax * 0.015, y, f"{q.value:g}", va="center",
                ha="left", fontsize=9,
                color=PALETTE["accent"] if y == len(qs) else PALETTE["ink"])
    unit = qs[0].unit
    ax.set_xlabel(unit, fontsize=10)
    ax.set_xlim(0, vmax * 1.12)
    ax.grid(axis="x", color="#dddddd", linestyle=":", linewidth=0.6, zorder=0)
    ax.spines["left"].set_linewidth(1.0)
    ax.spines["bottom"].set_linewidth(1.0)
    ax.tick_params(length=0)
    _ = DATA_LW
    fig.tight_layout()
    return fig

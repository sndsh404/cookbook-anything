"""diagrams.py - conceptual diagram helpers. These get you ~60% there; you
finish them by eye. They are deliberately simple and easy to tweak, not locked.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from figures import _finish, _resolve
from style import accent, figure_context


def _box(ax, x, y, w, h, label, edge, fill, fontsize=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                linewidth=1.4, edgecolor=edge, facecolor=fill, zorder=2))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=fontsize, color=edge, zorder=3)


def boxes_arrows(spec: dict, profile="clean", out="boxes_arrows.png", caption="") -> Path:
    """A row (or chain) of labeled boxes with arrows between them.

    spec = {"boxes": ["A", "B", "C"], "labels": ["", "calls", ""], "accent": 0}
    labels[i] rides the arrow from box i to box i+1.
    """
    prof = _resolve(profile)
    boxes = spec["boxes"]
    if not boxes:
        raise ValueError("boxes_arrows: no boxes given")
    acc = accent(prof)
    ink = prof["figures"]["ink"]
    fill = "#eef1f4"
    bw, bh, gap = 1.9, 0.7, 0.9
    n = len(boxes)
    fig_w = max(4.0, n * (bw + gap) - gap + 0.6)
    with figure_context(prof):
        fig, ax = plt.subplots(figsize=(fig_w, 2.0))
        ax.set_axis_off()
        ax.set_xlim(0, fig_w)
        ax.set_ylim(0, 2.0)
        centers = []
        hi = spec.get("accent", -1)
        for i, b in enumerate(boxes):
            x = 0.3 + i * (bw + gap)
            _box(ax, x, 0.65, bw, bh, b, acc if i == hi else ink, "#fadbd8" if i == hi else fill)
            centers.append((x + bw / 2, 0.65 + bh / 2))
        labels = spec.get("labels", [])
        for i in range(n - 1):
            (x1, y1), (x2, y2) = centers[i], centers[i + 1]
            ax.add_patch(FancyArrowPatch((x1 + bw / 2, y1), (x2 - bw / 2, y2),
                                         arrowstyle="-|>", mutation_scale=12,
                                         linewidth=1.2, color=ink))
            if i < len(labels) and labels[i]:
                ax.text((x1 + x2) / 2, y1 + 0.42, labels[i], ha="center",
                        fontsize=9, color="#777")
        return _finish(fig, ax, caption, out)


def memory_ladder(spec: dict, profile="clean", out="memory_ladder.png", caption="") -> Path:
    """A vertical ladder of layers (e.g. registers -> L1 -> L2 -> ... -> disk),
    widening downward to suggest 'bigger but slower'.

    spec = {"layers": [("registers","~1 ns"), ("L1","~1 ns"), ("disk","~1 ms")]}
    """
    prof = _resolve(profile)
    layers = spec["layers"]
    if not layers:
        raise ValueError("memory_ladder: no layers given")
    ink = prof["figures"]["ink"]
    acc = accent(prof)
    n = len(layers)
    with figure_context(prof):
        fig, ax = plt.subplots(figsize=(5.4, max(2.6, 0.7 * n + 0.6)))
        ax.set_axis_off()
        ax.set_xlim(0, 10)
        ax.set_ylim(0, n)
        for i, item in enumerate(layers):
            label = item[0] if isinstance(item, (list, tuple)) else str(item)
            note = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else ""
            w = 3.5 + i * (5.0 / max(n - 1, 1))
            x = (10 - w) / 2
            y = n - 1 - i
            edge = acc if i == 0 else ink
            _box(ax, x, y + 0.12, w, 0.76, label, edge, "#eef1f4")
            if note:
                ax.text(x + w + 0.2, y + 0.5, note, va="center", fontsize=9, color="#777")
        ax.annotate("", xy=(0.5, 0.1), xytext=(0.5, n - 0.1),
                    arrowprops=dict(arrowstyle="-|>", color="#999", lw=1.2))
        ax.text(0.2, n / 2, "bigger,\nslower", rotation=90, va="center", ha="center",
                fontsize=9, color="#999")
        return _finish(fig, ax, caption, out)


def pipeline(spec: dict, profile="clean", out="pipeline.png", caption="") -> Path:
    """A labeled left-to-right pipeline with the artifact passed between stages
    named on each arrow.

    spec = {"stages": ["intake","compile","render"],
            "artifacts": ["spans","model"]}   # artifacts[i] sits between stage i and i+1
    """
    prof = _resolve(profile)
    stages = spec["stages"]
    if not stages:
        raise ValueError("pipeline: no stages given")
    spec2 = {"boxes": stages, "labels": spec.get("artifacts", []), "accent": spec.get("accent", 0)}
    return boxes_arrows(spec2, profile=prof, out=out, caption=caption)

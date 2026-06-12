"""introspect.py - facts about a rendered figure, taken from the live artist
tree right before save. The sidecar these facts land in is ground truth for
figcheck: derived from what was actually drawn, never from declared intent.
"""
from __future__ import annotations

import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.text import Text


def _hex(color) -> str:
    try:
        rgba = mcolors.to_rgba(color)
    except (ValueError, TypeError):
        return "none"
    if rgba[3] == 0.0:
        return "none"
    return mcolors.to_hex(rgba[:3]).lower()


def collect_facts(fig) -> dict:
    """Walk the artist tree; return colors, font sizes, label bboxes, legend
    and title facts. Must be called AFTER the layout is final."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    colors: set[str] = set()
    font_sizes: list[float] = []
    labels: list[dict] = []
    titles: list[str] = []
    legends: list[dict] = []
    linewidths: list[float] = []
    n_lines = 0

    for ax in fig.get_axes():
        if ax.get_title():
            titles.append(ax.get_title())
        for leg in ([ax.get_legend()] if ax.get_legend() else []):
            bb = leg.get_window_extent(renderer)
            axbb = ax.get_window_extent(renderer)
            over_data = not (bb.x1 < axbb.x0 or bb.x0 > axbb.x1
                             or bb.y1 < axbb.y0 or bb.y0 > axbb.y1)
            legends.append({"frame_on": leg.get_frame_on(), "over_data": over_data})

    for artist in fig.findobj():
        if isinstance(artist, Text) and artist.get_visible() and artist.get_text().strip():
            colors.add(_hex(artist.get_color()))
            font_sizes.append(float(artist.get_fontsize()))
            try:
                bb = artist.get_window_extent(renderer)
                labels.append({"text": artist.get_text()[:60],
                               "bbox": [bb.x0, bb.y0, bb.x1, bb.y1]})
            except (RuntimeError, ValueError):
                pass
        elif isinstance(artist, Line2D) and artist.get_visible():
            if artist.get_linestyle() not in ("None", "none", None):
                colors.add(_hex(artist.get_color()))
                linewidths.append(float(artist.get_linewidth()))
                n_lines += 1
        elif isinstance(artist, Patch) and artist.get_visible():
            colors.add(_hex(artist.get_facecolor()))
            colors.add(_hex(artist.get_edgecolor()))

    colors.discard("none")
    return {
        "colors": sorted(colors),
        "font_sizes_pt": sorted(font_sizes),
        "labels": labels,
        "titles": titles,
        "legends": legends,
        "linewidths": sorted(set(round(w, 2) for w in linewidths)),
        "n_text_labels": len(labels),
    }

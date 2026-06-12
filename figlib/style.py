"""style.py - the house style. One file, two modes, both locked (DESIGN 6.1).

The palette is semantic, named, and closed. The default matplotlib cycle is
banned outright; figcheck enforces that every rendered color resolves to
this palette.
"""
from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# sketch mode probes for hand-drawn fonts that are rarely installed; the
# DejaVu fallback is fine and the warning spam is not
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

# semantic palette: six colors with meanings
PALETTE = {
    "ink": "#1a1a2e",     # text, axes, structure
    "accent": "#e63946",  # the one thing this figure is about
    "good": "#2a9d8f",    # healthy / verified / fast
    "warn": "#e9a23b",    # caution / fallback / slow
    "muted": "#9aa5b1",   # context elements, de-emphasized
    "paper": "#fbfaf8",   # background
}
# tints recipes may use for fills (derived, still closed)
FILLS = {
    "accent_fill": "#fadbd8",
    "good_fill": "#d8efec",
    "warn_fill": "#fbecd5",
    "muted_fill": "#eceff2",
}
GRID_COLOR = "#dddddd"
ALLOWED_COLORS = {c.lower() for c in list(PALETTE.values()) + list(FILLS.values())}
ALLOWED_COLORS |= {"#ffffff", "#000000", "none", GRID_COLOR}

FONT_MIN_PT = 9.0
AXIS_LW = 1.0
DATA_LW = 2.0
ANNOT_LW = 1.2
DOT_RADIUS = 4.0

_BASE = {
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": PALETTE["paper"],
    "figure.facecolor": PALETTE["paper"],
    "axes.facecolor": PALETTE["paper"],
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "text.color": PALETTE["ink"],
    "axes.labelcolor": PALETTE["ink"],
    "xtick.color": PALETTE["ink"],
    "ytick.color": PALETTE["ink"],
    "axes.edgecolor": PALETTE["ink"],
    "axes.linewidth": AXIS_LW,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "grid.color": GRID_COLOR,
    "grid.linestyle": ":",
    "grid.linewidth": 0.6,
    "lines.linewidth": DATA_LW,
    "axes.prop_cycle": plt.cycler(color=[PALETTE["ink"]]),  # the default cycle is banned
    "legend.frameon": False,
}


class FigureContext:
    """Apply a mode (print or sketch) for the duration of one render."""

    def __init__(self, mode: str = "print"):
        if mode not in ("print", "sketch"):
            raise ValueError(f"unknown mode {mode}; one mode per paper, print or sketch")
        self.mode = mode
        self._rc = None
        self._xkcd = None

    def __enter__(self):
        self._rc = matplotlib.rc_context(_BASE)
        self._rc.__enter__()
        if self.mode == "sketch":
            self._xkcd = plt.xkcd(scale=0.6, length=80, randomness=1.5)
            self._xkcd.__enter__()
            # xkcd resets some rc; reassert the parts that are non-negotiable
            for k in ("savefig.facecolor", "figure.facecolor", "axes.facecolor",
                      "text.color", "savefig.bbox", "figure.dpi", "savefig.dpi"):
                matplotlib.rcParams[k] = _BASE[k]
        return self

    def __exit__(self, *exc):
        if self._xkcd:
            self._xkcd.__exit__(*exc)
        self._rc.__exit__(*exc)
        return False

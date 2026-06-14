"""figures - generic figure recipes you feed real data to.

Each recipe takes a small, explicit data payload (a dict or numbers you bring)
and renders a clean figure in the chosen style profile. The recipes NEVER
invent data points: they plot exactly what you pass. Every figure leaves an
italic one-line caption slot for you to fill with the takeaway.

Two families:
  - data-driven (line_family, valley, scatter_diagonal, bars): the exact ones,
    for your measured numbers.
  - conceptual (boxes_arrows, memory_ladder, pipeline) and math (equation):
    starting points you finish by eye.

    from figures import line_family
    line_family({"series": {...}, "xlabel": "...", ...}, profile="chinchilla",
                out="loss.png", caption="loss falls as a power law in tokens")
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt  # noqa: E402

from style import accent, figure_context, load_profile, palette  # noqa: E402

ONE_IDEA_NOTE = "one figure, one idea: no dual axes, no rainbow colormaps, no chartjunk"


def _finish(fig, ax, caption: str, out: str | Path) -> Path:
    """Apply the caption slot and save. Returns the path written."""
    if caption:
        fig.text(0.5, -0.02, caption, ha="center", va="top",
                 fontsize=10, fontstyle="italic", wrap=True)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


def _resolve(profile) -> dict:
    return profile if isinstance(profile, dict) else load_profile(profile)

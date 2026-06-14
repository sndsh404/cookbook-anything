"""math.py - render a LaTeX-style formula cleanly as an image, so equations can
be dropped into a post without fighting fonts. Uses matplotlib mathtext (no
LaTeX install needed). Pass the formula in mathtext/LaTeX syntax WITHOUT the
surrounding $.

    equation(r"L(N, D) = E + \\frac{A}{N^\\alpha} + \\frac{B}{D^\\beta}",
             profile="chinchilla", out="loss_law.png",
             caption="the chinchilla loss law: irreducible loss plus two power terms")
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from figures import _finish, _resolve
from style import figure_context


def equation(formula: str, profile="clean", out="equation.png", caption="",
             fontsize: int = 22) -> Path:
    prof = _resolve(profile)
    ink = prof["figures"]["ink"]
    with figure_context(prof):
        # mathtext renders within $...$; size the canvas to the text
        fig = plt.figure(figsize=(6.0, 1.6))
        fig.text(0.5, 0.55, f"${formula}$", ha="center", va="center",
                 fontsize=fontsize, color=ink)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        return _finish(fig, ax, caption, out)

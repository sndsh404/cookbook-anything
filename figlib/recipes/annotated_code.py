"""annotated_code: walk a specific snippet. The code comes from a model span
(rendered, never screenshotted); annotations anchor to line numbers with
accent callouts. One idea: what to notice in this code.
"""
from __future__ import annotations

from . import CEILINGS, bare_axes, trunc
from style import FILLS, PALETTE

LINE_H = 0.26
CODE_FS = 9


def render(payload, model):
    spans = {s["id"]: s for s in model.get("spans", [])}
    span = spans.get(payload.code_span)
    if span is None:
        raise ValueError(f"annotated_code: span {payload.code_span} not in model (F-01)")
    lines = span.get("text", "").splitlines()[: CEILINGS["annotated_code"]]
    if not lines:
        raise ValueError("annotated_code: span has no text")

    notes = {int(a["line"]): a["text"] for a in payload.code_annotations}
    lines = [ln[:80] for ln in lines]
    code_w = min(max((len(ln) for ln in lines), default=20), 80) * 0.098 + 1.0
    note_w = 2.9 if notes else 0.2
    fig_h = len(lines) * LINE_H + 0.8
    fig_w = code_w + note_w + 0.6
    fig, ax = bare_axes(fig_w, fig_h)
    ax.set_aspect("auto")

    top = fig_h - 0.4
    for i, ln in enumerate(lines):
        y = top - i * LINE_H
        lineno = i + 1
        highlighted = lineno in notes
        if highlighted:
            from matplotlib.patches import Rectangle
            ax.add_patch(Rectangle((0.55, y - LINE_H * 0.45), code_w - 0.4, LINE_H * 0.95,
                                   facecolor=FILLS["accent_fill"], edgecolor="none", zorder=1))
        ax.text(0.45, y, str(lineno), ha="right", va="center", fontsize=CODE_FS,
                color=PALETTE["muted"], family="monospace", zorder=2)
        ax.text(0.62, y, ln.rstrip(), ha="left", va="center", fontsize=CODE_FS,
                color=PALETTE["accent"] if highlighted else PALETTE["ink"],
                family="monospace", zorder=2)

    for k, (lineno, note) in enumerate(sorted(notes.items())):
        y = top - (lineno - 1) * LINE_H
        nx = code_w + 0.45
        ax.annotate(
            trunc(note, 38), xy=(code_w + 0.05, y), xytext=(nx, y),
            fontsize=9, color=PALETTE["accent"], va="center",
            arrowprops=dict(arrowstyle="-", color=PALETTE["accent"], lw=1.0))

    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    return fig

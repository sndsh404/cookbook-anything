"""data.py - the exact, data-driven recipes. They plot what you give them and
nothing else. Good for loss-vs-tokens curves, the isoFLOP valley,
predicted-vs-observed scatter, and simple bar comparisons.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from figures import _finish, _resolve
from style import accent, figure_context, palette


def line_family(spec: dict, profile="clean", out="line_family.png", caption="") -> Path:
    """A family of lines on shared axes (e.g. loss vs tokens for several model
    sizes). Lines are labeled directly at their right end, not in a legend box.

    spec = {
      "series": {"label1": ([x...], [y...]), "label2": ([x...], [y...])},
      "xlabel": "tokens seen", "ylabel": "loss",
      "logx": True, "logy": True,            # optional
      "title": "",                            # optional, usually empty
    }
    """
    prof = _resolve(profile)
    series = spec["series"]
    if not series:
        raise ValueError("line_family: no series given (plot what you bring, nothing invented)")
    colors = palette(prof)
    with figure_context(prof):
        fig, ax = plt.subplots(figsize=(6.2, 4.0))
        xmax = None
        for i, (label, (xs, ys)) in enumerate(series.items()):
            if len(xs) != len(ys):
                raise ValueError(f"series '{label}': x and y differ in length")
            c = colors[i % len(colors)]
            ax.plot(xs, ys, color=c, marker="o", markersize=3)
            ax.text(xs[-1], ys[-1], f" {label}", color=c, va="center", fontsize=9.5)
            xmax = max(xmax, max(xs)) if xmax is not None else max(xs)
        if spec.get("logx"):
            ax.set_xscale("log")
        if spec.get("logy"):
            ax.set_yscale("log")
        ax.set_xlabel(spec.get("xlabel", ""))
        ax.set_ylabel(spec.get("ylabel", ""))
        if spec.get("title"):
            ax.set_title(spec["title"])
        # room on the right for the direct labels
        ax.margins(x=0.12)
        return _finish(fig, ax, caption, out)


def valley(spec: dict, profile="clean", out="valley.png", caption="") -> Path:
    """An isoFLOP valley: for each compute budget, loss vs a parameter (e.g.
    model size), with the minimum of each curve marked. The classic
    'compute-optimal sits at the bottom of the valley' figure.

    spec = {
      "curves": {"1e15 FLOPs": ([sizes...], [losses...]), ...},
      "xlabel": "parameters", "ylabel": "final loss",
      "logx": True,
      "mark_min": True,
    }
    """
    prof = _resolve(profile)
    curves = spec["curves"]
    if not curves:
        raise ValueError("valley: no curves given")
    colors = palette(prof)
    acc = accent(prof)
    with figure_context(prof):
        fig, ax = plt.subplots(figsize=(6.2, 4.2))
        mins = []
        for i, (label, (xs, ys)) in enumerate(curves.items()):
            c = colors[i % len(colors)]
            ax.plot(xs, ys, color=c, marker="o", markersize=3)
            ax.text(xs[-1], ys[-1], f" {label}", color=c, va="center", fontsize=9)
            j = min(range(len(ys)), key=lambda k: ys[k])
            mins.append((xs[j], ys[j]))
        if spec.get("mark_min", True) and mins:
            mx, my = zip(*mins)
            ax.plot(mx, my, color=acc, linestyle="--", marker="D", markersize=5,
                    label="per-budget optimum")
            ax.legend(loc="best")
        if spec.get("logx"):
            ax.set_xscale("log")
        ax.set_xlabel(spec.get("xlabel", ""))
        ax.set_ylabel(spec.get("ylabel", ""))
        ax.margins(x=0.12)
        return _finish(fig, ax, caption, out)


def scatter_diagonal(spec: dict, profile="clean", out="scatter_diagonal.png", caption="") -> Path:
    """Predicted vs observed, with the y=x diagonal. Points on the line mean the
    prediction held.

    spec = {
      "predicted": [...], "observed": [...],
      "labels": [...],                 # optional per-point labels
      "xlabel": "predicted loss", "ylabel": "observed loss",
    }
    """
    prof = _resolve(profile)
    pred = spec["predicted"]
    obs = spec["observed"]
    if len(pred) != len(obs):
        raise ValueError("scatter_diagonal: predicted and observed differ in length")
    if not pred:
        raise ValueError("scatter_diagonal: no points given")
    acc = accent(prof)
    ink = prof["figures"]["ink"]
    with figure_context(prof):
        fig, ax = plt.subplots(figsize=(4.8, 4.8))
        lo = min(min(pred), min(obs))
        hi = max(max(pred), max(obs))
        pad = (hi - lo) * 0.08 or 1.0
        ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], color=ink,
                linestyle="--", linewidth=1.0, label="y = x")
        ax.scatter(pred, obs, color=acc, s=36, zorder=3)
        for x, y, lab in zip(pred, obs, spec.get("labels", [])):
            ax.text(x, y, f" {lab}", fontsize=9, va="center")
        ax.set_xlim(lo - pad, hi + pad)
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_aspect("equal")
        ax.set_xlabel(spec.get("xlabel", "predicted"))
        ax.set_ylabel(spec.get("ylabel", "observed"))
        ax.legend(loc="upper left")
        return _finish(fig, ax, caption, out)


def bars(spec: dict, profile="clean", out="bars.png", caption="") -> Path:
    """A simple bar comparison, sorted, with one bar accented. No pies, no
    stacked rainbow.

    spec = {
      "values": {"label1": v1, "label2": v2, ...},
      "ylabel": "throughput (TB/s)",
      "accent": "label2",            # optional: which bar to highlight
      "sort": True,
    }
    """
    prof = _resolve(profile)
    values = spec["values"]
    if not values:
        raise ValueError("bars: no values given")
    items = list(values.items())
    if spec.get("sort", True):
        items.sort(key=lambda kv: kv[1], reverse=True)
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    acc = accent(prof)
    muted = prof["figures"]["palette"][3] if len(prof["figures"]["palette"]) > 3 else "#9aa5b1"
    hi = spec.get("accent")
    colors = [acc if k == hi else muted for k in labels]
    with figure_context(prof):
        fig, ax = plt.subplots(figsize=(6.0, max(2.2, 0.5 * len(labels) + 1)))
        ys = range(len(labels), 0, -1)
        ax.barh(list(ys), vals, color=colors, edgecolor="none")
        ax.set_yticks(list(ys))
        ax.set_yticklabels(labels, fontsize=10)
        vmax = max(vals)
        for y, v in zip(ys, vals):
            ax.text(v + vmax * 0.01, y, f"{v:g}", va="center", ha="left", fontsize=9)
        ax.set_xlabel(spec.get("ylabel", ""))
        ax.set_xlim(0, vmax * 1.14)
        ax.tick_params(length=0)
        return _finish(fig, ax, caption, out)

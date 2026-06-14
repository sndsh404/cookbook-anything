"""render.py - render one figure from a data spec file, no Python needed.

    python render.py <recipe> <spec.json> --profile chinchilla --out loss.png \
        --caption "loss falls predictably as tokens grow"

recipe is one of: line_family, valley, scatter_diagonal, bars, boxes_arrows,
memory_ladder, pipeline, equation. The spec file is JSON shaped for that recipe
(see figures/data.py and figures/diagrams.py docstrings). For `equation`, the
spec file is a plain text file containing the mathtext formula.

It plots exactly what the spec contains and never invents data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures.data import bars, line_family, scatter_diagonal, valley
from figures.diagrams import boxes_arrows, memory_ladder, pipeline
from figures.math import equation

RECIPES = {
    "line_family": line_family,
    "valley": valley,
    "scatter_diagonal": scatter_diagonal,
    "bars": bars,
    "boxes_arrows": boxes_arrows,
    "memory_ladder": memory_ladder,
    "pipeline": pipeline,
}


def _arg(name: str, default: str = "") -> str:
    i = sys.argv.index(f"--{name}") if f"--{name}" in sys.argv else -1
    return sys.argv[i + 1] if i >= 0 else default


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        print("recipes:", ", ".join(list(RECIPES) + ["equation"]))
        return 2
    recipe = sys.argv[1]
    spec_path = Path(sys.argv[2])
    profile = _arg("profile", "clean")
    out = _arg("out", f"{recipe}.png")
    caption = _arg("caption", "")

    if recipe == "equation":
        formula = spec_path.read_text(encoding="utf-8").strip()
        p = equation(formula, profile=profile, out=out, caption=caption)
        print(f"rendered {p} (equation, {profile})")
        return 0
    if recipe not in RECIPES:
        print(f"unknown recipe '{recipe}'. choices: {', '.join(list(RECIPES) + ['equation'])}")
        return 2
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    # JSON arrays-of-pairs for series/curves become tuples the recipes expect
    for key in ("series", "curves"):
        if key in spec:
            spec[key] = {k: tuple(v) for k, v in spec[key].items()}
    p = RECIPES[recipe](spec, profile=profile, out=out, caption=caption)
    print(f"rendered {p} ({recipe}, {profile})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

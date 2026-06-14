"""style.py - load a named style profile and apply its look.

A profile is a TOML file in authoring/profiles/. This module reads one, fills
missing fields from the baseline, and gives the figure recipes a matplotlib
context (clean or xkcd mode). It also exposes the structural/voice fields the
scaffold uses. Read-only; it never calls a model.

    from style import load_profile, figure_context
    prof = load_profile("layers")
    with figure_context(prof):
        ... draw ...
"""
from __future__ import annotations

import logging
import tomllib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"

BASELINE = {
    "name": "clean",
    "source": "baseline",
    "kind": "design",
    "structure": {
        "opening": "problem",
        "section_flow": "concept-walk",
        "close": "reading-list",
        "heading_case": "lower",
        "typical_sections": 7,
        "figures_per_post": 4,
    },
    "voice": {
        "person": "second",
        "sentence_rhythm": "short to medium, plain",
        "analogies": "light",
        "tone": "plain, confident",
        "notes": "",
    },
    "type": {"body_font": "monospace", "heading_font": "monospace"},
    "figures": {
        "mode": "clean",
        "background": "#fbfaf8",
        "ink": "#1a1a2e",
        "palette": ["#e63946", "#2a9d8f", "#e9a23b", "#9aa5b1", "#1a1a2e"],
        "line_weight": 2.0,
        "grid": "light-dotted",
        "caption_style": "italic",
        "font_min_pt": 9,
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = {k: (v.copy() if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def list_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.toml") if not p.stem.startswith("_"))


def load_profile(name: str) -> dict:
    """Load a profile by name (filename without .toml), merged over the baseline."""
    path = PROFILES_DIR / f"{name}.toml"
    if not path.exists():
        raise FileNotFoundError(
            f"no profile '{name}'. available: {', '.join(list_profiles())}")
    over = tomllib.loads(path.read_text(encoding="utf-8"))
    return _merge(BASELINE, over)


def _rc(prof: dict) -> dict:
    f = prof["figures"]
    grid_on = f.get("grid", "none") != "none"
    body = prof["type"].get("body_font", "monospace")
    family = "monospace" if body == "monospace" else "sans-serif"
    return {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "figure.facecolor": f["background"],
        "savefig.facecolor": f["background"],
        "axes.facecolor": f["background"],
        "font.family": family,
        "font.size": 11,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "xtick.labelsize": max(f.get("font_min_pt", 9), 9),
        "ytick.labelsize": max(f.get("font_min_pt", 9), 9),
        "text.color": f["ink"],
        "axes.labelcolor": f["ink"],
        "axes.edgecolor": f["ink"],
        "xtick.color": f["ink"],
        "ytick.color": f["ink"],
        "axes.linewidth": 1.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": grid_on,
        "grid.color": "#dddddd",
        "grid.linestyle": ":" if f.get("grid") == "light-dotted" else "-",
        "grid.linewidth": 0.6,
        "lines.linewidth": f.get("line_weight", 2.0),
        "axes.prop_cycle": plt.cycler(color=f["palette"]),
        "legend.frameon": False,
    }


class figure_context:
    """Apply a profile's matplotlib look for the duration of one figure."""

    def __init__(self, prof: dict):
        self.prof = prof
        self.mode = prof["figures"].get("mode", "clean")
        self._rc_ctx = None
        self._xkcd = None

    def __enter__(self):
        self._rc_ctx = matplotlib.rc_context(_rc(self.prof))
        self._rc_ctx.__enter__()
        if self.mode == "xkcd":
            self._xkcd = plt.xkcd(scale=0.6, length=80, randomness=1.5)
            self._xkcd.__enter__()
            # xkcd resets some rc; reassert what must hold
            for k in ("savefig.facecolor", "figure.facecolor", "axes.facecolor",
                      "text.color", "savefig.bbox", "figure.dpi", "savefig.dpi"):
                matplotlib.rcParams[k] = _rc(self.prof)[k]
        return self

    def __exit__(self, *exc):
        if self._xkcd:
            self._xkcd.__exit__(*exc)
        self._rc_ctx.__exit__(*exc)
        return False


def palette(prof: dict) -> list[str]:
    return prof["figures"]["palette"]


def accent(prof: dict) -> str:
    return prof["figures"]["palette"][0]


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "clean"
    p = load_profile(name)
    print(f"profile: {p['name']} ({p['source']})")
    print(f"  opening={p['structure']['opening']} flow={p['structure']['section_flow']} "
          f"close={p['structure']['close']} headings={p['structure']['heading_case']}")
    print(f"  figures: mode={p['figures']['mode']} palette={p['figures']['palette']}")
    print(f"  available profiles: {', '.join(list_profiles())}")

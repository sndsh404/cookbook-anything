"""constants.py - house style constants with NO matplotlib import, so the
checkers (figcheck, lint) and the cache-hit path stay cheap. style.py and
recipes re-export from here; this is the single source of truth.
"""
from __future__ import annotations

PALETTE = {
    "ink": "#1a1a2e",
    "accent": "#e63946",
    "good": "#2a9d8f",
    "warn": "#e9a23b",
    "muted": "#9aa5b1",
    "paper": "#fbfaf8",
}
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

# density ceilings per recipe (F-09): beyond these, cluster or split
CEILINGS = {
    "architecture_box": 14,
    "dataflow": 10,
    "dependency_graph": 25,
    "pipeline_stages": 8,
    "annotated_code": 40,
    "quantity": 12,
}

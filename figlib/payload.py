"""payload.py - the figure data contract (DESIGN 5.4).

A FigurePayload may contain ONLY: model node IDs, model edge references,
span-backed quantities, and layout hints. figcheck verifies every reference
against model.json; a figure that draws an arrow the model does not contain
fails F-01 and cannot ship.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict

RECIPES = ("architecture_box", "dataflow", "dependency_graph",
           "pipeline_stages", "annotated_code", "quantity")


@dataclass
class PayloadNode:
    id: str                      # MUST exist in model.json nodes
    label: str = ""              # display label (defaults to model name)
    cluster: str = ""            # layout hint
    role: str = ""               # "accent" | "good" | "warn" | "" (muted)


@dataclass
class PayloadEdge:
    source: str                  # MUST exist in model.json as an edge
    target: str                  # (source, target, type) triple
    type: str = "depends_on"
    label: str = ""
    unverified: bool = False     # confidence < 1.0 in the model => MUST render dashed


@dataclass
class PayloadQuantity:
    label: str
    value: float
    unit: str
    span: str                    # MUST exist in model.json spans


@dataclass
class FigurePayload:
    id: str
    recipe: str
    read: str                    # the declared Figure Read, written BEFORE drawing
    caption: str                 # a full sentence stating the takeaway
    mode: str = "print"          # one mode per paper
    density: int = 3             # dial 1..10
    nodes: list[PayloadNode] = field(default_factory=list)
    edges: list[PayloadEdge] = field(default_factory=list)
    quantities: list[PayloadQuantity] = field(default_factory=list)
    code_span: str = ""          # annotated_code: span id holding the snippet
    code_annotations: list = field(default_factory=list)  # [{line, text}]
    referenced_in: str = ""      # prose anchor (chapter/section) for F-06

    def to_dict(self) -> dict:
        return asdict(self)

    def sha(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()


def payload_from_dict(d: dict) -> FigurePayload:
    return FigurePayload(
        id=d["id"], recipe=d["recipe"], read=d.get("read", ""),
        caption=d.get("caption", ""), mode=d.get("mode", "print"),
        density=d.get("density", 3),
        nodes=[PayloadNode(**n) for n in d.get("nodes", [])],
        edges=[PayloadEdge(**e) for e in d.get("edges", [])],
        quantities=[PayloadQuantity(**q) for q in d.get("quantities", [])],
        code_span=d.get("code_span", ""),
        code_annotations=d.get("code_annotations", []),
        referenced_in=d.get("referenced_in", ""),
    )

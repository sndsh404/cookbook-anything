"""render.py - render one FigurePayload through its recipe.

Order is the contract: the Figure Read is declared in the payload BEFORE
this runs; the renderer embeds the payload hash and node IDs in the PNG
metadata and writes a sidecar JSON with facts introspected from the actual
artist tree. figcheck.py judges the sidecar + image, never our intentions.

Usage: python figlib/render.py <payload.json> <model.json> <out_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt

from introspect import collect_facts
from payload import FigurePayload, payload_from_dict
from recipes import registry
from style import FigureContext


def render_figure(payload: FigurePayload, model: dict, out_dir: Path) -> dict:
    recipes = registry()
    if payload.recipe not in recipes:
        raise ValueError(f"unknown recipe {payload.recipe}; the library is closed")
    out_dir.mkdir(parents=True, exist_ok=True)

    # incremental: an identical payload renders to an identical figure, so a
    # matching sidecar sha + existing png means zero work (M5)
    sc_path = out_dir / f"{payload.id}.sidecar.json"
    png_path = out_dir / f"{payload.id}.png"
    if sc_path.exists() and png_path.exists():
        old = json.loads(sc_path.read_text(encoding="utf-8"))
        if old.get("payload_sha") == payload.sha():
            old["cached"] = True
            return old

    with FigureContext(payload.mode):
        fig = recipes[payload.recipe](payload, model)
        facts = collect_facts(fig)
        png = out_dir / f"{payload.id}.png"
        svg = out_dir / f"{payload.id}.svg"
        node_ids = json.dumps([n.id for n in payload.nodes])
        fig.savefig(png, metadata={
            "ca:figure_id": payload.id,
            "ca:payload_sha": payload.sha(),
            "ca:node_ids": node_ids,
            "ca:read": payload.read,
        })
        fig.savefig(svg)
        plt.close(fig)

    sidecar = {
        "payload": payload.to_dict(),
        "payload_sha": payload.sha(),
        "facts": facts,
        "png": png.name,
        "svg": svg.name,
    }
    (out_dir / f"{payload.id}.sidecar.json").write_text(
        json.dumps(sidecar, indent=1), encoding="utf-8")
    return sidecar


def main() -> int:
    payload_path, model_path, out_dir = sys.argv[1:4]
    payload = payload_from_dict(json.loads(Path(payload_path).read_text(encoding="utf-8")))
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    sc = render_figure(payload, model, Path(out_dir))
    print(f"rendered {sc['png']} ({payload.recipe}, {payload.mode} mode)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

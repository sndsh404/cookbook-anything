"""Seeded defects: ten figures, each with one violation planted on purpose.
A critic is only trusted after it demonstrably catches these (DESIGN 9.2).
The figures bypass the recipe library deliberately (freeform matplotlib is
exactly how these defects happen in the wild) but write honest sidecars via
the same introspector the real renderer uses.

Usage: python figlib/seeded_defects/generate.py <out_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FIGLIB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FIGLIB))

import matplotlib.pyplot as plt

from introspect import collect_facts
from style import FigureContext, PALETTE, FILLS

TOY_MODEL = {
    "sources": [], "claims": [], "tours": [], "glossary": [], "assets": [],
    "spans": [{"id": "span:1", "source": "src:1", "locator": "x#L1", "text_sha": "t",
               "text": "def f():\n    return 1\n\ndef g():\n    return f()\n"}],
    "nodes": [
        {"id": "node:a", "type": "file", "name": "a.py", "spans": ["span:1"]},
        {"id": "node:b", "type": "file", "name": "b.py", "spans": ["span:1"]},
        {"id": "node:c", "type": "file", "name": "c.py", "spans": ["span:1"]},
    ],
    "edges": [
        {"source": "node:a", "target": "node:b", "type": "imports",
         "extractor": "ca-extract@python", "spans": ["span:1"], "confidence": 1.0},
        {"source": "node:a", "target": "node:c", "type": "depends_on",
         "extractor": "agent:planner", "spans": ["span:1"], "confidence": 0.75},
    ],
}

GOOD_CAPTION = "The intake stage filters secrets before any span is written."
GOOD_READ = "Reading this as: a dataflow figure for newcomers, print mode, density 2."


def base_payload(fid: str, **over) -> dict:
    p = {"id": fid, "recipe": "dataflow", "read": GOOD_READ,
         "caption": GOOD_CAPTION, "mode": "print", "density": 2,
         "nodes": [{"id": "node:a", "label": "a", "cluster": "", "role": ""}],
         "edges": [], "quantities": [], "code_span": "",
         "code_annotations": [], "referenced_in": "ch1"}
    p.update(over)
    return p


def save(fig, out_dir: Path, payload: dict) -> None:
    facts = collect_facts(fig)
    fig.savefig(out_dir / f"{payload['id']}.png")
    plt.close(fig)
    (out_dir / f"{payload['id']}.sidecar.json").write_text(
        json.dumps({"payload": payload, "payload_sha": "seeded", "facts": facts,
                    "png": f"{payload['id']}.png", "svg": ""}, indent=1),
        encoding="utf-8")


def simple_box_fig(label_kw=None, extra=None):
    fig, ax = plt.subplots(figsize=(4, 2.4))
    ax.set_axis_off()
    ax.add_patch(plt.Rectangle((0.2, 0.4), 0.25, 0.2, transform=ax.transAxes,
                               facecolor=FILLS["muted_fill"], edgecolor=PALETTE["ink"]))
    ax.text(0.325, 0.5, "intake", transform=ax.transAxes, ha="center", va="center",
            **(label_kw or {"fontsize": 10, "color": PALETTE["ink"]}))
    if extra:
        extra(fig, ax)
    return fig


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model.json").write_text(json.dumps(TOY_MODEL, indent=1), encoding="utf-8")
    manifest = []

    def expect(fid: str, rule: str, note: str):
        manifest.append({"id": fid, "expected_rule": rule, "note": note})

    # 1. default matplotlib color cycle (no house style at all)
    fig, ax = plt.subplots(figsize=(4, 2.4))
    for k in range(3):
        ax.plot([0, 1, 2], [k, k + 1, k * 2], label=f"s{k}")
    ax.text(0.5, 0.9, "series comparison", transform=ax.transAxes, fontsize=10)
    save(fig, out_dir, base_payload("d01_default_cycle"))
    expect("d01_default_cycle", "F-04", "default color cycle")

    # 2. jet/rainbow colors
    fig, ax = plt.subplots(figsize=(4, 2.4))
    cmap = plt.get_cmap("jet")
    for k in range(5):
        ax.bar(k, k + 1, color=cmap(k / 4))
    ax.text(0.5, 0.9, "sizes", transform=ax.transAxes, fontsize=10)
    save(fig, out_dir, base_payload("d02_jet"))
    expect("d02_jet", "F-04", "jet colormap")

    with FigureContext("print"):
        # 3. label collision: two labels printed on top of each other
        def coll(fig, ax):
            ax.text(0.325, 0.52, "buffer pool manager", transform=ax.transAxes,
                    ha="center", va="center", fontsize=10, color=PALETTE["ink"])
        fig = simple_box_fig(extra=coll)
        save(fig, out_dir, base_payload("d03_collision"))
        expect("d03_collision", "F-03", "two overlapping labels")

        # 4. 7pt label
        fig = simple_box_fig(label_kw={"fontsize": 7, "color": PALETTE["ink"]})
        save(fig, out_dir, base_payload("d04_tiny_font"))
        expect("d04_tiny_font", "F-02", "7pt label")

        # 5. boxed legend over data
        fig, ax = plt.subplots(figsize=(4, 2.4))
        ax.plot([0, 1, 2], [1, 2, 1.5], color=PALETTE["ink"], label="latency")
        ax.plot([0, 1, 2], [2, 1, 2.5], color=PALETTE["accent"], label="throughput")
        ax.legend(loc="center", frameon=True)
        save(fig, out_dir, base_payload("d05_legend_over_data"))
        expect("d05_legend_over_data", "F-07", "boxed legend over data")

        # 6. hallucinated edge: payload draws an arrow the model does not contain
        fig = simple_box_fig()
        save(fig, out_dir, base_payload(
            "d06_hallucinated_edge",
            nodes=[{"id": "node:b", "label": "b", "cluster": "", "role": ""},
                   {"id": "node:c", "label": "c", "cluster": "", "role": ""}],
            edges=[{"source": "node:b", "target": "node:c", "type": "imports",
                    "label": "", "unverified": False}]))
        expect("d06_hallucinated_edge", "F-01", "edge absent from the model")

        # 7. unverified edge rendered solid
        fig = simple_box_fig()
        save(fig, out_dir, base_payload(
            "d07_unverified_solid",
            nodes=[{"id": "node:a", "label": "a", "cluster": "", "role": ""},
                   {"id": "node:c", "label": "c", "cluster": "", "role": ""}],
            edges=[{"source": "node:a", "target": "node:c", "type": "depends_on",
                    "label": "", "unverified": False}]))
        expect("d07_unverified_solid", "F-01", "confidence<1.0 edge not dashed")

        # 8. noun-phrase caption
        fig = simple_box_fig()
        save(fig, out_dir, base_payload("d08_noun_caption",
                                        caption="Buffer pool architecture."))
        expect("d08_noun_caption", "F-05", "caption is a noun phrase")

        # 9. density: 30 nodes against the dependency_graph ceiling of 25
        fig = simple_box_fig()
        save(fig, out_dir, base_payload(
            "d09_overdense", recipe="dependency_graph",
            read="Reading this as: a dependency graph figure, print mode, density 9.",
            nodes=[{"id": "node:a", "label": f"n{k}", "cluster": "", "role": ""}
                   for k in range(30)]))
        expect("d09_overdense", "F-09", "30 nodes, ceiling 25")

        # 10. redundant title restating the caption
        def junk(fig, ax):
            ax.set_title(GOOD_CAPTION)
        fig = simple_box_fig(extra=junk)
        save(fig, out_dir, base_payload("d10_redundant_title"))
        expect("d10_redundant_title", "F-10", "title restates caption")

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"seeded {len(manifest)} defect figures into {out_dir}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

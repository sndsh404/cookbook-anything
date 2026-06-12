"""figures_from_plan.py - build FigurePayloads from plan.json + model.json,
render them into <workspace>/out/figures/, then run figcheck against the
paper. The payloads contain only model node IDs, model edge refs, and
span-backed quantities; anything else cannot reach a recipe.

Usage: python figlib/figures_from_plan.py <cookbook_dir> <workspace_dir>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figcheck import check_dir
from payload import FigurePayload, PayloadEdge, PayloadNode, PayloadQuantity
from render import render_figure


def _short(name: str) -> str:
    return name.split("/")[-1]


def build_payloads(model: dict, plan: dict) -> list[FigurePayload]:
    nodes = {n["id"]: n for n in model["nodes"]}
    file_ids = {n["id"] for n in model["nodes"] if n["type"] == "file"}
    imp = [e for e in model["edges"] if e["type"] == "imports"
           and e["source"] in file_ids and e["target"] in file_ids]
    payloads: list[FigurePayload] = []

    # ---- page one: the clusters and their members
    chapters = plan["chapters"]
    arch_nodes, arch_ids, labels = [], set(), set()
    for ch in chapters[:3]:
        for nid in ch["node_ids"][:3]:
            if nid not in nodes:
                continue
            label = _short(nodes[nid]["name"])
            if label in labels:
                label = "/".join(nodes[nid]["name"].split("/")[-2:])
            labels.add(label)
            arch_nodes.append(PayloadNode(id=nid, label=label, cluster=ch["title"],
                                          role="accent" if not arch_nodes else ""))
            arch_ids.add(nid)
    arch_edges = [PayloadEdge(source=e["source"], target=e["target"], type="imports")
                  for e in imp if e["source"] in arch_ids and e["target"] in arch_ids][:8]
    payloads.append(FigurePayload(
        id="fig_page_one", recipe="architecture_box",
        read=f"Reading this as: an architecture box figure for newcomers, "
             f"{len(arch_nodes)} nodes in {min(3, len(chapters))} clusters, print mode, density 3.",
        caption="The areas of this codebase and the files that anchor each one.",
        nodes=arch_nodes, edges=arch_edges, referenced_in="tldr"))

    # ---- one figure per chapter
    for ch in chapters:
        fid = f"fig_ch{ch['index'] + 1}"
        members = [nid for nid in ch["node_ids"] if nid in nodes]
        intra = [e for e in imp if e["source"] in members and e["target"] in members]
        recipe = ch["figure"]["recipe"]
        if recipe == "dependency_graph" and len(intra) >= 2:
            pop = Counter(e["target"] for e in intra)
            hub = pop.most_common(1)[0][0]
            users = [e["source"] for e in intra if e["target"] == hub][:9]
            ids = [hub] + [u for u in users if u != hub]
            pn = [PayloadNode(id=i, label=_short(nodes[i]["name"]),
                              role="accent" if i == hub else "") for i in ids]
            pe = [PayloadEdge(source=u, target=hub, type="imports")
                  for u in ids if u != hub
                  and any(e["source"] == u and e["target"] == hub for e in intra)]
            payloads.append(FigurePayload(
                id=fid, recipe="dependency_graph",
                read=f"Reading this as: a dependency graph figure of the {ch['title']} "
                     f"area, {len(ids)} nodes, accent on the hub, print mode, density 4.",
                caption=f"Inside {ch['title']}, most files lean on one hub module.",
                nodes=pn, edges=pe, referenced_in=f"ch{ch['index'] + 1}"))
        else:
            ranked = sorted((nodes[m] for m in members),
                            key=lambda n: -(n.get("attrs", {}).get("loc", 0) or 0))[:6]
            ranked = [n for n in ranked if n.get("attrs", {}).get("loc") and n.get("spans")]
            if not ranked:
                continue
            payloads.append(FigurePayload(
                id=fid, recipe="quantity",
                read=f"Reading this as: a quantity figure sizing the {ch['title']} "
                     "area's files, print mode, density 2.",
                caption=f"A few files carry most of the code in {ch['title']}.",
                quantities=[PayloadQuantity(label=_short(n["name"]),
                                            value=float(n["attrs"]["loc"]),
                                            unit="lines of code", span=n["spans"][0])
                            for n in ranked],
                referenced_in=f"ch{ch['index'] + 1}"))
    return payloads


def main() -> int:
    cb = Path(sys.argv[1])
    ws = Path(sys.argv[2])
    model = json.loads((cb / "model.json").read_text(encoding="utf-8"))
    plan = json.loads((cb / "plan.json").read_text(encoding="utf-8"))
    fig_dir = ws / "out" / "figures"
    payloads = build_payloads(model, plan)
    print(f"[Stage 5/7] figures: rendering {len(payloads)} payloads")
    for p in payloads:
        render_figure(p, model, fig_dir)
        print(f"  rendered {p.id} ({p.recipe})")
    paper = ws / "out" / "paper.md"
    report = check_dir(fig_dir, cb / "model.json", paper if paper.exists() else None)
    (ws / "out" / "figcheck_report.json").write_text(json.dumps(report, indent=1),
                                                     encoding="utf-8")
    p0 = sum(1 for f in report["findings"] if f["severity"] == "P0")
    p1 = sum(1 for f in report["findings"] if f["severity"] == "P1")
    print(f"[Stage 5/7] figcheck: {report['checked']} figures, {p0} P0, {p1} P1")
    for f in report["findings"]:
        print(f"  {f['severity']} [{f['rule']}] {f['text']}")
    return 1 if p0 or p1 else 0


if __name__ == "__main__":
    sys.exit(main())

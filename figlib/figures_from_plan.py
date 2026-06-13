"""figures_from_plan.py - build FigurePayloads from plan.json + model.json,
render them into <workspace>/out/figures/, then run figcheck against the
paper. The payloads contain only model node IDs, model edge refs, and
span-backed quantities; anything else cannot reach a recipe.

Usage: python figlib/figures_from_plan.py <cookbook_dir> <workspace_dir>
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figcheck import check_dir
from payload import FigurePayload, PayloadEdge, PayloadNode, PayloadQuantity
# render (and matplotlib) is imported lazily inside main(): a fully cached
# run never pays the matplotlib import (M5)


def _short(name: str) -> str:
    return name.split("/")[-1]


_GENERIC_DIRS = {"src", "lib", "source"}


def _labeler(model: dict):
    """Disambiguated short labels: basename if unique among file nodes, else
    qualified by the nearest non-generic ancestor dir, so five lib.rs become
    ca-model/lib.rs, ca-extract/lib.rs, ... not all 'src/lib.rs'."""
    files = [n["name"] for n in model["nodes"] if n["type"] == "file"]
    counts = Counter(_short(n) for n in files)

    def label(name: str) -> str:
        base = _short(name)
        if counts.get(base, 0) <= 1:
            return base
        parts = name.replace("\\", "/").split("/")
        for anc in reversed(parts[:-1]):
            if anc not in _GENERIC_DIRS:
                return f"{anc}/{base}"
        return "/".join(parts[-2:]) if len(parts) >= 2 else base

    return label


def build_payloads(model: dict, plan: dict) -> list[FigurePayload]:
    nodes = {n["id"]: n for n in model["nodes"]}
    file_ids = {n["id"] for n in model["nodes"] if n["type"] == "file"}
    imp = [e for e in model["edges"] if e["type"] == "imports"
           and e["source"] in file_ids and e["target"] in file_ids]
    # (source, target) -> a real edge type, calls preferred over imports, so a
    # dataflow figure of the worked path uses an edge that resolves in the model
    edge_type: dict[tuple[str, str], str] = {}
    for e in model["edges"]:
        if e["source"] in file_ids and e["target"] in file_ids:
            k = (e["source"], e["target"])
            if e["type"] == "calls" or k not in edge_type:
                edge_type[k] = e["type"]
    payloads: list[FigurePayload] = []
    lbl = _labeler(model)

    # ---- page one: the clusters and their members
    chapters = plan["chapters"]
    arch_nodes, arch_ids, labels = [], set(), set()
    for ch in chapters[:3]:
        for nid in ch["node_ids"][:3]:
            if nid not in nodes:
                continue
            label = lbl(nodes[nid]["name"])
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
        worked = [nid for nid in ch.get("worked_path", []) if nid in nodes]

        if recipe == "dataflow" and len(worked) >= 2:
            # the teaching figure: one real path through the area, each box
            # handing off to the next via a real call/import edge
            pn = [PayloadNode(id=nid, label=lbl(nodes[nid]["name"]),
                              role="accent" if k == 0 else "")
                  for k, nid in enumerate(worked)]
            pe = []
            for a, b in zip(worked, worked[1:]):
                t = edge_type.get((a, b))
                if t:
                    pe.append(PayloadEdge(source=a, target=b, type=t,
                                          label="calls" if t == "calls" else "uses"))
            payloads.append(FigurePayload(
                id=fid, recipe="dataflow",
                read=f"Reading this as: a dataflow figure following one path through "
                     f"the {ch['title']} area, {len(worked)} steps left to right, print mode, density 2.",
                caption=f"The path a task takes through {ch['title']}: each box hands off to the next.",
                nodes=pn, edges=pe, referenced_in=f"ch{ch['index'] + 1}"))
        elif recipe == "dependency_graph" and len(intra) >= 2:
            pop = Counter(e["target"] for e in intra)
            hub = pop.most_common(1)[0][0]
            users = [e["source"] for e in intra if e["target"] == hub][:9]
            ids = [hub] + [u for u in users if u != hub]
            pn = [PayloadNode(id=i, label=lbl(nodes[i]["name"]),
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
                quantities=[PayloadQuantity(label=lbl(n["name"]),
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
    render_figure = None
    for p in payloads:
        sc_path = fig_dir / f"{p.id}.sidecar.json"
        if (sc_path.exists() and (fig_dir / f"{p.id}.png").exists()
                and json.loads(sc_path.read_text(encoding="utf-8")).get("payload_sha") == p.sha()):
            print(f"  cached {p.id} ({p.recipe})")
            continue
        if render_figure is None:
            from render import render_figure  # noqa: PLC0415
        render_figure(p, model, fig_dir)
        print(f"  rendered {p.id} ({p.recipe})")
    paper = ws / "out" / "paper.md"
    report = check_dir(fig_dir, cb / "model.json", paper if paper.exists() else None)
    # a figure the prose points at but the figure stage never produced is a
    # broken reference (the inverse of F-06 orphan); flag it P1 so the gate
    # catches a paper claiming figures that do not exist
    if paper.exists():
        ptext = paper.read_text(encoding="utf-8")
        for ref in sorted(set(re.findall(r"!\[[^\]]*\]\(figures/([A-Za-z0-9_]+\.png)\)", ptext))):
            if not (fig_dir / ref).exists():
                report["findings"].append({"severity": "P1", "rule": "F-15",
                    "text": f"prose references figures/{ref} but it was never rendered"})
    (ws / "out" / "figcheck_report.json").write_text(json.dumps(report, indent=1),
                                                     encoding="utf-8")
    p0 = sum(1 for f in report["findings"] if f["severity"] == "P0")
    p1 = sum(1 for f in report["findings"] if f["severity"] == "P1")
    print(f"[Stage 5/7] figcheck: {report['checked']} figures, {p0} P0, {p1} P1")
    for f in report["findings"]:
        print(f"  {f['severity']} [{f['rule']}] {f['text']}")

    # prose lints ride in the same process (one python startup, not two)
    if paper.exists():
        from lint_prose import lint
        lf = lint(paper.read_text(encoding="utf-8"))
        (ws / "out" / "lint_report.json").write_text(
            json.dumps({"findings": lf}, indent=1), encoding="utf-8")
        lp1 = sum(1 for f in lf if f["severity"] == "P1")
        print(f"[Stage 5/7] lint_prose: {len(lf)} findings ({lp1} P1)")
        for f in lf:
            print(f"  {f['severity']} [{f['rule']}] {f['text']}")
        if lp1:
            return 1

    # the teaching gate rides here too (one python startup, not three); it is
    # report-only, grade is the single decision point
    from teaching_check import check as teaching_check
    trep = teaching_check(cb, ws)
    (ws / "out" / "teaching_report.json").write_text(json.dumps(trep, indent=1), encoding="utf-8")
    tp0 = sum(1 for f in trep["findings"] if f["severity"] == "P0")
    print(f"[Stage 5/7] teaching: {trep['passing']}/{trep['chapters']} chapters teach ({tp0} P0)")
    for f in trep["findings"]:
        print(f"  {f['severity']} [{f['rule']}] {f['text']}")
    return 1 if p0 or p1 else 0


if __name__ == "__main__":
    sys.exit(main())

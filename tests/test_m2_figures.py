"""M2 gate: the figure system, calibrated.

1. The critic (figcheck's mechanical battery) catches >= 9/10 seeded defects
   citing the correct rule IDs.
2. The provenance check rejects a hallucinated edge (defect d06).
3. The same payload renders cleanly in both modes (print + sketch).
4. All six recipes pass F-01..F-14 with zero P0/P1 on real model data
   (the llmwiki model from the M1 gate).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "figlib"))
sys.path.insert(0, str(ROOT / "tests"))

from figcheck import check_dir            # noqa: E402
from payload import (FigurePayload, PayloadEdge, PayloadNode,  # noqa: E402
                     PayloadQuantity)
from render import render_figure          # noqa: E402

WS = ROOT / "workspace" / "_m2test"
M1WS = ROOT / "workspace" / "_m1test"


def ensure_m1_model() -> dict:
    model_path = M1WS / ".cookbook" / "model.json"
    if not model_path.exists():
        r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_m1_compile.py")],
                           capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            raise RuntimeError(f"could not build m1 model: {r.stdout}\n{r.stderr}")
    return json.loads(model_path.read_text(encoding="utf-8"))


def part_a_seeded_defects(failures: list[str]) -> None:
    out = WS / "defects"
    if out.exists():
        shutil.rmtree(out)
    r = subprocess.run([sys.executable, str(ROOT / "figlib" / "seeded_defects" / "generate.py"),
                        str(out)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        failures.append(f"defect generation failed: {r.stderr[-500:]}")
        print("METRIC m2_seeded_defects_caught 0 up")
        return
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    report = check_dir(out, out / "model.json", None)
    caught = 0
    for m in manifest:
        hits = [f for f in report["findings"]
                if f["rule"] == m["expected_rule"] and f["text"].startswith(m["id"] + ":")]
        if hits:
            caught += 1
        else:
            print(f"  MISSED {m['id']} (expected {m['expected_rule']}: {m['note']})")
    print(f"METRIC m2_seeded_defects_caught {caught} up")
    if caught < 9:
        failures.append(f"critic caught {caught}/10 seeded defects (need >= 9)")
    # the hallucinated-edge defect specifically must be a P0
    d06 = [f for f in report["findings"]
           if f["text"].startswith("d06_hallucinated_edge:") and f["rule"] == "F-01"
           and f["severity"] == "P0"]
    if not d06:
        failures.append("hallucinated edge was not rejected as P0 F-01")


def build_real_payloads(model: dict) -> list[FigurePayload]:
    nodes = {n["id"]: n for n in model["nodes"]}
    edges = model["edges"]
    file_nodes = [n for n in model["nodes"] if n["type"] == "file"
                  and n["id"].endswith(".py")]

    def cluster_of(nid: str) -> str:
        parts = nid.removeprefix("node:file/").split("/")
        return parts[1] if len(parts) > 2 else "(root)"

    payloads: list[FigurePayload] = []

    # imports edges among file nodes
    fids = {n["id"] for n in file_nodes}
    imp = [e for e in edges if e["type"] == "imports"
           and e["source"] in fids and e["target"] in fids]

    # --- architecture_box (print AND sketch: the both-modes check)
    by_cluster: dict[str, list[str]] = {}
    for n in file_nodes:
        by_cluster.setdefault(cluster_of(n["id"]), []).append(n["id"])
    clusters = [kv for kv in sorted(by_cluster.items(), key=lambda kv: -len(kv[1]))
                if len(kv[1]) >= 2][:3]
    arch_nodes, arch_ids = [], set()
    for cname, members in clusters:
        for nid in members[:3]:
            label = nodes[nid]["name"].split("/")[-1]
            if any(label == a.label for a in arch_nodes):
                label = "/".join(nodes[nid]["name"].split("/")[-2:])
            arch_nodes.append(PayloadNode(
                id=nid, label=label, cluster=cname,
                role="accent" if len(arch_nodes) == 0 else ""))
            arch_ids.add(nid)
    arch_edges = [PayloadEdge(source=e["source"], target=e["target"], type="imports")
                  for e in imp if e["source"] in arch_ids and e["target"] in arch_ids][:8]
    for mode in ("print", "sketch"):
        payloads.append(FigurePayload(
            id=f"fig_arch_{mode}", recipe="architecture_box", mode=mode,
            read=f"Reading this as: an architecture box figure for newcomers, "
                 f"{len(arch_nodes)} nodes in {len(clusters)} clusters, {mode} mode, density 3.",
            caption="The api layer imports shared modules, which never import back.",
            nodes=arch_nodes, edges=arch_edges, referenced_in="ch1"))

    # --- dependency_graph: the most-imported file and its importers
    from collections import Counter
    pop = Counter(e["target"] for e in imp)
    if pop:
        hub, _ = pop.most_common(1)[0]
        users = [e["source"] for e in imp if e["target"] == hub][:8]
        ids = [hub] + users
        dg_nodes = [PayloadNode(id=i, label=nodes[i]["name"].split("/")[-1],
                                role="accent" if i == hub else "") for i in ids]
        dg_edges = [PayloadEdge(source=u, target=hub, type="imports") for u in users]
        payloads.append(FigurePayload(
            id="fig_deps", recipe="dependency_graph",
            read=f"Reading this as: a dependency graph figure, {len(ids)} nodes, "
                 "accent on the hub module, print mode, density 4.",
            caption="Most of the codebase reaches one hub module through imports.",
            nodes=dg_nodes, edges=dg_edges, referenced_in="ch2"))

    # --- dataflow + pipeline_stages: a real import chain a -> b -> c
    nxt = {}
    for e in imp:
        nxt.setdefault(e["source"], e["target"])
    chain = []
    for start in nxt:
        chain = [start]
        cur = start
        while cur in nxt and len(chain) < 4 and nxt[cur] not in chain:
            cur = nxt[cur]
            chain.append(cur)
        if len(chain) >= 3:
            break
    if len(chain) >= 3:
        ch_nodes = [PayloadNode(id=i, label=nodes[i]["name"].split("/")[-1],
                                role="accent" if k == 0 else "")
                    for k, i in enumerate(chain)]
        ch_edges = [PayloadEdge(source=chain[k], target=chain[k + 1], type="imports",
                                label="imports")
                    for k in range(len(chain) - 1)]
        payloads.append(FigurePayload(
            id="fig_flow", recipe="dataflow",
            read=f"Reading this as: a dataflow figure, {len(chain)} nodes left to right, "
                 "print mode, density 2.",
            caption="A request travels through three modules before reaching storage.",
            nodes=ch_nodes, edges=ch_edges, referenced_in="ch2"))
        payloads.append(FigurePayload(
            id="fig_pipeline", recipe="pipeline_stages",
            read=f"Reading this as: a pipeline stages figure, {len(chain)} stages, "
                 "print mode, density 2.",
            caption="Each stage hands a typed artifact to the next one.",
            nodes=ch_nodes, edges=ch_edges, referenced_in="ch3"))

    # --- annotated_code: a real function span
    func = next((n for n in model["nodes"]
                 if n["type"] == "function" and n.get("spans")
                 and 5 <= n.get("attrs", {}).get("loc", 0) <= 18), None)
    if func:
        payloads.append(FigurePayload(
            id="fig_code", recipe="annotated_code",
            read="Reading this as: an annotated code figure walking one function, "
                 "print mode, density 2.",
            caption="The function checks its inputs before doing any work.",
            code_span=func["spans"][0],
            code_annotations=[{"line": 1, "text": "the signature"},
                              {"line": 3, "text": "the early exit"}],
            referenced_in="ch3"))

    # --- quantity: real loc numbers from file nodes, span-backed
    biggest = sorted(file_nodes, key=lambda n: -n.get("attrs", {}).get("loc", 0))[:6]
    payloads.append(FigurePayload(
        id="fig_loc", recipe="quantity",
        read="Reading this as: a quantity figure comparing file sizes, "
             "print mode, density 2.",
        caption="A handful of files carry most of the code in this repo.",
        quantities=[PayloadQuantity(label=n["name"].split("/")[-1],
                                    value=float(n["attrs"]["loc"]), unit="lines of code",
                                    span=n["spans"][0]) for n in biggest],
        referenced_in="ch4"))
    return payloads


def part_b_recipes(failures: list[str]) -> None:
    model = ensure_m1_model()
    out = WS / "figures"
    if out.exists():
        shutil.rmtree(out)
    payloads = build_real_payloads(model)
    recipes_used = {p.recipe for p in payloads}
    if len(recipes_used) < 6:
        failures.append(f"only {len(recipes_used)} recipes exercised: {recipes_used}")
    modes_used = {p.mode for p in payloads}
    if modes_used != {"print", "sketch"}:
        failures.append(f"both-modes check incomplete: {modes_used}")
    for p in payloads:
        try:
            render_figure(p, model, out)
        except Exception as e:  # noqa: BLE001 - report and fail the gate
            failures.append(f"render {p.id} ({p.recipe}, {p.mode}) failed: {e}")
    report = check_dir(out, M1WS / ".cookbook" / "model.json", None)
    p01 = [f for f in report["findings"] if f["severity"] in ("P0", "P1")]
    print(f"METRIC m2_recipe_violations {len(p01)} down")
    for f in p01:
        print(f"  {f['severity']} [{f['rule']}] {f['text']}")
    if p01:
        failures.append(f"{len(p01)} P0/P1 findings on real recipe renders")
    print(f"METRIC m2_recipes_rendered {len(payloads)} up")


def main() -> int:
    failures: list[str] = []
    WS.mkdir(parents=True, exist_ok=True)
    part_a_seeded_defects(failures)
    part_b_recipes(failures)
    if failures:
        print("M2 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print("M2 GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

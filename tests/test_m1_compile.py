"""M1 gate: on a real mid-size repo (llmwiki, ~104 py + 9 sql files):
model.json validates; 100% of edges carry extractors; 100% of claims carry
spans; 0 unresolved danglers; a planted agent-proposed edge lands at
confidence < 1.0.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from intake import intake                    # noqa: E402
from compile_model import compile_model     # noqa: E402
import merge as merge_mod                    # noqa: E402
import model_schema                          # noqa: E402

REF = Path(r"C:\Users\bhansa01\Downloads\cookbook-20260611T231425Z-3-002\cookbook\llmwiki-master")
WS = ROOT / "workspace" / "_m1test"


def main() -> int:
    failures: list[str] = []
    src = WS / "sources"
    if not (src / "llmwiki").exists():
        src.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REF, src / "llmwiki",
                        ignore=shutil.ignore_patterns(".git", "node_modules", "*.png"))
    cb = WS / ".cookbook"
    if (cb / "model.json").exists():
        (cb / "model.json").unlink()

    intake(src, cb)
    model = compile_model(cb)

    errors = model_schema.validate(model)
    if errors:
        failures.append(f"schema invalid: {errors[:5]}")

    n_edges = len(model["edges"])
    with_ext = sum(1 for e in model["edges"] if e.get("extractor"))
    pct_ext = 100.0 * with_ext / n_edges if n_edges else 0.0
    print(f"METRIC m1_edges_extractor_pct {pct_ext:.1f} up")
    if pct_ext < 100.0:
        failures.append(f"edges with extractor: {pct_ext:.1f}% (need 100)")

    n_claims = len(model["claims"])
    with_spans = sum(1 for c in model["claims"] if c.get("spans"))
    pct_claims = 100.0 * with_spans / n_claims if n_claims else 0.0
    print(f"METRIC m1_claims_span_pct {pct_claims:.1f} up")
    if pct_claims < 100.0 or n_claims < 10:
        failures.append(f"claims with spans {pct_claims:.1f}%, n={n_claims} (need 100%, >=10)")

    node_ids = {n["id"] for n in model["nodes"]}
    danglers = sum(1 for e in model["edges"]
                   if e["source"] not in node_ids or e["target"] not in node_ids)
    print(f"METRIC m1_danglers {danglers} down")
    if danglers:
        failures.append(f"{danglers} dangling edges survived merge")

    if len(model["nodes"]) < 100:
        failures.append(f"suspiciously small model: {len(model['nodes'])} nodes")
    if not any(e["type"] == "foreign_key" for e in model["edges"]):
        print("note: no foreign_key edges found in llmwiki sql (not fatal)")
    if not any(e["type"] == "calls" for e in model["edges"]):
        failures.append("no calls edges at all; extractor too weak")

    # planted agent-proposed edge must land at confidence < 1.0
    two = [n["id"] for n in model["nodes"][:2]]
    model["edges"].append({"source": two[0], "target": two[1], "type": "depends_on",
                           "extractor": "agent:planner", "spans": [], "confidence": 1.0})
    model2, fixed, residue = merge_mod.merge(model)
    planted = [e for e in model2["edges"]
               if e.get("extractor") == "agent:planner"]
    if not planted or planted[0]["confidence"] >= 1.0:
        failures.append(f"planted agent edge not clamped: {planted}")
    else:
        print(f"planted agent edge clamped to {planted[0]['confidence']}")
    print(f"METRIC m1_agent_edge_clamped {1 if planted and planted[0]['confidence'] < 1.0 else 0} up")

    if failures:
        print("M1 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print(f"M1 GATE PASSED ({len(model['nodes'])} nodes, {n_edges} edges, {n_claims} claims)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

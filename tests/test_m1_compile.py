"""M1 gate (Rust core): on a real mid-size repo (llmwiki, ~104 py + 9 sql
files): model.json validates; 100% of edges carry extractors; 100% of claims
carry spans; 0 unresolved danglers; an agent-proposed edge at confidence 1.0
is REJECTED at load (the invariant is structural now), while one at < 1.0
loads fine.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import ca  # noqa: E402

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

    ca.intake(src, cb)
    ca.run("compile", str(cb))
    model = json.loads((cb / "model.json").read_text(encoding="utf-8"))

    proc = ca.run("validate", str(cb / "model.json"), check=False)
    if proc.returncode != 0:
        failures.append(f"ca validate rejected the compiled model: {proc.stderr[:300]}")

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
    if not any(e["type"] == "calls" for e in model["edges"]):
        failures.append("no calls edges at all; extractor too weak")
    if not any(e["type"] == "imports" for e in model["edges"]):
        failures.append("no imports edges at all")

    # the firewall test: an agent edge at confidence 1.0 must be REJECTED at
    # load; the same edge at 0.75 must be accepted
    two = sorted(node_ids)[:2]
    tampered = WS / "tampered.json"
    bad = dict(model)
    bad["edges"] = model["edges"] + [{"source": two[0], "target": two[1],
                                      "type": "depends_on", "extractor": "agent:planner",
                                      "spans": [], "confidence": 1.0}]
    tampered.write_text(json.dumps(bad), encoding="utf-8")
    rej = ca.run("validate", str(tampered), check=False)
    rejected = 1 if rej.returncode != 0 and "agent" in (rej.stderr + rej.stdout) else 0
    print(f"METRIC m1_agent_full_confidence_rejected {rejected} up")
    if not rejected:
        failures.append("tampered model with agent edge at 1.0 was NOT rejected")

    bad["edges"][-1]["confidence"] = 0.75
    tampered.write_text(json.dumps(bad), encoding="utf-8")
    ok = ca.run("validate", str(tampered), check=False)
    if ok.returncode != 0:
        failures.append(f"agent edge at 0.75 should validate: {ok.stderr[:200]}")

    if failures:
        print("M1 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print(f"M1 GATE PASSED ({len(model['nodes'])} nodes, {n_edges} edges, {n_claims} claims)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

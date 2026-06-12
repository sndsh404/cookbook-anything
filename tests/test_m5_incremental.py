"""M5 gate: the compounding loop.

A one-file change re-ships the paper with < 20% of the full-run work
(stage timings from the trace); a contradicting edit produces a superseded
claim correctly linked old-to-new; runs.jsonl reconstructs one claim's
history across three runs.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = Path(r"C:\Users\bhansa01\Downloads\cookbook-20260611T231425Z-3-002\cookbook\llmwiki-master")
WS = ROOT / "workspace" / "_m5test"
SRC = WS / "sources"


def pipeline() -> dict:
    r = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings",
         str(ROOT / "runner" / "stages.ts"), str(SRC), str(WS), "llmwiki"],
        capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(f"pipeline failed:\n{r.stdout[-1500:]}\n{r.stderr[-500:]}")
    return json.loads((WS / ".cookbook" / "timings.json").read_text(encoding="utf-8"))


def edit_readme(old: str, new: str) -> None:
    readme = SRC / "llmwiki" / "README.md"
    text = readme.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected sentence not in README: {old[:60]}")
    readme.write_text(text.replace(old, new), encoding="utf-8")


def model() -> dict:
    return json.loads((WS / ".cookbook" / "model.json").read_text(encoding="utf-8"))


def main() -> int:
    failures: list[str] = []
    if WS.exists():
        shutil.rmtree(WS)
    SRC.mkdir(parents=True)
    shutil.copytree(REF, SRC / "llmwiki",
                    ignore=shutil.ignore_patterns(".git", "node_modules", "*.png"))

    # ---- run 1: the full build
    t_full = pipeline()
    print(f"full run: {t_full['total_ms']}ms {t_full['stages']}")

    # pick a real doc claim from README to contradict
    m1 = model()
    span_loc = {s["id"]: s["locator"] for s in m1["spans"]}
    target = next(c for c in m1["claims"]
                  if c["status"] == "active" and not c["id"].startswith("c:w")
                  and span_loc.get(c["spans"][0], "").startswith("README"))
    v2_text = target["text"].rstrip(".") + " (this changed in v2)."
    v3_text = target["text"].rstrip(".") + " (and again in v3)."

    # ---- run 2: one-file contradicting edit
    edit_readme(target["text"], v2_text)
    t_incr = pipeline()
    pct = 100.0 * t_incr["total_ms"] / t_full["total_ms"]
    print(f"incremental run: {t_incr['total_ms']}ms {t_incr['stages']}")
    print(f"METRIC m5_rerun_work_pct {pct:.1f} down")
    if pct >= 20.0:
        failures.append(f"rerun took {pct:.1f}% of full-run time (need < 20%)")

    m2 = model()
    old = next((c for c in m2["claims"] if c["id"] == target["id"]), None)
    new = next((c for c in m2["claims"] if c.get("supersedes") == target["id"]), None)
    linked = (old is not None and old["status"] == "superseded"
              and new is not None and new["status"] == "active"
              and v2_text.startswith(new["text"][:40]))
    print(f"METRIC m5_supersession_linked {1 if linked else 0} up")
    if not linked:
        failures.append(f"supersession not linked: old={old and old['status']}, "
                        f"new={new and new['id']}")

    # ---- run 3: contradict again, then reconstruct the chain from runs.jsonl
    edit_readme(v2_text, v3_text)
    pipeline()
    events = []
    for line in (WS / ".cookbook" / "runs.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("stage") == "compile":
            events.extend(rec.get("claim_events", []))
    chain = [target["id"]]
    while True:
        nxt = next((e["new"] for e in events
                    if e.get("event") == "superseded" and e.get("old") == chain[-1]), None)
        if not nxt:
            break
        chain.append(nxt)
    print(f"claim history from runs.jsonl: {' -> '.join(chain)}")
    print(f"METRIC m5_history_chain_len {len(chain)} up")
    if len(chain) < 3:
        failures.append(f"could not reconstruct a 3-run history (chain {chain})")
    m3 = model()
    statuses = {c["id"]: c["status"] for c in m3["claims"] if c["id"] in chain}
    if not (statuses.get(chain[0]) == "superseded"
            and statuses.get(chain[-1]) == "active"):
        failures.append(f"chain statuses wrong: {statuses}")

    if failures:
        print("M5 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print("M5 GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""M3 gate: plan + write with the leash on.

Chapter prerequisite graph acyclic (prereqs only point backwards, verified);
claim coverage >= 95% on a full draft; 0 banned words and 0 em dashes in the
shipped paper; the verifier flags a deliberately planted unsupported
sentence; the prose lints catch 10/10 planted slop violations.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "figlib"))
import ca  # noqa: E402
from lint_prose import lint  # noqa: E402

M1WS = ROOT / "workspace" / "_m1test"
CB = M1WS / ".cookbook"


def ensure_model() -> None:
    if not (CB / "model.json").exists():
        r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_m1_compile.py")],
                           capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            raise RuntimeError(f"could not build m1 model: {r.stdout}\n{r.stderr}")


def main() -> int:
    failures: list[str] = []
    ensure_model()

    # ---- plan: acyclic by construction, verified here anyway
    ca.run("plan", str(CB))
    plan = json.loads((CB / "plan.json").read_text(encoding="utf-8"))
    acyclic = all(all(p < ch["index"] for p in ch["prereqs"]) for ch in plan["chapters"])
    print(f"METRIC m3_chapter_graph_acyclic {1 if acyclic else 0} up")
    if not acyclic:
        failures.append("a chapter prerequisite points forward (cycle possible)")
    if len(plan["chapters"]) < 3:
        failures.append(f"only {len(plan['chapters'])} chapters planned")

    # ---- write a clean draft + ship + coverage
    ca.run("write", str(CB), str(M1WS), "llmwiki", "--ship")
    cov = json.loads((M1WS / "out" / "coverage.json").read_text(encoding="utf-8"))
    print(f"METRIC m3_claim_coverage {cov['claim_coverage_pct']} up")
    if cov["claim_coverage_pct"] < 95.0:
        failures.append(f"writer coverage {cov['claim_coverage_pct']}% < 95%")

    # ---- verifier agrees on the clean draft
    v = ca.run("verify", str(CB), str(M1WS), check=False)
    if v.returncode != 0:
        failures.append(f"verifier rejected the clean draft:\n{v.stdout[-400:]}")
    vr = json.loads((M1WS / "out" / "verify_report.json").read_text(encoding="utf-8"))
    if vr["broken_markers"]:
        failures.append(f"broken markers on clean draft: {vr['broken_markers'][:3]}")

    # ---- the planted unsupported sentence is flagged
    ca.run("write", str(CB), str(M1WS), "llmwiki", "--plant-unsupported")
    v2 = ca.run("verify", str(CB), str(M1WS), check=False)
    vr2 = json.loads((M1WS / "out" / "verify_report.json").read_text(encoding="utf-8"))
    planted_flagged = any("scheduler" in s for s in vr2["unsupported_sentences"])
    print(f"METRIC m3_planted_flagged {1 if planted_flagged else 0} up")
    if not planted_flagged:
        failures.append("planted unsupported sentence was NOT flagged")
    if v2.returncode == 0 and vr2["coverage_pct"] < 95.0:
        failures.append("verifier exited 0 despite sub-95 coverage")

    # restore the clean draft (and shipped paper) for downstream stages
    ca.run("write", str(CB), str(M1WS), "llmwiki", "--ship")

    # ---- shipped prose: 0 banned words, 0 em dashes
    shipped = (M1WS / "out" / "paper.md").read_text(encoding="utf-8")
    findings = lint(shipped)
    banned = sum(1 for f in findings if f["rule"] == "prose-banned")
    emdash = sum(1 for f in findings if f["rule"] == "prose-emdash")
    print(f"METRIC m3_banned_words {banned} down")
    print(f"METRIC m3_emdashes {emdash} down")
    if banned or emdash:
        failures.append(f"shipped prose has {banned} banned words, {emdash} em dashes")
    if "{{" in shipped:
        failures.append("claim markers leaked into the shipped paper")
    if "## Claims appendix" not in shipped or "## Unverified appendix" not in shipped:
        failures.append("appendices missing from shipped paper")

    # ---- the prose lints catch 10/10 planted slop violations
    slop = (ROOT / "figlib" / "seeded_defects" / "prose_slop.md").read_text(encoding="utf-8")
    sf = lint(slop)
    by_rule = {}
    for f in sf:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    caught = (min(by_rule.get("prose-banned", 0), 7)
              + min(by_rule.get("prose-emdash", 0), 1)
              + min(by_rule.get("F-05", 0), 1)
              + min(by_rule.get("prose-long", 0), 1))
    print(f"METRIC m3_prose_defects_caught {caught} up")
    if caught < 10:
        failures.append(f"prose lints caught {caught}/10 planted violations ({by_rule})")

    if failures:
        print("M3 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print("M3 GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

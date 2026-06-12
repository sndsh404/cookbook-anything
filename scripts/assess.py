"""assess.py - the objective harness. The score comes from here, never from opinion.

What it does, in order:
  1. Build check: every script and figlib module compiles (py_compile).
  2. Gate tests: runs every tests/test_*.py as a subprocess. Any nonzero exit
     => score 0. Tests print "METRIC <name> <value> <up|down>" lines; those
     are the headline numbers.
  3. Regression check: compares headline numbers to .claude/state/
     last_assessment.json; a worse value in its declared direction is a
     regression and fails the gate.
  4. Hard-rule compliance on the live workspace (if a model/paper exists):
     every edge has an extractor, every claim has spans, unverified edges
     listed, banned vocabulary and em dashes in shipped prose, license
     records for assets.
  5. Checklist reconciliation: a ticked CLAUDE.md milestone box whose gate
     test is missing or failing is a P0 (checklist drift).
  6. Score: start 100; P0 -100 (or -40 for claim coverage), P1 -10, P2 -1.
     Exit nonzero if score < 80 OR any P0 OR a regression.

Writes quality_reports/assessment_latest.md and .claude/state/last_assessment.json.
"""
from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".claude" / "state"
REPORTS = ROOT / "quality_reports"
LAST = STATE / "last_assessment.json"

BANNED_WORDS = [
    "leverage", "robust", "seamless", "delve", "utilize", "streamline",
    "crucial", "comprehensive", "holistic", "in today's fast-paced world",
    "it's important to note", "dive deep",
]


class Findings:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, int]] = []  # (severity, text, deduction)

    def p0(self, text: str, deduction: int = 100) -> None:
        self.items.append(("P0", text, deduction))

    def p1(self, text: str, deduction: int = 10) -> None:
        self.items.append(("P1", text, deduction))

    def p2(self, text: str, deduction: int = 1) -> None:
        self.items.append(("P2", text, deduction))

    def has_p0(self) -> bool:
        return any(sev == "P0" for sev, _, _ in self.items)

    def score(self) -> int:
        return max(0, 100 - sum(d for _, _, d in self.items))


def check_build(f: Findings) -> bool:
    """cargo build + cargo test on the Rust core, py_compile on the Python
    leaf renderer (figlib) and harness. Any failure = score 0."""
    ok = True
    core = ROOT / "core"
    if core.exists():
        for cmd in (["cargo", "build", "--release"], ["cargo", "test", "--release", "--quiet"]):
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(core),
                                  timeout=1200, shell=False)
            if proc.returncode != 0:
                tail = "\n".join(((proc.stdout or "") + (proc.stderr or "")).splitlines()[-15:])
                f.p0(f"build: `{' '.join(cmd)}` failed\n```\n{tail}\n```")
                ok = False
                break
    else:
        f.p0("build: core/ cargo workspace missing")
        ok = False
    for d in ("scripts", "figlib", "tests"):
        base = ROOT / d
        if not base.exists():
            continue
        for py in sorted(base.rglob("*.py")):
            try:
                py_compile.compile(str(py), doraise=True)
            except py_compile.PyCompileError as e:
                f.p0(f"build: {py.relative_to(ROOT)} does not compile: {e.msg.splitlines()[0]}")
                ok = False
    return ok


def run_gate_tests(f: Findings) -> tuple[bool, dict[str, dict]]:
    """Run each tests/test_*.py. Collect METRIC lines. Any failure => gate dead."""
    metrics: dict[str, dict] = {}
    tests = sorted((ROOT / "tests").glob("test_*.py"))
    all_ok = True
    for t in tests:
        proc = subprocess.run(
            [sys.executable, str(t)], capture_output=True, text=True,
            cwd=str(ROOT), timeout=900,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        for m in re.finditer(r"^METRIC\s+(\S+)\s+([-\d.]+)\s+(up|down)\s*$", out, re.M):
            metrics[m.group(1)] = {"value": float(m.group(2)), "dir": m.group(3), "test": t.name}
        if proc.returncode != 0:
            tail = "\n".join(out.strip().splitlines()[-15:])
            f.p0(f"gate test FAILED: {t.name} (exit {proc.returncode})\n```\n{tail}\n```")
            all_ok = False
    if not tests:
        f.p1("no gate tests exist yet; nothing is verified")
    return all_ok, metrics


def check_regressions(f: Findings, metrics: dict[str, dict]) -> list[str]:
    regressions: list[str] = []
    if not LAST.exists():
        return regressions
    try:
        last = json.loads(LAST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return regressions
    last_metrics = last.get("metrics", {})
    for name, cur in metrics.items():
        prev = last_metrics.get(name)
        if not prev:
            continue
        delta = (prev["value"] - cur["value"]) if cur["dir"] == "up" else (cur["value"] - prev["value"])
        # tolerance: timing and percentage metrics jitter run to run; a real
        # regression moves more than 5% of the previous value (floor 0.05 so
        # count metrics like secrets_leaked 0 -> 1 still trip). The hard
        # thresholds live in the gate tests themselves.
        tolerance = 0.05 * max(abs(prev["value"]), 1.0)
        if delta > tolerance:
            msg = f"regression: {name} went {prev['value']} -> {cur['value']} (want {cur['dir']})"
            regressions.append(msg)
            f.p1(msg)
    return regressions


def check_hard_rules(f: Findings) -> None:
    """Compliance scan over the live workspace, if one exists."""
    model_path = ROOT / "workspace" / ".cookbook" / "model.json"
    if model_path.exists():
        try:
            model = json.loads(model_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            f.p0(f"model.json is not valid JSON: {e}")
            model = {}
        for e_ in model.get("edges", []):
            if not e_.get("extractor"):
                f.p0(f"edge {e_.get('source')}->{e_.get('target')} has no extractor (hard rule 1)")
            if e_.get("confidence", 1.0) >= 1.0 and e_.get("extractor", "").startswith("agent"):
                f.p0(f"agent-proposed edge at confidence 1.0: {e_.get('source')}->{e_.get('target')}")
        for c in model.get("claims", []):
            if not c.get("spans"):
                f.p0(f"claim {c.get('id')} has no spans (hard rule 2)")
        for a in model.get("assets", []):
            lic = a.get("license") or {}
            if not lic.get("name") or not lic.get("verified_by"):
                f.p0(f"asset {a.get('id')} lacks a verified license record (F-13)")

    paper = ROOT / "workspace" / "out" / "paper.md"
    if paper.exists():
        text = paper.read_text(encoding="utf-8", errors="replace")
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        for w in BANNED_WORDS:
            n = len(re.findall(rf"\b{re.escape(w)}\b", prose, re.I))
            if n:
                f.p1(f"banned vocabulary in shipped prose: '{w}' x{n}", deduction=3 * n)
        em = prose.count("—")
        if em:
            f.p1(f"em dashes in shipped prose: {em}", deduction=3 * em)


def reconcile_checklist(f: Findings, metrics: dict[str, dict]) -> None:
    claude = ROOT / "CLAUDE.md"
    if not claude.exists():
        f.p1("CLAUDE.md missing")
        return
    text = claude.read_text(encoding="utf-8")
    test_results = {t["test"] for t in metrics.values()}
    for m in re.finditer(r"- \[(x| )\] (M[\d.]+)", text):
        ticked, mile = m.group(1) == "x", m.group(2)
        slug = mile.lower().replace(".", "")
        gate_files = list((ROOT / "tests").glob(f"test_{slug}*.py"))
        gate_passed = any(g.name in test_results for g in gate_files)
        if ticked and not gate_passed:
            f.p0(f"checklist drift: {mile} is ticked but its gate test is missing or produced no metrics")
        if not ticked and gate_files and gate_passed:
            f.p2(f"{mile} gate passes but box is unticked (tick it)")


def main() -> int:
    f = Findings()
    built = check_build(f)
    metrics: dict[str, dict] = {}
    if built:
        tests_ok, metrics = run_gate_tests(f)
    else:
        tests_ok = False
    regressions = check_regressions(f, metrics)
    check_hard_rules(f)
    reconcile_checklist(f, metrics)

    score = 0 if not (built and tests_ok) else f.score()
    red = (score < 80) or f.has_p0() or bool(regressions)

    now = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Assessment - {now}",
        "",
        f"**Score: {score}/100** {'(RED - does not ship)' if red else '(green)'}",
        "",
        "## Headline numbers",
        "",
    ]
    for name, m in sorted(metrics.items()):
        lines.append(f"- `{name}` = {m['value']} (want {m['dir']}, from {m['test']})")
    if not metrics:
        lines.append("- none captured")
    lines += ["", "## Findings", ""]
    for sev, text, ded in sorted(f.items, key=lambda x: x[0]):
        lines.append(f"- **{sev}** (-{ded}) {text}")
    if not f.items:
        lines.append("- none")
    lines += ["", "## Regressions", ""]
    lines += [f"- {r}" for r in regressions] or ["- none"]

    REPORTS.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    (REPORTS / "assessment_latest.md").write_text("\n".join(lines), encoding="utf-8")
    LAST.write_text(json.dumps({
        "at": now, "score": score, "red": red, "metrics": metrics,
        "findings": [{"sev": s, "text": t, "deduction": d} for s, t, d in f.items],
    }, indent=2), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nEXIT {'1 (red)' if red else '0 (green)'}")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())

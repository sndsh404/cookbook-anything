"""M4 gate: ship a real paper.

Full pipeline end-to-end (stages.ts: intake -> compile -> topology -> plan
-> write -> verify -> figures -> lint -> grade) on a real codebase
(llmwiki). Ships at grade >= 80 with the page-one figure, a figure per
chapter, claims + unverified appendices, zero P0.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = Path(r"C:\Users\bhansa01\Downloads\cookbook-20260611T231425Z-3-002\cookbook\llmwiki-master")
WS = ROOT / "workspace" / "_m4test"


def main() -> int:
    failures: list[str] = []
    src = WS / "sources"
    if not (src / "llmwiki").exists():
        src.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REF, src / "llmwiki",
                        ignore=shutil.ignore_patterns(".git", "node_modules", "*.png"))

    r = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings",
         str(ROOT / "runner" / "stages.ts"), str(src), str(WS), "llmwiki"],
        capture_output=True, text=True, timeout=1800)
    sys.stdout.write(r.stdout[-3000:])
    if r.returncode != 0:
        failures.append(f"pipeline exited {r.returncode}:\n{r.stderr[-800:]}")

    grade_path = WS / "out" / "grade.json"
    score = 0
    if grade_path.exists():
        g = json.loads(grade_path.read_text(encoding="utf-8"))
        score = g["score"]
        if g["red"]:
            failures.append(f"grade is red: {[f['text'] for f in g['findings']][:5]}")
    else:
        failures.append("no grade.json produced")
    print(f"METRIC m4_grade {score} up")
    if score < 80:
        failures.append(f"grade {score} < 80, does not ship")

    paper_path = WS / "out" / "paper.md"
    if paper_path.exists():
        paper = paper_path.read_text(encoding="utf-8")
        head = "\n".join(paper.splitlines()[:60])
        if "![" not in head:
            failures.append("page-one figure missing from paper head")
        for sec in ("## Claims appendix", "## Unverified appendix", "## Glossary",
                    "## The cookbook"):
            if sec not in paper:
                failures.append(f"missing section: {sec}")
        n_ch = paper.count("## Chapter ")
        n_figs = len(list((WS / "out" / "figures").glob("fig_ch*.png")))
        print(f"METRIC m4_chapters_figured {n_figs} up")
        if n_figs < n_ch:
            failures.append(f"{n_ch} chapters but only {n_figs} chapter figures")
    else:
        failures.append("no paper.md shipped")

    fig_report = WS / "out" / "figcheck_report.json"
    if fig_report.exists():
        rep = json.loads(fig_report.read_text(encoding="utf-8"))
        p0 = sum(1 for f in rep["findings"] if f["severity"] == "P0")
        print(f"METRIC m4_figure_p0 {p0} down")
        if p0:
            failures.append(f"{p0} P0 figure findings at ship")

    if failures:
        print("M4 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print(f"M4 GATE PASSED (grade {score})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""teaching_check.py - the gate that catches a paper which verifies but does
not TEACH (the failure mode of the first dogfood: a chapter that is just "the
X area holds N files" + a filename list + a size chart).

A chapter passes only if it does the two things a Grokking-style chapter does
(see MEMORY.md): it opens with the WHY (>= 2 explanatory design claims, not
operational metrics), and its figure shows how the pieces INTERACT (a
dataflow or dependency graph), not how big the files are (a cluster-size
quantity chart). Failures are P0: a paper that lists files without teaching
does not ship.

Writes teaching_report.json, which ca-grade ingests.

Usage: python figlib/teaching_check.py <cookbook_dir> <workspace_dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MIN_DESIGN_CLAIMS = 2
INTERACTION_RECIPES = {"dataflow", "dependency_graph"}


def design_claim_ids(model: dict) -> set[str]:
    """Doc claims (c:NNNN, not writer-minted c:w) whose source is a design
    document, not a session metric under quality_reports."""
    loc = {s["id"]: s["locator"] for s in model["spans"]}
    out = set()
    for c in model["claims"]:
        if c["id"].startswith("c:w"):
            continue
        src = (loc.get(c["spans"][0], "") if c["spans"] else "").replace("\\", "/")
        if not src.startswith("quality_reports"):
            out.add(c["id"])
    return out


def chapter_figure_recipe(fig_dir: Path, idx: int) -> str | None:
    sc = fig_dir / f"fig_ch{idx}.sidecar.json"
    if not sc.exists():
        return None
    return json.loads(sc.read_text(encoding="utf-8"))["payload"].get("recipe")


def check(cookbook: Path, workspace: Path) -> dict:
    model = json.loads((cookbook / "model.json").read_text(encoding="utf-8"))
    draft = (workspace / "out" / "paper.draft.md").read_text(encoding="utf-8")
    fig_dir = workspace / "out" / "figures"
    design = design_claim_ids(model)

    findings: list[dict] = []
    passing = 0
    chapters = re.split(r"^## Chapter ", draft, flags=re.M)[1:]
    n_chapters = len(chapters)
    for chunk in chapters:
        header = chunk.split("\n", 1)[0]
        m = re.match(r"(\d+):\s*(.+)", header)
        if not m:
            continue
        idx, title = int(m.group(1)), m.group(2).strip()
        opening = chunk.split("![", 1)[0]  # prose before the first figure
        markers = re.findall(r"\{\{(c:\d+)\}\}", opening)
        n_design = sum(1 for mk in markers if mk in design)
        recipe = chapter_figure_recipe(fig_dir, idx)

        ok = True
        if n_design < MIN_DESIGN_CLAIMS:
            findings.append({"severity": "P0", "rule": "T-01",
                "text": f"chapter {idx} ({title}) opens with {n_design} design claims "
                        f"(need >= {MIN_DESIGN_CLAIMS}); it lists files without teaching why"})
            ok = False
        if recipe not in INTERACTION_RECIPES:
            findings.append({"severity": "P0", "rule": "T-02",
                "text": f"chapter {idx} ({title}) uses a '{recipe}' figure; a teaching "
                        "chapter needs a worked-example/interaction figure, not a size chart"})
            ok = False
        # move 6: a real "what you can now do" close
        if "what you can now do" not in chunk.lower():
            findings.append({"severity": "P1", "rule": "T-03",
                "text": f"chapter {idx} ({title}) has no 'what you can now do' close"})
        if ok:
            passing += 1

    return {"findings": findings, "chapters": n_chapters, "passing": passing}


def main() -> int:
    cookbook, workspace = Path(sys.argv[1]), Path(sys.argv[2])
    report = check(cookbook, workspace)
    (workspace / "out" / "teaching_report.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8")
    p0 = sum(1 for f in report["findings"] if f["severity"] == "P0")
    print(f"[Stage 5/7] teaching: {report['passing']}/{report['chapters']} chapters teach "
          f"({p0} P0)")
    for f in report["findings"]:
        print(f"  {f['severity']} [{f['rule']}] {f['text']}")
    # report-only: grade ingests teaching_report.json and is the single gate,
    # so the pipeline reaches grade even when a chapter fails to teach
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""M7 gate: the teaching gate catches a paper that verifies but does not
teach.

Calibration, both directions:
- the real dogfood self-paper (Grokking-style chapters) PASSES: every chapter
  teaches, 0 P0.
- a synthetic old-style chapter ("the X area holds N files" + a filename list
  + a size chart) FAILS on both T-01 (too few design claims) and T-02
  (cluster-size figure).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "figlib"))
from teaching_check import check  # noqa: E402

WS = ROOT / "workspace" / "_m7test"
SELFDOG = ROOT / "workspace" / "_selfdog"


def ensure_selfdog() -> None:
    if (SELFDOG / "out" / "paper.draft.md").exists():
        return
    src = SELFDOG / "sources" / "cookbook-anything"
    if not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT, src, ignore=shutil.ignore_patterns(
            ".git", "target", "workspace", "node_modules", "__pycache__",
            ".cookbook", "*.msi"))
    r = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings",
         str(ROOT / "runner" / "stages.ts"),
         str(SELFDOG / "sources"), str(SELFDOG), "cookbook-anything"],
        capture_output=True, text=True, timeout=1800)
    if not (SELFDOG / "out" / "paper.draft.md").exists():
        raise RuntimeError(f"could not build self-paper: {r.stdout[-800:]}\n{r.stderr[-400:]}")


def build_synthetic() -> None:
    """A good chapter and an old-style filename-list chapter, side by side."""
    if WS.exists():
        shutil.rmtree(WS)
    cb = WS / ".cookbook"
    out = WS / "out" / "figures"
    out.mkdir(parents=True)
    model = {
        "sources": [], "nodes": [], "edges": [], "tours": [], "glossary": [], "assets": [],
        "spans": [
            {"id": "span:d1", "source": "s", "locator": "DESIGN.md#L1", "text_sha": "x"},
            {"id": "span:d2", "source": "s", "locator": "DESIGN.md#L2", "text_sha": "x"},
            {"id": "span:q1", "source": "s", "locator": "quality_reports/checkpoints/x.md#L1", "text_sha": "x"},
        ],
        "claims": [
            {"id": "c:0001", "text": "Two firewalls keep facts honest.", "spans": ["span:d1"],
             "confidence": 0.9, "status": "active", "supersedes": None},
            {"id": "c:0002", "text": "Every edge carries an extractor.", "spans": ["span:d2"],
             "confidence": 0.9, "status": "active", "supersedes": None},
            {"id": "c:0003", "text": "The run shipped at grade 99.", "spans": ["span:q1"],
             "confidence": 0.9, "status": "active", "supersedes": None},
        ],
    }
    (cb).mkdir(parents=True, exist_ok=True)
    (cb / "model.json").write_text(json.dumps(model), encoding="utf-8")

    # one teaching chapter and two old-style filename-list chapters, so the
    # paper is mostly a listing (1/3 teach) and earns the fatal T-00 verdict
    draft = (
        "# x\n\n"
        "## Chapter 1: good\n\n"
        "See why this area exists:\n\n"
        "Two firewalls keep facts honest. {{c:0001}} Every edge carries an extractor. {{c:0002}}\n\n"
        "![fig](figures/fig_ch1.png)\n\n"
        "*Figure: the path.*\n\n"
        "What you can now do: trace it.\n\n"
        "## Chapter 2: bad\n\n"
        "The bad area holds 9 files of this codebase. {{c:w0001}} The run shipped at grade 99. {{c:0003}}\n\n"
        "- `a.py` (no docstring)\n- `b.py` (no docstring)\n- `c.py` (no docstring)\n\n"
        "![fig](figures/fig_ch2.png)\n\n"
        "*Figure: a few files carry most of the code.*\n\n"
        "## Chapter 3: alsobad\n\n"
        "The alsobad area holds 4 files of this codebase. {{c:w0002}}\n\n"
        "- `d.py` (no docstring)\n- `e.py` (no docstring)\n\n"
        "![fig](figures/fig_ch3.png)\n\n"
        "*Figure: a few files carry most of the code.*\n\n"
    )
    (WS / "out" / "paper.draft.md").write_text(draft, encoding="utf-8")
    for idx, recipe in [(1, "dataflow"), (2, "quantity"), (3, "quantity")]:
        (out / f"fig_ch{idx}.sidecar.json").write_text(
            json.dumps({"payload": {"id": f"fig_ch{idx}", "recipe": recipe}}), encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    # ---- direction 1: a mostly-filename-list paper must FAIL (P0 T-00),
    # and the bad chapter must be flagged for both shortfalls
    build_synthetic()
    rep = check(WS / ".cookbook", WS)
    bad_t01 = any(f["rule"] == "T-01" and "chapter 2" in f["text"] for f in rep["findings"])
    bad_t02 = any(f["rule"] == "T-02" and "chapter 2" in f["text"] for f in rep["findings"])
    paper_p0 = any(f["rule"] == "T-00" and f["severity"] == "P0" for f in rep["findings"])
    good_clean = not any("chapter 1" in f["text"] for f in rep["findings"])
    caught = 1 if (bad_t01 and bad_t02 and paper_p0 and good_clean) else 0
    print(f"METRIC m7_catches_filename_list {caught} up")
    if not bad_t01:
        failures.append("filename-list chapter not flagged for too few design claims (T-01)")
    if not bad_t02:
        failures.append("size-chart chapter not flagged (T-02)")
    if not paper_p0:
        failures.append("mostly-filename-list paper did not earn the fatal T-00 verdict")
    if not good_clean:
        failures.append("the teaching chapter was wrongly flagged")

    # ---- direction 2: the real self-paper must PASS
    ensure_selfdog()
    rep2 = check(SELFDOG / ".cookbook", SELFDOG)
    p0 = sum(1 for f in rep2["findings"] if f["severity"] == "P0")
    print(f"METRIC m7_selfpaper_chapters_teaching {rep2['passing']} up")
    print(f"METRIC m7_selfpaper_p0 {p0} down")
    if p0 != 0 or rep2["passing"] != rep2["chapters"]:
        failures.append(f"self-paper failed teaching: {rep2['passing']}/{rep2['chapters']}, "
                        f"{[f['text'] for f in rep2['findings'] if f['severity']=='P0']}")
    if rep2["chapters"] < 3:
        failures.append(f"self-paper has only {rep2['chapters']} chapters")

    if failures:
        print("M7 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print("M7 GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

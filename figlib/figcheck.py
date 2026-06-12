"""figcheck.py - the form firewall's mechanical battery (DESIGN 5.5).

Checks rendered figures against the rule catalog F-01..F-14, judging the
sidecar facts (introspected from the real artist tree) plus model.json.
Findings cite rule IDs; "looks off" is not a finding. Writes
figcheck_report.json that ca-grade ingests.

Usage: python figlib/figcheck.py <figures_dir> <model.json> [<paper.md>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from constants import ALLOWED_COLORS, CEILINGS, FONT_MIN_PT

BANNED_CMAP_MARKERS = {"#0000ff", "#00ffff", "#ffff00", "#ff0000", "#008000"}  # jet-ish anchors


def _overlap(a: list, b: list) -> float:
    """Intersection area of two [x0,y0,x1,y1] pixel boxes."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def check_sidecar(sc: dict, model: dict, paper_text: str | None) -> list[dict]:
    f: list[dict] = []
    pay = sc["payload"]
    facts = sc["facts"]
    fid = pay["id"]

    def add(sev, rule, text):
        f.append({"severity": sev, "rule": rule, "text": f"{fid}: {text}"})

    # ---- F-01 provenance: every node/edge/number resolves to the model
    node_ids = {n["id"] for n in model.get("nodes", [])}
    span_ids = {s["id"] for s in model.get("spans", [])}
    edge_set = {}
    for e in model.get("edges", []):
        edge_set[(e["source"], e["target"], e["type"])] = e.get("confidence", 1.0)
    for n in pay.get("nodes", []):
        if n["id"] not in node_ids:
            add("P0", "F-01", f"node {n['id']} does not exist in the model")
    for e in pay.get("edges", []):
        key = (e["source"], e["target"], e.get("type", "depends_on"))
        conf = edge_set.get(key)
        if conf is None:
            add("P0", "F-01", f"edge {key} does not exist in the model (hallucinated arrow)")
        elif conf < 1.0 and not e.get("unverified"):
            add("P0", "F-01", f"edge {key} has confidence {conf} but is not rendered dashed")
    for q in pay.get("quantities", []):
        if q.get("span") not in span_ids:
            add("P0", "F-01", f"quantity '{q.get('label')}' has no resolvable span")
    if pay.get("code_span") and pay["code_span"] not in span_ids:
        add("P0", "F-01", f"code span {pay['code_span']} not in model")

    # ---- F-02 legibility
    small = [s for s in facts.get("font_sizes_pt", []) if s < FONT_MIN_PT - 0.01]
    if small:
        add("P0", "F-02", f"text below {FONT_MIN_PT}pt rendered: {sorted(set(small))}")

    # ---- F-03 collisions among text labels
    labels = facts.get("labels", [])
    n_coll = 0
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            inter = _overlap(labels[i]["bbox"], labels[j]["bbox"])
            if inter > 4.0:  # px^2: tiny rounding contacts are not collisions
                n_coll += 1
                if n_coll <= 3:
                    add("P0", "F-03",
                        f"label collision: '{labels[i]['text']}' overlaps '{labels[j]['text']}'")
    if n_coll > 3:
        add("P0", "F-03", f"...and {n_coll - 3} more label collisions")

    # ---- F-04 palette
    bad = [c for c in facts.get("colors", []) if c not in ALLOWED_COLORS]
    if bad:
        jet = [c for c in bad if c in BANNED_CMAP_MARKERS]
        add("P1", "F-04",
            f"colors outside the house palette: {bad[:6]}"
            + (" (rainbow/jet markers present)" if jet else ""))

    # ---- F-05 caption: a full sentence stating the takeaway
    cap = (pay.get("caption") or "").strip()
    if not cap or len(cap.split()) < 5 or not cap.endswith(".") or not cap[0].isupper():
        add("P1", "F-05", f"caption is not a takeaway sentence: '{cap[:60]}'")

    # ---- F-06 orphan: referenced from prose
    if paper_text is not None:
        if pay["id"] not in paper_text:
            add("P1", "F-06", "figure is not referenced from prose")
    elif not pay.get("referenced_in"):
        add("P1", "F-06", "no prose reference recorded (referenced_in empty, no paper given)")

    # ---- F-07 legend discipline
    for leg in facts.get("legends", []):
        if leg.get("frame_on") and leg.get("over_data"):
            add("P1", "F-07", "boxed legend sits over data; use direct labels")
        elif leg.get("over_data"):
            add("P1", "F-07", "legend overlaps the axes data area")

    # ---- F-08 one idea: caption stating two takeaways (two sentences)
    if cap.count(".") > 1 and len(cap.split(".")[1].strip()) > 12:
        add("P1", "F-08", "caption states more than one idea; split the figure")

    # ---- F-09 density ceilings
    recipe = pay.get("recipe", "")
    ceiling = CEILINGS.get(recipe)
    n_items = max(len(pay.get("nodes", [])), len(pay.get("quantities", [])))
    if ceiling and n_items > ceiling:
        add("P1", "F-09", f"{n_items} items exceeds the {recipe} ceiling of {ceiling}")

    # ---- F-10 chartjunk: titles restating the caption (or any title at all)
    for t in facts.get("titles", []):
        cap_words = set(cap.lower().split())
        t_words = set(t.lower().split())
        if t_words and len(t_words & cap_words) / len(t_words) > 0.6:
            add("P2", "F-10", f"title restates the caption: '{t[:50]}'")
        else:
            add("P2", "F-10", f"figure has a title ('{t[:40]}'); the caption is the title")

    # ---- F-11 read match
    read = (pay.get("read") or "").lower()
    if not read:
        add("P2", "F-11", "no Figure Read declared")
    elif recipe and recipe.replace("_", " ") not in read and recipe not in read:
        add("P2", "F-11", f"declared read does not mention recipe '{recipe}'")

    # ---- F-13/F-14 external media: payloads here are model-only; any asset
    # reference must resolve to an asset record with a license
    for a in pay.get("assets", []) if isinstance(pay.get("assets"), list) else []:
        recs = {x["id"]: x for x in model.get("assets", [])}
        rec = recs.get(a)
        if rec is None or not rec.get("license", {}).get("verified_by"):
            add("P0", "F-13", f"external asset {a} lacks a verified license record")

    return f


def check_dir(fig_dir: Path, model_path: Path, paper_path: Path | None) -> dict:
    model = json.loads(model_path.read_text(encoding="utf-8")) if model_path.exists() else {}
    paper_text = paper_path.read_text(encoding="utf-8") if paper_path and paper_path.exists() else None
    findings: list[dict] = []
    sidecars = sorted(fig_dir.glob("*.sidecar.json"))
    for sc_path in sidecars:
        sc = json.loads(sc_path.read_text(encoding="utf-8"))
        findings.extend(check_sidecar(sc, model, paper_text))
    report = {"checked": len(sidecars), "findings": findings}
    return report


def main() -> int:
    fig_dir = Path(sys.argv[1])
    model_path = Path(sys.argv[2])
    paper_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    report = check_dir(fig_dir, model_path, paper_path)
    out = fig_dir / "figcheck_report.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    p0 = sum(1 for x in report["findings"] if x["severity"] == "P0")
    p1 = sum(1 for x in report["findings"] if x["severity"] == "P1")
    print(f"figcheck: {report['checked']} figures, {p0} P0, {p1} P1, "
          f"{len(report['findings']) - p0 - p1} P2")
    for x in report["findings"]:
        print(f"  {x['severity']} [{x['rule']}] {x['text']}")
    return 1 if p0 or p1 else 0


if __name__ == "__main__":
    sys.exit(main())

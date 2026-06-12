"""M6 gate: the acquisition/verification swarm obeys the truth firewall.

3 workers cover a 6-chapter PDF book in parallel (overlapping assignments),
produce >= 8 claims, every one span-backed; 2 planted unsourced findings are
rejected and 0 unsourced facts enter the model; independent support raises a
claim's confidence; a span-backed contradiction is recorded alongside the
original claim, never resolved by overwrite or vote.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import ca  # noqa: E402

WS = ROOT / "workspace" / "_m6test"
CB = WS / ".cookbook"
NODE = ["node", "--experimental-strip-types", "--no-warnings"]
SWARM = str(ROOT / "runner" / "swarm" / "book_swarm.ts")

DUP = "The boiler holds steady at eighty degrees during normal operation."
CONTRA = "The boiler does not hold a steady temperature during startup."
CHAPTERS = [
    f"Chapter one. {DUP} The relief valve opens automatically above the safety envelope.",
    "Chapter two. The feed pump runs only while the level sensor reads low. "
    "Operators check the gauge twice per shift according to the manual.",
    f"Chapter three. {CONTRA} Warmup takes roughly twenty minutes from cold.",
    "Chapter four. The condenser returns water to the tank through a brass line. "
    "A clogged return line is the most common maintenance fault.",
    "Chapter five. Monthly inspection covers the valve seats and the sight glass. "
    "Worn valve seats must be replaced rather than reground.",
    f"Chapter six. {DUP} The logbook records every deviation from steady state.",
]


def make_book(path: Path, chapters: list[str]) -> None:
    """A multi-page PDF, one FlateDecode content stream per chapter."""
    n = len(chapters)
    objs = [b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs.append(f"2 0 obj << /Type /Pages /Kids [{kids}] /Count {n} >> endobj".encode())
    font_num = 3 + 2 * n
    for i, text in enumerate(chapters):
        page, content = 3 + 2 * i, 4 + 2 * i
        objs.append(
            f"{page} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content} 0 R /Resources << /Font << /F1 {font_num} 0 R >> >> >> endobj".encode())
        safe = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        comp = zlib.compress(f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("latin-1"))
        objs.append(f"{content} 0 obj << /Length {len(comp)} /Filter /FlateDecode >> stream\n".encode()
                    + comp + b"\nendstream endobj")
    objs.append(f"{font_num} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj".encode())
    path.write_bytes(b"%PDF-1.4\n" + b"\n".join(objs) + b"\ntrailer << /Root 1 0 R >>\n%%EOF")


def model() -> dict:
    return json.loads((CB / "model.json").read_text(encoding="utf-8"))


def admit(findings: list[dict]) -> dict:
    f = WS / "findings_in.json"
    f.write_text(json.dumps({"findings": findings}), encoding="utf-8")
    proc = ca.run("admit", str(CB), str(f))
    return json.loads(proc.stdout.strip().splitlines()[-1])


def swarm(*args: str) -> dict:
    r = subprocess.run([*NODE, SWARM, *args], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"swarm failed: {r.stdout}\n{r.stderr}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> int:
    failures: list[str] = []
    if WS.exists():
        shutil.rmtree(WS)
    src = WS / "sources"
    src.mkdir(parents=True)
    make_book(src / "book.pdf", CHAPTERS)

    ca.intake(src, CB)
    ca.run("compile", str(CB))
    spans = {s["id"]: s for s in model()["spans"]}
    by_loc = {s["locator"]: s["id"] for s in spans.values()}
    if len([loc for loc in by_loc if "#p" in loc]) != 6:
        failures.append(f"expected 6 chapter spans, got {sorted(by_loc)}")

    # ---- verification path: admit the duplicated sentence from chapter one
    # only, then let the verify swarm find chapter six independently
    summary = admit([{"kind": "claim", "text": DUP,
                      "span_id": by_loc["book.pdf#p1"], "worker": "seed"}])
    claim_id = next(c["id"] for c in model()["claims"] if c["text"] == DUP)
    conf_before = next(c["confidence"] for c in model()["claims"] if c["id"] == claim_id)
    v = swarm("verify", str(CB), claim_id, "--workers", "3")
    if v["supports"] < 1:
        failures.append(f"verify swarm found no independent support: {v}")
    sf = json.loads((CB / "swarm_findings.json").read_text(encoding="utf-8"))
    admit(sf["findings"])
    after = next(c for c in model()["claims"] if c["id"] == claim_id)
    raised = 1 if (after["confidence"] > conf_before and len(after["spans"]) >= 2) else 0
    print(f"METRIC m6_support_confidence_raised {raised} up")
    if not raised:
        failures.append(f"support did not raise confidence: {conf_before} -> {after}")

    # ---- contradiction: span-backed counter-statement is recorded, the
    # original stays active (disagreement is recorded, not resolved)
    summary = admit([{"kind": "contradict", "claim_id": claim_id, "text": CONTRA,
                      "span_id": by_loc["book.pdf#p3"], "worker": "verifier-x"}])
    m = model()
    original = next(c for c in m["claims"] if c["id"] == claim_id)
    counter = next((c for c in m["claims"] if c["text"] == CONTRA), None)
    runs = [json.loads(line) for line in (CB / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    recorded = any(e.get("event") == "contradicted" and e.get("claim") == claim_id
                   for r in runs if r.get("stage") == "admit" for e in r.get("events", []))
    ok_contra = 1 if (summary["contradictions"] == 1 and counter is not None
                      and original["status"] == "active" and recorded) else 0
    print(f"METRIC m6_contradiction_recorded {ok_contra} up")
    if not ok_contra:
        failures.append(f"contradiction handling wrong: {summary}, recorded={recorded}")

    # ---- acquisition swarm: 3 workers, 6 chapters, parallel with overlap
    a = swarm("acquire", str(CB), "--workers", "3")
    print(f"METRIC m6_chapters_covered {a['chapters_covered']} up")
    if a["chapters_covered"] != 6:
        failures.append(f"workers covered {a['chapters_covered']}/6 chapters")
    if not any(s.startswith("reader-") for s in a["agents"]) or "archivist" not in a["agents"]:
        failures.append(f"handoff chain wrong: {a['agents']}")

    sf = json.loads((CB / "swarm_findings.json").read_text(encoding="utf-8"))
    findings = sf["findings"]
    if len(findings) < 12:
        failures.append(f"only {len(findings)} findings from 6 chapters")
    # plant 2 unsourced findings: a fake span, and a fabricated sentence
    findings.append({"kind": "claim", "text": "The reactor can run unattended for a year.",
                     "span_id": "span:99999", "worker": "reader-evil"})
    findings.append({"kind": "claim", "text": "This sentence was never in the book at all.",
                     "span_id": by_loc["book.pdf#p2"], "worker": "reader-sloppy"})
    summary = admit(findings)
    print(f"METRIC m6_claims_admitted {summary['admitted']} up")
    print(f"METRIC m6_rejected_unsourced {summary['rejected']} up")
    if summary["admitted"] < 8:
        failures.append(f"only {summary['admitted']} claims admitted")
    if summary["rejected"] != 2:
        failures.append(f"expected exactly 2 rejections, got {summary['rejected']}")

    # ---- the firewall number: 0 unsourced facts in the model
    m = model()
    span_text = {s["id"]: s["text"] for s in m["spans"]}
    unsourced = [c["id"] for c in m["claims"]
                 if not any(c["text"] in span_text.get(sp, "") for sp in c["spans"])]
    print(f"METRIC m6_unsourced_admitted {len(unsourced)} down")
    if unsourced:
        failures.append(f"unsourced claims entered the model: {unsourced}")
    if ca.run("validate", str(CB / "model.json"), check=False).returncode != 0:
        failures.append("model invalid after swarm admissions")
    # agreement on the duplicated sentence: multiple spans, confidence above base
    dup = next(c for c in m["claims"] if c["text"] == DUP)
    if len(dup["spans"]) < 2 or dup["confidence"] <= 0.6:
        failures.append(f"agreement did not raise the duplicated claim: {dup}")

    if failures:
        print("M6 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print("M6 GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

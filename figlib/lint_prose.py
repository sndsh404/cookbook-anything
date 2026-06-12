"""lint_prose.py - deterministic prose lints (DESIGN stage 4, pass 2).

Banned vocabulary, em dashes, figure-caption presence, sentence-length
outliers, topic-sentence presence. The banned list lives HERE so it is
enforced, not aspirational. Writes lint_report.json that ca-grade ingests.

Usage: python figlib/lint_prose.py <paper.md> [<report.json>]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BANNED = [
    "leverage", "robust", "seamless", "delve", "utilize", "streamline",
    "crucial", "comprehensive", "holistic", "in today's fast-paced world",
    "it's important to note", "dive deep",
]
# "navigate" is banned only metaphorically; left out of v0 (needs judgment)

LONG_SENTENCE_WORDS = 45


def lint(text: str) -> list[dict]:
    findings: list[dict] = []
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    # glossary and appendices quote source material verbatim (evidence, not
    # authored prose); lint only what the writer authored
    body = prose.split("## Glossary")[0]

    for w in BANNED:
        # multi-word phrases must match across line wraps
        pat = re.escape(w).replace(r"\ ", r"\s+")
        for m in re.finditer(rf"\b{pat}\b", body, re.I):
            line = body[:m.start()].count("\n") + 1
            findings.append({"severity": "P1", "rule": "prose-banned",
                             "text": f"banned word '{w}' at line {line}"})

    for m in re.finditer("—", body):
        line = body[:m.start()].count("\n") + 1
        findings.append({"severity": "P1", "rule": "prose-emdash",
                         "text": f"em dash at line {line}"})

    # a redaction marker in shipped prose means the writer quoted a span the
    # secret filter had to mutilate (M4 review, issue 1)
    for m in re.finditer(r"\[REDACTED:", body):
        line = body[:m.start()].count("\n") + 1
        findings.append({"severity": "P1", "rule": "prose-redaction-artifact",
                         "text": f"redaction artifact in prose at line {line}"})

    # every figure image needs a takeaway caption line right after it
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith("!["):
            nxt = next((x.strip() for x in lines[i + 1:i + 3] if x.strip()), "")
            if not nxt.startswith("*Figure:"):
                findings.append({"severity": "P1", "rule": "F-05",
                                 "text": f"figure at line {i + 1} has no caption line"})

    for raw in re.split(r"(?<=[.!?])\s+", body):
        n = len(raw.split())
        if n > LONG_SENTENCE_WORDS:
            findings.append({"severity": "P2", "rule": "prose-long",
                             "text": f"{n}-word sentence: '{raw[:60]}...'"})

    # topic sentences: a section's first paragraph should open with a
    # sentence, not a fragment (heuristic, honestly)
    for m in re.finditer(r"^## .+$\n+([^\n#!*-][^\n]*)", body, re.M):
        first = m.group(1).strip()
        if "." not in first and len(first.split()) > 3:
            findings.append({"severity": "P2", "rule": "prose-topic",
                             "text": f"section opens with a fragment: '{first[:50]}'"})
    return findings


def main() -> int:
    paper = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else paper.parent / "lint_report.json"
    findings = lint(paper.read_text(encoding="utf-8"))
    out.write_text(json.dumps({"findings": findings}, indent=1), encoding="utf-8")
    p1 = sum(1 for f in findings if f["severity"] == "P1")
    print(f"lint_prose: {len(findings)} findings ({p1} P1)")
    for f in findings:
        print(f"  {f['severity']} [{f['rule']}] {f['text']}")
    return 1 if p1 else 0


if __name__ == "__main__":
    sys.exit(main())

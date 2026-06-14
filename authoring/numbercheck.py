"""numbers.py - pull the load-bearing numbers out of a draft, nothing else.

Reads your draft and produces a short checklist of only the sentences that
carry a number, a unit, a date, or a named hardware/model spec - the claims
worth fact-checking. Everything else (your prose, your analogies) is left
untouched and never appears in the report.

    python numbers.py draft.md --out number-check.md

Then, in a Claude Code session, each item gets checked against a real source
with web search and marked confirmed / wrong (with the right value) /
unverifiable. The report is a side file you read while editing. It is NOT
attached to the published post - the post still ends with your reading list.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# a number with an optional unit, a year/date, a percentage, or a named spec.
UNIT = (r"(?:TB/s|GB/s|MB/s|GB|TB|MB|KB|kB|ns|us|µs|ms|GHz|MHz|MHz|W|nm|"
        r"tokens|params|parameters|FLOPs?|FLOP/s|epochs?|layers?|bits?|bytes?|x|%)")
NAMED_SPEC = r"\b(?:HBM\d\w*|DDR\d\w*|GDDR\d\w*|LPDDR\d\w*|PCIe\s?\d(?:\.\d)?|"\
             r"CXL\s?\d(?:\.\d)?|SXM\d?|NVLink\s?\d?|H100|A100|B200|MI\d{3}\w*)\b"
GREEK = r"(?:alpha|beta|gamma|lambda|sigma|α|β|γ|λ)"

PATTERNS = [
    re.compile(rf"~?\b\d[\d,\.]*\s*{UNIT}\b", re.I),                 # 1.2 TB/s, 70B params
    re.compile(rf"\b\d[\d,\.]*\s*[-x]\s*\d[\d,\.]*\s*{UNIT}\b", re.I),
    re.compile(r"\b\d[\d,\.]*\s*(?:billion|million|trillion|B|M|T)\b"),  # 1.4T tokens, 70B
    re.compile(NAMED_SPEC),                                          # HBM3E, DDR5
    re.compile(rf"{GREEK}\s*[~=]\s*[-\d\.]+", re.I),                 # alpha ~ 0.45
    re.compile(r"\b(?:19|20)\d{2}\b"),                              # years
    re.compile(r"\b\d[\d,\.]*\s*%"),                                # percentages
    re.compile(r"\$\s?\d[\d,\.]*\s*(?:k|K|M|B|million|billion)?"),  # prices
]

# sentences we do NOT flag even if a stray digit appears (headings, list bullets
# of pure prose, code fences)
SKIP_PREFIX = ("#", "```", "    ", "\t")


def split_sentences(text: str) -> list[str]:
    # strip code fences first; we do not fact-check code
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]+`", " ", text)
    out = []
    for para in text.split("\n"):
        p = para.strip()
        if not p or p.startswith(SKIP_PREFIX):
            continue
        for s in re.split(r"(?<=[.!?])\s+", p):
            s = s.strip().lstrip("-*0123456789. ")
            if s:
                out.append(s)
    return out


def load_bearing(sentence: str) -> list[str]:
    hits = []
    for pat in PATTERNS:
        for m in pat.finditer(sentence):
            tok = m.group(0).strip()
            # a bare 4-digit year alone is weak; keep it only if it looks like a date context
            hits.append(tok)
    # de-dup, keep order
    seen, uniq = set(), []
    for h in hits:
        if h.lower() not in seen:
            seen.add(h.lower())
            uniq.append(h)
    return uniq


def extract(text: str) -> list[dict]:
    items = []
    for s in split_sentences(text):
        figs = load_bearing(s)
        # require a real spec/number, not just a lone year or a list index
        strong = [f for f in figs if not re.fullmatch(r"(19|20)\d{2}", f)]
        if strong or (figs and len(figs) >= 2):
            items.append({"claim": s, "figures": figs})
    return items


def report(items: list[dict]) -> str:
    out = ["# number check\n",
           "Only the load-bearing numbers, for fact-checking. Not attached to the post.\n",
           f"_{len(items)} claim(s) to verify._\n"]
    for i, it in enumerate(items, 1):
        out.append(f"## {i}. {it['claim']}")
        out.append(f"- figures: {', '.join('`'+f+'`' for f in it['figures'])}")
        out.append("- [ ] status: __confirmed / wrong (correct: ___) / unverifiable__")
        out.append("- source: ___\n")
    return "\n".join(out)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    draft = Path(sys.argv[1])

    def arg(name, d):
        return sys.argv[sys.argv.index(f"--{name}") + 1] if f"--{name}" in sys.argv else d

    out = Path(arg("out", draft.with_name("number-check.md")))
    items = extract(draft.read_text(encoding="utf-8"))
    out.write_text(report(items), encoding="utf-8")
    print(f"pulled {len(items)} load-bearing claim(s) -> {out}")
    for it in items[:12]:
        print(f"  - {it['claim'][:70]}  [{', '.join(it['figures'][:3])}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

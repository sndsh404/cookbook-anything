# cookbook-anything

Point it at anything: a codebase, a database dump, a folder of PDFs, a book.
It compiles a paper that teaches it: well written, figure-rich, cookbook
structured, and verifiable down to the sentence.

## What it is

cookbook-anything is a compiler with two firewalls, not a paper generator.

- **The truth firewall.** The front end deterministically extracts a knowledge
  model from your sources. Every fact carries a citation to a source span.
  Every graph edge comes from an extractor script. Nothing enters the model on
  an LLM's word alone. A hallucinated architecture arrow is structurally
  impossible: figures can only render data that resolves to model node IDs.
- **The form firewall.** The back end renders that model into prose and
  figures under enforced taste rules: a declared Figure Read before any figure,
  a locked house style, a recipe library instead of freeform matplotlib, and a
  critic that must cite the specific rule it flags.

The paper is a view over the compiled model. The model persists, so the second
run on the same sources is an incremental update, not a re-derivation.

## The pipeline

```
web => ACQUIRE => sources => INTAKE => COMPILE => MODEL => PLAN => WRITE => FIGURE => SHIP
```

Six stages. Each has a deterministic floor (scripts), a judgment layer
(agents), and a checkable exit condition. An agent may never overwrite what
its scripts established.

| Stage | Floor | What it guarantees |
|---|---|---|
| ACQUIRE | `scripts/acquire.py` | robots.txt respected, every fetch archived and audited, images enter only with a verified license record |
| INTAKE | `scripts/intake.py` | every source has a parser, a hash, and a trace; secrets stripped before anything reaches spans |
| COMPILE | `scripts/extract_*.py`, `scripts/merge.py` | 100% of edges carry an extractor name, 100% of claims carry source spans |
| PLAN | `scripts/topology.py` | chapters ordered by dependency; no term before its prerequisites |
| WRITE | `scripts/lint_prose.py` | claim coverage >= 95%, banned vocabulary and em dashes at zero |
| FIGURE | `scripts/figcheck.py` + `figlib/` | provenance-checked payloads, house style, named failure modes F-01..F-14 |
| SHIP | `scripts/grade.py` | scored 0-100 with severity deductions; below 80 does not ship |

## What you get

`workspace/out/paper.md`: a TL;DR with a page-one figure, a CARS introduction,
guided-tour chapters in dependency order (each with at least one figure), a
cookbook of reproducible steps, a glossary, and three appendices that make the
whole thing verifiable: every claim with its source locators, every unverified
edge listed plainly, every external asset with its license and attribution.

## Quality is a script, not an opinion

- `scripts/grade.py` starts at 100 and deducts by severity. A provenance
  failure in a shipped figure is -100. The gate cannot be overridden by prose.
- Critics are calibrated on seeded defects (`figlib/seeded_defects/`): a critic
  is trusted only after it catches >= 9/10 violations planted on purpose.
- `scripts/assess.py` is the repo's own objective harness: build, tests,
  hard-rule compliance, regression check against the last run.

## Status

Early build. See `DESIGN.md` for the full spec and milestone gates (M0..M5),
`CLAUDE.md` for the operating guide, and `quality_reports/` for the audit
trail of every session.

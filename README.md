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

## How it works (demonstrated on itself)

Everything in this section was produced by running cookbook-anything on its own
repository. None of it is hand-written prose or hand-drawn figures. To
reproduce it, point the stage runner at a checkout of this repo:

```
node --experimental-strip-types runner/stages.ts <dir-containing-a-checkout> <workspace> cookbook-anything
```

The run compiled 68 source files into a model and shipped a paper at **grade
91/100**, passing the same gates every other run must pass: 100% of edges carry
an extractor, 100% of claims resolve to a source span, every figure passes
figcheck with its provenance resolving to the model, and every chapter teaches
(opens with why, walks a real path, closes with what you can now do) rather
than listing files.

The generated TL;DR, verbatim:

> This is a tour of cookbook-anything, compiled from its own source into a
> model of 68 files and 204 functions, every sentence below traceable to a
> span. Each chapter takes one area, shows the problem it solves, and walks a
> real path through the code, so by the end you can change it yourself.

The generated page-one figure (recipe `architecture_box`), showing the real
layer split the extractors found, the Rust core beside the Python figlib and
the TypeScript runner:

![generated architecture figure](docs/figures/fig_page_one.png)

A generated walkthrough excerpt, the `core` chapter, verbatim. It opens with
the project's own design rationale, then walks one real call path through the
Rust crates (every file reference resolves to a span in the claims appendix):

> See why this area exists, in the project's own words:
>
> Exit condition: model.json validates; 100% of edges have extractors; 100% of
> claims have spans; zero unresolved dangling references. [...] Secret hygiene:
> `intake.py` strips API keys, tokens, passwords, and high-entropy strings
> *before* anything reaches spans [...].
>
> At the center of `core` is `ca-model/lib.rs`: defines `Asset`, `Claim`,
> `ClaimStatus`.
>
> Follow one real path through core: start at `main.rs`, which reaches into
> `ca-extract/lib.rs`, which reaches into `ca-model/lib.rs`.

That path is the generated teaching figure for the chapter (recipe
`dataflow`), built from real call edges, not a size chart:

![generated core dataflow figure](docs/figures/fig_ch2.png)

The full generated paper is committed at
[`docs/self-paper.md`](docs/self-paper.md). Its claims appendix is the proof:
every sentence carries a claim id that resolves to a file and line range, so a
reader can check any sentence against its span (for example
`c:0001` resolves to `CLAUDE.md#L5-L9`).

### What this demonstration does and does not show (honestly)

- Extraction covers Python, Rust, and TypeScript: file structure, definitions,
  imports, and (for Python) cross-module calls. Config files (toml, json,
  lockfiles) are ingested as spans but not parsed into the graph.
- The figures are real recipes rendered off the compiled model and
  provenance-checked, not hand-drawn. The page-one figure is a summary showing
  three of the repo's code clusters; each chapter then gets its own teaching
  figure (a dataflow of one real path through that area).
- The teaching itself is assembled from verified facts: a chapter's "why"
  comes from real design claims in the docs, its worked path from real call or
  import edges, its file descriptions from real docstrings or definitions. The
  writer sequences true facts; it does not invent prose. A `grade` gate fails
  any paper that is mostly a file listing instead of teaching.
- The intake to ship pipeline is orchestrated by `runner/stages.ts` and
  described in `DESIGN.md`; it is not itself extracted as a dataflow graph, so
  the chapter figures show the repo's real code paths rather than a diagram of
  the stages.
- The LLM judgment layers (the figure vision-critic and the prose
  humanize-auditor) are not built yet. The gates exercised here are the
  deterministic ones: figcheck, the prose lints, claim verification, the
  teaching gate, and the scored grade.

## Status

Early build. See `DESIGN.md` for the full spec and milestone gates (M0..M6),
`CLAUDE.md` for the operating guide, and `quality_reports/` for the audit
trail of every session.

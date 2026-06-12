# CLAUDE.md: operating guide

## Prime directive

Deterministic code establishes ground truth; the LLM does judgment on top.
When output is wrong, the question is "which extractor, script, or rule
failed," never "the model hallucinated and we shrug." If an agent wants to
assert a fact or draw an edge no script extracted, the fix is a better
extractor or an honest "unverified" marker, never a more confident prompt.

## Hard rules (no exceptions)

1. No edge without an extractor. Agent-proposed edges enter at
   confidence < 1.0, render dashed, and are listed in the unverified appendix.
2. No claim without a span. Unsupported sentences are labeled opinion or cut.
3. Supersession over silent edits; every mutation logged to runs.jsonl.
4. Secrets stripped at intake, before anything reaches spans.
5. External media only with a verified license record; attribution
   non-removable; robots.txt respected unconditionally.
6. The score comes from scripts/assess.py and scripts/grade.py, never from
   opinion. Below 80, or any P0, or a regression: does not ship, not pushed.

## Repo map (polyglot, split along the firewall)

- `core/` RUST cargo workspace - the truth firewall. Crates: ca-model (the
  knowledge model; invariants encoded in types: no Edge without ExtractorId,
  no Claim without spans, no Asset without License, no agent edge at 1.0),
  ca-extract (intake + secret filter + python/markdown/csv/sql extractors),
  ca-merge, ca-topology, ca-grade, ca-cli (the `ca` binary).
- `runner/` TYPESCRIPT (Node) - acquire/ (fetch ladder, robots, cache,
  license gate), stages.ts (invokes the Rust core and the Python renderer),
  mcp.ts. Playwright for rendering/screenshots.
- `figlib/` PYTHON, leaf renderer only - style.py, recipes/, figcheck.py,
  lint_prose.py, seeded_defects/. Receives typed FigurePayloads, emits
  PNG/SVG + provenance metadata; never touches firewall invariants.
- `scripts/assess.py` the objective harness (Python is fine here; it is the
  meta-gate, not the core).
- `workspace/` per-project (gitignored): sources/, .cookbook/ (model.json,
  trace/, runs.jsonl), out/ (paper.md, figures/).
- `tests/` gate tests per milestone (drive the `ca` binary via tests/ca.py).
- `quality_reports/` assessments, checkpoints, session logs.

## Commands

- Run everything: `python scripts/assess.py` (exit 0 = green; runs cargo
  build + cargo test + all gate tests + hard-rule scans)
- Core only: `cd core; cargo test --release`
- Core CLI: `core\target\release\ca.exe <intake|compile|topology|validate|grade>`
- npm on this machine: use `npm.cmd` (powershell execution policy blocks npm.ps1)

## Milestone checklist (tick only after assess.py verifies)

- [x] M0 intake + trace + secret filter: 3 source types parse with traces;
      12 planted secrets, 0 leaks; rerun on unchanged sources reparses 0
- [x] M1 compile: model validates on a real repo; 100% edges have extractors;
      100% claims have spans; 0 danglers; planted proposed edge < 1.0
- [x] M2 figures: critic catches >= 9/10 seeded defects with correct rule
      IDs; hallucinated edge rejected; 6 recipes render in both modes
- [x] M2.5 acquire: license gate verifies via Commons metadata; mismatched CC
      claim rejected; ARR converted to figure request; 0 robots violations,
      0 off-allowlist over 50-page seeded crawl; rerun fetches 0
- [x] M3 plan + write: chapter graph acyclic; claim coverage >= 95%; 0 banned
      words, 0 em dashes; planted unsupported sentence flagged
- [x] M4 real paper ships at grade >= 80 with all appendices; 3 issues filed
- [x] M5 incremental: one-file change re-ships at < 20% of full-run work;
      supersession linked; runs.jsonl reconstructs claim history
- [x] M6 swarm: 3 workers cover a 6-chapter book in parallel; >= 8 claims
      all span-backed; 2 planted unsourced findings rejected, 0 admitted;
      support raises confidence; contradiction recorded, never resolved

## Conventions

- Python 3.14, stdlib + matplotlib only (no heavy deps without a recorded
  decision). Windows paths; use pathlib everywhere.
- Branches m<N>/<slug>; merge to main only on green assess.
- Commits authored as Sandesh Bhandari, lowercase, plain, no trailers.

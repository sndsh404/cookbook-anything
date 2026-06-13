# Checkpoint: make the writer TEACH (the cookbook, not a table of contents)

Date: 2026-06-13 (session 4)

## The problem

The first dogfood paper passed the truth firewall but failed the actual goal:
each chapter was "the X area holds N files" + a filename list + "open any
file." A verified table of contents, not a cookbook. The fix was the WRITER,
not the firewall; provenance was never weakened.

## The number

The self-paper now ships at grade 91 with **4/4 chapters teaching** (0 teaching
P0). A new teaching gate fails any paper where fewer than half the chapters
teach; the old filename-list self-paper would score 0/N and fail, a
Grokking-style chapter passes (proven by test_m7_teaching.py, both
directions). assess green across M0-M7.

## What shipped

- `MEMORY.md` [LEARN:teaching]: the six-move chapter template distilled from
  Grokking Algorithms, Clean Architecture, and Linux Kernel Development
  (problem first, name the job, one worked example traced, a figure that shows
  interaction, key files in plain language, what you can now do).
- `ca write` rewritten (core/ca-cli/src/write.rs) to that template. A chapter
  now opens with the project's own design rationale (real doc claims matched
  to the chapter's vocabulary, operational metrics from quality_reports
  excluded), walks one real call path, shows a dataflow figure of that path,
  explains 3-5 key files from their real docstrings/definitions, and closes
  with a concrete capability.
- Extraction extended so the teaching figures have real interaction to show:
  Python cross-module calls (python.rs), and Rust crate / TS relative import
  resolution to files (nativecode.rs + main.rs relink). The Rust core chapter
  now walks `main.rs -> ca-extract/lib.rs -> ca-model/lib.rs`, a real path.
- `ca plan` (plan.rs) computes each chapter's worked path (longest real
  call/import chain, deterministic) and key files (by degree), and picks a
  dataflow figure when a path exists.
- `figlib/figures_from_plan.py` renders the worked path as a provenance-checked
  dataflow; file labels disambiguated (five lib.rs become ca-model/lib.rs etc).
- The cookbook section is real runnable recipes traced to files (run the
  pipeline, add a figure recipe, teach a new language), each with an expected
  result and the test that verifies it. No more [unverified] placeholders.
- `figlib/teaching_check.py` + ca-grade ingestion: the gate. Per-chapter
  shortfalls are P2 nudges; a paper that is mostly file listings (< half its
  chapters teach) earns a fatal P0 and does not ship.

## Bugs the iteration caught (the gates earning their keep)

- The writer quoted source doc-claims verbatim into chapter openings, and
  llmwiki's claims contain em dashes, tripping the voice profile. Fixed: em
  dashes stripped from the displayed body text; the claim stays verbatim in
  the model and the appendix (the receipt is unaltered).
- The worked path was nondeterministic (HashSet iteration) and labelled five
  lib.rs identically, reading "lib.rs -> lib.rs". Fixed: deterministic DFS,
  and nearest-non-generic-ancestor labels.
- The teaching check was a third Python spawn that did not shrink on
  incremental runs, pushing M5 over its 20% budget. Folded into the figures
  process.

## Decisions

- The teaching verdict is paper-level: one thin area in an otherwise good
  paper is a nudge, not a block, so real repos (llmwiki ships at 87) still
  pass while a mostly-listing paper fails. This matches the user's explicit
  calibration: the old self-paper fails, a Grokking-style one passes.
- Floor-gated score metrics (m4_grade) are exempt from assess's trend
  regression: adding a gate legitimately lowers every grade, and the real
  floor (>= 80) is enforced by the gate test itself.

## Result

test_m7_teaching.py exit 0. METRIC m7_catches_filename_list=1,
m7_selfpaper_chapters_teaching=4, m7_selfpaper_p0=0. assess 100/100 green.
The self-paper (docs/self-paper.md) and README "How it works" section
regenerated from the teaching pipeline.

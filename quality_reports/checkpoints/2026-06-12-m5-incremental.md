# Checkpoint: M5 the compounding loop

Date: 2026-06-12 (session 1, final milestone)

## The numbers

A one-file change (README edit) re-ships the paper at **16.3% of full-run
work** (800ms vs 4919ms, stage timings in .cookbook/timings.json; gate
< 20%). The contradicting edit produces a superseded claim correctly linked
(old status superseded, new claim carries supersedes=old). runs.jsonl
reconstructs the claim's full history across three runs:
c:0001 -> c:0016 -> c:0017.

## What shipped

- Per-file incremental intake: SourceRec carries rel->sha plus
  rel->"size:mtime"; an unchanged stat reuses the stored sha without
  reading the file; only changed files are re-read and re-redacted
  (1 file reparsed, 259 carried).
- Claim supersession in compile: doc claims matched by span locator;
  same text keeps its identity, changed text mints a new id linked via
  supersedes, the old claim stays in the model marked superseded. Events
  logged per run to runs.jsonl.
- Figure render cache: identical payload sha + existing png = zero work;
  matplotlib is imported lazily so a fully cached run never pays it.
- Compile hot spot fixed: call extraction uses one alternation regex per
  file instead of one regex per function pair.
- Prose lints ride in the figures process (one python startup, not two).
- stages.ts writes per-stage wall timings to the trace.

## Bug the gate caught

The writer quoted a superseded claim whose span text had changed under it;
the verifier flagged it as a broken marker. Writers may quote active claims
only. Exactly the leash working.

## Decisions

- File-change detection trusts size+mtime to skip hashing (the git/make
  move); content hash remains the recorded truth.
- 19.8% first pass was too close to the gate; the lint-stage merge bought
  honest margin rather than loosening the threshold.

## Result

test_m5_incremental.py exit 0. METRIC m5_rerun_work_pct=16.3,
m5_supersession_linked=1, m5_history_chain_len=3.

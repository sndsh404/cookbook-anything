# cookbook-anything: a guided cookbook

## TL;DR

This codebase compiles to a model of 68 files and 204 functions, every one traced to source. The tour below walks 6 areas in dependency order, so nothing is used before it is taught.

![the system in one figure](figures/fig_page_one.png)

*Figure: The clusters of this codebase and which ones depend on which.*

## Introduction

Deterministic code establishes ground truth; the LLM does judgment on top. The name says the contract: hand it anything, get a cookbook back. It is a **compiler with two firewalls**. 

Read the chapters in order; each one assumes only what came before it. Use the cookbook section at the end to turn the tour into runnable steps.

Chapter map:

- Chapter 1: (root)
- Chapter 2: core
- Chapter 3: quality_reports
- Chapter 4: runner
- Chapter 5: figlib
- Chapter 6: tests

## Chapter 1: (root)

The (root) area holds 5 files of this codebase.

- `CLAUDE.md` (no docstring; see the source span in the claims appendix)
- `DESIGN.md` (no docstring; see the source span in the claims appendix)
- `MEMORY.md` (no docstring; see the source span in the claims appendix)
- `README.md` (no docstring; see the source span in the claims appendix)
- `WORKFLOW.md` (no docstring; see the source span in the claims appendix)

![chapter figure](figures/fig_ch1.png)

*Figure: A few files carry most of the code in (root).*

What you can now do: open any file in `(root)` and place it on this chapter's figure.

## Chapter 2: core

The core area holds 16 files of this codebase.

- `core/ca-cli/src/admit.rs` (no docstring; see the source span in the claims appendix)
- `core/ca-cli/src/main.rs` (no docstring; see the source span in the claims appendix)
- `core/ca-cli/src/plan.rs` (no docstring; see the source span in the claims appendix)
- `core/ca-cli/src/verify.rs` (no docstring; see the source span in the claims appendix)
- `core/ca-cli/src/write.rs` (no docstring; see the source span in the claims appendix)

![chapter figure](figures/fig_ch2.png)

*Figure: A few files carry most of the code in core.*

What you can now do: open any file in `core` and place it on this chapter's figure.

## Chapter 3: quality_reports

The quality_reports area holds 11 files of this codebase.

- `quality_reports/assessment_latest.md` (no docstring; see the source span in the claims appendix)
- `quality_reports/checkpoints/2026-06-11-m0-intake.md` (no docstring; see the source span in the claims appendix)
- `quality_reports/checkpoints/2026-06-11-m1-compile.md` (no docstring; see the source span in the claims appendix)
- `quality_reports/checkpoints/2026-06-12-m2-figures.md` (no docstring; see the source span in the claims appendix)
- `quality_reports/checkpoints/2026-06-12-m25-acquire.md` (no docstring; see the source span in the claims appendix)

![chapter figure](figures/fig_ch3.png)

*Figure: A few files carry most of the code in quality_reports.*

What you can now do: open any file in `quality_reports` and place it on this chapter's figure.

## Chapter 4: runner

The runner area holds 8 files of this codebase.

- `runner/acquire/acquire.ts` (no docstring; see the source span in the claims appendix)
- `runner/acquire/html2md.ts` (no docstring; see the source span in the claims appendix)
- `runner/acquire/infra.ts` (no docstring; see the source span in the claims appendix)
- `runner/acquire/license.ts` (no docstring; see the source span in the claims appendix)
- `runner/acquire/robots.ts` (no docstring; see the source span in the claims appendix)

![chapter figure](figures/fig_ch4.png)

*Figure: A few files carry most of the code in runner.*

What you can now do: open any file in `runner` and place it on this chapter's figure.

## Chapter 5: figlib

The figlib area holds 18 files of this codebase.

- `figlib/constants.py` says of itself: "constants.py - house style constants with NO matplotlib import, so the".
- `figlib/figcheck.py` says of itself: "figcheck.py - the form firewall's mechanical battery (DESIGN 5.5)".
- `figlib/figures_from_plan.py` says of itself: "figures_from_plan.py - build FigurePayloads from plan.json + model.json,".
- `figlib/introspect.py` says of itself: "introspect.py - facts about a rendered figure, taken from the live artist".
- `figlib/lint_prose.py` says of itself: "lint_prose.py - deterministic prose lints (DESIGN stage 4, pass 2)".

![chapter figure](figures/fig_ch5.png)

*Figure: The import structure inside figlib: most files lean on one hub.*

What you can now do: open any file in `figlib` and place it on this chapter's figure.

## Chapter 6: tests

The tests area holds 9 files of this codebase.

- `tests/ca.py` says of itself: "Shared helper: locate and invoke the ca binary (the Rust core CLI)".
- `tests/test_m0_intake.py` says of itself: "M0 gate: 3 source types parse with traces; 12 planted secrets -> 0 leaks".
- `tests/test_m1_compile.py` says of itself: "M1 gate (Rust core): on a real mid-size repo (llmwiki, ~104 py + 9 sql".
- `tests/test_m25_acquire.py` says of itself: "M2.5 gate: autonomous acquisition, license-gated".
- `tests/test_m2_figures.py` says of itself: "M2 gate: the figure system, calibrated".

![chapter figure](figures/fig_ch6.png)

*Figure: The import structure inside tests: most files lean on one hub.*

What you can now do: open any file in `tests` and place it on this chapter's figure.

## The cookbook

1. Clone the repo and open the entry points listed below. (expected: the files exist at the cited spans) [unverified]
2. Re-run the compile stage and diff model.json against the claims appendix. (expected: zero unresolved references) [unverified]

## Glossary

- **Archive-on-fetch**: every fetched page stored as markdown plus a rendered (span:d00027)
- **The license gate**: an external image enters the model only with a verified (span:d00029)
- **ExtractOut**: Accumulator passed through extractors. (span:r00168)
- **PdfPages**: their own spans (locator "book.pdf#p3"). (span:r00179)
- **FigureContext**: Apply a mode (print or sketch) for the duration of one render. (span:c00322)

## Claims appendix

- `c:0001` "Deterministic code establishes ground truth; the LLM does judgment on top." -> CLAUDE.md#L5-L9
- `c:0002` "The name says the contract: hand it anything, get a cookbook back." -> DESIGN.md#L7-L10
- `c:0003` "It is a **compiler with two firewalls**." -> DESIGN.md#L16-L27
- `c:0004` "Each has a deterministic floor (scripts) and a judgment layer (agents) and a checkable exit condition." -> DESIGN.md#L66-L68
- `c:0005` "One JSON document (sharded by kind on disk once large), with six record types." -> DESIGN.md#L115-L117
- `c:0006` "Secret hygiene: `intake.py` strips API keys, tokens, passwords, and high-entropy strings *before* anything reaches spans, and logs what it redacted (count and kind, never the value)." -> DESIGN.md#L206-L211
- `c:0007` "Every stage prints progress (`[Stage N/7] name...`, batch counters, one-line completion summaries)." -> DESIGN.md#L217-L218
- `c:0008` "Budget caps per run (pages, megabytes, minutes)." -> DESIGN.md#L227-L231
- `c:0009` "The **fetch ladder** (cheapest first, escalate only on failure): (1) static HTTP fetch rendered to clean markdown; (2) headless render for JS-heavy pages (also produces screenshots); (3) vision-guided browsing only when structure fails and only within budget." -> DESIGN.md#L233-L237
- `c:0010` "Web spans point at the archived copy, never the live URL alone." -> DESIGN.md#L240-L241
- `c:0011` "Public domain/CC0: free, provenance recorded." -> DESIGN.md#L244-L249
- `c:0012` "Screenshots are citation evidence, not decoration: browser-chrome frame stamped with URL and access date, minimal size, source always carried." -> DESIGN.md#L251-L252
- `c:0013` "Hard limits: no login walls, no paywall or CAPTCHA circumvention, no fetching off the allowlist." -> DESIGN.md#L254-L256
- `c:0014` "Exit condition: every fetched item has an archive copy, an audit entry, and (for media) a license record; zero robots.txt violations; budgets respected." -> DESIGN.md#L258-L259
- `c:0015` "The trace is what makes a wrong paper debuggable." -> DESIGN.md#L263-L266
- `c:0016` "Exit condition: a manifest where every source has a parser, a hash, and a trace; zero secrets in any span (verified by a planted-secret test, M0)." -> DESIGN.md#L268-L269
- `c:0017` "Exit condition: model.json validates; 100% of edges have extractors; 100% of claims have spans; zero unresolved dangling references." -> DESIGN.md#L283-L284
- `c:0018` "Exit condition: every chapter lists its node IDs, figure plan, prerequisite chapters; the prerequisite graph is acyclic." -> DESIGN.md#L294-L295
- `c:0019` "The list lives in `lint_prose.py`." -> DESIGN.md#L311-L315
- `c:0020` "Exit condition: claim coverage >= 95% of factual sentences; zero P0 prose lints; humanize pass complete with an inspectable diff." -> DESIGN.md#L317-L318
- `c:0021` "For each planned figure: declare the Figure Read, pull the payload from the model (provenance-checked), pick the recipe, render, run `figcheck.py`, then the critic inspects the actual rendered image and either passes it or cites rule IDs." -> DESIGN.md#L322-L325
- `c:0022` "Exit condition: every figure passes figcheck with zero P0/P1; payload provenance verifies; every figure referenced from prose with a takeaway caption." -> DESIGN.md#L327-L329
- `c:0023` "Assemble `paper.md` (anatomy §7), render figures at final resolution, run `grade.py`; ship only at or above the gate." -> DESIGN.md#L333-L336
- `c:0024` "The critic checks the rendered figure against its declared read." -> DESIGN.md#L369-L374
- `c:0025` "Anti-default discipline: no default color cycle, no jet/rainbow (viridis only for true continuous fields), no `figsize=(6.4, 4.8)` reflex, no title restating the caption, no 3D unless data is 3D, no pie charts, no dual y-axes." -> DESIGN.md#L376-L378
- `c:0026` "Every recipe enforces the **one-idea rule**: one point per figure, stated in the caption." -> DESIGN.md#L397-L398
- `c:0027` "A recipe's payload may contain **only**: model node IDs, model edge references, span-backed quantities, layout hints." -> DESIGN.md#L402-L407
- `c:0028` "Loop per figure: render → figcheck (mechanical) → critic on the PNG (visual) → fixes → re-render." -> DESIGN.md#L428-L429
- `c:0029` "Gates: **80 ships with warnings listed; 90 is the target; below 80 does not ship.** A red grade cannot be pushed or delivered silently." -> DESIGN.md#L484-L485
- `c:0030` "Append-only `[LEARN:tag]` entries." -> MEMORY.md#L3-L4
- `c:0031` "The score must come from assess.py before any push; opinion-based "looks done" is how slop ships." -> MEMORY.md#L6-L8
- `c:0032` "Push auth to github.com/sndsh404 works." -> MEMORY.md#L10-L13
- `c:0033` "Planted secrets must be assembled at runtime (string joins) so they exist only in the gitignored workspace." -> MEMORY.md#L15-L15
- `c:0034` "Encoding invariants in types beats enforcing them in pipelines." -> MEMORY.md#L19-L19
- `c:0035` "Wall-time gates are won in startup costs." -> MEMORY.md#L23-L23
- `c:0036` "Status filters on claim queries are load-bearing, not cosmetic." -> MEMORY.md#L25-L25
- `c:0037` "The part that keeps it honest is not the swarm at all, it is the single admission gate: workers propose, ca admit re-verifies every span reference, so a sloppy worker can only waste its own time." -> MEMORY.md#L27-L27
- `c:0038` "Give timing metrics a small tolerance band in the harness and keep the hard threshold in the gate test itself." -> MEMORY.md#L29-L29
- `c:0039` "Point it at anything: a codebase, a database dump, a folder of PDFs, a book." -> README.md#L3-L5
- `c:0040` "The paper is a view over the compiled model." -> README.md#L21-L22
- `c:0041` "Each has a deterministic floor (scripts), a judgment layer (agents), and a checkable exit condition." -> README.md#L30-L32
- `c:0042` "See `DESIGN.md` for the full spec and milestone gates (M0..M5), `CLAUDE.md` for the operating guide, and `quality_reports/` for the audit trail of every session." -> README.md#L63-L65
- `c:0043` "This repo runs on a four-document system plus an objective harness." -> WORKFLOW.md#L3-L4
- `c:0044` "Ten violations planted on purpose." -> figlib/seeded_defects/prose_slop.md#L3-L4
- `c:0045` "We leverage the buffer pool to deliver a seamless experience." -> figlib/seeded_defects/prose_slop.md#L8-L10
- `c:0046` "The cache sits between the executor and the disk — every request passes through it." -> figlib/seeded_defects/prose_slop.md#L14-L15
- `c:0047` "This paragraph is plain text where the takeaway caption should have been." -> figlib/seeded_defects/prose_slop.md#L21-L21
- `c:0048` "The model is one JSON document." -> figlib/seeded_defects/prose_slop.md#L34-L34
- `c:0049` "Also: 3 source types (git repo, PDF, mixed folder) parse with per-source trace timelines; rerun on unchanged sources reparses 0 (sha256 manifest check)." -> quality_reports/checkpoints/2026-06-11-m0-intake.md#L7-L9
- `c:0050` "METRIC secrets_leaked=0, m0_sources_parsed=3, m0_rerun_reparsed=0." -> quality_reports/checkpoints/2026-06-11-m0-intake.md#L32-L33
- `c:0051` "On llmwiki-master (real repo, 104 py + 9 sql files): 100% of 2172 edges carry extractors; 100% of 16 claims carry spans; 0 dangling edges after merge; planted agent-proposed edge clamped to 0.75 by merge.py." -> quality_reports/checkpoints/2026-06-11-m1-compile.md#L7-L10
- `c:0052` "METRIC m1_edges_extractor_pct=100, m1_claims_span_pct=100, m1_danglers=0, m1_agent_edge_clamped=1." -> quality_reports/checkpoints/2026-06-11-m1-compile.md#L40-L41
- `c:0053` "Critic caught 10/10 seeded defects citing the correct rule IDs (gate >= 9)." -> quality_reports/checkpoints/2026-06-12-m2-figures.md#L7-L10
- `c:0054` "First run on real data: F-03 (annotation column overlapping long code lines in annotated_code) and F-04 (grid color missing from the allowed set)." -> quality_reports/checkpoints/2026-06-12-m2-figures.md#L40-L44
- `c:0055` "METRIC m2_seeded_defects_caught=10, m2_recipe_violations=0, m2_recipes_rendered=7." -> quality_reports/checkpoints/2026-06-12-m2-figures.md#L48-L49
- `c:0056` "METRIC m25_robots_violations=0, m25_offsite_denied=1, m25_pages_archived=50, m25_rerun_fetches=0, m25_license_verified=1 (live api), m25_mismatch_rejected=1, m25_arr_rejected=1, m25_screenshot_framed=1." -> quality_reports/checkpoints/2026-06-12-m25-acquire.md#L45-L48
- `c:0057` "Chapter prerequisite graph acyclic (prereqs may only point backwards by construction; forward deps counted and dropped honestly)." -> quality_reports/checkpoints/2026-06-12-m3-write.md#L7-L12
- `c:0058` "METRIC m3_chapter_graph_acyclic=1, m3_claim_coverage=100, m3_planted_flagged=1, m3_banned_words=0, m3_emdashes=0, m3_prose_defects_caught=10." -> quality_reports/checkpoints/2026-06-12-m3-write.md#L53-L55
- `c:0059` "Full pipeline (stages.ts: intake -> compile -> topology -> plan -> write -> verify -> figures -> lint -> grade) on llmwiki ships at **grade 99/100** (gate >= 80), zero P0, page-one figure present, all 4 chapters figured, claims + unverified appendices emitted." -> quality_reports/checkpoints/2026-06-12-m4-ship.md#L7-L11
- `c:0060` "That is DESIGN v2 ("every real complaint becomes a named, checkable rule") happening in v0." -> quality_reports/checkpoints/2026-06-12-m4-ship.md#L27-L30
- `c:0061` "METRIC m4_grade=99, m4_chapters_figured=4, m4_figure_p0=0." -> quality_reports/checkpoints/2026-06-12-m4-ship.md#L34-L35
- `c:0062` "A one-file change (README edit) re-ships the paper at **16.3% of full-run work** (800ms vs 4919ms, stage timings in .cookbook/timings.json; gate < 20%)." -> quality_reports/checkpoints/2026-06-12-m5-incremental.md#L7-L12
- `c:0063` "The writer quoted a superseded claim whose span text had changed under it; the verifier flagged it as a broken marker." -> quality_reports/checkpoints/2026-06-12-m5-incremental.md#L33-L35
- `c:0064` "METRIC m5_rerun_work_pct=16.3, m5_supersession_linked=1, m5_history_chain_len=3." -> quality_reports/checkpoints/2026-06-12-m5-incremental.md#L46-L47
- `c:0065` "Independent support raises a claim's confidence (0.6 -> 0.7 with a second span); a span-backed contradiction mints a second claim and an event in runs.jsonl while the original stays active." -> quality_reports/checkpoints/2026-06-12-m6-swarm.md#L7-L13
- `c:0066` "METRIC m6_chapters_covered=6, m6_claims_admitted=9, m6_rejected_unsourced=2, m6_unsourced_admitted=0, m6_support_confidence_raised=1, m6_contradiction_recorded=1." -> quality_reports/checkpoints/2026-06-12-m6-swarm.md#L56-L59
- `c:0067` "Reviewer: Sandesh (stand-in during autonomous session)." -> quality_reports/issues/2026-06-12-paper-review.md#L3-L4
- `c:0068` "Chapters 1-3 all carry "*Figure: few internal edges; sizes orient the reader faster here*", which is the planner's internal `why`, not a takeaway, and it repeats verbatim." -> quality_reports/issues/2026-06-12-paper-review.md#L17-L21
- `c:0069` "The planner should fold clusters below ~3 files into a "supporting" chapter." -> quality_reports/issues/2026-06-12-paper-review.md#L38-L40
- `c:0070` "One autonomous session, all milestones M0 through M5 shipped green." -> quality_reports/session_logs/2026-06-12-session-1.md#L3-L3
- `c:0071` "Final assess: 100/100 green, no regressions." -> quality_reports/session_logs/2026-06-12-session-1.md#L17-L18
- `c:0072` "Open items for the next session: planner folding of thin chapters (filed issue 5), the LLM vision critic on rendered PNGs (the judgment layer the seeded-defect gate was built to calibrate), playwright as fetch ladder rung 2, and the docx export." -> quality_reports/session_logs/2026-06-12-session-1.md#L26-L29
- `c:w0001` "This codebase compiles to a model of 68 files and 204 functions, every one traced to source." -> CLAUDE.md
- `c:w0002` "The tour below walks 6 areas in dependency order, so nothing is used before it is taught." -> CLAUDE.md
- `c:w0003` "The (root) area holds 5 files of this codebase." -> CLAUDE.md, DESIGN.md, MEMORY.md, README.md
- `c:w0004` "The core area holds 16 files of this codebase." -> core/ca-cli/src/admit.rs, core/ca-cli/src/main.rs, core/ca-cli/src/plan.rs, core/ca-cli/src/verify.rs
- `c:w0005` "The quality_reports area holds 11 files of this codebase." -> quality_reports/assessment_latest.md, quality_reports/checkpoints/2026-06-11-m0-intake.md, quality_reports/checkpoints/2026-06-11-m1-compile.md, quality_reports/checkpoints/2026-06-12-m2-figures.md
- `c:w0006` "The runner area holds 8 files of this codebase." -> runner/acquire/acquire.ts, runner/acquire/html2md.ts, runner/acquire/infra.ts, runner/acquire/license.ts
- `c:w0007` "The figlib area holds 18 files of this codebase." -> figlib/constants.py, figlib/figcheck.py, figlib/figures_from_plan.py, figlib/introspect.py
- `c:w0008` "`figlib/constants.py` says of itself: "constants.py - house style constants with NO matplotlib import, so the"." -> figlib/constants.py
- `c:w0009` "`figlib/figcheck.py` says of itself: "figcheck.py - the form firewall's mechanical battery (DESIGN 5.5)"." -> figlib/figcheck.py
- `c:w0010` "`figlib/figures_from_plan.py` says of itself: "figures_from_plan.py - build FigurePayloads from plan.json + model.json,"." -> figlib/figures_from_plan.py
- `c:w0011` "`figlib/introspect.py` says of itself: "introspect.py - facts about a rendered figure, taken from the live artist"." -> figlib/introspect.py
- `c:w0012` "`figlib/lint_prose.py` says of itself: "lint_prose.py - deterministic prose lints (DESIGN stage 4, pass 2)"." -> figlib/lint_prose.py
- `c:w0013` "The tests area holds 9 files of this codebase." -> tests/ca.py, tests/test_m0_intake.py, tests/test_m1_compile.py, tests/test_m25_acquire.py
- `c:w0014` "`tests/ca.py` says of itself: "Shared helper: locate and invoke the ca binary (the Rust core CLI)"." -> tests/ca.py
- `c:w0015` "`tests/test_m0_intake.py` says of itself: "M0 gate: 3 source types parse with traces; 12 planted secrets -> 0 leaks"." -> tests/test_m0_intake.py
- `c:w0016` "`tests/test_m1_compile.py` says of itself: "M1 gate (Rust core): on a real mid-size repo (llmwiki, ~104 py + 9 sql"." -> tests/test_m1_compile.py
- `c:w0017` "`tests/test_m25_acquire.py` says of itself: "M2.5 gate: autonomous acquisition, license-gated"." -> tests/test_m25_acquire.py
- `c:w0018` "`tests/test_m2_figures.py` says of itself: "M2 gate: the figure system, calibrated"." -> tests/test_m2_figures.py

## Unverified appendix

- no agent-proposed edges in this model
- cookbook steps marked [unverified] above await execution evidence

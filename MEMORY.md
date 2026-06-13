# MEMORY.md: durable lessons

Append-only `[LEARN:tag]` entries. Read at session start; written after every
milestone or surprise.

[LEARN:workflow] 2026-06-11 The roofline pattern ports cleanly: four docs +
an objective harness + checkpoints. The score must come from assess.py before
any push; opinion-based "looks done" is how slop ships.

[LEARN:env] 2026-06-11 Toolchain: Windows 11, Python 3.14.3, matplotlib
3.10.8, git 2.44, PowerShell 5.1 (no && chaining). Reference repos extracted
locally (exact path in .claude/state/env.local.md, gitignored); tests read it
from the CA_REF_DIR env var or .claude/state/ref_dir.txt.

[LEARN:secrets] 2026-06-11 GitHub push protection scans pushed blobs and blocks secret-shaped literals even in test fixtures. Planted secrets must be assembled at runtime (string joins) so they exist only in the gitignored workspace. Our own intake filter and GitHub's scanner agree on what looks like a secret, which is a free calibration signal.

[LEARN:rust] 2026-06-12 regex::bytes has unicode mode ON by default, so '.' refuses to cross invalid UTF-8 (e.g. compressed PDF streams) and the pattern silently never matches. Use (?-u) for binary scanning. Cost: one silent extraction failure that only the gate test caught.

[LEARN:architecture] 2026-06-12 The polyglot split (rust core / ts runner / python figlib) made one whole class of merge code disappear: the agent-confidence clamp is gone because ca-model makes an agent edge at confidence 1.0 unrepresentable. Encoding invariants in types beats enforcing them in pipelines.

[LEARN:git] 2026-06-12 Commit style: one line, lowercase, short, no trailers (e.g. 'm4: ship paper at grade 99').

[LEARN:incremental] 2026-06-12 The 20 pct incremental gate was met by attacking fixed overheads, not the obvious stages: lazy matplotlib import (a cached figure run never pays it), stat-based hash skipping (git's move), one alternation regex instead of O(n^2) regex builds, and merging two python spawns into one. Wall-time gates are won in startup costs.

[LEARN:verify] 2026-06-12 Supersession plus a verbatim-checking verifier caught a subtle writer bug: quoting a superseded claim whose span text changed under it. Status filters on claim queries are load-bearing, not cosmetic.

[LEARN:swarm] 2026-06-12 The OpenAI swarm pattern (agent + handoff + shared context, nothing else) drops cleanly onto deterministic workers: parallel fan-out is just Promise.all over handoffs with array-merging context. The part that keeps it honest is not the swarm at all, it is the single admission gate: workers propose, ca admit re-verifies every span reference, so a sloppy worker can only waste its own time.

[LEARN:harness] 2026-06-12 Zero-tolerance regression checks on wall-clock metrics produce false reds (15.6 to 15.8 pct). Give timing metrics a small tolerance band in the harness and keep the hard threshold in the gate test itself.

[LEARN:privacy] 2026-06-12 Absolute paths in committed files leak a username and break on other machines; they crept in via test fixtures hardcoding a reference-repo path. Fix: tests read machine paths from an env var or a gitignored .claude/state file, and assess.py scans tracked files for home-dir patterns (C:\Users\, /home/, /Users/) as a P1 so it cannot silently recur. Git history still holds the old leak; not rewriting it, just stopping the bleed.

[LEARN:dogfood] 2026-06-13 Running the tool on its own repo was the best test we had: it caught three real bugs no synthetic gate did. The repo documents its own machinery, so the writer quoted a {{c:NNNN}} marker example into the paper and the verifier choked; the architecture figure silently omitted whole layers because extraction was Python-only; and doc-only chapters referenced figures that were never rendered. A tool that consumes its own docs surfaces collisions between its data and its mechanism that no clean-room fixture will. Dogfood early.

[LEARN:teaching] 2026-06-13 The chapter template, distilled from Grokking Algorithms (gold standard), Clean Architecture, and Linux Kernel Development. A verified table of contents is not a cookbook; these six moves are what make prose TEACH:
  1. PROBLEM FIRST. Open with the problem this component solves and what breaks without it, before any mechanism. Grokking opens binary search with "searching for a person in the phone book", not with the algorithm. Clean Arch opens structured programming with the decade-long goto war. Love opens task_struct with why you need fast access to the current task. Make the reader feel the need first.
  2. NAME IT, ONE-LINE JOB. After the problem, name the component and state its single job in one plain sentence.
  3. ONE WORKED EXAMPLE, TRACED. Follow ONE concrete thing through the mechanism with real values and visible state changes, step by step. Grokking: guess 50 (too low, half gone) -> 75 (too high) -> 63. Not an abstract description; an actual trace. Often contrast the naive way first to make the pain real ("simple search could take 99 guesses").
  4. A TEACHING FIGURE THAT SHOWS INTERACTION. Dataflow, sequence, or state-machine showing how the pieces move/talk, captioned with the lesson it teaches. Love's Fig 3.3 is a process-state flowchart, not a bar chart. A figure of file sizes teaches nothing about how the system works.
  5. EXPLAIN 3-5 KEY PIECES IN PLAIN LANGUAGE. What each does and why, conversational, annotated like Grokking annotates each line of binary_search ("low and high keep track of which part"). Never an exhaustive filename dump.
  6. CLOSE WITH "WHAT YOU CAN NOW DO." A concrete capability or an exercise the reader can act on, like Grokking's end-of-chapter exercises.
  Voice: plain and conversational, WHY before HOW, one concept per chapter explored deeply rather than many listed shallowly. The dogfood paper failed exactly here: "the X area holds N files" + filename list + "open any file" is moves 0 of 6. Use the explanatory design claims already in the model (e.g. "compiler with two firewalls") for move 1, the real call/import edges for move 3-4.

[LEARN:teaching-impl] 2026-06-13 Building the teaching writer, what mattered: (1) the WHY claims must come from design docs, not session metrics - claims sourced from quality_reports (grades, edge counts) are true but operational noise; exclude them from chapter openings. (2) The teaching figure needs real interaction edges to show, so extraction had to grow cross-module calls (python) and crate/relative import resolution (rust/ts) - without them the figure is a file-size bar chart, which teaches nothing. (3) Disambiguate file labels by NEAREST NON-GENERIC ancestor: five lib.rs all have parent "src", so "src/lib.rs" is still ambiguous; "ca-model/lib.rs" is right. (4) The teaching gate must be paper-level (fail if < half the chapters teach), not per-chapter-fatal, or any real repo with one thin area becomes unshippable. (5) Quoting source claims verbatim can import voice violations (em dashes) into the body - strip them on display, keep the claim verbatim in the model and appendix.

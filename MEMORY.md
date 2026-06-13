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

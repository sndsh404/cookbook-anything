# MEMORY.md — durable lessons

Append-only `[LEARN:tag]` entries. Read at session start; written after every
milestone or surprise.

[LEARN:workflow] 2026-06-11 The roofline pattern ports cleanly: four docs +
an objective harness + checkpoints. The score must come from assess.py before
any push; opinion-based "looks done" is how slop ships.

[LEARN:env] 2026-06-11 This machine: Windows 11, Python 3.14.3, matplotlib
3.10.8, git 2.44, PowerShell 5.1 (no && chaining). Push auth to
github.com/sndsh404 works. Reference repos extracted at
C:\Users\bhansa01\Downloads\cookbook-20260611T231425Z-3-002\cookbook\.

[LEARN:secrets] 2026-06-11 GitHub push protection scans pushed blobs and blocks secret-shaped literals even in test fixtures. Planted secrets must be assembled at runtime (string joins) so they exist only in the gitignored workspace. Our own intake filter and GitHub's scanner agree on what looks like a secret, which is a free calibration signal.

[LEARN:rust] 2026-06-12 regex::bytes has unicode mode ON by default, so '.' refuses to cross invalid UTF-8 (e.g. compressed PDF streams) and the pattern silently never matches. Use (?-u) for binary scanning. Cost: one silent extraction failure that only the gate test caught.

[LEARN:architecture] 2026-06-12 The polyglot split (rust core / ts runner / python figlib) made one whole class of merge code disappear: the agent-confidence clamp is gone because ca-model makes an agent edge at confidence 1.0 unrepresentable. Encoding invariants in types beats enforcing them in pipelines.

[LEARN:git] 2026-06-12 Sandesh wants commit messages short and sweet, e.g. 'm4: ship paper at grade 99'. Keep them one line, lowercase, no trailers.

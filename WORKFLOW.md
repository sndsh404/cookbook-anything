# WORKFLOW.md — the session loop

This repo runs on a four-document system plus an objective harness. The loop
is the same every session, no exceptions.

## The four documents

| Document | Role | Who writes it |
|---|---|---|
| `DESIGN.md` | the full spec: stages, schema, rules, milestone gates | edited only when the design genuinely changes; changes are logged |
| `CLAUDE.md` | the operating guide: prime directive, hard rules, repo map, commands, milestone checklist | updated when reality changes; checkboxes tick only after the harness verifies |
| `WORKFLOW.md` | this file: how a session runs | rarely |
| `MEMORY.md` | durable `[LEARN:tag]` entries, the compounding half of the loop | appended after every milestone or surprise |

## Supporting state

- `quality_reports/assessment_latest.md` — output of the last `assess.py` run.
- `quality_reports/checkpoints/YYYY-MM-DD-<slug>.md` — one per milestone or
  significant session: what shipped, the number that moved, decisions made.
- `quality_reports/session_logs/` — running log per session.
- `.claude/state/last_assessment.json` — machine-readable last score, for
  regression detection. Gitignored; the markdown report is the durable record.

## The session loop

1. **Orient.** Read CLAUDE.md (checklist), the latest assessment, and the last
   checkpoint. Pick the first unchecked milestone.
2. **Restate the number.** Every milestone ends in a number (DESIGN §10). Say
   it before writing code. If the criterion has no number, pick the closest
   verifiable proxy and record that decision.
3. **Study the pattern.** The reference repos exist so we extract patterns,
   not guesses. Read the relevant one before writing the equivalent.
4. **Implement on a branch** `m<N>/<slug>`. Code AND its gate test together.
5. **Gate.** `python scripts/assess.py` must exit 0: build + tests pass, the
   milestone number is met and recorded, no regression vs the last run, no
   hard-rule violations.
6. **Record.** Checkpoint file, `[LEARN]` entries, tick the CLAUDE.md box
   (only if the harness verified it), merge to main, push (only on green).
7. **Next milestone immediately.** If blocked after three genuine attempts,
   log the blocker in the checkpoint and start the next independent milestone.

## Hard rules (enforced by assess.py, not by promises)

- The score comes from the script, never from opinion. The assessor's job is
  to find the weakest link, not to praise.
- A red gate (score < 80, any P0, or a regression) cannot reach main.
- Deterministic code establishes ground truth; judgment layers only annotate.
  No edge without an extractor. No claim without a span. No external asset
  without a verified license record.
- Commits are authored by Sandesh Bhandari, plain lowercase messages, no
  generated-with trailers.

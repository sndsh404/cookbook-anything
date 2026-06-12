# Paper review: llmwiki cookbook (M4 human pass)

Reviewer: Sandesh (stand-in during autonomous session). Five concrete
issues; each becomes a rule, a writer fix, or a recorded limitation.

## Issue 1 (P1): redaction artifact quoted into shipped prose

The intro quotes a doc claim containing "gist.github.[REDACTED:high_entropy]"
(the entropy filter ate a gist URL hash at intake, and the claim extractor
lifted the sentence verbatim).
**Fix shipped:** claim extraction rejects sentences containing "[REDACTED"
(core/ca-extract markdown.rs), and lint_prose gains a P1
`prose-redaction-artifact` rule so any future leak is caught at the gate.

## Issue 2 (P1): chapter figure captions are identical boilerplate

Chapters 1-3 all carry "*Figure: few internal edges; sizes orient the reader
faster here*", which is the planner's internal `why`, not a takeaway, and it
repeats verbatim. **Fix shipped:** the writer now composes a per-chapter
takeaway caption from the recipe + chapter title (distinct, sentence-cased,
ends with a period).

## Issue 3 (P2): "(no docstring)" bullets dominate the chapters

11 of 15 file bullets are the fallback line; alphabetical pick surfaces the
least documented files. **Fix shipped:** the writer sorts chapter members
documented-first so the bullets teach something.

## Issue 4 (P2): grader and linter disagreed on em-dash scope

ca-grade scanned the whole paper (found 2 em dashes inside verbatim glossary
quotes, -6) while lint_prose scopes to authored prose. One rule, two scopes.
**Fix shipped:** ca-grade now scopes its prose scans to the authored body
(before ## Glossary), same as the linter.

## Issue 5 (P3, recorded): thin chapters

"converter" is a 2-file chapter (one file is requirements.txt). The planner
should fold clusters below ~3 files into a "supporting" chapter. Not fixed in
this session; candidate for the next planner iteration.

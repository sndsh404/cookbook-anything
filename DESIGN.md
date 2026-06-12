# cookbook-anything

*Point it at anything (a codebase, a database dump, a folder of PDFs, a book)
and it compiles a paper that teaches it: well written, figure-rich, cookbook
structured, and verifiable down to the sentence.*

The name says the contract: hand it anything, get a cookbook back. The
quality bar is borrowed from the Young Lady's Illustrated Primer in
Stephenson's *The Diamond Age*: a book that can take any subject and teach it
to one specific reader, beautifully.

---

## 0. What this is, in one paragraph

cookbook-anything is not a paper generator. It is a **compiler with two firewalls**. The
front end deterministically extracts a knowledge model from the sources: every
fact has a citation to a source span, every graph edge comes from an extractor
script, nothing enters the model on the LLM's word alone. That is the **truth
firewall**, and it is what makes the output verifiable instead of plausible.
The back end renders that model into prose and figures under enforced taste
rules: a declared Figure Read before any figure, a locked house style, a recipe
library instead of freeform matplotlib, a critic that must cite the specific
rule it is flagging. That is the **form firewall**, and it is what makes the
output look designed instead of generated. The paper is a *view over the
compiled model*. Because the model persists, the second run on the same
sources is an incremental update, not a re-derivation: the system compounds.

**Prime directive.** At every stage, deterministic code establishes ground
truth and the LLM does judgment on top of it. When output is wrong, the
question is always "which extractor, script, or rule failed," never "the model
hallucinated and we shrug." If you find yourself letting an agent assert a fact
or draw an edge that no script extracted, stop: the fix is a better extractor
or an honest "unverified" marker, never a more confident prompt.

---

## 1. Lineage

Built by extracting the load-bearing pattern from the studied systems. The
mapping is the design, not decoration:

| Source | Pattern taken | Becomes |
|---|---|---|
| Karpathy LLM Wiki gist (v2) | compile don't re-derive; claims carry citations + confidence; supersession; secret-filter on ingest; audit trail | the knowledge model and its lifecycle |
| llmwiki | deterministic index + a tiny fixed tool surface; restraint | the model store and its access API |
| Understand-Anything | scan/batch/parallel-analyze/merge+review pipeline; topology script before pedagogy; incremental updates; progress reporting; "a graph that quietly teaches" | the compile and plan stages |
| coroot | the map is derived from measured structure, zero config, no blind spots; predefined inspections | structure graphs come from extractors only; hallucinated edges are impossible by construction |
| WeKnora | pluggable per-source parsers; parsing trace timeline; parent-child chunking | the intake stage and its observability |
| Trilium | one note, many parents (clones); typed attributes | concept pages written once, placed in many chapters |
| WritingAIPaper | CARS introduction; page-one figure; confusion time; topic sentences; reviewer-comment rubric | the document architecture and prose lints |
| humanizer | signs-of-AI-writing catalog; rewrite don't delete; voice calibration from a sample; "sterile is also slop" | the prose firewall |
| taste-skill | brief inference (declare the read first); explicit dials; anti-default discipline; hard rules with named failure modes | the Figure Read protocol and the figure rule catalog |
| matplotlib-gallery | a curated catalog by chart type; publication settings | the house recipe library: choose a recipe, don't improvise |
| claude-code-my-workflow | computed label positions (six-pass collision protocol); semantic visual conventions; scripted quality score with severity deductions; claim-verifier; critics that cite the rule | the figure QA loop and the grading harness |
| scrapy | the politeness middleware stack: robots.txt, retry/backoff, HTTP cache, offsite scoping, throttling | the deterministic floor of autonomous acquisition |
| firecrawl | URL to clean LLM-ready markdown / screenshot / structured JSON | the canonical web ingestion formats |
| Scrapling | adaptive parsing that relocates elements when sites change; a tiered fetch ladder | selector self-healing on incremental re-runs; escalate fetch cost only on failure |
| Scrapegraph-ai | declare a schema, the pipeline fills it from the page | asset requests as typed payloads, not "go scrape something" |
| Scrape-anything web agent | screenshot, look, decide: vision-guided browsing when structure fails | the last rung of the fetch ladder |
| medium2pdf-scraper | archive web content as durable searchable PDFs at fetch time | archive-on-fetch, so spans survive web rot |

**Honest prior art.** DeepWiki, Devin's wiki features, repo-explainer tools,
and "chat with your codebase" products all exist. What none of them center,
and what cookbook-anything's three defensible contributions are: (1) the **figure
provenance contract**, where a figure can only render data that resolves to
model node IDs, making a hallucinated architecture arrow structurally
impossible; (2) the **form firewall as enforceable rules**, a critic loop over
actually rendered images citing named failure modes, not "make it pretty";
(3) **critic calibration by seeded defects**, where a critic is only trusted
after it demonstrably catches violations planted on purpose. Everything else
is good engineering; those three are the thesis.

---

## 2. System shape

```
            TRUTH FIREWALL                          FORM FIREWALL
  ┌────────────────────────────────┐   ┌─────────────────────────────────┐
  web ⇄ ACQUIRE → sources → INTAKE → COMPILE → MODEL → PLAN → WRITE → FIGURE → SHIP
   (license gate,                                      ↑ asset requests (demand mode) │
    archive, audit)  ←───────────────────────────────────────────────────────────────┘
            scripts   scripts+agents    script  agent   recipes  score
            (parse,    (extract graph,  orders  drafts  render+  gates
             filter,    annotate,       chapters from   inspect
             trace)     merge, review)  by topology     loop
                                  ▲
                                  │ persists in .cookbook/ ; second run is
                                  └ incremental (changed sources only)
```

Six stages. Each has a deterministic floor (scripts) and a judgment layer
(agents) and a checkable exit condition. A stage's agent may never overwrite
what its scripts established; it may only annotate, select, and explain.

cookbook-anything runs as a Claude Code project: skills are the stage entrypoints, agents
are the judgment layers, scripts are the floors, and the workspace holds the
sources, the compiled model, and the outputs.

---

## 3. Workspace and repo layout

```
cookbook-anything/
  .claude/
    skills/            # stage entrypoints (orchestrator + per-stage)
    agents/            # judgment layers (analyzer, reviewers, critics)
  scripts/
    acquire.py       # web fetch ladder, robots/rate limits, archive-on-fetch, license gate
    intake.py        # source router, parser dispatch, secret filter, manifest, trace
    extract_code.py  # imports/defines/calls graph (per-language extractors)
    extract_doc.py   # PDF/markdown/HTML structure: sections, headings, spans
    extract_data.py  # CSV/SQL schema: tables, columns, foreign keys
    merge.py         # normalize, dedupe, drop dangling refs; report fixed vs could-not-fix
    topology.py      # entry points, centrality, dependency order, clusters
    figcheck.py      # collision passes, palette/font checks, provenance verification
    lint_prose.py    # confusion-time, banned vocabulary, claim coverage, caption checks
    grade.py         # the scored gate (assess.py pattern)
  figlib/
    style.py         # the house style: rcParams, palette, both modes (print/sketch)
    recipes/         # one module per recipe (see §6.3)
    seeded_defects/  # known-bad figures for critic calibration (see §9.2)
  workspace/         # per-project; gitignored
    sources/         # the user's inputs (or pointers to them)
    .cookbook/         # the compiled model + trace + ledger (persists across runs)
      model.json     # the knowledge model (§4)
      trace/         # per-source parsing timelines
      runs.jsonl     # audit trail of every operation
    out/
      paper.md       # the deliverable + figures/ + paper.docx (optional)
  DESIGN.md          # this file
  CLAUDE.md          # operating guide distilled from this file
  MEMORY.md          # durable [LEARN] record (the compounding half of /improve)
```

---

## 4. The knowledge model

One JSON document (sharded by kind on disk once large), with six record
types. This schema is the contract every stage reads and writes. Nothing in
the paper may rest on information that is not in it.

```jsonc
{
  "sources": [{
    "id": "src:0001",
    "type": "git_repo | pdf | markdown | csv | sql_dump | folder",
    "path": "sources/bustub-master",
    "parser": "extract_code.py@cpp",
    "sha256": "...",
    "ingested_at": "2026-06-11T..."
  }],

  "spans": [{
    "id": "span:00042",
    "source": "src:0001",
    "locator": "src/buffer/buffer_pool_manager.cpp#L41-L88",
    "text_sha": "..."
  }],

  "nodes": [{
    "id": "node:bpm",
    "type": "file | function | class | module | concept | table | column | section | person | decision",
    "name": "BufferPoolManager",
    "summary": "Owns the frame table; decides which pages live in memory.",
    "attrs": {"language": "cpp", "loc": 412, "complexity": "moderate"},
    "spans": ["span:00042"]
  }],

  "edges": [{
    "source": "node:bpm",
    "target": "node:lru_k",
    "type": "imports | calls | defines | contains | documents | depends_on | foreign_key | supersedes | contradicts",
    "extractor": "extract_code.py@cpp",
    "spans": ["span:00043"],
    "confidence": 1.0
  }],

  "claims": [{
    "id": "c:0317",
    "text": "Page eviction uses an LRU-K replacer with K=2 by default.",
    "spans": ["span:00044", "span:00102"],
    "confidence": 0.9,
    "status": "active | superseded",
    "supersedes": null
  }],

  "tours": [{
    "id": "tour:main",
    "steps": [{"node": "node:readme", "why": "orients before any code"}]
  }],

  "glossary": [{
    "term": "frame",
    "definition": "A slot of buffer-pool memory that holds one page.",
    "first_span": "span:00042"
  }],

  "assets": [{
    "id": "asset:0007",
    "kind": "image | screenshot | pdf_snapshot",
    "origin_url": "https://commons.wikimedia.org/wiki/File:Bplustree.png",
    "archive_path": "sources/web/asset-0007.png",
    "fetched_at": "2026-06-11T...",
    "sha256": "...",
    "license": {
      "name": "CC BY-SA 4.0",
      "author": "...",
      "evidence_url": "...",
      "verified_by": "commons_api | openverse_api | page_statement"
    },
    "attribution": "Image: <author>, CC BY-SA 4.0, via Wikimedia Commons"
  }]
}
```

Three rules with no exceptions:

1. **No edge without an extractor.** Agents may *propose* an edge they believe
   exists; it enters with `confidence < 1.0`, is rendered dashed in any figure,
   and is listed in the paper's "unverified" appendix until an extractor or a
   human confirms it.
2. **No claim without a span.** A sentence the writer cannot back with a span
   is opinion, and opinion is labeled as such in the paper or cut.
3. **Supersession over silent edits.** When a re-run contradicts an existing
   claim, the old claim is marked superseded and linked, never deleted. The
   audit trail (`runs.jsonl`) records every mutation with a timestamp and the
   stage that made it.

Secret hygiene: `intake.py` strips API keys, tokens, passwords, and
high-entropy strings *before* anything reaches spans, and logs what it
redacted (count and kind, never the value). Secret filtering is not PII
scrubbing: the default policy for database sources is **schema-first**
(tables, columns, types, foreign keys, row counts; sampled rows only with
basic PII redaction; full row ingestion opt-in and logged).

---

## 5. The pipeline, stage by stage

Every stage prints progress (`[Stage N/7] name...`, batch counters, one-line
completion summaries).

### Stage 0 — ACQUIRE (autonomous, budgeted, license-gated)

Two modes. **Seed mode**: user gives URLs/topics up front. **Demand mode**:
during PLAN or FIGURE an agent files a typed **asset request** and Stage 0
fulfills it. No agent fetches directly; every request goes through
`acquire.py`.

`acquire.py` is scrapy's middleware stack reborn: robots.txt respected
unconditionally, per-domain rate limits and backoff, an HTTP cache so nothing
is fetched twice, offsite scoping to the allowlist, an honest User-Agent, and
every fetch logged to the audit trail. Budget caps per run (pages, megabytes,
minutes).

The **fetch ladder** (cheapest first, escalate only on failure): (1) static
HTTP fetch rendered to clean markdown; (2) headless render for JS-heavy pages
(also produces screenshots); (3) vision-guided browsing only when structure
fails and only within budget. Adaptive relocation re-finds content when a
site's structure changed; the trace records the heal.

**Archive-on-fetch**: every fetched page stored as markdown plus a rendered
snapshot in `sources/web/`. Web spans point at the archived copy, never the
live URL alone. The live URL plus access date ride along as metadata.

**The license gate**: an external image enters the model only with a verified
license record (Wikimedia Commons API, Openverse, or an archived explicit
page statement). Public domain/CC0: free, provenance recorded. CC BY / BY-SA:
usable, attribution auto-generated and non-removable; SA flagged. NC/ND:
flagged to the user before use. Unknown/all-rights-reserved: does not embed;
link instead, or file a figure request to re-draw the facts as an original
diagram from the model.

Screenshots are citation evidence, not decoration: browser-chrome frame
stamped with URL and access date, minimal size, source always carried.

Hard limits: no login walls, no paywall or CAPTCHA circumvention, no fetching
off the allowlist. If the system cannot verify it is allowed, it does not do
it silently.

Exit condition: every fetched item has an archive copy, an audit entry, and
(for media) a license record; zero robots.txt violations; budgets respected.

### Stage 1 — INTAKE (deterministic only; no agent)

`intake.py` walks `sources/`, routes each item to a parser by type, runs the
secret filter, and writes the source manifest plus a per-source trace
timeline (which parser ran, what it produced, where it fell back). The trace
is what makes a wrong paper debuggable.

Exit condition: a manifest where every source has a parser, a hash, and a
trace; zero secrets in any span (verified by a planted-secret test, M0).

### Stage 2 — COMPILE (scripts extract; agents annotate; script merges; agent reviews residue)

1. **Extract.** `extract_code.py` (imports, defines, contains; calls where
   supported), `extract_doc.py` (section graph), `extract_data.py` (schema
   graph). All edges born here carry `confidence: 1.0` and the extractor name.
2. **Annotate in parallel.** Spans batched; analyzer writes node summaries,
   proposes concept nodes, extracts claims with spans, drafts glossary
   entries. Bounded context per batch keeps summaries grounded.
3. **Merge.** `merge.py` normalizes IDs, dedupes, drops dangling refs; prints
   *Fixed* and *Could not fix*.
4. **Review the residue.** The reviewer handles only the second list.

Exit condition: model.json validates; 100% of edges have extractors; 100% of
claims have spans; zero unresolved dangling references.

### Stage 3 — PLAN (script computes structure; agent designs pedagogy)

`topology.py` computes entry points, dependency chains, centrality, clusters.
Then the planner turns topology into a chapter plan: dependency order (no
term before its prerequisites), CARS opening, page-one figure assigned before
a word is written, a figure plan per chapter (no chapter ships without a
figure unless a written reason is recorded), concept pages with many parents.

Exit condition: every chapter lists its node IDs, figure plan, prerequisite
chapters; the prerequisite graph is acyclic.

### Stage 4 — WRITE (agent drafts; script lints; agents audit)

Writer drafts strictly from the model with inline claim markers
(`{{c:0317}}`), stripped only at ship time after verification. Three passes:

1. **claim-verifier** (adversarial): every marker resolves to spans that
   actually support the sentence; unsupported flagged, not silently fixed.
2. **`lint_prose.py`** (deterministic): confusion-time checks (glossary term
   first use within 50 words of definition or link; topic sentences),
   banned-vocabulary scan, em-dash scan, sentence-length distribution,
   caption checks.
3. **humanize-auditor**: signs-of-AI-writing catalog with the voice profile;
   rewrite don't delete; fires both directions (slop and sterile).

Default voice profile: plain confident prose, short sentences favored, first
person sparing, no em dashes, banned list includes at minimum: *leverage,
robust, seamless, delve, utilize, streamline, navigate (metaphorical),
crucial, comprehensive, holistic, in today's fast-paced world, it's important
to note, dive deep*. The list lives in `lint_prose.py`.

Exit condition: claim coverage >= 95% of factual sentences; zero P0 prose
lints; humanize pass complete with an inspectable diff.

### Stage 5 — FIGURE

For each planned figure: declare the Figure Read, pull the payload from the
model (provenance-checked), pick the recipe, render, run `figcheck.py`, then
the critic inspects the actual rendered image and either passes it or cites
rule IDs. Max 3 iterations, then escalate with the critic's report.

Exit condition: every figure passes figcheck with zero P0/P1; payload
provenance verifies; every figure referenced from prose with a takeaway
caption.

### Stage 6 — SHIP

Assemble `paper.md` (anatomy §8), render figures at final resolution, run
`grade.py`; ship only at or above the gate. Strip claim markers; emit the
claims appendix and the unverified-edges appendix. Append the run to
`runs.jsonl`.

**Incremental re-runs.** `intake.py` hashes sources; only changed sources
re-enter the pipeline. Contradicting claims trigger supersession. Plan and
prose re-touch only chapters whose nodes changed. Target: a one-file change
re-ships touching < 20% of the pipeline work (M5).

---

## 6. The figure system

### 6.1 House style

One `figlib/style.py`, two modes, both locked:

- **`print` mode** (default): `figure.dpi: 200`, tight bounding boxes, top and
  right spines off, light gray dotted grid (`#DDDDDD`, behind data), humanist
  sans at a floor of 9pt rendered (DejaVu Sans fallback), axis line weight
  1.0, data 2.0, annotation 1.2, consistent dot radius.
- **`sketch` mode**: xkcd mode tuned to hand-drawn-notes. Same palette, same
  rules. One mode per paper; mixing is a P1.

**Palette: semantic, named, closed.** Six colors: `ink`, `accent`, `good`,
`warn`, `muted`, `paper`. Default matplotlib cycle banned; `accent` once per
figure family with one meaning; solid = real/observed, dashed =
proposed/unverified/counterfactual (confidence < 1.0 edges must render
dashed).

**Direct labeling over legends.** Boxed legend over data is F-07. Legends only
when > ~6 series, frameless, outside the axes.

### 6.2 The Figure Read (declare before drawing)

Before rendering, the figure stage writes one line into the figure metadata:
"Reading this as: a *dataflow* figure for *newcomers*, 7 nodes from
`tour:main` steps 2-4, left-to-right, accent on the buffer pool, print mode,
density dial 3." Two dials: **density** (1-10) and **formality** (print vs
sketch, per paper). The critic checks the rendered figure against its
declared read.

Anti-default discipline: no default color cycle, no jet/rainbow (viridis only
for true continuous fields), no `figsize=(6.4, 4.8)` reflex, no title
restating the caption, no 3D unless data is 3D, no pie charts, no dual y-axes.

### 6.3 The recipe library (v0 ships twelve; M2 lands six)

| Recipe | Use when | Payload (from the model) |
|---|---|---|
| `architecture_box` | page-one figure; component overview | nodes + contains/depends_on edges, clustered |
| `dataflow` | how a request/datum moves | ordered nodes + directed edges |
| `dependency_graph` | what imports/uses what | nodes + imports edges; > 25 nodes triggers clustering |
| `pipeline_stages` | sequential processes | ordered stages + artifacts |
| `layered_stack` | abstraction layers | ordered layers + one-line roles |
| `sequence` | call order over time | actors + ordered calls edges |
| `state_machine` | lifecycles, statuses | states + transition edges |
| `before_after` | refactors, migrations | two payloads, shared scale |
| `annotated_code` | walking a snippet | a span + annotation anchors |
| `schema_er` | database sources | tables + foreign_key edges |
| `concept_map` | idea relationships | concept nodes + typed edges |
| `quantity` | numbers worth seeing | series with units and provenance |

Every recipe enforces the **one-idea rule**: one point per figure, stated in
the caption. Density beyond a recipe's ceiling forces clustering or a split.

### 6.4 The figure data contract

A recipe's payload may contain **only**: model node IDs, model edge
references, span-backed quantities, layout hints. The renderer embeds the
payload hash and node IDs in the output metadata. `figcheck.py` verifies:
every node exists in the model; every edge exists (or confidence < 1.0 AND
dashed); every number carries a span reference. A figure that draws an arrow
the model does not contain fails F-01 and cannot ship.

### 6.5 The rule catalog and the critic loop

| ID | Severity | Rule |
|---|---|---|
| F-01 | P0 | Provenance: every node/edge/number resolves to the model; unverified edges render dashed |
| F-02 | P0 | Legibility: no rendered text below 9pt-equivalent at actual display width |
| F-03 | P0 | Collisions: no label-label or label-element overlap |
| F-04 | P1 | Palette: house palette only; no default cycle; accent once, semantic |
| F-05 | P1 | Caption: full sentence stating the takeaway, not a noun phrase |
| F-06 | P1 | Orphan: figure referenced from prose; reference says what to look at |
| F-07 | P1 | Legend: direct labels preferred; boxed legend over data fails |
| F-08 | P1 | One idea: one point per figure; caption states it |
| F-09 | P1 | Density: within the recipe's ceiling |
| F-10 | P2 | Chartjunk: no redundant title, heavy grid, 3D, drop shadows |
| F-11 | P2 | Read match: rendered figure matches declared Figure Read |
| F-12 | P2 | Consistency: line weights, dot sizes, arrowheads identical across figures |
| F-13 | P0 | External media: verified license record; attribution present and matching; NC/ND only with logged approval |
| F-14 | P1 | Screenshots: browser-chrome frame, URL + date stamp, minimal size, evidence reference in prose |

Loop per figure: render → figcheck (mechanical) → critic on the PNG (visual)
→ fixes → re-render. Max 3 iterations, then escalate with cited findings.

---

## 7. The writing system (contracts)

- **Claim coverage >= 95%** of factual sentences resolve to claims with spans.
- **Confusion-time lints**: first use defined within 50 words or linked; topic
  sentences; long-sentence outliers. (Heuristics, honestly.)
- **Voice profile enforced by script**: banned vocabulary and em-dash scans in
  `lint_prose.py`; tone judgment in the humanize pass.
- **Opinion labeling**: sentences without claim support get a span, get cut,
  or get marked as interpretation.

---

## 8. The paper spec

`paper.md` (plus `figures/`, optional `paper.docx`), in order:

1. **TL;DR** (<= 150 words) and the **page-one figure** with takeaway caption.
2. **Introduction** (CARS), ending with the chapter map.
3. **Guided-tour chapters** in dependency order: topic-sentence opening, at
   least one figure, concept pages by reference, code via `annotated_code`,
   closing "what you can now do" line.
4. **The cookbook**: numbered reproducible step sequences; every step a
   command/action plus expected result (span-backed or marked unverified).
5. **Glossary**, generated from the model.
6. **Claims appendix**: every claim ID, text, source locators. Non-optional.
7. **Unverified appendix**: agent-proposed edges and kept interpretations.
8. **Attribution appendix**: every external asset with author, license,
   source URL. If this list and the figures disagree, the build fails (F-13).

---

## 9. Quality: the gate and the calibration

### 9.1 `grade.py` (the scored gate)

Start at 100, deduct by severity; the skill may not override the script:

| Sev | Finding | Deduction |
|---|---|---|
| P0 | Any F-01 (provenance) failure in a shipped figure | -100 |
| P0 | Claim coverage < 95% | -40 |
| P0 | A planted secret survives into spans or the paper | -100 |
| P0 | Page-one figure missing | -20 |
| P0 | External asset without verified license record or attribution mismatch (F-13) | -100 |
| P0 | A robots.txt violation or off-allowlist fetch in the audit trail | -100 |
| P1 | A screenshot without its URL + date stamp (F-14) | -10 |
| P1 | Any F-02..F-09 or F-14 unresolved at ship | -10 each |
| P1 | A chapter with no figure and no recorded reason | -5 each |
| P1 | Banned vocabulary / em dashes in shipped prose | -3 each |
| P2 | Confusion-time lints outstanding | -1 each |

Gates: **80 ships with warnings listed; 90 is the target; below 80 does not
ship.** A red grade cannot be pushed or delivered silently.

### 9.2 Critic calibration by seeded defects

`figlib/seeded_defects/` holds figures with known planted violations (default
palette, a label collision, a legend over data, an edge absent from a toy
model, a 7pt label), and `lint_prose.py` has a twin corpus of prose with
planted slop. **Gate: the figure critic catches >= 9/10 planted defects and
cites the correct rule IDs; the prose lints catch 10/10 of theirs.** Re-run
whenever a critic or rule changes.

---

## 10. Milestones

**M0 — Intake + trace + secret filter.** Three source types (git repo, PDF,
mixed folder), manifest + per-source traces. *Done when:* all three parse
with traces; 12 planted secrets yield 0 leaks into spans; re-running on
unchanged sources does zero re-parsing.

**M1 — Compile: the model with both rules enforced.** Extractors for one code
language, markdown/PDF sections, CSV schema; analyzer batching; merge +
review. *Done when:* on a real mid-size repo, model.json validates; 100% of
edges carry extractors; 100% of claims carry spans; 0 unresolved danglers; a
planted agent-proposed edge lands at confidence < 1.0.

**M2 — The figure system, calibrated.** style.py both modes, six recipes
(`architecture_box`, `dataflow`, `dependency_graph`, `pipeline_stages`,
`annotated_code`, `quantity`), figcheck.py, the critic, seeded defects.
*Done when:* critic catches >= 9/10 planted defects citing correct rule IDs;
provenance check rejects a hallucinated edge; same payload renders in both
modes; all six recipes pass F-01..F-14 on real model data.

**M2.5 — Autonomous acquisition, license-gated.** acquire.py (robots, rate
limits, cache, audit, budgets), ladder rungs 1-2, archive-on-fetch, license
gate vs Commons API, asset records, F-13/F-14 checks. *Done when:* demand-mode
request fetches a Commons image with API-verified license and auto
attribution; an image whose page claims CC but whose API metadata disagrees is
rejected; all-rights-reserved is rejected and converted to a figure request; a
screenshot ships framed with URL + date; audit shows 0 robots violations and
0 off-allowlist fetches across a 50-page seeded crawl; re-run fetches 0 pages.

**M3 — Plan + write with the leash on.** topology.py, planner, writer with
claim markers, claim-verifier, lint_prose.py, humanize pass. *Done when:*
chapter order respects the prerequisite graph (acyclic); claim coverage >=
95% on a full draft; 0 banned words, 0 em dashes; the verifier flags a
deliberately unsupported planted sentence.

**M4 — Ship a real paper.** Full pipeline on one real codebase, grade.py
wired. *Done when:* paper ships at grade >= 80 with page-one figure, every
chapter figured or excused, claims + unverified appendices emitted, and a
human files at least three concrete issues that become seeded defects or
rules.

**M5 — The compounding loop.** Incremental re-runs and supersession. *Done
when:* a one-file change re-ships with < 20% of full-run work (stage
timings); a contradicting edit produces a superseded claim correctly linked;
runs.jsonl reconstructs one claim's history across three runs.

**Definition of v0 done:** a stranger points cookbook-anything at a repo they
don't know, gets a paper they can verify sentence-by-sentence against the
claims appendix, with figures that contain no arrow the extractors didn't
find, in a visual style no one mistakes for default matplotlib. Then they
change a file and the paper updates without starting over.

---

## 11. Non-goals for v0

No web dashboard. No embeddings/hybrid search. No memory decay/consolidation
tiers. No video/audio or OCR-heavy ingestion. No image-generation figures.
No call-graph completeness claims. No multi-user. No login walls, paywalls,
CAPTCHAs, anti-bot arms race, or industrial crawling.

---

## 12. Honest seams

1. The critic loop is the novel, unproven part; the seeded-defect gate exists
   for exactly that reason, and M2 lands early on purpose.
2. Extractor depth is a treadmill: narrow-and-true over broad-and-flaky;
   confidence < 1.0 + the unverified appendix as the pressure valve.
3. Confusion-time lints are heuristics; real reader feedback is the signal.
4. PDF structure extraction is messy; v0 is text-layer with honest fallbacks.
5. License detection has a hard edge; the default is deny-and-redraw.
6. The web rots and fights back; archive-on-fetch handles rot, the trace
   records failures honestly.
7. Cost: bounds exist (batching, 3-iteration cap, incremental runs); the
   trace records per-stage cost.

---

## 13. After v0

v1: the reader model (per-audience confusion budgets and chapter depth).
v2: the critic's rule catalog grows from filed reader issues.
v3: hybrid search and the memory lifecycle when a model outgrows its index.
The compounding property is the point.

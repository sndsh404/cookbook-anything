# DESIGN.md, the authoring tool

## What this is

A small tool that turns a topic into a finished technical blog post: researched,
drafted in a chosen house style, illustrated with real-data figures, and
delivered as a Word document. It is a handful of plain scripts plus a set of
style profiles. It runs inside a Claude Code session on a Pro subscription , 
no model API, no per-token billing.

It is **not** a paper compiler, a knowledge engine, or an essay-generating
black box. It does the mechanical and research work around a post; the prose is
written in-session and stays the author's to sharpen.

## The core principle

There are two kinds of work in making a good post: the **gathering** (finding
images, plotting figures, taking screenshots, checking numbers, laying out a
frame) and the **writing** (the argument, the analogies, the voice). The
gathering is tedious and automatable. The writing is judgment.

This tool automates the gathering completely and does the writing as in-session
work, researched, drafted, and assembled in one pass, but the result is a
*first draft*. The author refines it. The tool never pretends a draft is final,
and it never invents the facts the draft rests on.

This split is the whole design. The previous iteration of this project ignored
it, it tried to generate finished, "verified" prose mechanically and produced
dressed-up file listings. The lesson, encoded here: a machine can gather and it
can draft, but the data must be real and the final voice must be the author's.

## Two firewalls of honesty

Everything the tool produces passes two tests.

**The data firewall.** Every number in a figure must come from real research
with a citable source. If no real number exists for a planned figure, the
figure is dropped, not faked. Charts are where a lie is invisible, a fabricated
bar looks identical to a real one, so this line is absolute. Sources go in the
reading list; they are real or they are not there.

**The form firewall.** Every figure and every paragraph passes the taste and
voice rules below before it ships. The tool has a locked house style (the
profile), a fixed recipe library instead of freeform plotting, and explicit
rules for what a good figure and good prose look like.

## The form rules

These are the design skills the tool encodes. They are applied to every figure
and every passage.

### Figure taste

- **Declare the read first.** Before drawing a figure, state in one sentence
  what the reader should take away from it. If you can't write that sentence,
  the figure has no reason to exist, cut it.
- **One idea per figure.** No dual axes, no rainbow palettes, no chart-junk. A
  figure that needs two takeaways is two figures.
- **Label directly.** Put labels on the lines and bars, not in a legend the eye
  has to hunt through, wherever the layout allows.
- **The caption is the takeaway, not the axes.** "Loss falls predictably as
  tokens grow," not "loss versus tokens." The caption tells the reader what to
  conclude.
- **No defaults.** The profile sets line weights, palette, and fonts. Shipping
  raw matplotlib defaults is a tell of no care taken.
- **Real data, always.** (The data firewall, restated, because it is also a
  taste rule: a figure's job is to show the truth at a glance.)

### Voice

- **Avoid the tells of machine writing.** Overused dashes, "it's not just X,
  it's Y" constructions, hollow throat-clearing ("it's important to note
  that"), sterile hedging, and bullet lists where prose belongs. These read as
  filler.
- **Plain and confident.** Short concrete sentences over long abstract ones.
  Say the thing.
- **Analogies that do work.** A good analogy carries an idea the reader didn't
  have; a decorative one wastes a sentence. Strong technical writing leans on
  this, for example a tractor that won't take a part, a desk and a filing
  cabinet, professors and a stadium of students; match the kind and frequency of
  analogy in the source or profile chosen for this run.
- **Sterile is also slop.** Stripping all personality to sound "professional"
  is its own failure. The goal is a real human voice, not a neutral one.

### Structure

- **Long and thorough by default.** Match the length and depth of the source or
  profile chosen for this run, long and thorough by default, roughly 4,000 to
  8,000+ words. The scaffold carries more sections than a short piece, and every
  section is fully developed prose, not a summary or a stub. The length is
  earned by carrying each idea all the way, never by padding: if a passage is
  filler, cut it, and if a section is thin, develop it rather than pad it.
- **Open with a hook.** An analogy, a surprising fact, or a concrete problem , 
  whatever the chosen profile specifies. The first paragraph earns the rest.
- **One concept per section, walked in order.** Depth on a few ideas beats a
  shallow list of many.
- **Topic sentences carry the section.** A reader skimming the first line of
  each paragraph should get the argument.
- **Close with a reading list.** A short list of real sources at the end , 
  never inline, per-sentence citations. This follows the source or profile
  chosen for this run and is a deliberate rejection of the heavy citation
  machinery of the old project.

## The pipeline

```
topic + profile
  -> research real numbers (web search)
  -> render figures from that data        (figures/, render.py)
  -> draft the prose in the profile style  (in-session)
  -> fetch license-clean images if visual  (fetch_images.py)
  -> fill the reading list with real sources
  -> assemble markdown + figures + images
  -> convert to .docx                      (pandoc)
```

One command in (`make_post.py "topic" --profile <name>`), one Word file out.

## Style profiles

A profile is a `.toml` file in `profiles/`. It describes *how a post in this
style is shaped and how it looks*, opening move, section flow, close, heading
case, fonts, palette, figure look (clean or hand-drawn), never *what it says*.
Missing fields fall back to a calm baseline: monospace body, lowercase
headings, italic one-line captions. No profile is the canonical or reference
style; each is just one selectable option, and the active style is always the
source or profile chosen for the current run, a site, a profile name, or a
profile built from a site, never a fixed author or a single reference post.

Profiles can be hand-written or learned from a site: `fetch_site.py` archives
posts (robots-respecting), and `build_profile.py` measures the mechanical
signals (heading case, section count, figures per post, caption style) into a
profile skeleton. The boundary holds: **style is learned from anyone; content
and figures are only ever the author's own or license-clean.** The tool never
near-copies a source post with words swapped.

## The scripts

- `make_post.py`, the orchestrator; topic in, .docx out.
- `scaffold.py`, lays the styled frame (headings, figure and section slots).
- `style.py` + `profiles/`, load and apply a style profile.
- `figures/data.py`, exact, data-driven recipes (line_family, valley,
  scatter_diagonal, bars). Plot only what they're given.
- `figures/diagrams.py`, conceptual diagrams (boxes_arrows, memory_ladder,
  pipeline); deliberately simple, easy to finish by eye.
- `figures/math.py`, render an equation cleanly.
- `render.py`, render one figure from a spec file, no Python needed.
- `fetch_images.py`, license-clean image candidates with attribution.
- `screenshot.py`, a clean, framed terminal screenshot for code posts.
- `numbercheck.py`, pull the load-bearing numbers out of a draft into a
  checklist to verify (numbers only; leaves prose untouched).
- `fetch_site.py` + `build_profile.py`, learn a style profile from a site.

## What this tool is deliberately NOT

- Not a compiler, not a knowledge-model, not a swarm, no milestones.
- No per-sentence citations, no claims appendix, no unverified appendix, no
  grade gate.
- No model API, no `ANTHROPIC_API_KEY`, no autowriter that bills per run.
- Not large. If the design starts growing past a handful of small scripts, stop
 , sprawl is the failure mode this project was built in reaction to.

## Hard rules, in one place

1. Real researched data only; drop a figure rather than fake it.
2. Draft in-session; never add a paid-API autowriter or set a key.
3. The author owns the final voice; the tool delivers a first draft.
4. Reading-list sources at the end; never inline per-sentence citations.
5. Learn style from anyone; copy content and figures only from the author's
   own work or license-clean sources.
6. Long and thorough by default: match the length and depth of the source or
   profile chosen for this run, roughly 4,000 to 8,000+ words, more sections,
   each fully developed, never padded.
7. Stay small.

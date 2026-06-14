---
name: authoring-assistant
description: Turn a single topic into a finished, figure-rich technical blog post in a chosen house style, output as a Word .docx. Use when the user gives a topic (or a topic plus a style/profile name) and wants the post researched, drafted, illustrated, and assembled. Handles the mechanical work, style scaffold, figures from real data, license-clean images, terminal screenshots, a finished .docx, and writes the prose in-session. Never fabricates figure data and never calls a paid model API.
---

# authoring-assistant

A skill for turning a topic into a complete technical blog post: researched,
drafted in a chosen style, illustrated with real-data figures, and delivered as
a Word document. It lives in `authoring/` and runs on the user's Claude Pro
subscription, no API key, no per-token billing.

## When to use this

The user gives a topic. That is the trigger. Examples: "why most projects are a
waste," "how flash attention saves memory," "what RISC-V changes about chip
ownership." Optionally they name a style profile (`layers`, `chinchilla`,
`clean`, `taste`, `humanizer`, `writingpaper`, `sketch`, or one built from a
site). If they don't, default to `layers`.

The user only has to give the topic. Everything below is your job, not theirs.

## The one rule that defines this skill

**You gather, research, illustrate, and draft. The post comes out written, not
slotted, but it is a first draft for the user to sharpen, and you never invent
data.** Two hard lines, both learned the hard way:

1. **Real data only.** A figure may only show numbers you actually researched
   and can cite. If you cannot find a real number for a figure, leave that
   figure out. Never fill a chart with plausible-looking invented numbers, a
   fabricated figure is worse than no figure.
2. **No paid autopilot.** Do the research and the writing yourself, in this
   session, using web search. Do not add code that calls a model API, and never
   set `ANTHROPIC_API_KEY`. The writing is in-session work on the subscription,
   not a billed script.

## The workflow

Given a topic (and optional profile), run this end to end:

1. **Pick the profile.** Use the named one, or `layers` by default. The profile
   sets structure (opening move, section flow, close), heading case, fonts,
   palette, and figure look. Read it with `style.py`.

2. **Research real numbers.** Web-search for citable figures worth charting on
   this topic, rates, benchmarks, costs, growth, counts, comparisons. Keep
   only numbers you can attribute to a real source. Note the source for each.

3. **Build the figures from that data.** Write the researched numbers into the
   spec files and render with the recipes in `figures/` (line_family, valley,
   scatter_diagonal, bars; boxes_arrows, memory_ladder, pipeline; equation for
   math). One idea per figure. If a planned figure has no real data, drop it.

4. **Write the prose.** Fill every section with real first-draft prose in the
   profile's style, opening hook, one concept per section walked in order,
   topic sentences that carry their paragraph. Apply the voice discipline in
   DESIGN.md (no AI tells, plain confident prose, analogies that do work).
   Write a real one-line takeaway caption under each figure.

5. **Images, only when they help.** For concrete subjects, fetch license-clean
   images with `fetch_images.py` (Wikimedia Commons + Openverse, free licenses
   only, attribution included). For abstract subjects, skip images, the search
   returns junk. Default to no images unless the topic is visual.

6. **Fill the sources.** Put the real sources you researched into the
   reading-list section at the end. A reading list, never inline per-sentence
   citations.

7. **Assemble and convert.** Stitch prose + figures + images into markdown,
   then convert to `.docx` with pandoc (install via winget if missing). Give
   the user the `.docx` path.

## What you produce

A finished, readable first-draft post in a Word file, with real figures, real
sources, and the chosen house style, for the user to refine. Their voice and
final polish stay theirs; you get them a complete, honest starting draft in one
step.

## What this skill never does

- Never fabricates figure data, statistics, or sources.
- Never copies another site's actual sentences or specific figures; it may
  learn *style* from anyone, but published prose and figures are original.
- Never adds per-sentence citations, a claims appendix, a grade gate, a
  knowledge-model, milestones, or a compiler. This is a small tool; keep it
  small.
- Never calls a paid model API or sets `ANTHROPIC_API_KEY`.

## The scripts

`make_post.py` (orchestrator), `scaffold.py` (style frame), `figures/` +
`render.py` (figures from data), `fetch_images.py` (license-clean images),
`screenshot.py` (terminal shots), `numbercheck.py` (load-bearing-number
checklist), `fetch_site.py` + `build_profile.py` (learn a style from a site),
`style.py` + `profiles/` (the style profiles). See DESIGN.md for how they fit
together and CLAUDE.md for the standing instructions.

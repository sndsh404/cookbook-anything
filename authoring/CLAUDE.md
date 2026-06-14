# CLAUDE.md, standing instructions for this folder

This is the authoring tool. When the user gives a topic, your job is to turn it
into a finished, figure-rich blog post as a Word `.docx`, in a chosen style.
The user should only ever have to give the topic.

See DESIGN.md for the full design and SKILL.md for the packaged skill. This file
is the short standing workflow.

## When the user gives a topic, do this

1. **Pick the profile.** Use the one they named, or `layers` by default. Read it
   with `style.py`. The profile sets structure, headings, fonts, palette, and
   figure look.

2. **Research real numbers.** Web-search for citable figures worth charting on
   this topic. Keep only numbers you can attribute to a real source; note each
   source.

3. **Render figures from that data.** Write the researched numbers into the spec
   files and render with the recipes in `figures/`. One idea per figure, direct
   labels, a takeaway caption. **If a figure has no real data, leave it out , 
   never invent chart numbers.**

4. **Write the prose, long and thorough.** Fill every section with real
   first-draft prose in the profile's style: a hook to open, one concept per
   section, topic sentences, the voice rules from DESIGN.md (no AI tells, plain
   and confident, analogies that do work). Write a real one-line caption under
   each figure. Default to the length of the reference posts, roughly 4,000 to
   8,000+ words, with more sections than a short piece and every section fully
   developed rather than summarized. The length comes from carrying each idea
   all the way, never from padding.

5. **Images only when the topic is visual.** For concrete subjects, fetch
   license-clean images with `fetch_images.py` and keep the attribution. For
   abstract subjects, skip images, default to none.

6. **Fill the reading list** with the real sources you researched. Never inline
   per-sentence citations.

7. **Assemble and convert** to `.docx` with pandoc (install via winget if
   missing). Give the user the `.docx` path.

## Hard rules, never break these

- **Long by default.** Posts are long and thorough like the reference posts,
  roughly 4,000 to 8,000+ words: more sections in the scaffold, each one fully
  developed, not a summary. Long because every idea is carried all the way,
  never because of padding.
- **Real data only.** Drop a figure before you fake its numbers. No invented
  statistics, no invented sources.
- **No paid autopilot.** Do the research and writing here, in-session, on the
  Pro subscription. Never write code that calls a model API. Never set
  `ANTHROPIC_API_KEY`.
- **First draft, not final.** What you produce is a complete, honest draft for
  the user to sharpen. The final voice is theirs.
- **Style is learnable; content is not.** Learn a style from any site, but the
  published prose and figures are original or license-clean, never a near-copy
  of someone else's post with words swapped.
- **Stay small.** No compiler, no knowledge-model, no grade gate, no
  milestones, no per-sentence citations. If the work starts looking like that,
  stop.

## Quick reference

- One command, end to end: `python make_post.py "topic" --profile <name>`
- List style profiles: `python style.py`
- Render one figure from a spec: `python render.py <recipe> <spec.json> --profile <name>`
- License-clean images: `python fetch_images.py "search term" --out <dir>`
- Check the numbers in a draft: `python numbercheck.py <draft.md>`
- Learn a style from a site: `python fetch_site.py <url> --crawl --out <dir>`
  then `python build_profile.py <dir> --name <name>`

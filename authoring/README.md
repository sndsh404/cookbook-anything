# authoring

An authoring assistant for long-form technical blog posts. It does the boring
gathering and scaffolding so you can focus on the writing. **You stay the
author.** The tool gathers assets, renders figures, and lays out a scaffold in
a style you choose. It never writes the essay for you and never invents data.

This lives in the same repo as `cookbook-anything` but shares nothing with it:
no compiler, no model-of-the-repo, no per-sentence citations, no claims
appendix, no grade gate, no milestones. Just a handful of small scripts plus a
style/profile config.

## The keystone: clone a style, not its content

Point the tool at **any** site as inspiration. It builds a *style profile* from
that site (structure, voice, pacing, headings, formatting, the kinds of figures
and the layout). Then you give it a **different topic**, and the scaffold comes
out matching that site's style as tightly as possible.

The line is firm: **style is cloned, content is not.** Per post the only new
things are the words (a new topic means new sentences and facts) and the
figures/images (rendered fresh, or license-clean with attribution). The tool
never copies the source site's actual sentences and never reproduces its
specific figures or images.

## How it runs (no model API)

Nothing here calls an LLM API, and `ANTHROPIC_API_KEY` must stay unset. The work
splits cleanly:

- **Deterministic scripts** (run anytime, no model): fetch images, render
  figures from a spec, grab terminal screenshots, extract numbers from a draft,
  fetch a site to local markdown, extract a profile skeleton.
- **In-session steps** (you + Claude in a session, using web search, no API):
  draft the scaffold for the new topic, write the figure specs from your data,
  write the voice notes in a profile, fact-check the extracted numbers.

## The pieces

| Script | Does | You then |
|---|---|---|
| `profiles/*.toml` | named, pickable styles (the two posts, the design files, any fetched site) | pick one per post |
| `style.py` | loads a profile, applies the matplotlib look (clean or xkcd) | - |
| `figures/` | generic recipes (line family, valley, scatter+diagonal, bars, boxes-arrows, memory ladder, pipeline, mathtext) | feed real data, fill the caption |
| `fetch_images.py` | license-clean candidates from Wikimedia Commons + Openverse, with attribution sidecars | pick which to place |
| `screenshot.py` | a framed, trimmed screenshot of real terminal output | drop into a code walkthrough |
| `numbercheck.py` | pulls only the load-bearing numbers/specs from your draft into a checklist | fix what the in-session check flags |
| `fetch_site.py` | robots-respecting fetch of any site's posts to clean markdown | read the archive |
| `build_profile.py` | extracts a style skeleton from fetched posts | fill the voice notes, save as a profile |
| `scaffold.py` | a styled scaffold for a new topic in a chosen style (headings, figure/image slots, reading-list section) | write the prose |

## A post, start to finish

1. You hand in: a topic, your notes/outline, your data (CSV or dict), your
   source list, and a chosen style profile. For a code post, the repo + commands.
2. `scaffold.py` lays the frame in that style: section headings, figure slots
   with captions-to-write, image slots, a reading-list section. (You do not get
   an essay.)
3. The scripts fetch image candidates, render figures from your data, grab
   screenshots. You pick images and approve figures.
4. You write the prose.
5. `numbercheck.py` pulls the load-bearing numbers; the in-session check flags any
   that are wrong. The report is a side file, never attached to the post.
6. Final assembly: a styled post (markdown + the figures and chosen images),
   ending with your reading-list sources. No inline citations.

## What it never does

Invent numbers or data. Call a model API. Copy a source site's sentences or
lift its specific figures/images. Footnote every clause. Grow into a compiler.

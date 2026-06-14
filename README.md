# authoring

An authoring assistant for long-form technical blog posts. It does the
gathering and scaffolding (style profiles, figures from your data, license-clean
images, terminal screenshots, a number checklist) so you write the prose. It
never writes the essay, never invents data, and calls no model API. Everything
lives in `authoring/`.

## Scripts

Run from the `authoring/` directory.

- **Scaffold a post** in a chosen style:
  `python scaffold.py "<topic>" --profile <name> --out draft.md`
  Profiles: `layers`, `chinchilla`, `clean`, `sketch`, `taste`, `writingpaper`,
  `humanizer` (or any you build from a site). `python style.py` lists them.

- **Render a figure** from your data:
  `python render.py <recipe> <spec.json> --profile <name> --out fig.png --caption "..."`
  Recipes: `line_family`, `valley`, `scatter_diagonal`, `bars`, `boxes_arrows`,
  `memory_ladder`, `pipeline`, `equation`. It plots exactly what the spec
  contains.

- **Fetch license-clean images**:
  `python fetch_images.py "<search term>" --out assets/<name> --n 6`
  Wikimedia Commons + Openverse only; keeps PD/CC0/CC-BY/CC-BY-SA; writes an
  attribution sidecar per image.

- **Terminal screenshot** of real output:
  `python screenshot.py "<command>" --out shot.png --tail 20 --caption "..."`

- **Number checklist** from a draft (numbers/specs only, never the prose):
  `python numbercheck.py draft.md --out number-check.md`

- **Learn a style from any site**:
  `python fetch_site.py <url> --crawl --out archive/<name>`
  then `python build_profile.py archive/<name> --name <name>`
  Fetches posts (robots-respecting) to local markdown and writes a profile
  skeleton; you fill the `[voice]` notes. Style is learned; content is not
  copied.

## Requires

Python 3.11+ and matplotlib. No other dependencies.

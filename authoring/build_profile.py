"""build_profile.py - extract a style skeleton from fetched posts.

Reads the markdown posts in an archive folder (from fetch_site.py) and measures
the MECHANICAL style signals it can: heading case, typical section count,
figures per post, caption style, opening shape, average paragraph length. It
writes a profile .toml skeleton with those filled in and the [voice] notes left
blank - those are yours (or the in-session step's) to write after reading the
posts. Style is what we clone; the words stay the source's.

    python build_profile.py archive/example --name example

Then read the posts, fill the [voice] notes, and the profile is selectable.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _strip_front(md: str) -> str:
    return re.sub(r"^---.*?---\n", "", md, flags=re.S)


def analyze(posts: list[str]) -> dict:
    headings, sections, figures, paras, openings = [], [], [], [], []
    caption_italic = 0
    caption_total = 0
    for md in posts:
        body = _strip_front(md)
        hs = re.findall(r"^#{1,6}\s+(.+)$", body, re.M)
        headings += hs
        sections.append(len([h for h in hs]))
        figures.append(len(re.findall(r"!\[", body)))
        # captions: italic single lines often follow images
        for line in body.splitlines():
            t = line.strip()
            if t.startswith("*") and t.endswith("*") and len(t) < 160 and len(t) > 3:
                caption_italic += 1
            if t.startswith("*") and t.endswith("*"):
                caption_total += 1
        for p in body.split("\n\n"):
            p = p.strip()
            if p and not p.startswith(("#", "!", "-", "*", "```")):
                paras.append(len(p.split()))
        # opening: the first real paragraph
        first = next((p.strip() for p in body.split("\n\n")
                      if p.strip() and not p.strip().startswith(("#", "!", "```"))), "")
        openings.append(first[:200])

    # heading case
    def case_of(h: str) -> str:
        words = [w for w in re.findall(r"[A-Za-z]+", h)]
        if not words:
            return "lower"
        if all(w.islower() for w in words):
            return "lower"
        if words[0][:1].isupper() and all(w.islower() for w in words[1:]):
            return "sentence"
        return "title"
    cases = [case_of(h) for h in headings] or ["lower"]
    heading_case = max(set(cases), key=cases.count)

    avg_par = round(sum(paras) / len(paras)) if paras else 60
    rhythm = ("short, plain" if avg_par < 45 else
              "short to medium" if avg_par < 80 else "medium to long")

    return {
        "typical_sections": round(sum(sections) / len(sections)) if sections else 6,
        "figures_per_post": round(sum(figures) / len(figures)) if figures else 3,
        "heading_case": heading_case,
        "caption_style": "italic" if caption_italic >= max(caption_total, 1) * 0.5 else "plain",
        "rhythm": rhythm,
        "opening_sample": openings[0] if openings else "",
        "n_posts": len(posts),
    }


def skeleton(name: str, src: str, a: dict) -> str:
    src = src.replace("\\", "/")                 # backslashes are TOML escapes
    sample = a["opening_sample"][:140].replace("'", " ")
    return f'''name = "{name}"
source = "{src}"
kind = "site"

[structure]
# measured from the fetched posts; adjust if you disagree
opening = "analogy"            # GUESS - set to analogy | surprising-fact | from-scratch | problem | definition
section_flow = "concept-walk"  # GUESS - set to concept-walk | build-derive-compare | problem-solution | survey
close = "reading-list"         # GUESS - check how the source ends
heading_case = "{a['heading_case']}"
typical_sections = {a['typical_sections']}
figures_per_post = {a['figures_per_post']}

[voice]
# TODO (in-session, after reading the posts): fill these in your own words.
# Measured paragraph rhythm: {a['rhythm']} (avg paragraph length).
# First paragraph of the first post, for reference:
#   {sample}
person = ""                    # first-plural | first-singular | second | third
sentence_rhythm = "{a['rhythm']}"
analogies = ""                 # heavy | light | none
tone = ""
notes = ""

[type]
body_font = "monospace"
heading_font = "monospace"

[figures]
mode = "clean"
background = "#fbfaf8"
ink = "#1a1a2e"
palette = ["#e63946", "#2a9d8f", "#e9a23b", "#9aa5b1", "#1a1a2e"]
line_weight = 2.0
grid = "light-dotted"
caption_style = "{a['caption_style']}"
font_min_pt = 9
'''


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2

    def arg(name, d):
        return sys.argv[sys.argv.index(f"--{name}") + 1] if f"--{name}" in sys.argv else d

    archive = Path(args[0])
    name = arg("name", archive.name)
    posts = [p.read_text(encoding="utf-8") for p in sorted(archive.glob("*.md"))]
    if not posts:
        print(f"no .md posts in {archive}. run fetch_site.py first.")
        return 1
    a = analyze(posts)
    out = Path(__file__).resolve().parent / "profiles" / f"{name}.toml"
    out.write_text(skeleton(name, str(archive), a), encoding="utf-8")
    print(f"wrote {out} from {a['n_posts']} post(s):")
    print(f"  headings={a['heading_case']}  sections~{a['typical_sections']}  "
          f"figures~{a['figures_per_post']}  captions={a['caption_style']}  rhythm={a['rhythm']}")
    print("  [voice] notes left blank - read the posts and fill them in your words.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

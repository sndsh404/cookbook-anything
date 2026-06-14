"""scaffold.py - lay out an empty, styled frame for a NEW topic in a chosen
style. Section headings, figure slots with captions-to-write, image slots, and
a reading-list section - shaped by the profile (its opening move, section flow,
close, heading case, and how many figures it tends to use). You write the prose.

    python scaffold.py "how GPUs schedule warps" --profile layers --out draft.md

The scaffold is a frame, not an essay. It never writes your sentences and never
invents data. The figure slots tell you which recipe to feed your numbers to.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from style import load_profile

OPENING_PROMPT = {
    "analogy": "Open with a concrete, everyday analogy for {topic}, then name the through-line it reveals. (The reader should feel the idea before the abstraction.)",
    "surprising-fact": "Open with the surprising result about {topic}, stated plainly. Then promise to build the smallest thing that shows it.",
    "from-scratch": "Open by setting up the smallest version of {topic} you can build from scratch, and what you'll derive from it.",
    "problem": "Open with the concrete problem {topic} solves and what breaks without it.",
    "definition": "Open by naming {topic} and its one-line job, then why it matters.",
}

FLOW_SECTIONS = {
    "concept-walk": ["the core idea", "how it works", "where it bites", "a worked example", "the trade-off"],
    "build-derive-compare": ["build the smallest version", "derive its behavior", "measure it", "compare two approaches", "what scales and what doesn't"],
    "problem-solution": ["the problem", "why the obvious fix fails", "the approach", "how it works", "limits"],
    "survey": ["the landscape", "approach one", "approach two", "approach three", "how to choose"],
}

CLOSE_PROMPT = {
    "reading-list": ("sources", "A short reading list - the few works this draws on. Plain links, no inline citations."),
    "your-turn": ("your turn", "A concrete thing the reader can now go try, and where to start."),
    "summary": ("takeaways", "Three or four sentences: what to remember."),
    "call-to-action": ("what to do next", "One concrete next step for the reader."),
}

FIG_SUGGEST = {
    "build-derive-compare": ["line_family", "valley", "scatter_diagonal", "bars", "equation"],
    "concept-walk": ["boxes_arrows", "memory_ladder", "pipeline", "bars", "line_family"],
    "problem-solution": ["pipeline", "bars", "boxes_arrows", "line_family"],
    "survey": ["bars", "boxes_arrows", "line_family", "scatter_diagonal"],
}


def case(text: str, how: str) -> str:
    if how == "lower":
        return text.lower()
    if how == "sentence":
        return text[:1].upper() + text[1:]
    if how == "title":
        return text.title()
    return text


def build(topic: str, prof: dict) -> str:
    st = prof["structure"]
    hc = st["heading_case"]
    flow = st["section_flow"]
    sections = FLOW_SECTIONS.get(flow, FLOW_SECTIONS["concept-walk"])
    n_sections = max(3, min(st.get("typical_sections", 6), len(sections) + 2))
    n_figs = st.get("figures_per_post", 4)
    fig_recipes = FIG_SUGGEST.get(flow, FIG_SUGGEST["concept-walk"])
    close_h, close_note = CLOSE_PROMPT.get(st["close"], CLOSE_PROMPT["reading-list"])

    out = []
    out.append(f"# {case(topic, hc)}\n")
    out.append(f"<!-- scaffold: style='{prof['name']}' ({prof['source']}). "
               f"voice: {prof['voice'].get('tone','')}; person {prof['voice'].get('person','')}; "
               f"analogies {prof['voice'].get('analogies','')}. You write the prose. -->\n")
    out.append(f"_{date.today().isoformat()} / #essays_\n")

    # opening
    out.append(f"## {case('opening', hc)}\n")
    out.append(f"<!-- {OPENING_PROMPT.get(st['opening'], OPENING_PROMPT['problem']).format(topic=topic)} -->\n")
    out.append("(write the hook here)\n")

    # body sections, with figure/image slots distributed through them
    body = sections[: n_sections]
    fig_at = set()
    for k in range(n_figs):
        fig_at.add(min(k * max(len(body) // max(n_figs, 1), 1), len(body) - 1))
    fi = 0
    for i, sec in enumerate(body):
        out.append(f"## {case(sec, hc)}\n")
        out.append("(write this section)\n")
        if i in fig_at and fi < n_figs:
            recipe = fig_recipes[fi % len(fig_recipes)]
            out.append(f"[FIGURE {fi+1}: recipe `{recipe}` - feed it your data: "
                       f"`python render.py {recipe} <spec.json> --profile {prof['name']} "
                       f"--out fig{fi+1}.png --caption \"...\"`]")
            out.append("*caption to write: the one takeaway of this figure*\n")
            fi += 1
        if i == 1:
            out.append("[IMAGE slot: `python fetch_images.py \"<search term>\" --out assets/img"
                       f"{i}` then pick one; attribution goes under it]\n")

    # close
    out.append(f"## {case(close_h, hc)}\n")
    out.append(f"<!-- {close_note} -->\n")
    out.append("- source one\n- source two\n")
    return "\n".join(out)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    topic = args[0]

    def arg(name, d):
        return sys.argv[sys.argv.index(f"--{name}") + 1] if f"--{name}" in sys.argv else d

    profile = arg("profile", "clean")
    out = Path(arg("out", "draft.md"))
    prof = load_profile(profile)
    out.write_text(build(topic, prof), encoding="utf-8")
    print(f"scaffolded '{topic}' in style '{profile}' -> {out}")
    print(f"  opening={prof['structure']['opening']} flow={prof['structure']['section_flow']} "
          f"close={prof['structure']['close']} headings={prof['structure']['heading_case']}")
    print("  the frame is yours to write into; figure slots name the recipe to feed your data to.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

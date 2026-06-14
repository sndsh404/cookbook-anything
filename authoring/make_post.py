"""make_post.py - assemble a styled post scaffold into a Word .docx.

    python make_post.py "how flash attention saves memory" --profile layers

It runs the mechanical pipeline around a post and leaves the judgment to you:

  1. scaffolds a long, styled frame for the topic (scaffold.py),
  2. renders every figure that has REAL data in <postdir>/specs/, and drops any
     figure that does not - it never invents chart numbers,
  3. embeds license-clean images, only when you ask for them (visual topics),
  4. assembles the markdown with the figures and images in place,
  5. converts to .docx with pandoc (installing it via winget if missing).

What it does NOT do: write your prose, or fabricate figure data. The section
prose slots and the figure caption slots are left for you to fill in-session.
No model API is called; ANTHROPIC_API_KEY stays unset.

Real-data figures: research the numbers, then write one spec file per figure
into <postdir>/specs/ before assembling. A figure slot named `figN` with recipe
`R` reads `specs/figN.json` (or `specs/figN.txt` for an `equation`). The spec
shapes are documented in figures/data.py, figures/diagrams.py, figures/math.py.
Run with no specs first to see which slots exist and what recipe each wants;
fill the ones you have real data for and re-run. Slots without data are dropped.

    python make_post.py "topic" [--profile layers] [--images N] \
        [--out-dir posts] [--specs DIR]

Images are off by default. Pass --images N only for visual topics; for abstract
topics leave them off (the search returns junk).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fetch_images import fetch
from figures.data import bars, line_family, scatter_diagonal, valley
from figures.diagrams import boxes_arrows, memory_ladder, pipeline
from figures.math import equation
from scaffold import build
from style import load_profile

RECIPES = {
    "line_family": line_family,
    "valley": valley,
    "scatter_diagonal": scatter_diagonal,
    "bars": bars,
    "boxes_arrows": boxes_arrows,
    "memory_ladder": memory_ladder,
    "pipeline": pipeline,
}

FIG_LINE = re.compile(r"^\[FIGURE (\d+): recipe `([^`]+)`")
CAPTION_LINE = re.compile(r"^\*caption to write")
IMAGE_LINE = re.compile(r"^\[IMAGE slot:")


def arg(name: str, default: str | None = None) -> str | None:
    flag = f"--{name}"
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def slugify(topic: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return s or "post"


def ensure_pandoc() -> str:
    """Return the pandoc executable, installing it via winget if missing."""
    exe = shutil.which("pandoc")
    if exe:
        return exe
    print("pandoc not found - trying to install it via winget...")
    try:
        subprocess.run(
            ["winget", "install", "--id", "JohnMacFarlane.Pandoc", "-e",
             "--source", "winget", "--accept-package-agreements",
             "--accept-source-agreements"],
            check=True,
        )
    except FileNotFoundError:
        raise SystemExit(
            "pandoc is missing and winget is not available. Install pandoc from "
            "https://pandoc.org/installing.html and re-run.")
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"winget could not install pandoc (exit {e.returncode}). "
                         "Install it manually from https://pandoc.org/installing.html")
    exe = shutil.which("pandoc")
    if not exe:
        for cand in (Path.home() / "AppData/Local/Pandoc/pandoc.exe",
                     Path("C:/Program Files/Pandoc/pandoc.exe")):
            if cand.exists():
                return str(cand)
        raise SystemExit("pandoc installed but not found on PATH - re-run this command.")
    return exe


def _load_spec(path: Path, recipe: str):
    if recipe == "equation":
        return path.read_text(encoding="utf-8").strip()
    spec = json.loads(path.read_text(encoding="utf-8"))
    # JSON arrays-of-pairs become the tuples the data recipes expect.
    for key in ("series", "curves"):
        if key in spec:
            spec[key] = {k: tuple(v) for k, v in spec[key].items()}
    return spec


def render_figure(num: int, recipe: str, spec_path: Path, assets_dir: Path,
                  profile: str) -> Path:
    """Render figure `num` from its real-data spec. Raises if the recipe is
    unknown. The caller only invokes this once it knows the spec exists."""
    out = assets_dir / f"fig{num}.png"
    if recipe == "equation":
        equation(_load_spec(spec_path, recipe), profile=profile, out=str(out))
    elif recipe in RECIPES:
        RECIPES[recipe](_load_spec(spec_path, recipe), profile=profile, out=str(out))
    else:
        raise SystemExit(f"figure {num}: unknown recipe '{recipe}'")
    return out


def image_block(saved: list[dict], enabled: bool) -> str | None:
    """Markdown for the fetched images, each with its attribution under it.
    Returns None when the image slot should be dropped entirely."""
    if not enabled:
        return None
    if not saved:
        return ("*(images requested but no license-clean candidates found, or no "
                "network. Re-run, or drop one in by hand with attribution.)*")
    lines = []
    for c in saved:
        lines.append(f"![]({(Path('assets/img') / c['file']).as_posix()})")
        lines.append("")
        lines.append(f"*{c['attribution']}*")
        lines.append("")
    return "\n".join(lines).rstrip()


def assemble(frame: str, specs_dir: Path, assets_dir: Path, profile: str,
             saved_images: list[dict], images_enabled: bool):
    """Walk the scaffold frame; render and embed each figure that has real data,
    drop any figure that has none, and place images only when enabled. Prose and
    caption slots are left untouched. Returns (markdown, rendered, dropped)."""
    src = frame.splitlines()
    out: list[str] = []
    rendered: list[tuple[int, str]] = []
    dropped: list[tuple[int, str, Path]] = []
    i = 0
    while i < len(src):
        line = src[i]
        m = FIG_LINE.match(line)
        if m:
            num, recipe = int(m.group(1)), m.group(2)
            ext = "txt" if recipe == "equation" else "json"
            spec_path = specs_dir / f"fig{num}.{ext}"
            if spec_path.exists():
                render_figure(num, recipe, spec_path, assets_dir, profile)
                rendered.append((num, recipe))
                out += ["", f"![](assets/fig{num}.png)", "",
                        f"*Figure {num}: write the one-line takeaway here*", ""]
            else:
                dropped.append((num, recipe, spec_path))
            # drop the scaffold's own "caption to write" line in both cases
            if i + 1 < len(src) and CAPTION_LINE.match(src[i + 1]):
                i += 1
            i += 1
            continue
        if IMAGE_LINE.match(line):
            block = image_block(saved_images, images_enabled)
            if block is not None:
                out += ["", block, ""]
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out) + "\n", rendered, dropped


def main() -> int:
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    flagged_values = set()
    for name in ("profile", "out-dir", "images", "specs"):
        v = arg(name)
        if v is not None:
            flagged_values.add(v)
    positional = [a for a in positional if a not in flagged_values]
    if not positional:
        print(__doc__)
        return 2

    topic = positional[0]
    profile = arg("profile", "layers")
    out_dir = Path(arg("out-dir", str(HERE / "posts")))
    n_images = int(arg("images", "0"))  # off by default; opt in for visual topics
    images_enabled = n_images > 0

    prof = load_profile(profile)  # validates the profile up front
    slug = slugify(topic)
    postdir = out_dir / slug
    assets = postdir / "assets"
    img_dir = assets / "img"
    specs_dir = Path(arg("specs", str(postdir / "specs")))
    for d in (postdir, assets, specs_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"== make_post: '{topic}' in style '{profile}' ==")
    print(f"   -> {postdir}")

    # 1. scaffold the long, styled frame (prose slots only; no prose written)
    frame = build(topic, prof)

    # 2. images: only when asked for (visual topics); off by default
    saved: list[dict] = []
    if images_enabled:
        print(f"-- fetching up to {n_images} license-clean image(s) for '{topic}'...")
        try:
            saved = fetch(topic, img_dir, n_images)
        except Exception as e:
            print(f"   image fetch failed ({e}); leaving the image slot empty")
        print(f"   got {len(saved)} image(s)")

    # 3. render real-data figures + assemble (figures with no data are dropped)
    print("-- rendering real-data figures and assembling markdown...")
    md, rendered, dropped = assemble(frame, specs_dir, assets, profile, saved,
                                     images_enabled)
    md_path = postdir / f"{slug}.md"
    md_path.write_text(md, encoding="utf-8")

    # 4. convert to .docx with pandoc (images embed into the file)
    pandoc = ensure_pandoc()
    docx_path = postdir / f"{slug}.docx"
    print("-- converting to .docx with pandoc...")
    subprocess.run([pandoc, md_path.name, "-o", docx_path.name],
                   cwd=str(postdir), check=True)

    print("\n== done ==")
    print(f"   figures rendered: {len(rendered)}"
          + (f"  ({', '.join('fig%d/%s' % (n, r) for n, r in rendered)})" if rendered else ""))
    if dropped:
        print(f"   figures dropped (no real data): {len(dropped)}")
        for num, recipe, sp in dropped:
            print(f"     - fig{num} ({recipe}): add real data at "
                  f"{sp.relative_to(postdir)} and re-run to include it")
    print(f"   images embedded:  {len(saved)}"
          + ("" if images_enabled else "  (off; pass --images N for visual topics)"))
    print(f"   markdown:         {md_path}")
    print(f"   WORD FILE:        {docx_path}")
    print("   prose and caption slots are left for you - write them in-session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

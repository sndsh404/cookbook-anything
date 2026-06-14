"""screenshot.py - a clean, framed screenshot of real terminal output.

Runs a command, captures its output, and renders it as a terminal-style image
(dark panel, monospace, a title bar with the command) so a code walkthrough can
show real output instead of pasted, reformatted text. Trim to the lines that
matter with --tail or --grep, and add a one-line caption.

    python screenshot.py "python render.py --help" --out shot.png --tail 20 \
        --caption "the figure recipes available"

It shows exactly what the command printed. It does not edit the output.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

BG = "#1e1e2e"
PANEL = "#11111b"
TEXT = "#cdd6f4"
DIM = "#6c7086"
DOTS = ["#f38ba8", "#f9e2af", "#a6e3a1"]


def run(cmd: str, cwd: str | None) -> str:
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           cwd=cwd, timeout=120)
        return (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return f"[command failed: {e}]"


def frame(output: str, cmd: str, out: Path, caption: str = "", tail: int = 0,
          grep: str = "") -> Path:
    lines = output.rstrip("\n").split("\n")
    if grep:
        lines = [ln for ln in lines if grep in ln] or lines
    if tail and len(lines) > tail:
        lines = lines[-tail:]
    lines = [ln[:110] for ln in lines]  # clip very long lines
    body = "\n".join(lines) if lines else "(no output)"

    n = max(len(lines), 1)
    width = max((len(ln) for ln in lines), default=20)
    fig_w = min(max(width * 0.085 + 1.0, 5.0), 12.0)
    fig_h = n * 0.26 + 1.1

    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    # panel
    ax.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                                boxstyle="round,pad=0.0,rounding_size=0.02",
                                facecolor=PANEL, edgecolor="#313244", linewidth=1.0))
    bar_y = 0.92
    for i, d in enumerate(DOTS):
        ax.plot(0.06 + i * 0.03, bar_y, "o", markersize=7, color=d)
    ax.text(0.5, bar_y, f"$ {cmd[:80]}", ha="center", va="center",
            color=DIM, family="monospace", fontsize=9)
    ax.text(0.05, bar_y - 0.07, body, ha="left", va="top", color=TEXT,
            family="monospace", fontsize=10, linespacing=1.35)
    if caption:
        fig.text(0.5, -0.01, caption, ha="center", va="top", fontsize=10,
                 fontstyle="italic", color="#444")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=BG, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]

    def arg(name, d):
        return sys.argv[sys.argv.index(f"--{name}") + 1] if f"--{name}" in sys.argv else d

    out = Path(arg("out", "screenshot.png"))
    caption = arg("caption", "")
    tail = int(arg("tail", "0"))
    grep = arg("grep", "")
    cwd = arg("cwd", None)
    output = run(cmd, cwd)
    p = frame(output, cmd, out, caption, tail, grep)
    print(f"framed {p} ({len(output.splitlines())} lines captured)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

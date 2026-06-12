"""screenshot_frame.py - screenshots are citation evidence, not decoration
(F-14): they render inside a browser-chrome frame stamped with the URL and
access date, at the minimal size that supports the point.

Usage: python figlib/screenshot_frame.py <image.png> <url> <out.png>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

from style import FigureContext, PALETTE, FILLS


def frame_screenshot(image_path: Path, url: str, out_path: Path,
                     accessed: str | None = None) -> dict:
    accessed = accessed or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    img = mpimg.imread(str(image_path))
    ih, iw = img.shape[0], img.shape[1]
    disp_w = 4.6  # minimal size that supports the point
    disp_h = disp_w * ih / iw
    bar_h, stamp_h = 0.34, 0.3
    fig_w, fig_h = disp_w + 0.3, disp_h + bar_h + stamp_h + 0.25

    with FigureContext("print"):
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.set_axis_off()
        ax.set_xlim(0, fig_w)
        ax.set_ylim(0, fig_h)
        x0, y0 = 0.15, stamp_h + 0.1
        # chrome bar with three window dots and the url
        ax.add_patch(FancyBboxPatch((x0, y0 + disp_h), disp_w, bar_h,
                                    boxstyle="round,pad=0.02,rounding_size=0.06",
                                    facecolor=FILLS["muted_fill"],
                                    edgecolor=PALETTE["muted"], linewidth=1.0))
        for k in range(3):
            ax.plot(x0 + 0.18 + k * 0.14, y0 + disp_h + bar_h / 2, "o",
                    markersize=4, color=PALETTE["muted"])
        ax.text(x0 + 0.62, y0 + disp_h + bar_h / 2, url[:70], fontsize=9,
                va="center", color=PALETTE["ink"])
        # the screenshot itself, bordered
        ax.imshow(img, extent=(x0, x0 + disp_w, y0, y0 + disp_h), aspect="auto", zorder=2)
        ax.add_patch(Rectangle((x0, y0), disp_w, disp_h, fill=False,
                               edgecolor=PALETTE["muted"], linewidth=1.0, zorder=3))
        # the evidence stamp
        ax.text(x0, 0.08, f"Source: {url[:80]}  ·  accessed {accessed}",
                fontsize=9, color=PALETTE["muted"])
        fig.savefig(out_path, metadata={"ca:kind": "screenshot", "ca:url": url,
                                        "ca:accessed": accessed})
        plt.close(fig)

    sidecar = {"kind": "screenshot", "url": url, "accessed": accessed,
               "png": out_path.name, "framed": True}
    out_path.with_suffix(".sidecar.json").write_text(json.dumps(sidecar, indent=1),
                                                     encoding="utf-8")
    return sidecar


if __name__ == "__main__":
    frame_screenshot(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))
    print(f"framed {sys.argv[3]}")

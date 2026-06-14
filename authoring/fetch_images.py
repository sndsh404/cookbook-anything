"""fetch_images.py - license-clean image candidates for a search term.

Searches Wikimedia Commons and Openverse (their public APIs only), keeps ONLY
clearly free licenses (public domain, CC0, CC-BY, CC-BY-SA), downloads the
candidates, and writes a sidecar per image with the title, author, license,
source URL, and the exact attribution line to place under it. It shows you a
few per search; it does not auto-place anything. It never scrapes random pages.

    python fetch_images.py "DDR5 module" --out assets/ddr5 --n 6

When in doubt about a license, it drops the image.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = "authoring-assistant/0.1 (personal blog tooling; contact: hiiamsandeshbhandari@gmail.com)"

# license codes/names we accept. Anything with NC or ND, or anything unclear,
# is dropped.
OPENVERSE_OK = {"cc0", "pdm", "by", "by-sa"}
COMMONS_OK_SUBSTR = ["public domain", "cc0", "cc by 4.0", "cc by-sa", "cc by 3.0",
                     "cc by 2.0", "cc by 1.0", "cc by-sa 4.0", "cc by-sa 3.0",
                     "cc by-sa 2.0", "attribution-sharealike", "attribution license"]
COMMONS_BAD_SUBSTR = ["nc", "nd", "noncommercial", "no derivatives", "fair use",
                      "all rights reserved", "copyright"]


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _get_json(url: str) -> dict:
    return json.loads(_get(url).decode("utf-8", "replace"))


def _strip_html(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", s or "").strip()


# ---------------------------------------------------------------- Commons

def search_commons(term: str, n: int) -> list[dict]:
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": term, "gsrnamespace": "6", "gsrlimit": str(n * 3),
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": "1000",
    })
    url = f"https://commons.wikimedia.org/w/api.php?{q}"
    try:
        data = _get_json(url)
    except Exception as e:
        print(f"  commons: request failed ({e})")
        return []
    out = []
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {}) or {}
        lic = _strip_html(meta.get("LicenseShortName", {}).get("value", ""))
        author = _strip_html(meta.get("Artist", {}).get("value", "")) or "unknown"
        lic_l = lic.lower()
        if any(b in lic_l for b in COMMONS_BAD_SUBSTR) and "public domain" not in lic_l:
            continue
        if not any(ok in lic_l for ok in COMMONS_OK_SUBSTR):
            continue
        out.append({
            "source": "Wikimedia Commons",
            "title": page.get("title", "").replace("File:", ""),
            "author": author,
            "license": lic,
            "page_url": info.get("descriptionurl", ""),
            "image_url": info.get("url", ""),
            # a ~1000px thumb to download as the candidate (full-res can be 20+MB)
            "thumb_url": info.get("thumburl", info.get("url", "")),
        })
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- Openverse

def search_openverse(term: str, n: int) -> list[dict]:
    q = urllib.parse.urlencode({
        "q": term, "license": "cc0,pdm,by,by-sa", "page_size": str(n),
        "mature": "false",
    })
    url = f"https://api.openverse.org/v1/images/?{q}"
    try:
        data = _get_json(url)
    except Exception as e:
        print(f"  openverse: request failed ({e})")
        return []
    out = []
    for r in data.get("results", []):
        code = (r.get("license") or "").lower()
        if code not in OPENVERSE_OK:
            continue
        ver = r.get("license_version", "")
        nice = {"cc0": "CC0", "pdm": "Public domain"}.get(
            code, f"CC {code.upper()} {ver}".strip())
        out.append({
            "source": "Openverse",
            "title": r.get("title", "") or "(untitled)",
            "author": r.get("creator", "") or "unknown",
            "license": nice,
            "page_url": r.get("foreign_landing_url", "") or r.get("url", ""),
            "image_url": r.get("url", ""),
        })
    return out


# ---------------------------------------------------------------- attribution

def attribution_line(c: dict) -> str:
    lic = c["license"]
    if lic.lower().startswith(("public domain", "cc0")):
        return f"{c['title']} ({lic}), via {c['source']}"
    # CC-BY / CC-BY-SA need author + license
    return f"\"{c['title']}\" by {c['author']} is licensed under {lic}, via {c['source']}"


def fetch(term: str, out_dir: Path, n: int) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cands = search_commons(term, n) + search_openverse(term, n)
    saved = []
    for i, c in enumerate(cands[: n * 2], 1):
        if not c.get("image_url"):
            continue
        dl_url = c.get("thumb_url") or c["image_url"]
        ext = Path(urllib.parse.urlparse(dl_url).path).suffix or ".jpg"
        stem = f"{i:02d}_{c['source'].split()[0].lower()}"
        img_path = out_dir / f"{stem}{ext}"
        try:
            img_path.write_bytes(_get(dl_url))
        except Exception as e:
            print(f"  skip {c['title'][:40]}: download failed ({e})")
            continue
        c["attribution"] = attribution_line(c)
        c["file"] = img_path.name
        (out_dir / f"{stem}.json").write_text(json.dumps(c, indent=2), encoding="utf-8")
        saved.append(c)
        if len(saved) >= n:
            break
    return saved


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    term = sys.argv[1]

    def arg(name, d):
        return sys.argv[sys.argv.index(f"--{name}") + 1] if f"--{name}" in sys.argv else d

    out_dir = Path(arg("out", f"assets/{term.replace(' ', '_')}"))
    n = int(arg("n", "6"))
    print(f"searching Commons + Openverse for '{term}' (license-clean only)...")
    saved = fetch(term, out_dir, n)
    if not saved:
        print("no license-clean candidates found (or no network). nothing downloaded.")
        return 1
    print(f"\n{len(saved)} candidate(s) in {out_dir} - pick the ones you want:\n")
    for c in saved:
        print(f"  [{c['file']}] {c['title'][:50]}")
        print(f"      {c['license']}  ({c['source']})")
        print(f"      attribution: {c['attribution']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

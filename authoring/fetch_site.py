"""fetch_site.py - fetch a site's posts into clean, readable local markdown.

Give it one or more post URLs (or a page to pull post links from). It respects
robots.txt, fetches politely, converts each page to readable markdown, and
saves an archive locally. This is for YOUR reading and for studying STYLE - it
is not a content miner. For sites that are not yours, the boundary is firm:
read and learn the style, never copy the words or the figures into a post.

    python fetch_site.py https://example.com/post --out archive/example
    python fetch_site.py https://example.com/blog --crawl --out archive/example

Style is learnable from anyone. Words and figures are theirs.
"""
from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.robotparser import RobotFileParser

UA = "authoring-assistant/0.1 (personal blog tooling; respects robots.txt)"


def _robots_ok(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    rp = RobotFileParser()
    rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True  # no robots.txt reachable: allowed by convention
    return rp.can_fetch(UA, url)


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def _decode_entities(s: str) -> str:
    import html
    return html.unescape(s)


def html_to_markdown(html: str) -> tuple[str, str]:
    title = _decode_entities(re.sub(r"\s+", " ",
            (re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I) or [None, ""])[1])).strip()
    s = re.sub(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    # prefer the article/main body if present
    m = re.search(r"<(article|main)[^>]*>(.*?)</\1>", s, re.S | re.I)
    if m:
        s = m.group(2)
    s = re.sub(r"<h([1-6])[^>]*>(.*?)</h\1>", lambda x: "\n" + "#" * int(x.group(1)) + " "
               + re.sub(r"<[^>]+>", "", x.group(2)).strip() + "\n", s, flags=re.S | re.I)
    s = re.sub(r"<pre[^>]*>(.*?)</pre>", lambda x: "\n```\n" + re.sub(r"<[^>]+>", "", x.group(1)) + "\n```\n", s, flags=re.S | re.I)
    s = re.sub(r"<li[^>]*>(.*?)</li>", lambda x: "\n- " + re.sub(r"<[^>]+>", "", x.group(1)).strip(), s, flags=re.S | re.I)
    s = re.sub(r"<img[^>]*alt=[\"']([^\"']*)[\"'][^>]*>", r"\n![\1](image)\n", s, flags=re.I)
    s = re.sub(r"<figcaption[^>]*>(.*?)</figcaption>", lambda x: "\n*" + re.sub(r"<[^>]+>", "", x.group(1)).strip() + "*\n", s, flags=re.S | re.I)
    s = re.sub(r"<(p|div|section|br)[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = _decode_entities(s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return title, s


def _post_links(html: str, base: str) -> list[str]:
    out = []
    for m in re.finditer(r'href=["\']([^"\'#]+)["\']', html):
        u = urllib.parse.urljoin(base, m.group(1)).split("#")[0]
        if urllib.parse.urlparse(u).netloc == urllib.parse.urlparse(base).netloc:
            if re.search(r"/(post|posts|blog|writing|article)s?/", u):
                out.append(u)
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def fetch_site(urls: list[str], out_dir: Path, crawl: bool) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if crawl and len(urls) == 1:
        try:
            urls = _post_links(_fetch(urls[0]), urls[0])[:20] or urls
        except Exception as e:
            print(f"  crawl: could not read index ({e})")
    saved = []
    for url in urls:
        if not _robots_ok(url):
            print(f"  robots.txt disallows {url}; skipping")
            continue
        try:
            title, md = html_to_markdown(_fetch(url))
        except Exception as e:
            print(f"  fetch failed for {url}: {e}")
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", (title or url).lower()).strip("-")[:60] or "post"
        path = out_dir / f"{slug}.md"
        front = f"---\nsource_url: {url}\ntitle: \"{title}\"\n---\n\n"
        path.write_text(front + md, encoding="utf-8")
        saved.append(path)
        print(f"  saved {path.name}  ({len(md)} chars)  <- {url}")
    return saved


VALUE_FLAGS = {"--out", "--name"}


def _positionals(argv: list[str]) -> list[str]:
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            if a in VALUE_FLAGS:
                skip = True
            continue
        out.append(a)
    return out


def main() -> int:
    args = _positionals(sys.argv[1:])
    if not args:
        print(__doc__)
        return 2

    def arg(name, d):
        return sys.argv[sys.argv.index(f"--{name}") + 1] if f"--{name}" in sys.argv else d

    out_dir = Path(arg("out", "archive/site"))
    crawl = "--crawl" in sys.argv
    print(f"fetching {len(args)} url(s) (robots-respecting) -> {out_dir}")
    saved = fetch_site(args, out_dir, crawl)
    if saved:
        print(f"\n{len(saved)} post(s) archived. study the style; the words and figures stay theirs.")
        print("next: python build_profile.py", out_dir, "--name <profile-name>")
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())

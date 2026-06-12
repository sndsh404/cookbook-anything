"""M2.5 gate: autonomous acquisition, license-gated.

Against a local seeded site (50 public pages, a robots-forbidden /private/
tree, offsite links): 0 robots violations and 0 off-allowlist fetches,
verified from the SERVER side; rerun fetches 0 pages (cache). License gate:
Commons metadata verifies (live API if reachable, fixture otherwise); a page
claim that disagrees with API metadata is rejected; all-rights-reserved is
rejected and converted into a figure request; an asset record without a
license cannot enter the model (ca validate). A screenshot ships framed
with URL + access date.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "figlib"))
import ca  # noqa: E402

WS = ROOT / "workspace" / "_m25test"
PORT = 8931
NODE = ["node", "--experimental-strip-types", "--no-warnings"]
ACQUIRE = str(ROOT / "runner" / "acquire" / "acquire.ts")

FIXTURE_OK = {"query": {"pages": {"1": {"imageinfo": [{
    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Bplustree.png",
    "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"},
                    "Artist": {"value": "<a href='#'>Jane Doe</a>"}}}]}}}}
FIXTURE_ARR = {"query": {"pages": {"1": {"imageinfo": [{
    "descriptionurl": "https://example.com/photo",
    "extmetadata": {"LicenseShortName": {"value": "All Rights Reserved"},
                    "Artist": {"value": "Someone"}}}]}}}}


def server_stats() -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/__stats", timeout=5) as r:
        return json.loads(r.read())


def crawl() -> dict:
    r = subprocess.run([*NODE, ACQUIRE, "crawl", f"http://127.0.0.1:{PORT}/",
                        "--workspace", str(WS), "--allow", "127.0.0.1",
                        "--max-pages", "60"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"crawl failed: {r.stdout}\n{r.stderr}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def run_asset(title: str, fixture: dict | None, claim: str = "") -> tuple[int, dict]:
    args = [*NODE, ACQUIRE, "asset", title, "--workspace", str(WS)]
    if fixture is not None:
        fp = WS / f"fixture_{abs(hash(title)) % 1000}.json"
        fp.write_text(json.dumps(fixture), encoding="utf-8")
        args += ["--fixture", str(fp)]
    if claim:
        args += ["--claim", claim]
    r = subprocess.run(args, capture_output=True, text=True, timeout=120)
    out = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    return r.returncode, out


def main() -> int:
    failures: list[str] = []
    if WS.exists():
        shutil.rmtree(WS)
    WS.mkdir(parents=True)

    # ---- the seeded crawl
    server = subprocess.Popen(["node", str(ROOT / "runner" / "testserver.mjs"), str(PORT)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(1.5)
        stats1 = crawl()
        s = server_stats()
        print(f"crawl 1: {stats1}; server saw {s}")
        print(f"METRIC m25_robots_violations {s['privateHits']} down")
        if s["privateHits"] != 0:
            failures.append(f"{s['privateHits']} hits on robots-forbidden /private/")
        if stats1["deniedRobots"] < 1:
            failures.append("crawler never even encountered/denied a private link")
        if stats1["deniedAllowlist"] < 1:
            failures.append("offsite link was not scoped out")
        print(f"METRIC m25_offsite_denied {stats1['deniedAllowlist']} up")
        archived = stats1["archived"]
        print(f"METRIC m25_pages_archived {archived} up")
        if archived < 50:
            failures.append(f"archived {archived} pages, expected 50")
        # archive-on-fetch: markdown copies with origin_url + fetched_at
        mds = list((WS / "sources" / "web").glob("*.md"))
        if len(mds) < 50:
            failures.append(f"only {len(mds)} archived markdown copies")
        elif "origin_url:" not in mds[0].read_text(encoding="utf-8"):
            failures.append("archived copy lacks origin_url metadata")

        # ---- rerun: the cache means the server sees zero new page fetches
        hits_before = server_stats()["hits"]
        stats2 = crawl()
        refetched = server_stats()["hits"] - hits_before
        print(f"crawl 2: {stats2}")
        print(f"METRIC m25_rerun_fetches {refetched} down")
        if refetched != 0:
            failures.append(f"rerun fetched {refetched} pages from the network (want 0)")
    finally:
        server.kill()

    # ---- license gate
    code, out = run_asset("File:Bplustree.png", None)  # try the LIVE Commons API
    live_worked = code == 0 and out.get("decision") == "embed"
    if not live_worked:
        code, out = run_asset("File:Bplustree.png", FIXTURE_OK)
    verified = 1 if (code == 0 and out.get("decision") == "embed"
                     and out["asset"]["license"]["verified_by"].startswith("commons_api")
                     and out["asset"]["attribution"]) else 0
    print(f"METRIC m25_license_verified {verified} up "
          f"({'live api' if live_worked else 'fixture'})")
    if not verified:
        failures.append(f"commons license verification failed: {out}")
    asset_rec = out.get("asset")

    code, out = run_asset("File:Mismatch.png", FIXTURE_OK, claim="CC0")
    rejected = 1 if code == 3 and out.get("decision") == "reject_redraw" else 0
    print(f"METRIC m25_mismatch_rejected {rejected} up")
    if not rejected:
        failures.append(f"page-claim/API mismatch was not rejected: {out}")

    code, out = run_asset("File:Proprietary.png", FIXTURE_ARR)
    arr_rejected = 1 if code == 3 and out.get("decision") == "reject_redraw" else 0
    print(f"METRIC m25_arr_rejected {arr_rejected} up")
    if not arr_rejected:
        failures.append(f"all-rights-reserved was not rejected: {out}")
    if not (WS / ".cookbook" / "figure_requests.jsonl").exists():
        failures.append("rejection did not produce a figure request")

    # ---- both firewalls: the asset enters the model only with its license
    if asset_rec:
        model = {"sources": [], "spans": [], "nodes": [], "edges": [], "claims": [],
                 "tours": [], "glossary": [], "assets": [asset_rec]}
        mp = WS / "model_with_asset.json"
        mp.write_text(json.dumps(model), encoding="utf-8")
        if ca.run("validate", str(mp), check=False).returncode != 0:
            failures.append("licensed asset should validate in the model")
        bad = dict(asset_rec)
        bad.pop("license")
        model["assets"] = [bad]
        mp.write_text(json.dumps(model), encoding="utf-8")
        if ca.run("validate", str(mp), check=False).returncode == 0:
            failures.append("asset WITHOUT license was accepted by the model (firewall hole)")

    # ---- screenshot framing (F-14)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fake = WS / "raw_shot.png"
    fig, ax = plt.subplots(figsize=(4, 2.5))
    ax.text(0.5, 0.5, "seeded page 1", ha="center")
    ax.set_axis_off()
    fig.savefig(fake)
    plt.close(fig)
    from screenshot_frame import frame_screenshot
    sc = frame_screenshot(fake, f"http://127.0.0.1:{PORT}/page/1", WS / "framed_shot.png")
    framed = 1 if sc["framed"] and sc["url"] and sc["accessed"] else 0
    print(f"METRIC m25_screenshot_framed {framed} up")
    if not framed:
        failures.append("screenshot frame missing url/date stamp")

    if failures:
        print("M2.5 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print("M2.5 GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

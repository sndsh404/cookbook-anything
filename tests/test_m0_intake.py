"""M0 gate: 3 source types parse with traces; 12 planted secrets -> 0 leaks
into spans; rerun on unchanged sources reparses 0.

Prints METRIC lines for assess.py. Exit nonzero on any failure.
"""
from __future__ import annotations

import json
import shutil
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from ca import intake  # noqa: E402  (drives the Rust core binary)

WS = ROOT / "workspace" / "_m0test"

# 12 planted secrets, assembled at runtime so no secret-shaped literal sits
# in the repo (GitHub push protection scans file content, and it is right to).
_j = "".join
SECRETS = [
    _j(["AKIA", "IOSFODNN7", "EXAMPLE"]),                              # 1 aws
    _j(["AKIA", "J4QWERTY", "12345678"]),                              # 2 aws
    _j(["ghp", "_", "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"]),          # 3 github
    _j(["xoxb", "-", "123456789012", "-", "abcdefghijklmnop"]),        # 4 slack
    _j(["eyJhbGciOiJIUzI1NiJ9", ".", "eyJzdWIiOiIxMjM0NTY3ODkwIn0",
        ".", "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9P"]),                     # 5 jwt
    "hunter2supersecretpw",                                            # 6 password=
    _j(["sk", "-", "9f8e7d6c5b4a3210fedcba98"]),                       # 7 api_key=
    "tOpS3cr3tV4lu3F0rT3st1ng",                                        # 8 secret:
    _j(["tok", "_", "4f5e6d7c8b9a0918273645"]),                        # 9 token=
    "Zx9kQ2mP7vL4nR8tW3yB6cF1dH5jS0aG9eK2uX7o",                        # 10 high entropy
    "q8Yt3Rw7Uj2Mk9Zx4Cv6Bn1Lp5Sd0Fg8Hh3Jk6Ld",                        # 11 high entropy
    _j(["-----BEGIN RSA PRIVATE", " KEY-----\n", "MIIEpAIBAAKCAQEA7gXqK9",
        "\n-----END RSA PRIVATE", " KEY-----"]),                       # 12 pem
]


def make_pdf(path: Path, text: str) -> None:
    """Minimal one-page PDF with a FlateDecode text stream."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    comp = zlib.compress(content)
    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
        b"4 0 obj << /Length " + str(len(comp)).encode() + b" /Filter /FlateDecode >> stream\n"
        + comp + b"\nendstream endobj",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
    ]
    out = b"%PDF-1.4\n" + b"\n".join(objs) + b"\ntrailer << /Root 1 0 R >>\n%%EOF"
    path.write_bytes(out)


def build_fixture() -> Path:
    if WS.exists():
        shutil.rmtree(WS)
    src = WS / "sources"

    # source 1: a fake git repo with planted secrets in code
    repo = src / "demo-repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (repo / "app.py").write_text(
        "import os\n\n"
        f'AWS_KEY = "{SECRETS[0]}"\n'
        f'password = "{SECRETS[5]}"\n'
        "def main():\n"
        '    """Entry point."""\n'
        "    print('hello')\n", encoding="utf-8")
    (repo / "config.py").write_text(
        f'api_key = "{SECRETS[6]}"\n'
        f'token = "{SECRETS[8]}"\n'
        f'GH = "{SECRETS[2]}"\n'
        f'SLACK = "{SECRETS[3]}"\n'
        "DEBUG = True\n", encoding="utf-8")
    (repo / "key.pem").write_text(SECRETS[11], encoding="utf-8")
    (repo / "key.pem").rename(repo / "key.txt")  # .txt so it is ingested

    # source 2: a PDF with a secret in its text layer
    make_pdf(src / "notes.pdf", f"Deployment notes. The staging key is {SECRETS[1]} do not share.")

    # source 3: a mixed folder
    folder = src / "mixed-docs"
    folder.mkdir(parents=True)
    (folder / "readme.md").write_text(
        "# Mixed docs\n\nThe service uses a queue.\n\n"
        f"jwt sample: {SECRETS[4]}\n"
        f"secret: {SECRETS[7]}\n", encoding="utf-8")
    (folder / "data.csv").write_text(
        "name,value\nalpha,1\nbeta,2\n", encoding="utf-8")
    (folder / "deploy.txt").write_text(
        f"first entropy blob {SECRETS[9]} end\n"
        f"second entropy blob {SECRETS[10]} end\n", encoding="utf-8")
    return src


def main() -> int:
    failures: list[str] = []
    src = build_fixture()
    cb = WS / ".cookbook"

    stats = intake(src, cb)

    manifest = json.loads((cb / "manifest.json").read_text(encoding="utf-8"))
    types = {s["type"] for s in manifest["sources"]}
    if len(manifest["sources"]) != 3:
        failures.append(f"expected 3 sources, got {len(manifest['sources'])}")
    if not {"git_repo", "pdf", "folder"} <= types:
        failures.append(f"expected git_repo+pdf+folder, got {types}")
    for s in manifest["sources"]:
        if not s.get("parser") or not s.get("sha256"):
            failures.append(f"source {s['id']} missing parser or sha")
        tr = cb / "trace" / f"{s['id'].replace(':', '-')}.jsonl"
        if not tr.exists() or not tr.read_text(encoding="utf-8").strip():
            failures.append(f"source {s['id']} has no trace")

    # the core number: 0 secret leaks anywhere under .cookbook/
    leaked = 0
    blob = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in cb.rglob("*") if p.is_file())
    for i, sec in enumerate(SECRETS):
        probe = sec.splitlines()[1] if "\n" in sec else sec  # key body for the pem
        if probe in blob:
            leaked += 1
            failures.append(f"secret #{i + 1} leaked into .cookbook ({probe[:8]}...)")
    print(f"METRIC secrets_leaked {leaked} down")
    print(f"METRIC m0_sources_parsed {stats['parsed']} up")

    if stats["redactions"] < 12:
        failures.append(f"expected >=12 redactions, got {stats['redactions']}")

    # rerun: zero re-parsing
    stats2 = intake(src, cb)
    print(f"METRIC m0_rerun_reparsed {stats2['parsed']} down")
    if stats2["parsed"] != 0 or stats2["skipped"] != 3:
        failures.append(f"rerun should skip all 3: parsed={stats2['parsed']} skipped={stats2['skipped']}")
    # spans must survive a skip-run intact
    n_spans = len((cb / "spans.jsonl").read_text(encoding="utf-8").strip().splitlines())
    if n_spans != stats["n_spans"] or n_spans == 0:
        failures.append(f"span store changed across skip-run: {stats['n_spans']} -> {n_spans}")

    # pdf text layer actually extracted (redacted marker present, prose intact)
    pdf_spans = [line for line in (cb / "spans.jsonl").read_text(encoding="utf-8").splitlines()
                 if '"notes.pdf"' in line]
    if not pdf_spans or "Deployment notes" not in pdf_spans[0]:
        failures.append("pdf text layer not extracted")

    if failures:
        print("M0 GATE FAILED:")
        for x in failures:
            print(" -", x)
        return 1
    print("M0 GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

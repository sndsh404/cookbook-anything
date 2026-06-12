"""intake.py - Stage 1. Deterministic only; no agent.

Walks a sources directory, routes each top-level item to a parser by type,
runs the secret filter BEFORE any text reaches the span store, and writes:

  <cookbook>/manifest.json        one record per source (id, type, parser, sha256)
  <cookbook>/spans.jsonl          file-level spans of REDACTED text
  <cookbook>/trace/<src-id>.jsonl per-source parsing timeline (the WeKnora idea)
  <cookbook>/runs.jsonl           append-only audit trail

Incremental: a source whose sha256 matches the existing manifest is skipped
(zero re-parsing), with a trace event saying so.

Usage: python scripts/intake.py <sources_dir> [<cookbook_dir>]
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

TEXT_EXT = {".py", ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml",
            ".cfg", ".ini", ".csv", ".sql", ".js", ".ts", ".html", ".css",
            ".sh", ".ps1", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".cookbook"}
MAX_FILE_BYTES = 2_000_000

# ---------------------------------------------------------------- secrets

SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\b")),
    ("credential_assignment", re.compile(
        r"(?i)\b(api[_-]?key|secret[_-]?key|secret|token|passwd|password)\b(\s*[:=]\s*)([\"']?)([^\s\"',;]{8,})\3")),
]
ENTROPY_TOKEN = re.compile(r"\b[A-Za-z0-9+/_=-]{28,}\b")


def _shannon(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def redact_secrets(text: str) -> tuple[str, dict[str, int]]:
    """Strip secrets; return (clean_text, counts_by_kind). Values never logged."""
    counts: dict[str, int] = {}

    def bump(kind: str, n: int = 1) -> None:
        if n:
            counts[kind] = counts.get(kind, 0) + n

    for kind, pat in SECRET_PATTERNS:
        if kind == "credential_assignment":
            def sub_assign(m: re.Match) -> str:
                bump(kind)
                return f"{m.group(1)}{m.group(2)}[REDACTED:{kind}]"
            text = pat.sub(sub_assign, text)
        else:
            text, n = pat.subn(f"[REDACTED:{kind}]", text)
            bump(kind, n)

    def sub_entropy(m: re.Match) -> str:
        tok = m.group(0)
        if "REDACTED" in tok:
            return tok
        if _shannon(tok) > 4.2:
            bump("high_entropy")
            return "[REDACTED:high_entropy]"
        return tok

    text = ENTROPY_TOKEN.sub(sub_entropy, text)
    return text, counts


# ---------------------------------------------------------------- pdf (minimal)

def extract_pdf_text(data: bytes, trace: "Trace") -> str:
    """Minimal text-layer extraction: stream objects, optional FlateDecode,
    Tj/TJ operators. Honest fallback with a trace note when unsupported."""
    chunks: list[str] = []
    for m in re.finditer(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", data, re.S):
        head, body = m.group(1), m.group(2)
        if b"/FlateDecode" in head:
            try:
                body = zlib.decompress(body)
            except zlib.error:
                trace.event("fallback", note="FlateDecode stream failed to inflate; skipped")
                continue
        if b"/Image" in head or b"/Subtype/Image" in head:
            continue
        try:
            s = body.decode("latin-1")
        except UnicodeDecodeError:
            continue
        for tm in re.finditer(r"\((?:[^()\\]|\\.)*\)\s*Tj|\[((?:[^\[\]\\]|\\.)*)\]\s*TJ", s):
            frag = tm.group(0)
            for lit in re.finditer(r"\(((?:[^()\\]|\\.)*)\)", frag):
                chunks.append(lit.group(1).replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\"))
        if chunks:
            chunks.append("\n")
    if not chunks:
        trace.event("fallback", note="no extractable text layer (would need OCR); skipping with trace note")
    return " ".join(chunks).strip()


# ---------------------------------------------------------------- trace / ids

class Trace:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, **fields) -> None:
        rec = {"at": datetime.now(timezone.utc).isoformat(), "event": kind, **fields}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def hash_source(path: Path) -> str:
    """Content hash of a file, or of a directory tree (paths + file hashes)."""
    if path.is_file():
        return sha256_bytes(path.read_bytes())
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_dir() or any(part in SKIP_DIRS for part in f.parts):
            continue
        h.update(str(f.relative_to(path)).encode())
        try:
            h.update(hashlib.sha256(f.read_bytes()).digest())
        except OSError:
            continue
    return h.hexdigest()


def classify(path: Path) -> str:
    if path.is_dir():
        return "git_repo" if (path / ".git").exists() else "folder"
    return {".pdf": "pdf", ".md": "markdown", ".csv": "csv", ".sql": "sql_dump"}.get(
        path.suffix.lower(), "file")


# ---------------------------------------------------------------- intake

def parse_source(src_path: Path, src_id: str, src_type: str, trace: Trace,
                 span_sink: list[dict], next_span: list[int]) -> dict[str, int]:
    """Produce redacted file-level spans. Returns total redaction counts."""
    redactions: dict[str, int] = {}

    def add_span(locator: str, text: str) -> None:
        clean, counts = redact_secrets(text)
        for k, v in counts.items():
            redactions[k] = redactions.get(k, 0) + v
        span_sink.append({
            "id": f"span:{next_span[0]:05d}",
            "source": src_id,
            "locator": locator,
            "text_sha": sha256_bytes(clean.encode("utf-8")),
            "text": clean,
        })
        next_span[0] += 1

    if src_type in ("git_repo", "folder"):
        n_files = 0
        for f in sorted(src_path.rglob("*")):
            if f.is_dir() or any(p in SKIP_DIRS for p in f.parts):
                continue
            if f.suffix.lower() == ".pdf":
                add_span(str(f.relative_to(src_path)), extract_pdf_text(f.read_bytes(), trace))
                n_files += 1
                continue
            if f.suffix.lower() not in TEXT_EXT or f.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                add_span(str(f.relative_to(src_path)), f.read_text(encoding="utf-8", errors="replace"))
                n_files += 1
            except OSError as e:
                trace.event("fallback", file=str(f.name), note=f"unreadable: {e}")
        trace.event("parsed", files=n_files)
    elif src_type == "pdf":
        add_span(src_path.name, extract_pdf_text(src_path.read_bytes(), trace))
        trace.event("parsed", files=1)
    else:  # markdown, csv, sql_dump, file
        add_span(src_path.name, src_path.read_text(encoding="utf-8", errors="replace"))
        trace.event("parsed", files=1)
    if redactions:
        trace.event("redacted", counts=redactions)  # counts and kinds only, never values
    return redactions


def intake(sources_dir: Path, cookbook_dir: Path) -> dict:
    cookbook_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cookbook_dir / "manifest.json"
    spans_path = cookbook_dir / "spans.jsonl"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"sources": []}
    old_by_path = {s["path"]: s for s in old["sources"]}

    old_spans: list[dict] = []
    if spans_path.exists():
        old_spans = [json.loads(line) for line in spans_path.read_text(encoding="utf-8").splitlines() if line]

    items = sorted([p for p in sources_dir.iterdir() if p.name not in SKIP_DIRS])
    print(f"[Stage 1/7] intake: {len(items)} sources in {sources_dir}")
    sources, spans = [], []
    next_span = [max([int(s["id"].split(":")[1]) for s in old_spans], default=0) + 1]
    stats = {"parsed": 0, "skipped": 0, "redactions": 0}

    for i, item in enumerate(items, 1):
        rel = item.name
        src_type = classify(item)
        digest = hash_source(item)
        prev = old_by_path.get(rel)
        src_id = prev["id"] if prev else f"src:{len(old_by_path) + stats['parsed'] + 1:04d}"
        trace = Trace(cookbook_dir / "trace" / f"{src_id.replace(':', '-')}.jsonl")
        parser = {"git_repo": "intake.py@repo", "folder": "intake.py@folder",
                  "pdf": "intake.py@pdf", "markdown": "intake.py@markdown",
                  "csv": "intake.py@csv", "sql_dump": "intake.py@sql",
                  "file": "intake.py@text"}[src_type]

        if prev and prev["sha256"] == digest:
            trace.event("skipped", reason="unchanged (sha256 match)")
            sources.append(prev)
            spans.extend(s for s in old_spans if s["source"] == src_id)
            stats["skipped"] += 1
            print(f"  [{i}/{len(items)}] {rel}: unchanged, skipped")
            continue

        trace.event("detected", type=src_type, parser=parser)
        red = parse_source(item, src_id, src_type, trace, spans, next_span)
        stats["parsed"] += 1
        stats["redactions"] += sum(red.values())
        sources.append({"id": src_id, "type": src_type, "path": rel, "parser": parser,
                        "sha256": digest, "ingested_at": datetime.now(timezone.utc).isoformat()})
        print(f"  [{i}/{len(items)}] {rel}: {src_type} parsed"
              + (f", {sum(red.values())} secrets redacted" if red else ""))

    manifest_path.write_text(json.dumps({"sources": sources}, indent=2), encoding="utf-8")
    with spans_path.open("w", encoding="utf-8") as fh:
        for s in spans:
            fh.write(json.dumps(s) + "\n")
    with (cookbook_dir / "runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "stage": "intake",
                             **stats, "n_sources": len(sources), "n_spans": len(spans)}) + "\n")
    print(f"[Stage 1/7] done: {stats['parsed']} parsed, {stats['skipped']} skipped, "
          f"{stats['redactions']} secrets redacted, {len(spans)} spans")
    return {**stats, "n_sources": len(sources), "n_spans": len(spans)}


if __name__ == "__main__":
    src = Path(sys.argv[1])
    cb = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent / ".cookbook"
    intake(src, cb)

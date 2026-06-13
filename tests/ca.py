"""Shared helper: locate and invoke the ca binary (the Rust core CLI)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CA = ROOT / "core" / "target" / "release" / "ca.exe"


def ref_dir() -> Path:
    """Where the studied reference repos (llmwiki, etc.) live on this machine.

    Machine-specific, so it is NOT hardcoded in committed files: read it from
    the CA_REF_DIR env var, or .claude/state/ref_dir.txt (both gitignored).
    """
    env = os.environ.get("CA_REF_DIR")
    if env:
        return Path(env)
    state = ROOT / ".claude" / "state" / "ref_dir.txt"
    if state.exists():
        line = state.read_text(encoding="utf-8").strip()
        if line:
            return Path(line)
    raise RuntimeError(
        "reference repo dir unknown: set CA_REF_DIR or write the path into "
        ".claude/state/ref_dir.txt (see .claude/state/env.local.md)")


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([str(CA), *args], capture_output=True, text=True, timeout=600)
    if check and proc.returncode != 0:
        raise RuntimeError(f"ca {' '.join(args)} failed ({proc.returncode}):\n"
                           f"{proc.stdout}\n{proc.stderr}")
    return proc


def intake(src: Path, cb: Path) -> dict:
    proc = run("intake", str(src), str(cb))
    return json.loads(proc.stdout.strip().splitlines()[-1])

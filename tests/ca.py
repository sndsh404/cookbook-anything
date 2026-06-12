"""Shared helper: locate and invoke the ca binary (the Rust core CLI)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CA = ROOT / "core" / "target" / "release" / "ca.exe"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([str(CA), *args], capture_output=True, text=True, timeout=600)
    if check and proc.returncode != 0:
        raise RuntimeError(f"ca {' '.join(args)} failed ({proc.returncode}):\n"
                           f"{proc.stdout}\n{proc.stderr}")
    return proc


def intake(src: Path, cb: Path) -> dict:
    proc = run("intake", str(src), str(cb))
    return json.loads(proc.stdout.strip().splitlines()[-1])

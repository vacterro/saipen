"""Build the T-1370 A/B pair: CUR (current bytes) and BASE (pre-T-1370).

Both sides are full copies of the live working tree, so the ONLY variable
between them is the T-1370 patch itself: identical .git, identical untracked
noise, identical environment. BASE then reverts every tracked path to HEAD
(306299cc) and removes the untracked artifacts T-1370 minted.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

LIVE = Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
AB = Path(sys.argv[1])
CUR = AB / "cur"
BASE = AB / "base"

SKIP = {"__pycache__", ".pytest_cache", ".workbuddy-ai"}

# Untracked artifacts minted by the T-1370 BUILD slice (E-6808/E-6811).
T1370_UNTRACKED = [
    "tools/saipen_engine/retirement.py",
    "tools/test_ticket_retirement.py",
    "tools/test_field_fixture_isolation.py",
    ".saipen/archive/retired",
    ".saipen/evidence/T-1370-retirement-20260916",
]


def _ignore(_directory: str, names: list[str]) -> set[str]:
    out = {n for n in names if n in SKIP or n.endswith(".pyc")}
    if os.name == "nt":
        reserved = {"CON", "PRN", "AUX", "NUL"}
        reserved.update(f"COM{i}" for i in range(1, 10))
        reserved.update(f"LPT{i}" for i in range(1, 10))
        out.update(
            n for n in names if n.rstrip(" .").split(".", 1)[0].upper() in reserved
        )
    return out


def copy(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(LIVE, dest, ignore=_ignore, symlinks=True)


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    return done.stdout + done.stderr


def main() -> int:
    AB.mkdir(parents=True, exist_ok=True)
    copy(CUR)
    print("CUR copied", flush=True)
    copy(BASE)
    print("BASE copied", flush=True)

    # BASE: every tracked path back to HEAD.
    print(git(BASE, "reset", "-q"), end="")
    print(git(BASE, "checkout", "-f", "HEAD", "--", "."), end="")

    for rel in T1370_UNTRACKED:
        target = BASE / rel
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()

    # BASE: drop intake artifacts for receipts HEAD's index does not know.
    index = json.loads((BASE / ".saipen/intake/index.json").read_text("utf-8-sig"))
    known = set(index.get("active", {})) | set(index.get("tombstones", {}))
    for sub in ("active", "contracts", "coverage", "tombstones"):
        directory = BASE / ".saipen/intake" / sub
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            receipt = path.name.split(".", 1)[0]
            if receipt.startswith("SRC-") and receipt not in known:
                path.unlink()
                print(f"BASE drop {sub}/{path.name}", flush=True)

    print("BASE head:", git(BASE, "rev-parse", "--short", "HEAD").strip())
    print("BASE dirty:", len(git(BASE, "status", "--porcelain=v1").splitlines()))
    print("CUR  head:", git(CUR, "rev-parse", "--short", "HEAD").strip())
    print("CUR  dirty:", len(git(CUR, "status", "--porcelain=v1").splitlines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

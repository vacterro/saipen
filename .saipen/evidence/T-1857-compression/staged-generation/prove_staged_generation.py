"""Prove the reported crash came from generation drift, and that no publishable
generation still carries it.

The operator's report was ``REGISTRY.json `limits` must be an object`` raised
while importing ``goal_authority``. Three generations exist in this worktree and
they are not the same bytes:

* HEAD    -- no goal_authority.py and no goal_authority block: consistent.
* index   -- goal_authority.py that never reads ``limits``: consistent.
* worktree-- goal_authority.py that DOES read ``limits`` at import time.

The crash is the CROSS-PAIRING of the worktree code with a registry that has no
``limits``. That pairing is reproduced here as the red control; the worktree
pairing with its own registry is the green control. Exit 0 means both held.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MISSING = "REGISTRY.json `limits` must be an object"


def staged(path: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "show", f":{path}"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except subprocess.CalledProcessError:
        return b""


def head(path: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except subprocess.CalledProcessError:
        return b""


def require_mapping_from(source: str):
    """Extract ``require_mapping`` from a registry.py source without importing it."""
    match = re.search(r"^def require_mapping\b.*?(?=^\S)", source, re.M | re.S)
    if not match:
        raise SystemExit("registry.py has no module-level require_mapping")
    namespace: dict = {"RegistryError": type("RegistryError", (ValueError,), {})}
    exec(match.group(0), namespace)  # noqa: S102 - the surveyed source is the subject
    return namespace["require_mapping"]


def run_case(label: str, code: bytes, registry: bytes, wants: str) -> bool:
    """Return True when the case behaves as ``wants`` ('crash' or 'clean')."""
    ga = code.decode("utf-8")
    demands = '"goal_authority"), "limits"' in ga
    reg = json.loads(registry.decode("utf-8-sig"))
    ga_block = reg.get("goal_authority")
    print(f"\n{label}")
    print(f"  code demands limits      : {demands}")
    print(f"  registry goal_authority  : {sorted(ga_block) if isinstance(ga_block, dict) else ga_block!r}")
    if not demands:
        print("  -> code never reads limits, cannot crash on it")
        return wants == "clean"
    require_mapping = require_mapping_from(staged("tools/saipen_engine/registry.py").decode("utf-8"))
    try:
        require_mapping(require_mapping(reg, "goal_authority"), "limits")
    except Exception as exc:  # noqa: BLE001 - the reported symptom IS the oracle
        crashed = type(exc).__name__ == "RegistryError" and MISSING in str(exc)
        print(f"  -> CRASH {type(exc).__name__}: {exc}")
        print(f"  -> exact reported message: {crashed}")
        return wants == "crash" and crashed
    print("  -> clean import")
    return wants == "clean"


def main() -> int:
    before = require_mapping_from(head("tools/saipen_engine/registry.py").decode("utf-8")) if head(
        "tools/saipen_engine/registry.py"
    ) else None

    results = {
        "HEAD generation": run_case(
            "HEAD (committed) generation", head("tools/saipen_engine/goal_authority.py"),
            head("saipen/REGISTRY.json"), "clean",
        ),
        "staged generation": run_case(
            "INDEX (staged) generation", staged("tools/saipen_engine/goal_authority.py"),
            staged("saipen/REGISTRY.json"), "clean",
        ),
        "drift red control": run_case(
            "RED CONTROL: worktree code + staged registry (the operator's drift state)",
            (ROOT / "tools/saipen_engine/goal_authority.py").read_bytes(),
            staged("saipen/REGISTRY.json"), "crash",
        ),
        "worktree generation": run_case(
            "GREEN CONTROL: worktree code + worktree registry",
            (ROOT / "tools/saipen_engine/goal_authority.py").read_bytes(),
            (ROOT / "saipen/REGISTRY.json").read_bytes(), "clean",
        ),
    }
    print("\n" + "=" * 68)
    for name, ok in results.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    ok = all(results.values())
    print("=" * 68)
    print("CONTROL HOLDS: drift reproduces the report; no publishable generation carries it"
          if ok else "CONTROL BROKEN: a case did not behave as specified")
    del before
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

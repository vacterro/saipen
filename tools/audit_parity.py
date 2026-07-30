#!/usr/bin/env python3
"""Measures how much weaker the portable floor is than the canonical validator.

The floor (`tests/validate.sh` / `.ps1`) exists for hosts without Python. It is
frozen against new checks on purpose, so the gap between it and
`tools/validate.py` is permanent by design -- but until this tool the SIZE of
that gap was documented as a single known omission, and it is not one. Applying
`tools/audit_checks.py`'s mutation table to both tools showed the floor catching
11 of 41, while announcing "Agent is conformant" in exactly the canonical
validator's words for the other 28.

The wording is corrected; the number is not something to correct, it is
something to keep honest. This prints it, and fails if the floor silently drops
below the recorded baseline -- a floor getting WEAKER without anyone saying so
is the failure worth guarding, not the gap itself.

Exit 0 when the floor still catches at least BASELINE cases, 1 otherwise.
Skips (exit 0, loudly) where no POSIX shell is available.
"""
from __future__ import annotations

import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HOME = Path(__file__).resolve().parent.parent

# Measured at v7.120.0. Raise it when the floor genuinely gains coverage; a
# drop means the floor lost a check without anyone noticing, which is the whole
# reason this number is written down instead of recomputed and forgotten.
BASELINE = 11


def find_bash() -> str | None:
    """A bare `bash` is the wrong binary on Windows: from Python it resolves to
    the WSL stub in System32, which without an installed distro prints a UTF-16
    error and runs nothing. An audit that scored every check dead once already
    did so for exactly this reason."""
    for candidate in (r"C:\Program Files\Git\bin\bash.exe",
                      r"C:\Program Files (x86)\Git\bin\bash.exe",
                      shutil.which("sh")):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def main() -> int:
    bash = find_bash()
    if bash is None:
        print("SKIP: no POSIX shell found -- cannot compare against the floor")
        return 0

    spec = importlib.util.spec_from_file_location(
        "audit_checks", HOME / "tools" / "audit_checks.py")
    ac = importlib.util.module_from_spec(spec)
    sys.modules["audit_checks"] = ac
    spec.loader.exec_module(ac)

    tmp = Path(tempfile.mkdtemp(prefix="audit_parity_"))
    pristine = tmp / "pristine"
    shutil.copytree(HOME, pristine, ignore=ac.IGNORE)

    def validate(root):
        return subprocess.run(
            [sys.executable, str(root / "tools" / "validate.py")], cwd=root,
            capture_output=True, text=True, errors="replace").returncode

    def floor(root):
        return subprocess.run(
            [bash, "tests/validate.sh"], cwd=root,
            capture_output=True, text=True, errors="replace").returncode

    if validate(pristine) != 0 or floor(pristine) != 0:
        print("FAIL: one of the two tools rejects an UNMODIFIED copy -- every "
              "number below would be measuring that instead")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    # One copy, restored between cases -- see the same note in audit_checks.py.
    # Every case touches exactly one file, so its bytes are the whole state.
    both, only_canonical, neither = [], [], []
    for label, rel, mutation, _expected in ac.CASES:
        target = pristine / rel
        saved = target.read_bytes() if target.exists() else None
        try:
            if not ac.apply_case(pristine, rel, mutation):
                continue
            v, f = validate(pristine), floor(pristine)
            if v != 0 and f != 0:
                both.append(label)
            elif v != 0:
                only_canonical.append(label)
            else:
                neither.append(label)
        finally:
            if saved is None:
                if target.exists():
                    target.unlink()
            else:
                target.write_bytes(saved)

    if validate(pristine) != 0 or floor(pristine) != 0:
        print("FAIL: the copy did not survive the run -- restoring between "
              "cases left a mutation behind, so the counts above are measuring "
              "a drifting tree")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    shutil.rmtree(tmp, ignore_errors=True)

    applied = len(both) + len(only_canonical) + len(neither)
    print(f"cases applied: {applied}")
    print(f"  caught by both:                 {len(both)}")
    print(f"  caught only by tools/validate:  {len(only_canonical)}")
    print(f"  caught by neither (WARN-only):  {len(neither)}")
    for label in neither:
        print(f"      {label}")

    if len(both) < BASELINE:
        print(f"\nFAIL: the floor catches {len(both)} of {applied}, below the "
              f"recorded baseline of {BASELINE}. It has LOST coverage -- that "
              f"is the failure this tool exists for, not the gap itself")
        return 1
    print(f"\nPASS: the floor catches {len(both)} of {applied} "
          f"(baseline {BASELINE}). The other {len(only_canonical)} need "
          f"Python, which is why the floor no longer claims conformance in the "
          f"canonical validator's words")
    return 0


if __name__ == "__main__":
    sys.exit(main())

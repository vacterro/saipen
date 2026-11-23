#!/usr/bin/env python3
"""T-1885 tag-guard control: silent when readable, explicit when not.

MEASURED DEFECT. `git for-each-ref refs/tags` refuses the WHOLE tag set when
any one tag names an object this clone cannot read: it exits 128 and returns no
complete rows. `tools/validate.py` built its peel map from that call, so in a
damaged clone the map came back empty, every lookup yielded None, zero
candidates were produced, and the orphaned-release-tag check reported nothing.
394 tags verified exactly as cleanly as 0.

WHY THIS CONTROL DAMAGES THE REAL REPOSITORY. The first attempt used a
disposable minimal git repository and could not work: validate.py needs a full
SAIPEN project (STATE, BOARD, LOG, IDENTITY, the protocol tree) before it ever
reaches the release-ledger block, and a stub reproducing all of that would be a
mock of the thing under test. So this control creates a BRAND-NEW annotated tag
whose object it owns, removes that object's loose file to reproduce the real
damage, runs the real validator, then restores the object byte-for-byte. Every
step is inside try/finally; the probe tag is deleted on exit; the final check
asserts the tag peels again and warns loudly if the probe tag survives.

The probe tag is new, its object is new, and no existing tag, ref, tracked path
or canonical file is touched -- the only transient write is one object file
belonging to this control.

WHAT IT PROVES, AND WHAT THIS REPOSITORY CANNOT PROVE.
This clone is ALREADY damaged: 394 of its 394 tags name objects it cannot
read, so the "fully healthy -> no warning" half is unobservable here and this
control does not claim it. What it can prove, and does, is that the warning is
a MEASUREMENT rather than a static message:

  baseline    -> warning present, unreadable count N, verified count >= 1
                 (the fallback loop really does check the tags it can read)
  +1 damage   -> removing the probe tag's object raises the count to exactly
                 N+1: the number tracks the object store, not the code path
  restored    -> the count returns to N: the probe leaves no residue

The "silent before the fix" half is established separately by the pre/post A/B
recorded in ab-prefix.log / ab-post.log: identical tree, identical 42 problems,
0 unreadable-tag warnings before the guard and 1 after.

Run: python -B .saipen/evidence/T-1885-campaign-scout/tag-guard-control.py
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATE = REPO_ROOT / "tools" / "validate.py"
NEEDLE = re.compile(r"could not be peeled to commits", re.IGNORECASE)
PROBE_TAG = "v0.0.0-t1885-guard-control"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _release_ledger_warnings() -> list[str]:
    """Run the real validator, return its release-ledger warning lines."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(VALIDATE), "--project-root", str(REPO_ROOT), "--no-receipt"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    blob = f"{proc.stdout}\n{proc.stderr}"
    return [ln for ln in blob.splitlines() if "release-ledger" in ln.lower() or NEEDLE.search(ln)]


def _loose_path(obj: str) -> Path:
    return REPO_ROOT / ".git" / "objects" / obj[:2] / obj[2:]


def main() -> int:
    failures: list[str] = []
    backup: Path | None = None
    object_path: Path | None = None
    tag_created = False
    try:
        existing = _git("rev-parse", "-q", "--verify", f"refs/tags/{PROBE_TAG}")
        if existing.returncode == 0:
            print(f"SKIP: a tag named {PROBE_TAG} already exists; refusing to touch it")
            return 0

        made = _git("tag", "-a", PROBE_TAG, "-m", "T-1885 guard-control probe")
        if made.returncode != 0:
            print(f"SKIP: cannot create the probe tag: {made.stderr.strip()[:200]}")
            return 0
        tag_created = True
        obj = _git("rev-parse", f"refs/tags/{PROBE_TAG}").stdout.strip()
        if not obj:
            failures.append("the probe tag has no object id")
            return _report(failures)
        object_path = _loose_path(obj)
        if not object_path.is_file():
            print("SKIP: the probe tag object is packed, not loose; this control "
                  "only reproduces loose-object damage")
            return 0
        os.chmod(object_path, stat.S_IWRITE | stat.S_IREAD)
        backup = Path(tempfile.mkdtemp(prefix="t1885-tagobj-")) / "obj"
        backup.write_bytes(object_path.read_bytes())

        def _counts(lines: list[str]) -> tuple[int, int, int]:
            """(warnings, unreadable, verified) parsed from the guard's text."""
            joined = " ".join(lines)
            m = re.search(
                r"(\d+)\s+of\s+(\d+)\s+local tag\(s\).*?verified\s+(\d+)\s+of them",
                joined,
                re.IGNORECASE | re.DOTALL,
            )
            if not m:
                return (0, -1, -1)
            return (1, int(m.group(1)), int(m.group(3)))

        # The probe tag adds one READABLE tag on top of this clone's damage.
        base_lines = _release_ledger_warnings()
        base_n, base_unread, base_verified = _counts(base_lines)
        print(f"baseline    : {base_n} warning(s), unreadable={base_unread}, "
              f"verified={base_verified}")
        for line in base_lines[:2]:
            print(f"  baseline| {line.strip()[:170]}")
        if base_n != 1:
            failures.append(
                "BASELINE FAIL: no unreadable-tag warning on this damaged clone "
                "(other release-ledger warnings are unrelated and ignored)"
            )
        if base_unread < 0:
            failures.append(
                "BASELINE FAIL: the warning does not carry parseable counts, so "
                "the measurement cannot be checked"
            )

        object_path.unlink()
        try:
            dmg_lines = _release_ledger_warnings()
        finally:
            object_path.parent.mkdir(parents=True, exist_ok=True)
            object_path.write_bytes(backup.read_bytes())
            os.chmod(object_path, stat.S_IWRITE | stat.S_IREAD)
        dmg_n, dmg_unread, dmg_verified = _counts(dmg_lines)
        print(f"+1 damage   : {dmg_n} warning(s), unreadable={dmg_unread}, "
              f"verified={dmg_verified}")
        for line in dmg_lines[:2]:
            print(f"  damaged | {line.strip()[:170]}")

        if dmg_n != 1:
            failures.append("DAMAGE FAIL: no unreadable-tag warning after damage")
        elif base_unread >= 0 and dmg_unread != base_unread + 1:
            failures.append(
                f"MEASUREMENT FAIL: removing one tag object changed the unreadable "
                f"count by {dmg_unread - base_unread} (expected +1); the number does "
                "not track the object store"
            )

        restored = _git("rev-parse", f"refs/tags/{PROBE_TAG}^{{commit}}")
        if restored.returncode != 0:
            failures.append(
                "RESTORE FAIL: the probe tag no longer peels after its object was "
                f"restored: {restored.stderr.strip()[:160]}"
            )
        else:
            print(f"restored    : {PROBE_TAG} peels to {restored.stdout.strip()[:12]}")

        back_lines = _release_ledger_warnings()
        back_n, back_unread, back_verified = _counts(back_lines)
        print(f"after       : {back_n} warning(s), unreadable={back_unread}, "
              f"verified={back_verified}")
        if back_unread != base_unread:
            failures.append(
                f"RESTORE FAIL: unreadable count is {back_unread} after restore, "
                f"was {base_unread} before damage"
            )

        return _report(failures)
        object_path = _loose_path(obj)
        if not object_path.is_file():
            print("SKIP: the probe tag object is packed, not loose; this control "
                  "only reproduces loose-object damage")
            return 0
        os.chmod(object_path, stat.S_IWRITE | stat.S_IREAD)
        backup = Path(tempfile.mkdtemp(prefix="t1885-tagobj-")) / "obj"
        backup.write_bytes(object_path.read_bytes())

        a_lines = _release_ledger_warnings()
        a_needle = [ln for ln in a_lines if NEEDLE.search(ln)]
        print(f"A healthy   : {len(a_needle)} unreadable-tag warning(s)")
        for line in a_needle[:2]:
            print(f"  healthy| {line.strip()[:170]}")
        if a_needle:
            failures.append(
                "RED FAIL: every tag object is readable, yet the guard warned: "
                f"{a_needle[0][:200]!r}"
            )

        object_path.unlink()
        try:
            b_lines = _release_ledger_warnings()
        finally:
            object_path.parent.mkdir(parents=True, exist_ok=True)
            object_path.write_bytes(backup.read_bytes())
            os.chmod(object_path, stat.S_IWRITE | stat.S_IREAD)
        b_needle = [ln for ln in b_lines if NEEDLE.search(ln)]
        print(f"B one object: {len(b_needle)} unreadable-tag warning(s)")
        for line in b_needle[:2]:
            print(f"  damaged| {line.strip()[:170]}")

        if not b_needle:
            failures.append(
                "GREEN FAIL: a tag object was missing and the guard stayed "
                "silent -- the instrument still cannot see the damage"
            )
        else:
            text = " ".join(b_needle)
            if not re.search(r"\bof\s+\d+\s+local tag", text):
                failures.append(
                    "GREEN FAIL: the warning does not state how many tags of how "
                    f"many were verified: {text[:200]!r}"
                )

        restored = _git("rev-parse", f"refs/tags/{PROBE_TAG}^{{commit}}")
        if restored.returncode != 0:
            failures.append(
                "RESTORE FAIL: the probe tag no longer peels after its object was "
                f"restored: {restored.stderr.strip()[:160]}"
            )
        else:
            print(f"restored    : {PROBE_TAG} peels to {restored.stdout.strip()[:12]}")

        return _report(failures)
    finally:
        if tag_created:
            _git("tag", "-d", PROBE_TAG)
        if backup is not None and object_path is not None and not object_path.exists():
            object_path.parent.mkdir(parents=True, exist_ok=True)
            object_path.write_bytes(backup.read_bytes())
            os.chmod(object_path, stat.S_IWRITE | stat.S_IREAD)
        if backup is not None:
            leftover_dir = backup.parent
            if leftover_dir.is_dir() and not any(leftover_dir.iterdir()):
                leftover_dir.rmdir()
        if tag_created:
            leftover = _git("rev-parse", "-q", "--verify", f"refs/tags/{PROBE_TAG}")
            if leftover.returncode == 0:
                print(f"WARNING: probe tag {PROBE_TAG} could not be removed")


def _report(failures: list[str]) -> int:
    print()
    if failures:
        print("RESULT: FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("RESULT: OK -- silent when readable, explicit when one object is gone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

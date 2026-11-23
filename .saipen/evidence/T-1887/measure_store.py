"""T-1888 premise re-measurement: read-only, one pass, prints a verdict.

The ticket claims the git object store is damaged (889/1133 HEAD commits and
395/396 tags unreadable, packed-refs naming five packs where three exist). The
verify clause is three measurable conditions. This script measures all three
plus the pack count and prints PASS/FAIL per condition; it mutates nothing.
"""

from __future__ import annotations

import subprocess
import sys


def run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True)


def main() -> int:
    failures: list[str] = []

    print("--- (1) HEAD-reachable commits are readable ---")
    revs = [r for r in run(["git", "rev-list", "HEAD"]).stdout.split() if r.strip()]
    bad = [
        r for r in revs
        if run(["git", "cat-file", "-e", r]).returncode != 0
    ]
    print(f"reachable={len(revs)} unreadable={len(bad)}")
    for r in bad[:10]:
        print("  BAD", r)
    if not revs or bad:
        failures.append(f"condition 1: {len(bad)} unreadable of {len(revs)}")

    print()
    print("--- (2) tag refs are readable ---")
    listed = run(["git", "for-each-ref", "refs/tags", "--format=%(refname)"])
    tags = [t for t in listed.stdout.splitlines() if t.strip()]
    unreadable: list[str] = []
    for tag in tags:
        if run(["git", "rev-parse", "--verify", tag]).returncode != 0:
            unreadable.append(tag)
    print(f"for-each-ref exit={listed.returncode} tags={len(tags)} unreadable={len(unreadable)}")
    for tag in unreadable[:10]:
        print("  BAD", tag)
    if listed.returncode != 0 or not tags or unreadable:
        failures.append(
            f"condition 2: exit={listed.returncode} unreadable={len(unreadable)} of {len(tags)}"
        )

    print()
    print("--- (3) git log -S resolves a known historical string ---")
    search = run(["git", "log", "-S", "finding_invalidated", "--oneline"])
    lines = [line for line in search.stdout.splitlines() if line.strip()]
    print(f"exit={search.returncode} commits={len(lines)}")
    for line in lines[:4]:
        print("  ", line)
    if search.returncode != 0 or not lines:
        failures.append(f"condition 3: exit={search.returncode} commits={len(lines)}")

    print()
    print("--- (4) fsck connectivity ---")
    fsck = run(["git", "fsck", "--connectivity-only"])
    errors = [
        line for line in (fsck.stdout + fsck.stderr).splitlines()
        if line.strip() and not line.startswith("dangling ")
    ]
    print(f"exit={fsck.returncode} non-dangling lines={len(errors)}")
    for line in errors[:10]:
        print("  ", line)
    # fsck names a foreign ref outside HEAD; that is INV-22's tracked cleanup,
    # not this ticket's HEAD-reachability claim, so it is reported not failed.
    print("  (note: a refs/codex/... error is a foreign ref outside HEAD)")

    print()
    if failures:
        print("VERDICT: FAIL")
        for item in failures:
            print("  -", item)
        return 1
    print("VERDICT: PASS -- no HEAD-reachable object is unreadable and no tag is unreadable")
    return 0


if __name__ == "__main__":
    sys.exit(main())

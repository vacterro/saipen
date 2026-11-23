"""Classify a verbose core-unit run by failing-test IDENTITY against the inherited set.

The inherited set is the 34 red identities recorded by T-1379's A/B
(`.saipen/evidence/T-1379-unclosable-ticket-20260917/core-unit-ab-by-identity.txt`),
re-confirmed unchanged by T-1376, T-1378 and this ticket's earlier waves. A count
comparison passes while one red is swapped for another, so this compares names:

    INHERITED   = red now, and in the recorded inherited set
    PATCH_OWNED = red now, a method name the inherited set does not hold
    FIXED       = in the inherited set, not red now (reported, never hidden)

`UNKNOWN` is a red line this parser cannot attribute to a test identity -- a
module import error, a crash without a test header. It is counted, not guessed.

    python core_unit_ab_identity.py <verbose unittest output>
"""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
INHERITED_RECORD = (
    HERE.parents[1] / "T-1379-unclosable-ticket-20260917" / "core-unit-ab-by-identity.txt"
)
HEADER = re.compile(r"^(FAIL|ERROR): (\S+) \(([^)]*)\)")
RESULT = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s")
SUMMARY = re.compile(r"^(OK|FAILED \(.*\))")


def inherited() -> collections.Counter:
    names: collections.Counter = collections.Counter()
    in_list = False
    for line in INHERITED_RECORD.read_text(encoding="utf-8").splitlines():
        if line.startswith("## The inherited red identities"):
            in_list = True
            continue
        if in_list:
            match = re.match(r"^(FAIL|ERROR): (\S+)$", line.strip())
            if match:
                names[match.group(2)] += 1
    return names


def main() -> int:
    text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    reds: list[tuple[str, str, str]] = []
    unknown: list[str] = []
    ran = None
    summary = None
    for line in text.splitlines():
        match = HEADER.match(line)
        if match:
            kind, name, dotted = match.groups()
            if name.startswith(("setUpClass", "setUpModule", "tearDown")) or "." not in dotted:
                unknown.append(line.strip())
            else:
                reds.append((kind, name, dotted))
            continue
        ran_match = RESULT.match(line)
        if ran_match:
            ran = int(ran_match.group(1))
        summary_match = SUMMARY.match(line)
        if summary_match:
            summary = summary_match.group(1)

    base = inherited()
    now = collections.Counter(name for _kind, name, _dotted in reds)
    patch_owned = sorted(
        f"{kind}: {dotted}" for kind, name, dotted in reds if now[name] > base.get(name, 0)
    )
    fixed = sorted(name for name in base if now.get(name, 0) < base[name])

    print(f"inherited record : {INHERITED_RECORD.name} ({sum(base.values())} identities)")
    print(f"current run      : Ran {ran}, {summary}")
    print(f"red identities   : {len(reds)}")
    print(f"PATCH_OWNED      : {len(patch_owned)}")
    for item in patch_owned:
        print(f"    {item}")
    print(f"UNKNOWN          : {len(unknown)}")
    for item in unknown:
        print(f"    {item}")
    print(f"FIXED (inherited, green now): {len(fixed)}")
    for item in fixed:
        print(f"    {item}")
    return 0 if not patch_owned and not unknown else 1


if __name__ == "__main__":
    raise SystemExit(main())

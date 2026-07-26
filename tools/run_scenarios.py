#!/usr/bin/env python
"""Run every executable conformance fixture and compare to its declaration.

Stdlib only. Run from the SAIPEN home:

    python tools/run_scenarios.py

`tests/scenarios/` holds two kinds of fixture. Behavioral ones are README-only
-- the assertion is about agent decision-making, which no script can judge --
and are skipped here. Structural ones ship a real `.saipen/` and declare the
outcome they expect on a line of their own README:

    expect: pass      the state is valid; tools/validate.py must exit 0
    expect: fail      the state carries the defect the fixture exists to
                      demonstrate; validate.py must exit non-zero

A fixture with a `.saipen/` and no `expect:` line is itself an error: an
un-declared fixture cannot be checked, and silently skipping it is how this
whole directory sat unexecuted for months (CONFORMANCE.md's "honest status"
note, v7.75.0).

Exit code is non-zero if any fixture's real outcome differs from its
declaration, so CI fails on it like any other gate.
"""

import re
import subprocess
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
VALIDATOR = HOME / "tools" / "validate.py"
SCENARIOS = HOME / "tests" / "scenarios"

EXPECT_RE = re.compile(r"^expect:\s*(pass|fail)\s*$", re.M)

if not SCENARIOS.is_dir():
    print(f"FAIL: no {SCENARIOS} -- run this from the SAIPEN home")
    sys.exit(1)

failures = []
checked = skipped = 0

for d in sorted(p for p in SCENARIOS.iterdir() if p.is_dir()):
    readme = d / "README.md"
    has_state = (d / ".saipen").is_dir()
    declared = None
    if readme.is_file():
        m = EXPECT_RE.search(readme.read_text(encoding="utf-8-sig"))
        declared = m.group(1) if m else None

    if not has_state:
        # Behavioral fixture. It must NOT declare an expectation -- there is
        # nothing to run, so a declaration here would be a promise no one keeps.
        if declared:
            failures.append(f"{d.name}: declares 'expect: {declared}' but ships "
                            f"no .saipen/ -- nothing to run")
        else:
            skipped += 1
        continue

    if declared is None:
        failures.append(f"{d.name}: ships a .saipen/ but declares no "
                        f"'expect: pass|fail' line -- cannot be checked")
        continue

    r = subprocess.run([sys.executable, str(VALIDATOR)], cwd=d,
                       capture_output=True, text=True)
    actual = "pass" if r.returncode == 0 else "fail"
    checked += 1
    if actual != declared:
        detail = ""
        for line in (r.stdout + r.stderr).splitlines():
            if line.startswith("FAIL"):
                detail = f" | first FAIL: {line[:120]}"
                break
        failures.append(f"{d.name}: declared '{declared}', got '{actual}' "
                        f"(validator exit {r.returncode}){detail}")
    else:
        print(f"PASS: {d.name} -- expected {declared}, got {actual}")

print(f"\n{checked} executable fixture(s) checked, "
      f"{skipped} behavioral fixture(s) skipped (README-only by design)")

if failures:
    print(f"\nFAILED: {len(failures)} fixture(s) disagree with their declaration")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)

if checked == 0:
    # A run that checked nothing is not a pass (phases/verify.md: a gate that
    # cannot fail is not a gate).
    print("FAILED: no executable fixtures found -- this suite collected 0 tests")
    sys.exit(1)

print("All fixtures match their declared outcome.")

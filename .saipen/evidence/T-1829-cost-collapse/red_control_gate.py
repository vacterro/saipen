"""RED control for the T-1829 publication wiring.

Each case mutates ONE fact of the live implementation, runs the test that is
supposed to notice, and restores the exact bytes. A case that stays green
means the test does not actually witness the behavior it claims.

Run: python .saipen/evidence/T-1829-cost-collapse/red_control_gate.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / "tools" / "saipen_engine" / "release.py"

# (label, old, new, test target, why this mutation should be caught)
CASES = [
    (
        "publication gate not consulted",
        '        problem = focused_unit.publication_gate(root)',
        '        problem = None  # RED CONTROL: gate detached',
        "tools.test_t1828_verification_policy.PublicationWiringTests",
        "release refuses before the external validator",
    ),
    (
        "gate consults the project copy",
        '    home = Path(__file__).resolve().parents[2]',
        '    home = Path(root).resolve()  # RED CONTROL: subject judges itself',
        "tools.test_t1750_release_boundary.RuntimeValidatorTests",
        "a downstream validator cannot replace the runtime gate",
    ),
    (
        "project root not forwarded",
        '        command += ["--project-root", str(project)]',
        '        pass  # RED CONTROL: managed project never named',
        "tools.test_t1750_release_boundary.RuntimeValidatorTests",
        "the managed project is named to the runtime validator",
    ),
]


def main() -> int:
    original = RELEASE.read_bytes()
    failures = []
    try:
        for label, old, new, target, why in CASES:
            text = original.decode("utf-8")
            if old not in text:
                print(f"SKIP  {label}: anchor missing")
                failures.append(label)
                continue
            RELEASE.write_bytes(text.replace(old, new, 1).encode("utf-8"))
            run = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", target],
                cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            caught = run.returncode != 0
            print(f"{'RED  ' if caught else 'GREEN'} {label} -> {why}")
            if not caught:
                failures.append(label)
    finally:
        RELEASE.write_bytes(original)

    restored = RELEASE.read_bytes() == original
    print(f"restored byte-identically: {restored}")
    if not restored or failures:
        print(f"FAIL: {len(failures)} mutation(s) survived; record not trustworthy")
        return 1
    print(f"PASS: all {len(CASES)} mutations were caught; implementation restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

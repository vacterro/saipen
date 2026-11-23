#!/usr/bin/env python
"""T-1942's one verifier: the same judgement over pre-fix and post-fix bytes.

Two reds were recorded against this ticket and they have different subjects, so
the verifier states both and neither can be satisfied by the other:

  BUDGET   `protocol_budget.check` reports no route over its frozen ceiling.
  FIXTURE  the four downstream fixtures still prove their layer. Under the
           pre-fix file they build their input with `render_boundary`, which
           since T-1916 refuses an autonomous handback, so they fail; under the
           post-fix file they assemble the same wire text without asking the
           renderer for a verdict.

Exit 0 only when both hold. This is deliberately NOT a substring match on the
source: the FIXTURE half runs pytest on the real file, so it measures behaviour.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"

SELECTION = (
    "autonomous_repair_is_not_a_response_boundary or "
    "public_autonomy_gate_reads_current_route or "
    "opencode_command_enforces_autonomy_on_its_followup_response or "
    "opencode_explicit_status_request_keeps_the_control_surface"
)


def budget() -> tuple[bool, str]:
    sys.path.insert(0, str(TOOLS))
    import protocol_budget

    errors = protocol_budget.check(ROOT / "saipen")
    return not errors, "budget: " + ("PASS" if not errors else "; ".join(errors))


def fixtures() -> tuple[bool, str]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(TOOLS / "test_response_surface_contract.py"),
            "-q",
            "-k",
            SELECTION,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    tail = [line for line in proc.stdout.strip().splitlines() if line.strip()][-1:]
    return proc.returncode == 0, "fixtures: " + (tail[0] if tail else "no output")


def main() -> int:
    ok_budget, budget_line = budget()
    ok_fixtures, fixture_line = fixtures()
    print(budget_line)
    print(fixture_line)
    verdict = "PASS" if ok_budget and ok_fixtures else "FAIL"
    print(f"VERDICT: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

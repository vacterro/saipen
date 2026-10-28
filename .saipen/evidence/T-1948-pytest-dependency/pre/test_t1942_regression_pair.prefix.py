"""T-1942's pair oracle: the two reds this ticket was filed for, measured.

The ticket exists because two INDEPENDENT assertions in the routine gate went
red on one tree: `protocol_budget` measured `ship_improve` past its frozen
ceiling because of the pending OPS.md wave, and four fixtures in
`test_response_surface_contract.py` built their input with `render_boundary`,
which since T-1916 refuses exactly that input. The fix touches both files, so a
regression pair for this ticket has to prove BOTH moved, and it has to prove it
with ONE verifier -- otherwise the green half can be produced by repairing only
the cheaper of the two.

`saipen work regression` runs this file twice: once over the pre-fix bytes of
both subjects and once over the current ones. The pair is admissible only if
this file is red on the first run and green on the second, so each method here
is a claim the fix is responsible for.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

#: The four fixtures T-1916 left red. Named by test, not by line, so the
#: selection survives unrelated edits to the file around them.
SELECTION = (
    "autonomous_repair_is_not_a_response_boundary or "
    "public_autonomy_gate_reads_current_route or "
    "opencode_command_enforces_autonomy_on_its_followup_response or "
    "opencode_explicit_status_request_keeps_the_control_surface"
)


class RegressionPairTests(unittest.TestCase):
    def test_no_declared_load_route_exceeds_its_frozen_ceiling(self):
        sys.path.insert(0, str(TOOLS))
        import protocol_budget

        self.assertEqual(protocol_budget.check(ROOT / "saipen"), [])

    def test_the_four_downstream_fixtures_still_assert_their_layer(self):
        # Behaviour, not a source substring: the pre-fix file passes the same
        # text to a renderer that now refuses it, and only running the file
        # shows that.
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
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
            timeout=600,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()

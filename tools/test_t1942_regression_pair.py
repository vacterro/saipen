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

import io
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

#: The four fixtures T-1916 left red. Named by their method suffix, not by line,
#: so the selection survives unrelated edits to the file around them.
SELECTION = (
    "autonomous_repair_is_not_a_response_boundary",
    "public_autonomy_gate_reads_current_route",
    "opencode_command_enforces_autonomy_on_its_followup_response",
    "opencode_explicit_status_request_keeps_the_control_surface",
)

#: The subject is a plain unittest module, so the pair runs its four fixtures
#: with the same stdlib runner the declared family uses. Spawning `-m pytest`
#: made this test's verdict a fact about the INTERPRETER's installed packages
#: rather than about the fixtures (T-1948): the shipped launcher carries no
#: pytest, so the whole family went red on a module it can run directly.
#:
#: The subject is loaded from its FILE and the methods are selected on the
#: loaded class, because the dotted-name routes are ambiguous here: the module
#: must be importable as both `test_response_surface_contract` (from `tools/`)
#: and `tools.test_response_surface_contract` (from the root) depending on the
#: caller, and each spelling resolves a DIFFERENT class object.
SUBJECT_PATH = TOOLS / "test_response_surface_contract.py"
SUBJECT_CLASS = "SurfaceBehaviourTests"

#: Two of the four are `@unittest.skipUnless(shutil.which("node"))`. They cannot
#: assert anything on a host without node, and a green that counted them as
#: covered would be a fact about the host -- the same defect as the pytest
#: dependency this ticket removes. The skip is therefore accepted, but only when
#: node's absence is what caused it.
NODE_GATED = frozenset(
    {
        "opencode_command_enforces_autonomy_on_its_followup_response",
        "opencode_explicit_status_request_keeps_the_control_surface",
    }
)


def _load_subject():
    """The subject module loaded by path, regardless of the caller's cwd."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_t1942_regression_subject", SUBJECT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _DevNull(io.StringIO):
    """Discard the runner's narration; failures are reported by the assertion."""


class RegressionPairTests(unittest.TestCase):
    def test_no_declared_load_route_exceeds_its_frozen_ceiling(self):
        sys.path.insert(0, str(TOOLS))
        import protocol_budget

        self.assertEqual(protocol_budget.check(ROOT / "saipen"), [])

    def test_the_four_downstream_fixtures_still_assert_their_layer(self):
        # Behaviour, not a source substring: the assertion has to survive the
        # subject actually running, because a fixture can keep its text while
        # the layer under it stops refusing that text.
        module = _load_subject()
        subject_class = getattr(module, SUBJECT_CLASS)
        suite = unittest.TestSuite(
            subject_class("test_" + name) for name in SELECTION
        )
        result = unittest.TextTestRunner(stream=_DevNull(), verbosity=0).run(suite)
        detail = "\n".join(f"{test}: {err}" for test, err in result.failures + result.errors)
        self.assertTrue(result.wasSuccessful(), detail)
        # A runner that silently selected nothing would pass and prove nothing,
        # so the count is asserted, not assumed.
        self.assertEqual(result.testsRun, len(SELECTION))
        skipped = {
            str(test).split()[0].rsplit(".", 1)[-1].removeprefix("test_")
            for test, _reason in result.skipped
        }
        if skipped:
            self.assertFalse(
                shutil.which("node"),
                "these fixtures were skipped although node IS available: " + repr(sorted(skipped)),
            )
            self.assertTrue(skipped <= set(SELECTION) & NODE_GATED, skipped)


if __name__ == "__main__":
    unittest.main()

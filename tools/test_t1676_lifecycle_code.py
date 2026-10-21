"""T-1676: the lifecycle refusal is a registered code of its own.

T-1672 named the class UNAUTHORIZED_LIFECYCLE_WRITE only in the reason and the
detail and refused with PROTOCOL_STATE_INVALID, because `command_resolution`
stood 10 bytes under its budget and a registry code costs 34. With the route
budgets in place (T-1670) the class is the code: status and every refused verb
return it, it is registered (no `unregistered_code` marker), fleet maps it to
the state surface as an operator decision, and every route budget still PASSes.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
import protocol_budget  # noqa: E402
from saipen_engine import fleet  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1671_lifecycle_authority import AGENT, _bytes, _project, _type_the_lifecycle  # noqa: E402

CODE = "UNAUTHORIZED_LIFECYCLE_WRITE"


def setUpModule() -> None:
    isolate_host_session()


class RegisteredCodeTests(unittest.TestCase):
    def test_the_code_is_registered(self):
        registry = json.loads((ROOT / "saipen" / "REGISTRY.json").read_text(encoding="utf-8"))
        self.assertIn(CODE, registry["error_codes"])

    def test_fleet_maps_it_to_the_state_surface_as_an_operator_decision(self):
        self.assertEqual(fleet._BLOCKING_SURFACE.get(CODE), "state")
        self.assertIn(CODE, fleet._OPERATOR_DECISION_CODES)

    def test_every_route_budget_still_passes(self):
        self.assertEqual(protocol_budget.check(ROOT / "saipen"), [])


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.root = _project()
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        _type_the_lifecycle(self.root)

    def cli(self, *args):
        return probes.cli(self.root, AGENT, *args)

    def test_status_and_every_refused_verb_return_the_class_as_the_code(self):
        before = _bytes(self.root)
        status = self.cli("status")
        self.assertEqual((status.get("ok"), status.get("code")), (False, CODE), status)
        self.assertEqual(status.get("action"), "saipen recover", status)
        for args in (
            ("transition", "SCOUT", "next"),
            ("checkpoint", "RUN", "T-001", "a note after the fact"),
            ("ticket", "add", "P2", "more work", "--verify", "it works"),
            ("ticket", "done", "T-001", "--closure-mode", "own_patch"),
            ("claim", "T-001"),
        ):
            with self.subTest(args=args):
                answer = self.cli(*args)
                self.assertEqual((answer.get("ok"), answer.get("code")), (False, CODE), answer)
                self.assertNotIn("unregistered_code", answer, answer)
        self.assertEqual(_bytes(self.root), before)


if __name__ == "__main__":
    unittest.main()

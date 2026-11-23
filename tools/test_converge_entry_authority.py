"""Converge entry must project the gated route, not the raw one.

Measured (T-2081): on a CURRENT_FAIL project, `set_converge_intent` wrote
`next_action: saipen crew` (target crew) or `saipen continue` (target done)
while `router.gate_route` on the same bytes refused the route with no
executable command. A host that reads STATE.next_action re-dispatches the
refused action against unchanged bytes, so the retry is a stall, not progress.

The contract pinned here: the converge-family writers store the action the ONE
gate chain admits; a refused route becomes a typed `WAIT:` under the closed
section 1.2 grammar, never a dispatchable command.

Run standalone:
    python -m unittest tools.test_converge_entry_authority
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
for _entry in (str(TOOLS), str(TOOLS.parent)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import operations  # noqa: E402
from saipen_engine import state as S  # noqa: E402
from test_t1412_conformance_truth import T1412Base, write_receipt  # noqa: E402


class ConvergeEntryAuthorityTests(T1412Base):
    def _enter(self, name: str, verdict: str, target: str) -> Path:
        root = self.make_project(name)
        write_receipt(root, verdict)
        result = operations.set_converge_intent(root, "tester", target)
        self.assertTrue(result.ok, result.message)
        return root

    def _next_action(self, root: Path) -> str:
        state = S.parse_state(
            (root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")
        )
        return str(state.get("next_action") or "")

    def _assert_wait(self, action: str) -> None:
        self.assertTrue(action.startswith("WAIT:"), action)
        self.assertIsNone(S.wait_grammar_error(action), action)
        # A refused converge route is not a pre-authorized stop: no consumer
        # may read it as permission to continue.
        self.assertNotIn(S.parse_wait(action), {"init"})

    def test_crew_entry_does_not_advertise_a_refused_route(self):
        root = self._enter("crew-fail", "FAIL", "crew")
        action = self._next_action(root)
        self.assertNotEqual(action, "saipen crew")
        self._assert_wait(action)
        self.assertIn("conformance", action)

    def test_done_entry_does_not_advertise_a_refused_continuation(self):
        root = self._enter("done-fail", "FAIL", "done")
        action = self._next_action(root)
        self.assertNotEqual(action, "saipen continue")
        self._assert_wait(action)

    def test_clean_conformance_keeps_both_routes(self):
        # The gate is asked about the PRE-write bytes: a CURRENT_PASS receipt
        # stands there, so the command is legal when it is written. The
        # post-write PASS staleness is CORE-001's checkpoint-hash rule.
        crew = self._enter("crew-pass", "PASS", "crew")
        self.assertEqual(self._next_action(crew), "saipen crew")
        done = self._enter("done-pass", "PASS", "done")
        self.assertEqual(self._next_action(done), "saipen continue")

    def test_finalize_does_not_advertise_a_refused_continuation(self):
        root = self._enter("finalize-fail", "FAIL", "done")
        result = operations.finalize_converge_intent(
            root, "tester", "done", "done: probe finalization"
        )
        self.assertTrue(result.ok, result.message)
        self._assert_wait(self._next_action(root))


if __name__ == "__main__":
    unittest.main()

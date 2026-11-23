"""T-2170 regression: phase-aware admission and executable routing.

RED (pre-fix):
  * router.route_next() over CLEAN + a workable TODO returns
    `PHASE SCOUT <ticket>` -- an action the DFA refuses.
  * entry.start_work() over CLEAN admits the Work, then returns
    VALIDATION_FAILED "CLEAN -> SCOUT not allowed", hiding the durable
    ticket behind a failed start and inviting a duplicate retry.

GREEN (post-fix):
  * route_next() returns the CURRENT phase as the executable action, with
    the DFA and phase document as the authority and the ticket queued.
  * start_work() returns ok:true USER_REQUEST_QUEUED, work_claimed:false,
    naming the phase that owns execution; no illegal transition is attempted.

The DFA itself is asserted unchanged: CLEAN -> SCOUT stays illegal.

Run: python -B <this file>  (the pen module is selected via sys.path).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

PEN_ROOT = Path(__file__).absolute().parent
TOOLS = Path.cwd() / "tools"
if not (TOOLS / "test_guard_hostile_matrix.py").is_file():
    TOOLS = PEN_ROOT.parents[7] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _load_pen_engine():
    """Load ONLY router/entry from the pen; the rest stays live."""
    import saipen_engine
    from saipen_engine import phases

    for name in ("router", "entry"):
        spec = importlib.util.spec_from_file_location(
            f"saipen_engine.{name}", PEN_ROOT / "saipen_engine" / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        module.__package__ = "saipen_engine"
        spec.loader.exec_module(module)
        setattr(saipen_engine, name, module)
        sys.modules[f"saipen_engine.{name}"] = module
    return phases


class CleanPhaseRoutingTests(unittest.TestCase):
    def setUp(self):
        import sys as _sys
        assert str(TOOLS) in _sys.path, ("TOOLS not on path", str(TOOLS), _sys.path[:5])
        from test_guard_hostile_matrix import fresh_project
        from test_hermetic_env import isolate_host_session

        isolate_host_session()
        self.root = fresh_project(phase="CLEAN", task="none", next_action="PHASE CLEAN")
        board = self.root / ".saipen" / "BOARD.md"
        board.write_text(
            "## DOING\n## TODO\n"
            "- [ ] T-1 [P2] clean probe | verify: the requested change is present "
            "and demonstrated against the user own description of it | "
            "request_witness: model_supplied | source_receipts: SRC-001\n"
            "## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )

    def _state_text(self):
        return (self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")

    def _board_text(self):
        return (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig")

    def test_dfa_forbids_clean_to_scout(self):
        phases = _load_pen_engine()
        self.assertFalse(phases.transition_legal("CLEAN", "SCOUT"))
        self.assertTrue(phases.transition_legal("CLEAN", "DONE"))

    def test_router_names_current_phase_not_illegal_scout(self):
        _load_pen_engine()
        from saipen_engine.router import route_next

        route = route_next(self._state_text(), self._board_text())
        self.assertEqual(route.get("action"), "PHASE CLEAN")
        self.assertEqual(route.get("queued_ticket"), "T-1")
        self.assertEqual(route.get("load"), "saipen/phases/clean.md")
        self.assertNotIn("SCOUT", str(route.get("action")))

    def test_router_after_legal_clean_exit_admits_scout(self):
        _load_pen_engine()
        from saipen_engine.router import route_next

        state = self._state_text().replace("phase: CLEAN", "phase: DONE")
        route = route_next(state, self._board_text())
        self.assertEqual(route.get("action"), "PHASE SCOUT T-1")

    def test_start_queues_work_instead_of_misleading_refusal(self):
        _load_pen_engine()
        from saipen_engine.entry import start_work

        result = start_work(
            self.root,
            "test-agent",
            actor_source="inherited",
            text="a new task submitted while CLEAN owns the session",
        )
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result.get("code"), "USER_REQUEST_QUEUED")
        self.assertFalse(result.get("work_claimed"))
        self.assertEqual(result.get("current_phase"), "CLEAN")
        self.assertEqual(result.get("next_action"), "PHASE CLEAN")
        self.assertTrue(result.get("ticket"))
        # The Work is durably queued in TODO, never claimed into SCOUT.
        board = self._board_text()
        self.assertIn("- [ ] " + result["ticket"], board)
        self.assertNotIn("- [/] " + result["ticket"], board)


if __name__ == "__main__":
    unittest.main(verbosity=2)

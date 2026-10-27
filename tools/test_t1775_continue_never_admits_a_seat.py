"""T-1775: continue on a cycle in flight never prescribes an act that admits a seat.

Bare `saipen improve` resumes only a seat of this agent's family whose report
holds no audit content; otherwise it admits a NEW core seat. `continue`
answered every cycle in flight with that bare form, so in _SAIRELAY, where the
only seat was complete and the cycle waited on its Core sweep, obeying the
router grew the roster 1 -> 2 with a zero-RUN draft, and later to 3
(imp-_sairelay-20261013-1 saipen-cli-02 RUN-1/IMP-001; SRC-248 R007).

The oracle obeys the router: it executes the action `continue` prints and
counts the roster afterwards.
"""

from __future__ import annotations

import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import improve  # noqa: E402
import test_continue_improve_fallthrough as _fallthrough  # noqa: E402

_invoke_cli = _fallthrough._invoke_cli

FINDING = (
    "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
    "expected: probe expected\nactual: probe actual\nevidence: probe evidence\n"
)


class ContinueNeverAdmitsASeat(unittest.TestCase):
    # The fallthrough suite's fixture project, borrowed by attribute: binding
    # its TestCase class here would collect that suite a second time.
    _make = _fallthrough.ContinueImproveFallthroughTests._make
    _board = staticmethod(_fallthrough.ContinueImproveFallthroughTests._board)

    def setUp(self) -> None:
        config = tempfile.TemporaryDirectory(prefix="saipen-test-user-config-")
        self.addCleanup(config.cleanup)
        patcher = mock.patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": config.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _cycle(self, name: str) -> tuple[Path, str, Path]:
        """A project whose first `cc` prepared one cycle with one seat of `tester`."""
        root = self._make(name, board=self._board())
        rc, first = _invoke_cli(root, "cc")
        self.assertEqual((rc, first.get("code")), (0, "IMPROVE_AUDIT_ASSIGNMENT"), first)
        return root, first["cycle_id"], root / first["report_path"]

    def _roster(self, root: Path, cycle: str) -> list[str]:
        manifest = improve.cycle_dir(root, cycle) / "MANIFEST.md"
        return [
            improve._field(block, "seat_id")
            for block in improve._seat_blocks(manifest.read_text(encoding="utf-8-sig"))
        ]

    def _route(self, root: Path) -> dict:
        rc, routed = _invoke_cli(root, "cc")
        self.assertEqual((rc, routed.get("code")), (0, "CONTINUE_IMPROVE_IN_FLIGHT"), routed)
        return routed

    def _obey(self, root: Path, action: str) -> dict:
        words = shlex.split(action)
        self.assertEqual(words[0], "saipen", action)
        rc, result = _invoke_cli(root, *words[1:])
        self.assertEqual(rc, 0, result)
        return result

    def test_a_complete_roster_routes_to_the_core_sweep(self) -> None:
        # The reported case: the only seat is complete with an unswept finding.
        root, cycle, report = self._cycle("complete")
        improve.append_run(report, FINDING)
        improve.complete_report(report)
        routed = self._route(root)
        self.assertEqual(routed["action"], f"saipen improve sweep-queue {cycle}", routed)

    def test_obeying_the_router_on_a_complete_roster_never_grows_it(self) -> None:
        root, cycle, report = self._cycle("obey-complete")
        improve.append_run(report, FINDING)
        improve.complete_report(report)
        before = self._roster(root, cycle)
        for _ in range(2):
            self._obey(root, self._route(root)["action"])
        self.assertEqual(self._roster(root, cycle), before)

    def test_an_incomplete_seat_of_this_family_resumes_by_its_session(self) -> None:
        root, cycle, _report = self._cycle("draft")
        seat = self._roster(root, cycle)[0]
        routed = self._route(root)
        self.assertEqual(routed["action"], f"saipen improve --session {seat}", routed)
        for _ in range(2):
            result = self._obey(root, routed["action"])
            self.assertEqual((result.get("seat_id"), result.get("resumed")), (seat, True), result)
        self.assertEqual(self._roster(root, cycle), [seat])

    def test_a_met_bar_routes_to_completion(self) -> None:
        root, cycle, report = self._cycle("bar")
        improve.append_run(report, "NO_FINDINGS -- probe audited the fixture and found nothing")
        improve.complete_report(report)
        self.assertEqual(improve.verify_cycle(improve.cycle_dir(root, cycle)), [])
        routed = self._route(root)
        self.assertEqual(routed["action"], f"saipen improve cycle-complete {cycle}", routed)

    def test_another_agents_incomplete_seat_is_not_taken_over(self) -> None:
        root, cycle, report = self._cycle("foreign")
        improve.append_run(report, "NO_FINDINGS -- probe audited the fixture and found nothing")
        improve.complete_report(report)
        improve.register_seat(
            improve.cycle_dir(root, cycle), "other-01", "core", "saipen_improve_SAIPEN.md"
        )
        routed = self._route(root)
        self.assertEqual(routed["action"], "saipen improve status", routed)
        self.assertIn("other-01", routed["detail"])

    def test_the_detail_no_longer_advises_the_bare_form(self) -> None:
        root, _cycle, report = self._cycle("detail")
        improve.append_run(report, FINDING)
        improve.complete_report(report)
        self.assertNotIn("(saipen improve)", self._route(root)["detail"])

    def test_an_unreadable_cycle_answers_read_only(self) -> None:
        # The one thing this route never does is admit, a fault included.
        root, _cycle, report = self._cycle("fault")
        improve.append_run(report, FINDING)
        improve.complete_report(report)
        with mock.patch.object(improve, "verify_cycle", side_effect=OSError("probe")):
            routed = self._route(root)
        self.assertEqual(routed["action"], "saipen improve status", routed)


if __name__ == "__main__":
    unittest.main()

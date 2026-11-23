"""T-1784: an Improve mutator's dry run answers the verdict its real call would.

`saipen improve <mutator> --dry-run` was answered by a separate planner that
checked only argument grammar, so on _SAIRELAY's active cycle
`improve cycle-complete --dry-run` answered `ok`, `DRY_RUN_PLAN`, "planned cycle
ACTIVE -> COMPLETE" while the cycle bar failed (reported there as
saipen-cli-03 RUN-1/IMP-001; reproduced read-only on 2026-10-14). A plan that
promises what the real call refuses is a false success.

The oracle compares both surfaces of the same command on the same bytes: a
refusal must be the real call's own refusal, a plan must leave every byte in
place, and the real call after a plan must do what the plan said.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_improve_reconcile as _reconcile  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _digest(root: Path) -> str:
    """Every byte under the project's .saipen, so a plan provably writes nothing."""
    digest = hashlib.sha256()
    for path in sorted((root / ".saipen").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class DryRunIsTheRealVerdict(unittest.TestCase):
    # The reconcile suite's fixture, borrowed by attribute: binding its
    # TestCase class here would collect that suite a second time.
    _project = _reconcile.ReconcileTests._project
    _cycle = _reconcile.ReconcileTests._cycle
    _run_text = staticmethod(_reconcile.ReconcileTests._run_text)
    _add_seat = _reconcile.ReconcileTests._add_seat
    _add_idle_seat = _reconcile.ReconcileTests._add_idle_seat
    _dispose = _reconcile.ReconcileTests._dispose
    _move_tree = _reconcile.ReconcileTests._move_tree
    _cli = staticmethod(_reconcile.ReconcileTests._cli)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1784-")
        self.addCleanup(self._tmp.cleanup)

    def _refused_alike(self, root: Path, *argv: str) -> dict:
        before = _digest(root)
        dry_rc, dry, _ = self._cli(root, *argv, "--dry-run")
        self.assertEqual(_digest(root), before, "a dry run wrote")
        real_rc, real, _ = self._cli(root, *argv)
        self.assertEqual(_digest(root), before, "a refused call wrote")
        self.assertNotEqual(real_rc, 0, real)
        self.assertEqual(
            (dry_rc, dry.get("ok"), dry.get("code"), dry.get("detail")),
            (real_rc, real.get("ok"), real.get("code"), real.get("detail")),
        )
        return dry

    def _planned_then_done(self, root: Path, *argv: str) -> tuple[dict, dict]:
        before = _digest(root)
        dry_rc, dry, _ = self._cli(root, *argv, "--dry-run")
        self.assertEqual((dry_rc, dry.get("code")), (0, "DRY_RUN_PLAN"), dry)
        self.assertEqual(_digest(root), before, "a dry run wrote")
        real_rc, real, _ = self._cli(root, *argv)
        self.assertEqual(real_rc, 0, real)
        self.assertNotEqual(_digest(root), before, "the planned call did nothing")
        return dry, real

    def test_cycle_complete_plan_refuses_a_failing_bar(self) -> None:
        # The reported case: a cycle whose bar fails is never planned COMPLETE.
        root = self._project()
        cycle = self._cycle(root)
        self._add_seat(root, cycle, "probe-01", findings=1)
        refused = self._refused_alike(root, "improve", "cycle-complete", cycle.name)
        self.assertIn("cycle bar is unmet", refused.get("detail", ""))

    def test_cycle_complete_plan_matches_a_met_bar(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_seat(root, cycle, "probe-01", findings=0)
        self._planned_then_done(root, "improve", "cycle-complete", cycle.name)
        manifest = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        self.assertIn("cycle_status: complete", manifest)

    def test_abort_plan_refuses_a_started_sweep(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_seat(root, cycle, "probe-01", findings=1)
        self._dispose(cycle, "probe-01", 1)
        refused = self._refused_alike(root, "improve", "abort", cycle.name)
        self.assertIn("sweep ledger already carries dispositions", refused.get("detail", ""))

    def test_abort_plan_matches_a_stuck_draft(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_idle_seat(root, cycle, "probe-01")
        self._planned_then_done(root, "improve", "abort", cycle.name)

    def test_retire_plan_refuses_the_last_reportable_seat(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_idle_seat(root, cycle, "probe-01")
        refused = self._refused_alike(
            root, "improve", "retire", cycle.name, "probe-01", "--reason", "EMPTY_DRAFT"
        )
        self.assertIn("no expected seat would remain", refused.get("detail", ""))

    def test_complete_plan_refuses_an_unmet_completion_bar(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_idle_seat(root, cycle, "probe-01")
        self._refused_alike(root, "improve", "complete", cycle.name, "probe-01", "PROBE")

    def test_submit_plan_refuses_what_append_refuses_and_plans_the_rest(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_idle_seat(root, cycle, "probe-01")
        smuggled = Path(self._tmp.name) / "smuggled.json"
        smuggled.write_text(json.dumps({"run_text": "## RUN 7\n\nNO_FINDINGS\n"}), encoding="utf-8")
        self._refused_alike(
            root, "improve", "submit", cycle.name, "probe-01", "PROBE", str(smuggled)
        )
        clean = Path(self._tmp.name) / "clean.json"
        clean.write_text(json.dumps({"run_text": self._run_text(0)}), encoding="utf-8")
        self._planned_then_done(
            root, "improve", "submit", cycle.name, "probe-01", "PROBE", str(clean)
        )

    def test_rebind_plan_refuses_a_current_identity(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_idle_seat(root, cycle, "probe-01")
        self._refused_alike(root, "improve", "rebind", cycle.name, "probe-01", "PROBE")

    def test_rebind_plan_matches_a_moved_protocol_identity(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        report = self._add_idle_seat(root, cycle, "probe-01")
        text = report.read_text(encoding="utf-8")
        moved = re.sub(
            r"(?m)^protocol_fingerprint:.*$", "protocol_fingerprint: sha256:" + "0" * 64, text
        )
        self.assertNotEqual(moved, text, "the fixture report carries no protocol_fingerprint")
        report.write_text(moved, encoding="utf-8")
        self._planned_then_done(root, "improve", "rebind", cycle.name, "probe-01", "PROBE")

    def test_retire_plan_matches_a_spare_seat(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_seat(root, cycle, "probe-01", findings=0)
        self._add_idle_seat(root, cycle, "probe-02")
        self._planned_then_done(
            root, "improve", "retire", cycle.name, "probe-02", "--reason", "EMPTY_DRAFT"
        )

    def test_complete_plan_matches_a_report_that_meets_its_bar(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_seat(root, cycle, "probe-01", findings=0, complete=False)
        self._planned_then_done(root, "improve", "complete", cycle.name, "probe-01", "PROBE")

    def test_stale_complete_supersession_plan_matches_the_binding(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_seat(root, cycle, "probe-01", findings=0)
        self._move_tree(root)
        self._add_seat(root, cycle, "probe-02", findings=0)
        self._planned_then_done(
            root,
            "improve",
            "retire",
            cycle.name,
            "probe-01",
            "--reason",
            "STALE_COMPLETE",
            "--replacement",
            "probe-02",
        )


if __name__ == "__main__":
    unittest.main()

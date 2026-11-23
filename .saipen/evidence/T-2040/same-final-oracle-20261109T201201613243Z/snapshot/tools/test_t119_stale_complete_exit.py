"""T-119: bounded evidence-preserving exit for a stale COMPLETE improve cycle.

When an active cycle's only complete reports are identity-stale (source tree
or protocol fingerprint drift) and all findings have final Core dispositions
(or zero findings), abort archives the cycle with `cycle_aborted:
stale-complete-preserved`, byte-preserving all report and sweep evidence.
Unswept findings still refuse abort.
`continue_fallback.resume_action` routes to `saipen improve abort <cycle>`
instead of looping on `sweep-queue`.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import improve  # noqa: E402
import test_improve_reconcile as _reconcile  # noqa: E402
from saipen_engine.continue_fallback import resume_action  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class StaleCompleteExitTests(unittest.TestCase):
    _project = _reconcile.ReconcileTests._project
    _cycle = _reconcile.ReconcileTests._cycle
    _run_text = staticmethod(_reconcile.ReconcileTests._run_text)
    _add_seat = _reconcile.ReconcileTests._add_seat
    _add_idle_seat = _reconcile.ReconcileTests._add_idle_seat
    _dispose = _reconcile.ReconcileTests._dispose
    _move_tree = _reconcile.ReconcileTests._move_tree

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t119-")
        self.addCleanup(self._tmp.cleanup)

    def _cli(self, root: Path, *words: str) -> tuple[int, dict]:
        done = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), *words, "--json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        return done.returncode, json.loads(done.stdout)

    def test_validate_manifest_accepts_stale_complete_preserved(self) -> None:
        text = (
            "# IMPROVE CYCLE ROSTER\n\n"
            "created_at: 2026-10-17T00:00:00Z\n"
            "project_identity: probe-project\n"
            "cycle_status: archived\n"
            "seat_id: probe-01\n"
            "role: core\n"
            "report_path: saipen_improve_PROBE.md\n"
            "availability: expected\n"
            "cycle_aborted: stale-complete-preserved\n"
        )
        errors = improve.validate_manifest(text, expected_cycle_id="imp-probe-1")
        self.assertEqual(errors, [])

    def test_validate_manifest_rejects_unknown_cycle_aborted(self) -> None:
        text = (
            "# IMPROVE CYCLE ROSTER\n\n"
            "created_at: 2026-10-17T00:00:00Z\n"
            "project_identity: probe-project\n"
            "cycle_status: archived\n"
            "seat_id: probe-01\n"
            "role: core\n"
            "report_path: saipen_improve_PROBE.md\n"
            "availability: expected\n"
            "cycle_aborted: unknown-marker\n"
        )
        errors = improve.validate_manifest(text, expected_cycle_id="imp-probe-1")
        self.assertTrue(any("cycle_aborted value" in err for err in errors), errors)

    def test_abort_stale_complete_zero_findings_archives_with_canonical_marker(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        report = self._add_seat(root, cycle, "probe-01", findings=0)
        self._move_tree(root)
        report_before = report.read_bytes()

        result = improve.abort_cycle(cycle)
        self.assertTrue(result["ok"], result)
        self.assertEqual(report.read_bytes(), report_before)

        manifest = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        self.assertIn("cycle_status: archived", manifest)
        self.assertIn("cycle_aborted: stale-complete-preserved", manifest)

        # Idempotent re-abort
        repeat = improve.abort_cycle(cycle)
        self.assertTrue(repeat["ok"], repeat)
        self.assertEqual(repeat.get("code"), "ALREADY_ARCHIVED")

    def test_abort_stale_complete_disposed_findings_preserves_evidence(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        report = self._add_seat(root, cycle, "probe-01", findings=1)
        self._dispose(cycle, "probe-01", 1, "NOT_REPRODUCED")
        self._move_tree(root)
        report_before = report.read_bytes()
        sweep_before = (cycle / "SWEEP.md").read_bytes()

        result = improve.abort_cycle(cycle)
        self.assertTrue(result["ok"], result)
        self.assertEqual(report.read_bytes(), report_before)
        self.assertEqual((cycle / "SWEEP.md").read_bytes(), sweep_before)

        manifest = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        self.assertIn("cycle_status: archived", manifest)
        self.assertIn("cycle_aborted: stale-complete-preserved", manifest)

    def test_abort_refuses_when_complete_report_has_unswept_findings(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        report = self._add_seat(root, cycle, "probe-01", findings=2)
        self._dispose(cycle, "probe-01", 1, "NOT_REPRODUCED")
        self._move_tree(root)
        report_before = report.read_bytes()
        manifest_before = (cycle / "MANIFEST.md").read_bytes()

        with self.assertRaisesRegex(improve.ImproveError, "unswept finding"):
            improve.abort_cycle(cycle)

        self.assertEqual(report.read_bytes(), report_before)
        self.assertEqual((cycle / "MANIFEST.md").read_bytes(), manifest_before)

    def test_resume_action_routes_to_abort_instead_of_sweep_queue_loop(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_seat(root, cycle, "antigravity-01", findings=0)
        self._move_tree(root)

        action, detail = resume_action(root, cycle.name, "antigravity")
        self.assertEqual(action, f"saipen improve abort {cycle.name}")
        self.assertIn("identity-stale", detail)

    def test_cli_abort_via_printed_route_closes_cycle_cleanly(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        report = self._add_seat(root, cycle, "antigravity-01", findings=0)
        self._move_tree(root)
        report_before = report.read_bytes()

        action, _detail = resume_action(root, cycle.name, "antigravity")
        words = shlex.split(action)
        self.assertEqual(words[:3], ["saipen", "improve", "abort"])

        rc, result = self._cli(root, *words[1:])
        self.assertEqual(rc, 0, result)
        self.assertEqual(report.read_bytes(), report_before)

        manifest = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        self.assertIn("cycle_status: archived", manifest)
        self.assertIn("cycle_aborted: stale-complete-preserved", manifest)


if __name__ == "__main__":
    unittest.main()

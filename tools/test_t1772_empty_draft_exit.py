"""T-1772: a cycle whose only seats are empty drafts has a finite printed exit.

`improve reconcile` classifies an un-started seat EMPTY_DRAFT and retires it,
but `retire` may not empty the roster, so a cycle whose every seat that could
still report is an empty draft had no reconcile route at all: reconcile
refused its own transition and named nothing else, while `validate` kept
printing `saipen improve reconcile <cycle>` as the cure. _SAIRELAY stayed red
for twelve days until `saipen improve abort` -- the sanctioned exit for a stuck
draft cycle -- was typed by hand (imp-_sairelay-20261013-1 saipen-cli-01
RUN-1/IMP-003; SRC-248 R006).

The oracle follows the printed route: reconcile's own canonical next command,
executed, must terminate the cycle without losing a report byte.
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
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class EmptyDraftCycleExit(unittest.TestCase):
    # The reconcile suite's fixture, borrowed by attribute: binding its
    # TestCase class here would collect that suite a second time.
    _project = _reconcile.ReconcileTests._project
    _cycle = _reconcile.ReconcileTests._cycle
    _run_text = staticmethod(_reconcile.ReconcileTests._run_text)
    _add_seat = _reconcile.ReconcileTests._add_seat
    _add_idle_seat = _reconcile.ReconcileTests._add_idle_seat

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1772-")
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

    def _single_empty_draft(self) -> tuple[Path, Path, Path]:
        root = self._project()
        cycle = self._cycle(root)
        report = self._add_idle_seat(root, cycle, "probe-01")
        return root, cycle, report

    def test_reconcile_names_the_sanctioned_exit(self) -> None:
        root, cycle, _report = self._single_empty_draft()
        rc, result = self._cli(root, "improve", "reconcile", cycle.name)
        self.assertNotEqual(rc, 0, result)
        self.assertEqual(
            result.get("canonical_next_command"), f"saipen improve abort {cycle.name}", result
        )

    def test_its_plan_names_the_same_exit(self) -> None:
        root, cycle, _report = self._single_empty_draft()
        rc, result = self._cli(root, "improve", "reconcile", cycle.name, "--dry-run")
        self.assertNotEqual(rc, 0, result)
        self.assertEqual(
            result.get("canonical_next_command"), f"saipen improve abort {cycle.name}", result
        )

    def test_the_printed_exit_terminates_the_cycle_and_keeps_every_report_byte(self) -> None:
        root, cycle, report = self._single_empty_draft()
        before = report.read_bytes()
        manifest_before = (cycle / "MANIFEST.md").read_bytes()
        _rc, refused = self._cli(root, "improve", "reconcile", cycle.name)
        self.assertEqual((cycle / "MANIFEST.md").read_bytes(), manifest_before)
        route = refused.get("canonical_next_command") or ""
        words = shlex.split(route)
        self.assertEqual(words[:3], ["saipen", "improve", "abort"], refused)
        rc, aborted = self._cli(root, *words[1:])
        self.assertEqual(rc, 0, aborted)
        self.assertEqual(report.read_bytes(), before)
        manifest = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        self.assertNotIn("cycle_status: active", manifest)

    def test_an_empty_draft_beside_evidence_still_retires(self) -> None:
        root = self._project()
        cycle = self._cycle(root)
        self._add_seat(root, cycle, "probe-01", findings=0)
        self._add_idle_seat(root, cycle, "probe-02")
        result = improve.reconcile_cycle(cycle)
        self.assertTrue(result["ok"], result)
        self.assertEqual([item["seat_id"] for item in result["retired"]], ["probe-02"])

    def test_a_retired_seat_is_not_a_survivor(self) -> None:
        # Retire's own rule: an unavailable seat cannot report, so an empty
        # draft beside one is still the last seat that could.
        root = self._project()
        cycle = self._cycle(root)
        self._add_idle_seat(root, cycle, "probe-01")
        self._add_idle_seat(root, cycle, "probe-02")
        improve.retire_seat(cycle, "probe-01", "EMPTY_DRAFT")
        rc, result = self._cli(root, "improve", "reconcile", cycle.name)
        self.assertNotEqual(rc, 0, result)
        self.assertEqual(
            result.get("canonical_next_command"), f"saipen improve abort {cycle.name}", result
        )


if __name__ == "__main__":
    unittest.main()

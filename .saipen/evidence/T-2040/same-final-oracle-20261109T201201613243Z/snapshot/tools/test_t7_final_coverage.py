"""T-7 (SAI_LIBRARY improve imp-sai_library-20261105-1 IMP-002): ONE definition
of final sweep coverage.

`NEEDS_EXTERNAL_EVIDENCE` is a committed decision but an UNRESOLVED one --
IMPROVE.md section 15 requires missing external evidence to be "an explicit
blocker, not a repeated actionable submit/complete instruction". It used to be
read two opposite ways over the SAME ledger:

    derive_status / verify_cycle / complete_cycle -> any closed-set string
        counted as coverage, so the cycle bar PASSED and cycle-complete froze
        the cycle as COMPLETE;

    improve_retrospective._view / reconcile          -> blocked.

So a strict cycle whose only disposition was `NEEDS_EXTERNAL_EVIDENCE` could be
declared COMPLETE (and `saipen improve verify` returned PASS) while `continue`
and `reconcile` still reported the same finding as pending/blocked. One truth
must govern every projection: an externally blocked finding keeps refusing the
bar. This test pins that truth both ways -- the blocked cycle now REFUSES, and
a genuinely final disposition still PASSES.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

import improve  # noqa: E402
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


class FinalCoverageIsOneTruth(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t7-coverage-")
        self.addCleanup(self._tmp.cleanup)
        self.root = self._project()

    def _project(self) -> Path:
        root = Path(self._tmp.name).resolve() / "project"
        saipen = root / ".saipen"
        saipen.mkdir(parents=True)
        (saipen / "LOG.md").write_text(
            "- 20.09.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8"
        )
        (saipen / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
        )
        (saipen / "STATE.md").write_text(
            '---\nphase: DONE\ntask: none\nnext_action: "saipen continue"\n'
            'blocker: ""\ntransition_from: SHIP\n'
            "saipen_version: 8\nschema_version: 3\n"
            'last_event: 900\nstyle_contract: ' + CURRENT_STYLE_CONTRACT + '\n'
            "agent: probe\nmode: full\n"
            "updated: 2026-09-20T00:00:00Z\n---\n",
            encoding="utf-8",
        )
        (saipen / "IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        (root / ".gitignore").write_text(".saipen/\n", encoding="utf-8")
        (root / "src.txt").write_text("source-v1\n", encoding="utf-8")
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "probe@example.invalid")
        _git(root, "config", "user.name", "T-7 Probe")
        _git(root, "add", ".gitignore", "src.txt")
        _git(root, "add", "-f", ".saipen/IDENTITY.md")
        _git(root, "commit", "-qm", "baseline")
        return root

    def _cycle(self, name: str = "imp-t7-20261105-01") -> Path:
        return improve.create_cycle(
            self.root, name, created_at="2026-11-05T00:00:00Z",
            project_identity="probe-project",
        )

    def _seat(self, cycle: Path, seat: str = "saipen-01") -> Path:
        improve.register_seat(cycle, seat, "core", "saipen_improve_PROBE.md")
        report = improve.create_report(
            self.root, cycle.name, seat, "PROBE", agent=seat, role="core",
            model_or_runtime="probe", context_scope="same bounded audit scope",
        )
        improve.append_run(
            report,
            "IMP-001 [P2] [LOGIC_ERROR] [reproduced] [note]\n"
            "expected: the finding remains accounted\n"
            "actual: the finding needs a disposition\n"
            "evidence: T-7 fixture finding 1\n",
        )
        improve.complete_report(report)
        return report

    def _dispose(self, cycle: Path, disposition: str, seat: str = "saipen-01") -> None:
        improve.write_sweep_entry(
            cycle,
            {
                "run": "RUN-1",
                "imp_id": "IMP-001",
                "disposition": disposition,
                "ticket": "-",
                "report": f"{seat}/saipen_improve_PROBE.md",
                "reproduced": "n",
            },
        )

    def test_needs_external_evidence_refuses_the_cycle_bar(self) -> None:
        cycle = self._cycle()
        self._seat(cycle)
        self._dispose(cycle, "NEEDS_EXTERNAL_EVIDENCE")
        # derive_status: the same reading as the retrospective projection.
        status = improve.derive_status(
            "saipen_improve_PROBE.md",
            (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig"),
            (cycle / "saipen-01" / "saipen_improve_PROBE.md").read_text(encoding="utf-8-sig"),
            (cycle / "SWEEP.md").read_text(encoding="utf-8-sig"),
            "saipen-01",
        )
        self.assertFalse(status["swept"])
        self.assertEqual(status["visible"], "blocked")
        self.assertEqual(status["missing"], ["RUN-1/IMP-001"])
        self.assertEqual(status["blocked"], ["RUN-1/IMP-001"])
        # verify_cycle: the bar names the unresolved finding.
        errors = improve.verify_cycle(cycle)
        self.assertTrue(errors, "an externally blocked finding must refuse the bar")
        self.assertTrue(any("IMP-001" in e for e in errors), errors)
        # complete_cycle: refuses; the cycle is NOT frozen as COMPLETE.
        with self.assertRaises(improve.ImproveError):
            improve.complete_cycle(cycle)
        manifest = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        self.assertIn("cycle_status: active", manifest)

    def test_a_final_disposition_still_passes_the_bar(self) -> None:
        cycle = self._cycle("imp-t7-20261105-02")
        self._seat(cycle)
        self._dispose(cycle, "NOT_REPRODUCED")
        status = improve.derive_status(
            "saipen_improve_PROBE.md",
            (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig"),
            (cycle / "saipen-01" / "saipen_improve_PROBE.md").read_text(encoding="utf-8-sig"),
            (cycle / "SWEEP.md").read_text(encoding="utf-8-sig"),
            "saipen-01",
        )
        self.assertTrue(status["swept"])
        self.assertEqual(status["visible"], "swept")
        self.assertEqual(status["missing"], [])
        self.assertEqual(improve.verify_cycle(cycle), [])
        improve.complete_cycle(cycle)
        self.assertIn(
            "cycle_status: complete", (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        )

    def test_the_route_names_the_blocker_not_empty_work(self) -> None:
        # The `continue` route must not advertise a sweep-queue that would
        # enumerate nothing: a blocked finding names its own blocker.
        from saipen_engine.continue_fallback import resume_action

        cycle = self._cycle("imp-t7-20261105-04")
        self._seat(cycle)
        self._dispose(cycle, "NEEDS_EXTERNAL_EVIDENCE")
        action, detail = resume_action(self.root, cycle.name, "saipen-01")
        self.assertIn("status", action)
        self.assertNotIn("sweep-queue", action)
        self.assertIn("external evidence", detail)

    def test_the_two_classifiers_agree(self) -> None:
        # The exact split the ticket names: the cycle bar (derive_status) and
        # the retrospective projection must read the SAME pending class. The
        # retrospective side treats exactly `NEEDS_EXTERNAL_EVIDENCE` as
        # pending/blocked (see improve_retrospective._view); the bar must name
        # the identical set as non-final, and nothing else.
        self.assertFalse(improve.is_final_coverage("NEEDS_EXTERNAL_EVIDENCE"))
        self.assertEqual(improve.NON_FINAL_DISPOSITIONS, {"NEEDS_EXTERNAL_EVIDENCE"})
        for disposition in improve.DISPOSITION - improve.NON_FINAL_DISPOSITIONS:
            self.assertTrue(improve.is_final_coverage(disposition), disposition)
        # And a disposition outside the closed set is never coverage.
        self.assertFalse(improve.is_final_coverage("NOT_A_DISPOSITION"))


if __name__ == "__main__":
    unittest.main()

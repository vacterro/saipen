"""SRC-085 M2: append_run owns the RUN heading; a poisoned body never lands.

AUDAPACK reproduction: `append_run` accepted a `run_text` that already began
with `## RUN N` while `append_run` itself also constructs the RUN heading. The
committed report then carried two headings for one RUN, the completion bar
refused it, and because reports are append/immutable `abort` was the only exit.

The contract implemented here: `append_run` receives a RUN BODY. A body that
carries a heading the report parser would read as an owned `## RUN N` section is
refused BEFORE any write, with the stable code RUN_BODY_REQUIRED, and the
proposed report passes the same RUN-identity bar (unique / ascending /
contiguous) the completion schema applies.
"""

from __future__ import annotations

import json
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


class RunBodyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="src085-run-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve() / "project"
        saipen = self.root / ".saipen"
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
            'saipen_home: "."\nagent: probe\nmode: full\n'
            "updated: 2026-09-20T00:00:00Z\n---\n",
            encoding="utf-8",
        )
        (saipen / "IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        self.cycle = improve.create_cycle(
            self.root,
            "imp-src085-20260920-01",
            created_at="2026-09-20T00:00:00Z",
            project_identity="probe-project",
        )
        improve.register_seat(self.cycle, "seat-a", "core", "saipen_improve_PROBE.md")
        self.report = improve.create_report(
            self.root,
            self.cycle.name,
            "seat-a",
            "PROBE",
            agent="seat-a",
            role="core",
            model_or_runtime="probe",
            context_scope="same bounded audit scope",
        )

    def test_a_body_that_smuggles_the_owned_heading_is_refused_before_write(self):
        before = self.report.read_bytes()
        for run_text in (
            "## RUN 1\n\nIMP-001 trace",
            "\n## RUN 4\n\nbody",
            "body first line\n\n## RUN 2\nmore body",
        ):
            with self.subTest(run_text=run_text):
                with self.assertRaises(improve.ImproveError) as ctx:
                    improve.append_run(self.report, run_text)
                self.assertEqual(getattr(ctx.exception, "code", None), "RUN_BODY_REQUIRED")
                self.assertEqual(self.report.read_bytes(), before)

    def test_a_plain_body_appends_exactly_one_canonical_run_and_completes(self):
        improve.append_run(self.report, "NO_FINDINGS\n")
        text = self.report.read_text(encoding="utf-8")
        self.assertEqual(text.count("## RUN 1"), 1)
        self.assertNotIn("## RUN 2", text)
        improve.complete_report(self.report)
        self.assertIn("report_status: complete", self.report.read_text(encoding="utf-8"))

    def test_the_cli_reports_the_stable_code_and_writes_nothing(self):
        payload = self.root / "findings.json"
        payload.write_text(
            json.dumps({"run_text": "## RUN 1\n\nIMP-001 smuggled heading"}),
            encoding="utf-8",
        )
        before = self.report.read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(self.root),
                "--json",
                "improve",
                "submit",
                self.cycle.name,
                "seat-a",
                "PROBE",
                str(payload),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        data = json.loads(result.stdout)
        self.assertFalse(data.get("ok"), data)
        self.assertEqual(data.get("code"), "RUN_BODY_REQUIRED", data)
        self.assertEqual(self.report.read_bytes(), before)

    def test_the_identity_bar_is_one_owner(self):
        self.assertEqual(improve._run_identity_problems([1, 2, 3]), [])
        self.assertTrue(improve._run_identity_problems([1, 1]))
        self.assertTrue(improve._run_identity_problems([2]))
        self.assertTrue(improve._run_identity_problems([2, 1]))



class UnevidencedRunBodyTests(RunBodyContractTests):
    """T-130: the sibling of the heading guard, for the OTHER unfinishable body.

    A RUN body that carries neither an ``IMP-<n>`` finding nor a NO_FINDINGS
    marker is an unfinished write, not an honest empty audit. The completion
    bar reads it as the latter's absence, refuses the report, and because a
    committed report is immutable the only exit left is ``improve abort`` --
    so one malformed submit destroys a cycle. It is refused at append time,
    before any write, with the stable code RUN_BODY_UNEVIDENCED.
    """

    def test_a_body_with_neither_finding_nor_marker_is_refused_before_write(self):
        before = self.report.read_bytes()
        for run_text in (
            "probe",
            "a bounded audit of the thing, and here is a paragraph about it",
            "NO FINDINGS",
            "  NO_FINDINGS -- indented, so it is not the marker",
            "prose mentioning NO_FINDINGS mid-line, which is not the marker",
        ):
            with self.subTest(run_text=run_text):
                with self.assertRaises(improve.ImproveError) as ctx:
                    improve.append_run(self.report, run_text)
                self.assertEqual(
                    getattr(ctx.exception, "code", None), "RUN_BODY_UNEVIDENCED"
                )
                self.assertEqual(self.report.read_bytes(), before)

    def test_both_evidenced_forms_are_accepted(self):
        improve.append_run(self.report, "NO_FINDINGS -- audited X, nothing found\n")
        improve.append_run(
            self.report,
            "IMP-001 [P2] [PROTOCOL_VIOLATION] [reproduced] [ticket]\n"
            "expected: a\nactual: b\nevidence: c\n",
        )
        text = self.report.read_text(encoding="utf-8")
        self.assertIn("## RUN 1", text)
        self.assertIn("## RUN 2", text)
        improve.complete_report(self.report)
        self.assertIn("report_status: complete", self.report.read_text(encoding="utf-8"))

    def test_a_refused_body_leaves_the_cycle_completable(self):
        """The property the defect destroyed: abort is never the only exit."""
        with self.assertRaises(improve.ImproveError):
            improve.append_run(self.report, "probe")
        improve.append_run(self.report, "NO_FINDINGS -- the honest empty form\n")
        improve.complete_report(self.report)
        self.assertIn("report_status: complete", self.report.read_text(encoding="utf-8"))

    def test_the_marker_is_anchored_to_a_line_start(self):
        self.assertTrue(improve._RUN_BODY_EVIDENCE_RE.search("IMP-004 x"))
        self.assertTrue(improve._RUN_BODY_EVIDENCE_RE.search("NO_FINDINGS -- x"))
        self.assertFalse(improve._RUN_BODY_EVIDENCE_RE.search("x NO_FINDINGS"))
        self.assertFalse(improve._RUN_BODY_EVIDENCE_RE.search("  NO_FINDINGS"))
        # The guard answers "does this body carry evidence", not "is the id
        # canonical": IMP-<any digits> is what the report parser reads as a
        # finding, and canonical-id shape stays the completion bar's business.
        self.assertTrue(improve._RUN_BODY_EVIDENCE_RE.search("IMP-4 short id"))
        self.assertFalse(improve._RUN_BODY_EVIDENCE_RE.search("IMPROVED-004 x"))
        self.assertFalse(improve._RUN_BODY_EVIDENCE_RE.search("findings: none"))


if __name__ == "__main__":
    unittest.main()

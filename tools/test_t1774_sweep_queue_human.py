"""T-1774: `improve sweep-queue` shows, without --json, what it enumerated.

IMPROVE.md defines sweep-queue as the read-only enumeration of the exact
unswept composite finding queue. Its payload carries that content in two
lists, `queue` and `precheck_errors`, and the shared human renderer prints an
allow-list of scalar keys only, so the command's whole human answer was the
line `code: IMPROVE_SWEEP_QUEUE` while the JSON held the findings and the
blockers (imp-_sairelay-20261013-1 saipen-cli-02 RUN-1/IMP-002; SRC-248 R008).

The oracle reads both surfaces of one cycle: every fact the JSON enumerates
must reach the human surface, and the JSON keeps its published shape.
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


CYCLE = "imp-t1774"
FINDINGS = (
    "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
    "expected: the enumeration is shown\n"
    "actual: one line of output\n"
    "evidence: probe-evidence-one\n",
    "IMP-002 [P2] [PROTOCOL_VIOLATION] [proven] [ticket]\n"
    "expected: blockers are named\n"
    "actual: blockers are hidden\n"
    "evidence: probe-evidence-two\n",
)


class SweepQueueHumanSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="t1774-")
        root = Path(cls._tmp.name).resolve() / "project"
        saipen = root / ".saipen"
        saipen.mkdir(parents=True)
        (saipen / "LOG.md").write_text(
            "- 14.10.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8"
        )
        (saipen / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n- [ ] T-900 [P1] probe | verify: probe\n"
            "## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        (saipen / "STATE.md").write_text(
            '---\nphase: DONE\ntask: none\nnext_action: "saipen continue"\n'
            'blocker: ""\ntransition_from: SHIP\n'
            "saipen_version: 8\nschema_version: 3\n"
            "last_event: 900\nstyle_contract: " + CURRENT_STYLE_CONTRACT + "\n"
            'saipen_home: "."\nagent: probe\nmode: full\n'
            "updated: 2026-10-14T00:00:00Z\n---\n",
            encoding="utf-8",
        )
        (saipen / "IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        cycle = improve.create_cycle(
            root, CYCLE, created_at="2026-10-14T00:00:00Z", project_identity="probe-project"
        )
        improve.register_seat(cycle, "seat-1", "core", "saipen_improve_A.md")
        report = improve.create_report(
            root,
            CYCLE,
            "seat-1",
            "A",
            agent="seat-1",
            role="core",
            model_or_runtime="probe",
            context_scope="probe scope",
        )
        improve.append_run(report, "\n".join(FINDINGS))
        improve.complete_report(report)
        # An expected seat with no report: a precheck blocker of its own kind.
        improve.register_seat(cycle, "seat-2", "core", "saipen_improve_B.md")
        cls.root = root
        cls.human = cls._run()
        cls.payload = json.loads(cls._run("--json").stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @classmethod
    def _run(cls, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "improve", "sweep-queue", CYCLE, *extra],
            cwd=str(cls.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )

    def test_the_fixture_enumerates_two_findings_and_their_blockers(self) -> None:
        # Instrument control: the JSON computes the facts the human surface owes.
        self.assertEqual(self.payload.get("code"), "IMPROVE_SWEEP_QUEUE", self.payload)
        self.assertEqual(len(self.payload["queue"]), 2, self.payload)
        self.assertGreaterEqual(len(self.payload["precheck_errors"]), 2, self.payload)

    def test_the_human_surface_names_the_cycle(self) -> None:
        self.assertEqual(self.human.returncode, 0, self.human.stderr)
        # Its own line: every composite finding_ref also carries the cycle id.
        self.assertIn(f"cycle: {CYCLE}", self.human.stdout.splitlines())

    def test_every_queued_finding_reaches_the_human_surface(self) -> None:
        for item in self.payload["queue"]:
            for key in ("finding_ref", "severity", "class", "expected", "actual", "evidence"):
                self.assertIn(str(item[key]), self.human.stdout, (key, self.human.stdout))

    def test_every_precheck_error_reaches_the_human_surface(self) -> None:
        for error in self.payload["precheck_errors"]:
            self.assertIn(error, self.human.stdout, self.human.stdout)

    def test_the_json_payload_keeps_its_published_shape(self) -> None:
        self.assertTrue(
            {"ok", "code", "cycle", "queue", "precheck_errors", "note"} <= set(self.payload),
            sorted(self.payload),
        )
        self.assertEqual(self.payload["cycle"], CYCLE)
        self.assertLessEqual(len(self.payload["precheck_errors"]), 5)
        for item in self.payload["queue"]:
            self.assertEqual(
                set(item),
                {
                    "finding_ref",
                    "run",
                    "imp",
                    "report",
                    "severity",
                    "class",
                    "expected",
                    "actual",
                    "evidence",
                },
            )


if __name__ == "__main__":
    unittest.main()

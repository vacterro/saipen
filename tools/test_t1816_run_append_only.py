"""T-1816 R006 bullet 3 -- appending RUN 2 must not rewrite RUN 1 (SRC-275 DRIFT-04).

The complement of ``test_t1816_run_provenance``: that file proves the per-RUN
identity is produced and cannot shadow the header. This one proves the property
that makes per-RUN identity worth having -- that an earlier run's bytes and the
report header are untouched by a later append, so a verifier can still tell
which tree each run was measured against.

The defect it guards is the observed "repair": because RUN 1's identity went
stale, the agent rewrote the report-wide header to the current identity. That
made the freshness check green and destroyed the distinction the field encodes.
A green check is not a preserved record.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

import improve  # noqa: E402
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class RunTwoPreservesRunOneTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1816-run-prov-")
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
            "imp-t1816-20260920-01",
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

    def _runs(self) -> "dict[int, str]":
        text = self.report.read_text(encoding="utf-8")
        parts = re.split(r"(?m)^## RUN (\d+)\s*$", text)
        # Strip only the separator whitespace the split leaves between sections;
        # the run's own bytes are what must be compared.
        return {int(parts[i]): parts[i + 1].strip("\n") for i in range(1, len(parts), 2)}

    def test_each_run_carries_its_own_identity(self) -> None:
        improve.append_run(self.report, "NO_FINDINGS\n")
        runs = self._runs()
        self.assertIn("run_source_head:", runs[1])
        self.assertIn("run_source_tree_fingerprint:", runs[1])

    def test_appending_run_two_leaves_run_one_bytes_identical(self) -> None:
        improve.append_run(self.report, "NO_FINDINGS\n")
        first = self._runs()[1]
        header_before = self.report.read_text(encoding="utf-8").split("\n## ", 1)[0]

        improve.append_run(self.report, "NO_FINDINGS\n")
        after = self.report.read_text(encoding="utf-8")
        self.assertEqual(self._runs()[1], first, "RUN 1 was rewritten by a later append")
        self.assertEqual(after.split("\n## ", 1)[0], header_before, "the header moved")
        self.assertIn("## RUN 2", after)

    def test_the_report_header_is_never_restamped_by_an_append(self) -> None:
        """The defect's 'fix' was rewriting this header. Appending must not."""
        head_before = improve._field(self.report.read_text(encoding="utf-8"), "source_head")
        improve.append_run(self.report, "NO_FINDINGS\n")
        improve.append_run(self.report, "NO_FINDINGS\n")
        head_after = improve._field(self.report.read_text(encoding="utf-8"), "source_head")
        self.assertEqual(head_after, head_before)

    def test_a_second_run_is_a_distinct_identity_record(self) -> None:
        improve.append_run(self.report, "NO_FINDINGS\n")
        improve.append_run(self.report, "NO_FINDINGS\n")
        runs = self._runs()
        self.assertEqual(sorted(runs), [1, 2])
        for number in (1, 2):
            self.assertIn("run_source_head:", runs[number])


if __name__ == "__main__":
    unittest.main()

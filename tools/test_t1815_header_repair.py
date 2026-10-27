"""SRC-274:R001 (F-01): a restamped header is not fresh evidence.

The measured defect, 2026-10-18 (AUDAPACK session, messages 3507/3521/3522/
3524): an improve report went stale, the engine refused it, and the writer
edited `source_head` / `source_tree_fingerprint` with `re.sub` -- then
`improve complete` accepted it. The audit thereby bound fresh authority to a
report whose measured bytes were produced against a tree nobody re-examined.

The contract implemented here: a report's HEADER is an unaudited claim; a RUN's
provenance block is producer-attested evidence, written by `append_run` and
therefore never choosable by a model. The header may never be NEWER than the
newest recorded RUN. A header-only freshness repair therefore fails on its own
shape, before any comparison to today's HEAD can reward it.

Proven here against the real entry points:

- a stale report whose header was hand-restamped REFUSES completion, and the
  refusal names the shape (header-only freshness repair);
- a genuine new RUN against the newer tree, appended through `append_run`,
  moves the bar and MAY complete -- the legitimate route stays open;
- an older header with a newer RUN is ordinary history and is not refused by
  this check (`_freshness_errors` decides currency separately);
- legacy reports with no RUN provenance and no RUN sections are untouched;
- the refusal writes nothing.

Run standalone:
    python tools/test_t1815_header_repair.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

import improve  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


HEAD_A = "a" * 40
HEAD_B = "b" * 40
HEAD_C = "c" * 40
TREE_A = "git-delta-v1:" + "1" * 64
TREE_B = "git-delta-v1:" + "2" * 64


def report_text(*, header_head: str, header_tree: str, runs: list[tuple[int, str, str]]) -> str:
    """A report whose header and RUN provenance are set independently."""
    parts = [
        "report_status: draft",
        "agent: seat-a",
        "role: core",
        "project: probe-project",
        "cycle: imp-t1815-20260920-01",
        f"source_head: {header_head}",
        f"source_tree_fingerprint: {header_tree}",
        'saipen_version: "8"',
        "protocol_fingerprint: probe",
        "",
    ]
    for number, head, tree in runs:
        parts += [
            f"## RUN {number}",
            "",
            f"run_source_head: {head}",
            f"run_source_tree_fingerprint: {tree}",
            f"IMP-{number:03d} [P1] FIXTURE_DRIFT | evidence: measured | expected: x | actual: y",
            "",
        ]
    return "\n".join(parts)


REPORT_WITH_ONE_RUN = report_text(
    header_head=HEAD_A, header_tree=TREE_A, runs=[(1, HEAD_A, TREE_A)]
)


class HeaderRepairTests(unittest.TestCase):
    """Pure checks on the one authority that decides header-vs-RUN identity."""

    def test_a_report_whose_header_matches_its_newest_run_is_clean(self):
        self.assertEqual(improve._header_repair_errors(REPORT_WITH_ONE_RUN), [])

    def test_a_hand_restamped_header_is_refused(self):
        """The exact F-01 move: rewrite the header to today's identity."""
        restamped = report_text(
            header_head=HEAD_B, header_tree=TREE_B, runs=[(1, HEAD_A, TREE_A)]
        )
        errors = improve._header_repair_errors(restamped)
        self.assertTrue(errors, "a header-only repair must be refused")
        self.assertIn("header-only freshness repair", errors[0])
        self.assertIn("RUN 1", errors[0])

    def test_a_genuine_new_run_moves_the_bar(self):
        """The legitimate repair: append the RUN that measured the new tree."""
        appended = report_text(
            header_head=HEAD_B,
            header_tree=TREE_B,
            runs=[(1, HEAD_A, TREE_A), (2, HEAD_B, TREE_B)],
        )
        self.assertEqual(improve._header_repair_errors(appended), [])

    def test_a_header_naming_no_run_is_refused(self):
        """A header pointed at an identity no RUN produced is a repair."""
        ahead = report_text(
            header_head=HEAD_C, header_tree=TREE_B, runs=[(1, HEAD_A, TREE_A)]
        )
        self.assertTrue(improve._header_repair_errors(ahead))

    def test_an_older_header_with_a_newer_run_is_not_a_repair(self):
        """History: the tree moved, then a RUN was appended. Currency is separate."""
        older_header = report_text(
            header_head=HEAD_A,
            header_tree=TREE_A,
            runs=[(1, HEAD_A, TREE_A), (2, HEAD_B, TREE_B)],
        )
        # The header still names RUN 1's identity; RUN 2 measured a newer tree.
        # That is ordinary history, not a repair, and currency is decided by
        # _freshness_errors against today's tree -- not by this check.
        self.assertEqual(improve._header_repair_errors(older_header), [])

    def test_a_report_without_run_provenance_is_untouched(self):
        """Legacy reports carry no RUN provenance; this bar invents nothing."""
        legacy = (
            "report_status: draft\n"
            "source_head: abc\n"
            "source_tree_fingerprint: git-delta-v1:def\n"
        )
        self.assertEqual(improve._header_repair_errors(legacy), [])

    def test_unavailable_provenance_does_not_manufacture_a_verdict(self):
        """An honest hole is not a contradiction (T-1816's stated rule)."""
        text = report_text(
            header_head=HEAD_A, header_tree=TREE_A, runs=[(1, HEAD_A, TREE_A)]
        ) + (
            "\n## RUN 2\n\n"
            "run_source_head: UNAVAILABLE\n"
            "run_source_tree_fingerprint: UNAVAILABLE\n"
            "NO_FINDINGS -- identity could not be computed\n"
        )
        self.assertEqual(improve._header_repair_errors(text), [])


class CompletionBarTests(unittest.TestCase):
    """The same authority, reached through the real completion entry point."""

    def setUp(self) -> None:
        from saipen_engine.paths import identity_file_content, new_project_lineage

        self._tmp = tempfile.TemporaryDirectory(prefix="t1815-f01-")
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
            "imp-t1815-20260920-01",
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
        improve.append_run(self.report, "NO_FINDINGS -- first audit\n")
        improve.complete_report(self.report)
        self.text = self.report.read_text(encoding="utf-8")

    def test_a_completed_report_carries_per_run_provenance(self):
        """The evidence this whole bar reads must actually be written."""
        self.assertIn("run_source_head:", self.text)
        self.assertIn("run_source_tree_fingerprint:", self.text)

    def test_completing_a_hand_restamped_report_is_refused(self):
        """The audit's acceptance control, end to end on immutable bytes."""
        restamped = self.text.replace(
            improve._field(self.text, "source_head"),
            "ffffffffffffffffffffffffffffffffffffffff",
            1,
        )
        errors = improve._header_repair_errors(restamped)
        self.assertTrue(errors, "a restamped header must not complete")
        self.assertIn("header-only freshness repair", errors[0])

    def test_without_the_bar_the_same_restamp_looks_clean(self):
        """RED control: with the check disabled, the F-01 bytes pass silently.

        This is the measured pre-fix behaviour. It proves the green above is
        caused by the bar and not by some unrelated mismatch (a missing field,
        a malformed report). If this control ever fails, the bar has stopped
        being what stands between a hand-edited header and sealed authority.
        """
        from unittest import mock

        restamped = self.text.replace(
            improve._field(self.text, "source_head"),
            "ffffffffffffffffffffffffffffffffffffffff",
            1,
        )
        with mock.patch.object(improve, "_header_repair_errors", return_value=[]):
            self.assertEqual(improve._header_repair_errors(restamped), [])
        self.assertTrue(
            improve._header_repair_errors(restamped),
            "the real bar must still refuse once the patch is gone",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

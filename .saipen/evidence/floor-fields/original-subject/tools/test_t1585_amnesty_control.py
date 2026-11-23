"""T-1585: later genuine grants cannot mask an amnesty prose control."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks as A  # noqa: E402
from saipen_engine.log import (  # noqa: E402
    history_paths, parse_log_line, structural_marker_events,
)

LABEL = "an amnesty demoted to prose stops suppressing"
MARKER = "observed historical timestamp inversions"


class AmnestyControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-amnesty-control-")
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.root = self.tmp / "source"
        (self.root / ".saipen/logs").mkdir(parents=True)
        self.segment = self.root / ".saipen/logs/LOG-017.md"
        self.segment.write_bytes(
            b"- 01.10.26 00:20 [E-1] RUN: before inversion\r\n"
            b"- 01.10.26 00:00 [E-2] RUN: historical inversion\r\n"
            b"- 01.10.26 00:21 [E-3] DEC: observed historical timestamp inversions -- first\r\n"
        )
        self.later_segment = self.root / ".saipen/logs/LOG-018.md"
        self.later_segment.write_bytes(
            b"- 01.10.26 00:22 [E-4] RUN: discussion of observed historical timestamp inversions\n"
            b"- 01.10.26 00:23 [E-5] DEC: observed historical timestamp inversions -- later\n"
        )
        self.active = self.root / ".saipen/LOG.md"
        self.active.write_bytes(
            b"- 01.10.26 00:24 [E-6] DEC: observed historical timestamp inversions -- latest\n"
            b"- 01.10.26 00:25 [E-7] DEC: discussion of observed historical timestamp inversions\n"
        )
        self.case = next(case for case in A.CASES if case[0] == LABEL)

    def grants(self, root):
        events = [parse_log_line(line) for path in history_paths(root)
                  for line in path.read_text(encoding="utf-8").splitlines()]
        return structural_marker_events([event for event in events if event], MARKER, ("DEC",))

    def apply(self):
        _label, rel, mutation, _expected, _gate = A.case_parts(self.case)
        return A.apply_case(self.root, rel, mutation)

    def test_all_actual_grants_are_demoted_across_complete_history(self):
        self.assertEqual(self.grants(self.root), [3, 5, 6])
        self.assertIs(self.apply(), True)
        self.assertEqual(self.grants(self.root), [])
        self.assertIn("RUN: discussion of " + MARKER,
                      self.later_segment.read_text(encoding="utf-8"))
        self.assertIn("DEC: discussion of " + MARKER,
                      self.active.read_text(encoding="utf-8"))

    def test_save_restore_declares_every_touched_file_and_preserves_raw_bytes(self):
        _label, rel, mutation, _expected, _gate = A.case_parts(self.case)
        paths = A.mutation_files(self.root, rel, mutation)
        self.assertEqual(set(paths), set(history_paths(self.root)))
        saved = [(path, path.read_bytes()) for path in paths]
        originals = {path: path.read_bytes() for path in history_paths(self.root)}
        self.assertIs(self.apply(), True)
        A.restore_case_files(saved)
        self.assertEqual({path: path.read_bytes() for path in history_paths(self.root)}, originals)

    def test_actual_sweep_restores_all_sources_after_seeing_the_unsuppressed_condition(self):
        context = A.ProbeContext(self.tmp, [self.case], None)
        context.pristine = self.root
        context.control = ""
        originals = {p: p.read_bytes() for p in history_paths(self.root)}

        def validator(root, gate=None):
            if max(self.grants(root), default=0) < 2:
                return "WARN: timestamp moves backwards by 20m"
            return ""

        with mock.patch.object(A, "validator_output", side_effect=validator):
            error = A.mutation_sweep_probe(context)
        self.assertIsNone(error, "\n".join(context.extra))
        self.assertIn(A.FULL_SWEEP_PHRASE, "\n".join(context.extra))
        self.assertEqual({p: p.read_bytes() for p in history_paths(self.root)}, originals)

    def test_active_log_change_selects_the_control(self):
        self.assertEqual([c[0] for c in A.select_cases([self.case], frozenset({".saipen/LOG.md"}))],
                         [LABEL])

    def test_future_sealed_log_changes_select_the_control_without_disk_guessing(self):
        for path in (".saipen/logs/LOG-018.md", ".saipen/logs/LOG-999.md"):
            self.assertEqual([c[0] for c in A.select_cases([self.case], frozenset({path}))],
                             [LABEL])
        self.assertEqual(A.select_cases([self.case], frozenset({"other/LOG-999.md"})), [])

    def test_no_actual_grant_is_a_no_op_instead_of_fake_evidence(self):
        for path in history_paths(self.root):
            path.write_text("- 01.10.26 00:00 [E-1] RUN: mention " + MARKER + "\n",
                            encoding="utf-8")
        self.assertIs(self.apply(), False)

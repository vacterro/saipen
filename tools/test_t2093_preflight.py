"""T-2093/T-2094: preflight must refuse only what is deterministically dead.

Night 8 shipped a timing gate that refused a focused run whenever ANY prior
record of the same sandbox scope measured a copy above the budget. The scope
shape ``{"mode": "FULL", "trees": []}`` is shared by every undeclared focused
run on every tree, so one 676 s record from a huge tree refused a tiny
unrelated project; the same gate scanned records in filename order and stopped
at the first >= 60 s entry, so a 650 s witness was invisible behind a 90 s one.

Night 9 splits the two answers:

* a deterministic refusal -- a request that cannot run at all (no matching
  tests, an unsupported budget);
* a historical timing ADVISORY -- measured cost of this exact selection on
  this exact tree. It names the expected copy, the witness and a reachable
  next step. It never blocks the run: a slow copy yesterday is not a proof
  about today's disk, cache or tree.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import preflight  # noqa: E402
from saipen_engine.sandbox_scope import select_modules  # noqa: E402

FINGERPRINT = "a" * 64
OTHER_TREE = "b" * 64
FULL_SCOPE = {"mode": "FULL", "trees": []}
DECLARED_SCOPE = {"mode": "DECLARED", "trees": []}


def _record(scope: dict, copy_s: float, *, verdict="FAIL", ran=0,
            patterns=("test_probe.py",), fingerprint=FINGERPRINT) -> dict:
    return {
        "family": "focused-unit",
        "fingerprint": fingerprint,
        "verdict": verdict,
        "patterns": list(patterns),
        "ran": ran,
        "sandbox_scope": scope,
        "timings_s": {"copy_wall_s": copy_s},
    }


class PreflightFixture(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="t2093-preflight-"))
        self.records = self.temp / ".saipen/evidence/focused-unit"
        self.records.mkdir(parents=True)
        self.tools = self.temp / "tools"
        self.tools.mkdir()
        (self.tools / "test_probe.py").write_text("", encoding="utf-8")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp, ignore_errors=True)

    def _write(self, name: str, record: dict) -> None:
        (self.records / name).write_text(json.dumps(record), encoding="utf-8")

    def _manifest(self, modules: dict) -> None:
        (self.tools / "sandbox_scope.json").write_text(
            json.dumps({"schema": 1, "modules": modules}), encoding="utf-8"
        )


class DeterministicBudgetRefusalTests(PreflightFixture):
    """Only a request that cannot run is refused; history is an advisory."""

    def test_a_non_positive_timeout_is_a_deterministic_refusal(self):
        for timeout in (0, -1):
            with self.subTest(timeout=timeout):
                problem = preflight.budget_problem(
                    self.temp, ["test_probe.py"], timeout
                )
                self.assertIsNotNone(problem)
                self.assertEqual(problem["code"], "UNSUPPORTED_VERIFICATION_BUDGET")

    def test_a_timeout_above_the_focused_cap_names_the_reachable_route(self):
        problem = preflight.budget_problem(self.temp, ["test_probe.py"], 301)
        self.assertIsNotNone(problem)
        self.assertEqual(problem["code"], "UNSUPPORTED_VERIFICATION_BUDGET")
        detail = problem["detail"]
        self.assertIn("300", detail)
        self.assertIn("full evidence", detail)

    def test_a_supported_timeout_is_not_refused_by_history(self):
        # R1 (night 9): an unrelated stale record measured 676 s of copy.
        self._write("a.json", _record(
            FULL_SCOPE, 676.58, patterns=("test_other.py",)
        ))
        self.assertIsNone(
            preflight.budget_problem(self.temp, ["test_probe.py"], 300)
        )

    def test_a_measured_over_budget_copy_is_never_a_refusal(self):
        self._write("a.json", _record(FULL_SCOPE, 676.58))
        self.assertIsNone(
            preflight.budget_problem(self.temp, ["test_probe.py"], 300)
        )
        advisory = preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        )
        self.assertIsNotNone(advisory)
        self.assertEqual(advisory["code"], "HISTORICAL_TIMING_ADVISORY")
        self.assertNotEqual(advisory["code"], "INSUFFICIENT_VERIFICATION_BUDGET")
        self.assertEqual(advisory["expected_copy_s"], 676.58)
        self.assertEqual(advisory["witness"]["copy_wall_s"], 676.58)

    def test_a_historical_fail_is_not_safety_authority(self):
        # R4: the record is red, but red says nothing about admission.
        self._write("a.json", _record(FULL_SCOPE, 676.58, verdict="FAIL", ran=0))
        self.assertIsNone(
            preflight.budget_problem(self.temp, ["test_probe.py"], 300)
        )
        advisory = preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        )
        self.assertEqual(advisory["witness"]["verdict"], "FAIL")


class HistoricalTimingAdvisoryTests(PreflightFixture):
    """The advisory is bound to the exact selection and tree it measured."""

    def test_another_pattern_set_is_not_this_selection(self):
        # R1: same FULL scope, different selected tests -> not a witness.
        self._write("a.json", _record(
            FULL_SCOPE, 676.58, patterns=("test_other.py",)
        ))
        self.assertIsNone(preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        ))

    def test_a_changed_source_tree_does_not_inherit_the_old_timing(self):
        # R3: the same paths on a different tree are a different subject.
        self._write("a.json", _record(
            FULL_SCOPE, 676.58, fingerprint=OTHER_TREE
        ))
        self.assertIsNone(preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        ))

    def test_a_small_current_corpus_is_not_blocked_by_a_large_old_one(self):
        # The measured night-8 red: a fresh tiny project inherited a 676 s
        # record from a huge tree because both resolved FULL.
        (self.tools / "test_small.py").write_text("", encoding="utf-8")
        self._write("a.json", _record(
            FULL_SCOPE, 676.58, patterns=("test_small.py",)
        ))
        self.assertIsNone(preflight.budget_problem(
            self.temp, ["test_small.py"], 300
        ))
        self.assertIsNone(preflight.timing_advisory(
            self.temp, ["test_small.py"], 300, fingerprint=OTHER_TREE
        ))

    def test_the_worst_record_wins_whatever_the_filename_order(self):
        # R2: night 8 broke at the first >= 60 s entry, so 90 s a.json hid
        # the 650 s z.json. Scan every record, then max deterministically.
        for first, last in (("a.json", "z.json"), ("z.json", "a.json")):
            with self.subTest(first=first):
                for path in self.records.glob("*.json"):
                    path.unlink()
                self._write(first, _record(FULL_SCOPE, 90.0))
                self._write(last, _record(FULL_SCOPE, 650.0))
                advisory = preflight.timing_advisory(
                    self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
                )
                self.assertIsNotNone(advisory)
                self.assertEqual(advisory["expected_copy_s"], 650.0)
                self.assertEqual(advisory["records_examined"], 2)

    def test_a_measured_copy_within_budget_is_not_an_advisory(self):
        self._write("a.json", _record(
            DECLARED_SCOPE, 4.06, verdict="PASS", ran=12
        ))
        self._manifest({"test_probe.py": []})
        self.assertIsNone(preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        ))

    def test_the_60_second_floor_keeps_noise_out_of_the_advisory(self):
        self._write("a.json", _record(FULL_SCOPE, 45.0))
        self.assertIsNone(preflight.timing_advisory(
            self.temp, ["test_probe.py"], 30, fingerprint=FINGERPRINT
        ))

    def test_unreadable_or_corrupt_records_never_advise(self):
        (self.records / "a.json").write_text("{not json", encoding="utf-8")
        (self.records / "b.json").write_text("[1, 2, 3]", encoding="utf-8")
        self.assertIsNone(preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        ))

    def test_missing_record_directory_is_not_an_advisory(self):
        self.assertIsNone(preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT,
            record_dir=self.temp / "elsewhere",
        ))

    def test_a_declared_scope_gets_a_reachable_recommendation(self):
        self._manifest({"test_probe.py": []})
        self._write("a.json", _record(DECLARED_SCOPE, 250.0))
        advisory = preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        )
        self.assertIsNone(advisory, "250 s of copy fits a 300 s budget")

        self._write("a.json", _record(DECLARED_SCOPE, 450.0))
        advisory = preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        )
        self.assertIsNotNone(advisory)
        recommendation = advisory["recommendation"]
        self.assertIn("300 s", recommendation)
        self.assertNotIn("larger budget", recommendation)

    def test_a_full_scope_recommendation_names_a_reachable_route(self):
        # R8: never recommend raising the focused budget above its own cap.
        self._write("a.json", _record(FULL_SCOPE, 676.58))
        advisory = preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300, fingerprint=FINGERPRINT
        )
        recommendation = advisory["recommendation"]
        self.assertIn("sandbox_scope.json", recommendation)
        self.assertIn("full evidence", recommendation)
        self.assertNotIn("larger budget", recommendation)

    def test_without_a_tree_identity_the_advisory_still_never_refuses(self):
        self._write("a.json", _record(FULL_SCOPE, 676.58))
        self.assertIsNone(
            preflight.budget_problem(self.temp, ["test_probe.py"], 300)
        )
        self.assertIsNotNone(preflight.timing_advisory(
            self.temp, ["test_probe.py"], 300
        ))


class SelectionRefusalTests(PreflightFixture):
    def test_a_dead_pattern_is_refused_before_the_copy(self):
        problem = preflight.selection_problem(self.temp, ["test_nope_*.py"])
        self.assertIsNotNone(problem)
        self.assertEqual(problem["code"], "EMPTY_TEST_SELECTION")
        self.assertEqual(problem["patterns"], ["test_nope_*.py"])

    def test_a_live_pattern_proceeds(self):
        self.assertIsNone(preflight.selection_problem(self.temp, ["test_probe.py"]))

    def test_one_live_one_dead_refuses_only_the_dead_one(self):
        problem = preflight.selection_problem(
            self.temp, ["test_probe.py", "test_dead_*.py"]
        )
        self.assertIsNotNone(problem)
        self.assertEqual(problem["patterns"], ["test_dead_*.py"])

    def test_a_missing_tools_dir_is_not_a_selection_refusal(self):
        self.assertIsNone(
            preflight.selection_problem(self.temp / "absent", ["test_x.py"])
        )

    def test_selection_agrees_with_the_shared_scope_selector(self):
        # W3: one selector, not two pattern-matching algorithms.
        for extra in ("test_b.py", "test_c.py"):
            (self.tools / extra).write_text("", encoding="utf-8")
        for patterns in (
            ["test_*.py"],
            ["test_probe.py"],
            ["test_[bc].py"],
            ["test_nope.py", "test_probe.py"],
            ["test_nope*.py"],
        ):
            with self.subTest(patterns=patterns):
                selected, unmatched = select_modules(self.temp, patterns)
                problem = preflight.selection_problem(self.temp, patterns)
                self.assertEqual(problem is None, unmatched == [],
                                 (selected, unmatched, problem))
                self.assertEqual(
                    sorted(problem["patterns"]) if problem else [],
                    sorted(unmatched),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)

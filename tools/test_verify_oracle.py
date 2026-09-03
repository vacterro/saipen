"""Test-oracle integrity regressions (T-1276, `VERIFY-ORACLE-01`).

The defect this closes is the cheapest way to close a bug ticket:

    BUG EXISTS -> TEST FAILS -> weaken the fixture -> TEST PASSES -> DONE

`phases/verify.md` already demanded a regression test that failed before the
fix. It could not say WHICH test, so the FAIL and the PASS were allowed to come
from different verifiers. Every downstream guard then reads green: REVIEW
re-runs the ticket's own `verify:` and gets the same green from the same
weakened oracle, and `acceptance.py` marks evidence stale only on RE-entering
BUILD, so an edit made inside the one BUILD never trips it.

These tests run a REAL subject and a REAL oracle in a subprocess rather than
asserting over invented strings: the point of the ticket is that green is
cheap, so the fixture has to be able to actually produce a dishonest green.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.oracle import (  # noqa: E402
    ADMISSIBLE,
    NOT_A_REGRESSION_PAIR,
    ORACLE_CHANGED,
    SUBJECT_UNCHANGED,
    oracle_digest,
    parse_identity,
    regression_pair_verdict,
    verifier_identity,
)

# The subject: clamp to a maximum of 3. The buggy one forgets to clamp.
BUGGY = "def clamp(value):\n    return value\n"
FIXED = "def clamp(value):\n    return min(value, 3)\n"

# The oracle: the assertion that DEFINES success.
ORACLE = (
    "from subject import clamp\n"
    "assert clamp(5) == 3, f'clamp(5) == {clamp(5)}'\n"
    "print('ok')\n"
)
# The same file after the classic edit: the input no longer reaches the bug.
WEAKENED = (
    "from subject import clamp\n"
    "assert clamp(1) == 1, f'clamp(1) == {clamp(1)}'\n"
    "print('ok')\n"
)

COMMAND = "python check.py"


class OracleFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-verify-oracle-")
        self.root = Path(self.tmp.name)
        self.subject = self.root / "subject.py"
        self.check = self.root / "check.py"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # helpers -------------------------------------------------------------

    def arrange(self, subject: str, oracle: str) -> None:
        self.subject.write_text(subject, encoding="utf-8")
        self.check.write_text(oracle, encoding="utf-8")

    def run_oracle(self) -> bool:
        """True when the oracle passes. A real process, a real verdict."""
        done = subprocess.run(
            [sys.executable, "check.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return done.returncode == 0

    def record(self, result: str) -> dict:
        return {
            "result": result,
            "verifier": verifier_identity(COMMAND, ["check.py"], self.root),
            "subject": oracle_digest(self.root, ["subject.py"]),
        }


# ---------------------------------------------------------------------------
# AC-04 -- the three-way table, run for real
# ---------------------------------------------------------------------------


class ThreeWayRegressionTests(OracleFixture):
    def test_buggy_subject_with_the_original_oracle_is_red(self) -> None:
        self.arrange(BUGGY, ORACLE)
        self.assertFalse(self.run_oracle())

    def test_fixed_subject_with_the_same_oracle_is_green_and_admissible(self) -> None:
        self.arrange(BUGGY, ORACLE)
        self.assertFalse(self.run_oracle())
        before = self.record("FAIL")

        self.subject.write_text(FIXED, encoding="utf-8")
        self.assertTrue(self.run_oracle())
        after = self.record("PASS")

        verdict = regression_pair_verdict(before, after)
        self.assertEqual(verdict["code"], ADMISSIBLE)
        self.assertTrue(verdict["admissible"])
        self.assertEqual(before["verifier"], after["verifier"], "the oracle must not move")
        self.assertNotEqual(before["subject"], after["subject"], "the subject must move")

    def test_buggy_subject_with_a_weakened_oracle_is_green_and_rejected(self) -> None:
        # The headline. The suite goes green, the bug is untouched, and the
        # pair is still refused as evidence of a fix.
        self.arrange(BUGGY, ORACLE)
        self.assertFalse(self.run_oracle())
        before = self.record("FAIL")

        self.check.write_text(WEAKENED, encoding="utf-8")
        self.assertTrue(self.run_oracle(), "the weakened oracle must really pass")
        after = self.record("PASS")

        self.assertEqual(before["subject"], after["subject"], "the bug is still there")
        verdict = regression_pair_verdict(before, after)
        self.assertEqual(verdict["code"], ORACLE_CHANGED)
        self.assertFalse(verdict["admissible"])
        self.assertIn(
            "the only thing that turned this green was the check itself", verdict["reason"]
        )

    def test_changing_both_sides_at_once_is_unattributable(self) -> None:
        self.arrange(BUGGY, ORACLE)
        before = self.record("FAIL")
        self.subject.write_text(FIXED, encoding="utf-8")
        self.check.write_text(WEAKENED, encoding="utf-8")
        after = self.record("PASS")
        verdict = regression_pair_verdict(before, after)
        self.assertEqual(verdict["code"], ORACLE_CHANGED)
        self.assertIn("nothing attributes the green to the fix", verdict["reason"])


# ---------------------------------------------------------------------------
# AC-01 -- the known-bad input is the pre-fix subject
# ---------------------------------------------------------------------------


class MutationControlTests(OracleFixture):
    def test_restoring_the_bug_under_an_unchanged_oracle_goes_red_again(self) -> None:
        # The fix must be NECESSARY for the green, which is only provable by
        # taking it away and watching the light come back on.
        self.arrange(FIXED, ORACLE)
        self.assertTrue(self.run_oracle())
        self.subject.write_text(BUGGY, encoding="utf-8")
        self.assertFalse(self.run_oracle(), "restored bug stayed green: the oracle proves nothing")

    def test_a_weakened_oracle_fails_that_control(self) -> None:
        # Same mutation, weakened oracle: the bug comes back and the gate does
        # not notice. This is what the control is for.
        self.arrange(FIXED, WEAKENED)
        self.assertTrue(self.run_oracle())
        self.subject.write_text(BUGGY, encoding="utf-8")
        self.assertTrue(self.run_oracle(), "the weakened oracle cannot see the restored bug")

    def test_the_norm_names_the_pre_fix_subject_as_the_known_bad_input(self) -> None:
        text = (ROOT / "saipen" / "phases" / "verify.md").read_text(encoding="utf-8-sig")
        self.assertIn("known-bad input is the PRE-FIX SUBJECT", text)
        self.assertIn("<!-- RULE-OWNER: VERIFY-ORACLE-01 -->", text)


# ---------------------------------------------------------------------------
# AC-02 -- verifier identity covers content AND command
# ---------------------------------------------------------------------------


class VerifierIdentityTests(OracleFixture):
    def test_identical_bytes_give_identical_identity(self) -> None:
        self.arrange(BUGGY, ORACLE)
        first = verifier_identity(COMMAND, ["check.py"], self.root)
        second = verifier_identity(COMMAND, ["check.py"], self.root)
        self.assertEqual(first, second)

    def test_editing_the_oracle_changes_identity(self) -> None:
        self.arrange(BUGGY, ORACLE)
        before = verifier_identity(COMMAND, ["check.py"], self.root)
        self.check.write_text(WEAKENED, encoding="utf-8")
        self.assertNotEqual(before, verifier_identity(COMMAND, ["check.py"], self.root))

    def test_deleting_the_failing_case_changes_identity(self) -> None:
        # An absent path contributes an explicit absence marker. Skipping it
        # would make deletion -- one of the ways this defect is committed --
        # the single edit the check could not see.
        self.arrange(BUGGY, ORACLE)
        before = oracle_digest(self.root, ["check.py"])
        self.check.unlink()
        self.assertNotEqual(before, oracle_digest(self.root, ["check.py"]))

    def test_narrowing_the_command_changes_identity_with_files_untouched(self) -> None:
        self.arrange(BUGGY, ORACLE)
        wide = verifier_identity("pytest tests/", ["check.py"], self.root)
        narrow = verifier_identity("pytest tests/ -k not_the_broken_one", ["check.py"], self.root)
        self.assertNotEqual(wide, narrow)
        self.assertEqual(
            oracle_digest(self.root, ["check.py"]), oracle_digest(self.root, ["check.py"])
        )

    def test_path_order_and_separator_do_not_change_identity(self) -> None:
        self.arrange(BUGGY, ORACLE)
        forward = oracle_digest(self.root, ["check.py", "subject.py"])
        reversed_sep = oracle_digest(self.root, ["subject.py", r"check.py"])
        self.assertEqual(forward, reversed_sep)

    def test_identity_tokens_round_trip_through_an_evidence_line(self) -> None:
        line = (
            "AC-EVIDENCE AC-01 PASS behavioral -- "
            "oracle:abc123def456 subject:0011223344 -- test:x"
        )
        self.assertEqual(
            parse_identity(line), {"oracle": "abc123def456", "subject": "0011223344"}
        )
        self.assertEqual(parse_identity("AC-EVIDENCE AC-01 PASS behavioral -- test:x"), {})


# ---------------------------------------------------------------------------
# AC-03 / AC-05 -- the escape path, and the check's own red control
# ---------------------------------------------------------------------------


class VerdictDiscriminationTests(unittest.TestCase):
    """Both directions are pinned, so the check cannot be disarmed silently.

    A stub returning ADMISSIBLE always fails the rejection cases; a stub
    returning ORACLE_CHANGED always fails the admissible case. That pairing is
    this check's own red control (AC-05): there is no constant it can collapse
    to that leaves this class green.
    """

    HONEST = ({"result": "FAIL", "verifier": "v1", "subject": "s1"},
              {"result": "PASS", "verifier": "v1", "subject": "s2"})
    GREENWASH = ({"result": "FAIL", "verifier": "v1", "subject": "s1"},
                 {"result": "PASS", "verifier": "v2", "subject": "s1"})

    def test_the_honest_pair_is_admissible(self) -> None:
        self.assertEqual(regression_pair_verdict(*self.HONEST)["code"], ADMISSIBLE)

    def test_the_greenwash_pair_is_not(self) -> None:
        self.assertEqual(regression_pair_verdict(*self.GREENWASH)["code"], ORACLE_CHANGED)

    def test_no_constant_verdict_can_satisfy_both(self) -> None:
        honest = regression_pair_verdict(*self.HONEST)
        greenwash = regression_pair_verdict(*self.GREENWASH)
        self.assertNotEqual(honest["code"], greenwash["code"])
        self.assertTrue(honest["admissible"])
        self.assertFalse(greenwash["admissible"])

    def test_an_unrecorded_identity_is_not_a_matching_one(self) -> None:
        verdict = regression_pair_verdict(
            {"result": "FAIL", "subject": "s1"}, {"result": "PASS", "subject": "s2"}
        )
        self.assertEqual(verdict["code"], ORACLE_CHANGED)
        self.assertIn("not a matching one", verdict["reason"])

    def test_the_same_verifier_and_the_same_subject_prove_nothing(self) -> None:
        verdict = regression_pair_verdict(
            {"result": "FAIL", "verifier": "v1", "subject": "s1"},
            {"result": "PASS", "verifier": "v1", "subject": "s1"},
        )
        self.assertEqual(verdict["code"], SUBJECT_UNCHANGED)
        self.assertFalse(verdict["admissible"])

    def test_a_pass_to_pass_pair_is_not_a_regression_comparison(self) -> None:
        verdict = regression_pair_verdict(
            {"result": "PASS", "verifier": "v1", "subject": "s1"},
            {"result": "PASS", "verifier": "v1", "subject": "s2"},
        )
        self.assertEqual(verdict["code"], NOT_A_REGRESSION_PAIR)

    def test_the_reason_always_says_what_to_do_next(self) -> None:
        verdict = regression_pair_verdict(*self.GREENWASH)
        self.assertIn("re-establish it against the current oracle", verdict["reason"])

    def test_the_escape_path_for_a_legitimate_test_change_is_written_down(self) -> None:
        text = (ROOT / "saipen" / "phases" / "verify.md").read_text(encoding="utf-8-sig")
        self.assertIn("Changing the verifier is allowed", text)
        self.assertIn("tests are not frozen during a", text)
        self.assertIn("its own red control", text)
        self.assertIn("is not a pair", text)


if __name__ == "__main__":
    unittest.main()

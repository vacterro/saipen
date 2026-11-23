"""T-5: an N/N ratio before a FAIL-family token is evidence, not a count.

Measured on ZAICODER E-86: an honest green verify checkpoint narrated its
red control as "3/3 failure classes fire on the known-bad fixture, 0 findings
on the real tree". `_FAIL_COUNTED_RE` read the bare second digit as three
failures and vetoed a green cycle (VERIFY -> REVIEW refused). Same family as
T-1444 (foreign scope), T-1620 (previous run), T-1762 (red control) and
T-1770 (pair stage): the counted shape carries an attribution the grammar
must honour, and a RATIO is not a count at all.

Pinned both ways: an N/N ratio is exempt, while a bare nonzero count, a
nonzero field and a real FAIL verdict still claim from anywhere so a real
failure can never be talked past.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.log import _claims_failure, verification_evidence  # noqa: E402
from test_verification_grammar import TICKET, events  # noqa: E402

#: The exact text VERIFY -> REVIEW refused (ZAICODER LOG E-86).
E_86 = (
    "verify -> PASS [target: T-2] conf: high -- saipen test suite run T-2 after the control "
    "fix; receipt .saipen/evidence/suite/d79963e056b5d582-20261104T125314568984Z.json "
    "sha256:d58bdf2c37d37b5d43b2a1c5b3788cc367f507a01d816647197a4a307f295f4e. "
    "Detector and control both re-exercised: 3/3 failure classes fire on the known-bad "
    "fixture, 0 findings on the real tree."
)


class TheRefusedCheckpoint(unittest.TestCase):
    def test_the_exact_e86_text_is_not_a_failure_claim(self) -> None:
        self.assertFalse(_claims_failure(E_86))

    def test_the_green_cycle_it_closed_is_accepted(self) -> None:
        ok, reason = verification_evidence(TICKET, events(E_86))
        self.assertTrue(ok, reason)
        self.assertEqual(reason, E_86)


class ARatioIsNotACount(unittest.TestCase):
    def test_ratio_shapes_are_not_failure_claims(self) -> None:
        for text in (
            "verify -> PASS conf: high -- 3/3 failure classes fire on the known-bad fixture",
            "verify -> PASS conf: high -- 7/7 FAIL cases detected on the control",
            "verify -> PASS conf: high -- 12/12 failures caught by the detector",
            "verify -> PASS conf: high -- control 5/5 failed as designed",
            "verify -> PASS conf: high -- 0/3 failure classes fire on the real tree",
        ):
            self.assertFalse(_claims_failure(text), text)

    def test_a_real_count_near_a_ratio_still_claims(self) -> None:
        for text in (
            "verify -> PASS conf: high -- 3/3 controls fire, but 2 FAIL on this run",
            "verify -> PASS conf: high -- detector 3/3, failures=3 on the fixed subject",
            "verify -> PASS conf: high -- 3/3 classes fire; 4 failed this run",
        ):
            self.assertTrue(_claims_failure(text), text)

    def test_a_failing_verdict_is_not_excused_by_a_ratio(self) -> None:
        text = "verify -> FAIL -- 3/3 control classes fire"
        self.assertTrue(_claims_failure(text))
        ok, _reason = verification_evidence(TICKET, events(text))
        self.assertFalse(ok)

    def test_plain_counts_and_fields_are_unchanged(self) -> None:
        for text in (
            "verify -> PASS conf: high -- 3 failures on this run",
            "verify -> PASS conf: high -- 2 FAIL",
            "verify -> PASS conf: high -- failed=3",
        ):
            self.assertTrue(_claims_failure(text), text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

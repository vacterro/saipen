"""The attempt-admission finding is a named, work-owned defect.

Measured on this repository: after the crew-defer closure, `validate --gate core`
emitted `attempt-admission -- ticket T-2163 is DONE but its candidate attempt
A-022 closed at E-23109 with no VERIFY boundary after that close` with
`rule_id: unclassified`, `subject_kind: global`, `subject_id: None`. The
finding therefore routed to OWNER_UNKNOWN instead of the engine that wrote it,
and could never be attached to owning Work.

The message is a normal validator problem, so the one classifier must name it
and give it the Work subject; the ownership table must route the family to
ENGINE_INTERNAL -- no new router, no second rule table.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import findings  # noqa: E402
from saipen_engine.finding_ownership import owner_class  # noqa: E402

ATTEMPT_ADMISSION = (
    "attempt-admission -- ticket T-2163 is DONE but its candidate attempt "
    "A-022 closed at E-23109 with no VERIFY boundary after that close -- "
    "a producer claim admitted without independent verification"
)
SHORT = (
    "attempt-admission -- ticket T-1 is DONE but its candidate attempt "
    "A-001 closed at E-12 with no VERIFY boundary after that close"
)


class RecognitionTests(unittest.TestCase):
    def test_the_attempt_admission_family_is_named(self) -> None:
        row = findings.classify("problem", ATTEMPT_ADMISSION)
        self.assertEqual(row["rule_id"], "attempt_admission")
        self.assertNotEqual(row["rule_id"], "unclassified")

    def test_the_attempt_admission_subject_is_the_work(self) -> None:
        row = findings.classify("problem", ATTEMPT_ADMISSION)
        self.assertEqual(row["subject_kind"], "work")
        self.assertEqual(row["subject_id"], "T-2163")

    def test_a_short_live_message_binds_its_own_ticket(self) -> None:
        row = findings.classify("problem", SHORT)
        self.assertEqual(row["rule_id"], "attempt_admission")
        self.assertEqual(row["subject_id"], "T-1")

    def test_different_tickets_are_different_findings(self) -> None:
        a = findings.classify("problem", ATTEMPT_ADMISSION)
        b = findings.classify("problem", SHORT)
        self.assertNotEqual(a["finding_key"], b["finding_key"])

    def test_the_detail_carries_the_event_not_a_synthetic_id(self) -> None:
        row = findings.classify("problem", ATTEMPT_ADMISSION)
        self.assertEqual(row["detail"], "E-23109,T-2163")

    def test_the_family_routes_to_engine_work(self) -> None:
        row = findings.classify("problem", ATTEMPT_ADMISSION)
        self.assertEqual(owner_class(row["rule_id"]), "ENGINE_INTERNAL")


if __name__ == "__main__":
    unittest.main()

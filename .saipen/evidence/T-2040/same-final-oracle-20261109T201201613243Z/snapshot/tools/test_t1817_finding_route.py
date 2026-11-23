"""SRC-276 R002 / F-01+F-02: a blocked finding routes to its existing owner.

The measured field defect: `cc all` hit `CONFORMANCE_UNHEALTHY` with
`ENGINEERING_REQUIRED, action: null`; the agent then ran `saipen start` with the
blocked finding as its text and minted SRC-011/T-62 over a subject T-57 already
tracked. Nothing was repaired and the project carried a duplicate record.

These controls pin the resolver's contract. They are the reason a continuation
can name existing Work instead of opening a new one, and they pin the two ways
that must still be refused: reopening DONE Work, and guessing between two live
claimants.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import finding_route as R  # noqa: E402


def tickets(**spec) -> dict:
    """Minimal parsed-BOARD shape: section, description, fields."""
    out = {}
    for tid, body in spec.items():
        section, fields = body
        out[tid] = {"id": tid, "section": section, "description": "", "fields": fields}
    return out


def finding(rule_id: str, subject: str) -> dict:
    return {"rule_id": rule_id, "subject_id": subject, "subject_kind": "source"}


class SubjectWorkTests(unittest.TestCase):
    def test_a_work_subject_routes_to_its_own_ticket(self):
        result = R.resolve(
            Path("."),
            finding("work_closure_evidence", "T-7"),
            tickets(**{"T-7": ("## TODO", {})}),
        )
        self.assertEqual(result["code"], "ROUTED_TO_OWNER")
        self.assertEqual(result["owner"], "T-7")
        self.assertEqual(result["linkage"], R.LINKAGE_SUBJECT)

    def test_a_missing_subject_ticket_is_not_invented(self):
        result = R.resolve(
            Path("."),
            finding("work_closure_evidence", "T-999"),
            tickets(**{"T-7": ("## TODO", {})}),
        )
        self.assertEqual(result["code"], "NO_OWNER")
        self.assertIsNone(result["owner"])

    def test_a_done_subject_ticket_is_never_reopened(self):
        result = R.resolve(
            Path("."),
            finding("work_closure_evidence", "T-7"),
            tickets(**{"T-7": ("## DONE", {})}),
        )
        self.assertEqual(result["code"], "DONE_ONLY")
        self.assertIsNone(result["owner"])
        self.assertEqual(result["done"], ["T-7"])


class FamilyRoutingTests(unittest.TestCase):
    def test_an_open_ticket_already_carrying_the_rule_is_the_owner(self):
        blocked = {
            "blocker": "ACTIVE_DEPENDENCY:T-9 -- source_receipt_closed_archive_invalid SRC-003"
        }
        result = R.resolve(
            Path("."),
            finding("source_receipt_closed_archive_invalid", "SRC-003"),
            tickets(**{"T-9": ("## BLOCKED", blocked)}),
        )
        self.assertEqual(result["code"], "ROUTED_TO_OWNER")
        self.assertEqual(result["owner"], "T-9")
        self.assertEqual(result["linkage"], R.LINKAGE_FAMILY)

    def test_a_near_miss_subject_is_not_an_owner(self):
        # SRC-003 must never match SRC-0030: a prefix match would hand a
        # finding to an unrelated ticket.
        blocked = {"blocker": "source_receipt_closed_archive_invalid SRC-0030"}
        result = R.resolve(
            Path("."),
            finding("source_receipt_closed_archive_invalid", "SRC-003"),
            tickets(**{"T-9": ("## BLOCKED", blocked)}),
        )
        self.assertEqual(result["code"], "NO_OWNER")

    def test_two_live_claimants_are_ambiguity_not_a_guess(self):
        field = {"blocker": "source_receipt_closed_archive_invalid SRC-003"}
        result = R.resolve(
            Path("."),
            finding("source_receipt_closed_archive_invalid", "SRC-003"),
            tickets(**{"T-9": ("## BLOCKED", field), "T-10": ("## TODO", dict(field))}),
        )
        self.assertEqual(result["code"], "AMBIGUOUS")
        self.assertIsNone(result["owner"])
        self.assertEqual(result["live"], ["T-9", "T-10"])

    def test_a_done_claimant_does_not_make_a_live_one_ambiguous(self):
        field = {"blocker": "source_receipt_closed_archive_invalid SRC-003"}
        result = R.resolve(
            Path("."),
            finding("source_receipt_closed_archive_invalid", "SRC-003"),
            tickets(**{"T-9": ("## TODO", dict(field)), "T-10": ("## DONE", dict(field))}),
        )
        self.assertEqual(result["code"], "ROUTED_TO_OWNER")
        self.assertEqual(result["owner"], "T-9")


class RouteCommandTests(unittest.TestCase):
    def test_a_routed_finding_names_claim_and_never_start(self):
        result = {"code": "ROUTED_TO_OWNER", "owner": "T-9"}
        command = R.route_command(result)
        self.assertEqual(command, "saipen ticket claim T-9")
        self.assertNotIn("saipen start", command)

    def test_every_other_outcome_invents_no_command(self):
        for code in ("DONE_ONLY", "NO_OWNER", "AMBIGUOUS"):
            self.assertIsNone(R.route_command({"code": code}), code)

    def test_the_measured_duplicate_shape_resolves_instead_of_starting(self):
        # The real shape: a closed-archive finding on SRC-003, while the
        # existing engine-owned ticket for exactly that subject is still open.
        blocked = {
            "blocker": "BLOCKED_EXTERNAL -- SRC-003 archive bundle invalid; "
                       "source_receipt_closed_archive_invalid SRC-003"
        }
        result = R.resolve(
            Path("."),
            finding("source_receipt_closed_archive_invalid", "SRC-003"),
            tickets(**{"T-57": ("## DOING", blocked)}),
        )
        self.assertEqual(result["code"], "ROUTED_TO_OWNER")
        self.assertEqual(R.route_command(result), "saipen ticket claim T-57")


if __name__ == "__main__":
    unittest.main()

"""SRC-276 R005: the ENGINEERING_REQUIRED diagnostic carries typed ownership.

The measured F-11 shape: an unregistered Repair path returned
``ENGINEERING_REQUIRED, owner: SAIPEN conformance/remediation, terminal: true,
action: null``, and the host rendered that internal engine obligation beside a
genuinely operator-gated authority grant as one "blocking actions that need
you" list. An operator was asked to adjudicate an engineering defect, and the
engine-ownable repair was never routed as engine Work.

This oracle is red on the pre-fix engine and green now. It uses the SAME
fixture the conformance repair boundary already uses (a CURRENT_FAIL with no
registered repair), so it measures the real decision path rather than a
synthetic dictionary.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import conformance as C  # noqa: E402
from saipen_engine import finding_ownership as O  # noqa: E402
from saipen_engine import findings  # noqa: E402
import test_conformance_repair_boundary as fixtures  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def diagnostics(*messages: str) -> dict:
    problems = [findings.classify("problem", message) for message in messages]
    return {
        "status": "complete",
        "ruleset_version": findings.RULESET_VERSION,
        "ruleset_fingerprint": findings.ruleset_fingerprint(),
        "problem_count": len(problems),
        "warning_count": 0,
        "problems": problems,
    }


class DiagnosticOwnershipTests(fixtures.RepairBoundaryTests):
    """Reuses the real CURRENT_FAIL fixture; adds the ownership contract."""

    def _engineering_required(self, *messages: str) -> dict:
        root = self.make_project("ownership-" + str(len(messages)))
        receipt = C.generate_conformance_receipt(
            root, gate="core", exit_code=1, blocking_findings=diagnostics(*messages)
        )
        decision = C.conformance_decision(root)
        self.assertEqual(decision["status"], C.STATUS_CURRENT_FAIL)
        self.assertEqual(decision["repair_status"], "ENGINEERING_REQUIRED")
        self.assertEqual(decision["diagnostic"]["receipt_id"], receipt["receipt_id"])
        return decision["diagnostic"]

    def test_engine_owned_findings_reach_the_diagnostic_as_engine_work(self):
        diagnostic = self._engineering_required(
            "closed receipt SRC-003 archive bundle invalid: missing metadata"
        )
        ownership = diagnostic["ownership"]
        self.assertEqual(ownership["engine_work_count"], 1)
        self.assertEqual(ownership["operator_action_count"], 0)
        item = ownership["groups"]["ENGINE_INTERNAL"][0]
        self.assertEqual(item["rule_id"], "source_receipt_closed_archive_invalid")
        self.assertIs(item["operator_action_due"], False)
        self.assertEqual(item["route"], O.ENGINE_ROUTE)
        self.assertNotIn("saipen start", item["route"])

    def test_the_diagnostic_never_claims_a_human_obligation_by_itself(self):
        # The exact F-11 defect: an engine-internal CURRENT_FAIL whose only
        # repair path is engine work must not present as an operator action.
        diagnostic = self._engineering_required(
            "ORPHAN_RECEIPT SRC-009 is not linked to any Work",
            "ticket T-1 is ## DONE but carries no current-cycle verification evidence"
            " (classifier: none)",
        )
        self.assertEqual(diagnostic["operator_action_count"], 0)
        self.assertEqual(diagnostic["engine_work_count"], 2)
        # The generic prose survives: this is an addition, never a replacement.
        self.assertIn("CURRENT_FAIL has no registered executable repair", diagnostic["detail"])

    def test_an_unknown_family_is_reported_unknown_not_silently_owned(self):
        diagnostic = self._engineering_required("some novel defect no rule classifies")
        ownership = diagnostic["ownership"]
        self.assertEqual(ownership["unknown_count"], 1)
        self.assertEqual(ownership["engine_work_count"], 0)
        self.assertEqual(ownership["operator_action_count"], 0)
        unknown = ownership["groups"]["UNKNOWN"][0]
        self.assertEqual(unknown["owner_class"], "UNKNOWN")
        self.assertIsNone(unknown["route"])

    def test_an_unreadable_finding_set_omits_rather_than_invents_ownership(self):
        root = self.make_project("ownership-unavailable")
        C.generate_conformance_receipt(
            root, gate="core", exit_code=1,
            blocking_findings={"status": "unavailable", "reason": "classifier failed"},
        )
        decision = C.conformance_decision(root)
        diagnostic = decision["diagnostic"]
        self.assertEqual(diagnostic["findings_status"], "unavailable")
        # No findings means no ownership opinion: the absence is honest, and no
        # zeroed counters are published as a measurement.
        self.assertNotIn("ownership", diagnostic)
        self.assertEqual(diagnostic.get("engine_work_count"), None)

    def test_ownership_never_mutates_the_receipt_identity(self):
        root = self.make_project("ownership-identity")
        blocking = diagnostics("closed receipt SRC-003 archive bundle invalid: missing metadata")
        receipt = C.generate_conformance_receipt(
            root, gate="core", exit_code=1, blocking_findings=blocking
        )
        first = C.conformance_decision(root)
        second = C.conformance_decision(root)
        self.assertEqual(first["diagnostic"]["ownership"], second["diagnostic"]["ownership"])
        current = C.conformance_decision(root)["status_block"]["receipt"]
        self.assertEqual(current["blocking_findings"], blocking)
        self.assertEqual(current["receipt_id"], receipt["receipt_id"])
        self.assertNotIn("ownership", current)


class HandoffSeparationTests(unittest.TestCase):
    """The two obligations a host must render differently stay distinct."""

    def test_engine_work_is_routed_without_an_operator_question(self):
        action = O.safe_next_action(
            {"rule_id": "source_receipt_orphan", "subject_id": "SRC-009"}
        )
        self.assertEqual(action["owner_class"], "ENGINE_INTERNAL")
        self.assertIs(action["operator_action_due"], False)
        self.assertEqual(action["route"], "saipen continue")

    def test_external_obligation_blocks_its_own_ticket_not_the_operator(self):
        action = O.safe_next_action(
            {"rule_id": "producer_package_malformed", "subject_id": "SRC-010"},
            work="T-1817",
        )
        self.assertEqual(action["owner_class"], "UNAVAILABLE_EXTERNAL")
        self.assertIs(action["operator_action_due"], False)
        self.assertRegex(action["route"], r"saipen ticket block T-1817")

    def test_only_a_witnessed_scoped_decision_renders_a_human_action(self):
        finding = {"rule_id": "source_credential_unsafe", "subject_id": "SRC-003"}
        self.assertIs(
            O.safe_next_action(finding)["operator_action_due"], False
        )
        self.assertIs(
            O.safe_next_action(
                finding, decision={"witness": "model_supplied", "subject": "SRC-003"}
            )["operator_action_due"],
            False,
        )
        witnessed = O.safe_next_action(
            finding, decision={"witness": "operator", "subject": "SRC-003"}
        )
        self.assertIs(witnessed["operator_action_due"], True)
        self.assertEqual(witnessed["route"], O.OPERATOR_ROUTE)


if __name__ == "__main__":
    unittest.main()

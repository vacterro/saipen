"""SRC-276 R005 / F-11: typed finding ownership never invents a human action.

The measured defect: the engine answered ``ENGINEERING_REQUIRED`` with
``action: null`` for an internal engine repair, and the host rendered that
alongside a genuinely operator-gated authority grant as one list of "Blocking
actions that need you". An agent then asked the operator to authorize an
engine-ownable defect, and the operator was asked to make an engineering
decision that was never theirs.

These controls pin the two contracts the routing depends on:

* a known rule has ONE stable owner class, and an engine-ownable finding never
  renders an operator action nor routes to a new consumer ``start``;
* only a WITNESSED, subject-matching decision renders ``operator_action_due``,
  so the class alone never manufactures authority;
* ownership is derived presentation metadata: it must not change a finding's
  ``finding_key``/``detail_hash``/``ruleset_fingerprint``, because that would
  stale every debt snapshot.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import finding_ownership as O  # noqa: E402
from saipen_engine import findings  # noqa: E402


def finding(rule_id: str, subject: str = "SRC-003") -> dict:
    return {"rule_id": rule_id, "subject_kind": "source", "subject_id": subject,
            "finding_key": "0" * 16, "severity": "problem"}


class OwnerTableTests(unittest.TestCase):
    def test_every_mapped_rule_exists_in_the_classifier(self):
        known = {rule["rule_id"] for rule in findings.RULE_TABLE}
        unknown = sorted(set(O._RULE_OWNERS) - known)
        self.assertEqual(unknown, [], f"ownership maps rules that do not exist: {unknown}")

    def test_every_classifier_rule_has_a_typed_owner(self):
        # An unmapped rule is UNKNOWN by design, but that must be a deliberate
        # gap rather than a rule family nobody ever classified.
        unmapped = sorted(
            rule["rule_id"] for rule in findings.RULE_TABLE
            if rule["rule_id"] not in O._RULE_OWNERS
        )
        self.assertEqual(unmapped, [], f"rule families without a typed owner: {unmapped}")

    def test_owner_classes_are_the_closed_set(self):
        for rule_id in O._RULE_OWNERS:
            self.assertIn(O.owner_class(rule_id), findings.OWNER_CLASSES, rule_id)

    def test_an_unknown_rule_is_unknown_never_engine_ownable(self):
        self.assertEqual(O.owner_class("no_such_rule"), "UNKNOWN")
        self.assertEqual(O.owner_class(None), "UNKNOWN")
        action = O.safe_next_action({"rule_id": "no_such_rule"})
        self.assertEqual(action["owner_class"], "UNKNOWN")
        self.assertIsNone(action["route"])
        self.assertIs(action["operator_action_due"], False)
        self.assertTrue(action["detail"])


class EngineOwnershipTests(unittest.TestCase):
    def test_engine_finding_never_asks_the_operator(self):
        for rule_id, owner in O._RULE_OWNERS.items():
            if owner != "ENGINE_INTERNAL":
                continue
            action = O.safe_next_action(finding(rule_id))
            self.assertIs(action["operator_action_due"], False, rule_id)
            self.assertEqual(action["route"], O.ENGINE_ROUTE, rule_id)

    def test_engine_route_is_never_a_new_consumer_start(self):
        # SRC-276 F-01/F-11: ENGINEERING_REQUIRED -> `saipen start` in the
        # consumer project -> ENGINEERING_REQUIRED again. The route must be the
        # engine's own continuation.
        for rule_id, owner in O._RULE_OWNERS.items():
            if owner != "ENGINE_INTERNAL":
                continue
            route = O.safe_next_action(finding(rule_id))["route"]
            self.assertNotIn("saipen start", route, rule_id)

    def test_external_finding_names_the_block_not_an_operator_action(self):
        action = O.safe_next_action(finding("producer_package_malformed", "T-1"), work="T-1817")
        self.assertEqual(action["owner_class"], "UNAVAILABLE_EXTERNAL")
        self.assertIs(action["operator_action_due"], False)
        self.assertIn("BLOCKED_EXTERNAL", action["route"])
        self.assertIn("T-1817", action["route"])


class OperatorDecisionTests(unittest.TestCase):
    def test_the_class_alone_renders_no_human_action(self):
        action = O.safe_next_action(finding("source_credential_unsafe"))
        self.assertEqual(action["owner_class"], "OPERATOR_DECISION")
        self.assertIs(action["operator_action_due"], False)
        self.assertIsNone(action["route"])

    def test_a_model_supplied_capsule_is_not_operator_authority(self):
        for witness in ("model_supplied", "model", "", None):
            action = O.safe_next_action(
                finding("source_credential_unsafe"),
                decision={"witness": witness, "subject": "SRC-003"},
            )
            self.assertIs(action["operator_action_due"], False, witness)
            self.assertIsNone(action["route"], witness)

    def test_a_witnessed_decision_about_another_subject_grants_nothing(self):
        action = O.safe_next_action(
            finding("source_credential_unsafe"),
            decision={"witness": "operator", "subject": "SRC-999"},
        )
        self.assertIs(action["operator_action_due"], False)
        self.assertIsNone(action["route"])

    def test_a_witnessed_scoped_decision_renders_the_one_operator_action(self):
        decision = {"witness": "operator", "subject": "SRC-003"}
        action = O.safe_next_action(
            finding("source_credential_unsafe"), decision=decision
        )
        self.assertIs(action["operator_action_due"], True)
        self.assertEqual(action["route"], O.OPERATOR_ROUTE)
        self.assertEqual(action["decision"], decision)


class ProjectionTests(unittest.TestCase):
    def test_partition_separates_the_two_obligations(self):
        projected = O.partition(
            [
                finding("source_receipt_orphan", "SRC-001"),
                finding("work_closure_evidence", "T-1"),
                finding("producer_package_malformed", "SRC-002"),
                finding("source_credential_unsafe", "SRC-003"),
                finding("no_such_rule", "SRC-004"),
            ]
        )
        groups = projected["groups"]
        self.assertEqual(len(groups["ENGINE_INTERNAL"]), 2)
        self.assertEqual(projected["engine_work_count"], 2)
        self.assertEqual(projected["external_count"], 1)
        self.assertEqual(projected["unknown_count"], 1)
        # The credential finding is operator-classed but NOT witnessed, so the
        # human count is zero: a class is not an obligation.
        self.assertEqual(len(groups["OPERATOR_DECISION"]), 1)
        self.assertEqual(projected["operator_action_count"], 0)

    def test_ownership_never_changes_finding_identity(self):
        # A projection is derived metadata. If it reached finding_key,
        # detail_hash or the ruleset fingerprint, every debt snapshot would
        # refuse comparison (BASELINE_RULESET_CHANGED).
        message = "closed receipt SRC-003 archive bundle invalid: missing metadata"
        before = findings.classify("problem", message)
        fingerprint = findings.ruleset_fingerprint()
        O.projection(before)
        after = findings.classify("problem", message)
        self.assertEqual(before, after)
        self.assertEqual(findings.ruleset_fingerprint(), fingerprint)
        self.assertNotIn("owner_class", after)
        self.assertNotIn("operator_action_due", after)

    def test_projection_carries_no_message_content(self):
        # Presentation safety: a projection is identity + ownership only, so a
        # credential finding cannot leak through it.
        message = (
            "source credential gate: SOURCE_CREDENTIALS_UNSAFE credential pattern "
            "sk-live-DO-NOT-LEAK-9f8e7d6c5b4a in exact archive source SRC-033"
        )
        projected = O.projection(findings.classify("problem", message))
        rendered = repr(projected)
        self.assertNotIn("sk-live", rendered)
        self.assertNotIn("DO-NOT-LEAK", rendered)


if __name__ == "__main__":
    unittest.main()

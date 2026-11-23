"""Shared blocker diagnostics preserve scheduling and authority (SRC-289 W1)."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import audit_inbox, board, response_surface, router  # noqa: E402
from test_t1807_audit_liveness_regression import _valid_state_text  # noqa: E402


def ticket(tid, blocker="", *, needs=(), section="## BLOCKED"):
    return {"id": tid, "section": section, "checkbox": " ", "needs": list(needs),
            "fields": {"blocker": blocker}, "priority": "P2"}


def shared_case():
    items = {
        "T-1317": ticket("T-1317", "BLOCKED_EXTERNAL -- native host unavailable"),
        "T-1815": ticket("T-1815", "publication blocked: 206 foreign pre-existing staged paths"),
        "T-1816": ticket("T-1816", "PUBLICATION_STAGING_BLOCKED: 206 foreign paths"),
        "T-1817": ticket("T-1817", "PUBLICATION_STAGING_BLOCKED: 206 foreign paths"),
        "T-1856": ticket("T-1856", "publication blocked: the same 206 foreign pre-staged paths"),
    }
    for number in (1853, 1854, 1855):
        tid = f"T-{number}"
        items[tid] = ticket(tid, needs=("T-1815",), section="## TODO")
    return items


def audit_case(items):
    state = {"layers": [{"layer": 1, "rel": "audit/1.md", "receipt_id": "SRC-001",
                         "linked_work": "T-1317", "sha256": "abc",
                         "state": audit_inbox.ACTIVE}],
             "residue": [], "orphans": [], "corrupt": False}
    return audit_inbox.projection_from_classification(state, tickets=items)


def board_text(items):
    lines = []
    for section in board.REQUIRED_HEADINGS:
        lines.append(section)
        for tid, item in items.items():
            if item["section"] != section:
                continue
            line = f"- [ ] {tid} [P2] fixture"
            if item["needs"]:
                line += " | needs: " + ",".join(item["needs"])
            if item["fields"].get("blocker"):
                line += " | blocker: " + item["fields"]["blocker"]
            lines.append(line)
    return "\n".join(lines) + "\n"


class SharedBlockerTests(unittest.TestCase):
    def projection(self, items):
        project = getattr(board, "project_blockers", None)
        self.assertIsNotNone(project, "BOARD has no canonical shared-blocker projection")
        return project(items)

    def test_publication_aliases_use_existing_operator_class(self):
        items = shared_case()
        for tid in ("T-1815", "T-1816", "T-1817", "T-1856"):
            with self.subTest(ticket=tid):
                self.assertEqual(board.resolve_root_blocker(tid, items)[1], "WAIT_USER_DECISION")

    def test_projection_groups_roots_and_transitive_todo_without_mutation(self):
        items = shared_case()
        before = copy.deepcopy(items)
        projected = self.projection(items)
        group = next(g for g in projected["groups"] if g["cause"] == "publication-staging")
        self.assertEqual(set(group["root_tickets"]), {"T-1815", "T-1816", "T-1817", "T-1856"})
        self.assertEqual(set(group["dependent_tickets"]), {"T-1853", "T-1854", "T-1855"})
        self.assertEqual(group["owner"], "tools/saipen_engine/release.py")
        self.assertFalse(group["recovery_internally_authorized"])
        self.assertTrue(group["external_input_required"])
        self.assertTrue(group["read_only_work_may_proceed"])
        self.assertTrue(group["resumption_preconditions"])
        self.assertEqual(group["recovery_operation"]["command"], None)
        self.assertTrue(group["recovery_operation"]["operator_action"])
        self.assertEqual(items, before)

    def test_each_blocked_item_has_one_complete_diagnostic(self):
        items = shared_case()
        projection = self.projection(items)
        required = {"blocker_class", "root_cause", "owner", "shared_blocker_id",
                    "dependent_tickets", "recovery_internally_authorized",
                    "external_input_required", "read_only_work_may_proceed",
                    "recovery_operation", "resumption_preconditions"}
        for tid, item in items.items():
            if item["section"] == "## BLOCKED":
                self.assertLessEqual(required, projection["items"][tid].keys())

    def test_multiple_dependency_roots_are_retained(self):
        items = shared_case()
        items["T-2000"] = ticket("T-2000", needs=("T-1815", "T-1317"), section="## TODO")
        result = self.projection(items)
        self.assertEqual(set(result["items"]["T-2000"]["root_tickets"]), {"T-1815", "T-1317"})

    def test_dependency_cycle_is_not_recoverable_or_complete(self):
        items = {"T-1": ticket("T-1", "ACTIVE_DEPENDENCY:T-2", needs=("T-2",)),
                 "T-2": ticket("T-2", "ACTIVE_DEPENDENCY:T-1", needs=("T-1",))}
        result = self.projection(items)
        self.assertTrue(result["items"])
        self.assertFalse(any(g["recovery_internally_authorized"] for g in result["groups"]))
        self.assertFalse(board.classify_idle_work(items)["all_requirements_complete"])

    def test_incidental_words_do_not_grant_staging_recovery_authority(self):
        items = {"T-1": ticket("T-1", "UNKNOWN -- example: PUBLICATION_STAGING_BLOCKED")}
        result = self.projection(items)
        self.assertEqual(result["items"]["T-1"]["blocker_class"], "UNKNOWN")
        self.assertFalse(result["items"]["T-1"]["recovery_internally_authorized"])

    def test_shared_release_obstruction_is_prioritized_over_older_external_work(self):
        result = board.classify_idle_work(shared_case())
        self.assertEqual(result["disposition"], "IDLE_OPERATOR_REQUIRED")
        self.assertEqual(result["primary_blocker"]["cause"], "publication-staging")
        self.assertIn("T-1317", result["externally_blocked"])
        self.assertFalse(result["all_requirements_complete"])

    def test_102_blocked_and_three_todo_never_mean_all_complete(self):
        items = shared_case()
        for number in range(100, 197):
            tid = f"T-{number}"
            items[tid] = ticket(tid, "BLOCKED_EXTERNAL -- upstream")
        self.assertEqual(sum(t["section"] == "## BLOCKED" for t in items.values()), 102)
        result = board.classify_idle_work(items)
        self.assertFalse(result["all_requirements_complete"])
        self.assertEqual(result["stop_reason"], "NO_ADMISSIBLE_WORK")

    def test_audit_uses_project_wide_shared_blocker_owner(self):
        result = audit_case(shared_case())
        self.assertEqual(result["idle_classification"], "IDLE_OPERATOR_REQUIRED")
        self.assertEqual(result["primary_blocker"]["cause"], "publication-staging")
        self.assertEqual(result["next_exact_action"], "saipen status")

    def test_router_carries_the_actionable_blocker_with_no_synthetic_progress(self):
        items = shared_case()
        result = router.route_next(
            _valid_state_text(), board_text(items), audit_inbox=audit_case(items)
        )
        self.assertEqual(result["primary_blocker"]["cause"], "publication-staging")
        self.assertEqual(result["executable_behavior"], "RESTATE_AND_STOP")
        self.assertNotEqual(result["terminal_classification"], "ALL_WORK_COMPLETE")

    def test_independent_work_still_runs_before_blocker_diagnostics(self):
        items = shared_case()
        items["T-9999"] = ticket("T-9999", section="## TODO")
        result = router.route_next(
            _valid_state_text(), board_text(items), audit_inbox=audit_case(items)
        )
        self.assertEqual(result["ticket"], "T-9999")
        self.assertEqual(result["action"], "PHASE SCOUT T-9999")

    def test_human_status_cannot_look_complete_while_automation_is_blocked(self):
        text = response_surface.digest_from_facts({
            "phase": "DONE", "task": "none", "automation": {"disposition": "BLOCKED"},
            "blockers": [{"ticket": "T-1", "blocker": "BLOCKED_EXTERNAL"}],
            "validation": "CURRENT_FAIL", "next_action": "NONE",
        }, language="en")
        self.assertIn("STATUS: BLOCKED", text)
        self.assertNotIn("STATUS: DONE", text)
        self.assertNotIn("RESULT: Complete", text)

    def test_done_phase_alone_cannot_claim_campaign_completion(self):
        text = response_surface.digest_from_facts({"phase": "DONE", "task": "none"}, language="en")
        self.assertNotIn("RESULT: Complete", text)

    def test_idle_verdict_round_trips_through_the_authoritative_checker(self):
        for disposition in ("BLOCKED", "WAIT_USER", "WAIT_EXTERNAL", "INVALID"):
            with self.subTest(disposition=disposition):
                due = disposition == "WAIT_USER"
                facts = {
                    "phase": "DONE", "task": "none", "validation": "CURRENT_FAIL",
                    "automation": {"disposition": disposition, "operator_action_due": due},
                    "blockers": [{"ticket": "T-1", "blocker": "BLOCKED_EXTERNAL"}],
                    "next_action": "NONE",
                }
                text = response_surface.digest_from_facts(facts, language="en")
                self.assertEqual(response_surface.response_errors(
                    text, current_phase="DONE", current_task="none",
                    current_idle_disposition=disposition, operator_due=due,
                ), [])
                self.assertNotIn("STATUS: DONE", text)

    def test_idle_projection_cannot_waive_an_active_phase_or_claim_done(self):
        for phase, claimed in (("BUILD", "BLOCKED"), ("DONE", "DONE")):
            facts = {
                "phase": phase, "task": "none", "validation": "CURRENT_FAIL",
                "automation": {"disposition": "BLOCKED"},
                "blockers": [{"ticket": "T-1", "blocker": "BLOCKED_EXTERNAL"}],
                "next_action": "NONE",
            }
            text = response_surface.digest_from_facts(facts, language="en")
            text = text.replace(text.splitlines()[0], f"STATUS: {claimed}", 1)
            self.assertTrue(response_surface.response_errors(
                text, current_phase=phase, current_task="none",
                current_idle_disposition="BLOCKED",
            ))


if __name__ == "__main__":
    unittest.main()

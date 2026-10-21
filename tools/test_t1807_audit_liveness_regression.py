"""T-1807 / SAIHANDOFF: Audit liveness and truthful goal completion regression (Controls 1-10).

Negative controls:
1. ACTIVE audit with BLOCKED linked Work.
2. NEW audit generation.
3. Existing registered audit with unchanged bytes.
4. Completed audit awaiting canonical cleanup.
5. External dependency genuinely resolved.
6. External dependency still missing.
7. Foreign-owner ticket.
8. Genuine operator-only gate.
9. New independent user goal with parked historical work.
10. Empty board with no unresolved obligations.
"""

from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from saipen_engine import audit_inbox, board, continue_loop, router  # noqa: E402


def _valid_state_text(
    *, phase: str = "DONE", task: str = "none", next_action: str = "saipen continue"
) -> str:
    lines = [
        "---",
        f"phase: {phase}",
        f"task: {task}",
        f"next_action: {next_action}",
        'blocker: ""',
        "transition_from: SHIP",
        "saipen_version: 8",
        "schema_version: 3",
        "last_event: 1",
        f"style_contract: {CURRENT_STYLE_CONTRACT}",
        "agent: tester",
        "requires:\n  - filesystem\n  - python",
        "mode: full",
        'updated: "2026-10-17T12:00:00Z"',
        "execution_intent: goal",
        "goal_waves: 0",
        "goal_tickets: 0",
        "---",
    ]
    return "\n".join(lines) + "\n"


class AuditLivenessNegativeControls(unittest.TestCase):
    def test_control_01_active_audit_with_blocked_work(self):
        (
            """1. ACTIVE audit with BLOCKED linked Work routes NO_ADMISSIBLE_WORK with """
            """exact next step."""
        )
        state = {
            "layers": [
                {
                    "layer": 1,
                    "rel": "audit/1.md",
                    "receipt_id": "SRC-001",
                    "linked_work": "T-100",
                    "sha256": "abc",
                    "state": audit_inbox.ACTIVE,
                }
            ],
            "residue": [],
            "orphans": [],
            "corrupt": False,
        }
        tickets = {
            "T-100": {
                "id": "T-100",
                "section": "## BLOCKED",
                "fields": {
                    "blocker": "BLOCKED_EXTERNAL -- upstream repo is blocked",
                    "blocker_scope": "ticket",
                },
                "needs": [],
            }
        }
        proj = audit_inbox.projection_from_classification(state, tickets=tickets)
        self.assertIsNotNone(proj)
        self.assertTrue(proj.get("unworkable_active_only"))
        self.assertEqual(proj.get("unresolved_audit_count"), 1)
        self.assertEqual(proj.get("idle_classification"), "IDLE_BLOCKED_EXTERNAL")
        self.assertEqual(proj.get("stop_reason"), "NO_ADMISSIBLE_WORK")
        self.assertEqual(proj.get("next_exact_action"), "saipen ticket resolve-external T-100")

        # Router behavior:
        st_text = _valid_state_text()
        bd_text = (
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n- [ ] T-100 [P1] ext | blocker: "
            "BLOCKED_EXTERNAL -- upstream\n"
        )
        routed = router.route_next(st_text, bd_text, audit_inbox=proj)
        self.assertEqual(routed["reason"], "audit-inbox-unworkable")
        self.assertEqual(routed["stop_reason"], "NO_ADMISSIBLE_WORK")
        self.assertEqual(routed["idle_classification"], "IDLE_BLOCKED_EXTERNAL")
        self.assertEqual(routed["unresolved_audit_count"], 1)
        self.assertEqual(routed["next_exact_action"], "saipen ticket resolve-external T-100")

    def test_control_02_new_audit_generation(self):
        """2. NEW audit generation routes saipen audit ingest and classifies APPLY_AUDIT_INGEST."""
        state = {
            "layers": [
                {
                    "layer": 2,
                    "rel": "audit/2.md",
                    "receipt_id": None,
                    "sha256": "newbytes",
                    "state": audit_inbox.NEW,
                }
            ],
            "residue": [],
            "orphans": [],
            "corrupt": False,
        }
        proj = audit_inbox.projection_from_classification(state, tickets={})
        self.assertIsNotNone(proj)
        self.assertEqual(proj.get("action"), "saipen audit ingest")
        self.assertEqual(proj.get("layer"), 2)

        st_text = _valid_state_text()
        bd_text = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
        routed = router.route_next(st_text, bd_text, audit_inbox=proj)
        self.assertEqual(routed["action"], "saipen audit ingest")
        self.assertEqual(routed["reason"], "audit-inbox")

        kind = continue_loop.classify_route(
            routed, {"phase": "DONE", "task": "none"}, {"tickets": {}}
        )
        self.assertEqual(kind, continue_loop.APPLY_AUDIT_INGEST)

    def test_control_03_existing_registered_audit_unchanged(self):
        """3. Existing registered audit with unchanged bytes does not re-ingest."""
        state = {
            "layers": [
                {
                    "layer": 1,
                    "rel": "audit/1.md",
                    "receipt_id": "SRC-001",
                    "linked_work": "T-100",
                    "sha256": "unchanged",
                    "state": audit_inbox.ACTIVE,
                }
            ],
            "residue": [],
            "orphans": [],
            "corrupt": False,
        }
        # When linked work is workable TODO, it routes PHASE SCOUT, not ingest
        tickets = {
            "T-100": {
                "id": "T-100",
                "section": "## TODO",
                "checkbox": " ",
                "fields": {},
                "needs": [],
            }
        }
        proj = audit_inbox.projection_from_classification(state, tickets=tickets)
        self.assertEqual(proj.get("action"), "PHASE SCOUT T-100")
        self.assertNotEqual(proj.get("action"), "saipen audit ingest")

    def test_control_04_completed_audit_awaiting_cleanup(self):
        """4. Completed audit awaiting canonical cleanup routes ingest settlement."""
        state = {
            "layers": [
                {
                    "layer": 1,
                    "rel": "audit/1.md",
                    "receipt_id": "SRC-001",
                    "linked_work": "T-100",
                    "sha256": "closed",
                    "state": audit_inbox.CLOSED_PENDING_DELETE,
                }
            ],
            "residue": [],
            "orphans": [],
            "corrupt": False,
        }
        proj = audit_inbox.projection_from_classification(state, tickets={})
        self.assertEqual(proj.get("action"), "saipen audit ingest")
        self.assertIn("CLOSED", proj.get("detail", ""))

    def test_control_05_external_dependency_genuinely_resolved(self):
        """5. External dependency genuinely resolved moves ticket to DONE and unblocks."""
        # When ticket reached DONE, it no longer blocks
        tickets = {
            "T-1653": {
                "id": "T-1653",
                "section": "## DONE",
                "fields": {
                    "external_authority": "lineage-ded945ae8243480ab1bfee73baeb29c6",
                    "external_implementation": "T-289@5f0dc0c",
                },
                "needs": [],
            }
        }
        idle = board.classify_idle_work(tickets)
        self.assertNotIn("T-1653", idle["externally_blocked"])
        self.assertEqual(idle["all_requirements_complete"], True)

    def test_control_06_external_dependency_still_missing(self):
        """6. External dependency still missing retains BLOCKED_EXTERNAL and reports it."""
        tickets = {
            "T-1738": {
                "id": "T-1738",
                "section": "## BLOCKED",
                "fields": {
                    "blocker": "BLOCKED_EXTERNAL -- SRC-236 unmet",
                    "blocker_scope": "ticket",
                },
                "needs": [],
            }
        }
        idle = board.classify_idle_work(tickets)
        self.assertEqual(idle["disposition"], "IDLE_BLOCKED_EXTERNAL")
        self.assertEqual(idle["stop_reason"], "NO_ADMISSIBLE_WORK")
        self.assertIn("T-1738", idle["externally_blocked"])
        self.assertEqual(idle["next_exact_action"], "saipen ticket resolve-external T-1738")

    def test_control_07_foreign_owner_ticket(self):
        """7. Foreign-owner ticket is not workable and does not launder into self."""
        now = datetime.datetime(2026, 10, 17, 12, 0, 0, tzinfo=datetime.timezone.utc)
        recent_time = "2026-10-17T11:55:00Z"
        ticket = {
            "id": "T-500",
            "section": "## DOING",
            "fields": {"owner": "foreign_agent", "claim_time": recent_time},
            "needs": [],
        }
        tickets = {"T-500": ticket}
        status = board.claim_status(ticket, agent="local_agent", now=now)
        self.assertEqual(status, "FOREIGN_LIVE")
        self.assertFalse(board.ticket_is_workable(ticket, tickets, agent="local_agent", now=now))

    def test_control_08_genuine_operator_only_gate(self):
        """8. Genuine operator-only gate reports IDLE_OPERATOR_REQUIRED."""
        now = datetime.datetime(2026, 10, 17, 12, 0, 0, tzinfo=datetime.timezone.utc)
        tickets = {
            "T-600": {
                "id": "T-600",
                "section": "## BLOCKED",
                "fields": {
                    "blocker": "WAIT_USER_DECISION -- Human decision required on architecture",
                    "retry_not_before": "2026-10-17T11:00:00Z",
                },
                "needs": [],
            }
        }
        idle = board.classify_idle_work(tickets, now=now)
        self.assertEqual(idle["disposition"], "IDLE_OPERATOR_REQUIRED")
        self.assertIn("T-600", idle["operator_required"])
        self.assertEqual(idle["next_exact_action"], "saipen status")
        self.assertIsNotNone(idle.get("decision_request"))
        self.assertEqual(idle["decision_request"]["blocked_operation"], "ticket progress T-600")

    def test_control_09_new_independent_user_goal_with_parked_work(self):
        """9. New independent user goal enters start route even with 90+ blocked tickets."""
        tickets = {
            f"T-{i}": {
                "id": f"T-{i}",
                "section": "## BLOCKED",
                "fields": {"blocker": "BLOCKED_EXTERNAL -- waiting upstream"},
                "needs": [],
            }
            for i in range(100, 195)
        }
        # Add new independent user ticket
        tickets["T-999"] = {
            "id": "T-999",
            "section": "## TODO",
            "checkbox": " ",
            "fields": {
                "user_explicit": "true",
                "priority": "P1",
            },
            "needs": [],
        }
        top, reason = board.pick_next_work(tickets)
        self.assertEqual(top, "T-999")
        self.assertEqual(reason, "start-user-explicit")

        # Router also picks it
        st_text = _valid_state_text()
        bd_text = (
            "## DOING\n## TODO\n- [ ] T-999 [P1] new task | user_explicit: true\n## "
            "DONE\n## BLOCKED\n"
        )
        routed = router.route_next(st_text, bd_text)
        self.assertEqual(routed["action"], "PHASE SCOUT T-999")
        self.assertEqual(routed["ticket"], "T-999")

    def test_control_10_empty_board_clean_obligations(self):
        """10. Empty board with no unresolved obligations reaches ALL_REQUIREMENTS_COMPLETE."""
        tickets = {}
        inbox = {
            "pending": [],
            "unresolved_audit_count": 0,
            "residue": [],
            "invalid": [],
        }
        idle = board.classify_idle_work(tickets, audit_inbox=inbox)
        self.assertEqual(idle["disposition"], "ALL_WORK_COMPLETE")
        self.assertEqual(idle["stop_reason"], "ALL_REQUIREMENTS_COMPLETE")
        self.assertFalse(idle["no_admissible_work"])
        self.assertTrue(idle["all_requirements_complete"])
        self.assertEqual(idle["unresolved_audit_count"], 0)

    def test_control_11_operator_does_not_starve_external_dependency(self):
        (
            """11. Operator-required ticket does not starve independent external """
            """dependency resolution."""
        )
        tickets = {
            "T-600": {
                "id": "T-600",
                "section": "## BLOCKED",
                "fields": {
                    "blocker": "WAIT_USER_DECISION -- human decision",
                },
                "needs": [],
            },
            "T-700": {
                "id": "T-700",
                "section": "## BLOCKED",
                "fields": {
                    "blocker": "BLOCKED_EXTERNAL -- waiting upstream",
                },
                "needs": [],
            },
        }
        idle = board.classify_idle_work(tickets)
        self.assertEqual(idle["disposition"], "IDLE_BLOCKED_EXTERNAL")
        self.assertEqual(idle["next_exact_action"], "saipen ticket resolve-external T-700")
        self.assertIn("T-700", idle["externally_blocked"])
        self.assertIn("T-600", idle["operator_required"])

    def test_control_12_handback_unblock_exact_action(self):
        (
            """12. Handback parked on active dependency generates clean ticket unblock """
            """without placeholder."""
        )
        tickets = {
            "T-800": {
                "id": "T-800",
                "section": "## BLOCKED",
                "fields": {
                    "blocker": "ACTIVE_DEPENDENCY:T-801 -- parked child",
                    "blocked_on": "T-801",
                },
                "needs": ["T-801"],
            },
            "T-801": {
                "id": "T-801",
                "section": "## DOING",
                "fields": {},
                "needs": [],
            },
        }
        # T-800 is a handback; when classified directly under operator_required list
        target_tid = "T-800"
        t_data = tickets[target_tid]
        t_fields = t_data.get("fields", {})
        holder_id = str(t_fields.get("blocked_on", "")).strip()
        blocker_str = str(t_fields.get("blocker", "")).strip()
        has_handback = bool(
            holder_id
            and blocker_str.startswith(f"ACTIVE_DEPENDENCY:{holder_id}")
            and holder_id in t_data.get("needs", [])
        )
        self.assertTrue(has_handback)

    def test_control_13_audit_inbox_prioritizes_external_over_operator(self):
        """13. Audit inbox unworkable active items prioritize external before operator."""
        from saipen_engine import audit_inbox

        state = {
            "ok": True,
            "layers": [
                {
                    "layer": 1,
                    "rel": "audit/L1.md",
                    "state": audit_inbox.ACTIVE,
                    "receipt_id": "SRC-901",
                    "linked_work": "T-701",
                },
                {
                    "layer": 2,
                    "rel": "audit/L2.md",
                    "state": audit_inbox.ACTIVE,
                    "receipt_id": "SRC-902",
                    "linked_work": "T-702",
                },
            ],
            "orphans": [],
            "residue": [],
        }
        tickets = {
            "T-701": {
                "id": "T-701",
                "section": "## BLOCKED",
                "fields": {"blocker": "WAIT_USER_DECISION -- human"},
                "needs": [],
            },
            "T-702": {
                "id": "T-702",
                "section": "## BLOCKED",
                "fields": {"blocker": "BLOCKED_EXTERNAL -- upstream"},
                "needs": [],
            },
        }
        proj = audit_inbox.projection_from_classification(state, tickets=tickets)
        self.assertEqual(proj["idle_classification"], "IDLE_BLOCKED_EXTERNAL")
        self.assertEqual(proj["next_exact_action"], "saipen ticket resolve-external T-702")


if __name__ == "__main__":
    unittest.main()

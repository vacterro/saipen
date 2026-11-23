"""T-1715: block-for is the active-parent handoff, never a queue reservation.

The active-parent handoff saves the parent's resume phase tuple so a DOING
parent parks behind a workable TODO child. The generic TODO-block path used to
accept ``block-for`` on a merely TODO parent as well and stored STATE's
UNRELATED active phase as that parent's resume (E-14412/E-14444): a never-built
ticket was later resumed in VERIFY, a phase it never reached. This suite pins
the owned-active-DOING-parent contract and its refusals:

  RED 1  an unopened ## TODO parent refuses with ZERO canonical writes.
  RED 2  an unclaimed parent refuses with zero canonical writes.
  RED 3  a foreign-claimed parent refuses with zero canonical writes.
  GREEN  the legitimate owned active-parent handoff still parks the parent with
         a valid resume phase tuple.
  GREEN  ordinary legal TODO ``block`` is a different operation and still works.

Run standalone:
    python tools/test_t1715_block_for_parent_guard.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_dependency_resume_liveness import AGENT, ResumeFixture  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine.operations import (  # noqa: E402
    apply_claim,
    ticket_move,
    transition_phase,
)


def setUpModule():
    isolate_host_session()


class BlockForParentGuardTests(ResumeFixture):
    def canonical_bytes(self, project: Path) -> tuple[str, str, str]:
        base = project / ".saipen"
        return (
            (base / "BOARD.md").read_text(encoding="utf-8"),
            (base / "STATE.md").read_text(encoding="utf-8"),
            (base / "LOG.md").read_text(encoding="utf-8"),
        )

    def test_3_block_for_on_unopened_todo_parent_refuses_with_zero_writes(self):
        project = self.make_project()
        active = self.add(project, "active work in verify")
        todo_parent = self.add(project, "unopened todo parent")
        todo_child = self.add(project, "unopened todo child")

        self.assertTrue(apply_claim(project, active, AGENT, explicit=True).ok)
        self.assertTrue(transition_phase(project, "BUILD", AGENT, active, "build complete").ok)
        self.assertTrue(transition_phase(project, "VERIFY", AGENT, active, "verify in progress").ok)

        before = self.canonical_bytes(project)
        result = ticket_move(
            project,
            "block-for",
            todo_parent,
            AGENT,
            "try to borrow the active handoff for an unopened item",
            blocked_on=todo_child,
        )

        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "ILLEGAL_TICKET_LIFECYCLE")
        self.assertEqual(before, self.canonical_bytes(project))

    def test_2_block_for_on_unclaimed_parent_refuses_with_zero_writes(self):
        project = self.make_project()
        parent = self.add(project, "unclaimed parent")
        child = self.add(project, "child ticket")

        before = self.canonical_bytes(project)
        result = ticket_move(
            project, "block-for", parent, AGENT, "block an unclaimed parent", blocked_on=child
        )

        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "ILLEGAL_TICKET_LIFECYCLE")
        self.assertEqual(before, self.canonical_bytes(project))

    def test_1_block_for_on_foreign_parent_refuses_with_zero_writes(self):
        project = self.make_project()
        parent = self.add(project, "foreign-claimed DOING parent")
        child = self.add(project, "child ticket")

        self.assertTrue(apply_claim(project, parent, "other-agent", explicit=True).ok)

        before = self.canonical_bytes(project)
        result = ticket_move(
            project,
            "block-for",
            parent,
            "caller-agent",
            "block a parent held by another seat",
            blocked_on=child,
        )

        self.assertFalse(result.ok, result.to_dict())
        # The pre-existing SELF-ownership gate already refuses a live foreign
        # claim with zero writes; the handoff guard never needs to see it.
        self.assertEqual(result.code, "TICKET_NOT_WORKABLE")
        self.assertEqual(before, self.canonical_bytes(project))

    def test_legitimate_active_parent_handoff_succeeds(self):
        project = self.make_project()
        parent = self.add(project, "active parent work")
        child = self.add(project, "workable child work")

        self.assertTrue(apply_claim(project, parent, AGENT, explicit=True).ok)
        self.assertTrue(transition_phase(project, "BUILD", AGENT, parent, "building").ok)

        result = ticket_move(
            project, "block-for", parent, AGENT, "parent waits on child", blocked_on=child
        )

        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "BLOCKED_FOR")
        parked = self.tickets(project)[parent]
        self.assertEqual(parked["section"], "## BLOCKED")
        self.assertEqual(parked["fields"]["blocked_on"], child)
        self.assertEqual(parked["fields"]["resume_phase"], "BUILD")

    def test_ordinary_legal_todo_block_succeeds(self):
        project = self.make_project()
        todo_item = self.add(project, "ordinary backlog item to block")

        result = ticket_move(project, "block", todo_item, AGENT, "ordinary blocker reason")

        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "BLOCK")
        self.assertEqual(self.tickets(project)[todo_item]["section"], "## BLOCKED")


if __name__ == "__main__":
    unittest.main()

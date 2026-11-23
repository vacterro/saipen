"""SRC-308 (T-1883): causal blocker ownership, never global inventory.

The incident: a project in an ACTIVE phase carried an agent-written
`STATE.blocker` describing an already-completed `REVIEW -> SHIP` transition.
`_state_blocker_repairs` refused to repair it because the BOARD happened to hold
four UNRELATED blocked tickets (T-1469, T-1480, T-1483, T-1505), so the operator
was asked to act as a manual state reconciler for a defect the engine can prove.

These tests hold the closed causal rule. They never assert on prose wording: an
unrelated blocked ticket must leave the verdict EXACTLY as it would be if the
ticket did not exist (AC-01..AC-04), and a related one must still refuse
(AC-05), and ambiguity must fail closed (AC-06). No existing security check is
weakened, replaced or deleted -- `test_a_related_live_board_block_refuses` in
test_recovery_reachability.py keeps the related coverage at its original site.

AC-07..AC-24 are end-to-end and live in the modules that own those surfaces
(goal checkpoints, release, auto-doctor); this module CROSS-REFERENCES them
rather than re-implementing a weaker copy here. See AC_COVERAGE below.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.reconcile import (  # noqa: E402
    _causally_related_blocks,
    _state_blocker_repairs,
    reconcile_protocol_state,
)
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    # An outer host session must never bind these disposable fixtures.
    isolate_host_session()


INCIDENT_BLOCKER = "operator_required (continuation_authority) for REVIEW -> SHIP"
UNRELATED = ("T-1469", "T-1480", "T-1483", "T-1505")
ACTIVE = "T-1517"

#: Which Work owns the end-to-end half of each handoff acceptance criterion.
AC_COVERAGE = {
    "AC-07": "test_t1729_gate_decision_lifecycle.py (committed transition discharges the gate)",
    "AC-08": "test_recovery_reachability.py (an uncommitted transition is never fabricated)",
    "AC-09": "test_t1704_goal_checkpoint_priority.py (no redundant reauthorization)",
    "AC-10": "test_reconcile_valve.py (exhausted budget keeps hard_wait)",
    "AC-11": "test_t1704_goal_checkpoint_priority.py (persistent checkpoint continues)",
    "AC-12": "test_t1750_release_boundary.py (first publication keeps its gate)",
    "AC-14": "test_t1729_operator_gate.py (a replayed carrier cannot discharge a gate)",
    "AC-17": "test_reconcile_history_ledger_blocked.py (CAS conflict, no stale repair)",
    "AC-18": "test_t1751_reconcile_surfaces.py (second reconcile is CLEAN, no writes)",
    "AC-19": "test_t1792_auto_doctor.py (a committed repair is recognised after restart)",
    "AC-21": "test_t1746_crew_terminal_outcome.py (no unauthorized publish)",
}


def _board(blocked=(), needs=None, doing_needs=None):
    """A parsed-board shape: `needs` per ticket, section decides membership."""
    needs = needs or {}
    doing_needs = doing_needs or {}
    tickets = {}
    for tid in blocked:
        tickets[tid] = {"id": tid, "section": "## BLOCKED",
                        "needs": list(needs.get(tid, [])), "fields": {}}
    for tid, ids in doing_needs.items():
        tickets[tid] = {"id": tid, "section": "## DOING",
                        "needs": list(ids), "fields": {}}
    return {"tickets": tickets}


def _state(blocker=INCIDENT_BLOCKER, task=ACTIVE, phase="SHIP"):
    return {"phase": phase, "task": task, "blocker": blocker}


class UnrelatedBlocksCannotVetoTests(unittest.TestCase):
    """AC-01..AC-04: the count and identity of unrelated blocks are irrelevant."""

    def _verdict(self, board):
        repairs = _state_blocker_repairs(_state(), board)
        self.assertEqual(len(repairs), 1, repairs)
        return repairs[0]

    def test_ac01_incident_shape_repairs_the_proven_stale_blocker(self):
        verdict = self._verdict(_board(UNRELATED))
        self.assertEqual(verdict["to"], "none")
        self.assertNotIn("refuse", verdict)
        self.assertEqual(verdict["classification"], "SAFE_CANONICAL_REPAIR")

    def test_ac02_no_blocked_tickets_gives_the_same_verdict(self):
        with_blocks = self._verdict(_board(UNRELATED))
        without = self._verdict(_board())
        for key in ("to", "classification", "field", "from"):
            self.assertEqual(with_blocks[key], without[key], (key, with_blocks, without))
        self.assertNotIn("refuse", without)

    def test_ac03_one_unrelated_block_changes_nothing(self):
        alone = self._verdict(_board(["T-1469"]))
        self.assertEqual(alone["to"], "none")
        self.assertNotIn("refuse", alone)

    def test_ac04_one_hundred_unrelated_blocks_change_nothing(self):
        many = tuple(f"T-{n:04d}" for n in range(1, 101))
        verdict = self._verdict(_board(many))
        self.assertEqual(verdict["to"], "none")
        self.assertNotIn("refuse", verdict)
        self.assertEqual(verdict["classification"], "SAFE_CANONICAL_REPAIR")


class RelatedGatesStillRefuseTests(unittest.TestCase):
    """AC-05: a blocked ticket that genuinely governs the active work is kept."""

    def test_ac05_active_work_depending_on_a_blocked_ticket_refuses(self):
        repairs = _state_blocker_repairs(
            _state(), _board(["T-1469"], doing_needs={ACTIVE: ["T-1469"]})
        )
        self.assertTrue(repairs[0]["refuse"], repairs)
        self.assertIsNone(repairs[0]["to"])
        self.assertEqual(repairs[0]["classification"], "RELATED_ACTIVE_GATE")
        self.assertIn("T-1469", repairs[0]["reason"])

    def test_ac05_a_blocked_ticket_that_needs_the_active_work_refuses(self):
        repairs = _state_blocker_repairs(
            _state(), _board(["T-1469"], needs={"T-1469": [ACTIVE]})
        )
        self.assertTrue(repairs[0]["refuse"], repairs)
        self.assertEqual(repairs[0]["classification"], "RELATED_ACTIVE_GATE")

    def test_ac05_a_blocker_naming_the_blocked_ticket_refuses(self):
        repairs = _state_blocker_repairs(
            _state(blocker="HELD pending T-1469 review"), _board(["T-1469"])
        )
        self.assertTrue(repairs[0]["refuse"], repairs)
        self.assertEqual(repairs[0]["classification"], "RELATED_ACTIVE_GATE")

    def test_a_recognised_class_token_still_refuses_with_unrelated_blocks(self):
        repairs = _state_blocker_repairs(
            _state(blocker="BLOCKED_EXTERNAL -- vendor cert"), _board(UNRELATED)
        )
        self.assertTrue(repairs[0]["refuse"], repairs)
        self.assertEqual(repairs[0]["classification"],
                         "GENUINE_OPERATOR_DECISION_REQUIRED")
        self.assertIn("OPERATOR_DECISION_REQUIRED", repairs[0]["reason"])


class AmbiguityFailsClosedTests(unittest.TestCase):
    """AC-06: ownership that cannot be established is never inferred away."""

    def test_ac06_a_ticketless_state_relates_to_nothing(self):
        """An empty `task` cannot own a board relation, so no ticket governs it.

        The point is that the EMPTY case does not restore presence-based
        vetoing: no id means no relation, which is the same closed answer the
        classifier gives any unrelated ticket.
        """
        related, unrelated = _causally_related_blocks(
            "", list(UNRELATED), _board(UNRELATED)["tickets"], INCIDENT_BLOCKER
        )
        self.assertEqual(related, [])
        self.assertEqual(unrelated, list(UNRELATED))

    def test_ac06_an_id_inside_a_longer_number_is_not_that_id(self):
        """`T-15` must not match `T-151`; token bounds, not substring."""
        related, unrelated = _causally_related_blocks(
            "T-1517", ["T-151"], _board(["T-151"])["tickets"], "see T-1517"
        )
        self.assertEqual(related, [])
        self.assertEqual(unrelated, ["T-151"])

    def test_ac06_a_blocked_set_with_no_relation_is_reported_not_trusted(self):
        related, unrelated = _causally_related_blocks(
            ACTIVE, list(UNRELATED), _board(UNRELATED)["tickets"], INCIDENT_BLOCKER
        )
        self.assertEqual(related, [])
        self.assertEqual(unrelated, list(UNRELATED))
        repairs = _state_blocker_repairs(_state(), _board(UNRELATED))
        self.assertIn("do not apply to this Work", repairs[0]["reason"])


class NoSecondFrameworkTests(unittest.TestCase):
    """The classification rides the EXISTING repair contract, not a parallel one."""

    def test_every_repair_keeps_the_fields_consumers_read(self):
        for board in (_board(), _board(UNRELATED), _board(["T-1469"])):
            repairs = _state_blocker_repairs(_state(), board)
            self.assertEqual(len(repairs), 1, repairs)
            for key in ("field", "from", "to", "surface", "reason"):
                self.assertIn(key, repairs[0], (key, repairs[0]))
            self.assertEqual(repairs[0]["field"], "blocker")
            self.assertEqual(repairs[0]["surface"], "state")

    def test_a_refusal_carries_the_operator_route_and_a_repair_does_not(self):
        refusal = _state_blocker_repairs(
            _state(blocker="HELD -- operator must decide"), _board()
        )[0]
        self.assertTrue(refusal["refuse"])
        self.assertIn("resolve-blocker", refusal["canonical_next_command"])
        repair = _state_blocker_repairs(_state(), _board())[0]
        self.assertNotIn("canonical_next_command", repair)
        self.assertNotIn("refuse", repair)


class AcCoverageIsNamedTests(unittest.TestCase):
    """A criterion delegated to another module must still name that module.

    This is a documentation gate with teeth: it fails if a mapping is emptied,
    so the end-to-end half cannot be quietly dropped in a later edit.
    """

    def test_every_delegated_criterion_names_a_real_module(self):
        self.assertGreaterEqual(len(AC_COVERAGE), 10, AC_COVERAGE)
        for criterion, owner in AC_COVERAGE.items():
            with self.subTest(criterion=criterion):
                self.assertRegex(criterion, r"^AC-\d{2}$")
                module = owner.split(" ", 1)[0]
                self.assertTrue((TOOLS / module).is_file(), module)


def _incident_project(blocked=(), active_needs=()) -> Path:
    """The FastPrompter shape on disk: SHIP phase, agent-written blocker.

    Every blocked ticket gets a real allocation event, because `recover`
    otherwise refuses for legacy adoption FIRST and the blocker classifier
    never reaches a verdict -- two refusals in one fixture cannot testify.
    """
    root = Path(tempfile.mkdtemp(prefix="t1883-e2e-"))
    (root / ".saipen").mkdir(parents=True)
    from saipen_engine.state import running_home

    (root / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: SHIP\n"
        f"task: {ACTIVE}\n"
        f'next_action: "PHASE SHIP {ACTIVE}"\n'
        f'blocker: "{INCIDENT_BLOCKER}"\n'
        "transition_from: REVIEW\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        f"last_event: {len(blocked) + 4}\n"
        "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
        "mode: full\n"
        "updated: 2026-10-24T00:00:00Z\n"
        "agent: tester\n"
        f"saipen_home: {running_home().as_posix()}\n"
        "---\n",
        encoding="utf-8",
    )
    need_field = f" | needs: {', '.join(active_needs)}" if active_needs else ""
    rows = "".join(
        f"- [ ] {tid} [P2] parked external work | verify: external ack"
        " | blocker: vendor ack pending | blocker_scope: ticket\n"
        for tid in blocked
    )
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n"
        f"- [/] {ACTIVE} [P1] ship the release | verify: acceptance suite"
        f"{need_field}"
        " | owner: tester | claim_time: 2026-10-24T00:00:00Z\n"
        "## TODO\n## DONE\n## BLOCKED\n" + rows,
        encoding="utf-8",
    )
    events = [
        f"- 24.10.26 00:00 [E-004] [{ACTIVE}] [agent: tester] "
        f"[op: ticket-{1517:032d}] DEC: ticket added via SAIOPS\n"
    ]
    for offset, tid in enumerate(blocked, start=1):
        events.append(
            f"- 24.10.26 00:00 [E-{4 + offset:03d}] [{tid}] [agent: tester] "
            f"[op: ticket-{int(tid.split('-')[1]):032d}] DEC: ticket added via SAIOPS\n"
        )
    (root / ".saipen" / "LOG.md").write_text("# Log\n" + "".join(events),
                                            encoding="utf-8")
    return root


class EndToEndVerdictTests(unittest.TestCase):
    """AC-01/AC-02 through the ONE verdict owner, not the private helper."""

    def _reconcile(self, blocked=(), active_needs=()):
        root = _incident_project(blocked, active_needs)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        before = {n: (root / ".saipen" / n).read_bytes()
                  for n in ("STATE.md", "BOARD.md", "LOG.md")}
        result = reconcile_protocol_state(root, "tester", dry_run=False)
        after = {n: (root / ".saipen" / n).read_bytes() for n in before}
        record = next(
            (row for row in (result.get("changed") or {}).get("state") or []
             if isinstance(row, dict) and row.get("field") == "blocker"),
            None,
        )
        return result, record, {n: before[n] != after[n] for n in before}

    def test_ac01_the_incident_project_repairs_through_the_real_pipeline(self):
        result, record, _ = self._reconcile(UNRELATED)
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result.get("code"), "REPAIRED", result)
        self.assertIsNotNone(record, result)
        self.assertEqual(record["to"], "none")
        self.assertEqual(record["classification"], "SAFE_CANONICAL_REPAIR")
        self.assertIn("do not apply to this Work", record["reason"])
        # The four unrelated tickets are neither unblocked nor rewritten.
        self.assertEqual((result.get("changed") or {}).get("board"), [], result)

    def test_ac02_the_same_project_without_blocks_gives_the_same_repair(self):
        with_blocks, record_a, _ = self._reconcile(UNRELATED)
        without, record_b, _ = self._reconcile()
        self.assertEqual((record_a["to"], record_a["classification"]),
                         (record_b["to"], record_b["classification"]))
        self.assertEqual(with_blocks.get("code"), without.get("code"))

    def test_ac05_a_related_block_still_refuses_and_writes_nothing(self):
        result, record, wrote = self._reconcile(("T-1469",), ("T-1469",))
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "RECONCILE_REAUTH_REQUIRED", result)
        self.assertEqual(record["classification"], "RELATED_ACTIVE_GATE")
        self.assertTrue(record["refuse"])
        self.assertFalse(any(wrote.values()), wrote)



if __name__ == "__main__":
    unittest.main()

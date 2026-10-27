"""Project readiness is independent of the execution phase (T-1862 / SRC-294).

The reported defect: a project reports `phase: DONE`, `task: none` and reads as
complete while a durable audit layer, 162 UNKNOWN source clauses and blocked
tickets are still outstanding. `DONE` was never wrong -- it is the lifecycle
verdict of the last execution ticket. What was missing is a computed answer that
survives that phase transition.

This suite is the SRC-294 regression matrix A-L. Each case is a synthetic input
mapping; the derivation is pure, so no project directory is needed except where
the case is specifically about the read-only projection.

A. no tickets, no audits, all coverage terminal     -> PROJECT_ACCEPTED
B. last ticket DONE, active audit present           -> AUDIT_OUTSTANDING
C. last ticket DONE, UNKNOWN clauses                -> SOURCE_RECONCILIATION_REQUIRED
D. last ticket DONE, external blocker only          -> EXTERNALLY_BLOCKED
E. operator-paused security ticket                  -> VISIBLE_BUT_NOT_RUNNABLE
F. audit layer consumed, valid archived receipt     -> no false reopening
G. audit source missing, contract intact            -> integrity blocker retained
H. duplicate source references                      -> counted once
I. invalid source records                           -> no fake completed coverage
J. fresh operator authorization absent              -> status reporting cannot reset authority
K. cross-project status                             -> no STATE modification
L. historical source claims without verification    -> readiness stays qualified
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import readiness  # noqa: E402


def state(phase="DONE", task=None, **extra):
    base = {
        "phase": phase,
        "task": task,
        "next_action": "PHASE DONE",
        "continuation_authority": "operator_required",
        "authority_source": "E-1",
        "authority_until": "budget",
        "safety_valve_mode": "hard_wait",
        "execution_intent": "goal",
    }
    base.update(extra)
    return base


def ticket(tid, section, blocker="", needs=()):
    fields = {"blocker": blocker} if blocker else {}
    return {"id": tid, "section": section, "checkbox": " ", "needs": list(needs),
            "fields": fields, "priority": "P2"}


def inbox(pending=0, invalid=0, residue=0):
    return {
        "ok": True,
        "pending": [{"layer": i, "state": "ACTIVE"} for i in range(pending)],
        "invalid": [{"layer": 100 + i} for i in range(invalid)],
        "closed_pending_delete": [],
        "residue_count": residue,
        "clean": not pending and not invalid and not residue,
        "error_state": None,
        "inbox_state": None,
    }


def receipts(*pairs):
    """(requirements, unresolved) pairs -> the shape intake supplies."""
    return [
        {"receipt": f"SRC-{index + 1:03d}", "requirements": total, "unresolved": open_}
        for index, (total, open_) in enumerate(pairs)
    ]


class MatrixA(unittest.TestCase):
    """A. No tickets, no audits, all coverage terminal: project may be READY."""

    def test_accepted(self):
        result = readiness.derive(
            state=state(),
            tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None,
            inbox=inbox(),
            receipts=receipts((3, 0), (5, 0)),
            tombstones={"SRC-900": {"unresolved": 0}},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.PROJECT_ACCEPTED)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["ready"])
        self.assertFalse(result["grants_authority"])

    def test_not_accepted_while_phase_mid_flight(self):
        """Everything terminal but the phase is not terminal -> IDLE, not ACCEPTED."""
        result = readiness.derive(
            state=state(phase="BUILD", task=None),
            tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None,
            inbox=inbox(),
            receipts=receipts((1, 0)),
            tombstones={},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.EXECUTION_IDLE)
        self.assertFalse(result["accepted"])


class MatrixB(unittest.TestCase):
    """B. Last ticket DONE, active audit present: execution DONE, project NOT_READY."""

    def test_execution_done_but_audit_outstanding(self):
        result = readiness.derive(
            state=state(),
            tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None,
            inbox=inbox(pending=1),
            receipts=receipts((2, 0)),
            tombstones={},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["execution"]["phase"], "DONE")
        self.assertTrue(result["execution"]["terminal_phase"])
        self.assertEqual(result["status"], readiness.AUDIT_OUTSTANDING)
        self.assertFalse(result["ready"])


class MatrixC(unittest.TestCase):
    """C. Last ticket DONE, 162 UNKNOWN clauses: source reconciliation required."""

    def test_unknown_clauses_keep_readiness_qualified(self):
        result = readiness.derive(
            state=state(),
            tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None,
            inbox=inbox(),
            receipts=receipts((230, 162)),
            tombstones={},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.SOURCE_RECONCILIATION_REQUIRED)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["dimensions"]["source"]["outstanding"], 162)
        self.assertEqual(result["dimensions"]["source"]["terminal"], 68)


class MatrixD(unittest.TestCase):
    """D. Last ticket DONE, external blocker only: externally blocked acceptance."""

    def test_external_blocker_distinguished(self):
        result = readiness.derive(
            state=state(),
            tickets={
                "T-001": ticket("T-001", "## DONE"),
                "T-301": ticket("T-301", "## BLOCKED",
                                "BLOCKED_EXTERNAL -- vendor session required"),
            },
            top_workable=None,
            inbox=inbox(),
            receipts=receipts((1, 0)),
            tombstones={},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.EXTERNALLY_BLOCKED)
        self.assertEqual(result["dimensions"]["work"]["blocked_external"], 1)

    def test_work_blocked_is_not_external(self):
        result = readiness.derive(
            state=state(),
            tickets={"T-301": ticket("T-301", "## BLOCKED", "needs an operator decision")},
            top_workable=None,
            inbox=inbox(),
            receipts=[],
            tombstones={},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.WORK_BLOCKED)
        self.assertEqual(result["dimensions"]["work"]["blocked_external"], 0)


class MatrixE(unittest.TestCase):
    """E. Operator-paused security ticket: visible but never auto-admitted."""

    def test_paused_ticket_visible_but_not_runnable(self):
        result = readiness.derive(
            state=state(phase="BUILD", task="T-005"),
            tickets={
                "T-005": ticket("T-005", "## DOING"),
                "T-006": ticket("T-006", "## BLOCKED",
                                "WAIT_USER_DECISION -- security posture change"),
            },
            top_workable=None,
            inbox=inbox(),
            receipts=[],
            tombstones={},
            orphans={"ok": True, "orphans": []},
        )
        # Visible: counted, and the pause is named.
        self.assertEqual(result["dimensions"]["work"]["blocked"], 1)
        # NOT conflated with "blocked work is all there is": one DOING ticket
        # is being executed, so the project is working, not stopped.
        self.assertEqual(result["status"], readiness.WORK_AVAILABLE)
        self.assertEqual(result["dimensions"]["work"]["claimed"], 1)
        # Never admitted: readiness grants no authority and names no work.
        self.assertFalse(result["grants_authority"])
        self.assertIsNone(result["dimensions"]["work"]["top_workable"])
        self.assertEqual(result["dimensions"]["authority"]["continuation_authority"],
                         "operator_required")


class MatrixF(unittest.TestCase):
    """F. Audit layer consumed, valid archived receipt: no false reopening."""

    def test_consumed_audit_does_not_reopen(self):
        result = readiness.derive(
            state=state(),
            tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None,
            inbox=inbox(),
            receipts=receipts((4, 0)),
            # The closed receipt now lives in the archive half of the index.
            tombstones={"SRC-900": {"unresolved": 0, "status": "CLOSED"}},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.PROJECT_ACCEPTED)
        self.assertEqual(result["dimensions"]["source"]["outstanding"], 0)
        # Reported as archived history, never as a second active obligation.
        self.assertEqual(result["dimensions"]["source"]["archived"]["receipts"], 1)


class MatrixG(unittest.TestCase):
    """G. Audit source missing, contract intact: integrity blocker retained."""

    def test_orphan_receipt_blocks_acceptance(self):
        result = readiness.derive(
            state=state(),
            tickets={},
            top_workable=None,
            inbox=inbox(),
            receipts=receipts((1, 0)),
            tombstones={},
            orphans={"ok": True,
                     "orphans": [{"receipt": "SRC-777", "state": "ARCHIVE_COMMIT_PENDING"}]},
        )
        self.assertEqual(result["status"], readiness.INTEGRITY_BLOCKED)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["dimensions"]["integrity"]["orphans"], 1)


class MatrixH(unittest.TestCase):
    """H. Duplicate source references: counted once."""

    def test_archive_and_active_are_not_summed(self):
        one_receipt = receipts((10, 4))
        result = readiness.derive(
            state=state(),
            tickets={},
            top_workable=None,
            inbox=inbox(),
            receipts=one_receipt,
            # The same receipt's archived record must not add obligations.
            tombstones={"SRC-001": {"unresolved": 4, "status": "CLOSED"}},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["dimensions"]["source"]["requirements"], 10)
        self.assertEqual(result["dimensions"]["source"]["outstanding"], 4)
        # Archived unresolved is reported, but it is NOT live coverage.
        self.assertEqual(
            result["dimensions"]["source"]["archived"]["unresolved_at_closure"], 4
        )


class MatrixI(unittest.TestCase):
    """I. Invalid source records: no fake completed coverage."""

    def test_malformed_ledger_is_not_zero_outstanding(self):
        """The CLI turns a malformed ledger into INTEGRITY, never acceptance."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".saipen/intake/active").mkdir(parents=True)
            (root / ".saipen/intake/coverage").mkdir(parents=True)
            (root / ".saipen/intake/coverage/SRC-001.json").write_text(
                '{"requirements": "not-an-object"}', encoding="utf-8"
            )
            (root / ".saipen/intake/active/SRC-001.md").write_text("body", encoding="utf-8")
            from saipen_engine import intake

            with self.assertRaises(ValueError):
                intake.coverage_summary(root, "SRC-001")


class MatrixJ(unittest.TestCase):
    """J. Fresh operator authorization absent: reporting cannot reset authority."""

    def test_authority_quoted_never_escalated(self):
        result = readiness.derive(
            state=state(next_action="WAIT: safety valve reached (0 waves / 23 tickets)"),
            tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None,
            inbox=inbox(pending=1),
            receipts=receipts((5, 5)),
            tombstones={},
            orphans={"ok": True, "orphans": [{"receipt": "SRC-9"}]},
        )
        authority = result["dimensions"]["authority"]
        self.assertEqual(authority["continuation_authority"], "operator_required")
        self.assertEqual(authority["safety_valve_mode"], "hard_wait")
        self.assertEqual(authority["authority_source"], "E-1")
        self.assertTrue(authority["waiting"])
        # Readiness never grants, whatever it computed.
        self.assertFalse(result["grants_authority"])
        self.assertTrue(result["authority_unchanged"])

    def test_ready_does_not_imply_permission(self):
        accepted = readiness.derive(
            state=state(), tickets={}, top_workable=None, inbox=inbox(),
            receipts=[], tombstones={}, orphans={"ok": True, "orphans": []},
        )
        self.assertTrue(accepted["accepted"])
        self.assertFalse(accepted["grants_authority"])
        self.assertEqual(
            accepted["dimensions"]["authority"]["continuation_authority"], "operator_required"
        )


class MatrixK(unittest.TestCase):
    """K. Cross-project status: no accidental modification of project STATE."""

    def test_status_is_read_only(self):
        """`status` reports readiness and writes nothing into project memory.

        Uses the canonical project fixture so the STATE is valid by the same
        rules production enforces; a hand-built STATE would measure the
        validator instead of the read-only property.
        """
        from test_t1363_zero_manual_entry import project

        root = project(
            self,
            execution_intent="goal",
            goal_waves=0,
            goal_tickets=0,
        )
        memory = root / ".saipen"
        before = {
            name: (memory / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        env = dict(os.environ)
        env["SAIPEN_HOME"] = str(TOOLS.parent)
        proc = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "status", "--json"],
            cwd=str(root), capture_output=True, text=True, env=env, timeout=180,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertIn("readiness", payload)
        self.assertIn("status", payload["readiness"])
        after = {
            name: (memory / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        self.assertEqual(before, after, "status must not write project memory")

    def test_human_and_machine_status_agree(self):
        """The plain-text answer names the same readiness the JSON carries.

        SRC-294's core symptom was a human reading `phase: DONE` as completion.
        A machine-only projection would leave that reading intact, so the
        rendered line is part of the contract: it must name the derived status,
        and it must name the quoted authority so no one reads it as a grant.
        """
        from test_t1363_zero_manual_entry import project

        root = project(
            self,
            execution_intent="goal",
            goal_waves=0,
            goal_tickets=0,
            continuation_authority="operator_required",
            authority_source="E-1",
            authority_until="budget",
            safety_valve_mode="hard_wait",
        )
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
            "- [ ] T-5000 [P1] vendor reply | verify: test | "
            "blocker: BLOCKED_EXTERNAL -- vendor reply\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["SAIPEN_HOME"] = str(TOOLS.parent)
        machine = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "status", "--json"],
            cwd=str(root), capture_output=True, text=True, env=env, timeout=180,
        )
        self.assertEqual(machine.returncode, 0, machine.stderr or machine.stdout)
        derived = json.loads(machine.stdout)["readiness"]["status"]
        human = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "status"],
            cwd=str(root), capture_output=True, text=True, env=env, timeout=180,
        )
        self.assertEqual(human.returncode, 0, human.stderr or human.stdout)
        self.assertIn(f"Readiness: {derived}", human.stdout)
        self.assertIn("authority unchanged:", human.stdout)
        # The phase is still published, and still means what it meant.
        self.assertIn("phase: DONE", human.stdout)


class MatrixL(unittest.TestCase):
    """L. Historical source claims without verification stay qualified."""

    def test_receipt_without_evidence_stays_outstanding(self):
        """A terminal-looking disposition with no evidence is not terminal.

        The intake interpreter already owns this rule; readiness must consume
        its answer rather than re-deciding it. A receipt reporting unresolved
        obligations therefore keeps readiness qualified even when every
        requirement's disposition string reads VERIFIED.
        """
        result = readiness.derive(
            state=state(),
            tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None,
            inbox=inbox(),
            receipts=[{"receipt": "SRC-050", "requirements": 7, "unresolved": 3}],
            tombstones={},
            orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.SOURCE_RECONCILIATION_REQUIRED)
        self.assertEqual(result["dimensions"]["source"]["outstanding"], 3)


class UnreadableInputs(unittest.TestCase):
    """Absent or failed inputs may never be read as completion."""

    def test_unknown_inbox_is_not_clean(self):
        dim = readiness._audit_dimension(None)
        self.assertFalse(dim["known"])
        result = readiness.derive(
            state=state(), tickets={}, top_workable=None, inbox=None,
            receipts=receipts((1, 0)), tombstones={}, orphans=None,
        )
        # A failed inbox read cannot prove every audit layer was consumed.
        self.assertFalse(result["dimensions"]["audit"]["known"])
        self.assertFalse(result["dimensions"]["integrity"]["known"])
        self.assertEqual(result["status"], readiness.INTEGRITY_BLOCKED)
        self.assertFalse(result["accepted"])

    def test_unknown_orphans_block_acceptance(self):
        result = readiness.derive(
            state=state(), tickets={}, top_workable=None, inbox=inbox(),
            receipts=[], tombstones={}, orphans=None,
        )
        self.assertEqual(result["status"], readiness.INTEGRITY_BLOCKED)
        self.assertFalse(result["accepted"])

    def test_failed_audit_classification_blocks_acceptance(self):
        failed = {"ok": False, "code": "AUDIT_INBOX_UNREADABLE", "clean": False}
        result = readiness.derive(
            state=state(), tickets={}, top_workable=None, inbox=failed,
            receipts=[], tombstones={}, orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.AUDIT_OUTSTANDING)
        self.assertFalse(result["accepted"])

    def test_missing_audit_classification_blocks_acceptance(self):
        result = readiness.derive(
            state=state(), tickets={}, top_workable=None, inbox=None,
            receipts=[], tombstones={}, orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.AUDIT_OUTSTANDING)
        self.assertFalse(result["accepted"])

    def test_failed_orphan_diagnostic_blocks_acceptance(self):
        failed = {"ok": False, "orphans": []}
        result = readiness.derive(
            state=state(), tickets={}, top_workable=None, inbox=inbox(),
            receipts=[], tombstones={}, orphans=failed,
        )
        self.assertEqual(result["status"], readiness.INTEGRITY_BLOCKED)
        self.assertFalse(result["accepted"])

    def test_audit_residue_blocks_acceptance(self):
        result = readiness.derive(
            state=state(), tickets={}, top_workable=None, inbox=inbox(residue=1),
            receipts=[], tombstones={}, orphans={"ok": True, "orphans": []},
        )
        self.assertEqual(result["status"], readiness.AUDIT_OUTSTANDING)
        self.assertFalse(result["accepted"])

    def test_unreadable_coverage_is_not_empty_coverage(self):
        """`None` receipts means the index failed, and that is not zero debt.

        Found in REVIEW of this ticket: `_status` caught an unreadable index
        and passed `receipts=[]`, which this dimension read as "no outstanding
        clause" -- so a project with corrupt source records could report
        PROJECT_ACCEPTED. The empty list is the only input that means "read
        it, and there is nothing"; `None` must refuse acceptance.
        """
        result = readiness.derive(
            state=state(), tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None, inbox=inbox(),
            receipts=None, tombstones={}, orphans={"ok": True, "orphans": []},
        )
        self.assertFalse(result["dimensions"]["source"]["receipts_known"])
        self.assertEqual(result["status"], readiness.INTEGRITY_BLOCKED)
        self.assertFalse(result["accepted"])
        self.assertFalse(result["ready"])

    def test_empty_coverage_still_allows_acceptance(self):
        """The other half of the same pair: a READ empty index is complete."""
        result = readiness.derive(
            state=state(), tickets={"T-001": ticket("T-001", "## DONE")},
            top_workable=None, inbox=inbox(),
            receipts=[], tombstones={}, orphans={"ok": True, "orphans": []},
        )
        self.assertTrue(result["dimensions"]["source"]["receipts_known"])
        self.assertEqual(result["status"], readiness.PROJECT_ACCEPTED)


class Vocabulary(unittest.TestCase):
    def test_statuses_unique_and_headlined(self):
        self.assertEqual(len(set(readiness.STATUSES)), len(readiness.STATUSES))
        for name in readiness.STATUSES:
            self.assertIn(name, readiness.HEADLINES)

    def test_matrix_letters_are_documented(self):
        doc = (TOOLS / "saipen_engine/readiness.py").read_text(encoding="utf-8")
        for phrase in ("execution phase", "never escalates authority", "never writes"):
            self.assertIn(phrase, doc)


if __name__ == "__main__":
    unittest.main()

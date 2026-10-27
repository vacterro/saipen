"""T-1614 FUTURE GATE regressions: one deferred-authority lifecycle (matrix A-X).

A gate is a DEFERRED AUTHORITY CANDIDATE: recorded, deferred, evaluated,
promoted as ONE bounded slice, closed. It is never active Work, never a rule
source and never implementation authority before promotion. Each test below is
one row of the acceptance matrix in the SAIHANDOFF.

The normative owner is `saipen/FUTURE.md` (Rule FUTURE-GATE-01); every
assertion here is a mechanical consequence of it.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine import future_gate as gates  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.state import parse_state_or_error  # noqa: E402
from saipen_engine.journal import ensure_project_lineage  # noqa: E402
from saipen_engine.operations import ticket_add, ticket_move  # noqa: E402
from saipen_engine.router import (  # noqa: E402
    audit_inbox_projection,
    future_gate_projection,
    route_next,
)

#: The normative owner. Read here so the coverage contract can prove a check
#: actually consumes the document the rules are published in.
FUTURE_OWNER = ROOT / "saipen" / "FUTURE.md"

BOARD_PREAMBLE = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"


def _project(phase="DONE", task="none", intent="normal", waves=0, tickets=0):
    base = Path(tempfile.mkdtemp(prefix="saipen-t1614-"))
    project = base / "project"
    (project / ".saipen").mkdir(parents=True)
    text = (
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        'next_action: "saipen continue"\n'
        'blocker: ""\n'
        "transition_from: DONE\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 1\n"
        "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
        f'saipen_home: "{str(ROOT).replace(chr(92), chr(92) * 2)}"\n'
        "agent: tester\n"
        "requires:\n  - filesystem\n  - python\n"
        "mode: full\n"
        f"execution_intent: {intent}\n"
        + (f"goal_waves: {waves}\ngoal_tickets: {tickets}\n" if intent == "goal" else "")
        + 'updated: "2026-10-05T00:00:00Z"\n'
        "---\n"
    )
    (project / ".saipen" / "STATE.md").write_text(text, encoding="utf-8")
    (project / ".saipen" / "BOARD.md").write_text(BOARD_PREAMBLE, encoding="utf-8")
    (project / ".saipen" / "LOG.md").write_text(
        "- 01.09.26 00:00 [E-001] [agent: tester] RUN: fixture -> PASS\n", encoding="utf-8"
    )
    # A repository path for a gate to point `evidence:` at: readiness requires a
    # ref that EXISTS, so the fixture seeds one instead of leaning on SAIPEN's
    # own tree.
    (project / "evidence.md").write_text(
        "# Evidence\n\nThe defect this gate defers.\n", encoding="utf-8"
    )
    ensure_project_lineage(project)
    return base, project


def _gate_doc(
    gate_id: str,
    title: str = "A deferred capability",
    *,
    state: str = "DEFERRED",
    priority: str = "P2",
    basis: str = "measured",
    estimate: str = "1",
    needs: str = "none",
    evidence: str = "evidence.md",
    body: str = "Design context for the candidate.",
) -> str:
    return (
        f"{gates.DOC_MARKER}\n"
        f"id: {gate_id}\n"
        f"title: {title}\n"
        f"state: {state}\n"
        f"priority: {priority}\n"
        f"basis: {basis}\n"
        f"estimate: {estimate}\n"
        "slice: implement the ONE bounded unit named in this gate\n"
        f"needs: {needs}\n"
        f"evidence: {evidence}\n"
        f"\n# {title}\n\n{body}\n"
    )


def _write_gate(project: Path, name: str, text: str) -> Path:
    directory = project / "future_gate"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def _tickets(project: Path) -> dict:
    return parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))["tickets"]


def _add(project: Path, text: str, *, priority: str = "P1", needs=None) -> str:
    """Add one BOARD ticket and return its id."""
    return ticket_add(project, "tester", priority, text, needs or [], "verify it").get("ticket")


def _doing(project: Path, ticket_id: str, text: str) -> None:
    """Seed the ONE live claim by hand: `ticket_move` has no claim action."""
    board = f"## DOING\n- [/] {ticket_id} [P1] {text} | verify: verify it\n"
    board += "## TODO\n## DONE\n## BLOCKED\n"
    (project / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")


def _done(project: Path, ticket_id: str, text: str = "shipped work") -> None:
    """Seed one closed ticket: readiness only reads BOARD's DONE section."""
    board = f"## DOING\n## TODO\n## DONE\n- [x] {ticket_id} [P1] {text} | verify: proof\n"
    board += "## BLOCKED\n"
    (project / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")


def _hold(project: Path, key: str, value: str) -> None:
    """Append one STATE frontmatter field without disturbing the fixture."""
    path = project / ".saipen" / "STATE.md"
    text = path.read_text(encoding="utf-8").replace(
        'next_action: "saipen continue"',
        f'next_action: "saipen continue"\n{key}: {value}',
    )
    path.write_text(text, encoding="utf-8")


def _route(project: Path, **kwargs) -> dict:
    state = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
    board = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
    return route_next(
        state,
        board,
        current_agent="tester",
        future_gate=future_gate_projection(project, board),
        **kwargs,
    )


class FutureGateMatrixTests(unittest.TestCase):
    def setUp(self):
        self._tmp = []

    def tearDown(self):
        for base in self._tmp:
            shutil.rmtree(base, ignore_errors=True)

    def _proj(self, **kwargs):
        base, project = _project(**kwargs)
        self._tmp.append(base)
        return project

    # ------------------------------------------------------------ A: intake

    def test_A_operator_statement_records_a_gate_not_a_ticket(self):
        """A: an explicit operator statement records a deferred candidate."""
        project = self._proj()
        path = gates.add(project, "Deferred retention policy", "Why this is deferred.")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(gates.DOC_MARKER))
        self.assertIn("state: DEFERRED", text)
        # Recording a gate creates NO ticket: the seat is untouched.
        self.assertEqual(list(_tickets(project)), [])

    def test_B_an_explicit_refresh_reconciles_a_new_document(self):
        """B: an explicit refresh rebuilds the projection over a new file.

        The name says what the body proves. Zero-manual discovery WITHOUT any
        refresh call is AUTO-01/AUTO-02 below, through the public route.
        """
        project = self._proj()
        _write_gate(project, "one.md", _gate_doc("FG-0001", "First gate"))
        first, _ = gates.refresh(project)
        self.assertEqual(first["corpus"]["documents"], 1)
        self.assertEqual(gates.freshness(project)["state"], gates.CURRENT)
        _write_gate(project, "two.md", _gate_doc("FG-0002", "Second gate"))
        # The corpus moved: the projection is stale BEFORE anyone refreshes.
        self.assertEqual(gates.freshness(project)["state"], gates.STALE)
        second, _ = gates.refresh(project)
        self.assertEqual(second["corpus"]["documents"], 2)
        self.assertEqual([g["id"] for g in second["gates"]], ["FG-0001", "FG-0002"])
        # FG-0001 kept its identity and lifecycle across the incremental pass.
        self.assertEqual(second["gates"][0]["title"], "First gate")

    def test_C_identity_survives_a_rename(self):
        """C: identity is the record, never the filename."""
        project = self._proj()
        original = _write_gate(project, "old-name.md", _gate_doc("FG-0007", "Stable title"))
        gates.refresh(project)
        renamed = project / "future_gate" / "new-name.md"
        original.rename(renamed)
        index, _ = gates.refresh(project)
        record = next(g for g in index["gates"] if g["id"] == "FG-0007")
        self.assertEqual(record["path"], "future_gate/new-name.md")
        self.assertEqual(record["identity_source"], "document-header")
        self.assertEqual(index["corpus"]["absent"], 0)

    def test_C2_an_undeclared_gate_is_reconciled_by_digest(self):
        """C: with no declared id, CONTENT carries identity across a rename."""
        project = self._proj()
        header = _gate_doc("FG-0000", "Content addressed")
        header = header.replace("id: FG-0000\n", "")
        original = _write_gate(project, "old-name.md", header)
        gates.refresh(project)
        original.rename(project / "future_gate" / "new-name.md")
        index, _ = gates.refresh(project)
        record = index["gates"][0]
        self.assertEqual(record["path"], "future_gate/new-name.md")
        self.assertEqual(record["identity_source"], "digest")
        self.assertEqual(record["title"], "Content addressed")

    # ------------------------------------------------------------ D: routing

    def test_D_an_eligible_gate_beats_idle_maintenance(self):
        """D: the idle fixture wins over the HUNT -> ADD fallthrough."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001", "Ready gate"))
        gates.refresh(project)
        routed = _route(project)
        self.assertEqual(routed["reason"], "future-gate-promotion")
        self.assertEqual(routed["action"], "saipen future promote FG-0001")
        self.assertEqual(routed["action_kind"], "FUTURE_GATE_PROMOTION")
        # Not the halt verdict it replaced.
        self.assertNotEqual(routed["reason"], "maintain")

    def test_D2_the_continue_chain_classifies_the_promotion(self):
        """D: the idle promotion is a typed kind, never prose to remember."""
        from saipen_engine import continue_loop

        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        routed = _route(project)
        state = parse_state_or_error(
            (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        )[0]
        board = parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        self.assertEqual(
            continue_loop.classify_route(routed, state, board),
            continue_loop.PROMOTE_FUTURE_GATE,
        )

    def test_D3_the_public_payload_names_the_gate_mechanically(self):
        """D: `saipen continue --json` carries the kind and the gate id."""
        from saipen import _route_payload
        from saipen_engine import continue_loop

        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        routed = _route(project)
        state_text = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        state, _err = parse_state_or_error(state_text)
        board = parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        kind = continue_loop.classify_route(routed, state, board)
        route = {
            "routed": routed,
            "state": state,
            "state_text": state_text,
            "subject": "",
            "pending": [],
            "parked": None,
        }
        payload = _route_payload(project, route, reconciliation=None, dry_run=True, kind=kind)
        self.assertEqual(payload["action_kind"], "FUTURE_GATE_PROMOTION")
        self.assertEqual(payload["future_gate"], "FG-0001")
        self.assertEqual(
            [step["action"] for step in payload["projected_steps"]],
            ["saipen future promote FG-0001", "PHASE SCOUT <T-###>"],
        )

    def test_E_a_gate_never_preempts_active_work(self):
        """E: one DOING ticket outranks every gate."""
        project = self._proj(phase="SCOUT", task="T-1")
        _doing(project, "T-1", "live work")
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        routed = _route(project)
        self.assertEqual(routed.get("reason"), "adopt")
        self.assertEqual(routed.get("action"), "saipen claim T-1")
        self.assertNotEqual(routed.get("reason"), "future-gate-promotion")

    def test_F_a_gate_never_outranks_workable_todo(self):
        """F: the BOARD Pick Rule outranks an eligible gate."""
        project = self._proj()
        tid = _add(project, "workable todo")
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        routed = _route(project)
        self.assertEqual(routed.get("ticket"), tid)
        self.assertNotEqual(routed.get("reason"), "future-gate-promotion")

    def test_G_no_eligible_gate_reproduces_todays_verdict(self):
        """G: with no eligible gate the MAINTAIN halt verdict is unchanged."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001", state="NEEDS_REVIEW"))
        gates.refresh(project)
        # One bounded refinement of the ambiguous record, THEN today's verdict.
        routed = _route(project)
        self.assertEqual(routed["reason"], "future-gate-refinement")
        gates.refine(project, "FG-0001", board_tickets=_tickets(project))
        routed = _route(project)
        self.assertEqual(routed["action"], "saipen continue")
        self.assertEqual(routed["reason"], "maintain")

    def test_H_a_live_operator_gate_outranks_a_future_gate(self):
        """H: STATE.improve_gate holds the idle fallthrough, gates included."""
        project = self._proj()
        tid = _add(project, "operator gate")
        self.assertEqual(
            ticket_move(
                project, "block", tid, "tester", payload="an operator must decide"
            ).get("code"),
            "BLOCK",
        )
        _hold(project, "improve_gate", tid)
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        routed = _route(project)
        self.assertEqual(routed["reason"], "improve-gate")
        self.assertNotEqual(routed.get("reason"), "future-gate-promotion")

    def test_I_the_goal_valve_defers_instead_of_bypassing(self):
        """I: goal mode never spends past the safety valve."""
        project = self._proj(intent="goal", waves=3)
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        routed = _route(project)
        self.assertEqual(routed["action"], "saipen continue")
        self.assertEqual(routed["reason"], "maintain")

    def test_J_goal_mode_below_the_cap_still_promotes(self):
        """J: a closed valve is the only thing that defers a gate."""
        project = self._proj(intent="goal", waves=1, tickets=2)
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        routed = _route(project)
        self.assertEqual(routed["reason"], "future-gate-promotion")

    # ------------------------------------------------------------ K: readiness

    def test_K_an_unmet_prerequisite_is_not_eligible(self):
        """K: readiness is mechanical, and it names the failing condition."""
        project = self._proj()
        tid = _add(project, "prerequisite")
        _write_gate(project, "gate.md", _gate_doc("FG-0001", needs=tid))
        gates.refresh(project)
        report = gates.evaluate(project, _tickets(project))
        evaluated = {e["id"]: e for e in report["evaluated"]}
        self.assertEqual(evaluated["FG-0001"]["verdict"], gates.INELIGIBLE)
        self.assertTrue(any(tid in reason for reason in evaluated["FG-0001"]["reasons"]))
        self.assertIsNone(report["next"])

    def test_L_a_done_prerequisite_unblocks_the_gate(self):
        """L: prerequisite-unblocked gate becomes the deterministic next."""
        project = self._proj()
        tid = _add(project, "prerequisite")
        _done(project, tid)
        _write_gate(project, "gate.md", _gate_doc("FG-0001", needs=tid))
        gates.refresh(project)
        self.assertEqual(gates.evaluate(project, _tickets(project))["next"], "FG-0001")

    def test_M_missing_evidence_is_ineligible(self):
        """M: a gate that points at a path that does not exist never routes."""
        project = self._proj()
        _write_gate(
            project,
            "gate.md",
            _gate_doc("FG-0001", evidence="future_gate/no-such-document.md"),
        )
        gates.refresh(project)
        report = gates.evaluate(project, _tickets(project))
        self.assertIsNone(report["next"])
        self.assertTrue(
            any("does not exist" in r for r in report["evaluated"][0]["reasons"]),
            report["evaluated"],
        )

    def test_N_a_historical_document_is_never_ready_by_guess(self):
        """N: the corpus's unmarked documents classify as NEEDS_REVIEW."""
        project = self._proj()
        _write_gate(
            project,
            "legacy.md",
            "# FUTURE GATE - OLD\n\nStatus: REFERENCE ONLY\n\nAn idea.\n",
        )
        index, _ = gates.refresh(project)
        self.assertEqual(index["gates"][0]["state"], gates.NEEDS_REVIEW)
        self.assertEqual(gates.status(project)["next"], None)
        # Refinement records the honest verdict; it never invents readiness.
        verdict = gates.refine(project, index["gates"][0]["id"], board_tickets=_tickets(project))
        self.assertEqual(verdict["state"], gates.NEEDS_REVIEW)
        self.assertEqual(gates.status(project)["next"], None)
        self.assertEqual(_route(project)["reason"], "maintain")

    def test_O_live_work_owning_a_gate_blocks_a_second_ticket(self):
        """O: no duplicate Work for the same gate root cause."""
        project = self._proj()
        tid = _add(project, "the one bounded slice")
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        index, _ = gates.refresh(project)
        # T-1641: ownership is the slice record. The ticket's text says nothing
        # about the gate; the record binds it, here on a gate a rebuild left
        # unpromoted.
        index["gates"][0]["slices"] = [
            {"ticket": tid, "slice": index["gates"][0]["slice"], "closure": "done"}
        ]
        gates.write_index(project, index)
        report = gates.evaluate(project, _tickets(project))
        self.assertIsNone(report["next"])
        self.assertTrue(
            any(tid in reason for reason in report["evaluated"][0]["reasons"]),
            report["evaluated"],
        )
        # The duplicate is a refusal, never a second ticket.
        promotion = gates.promote(project, "FG-0001", board_tickets=_tickets(project))
        self.assertFalse(promotion["ok"])
        self.assertEqual(len(list(_tickets(project))), 1)

    # ------------------------------------------------------------ P: selection

    def test_P_explicit_priority_outranks_selection_order(self):
        """P: the selection ladder is deterministic and precedence-ordered."""
        project = self._proj()
        _write_gate(project, "a.md", _gate_doc("FG-0001", priority="P3", basis="speculative"))
        _write_gate(project, "b.md", _gate_doc("FG-0002", priority="P0", basis="speculative"))
        _write_gate(project, "c.md", _gate_doc("FG-0003", priority="P1", basis="measured"))
        gates.refresh(project)
        self.assertEqual(gates.evaluate(project, _tickets(project))["next"], "FG-0002")

    def test_Q_measured_beats_speculative_and_small_beats_large(self):
        """Q: basis then slice size break a priority tie."""
        project = self._proj()
        _write_gate(project, "a.md", _gate_doc("FG-0001", basis="speculative", estimate="1"))
        _write_gate(project, "b.md", _gate_doc("FG-0002", basis="measured", estimate="9"))
        _write_gate(project, "c.md", _gate_doc("FG-0003", basis="measured", estimate="2"))
        gates.refresh(project)
        self.assertEqual(gates.evaluate(project, _tickets(project))["next"], "FG-0003")

    def test_R_only_one_gate_is_ever_selected(self):
        """R: selection returns exactly one candidate, never a batch."""
        project = self._proj()
        for n in range(1, 5):
            _write_gate(project, f"g{n}.md", _gate_doc(f"FG-{n:04d}", f"Gate {n}"))
        gates.refresh(project)
        projection = gates.projection(project, _tickets(project))
        self.assertEqual(len(projection["eligible"]), 1)
        self.assertEqual(projection["gate"]["id"], "FG-0001")

    # ------------------------------------------------------------ S: promotion

    def test_S_promotion_binds_one_slice_and_links_the_work(self):
        """S: promotion goes through the ordinary Source/Work ingress."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0042", "Promotable gate"))
        gates.refresh(project)
        from saipen import _execute_future_promotion

        payload, rc = _execute_future_promotion(project, "FG-0042", False)
        self.assertEqual(rc, 0, payload)
        self.assertEqual(payload["code"], "FUTURE_GATE_PROMOTED")
        ticket = payload["ticket"]
        self.assertIn(ticket, _tickets(project))
        self.assertIn("FG-0042", _tickets(project)[ticket]["raw"])
        record = gates.get_gate(project, "FG-0042")
        self.assertEqual(record.state, gates.PROMOTED)
        self.assertEqual(record.slices[0]["ticket"], ticket)
        self.assertEqual(record.slices[0]["closure"], gates.UNRESOLVED)

    def test_T_promotion_is_idempotent_for_the_same_slice(self):
        """T: re-running the promotion for one slice does not double-file."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0042"))
        gates.refresh(project)
        from saipen import _execute_future_promotion

        first, rc_first = _execute_future_promotion(project, "FG-0042", False)
        second, rc_second = _execute_future_promotion(project, "FG-0042", False)
        self.assertEqual(rc_first, 0)
        # One slice is bound, so the gate is PROMOTED with an open slice: the
        # second run is a refusal, not a second ticket.
        self.assertEqual(rc_second, 1)
        self.assertEqual(second["code"], "FUTURE_GATE_NOT_ELIGIBLE")
        self.assertEqual(len(list(_tickets(project))), 1)
        self.assertEqual(first["ticket"], next(iter(_tickets(project))))

    def test_U_a_gate_closes_only_when_every_slice_resolves(self):
        """U: partial promotion keeps the gate open; closure is explicit."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0042"))
        gates.refresh(project)
        from saipen import _execute_future_promotion

        payload, _rc = _execute_future_promotion(project, "FG-0042", False)
        ticket = payload["ticket"]
        gates.record_slice(project, "FG-0042", ticket=ticket, closure="done")
        closed = gates.get_gate(project, "FG-0042")
        self.assertTrue(closed.closed)
        self.assertEqual(closed.state, gates.PROMOTED)
        # A closed gate is not READY again.
        report = gates.evaluate(project, _tickets(project))
        self.assertIsNone(report["next"])

    def test_V_an_ineligible_gate_refuses_with_the_named_reason(self):
        """V: promotion names WHY, and creates nothing."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0042", state="NEEDS_REVIEW"))
        gates.refresh(project)
        from saipen import _execute_future_promotion

        payload, rc = _execute_future_promotion(project, "FG-0042", False)
        self.assertEqual(rc, 1)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["reasons"])
        self.assertEqual(list(_tickets(project)), [])

    # ------------------------------------------------------------ W: index truth

    def test_W_a_corrupt_index_never_fabricates_readiness(self):
        """W: unreadable is not empty."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        gates.index_path(project).write_text("{ not json", encoding="utf-8")
        projection = gates.projection(project, _tickets(project))
        self.assertFalse(projection["indexed"])
        self.assertEqual(projection["eligible"], [])
        self.assertIn("not an empty one", projection["detail"])
        # A corrupt derived index is repaired, never read as "no future work".
        self.assertEqual(_route(project)["reason"], "future-gate-refresh")

    def test_X_a_missing_index_is_unindexed_not_empty(self):
        """X: a project with gates but no index says so, and never claims ready."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        self.assertIsNone(gates.load_index(project))
        projection = gates.projection(project, _tickets(project))
        self.assertFalse(projection["indexed"])
        self.assertEqual(projection["eligible"], [])
        self.assertTrue(projection["refresh_required"])
        self.assertEqual(projection["index_state"], gates.MISSING)
        # Missing projection must not authorize the HUNT/ADD fallthrough.
        self.assertEqual(_route(project)["reason"], "future-gate-refresh")

    def test_Y_an_empty_corpus_over_a_written_index_is_current(self):
        """Y: zero documents is a fact, not schema drift.

        The witness count was compared as `int(prior or -1)`, and `0 or -1` is
        -1, so an empty corpus could never match itself: the projection stayed
        STALE forever and every `continue` re-ran `saipen future refresh`
        against the corpus it had just indexed (CONTINUE_FIXED_POINT).
        """
        project = self._proj()
        gates.refresh(project)
        fresh = gates.freshness(project)
        self.assertEqual(fresh["state"], gates.CURRENT)
        self.assertEqual(fresh["documents"], 0)
        projection = gates.projection(project, _tickets(project))
        self.assertFalse(projection["refresh_required"])
        self.assertEqual(projection["eligible"], [])
        self.assertNotEqual(_route(project)["reason"], "future-gate-refresh")

    # ------------------------------------------------------------ owner + shape

    def test_read_only_mode_lists_but_never_mutates(self):
        """A read-only session evaluates every gate and promotes none of them."""
        from saipen import _future

        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        before = gates.index_path(project).read_bytes()
        prior = os.environ.get("SAIPEN_CAPABILITY")
        os.environ["SAIPEN_CAPABILITY"] = "read-only"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(_future(project, ["status"], True, False), 0)
                self.assertEqual(_future(project, ["next"], True, False), 0)
                for verb in (
                    ["refresh"],
                    ["promote", "FG-0001"],
                    ["add", "A new deferred idea"],
                ):
                    self.assertEqual(_future(project, verb, True, False), 1, verb)
        finally:
            if prior is None:
                os.environ.pop("SAIPEN_CAPABILITY", None)
            else:
                os.environ["SAIPEN_CAPABILITY"] = prior
        self.assertEqual(gates.index_path(project).read_bytes(), before)
        self.assertEqual(list(_tickets(project)), [])
        self.assertEqual([p.name for p in (project / "future_gate").iterdir()], ["gate.md"])

    def test_the_normative_owner_publishes_the_lifecycle(self):
        """The rules the matrix above enforces live in saipen/FUTURE.md."""
        text = FUTURE_OWNER.read_text(encoding="utf-8")
        for token in (
            "RULE-OWNER: FUTURE-GATE-01",
            "deferred authority candidate",
            "procrastination sink",
            ".saipen/future/index.json",
            "AUTONOMOUS WORK EXHAUSTED",
            "Never activate more than one gate at a time",
        ):
            self.assertIn(token, text, token)

    def test_the_idle_ladder_is_published_in_maintenance(self):
        """MAINTENANCE owns the ORDER; FUTURE.md owns the eligibility rules."""
        maintenance = (ROOT / "saipen" / "MAINTENANCE.md").read_text(encoding="utf-8")
        self.assertIn("THE IDLE LADDER", maintenance)
        self.assertIn("eligible FUTURE GATE > HUNT > ADD", maintenance)

    def test_the_index_is_machine_owned_json_with_a_stable_shape(self):
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        gates.refresh(project)
        raw = json.loads(gates.index_path(project).read_text(encoding="utf-8"))
        self.assertEqual(raw["marker"], gates.INDEX_MARKER)
        self.assertEqual(raw["schema"], gates.SCHEMA_VERSION)
        self.assertEqual(raw["gates"][0]["id"], "FG-0001")


def _cli(project: Path, *args: str, capability: str | None = None) -> dict:
    """Run the PUBLIC CLI -- the operator's actual entry point.

    The AUTO matrix deliberately never shells out to `saipen future refresh`:
    requiring that by hand is the very defect these cases exist to close.
    """
    env = dict(os.environ)
    env.pop("SAIPEN_CAPABILITY", None)
    if capability:
        env["SAIPEN_CAPABILITY"] = capability
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "saipen.py"),
            *args,
            "--project-root",
            str(project),
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:  # a crash is a failure, never a silent pass
        payload = {"stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    payload["_rc"] = proc.returncode
    return payload


def _ops(payload: dict) -> list[str]:
    return [step.get("operation") for step in payload.get("continue_trace") or []]


class FutureGateAutoDiscoveryTests(unittest.TestCase):
    """AUTO-01..AUTO-16 -- dropping a file into future_gate/ is sufficient.

    Every case drives the PUBLIC continuation route with a writable
    capability. None of them calls `saipen future refresh` by hand, because
    making the operator refresh the index is the defect being closed.
    """

    def setUp(self):
        self._tmp = []

    def tearDown(self):
        for base in self._tmp:
            shutil.rmtree(base, ignore_errors=True)

    def _proj(self, **kwargs):
        base, project = _project(**kwargs)
        self._tmp.append(base)
        return project

    @staticmethod
    def _idle(project: Path) -> None:
        """Return the fixture to a BOARD halt.

        A successful promotion moves the project into SCOUT, and live Work
        outranks every Future rung -- which is correct, and useless for probing
        the Future layer. This rewinds only that progress.
        """
        state = project / ".saipen" / "STATE.md"
        text = re.sub(
            r"^phase: .*$", "phase: DONE", state.read_text(encoding="utf-8"), flags=re.MULTILINE
        )
        text = re.sub(r"^task: .*$", "task: none", text, flags=re.MULTILINE)
        state.write_text(text, encoding="utf-8")
        (project / ".saipen" / "BOARD.md").write_text(BOARD_PREAMBLE, encoding="utf-8")

    @staticmethod
    def _route_fully(project: Path) -> dict:
        """`route_next` with every projection the real caller supplies."""
        return route_next(
            (project / ".saipen" / "STATE.md").read_text(encoding="utf-8"),
            (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"),
            current_agent="tester",
            future_gate=future_gate_projection(project),
            audit_inbox=audit_inbox_projection(project),
        )

    # ---------------------------------------------------------- AUTO-01 .. 03

    def test_AUTO01_no_index_and_a_dropped_gate_is_refreshed_by_the_public_route(self):
        """AUTO-01: no index, one valid gate, BOARD halted, audit idle.

        The public writable continuation performs the refresh itself, the gate
        becomes visible, and HUNT never runs ahead of the Future layer.
        """
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001", "Dropped gate"))
        self.assertIsNone(gates.load_index(project))
        self.assertEqual(gates.freshness(project)["state"], gates.MISSING)

        payload = _cli(project, "continue")

        self.assertEqual(_ops(payload)[0], "future_refresh", payload)
        self.assertEqual(payload["continue_trace"][0]["result"], "FUTURE_GATE_REFRESHED")
        self.assertNotIn("improve", _ops(payload))
        self.assertEqual(gates.freshness(project)["state"], gates.CURRENT)
        # Visibility, then the ordinary promotion of exactly one bounded slice.
        self.assertEqual(payload["continue_trace"][1]["operation"], "future_promote")
        board = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertIn("FG-0001", board)

    def test_AUTO02_a_new_file_over_a_current_index_is_refreshed_without_a_command(self):
        """AUTO-02: the stale-index red control, reproduced through `cc` alone."""
        project = self._proj()
        _write_gate(project, "one.md", _gate_doc("FG-0001", "First"))
        _cli(project, "continue")
        self._idle(project)
        self.assertEqual(gates.freshness(project)["state"], gates.CURRENT)

        # No refresh command. Just the file.
        _write_gate(project, "two.md", _gate_doc("FG-0002", "Second"))
        self.assertEqual(gates.freshness(project)["state"], gates.STALE)
        self.assertEqual(self._route_fully(project)["reason"], "future-gate-refresh")

        payload = _cli(project, "continue")

        self.assertEqual(_ops(payload)[0], "future_refresh", payload)
        ids = {g["id"] for g in gates.status(project)["gates"]}
        self.assertEqual(ids, {"FG-0001", "FG-0002"})

    def test_AUTO03_an_edited_document_is_visible_to_routing(self):
        """AUTO-03: content mutation cannot hide behind a matching count."""
        project = self._proj()
        path = _write_gate(project, "gate.md", _gate_doc("FG-0001", state="NEEDS_REVIEW"))
        _cli(project, "continue")
        self._idle(project)
        self.assertEqual(gates.freshness(project)["state"], gates.CURRENT)

        edited = path.read_text(encoding="utf-8") + "\nAn added paragraph.\n"
        path.write_text(edited, encoding="utf-8")

        self.assertEqual(gates.freshness(project)["state"], gates.STALE)
        self.assertEqual(self._route_fully(project)["reason"], "future-gate-refresh")
        payload = _cli(project, "continue")
        self.assertEqual(_ops(payload)[0], "future_refresh", payload)
        self.assertEqual(gates.freshness(project)["state"], gates.CURRENT)

    # ---------------------------------------------------------- AUTO-04 .. 06

    def test_AUTO04_a_rename_is_a_corpus_delta_and_identity_survives(self):
        """AUTO-04: the filename is never the identity."""
        project = self._proj()
        original = _write_gate(project, "before.md", _gate_doc("FG-0042", "Stable identity"))
        _cli(project, "continue")
        self._idle(project)

        original.rename(project / "future_gate" / "after.md")

        self.assertEqual(gates.freshness(project)["state"], gates.STALE)
        payload = _cli(project, "continue")
        self.assertEqual(_ops(payload)[0], "future_refresh", payload)
        record = next(g for g in gates.status(project)["gates"] if g["id"] == "FG-0042")
        self.assertEqual(record["path"], "future_gate/after.md")
        self.assertTrue(record["present"])

    def test_AUTO05_a_corrupt_index_is_rebuilt_without_an_operator_prompt(self):
        """AUTO-05: derived state is recoverable, so it is never a dead end."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001", state="NEEDS_REVIEW"))
        _cli(project, "continue")
        self._idle(project)
        gates.index_path(project).write_text("{ not json", encoding="utf-8")

        self.assertEqual(gates.freshness(project)["state"], gates.CORRUPT)
        payload = _cli(project, "continue")

        self.assertEqual(_ops(payload)[0], "future_refresh", payload)
        self.assertEqual(gates.freshness(project)["state"], gates.CURRENT)
        report = gates.status(project, _tickets(project))
        self.assertTrue(report["indexed"])
        # Rebuilt from the corpus, never read as "no eligible gate exists".
        self.assertEqual(report["counts"][gates.NEEDS_REVIEW], 1)
        self.assertIsNone(report["next"])

    def test_AUTO06_read_only_reports_the_stale_projection_and_mutates_nothing(self):
        """AUTO-06: read-only detects, reports, and never repairs."""
        project = self._proj()
        _write_gate(project, "one.md", _gate_doc("FG-0001"))
        _cli(project, "continue")
        self._idle(project)
        _write_gate(project, "two.md", _gate_doc("FG-0002", "Second"))
        before = gates.index_path(project).read_bytes()

        payload = _cli(project, "continue", capability="read-only")

        self.assertEqual(payload["reason"], "read-only-mode", payload)
        self.assertEqual(payload["executable_behavior"], "RESTATE_AND_STOP")
        self.assertEqual(_ops(payload), [])
        self.assertEqual(gates.index_path(project).read_bytes(), before)
        projection = gates.projection(project, _tickets(project))
        self.assertEqual(projection["index_state"], gates.STALE)
        self.assertTrue(projection["refresh_required"])
        self.assertEqual(projection["eligible"], [])
        self.assertIn("not an empty one", projection["detail"])
        self.assertEqual(projection["canonical_next_action"], "saipen future refresh")

    # ---------------------------------------------------------- AUTO-07 .. 11

    def test_AUTO07_an_unmarked_document_is_discovered_and_refined_with_no_import(self):
        """AUTO-07: CASE B of the zero-manual requirement -- no machine header."""
        project = self._proj()
        _write_gate(project, "raw.md", "# A design idea\n\nStatus: DEFERRED\n\nContext.\n")

        payload = _cli(project, "continue")

        self.assertEqual(_ops(payload)[:2], ["future_refresh", "future_refine"], payload)
        records = gates.status(project)["gates"]
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["reviewed"])
        self.assertTrue(gates.record_path(project, records[0]["id"]).is_file())
        # Refinement recorded a verdict and rerouted; continuation did not stall.
        self.assertEqual(self._route_fully(project)["reason"], "maintain")

    def test_AUTO08_exactly_one_bounded_refinement_runs_before_hunt(self):
        """AUTO-08: an ambiguous record is offered once, then never again."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001", state="NEEDS_REVIEW"))

        payload = _cli(project, "continue")

        self.assertEqual(_ops(payload).count("future_refine"), 1, payload)
        # The corpus cannot spin: the verdict is reviewed, so it is not re-offered.
        self.assertEqual(self._route_fully(project)["reason"], "maintain")
        again = _cli(project, "continue")
        self.assertNotIn("future_refine", _ops(again), again)

    def test_AUTO09_refinement_records_a_verified_terminal_verdict(self):
        """AUTO-09: `IMPLEMENTED by T-1` with T-1 DONE is resolved, not filed."""
        project = self._proj()
        _done(project, "T-1")
        _write_gate(project, "legacy.md", "# OLD GATE\n\nStatus: SHIPPED\n\nIMPLEMENTED by T-1.\n")

        payload = _cli(project, "continue")

        self.assertIn("future_refine", _ops(payload), payload)
        record = gates.status(project)["gates"][0]
        self.assertEqual(record["state"], gates.INELIGIBLE)
        self.assertIn("T-1", " ".join(record.get("reasons") or []))
        self.assertEqual(self._route_fully(project)["reason"], "maintain")
        # The historical record produced no new Work for an already closed cause.
        self.assertEqual(list(_tickets(project)), ["T-1"])

    def test_AUTO10_an_unready_verdict_defers_and_never_deadlocks(self):
        """AUTO-10: a `NOT READY` corpus keeps its intent and keeps moving."""
        project = self._proj()
        _write_gate(
            project,
            "legacy.md",
            "# OLD GATE\n\nStatus: DEFERRED\n\nA roadmap item, NOT IMPLEMENTED yet.\n",
        )

        payload = _cli(project, "continue")

        self.assertIn("future_refine", _ops(payload), payload)
        record = gates.status(project)["gates"][0]
        self.assertEqual(record["state"], gates.DEFERRED)
        # Deferred is not READY: no bounded slice was named, so nothing promotes.
        self.assertIsNone(gates.status(project, _tickets(project))["next"])
        self.assertEqual(self._route_fully(project)["reason"], "maintain")

    def test_AUTO11_a_refined_legacy_gate_promotes_through_the_ordinary_ingress(self):
        """AUTO-11: reviewed facts make exactly ONE bounded slice eligible."""
        project = self._proj()
        _write_gate(
            project,
            "legacy.md",
            "# OLD GATE\n\nStatus: DEFERRED\n\nA roadmap item, NOT IMPLEMENTED yet.\n",
        )
        _cli(project, "continue")
        gate_id = gates.status(project)["gates"][0]["id"]
        self.assertIsNone(gates.status(project, _tickets(project))["next"])

        _cli(
            project,
            "future",
            "refine",
            gate_id,
            "--slice",
            "implement the ONE bounded unit named in the record",
            "--evidence",
            "evidence.md",
        )

        self.assertEqual(gates.status(project, _tickets(project))["next"], gate_id)
        self.assertEqual(self._route_fully(project)["reason"], "future-gate-promotion")
        payload = _cli(project, "continue")
        self.assertIn("future_promote", _ops(payload), payload)
        board = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertIn(gate_id, board)

    # ---------------------------------------------------------- AUTO-12 .. 16

    def test_AUTO12_live_work_outranks_a_stale_projection(self):
        """AUTO-12: ordinary Work wins and the Future layer may stay unrefreshed."""
        project = self._proj()
        ticket = _add(project, "ordinary work in flight")
        _doing(project, ticket, "ordinary work in flight")
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))

        routed = self._route_fully(project)

        self.assertNotIn(
            routed["reason"], ("future-gate-refresh", "future-gate-refinement"), routed
        )
        self.assertEqual(routed["reason"], "adopt")
        self.assertEqual(gates.freshness(project)["state"], gates.MISSING)

    def test_AUTO13_an_actionable_audit_outranks_a_stale_projection(self):
        """AUTO-13: the audit layer is consumed before the Future layer."""
        project = self._proj()
        (project / "audit").mkdir(exist_ok=True)
        (project / "audit" / "1.md").write_text("# finding\n\nSomething real.\n", encoding="utf-8")
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))

        routed = self._route_fully(project)

        self.assertNotIn(
            routed["reason"], ("future-gate-refresh", "future-gate-refinement"), routed
        )
        self.assertIn("audit", routed["action"], routed)
        payload = _cli(project, "continue")
        self.assertNotIn("future_refresh", _ops(payload), payload)

    def test_AUTO14_the_live_corpus_migrates_without_touching_an_original(self):
        """AUTO-14: every real document is indexed and classified, none rewritten."""
        project = self._proj()
        source = ROOT / "future_gate"
        originals: dict[str, bytes] = {}
        for path in sorted(source.rglob("*.md")):
            target = project / "future_gate" / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            originals[target.relative_to(project).as_posix()] = target.read_bytes()
        self.assertGreater(len(originals), 1, "the live corpus is the fixture")

        _cli(project, "continue")

        indexed = gates.status(project)
        self.assertEqual(gates.freshness(project)["documents"], len(originals))
        # The historical corpus is every document without the v1 marker; a
        # gate recorded through `saipen future add` is classified by its own
        # header (T-1626, FG-0046).
        legacy = {
            relative
            for relative, blob in originals.items()
            if not blob.decode("utf-8", errors="replace").lstrip().startswith(gates.DOC_MARKER)
        }
        self.assertGreater(len(legacy), 1, "the historical corpus is the subject")
        self.assertEqual(indexed["counts"][gates.NEEDS_REVIEW], len(legacy))
        # Nothing is READY by guess: every historical record is ambiguous first.
        paths = {gate["id"]: gate["path"] for gate in indexed["gates"]}
        routed = gates.status(project, _tickets(project))["next"]
        self.assertNotIn(paths.get(routed), legacy, routed)

        while True:
            pending = [
                g["id"]
                for g in gates.status(project)["gates"]
                if g["state"] == gates.NEEDS_REVIEW and not g.get("reviewed")
            ]
            if not pending:
                break
            _cli(project, "future", "refine", pending[0])

        after = gates.status(project, _tickets(project))
        self.assertEqual(sum(after["counts"].values()), len(originals))
        self.assertNotIn(paths.get(after["next"]), legacy, after["next"])
        self.assertEqual(list(_tickets(project)), [])
        for relative, blob in originals.items():
            self.assertEqual((project / relative).read_bytes(), blob, relative)

    def test_AUTO15_repeating_the_route_is_idempotent(self):
        """AUTO-15: an exact retry creates no duplicate identity and no ticket."""
        project = self._proj()
        _write_gate(project, "gate.md", _gate_doc("FG-0001"))
        _cli(project, "continue")
        self._idle(project)
        second = _cli(project, "continue")
        self._idle(project)
        third = _cli(project, "continue")

        ids = [g["id"] for g in gates.status(project)["gates"]]
        self.assertEqual(ids, sorted(set(ids)))
        self.assertEqual(len(ids), 1)
        self.assertLessEqual(len(_tickets(project)), 1, (second, third))

    def test_AUTO16_no_future_documents_leaves_hunt_unchanged(self):
        """AUTO-16: with no corpus at all, the ladder below is byte-identical."""
        project = self._proj()
        self.assertFalse((project / "future_gate").exists())

        routed = self._route_fully(project)

        self.assertEqual(routed["reason"], "maintain")
        self.assertEqual(routed["action"], "saipen continue")
        self.assertNotIn("future_gate", routed)
        payload = _cli(project, "continue")
        self.assertNotIn("future_refresh", _ops(payload), payload)


if __name__ == "__main__":
    unittest.main()
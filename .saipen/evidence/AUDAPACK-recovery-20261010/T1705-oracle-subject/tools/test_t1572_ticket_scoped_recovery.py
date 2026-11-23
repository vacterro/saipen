"""T-1572: ticket-scoped phase recovery for the CURRENT_DONE_JOURNAL_GAP.

The downstream shape, measured on an AUDAPACK-class project (29.09.26): the
STATE claims `phase: DONE / task: T-261 / transition_from: VERIFY`, the BOARD
carries T-261 under `## DONE` beside a genuinely finished T-260, and the LOG
proves T-261 only up to VERIFY -- no `transition to SHIP`, no finish event.
The VERIFY -> DONE pair is illegal, so every strict reader refuses; but
`_state_phase_repairs` derived its replacement from the GLOBAL transition
chain, whose tail belongs to T-260 (REVIEW, SHIP). Recovery therefore
proposed `phase: SHIP / transition_from: REVIEW` -- a state its own
validator rejects (SHIP is ticket-bearing, the BOARD has no ## DOING ticket)
-- and the project was stranded with no route at all.

Two defects, both closed here:

  * the event-to-ticket binding is now defined ONCE and used everywhere: a
    ticket's lifecycle transitions are exactly the `[T-###]`-tagged
    `transition to <PHASE>` events (the canonical writer tags exactly the
    five ticket-bearing destinations); untagged transition events are
    project-level and are never evidence for a ticket's phase;
  * the shape itself has an explicit classification --
    CURRENT_DONE_JOURNAL_GAP -- with ONE conservative, bounded recovery
    route: reopen T-261 into ## DOING, restore STATE to its last PROVEN
    lifecycle phase (VERIFY from BUILD), point next_action at the canonical
    `PHASE VERIFY T-261`, and let the ordinary REVIEW -> SHIP -> finish
    lifecycle re-establish completion. No SHIP or finish event is ever
    fabricated; the original STATE and BOARD bytes are preserved as
    recovery evidence; the whole plan commits only under ONE operator
    approval (`--apply-approved-repair`).

Regression matrix (report sections 9-10): A/B/C/I/J/K/L live here; E/F/G/H
are pinned by the neighbor suites plus the unit guards at the bottom of
this file.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_fixture_support import CURRENT_STYLE_CONTRACT
from test_hermetic_env import isolate_host_session
from saipen_engine.reconcile import _state_phase_repairs, _transition_chain

SAIPEN_CLI = Path(__file__).resolve().parent / "saipen.py"
_HOME = Path(__file__).resolve().parent.parent


def setUpModule() -> None:
    # An outer host session must never bind this module's disposable
    # fixtures (test_hermetic_env).
    isolate_host_session()


def _event(number: int, op_id: str, text: str, ticket: str | None = None) -> dict:
    # `text` is the taxonomy-stripped body the LOG parser hands reconcilers
    # (the `RUN:` / `DEC:` marker is parsed into `taxonomy`, never into text).
    return {"event": number, "op_id": op_id, "text": text, "taxonomy": "RUN",
            "ticket": ticket}


_A = "a" * 32
_B = "b" * 32
_C = "c" * 32
_D = "d" * 32
_E = "e" * 32
_F = "f" * 32
_G = "g" * 32
_H = "h" * 32
_I = "i" * 32
_J = "j" * 32
_K = "k" * 32
_L = "l" * 32
_M = "m" * 32

#: The interleaved two-ticket journal. T-260 runs its FULL lifecycle
#: (claim, SCOUT, BUILD, VERIFY, REVIEW, SHIP, finish) while T-261 -- claimed
#: AFTER T-260 reached VERIFY -- stops at VERIFY: no SHIP, no finish. T-260's
#: REVIEW/SHIP/finish are the NEWEST transitions in the global chain, which
#: is exactly what made the unscoped reader repair T-261's state from T-260's
#: history. E-014 is an untagged project-level transition: it belongs to no
#: ticket and must never enter a ticket's chain.
_AUDAPACK_EVENTS = [
    _event(1, "claim-" + _A, "claimed via SAIOPS -- owner auda", "T-260"),
    _event(2, "transition-" + _B, "transition to SCOUT -- the generator swap", "T-260"),
    _event(3, "transition-" + _C, "transition to BUILD -- the generator swap", "T-260"),
    _event(4, "transition-" + _D, "transition to VERIFY -- the generator swap", "T-260"),
    _event(5, "checkpoint-" + _E, "VERIFY -- the generator swap gates green", "T-260"),
    _event(6, "claim-" + _F, "claimed via SAIOPS -- owner auda", "T-261"),
    _event(7, "transition-" + _G, "transition to SCOUT -- the parser rewrite", "T-261"),
    _event(8, "transition-" + _H, "transition to BUILD -- the parser rewrite", "T-261"),
    _event(9, "transition-" + _I, "transition to VERIFY -- the parser rewrite", "T-261"),
    _event(10, "checkpoint-" + _J, "VERIFY -- the parser rewrite gates green", "T-261"),
    _event(11, "transition-" + _K, "transition to REVIEW -- the generator swap", "T-260"),
    _event(12, "transition-" + _L, "transition to SHIP -- the generator swap", "T-260"),
    _event(13, "finish-" + _M, "ticket finished via SAIOPS -- completion (from SHIP)", "T-260"),
    _event(14, "transition-" + _A, "transition to PLAN -- project level, no ticket"),
]

_GAP_STATE = {
    "phase": "DONE",
    "task": "T-261",
    "transition_from": "VERIFY",
    "last_event": 14,
    "next_action": "saipen continue",
}

_GAP_BOARD = {
    "tickets": {
        "T-260": {
            "section": "## DONE",
            "fields": {"owner": "auda", "claim_time": "2026-09-29T10:04:00Z",
                       "closure_mode": "own_patch"},
        },
        "T-261": {
            "section": "## DONE",
            "fields": {"owner": "auda", "claim_time": "2026-09-29T11:04:00Z",
                       "closure_mode": "own_patch"},
        },
    }
}


class TicketScopeBindingTests(unittest.TestCase):
    """Matrix A/B/I: the binding is defined once and admits no cross-talk."""

    def test_foreign_predecessor_cannot_supply_source_phase(self):
        events = list(_AUDAPACK_EVENTS)
        events.insert(8, _event(8, "transition-foreign", "transition to SHIP", "T-260"))
        repairs = _state_phase_repairs(dict(_GAP_STATE), events, _GAP_BOARD)
        self.assertEqual({r["field"]: r["to"] for r in repairs}["transition_from"], "BUILD")

    def test_reclaim_does_not_reuse_the_previous_lifecycle(self):
        events = [
            *_AUDAPACK_EVENTS,
            _event(15, "claim-new", "claimed via SAIOPS -- owner auda", "T-261"),
            _event(16, "transition-new", "transition to BUILD", "T-261"),
        ]
        state = dict(_GAP_STATE, last_event=16)
        self.assertEqual(_transition_chain(events, 16, ticket="T-261"), [(16, "BUILD")])
        repairs = _state_phase_repairs(state, events, _GAP_BOARD)
        self.assertEqual({r["field"]: r["to"] for r in repairs}["transition_from"], "SCOUT")

    def test_the_binding_is_exactly_the_tagged_events(self):
        """Matrix B / report S1: one definition, tested as its own contract."""
        chain260 = _transition_chain(_AUDAPACK_EVENTS, 14, ticket="T-260")
        chain261 = _transition_chain(_AUDAPACK_EVENTS, 14, ticket="T-261")
        self.assertEqual(
            chain260,
            [(2, "SCOUT"), (3, "BUILD"), (4, "VERIFY"), (11, "REVIEW"), (12, "SHIP")],
            chain260,
        )
        self.assertEqual(
            chain261, [(7, "SCOUT"), (8, "BUILD"), (9, "VERIFY")], chain261
        )
        # The untagged project-level transition (E-014) is in NO ticket chain.
        for tid in ("T-260", "T-261"):
            self.assertNotIn((14, "PLAN"), _transition_chain(_AUDAPACK_EVENTS, 14, ticket=tid))
        # The unscoped read still exists and still sees every event -- it is
        # simply no longer allowed to answer a ticket-scoped question.
        self.assertEqual(_transition_chain(_AUDAPACK_EVENTS, 14)[-1], (14, "PLAN"))

    def test_matrix_A_unrelated_ticket_never_supplies_phase_evidence(self):
        """THE hostile carrier (report S10): pre-fix this is RED.

        T-260's REVIEW (E-011) and SHIP (E-012) are the global chain tail, so
        the unscoped repair proposed `phase: SHIP / transition_from: REVIEW`
        for T-261's state -- a proposal its own validator then rejected. The
        repaired derivation uses ONLY T-261's own tagged events.
        """
        repairs = _state_phase_repairs(dict(_GAP_STATE), _AUDAPACK_EVENTS, _GAP_BOARD)
        by_field = {r["field"]: r for r in repairs}
        self.assertIn("phase", by_field, repairs)
        self.assertFalse(by_field["phase"].get("blocked"), repairs)
        # T-261's own E-009 proves the destination, E-008 the source.
        self.assertEqual(by_field["phase"]["to"], "VERIFY", repairs)
        self.assertEqual(by_field["transition_from"]["to"], "BUILD", repairs)
        # The classification is explicit, not an anonymous T-1318 repair.
        self.assertEqual(
            by_field["phase"].get("_class"), "current-done-journal-gap", repairs
        )
        # And NO T-260 event number is cited anywhere in the repair set.
        reasons = " ".join(str(r.get("reason", "")) for r in repairs)
        self.assertNotIn("E-011", reasons, reasons)
        self.assertNotIn("E-012", reasons, reasons)

    def test_the_gap_owns_next_action_with_the_canonical_projection(self):
        repairs = _state_phase_repairs(dict(_GAP_STATE), _AUDAPACK_EVENTS, _GAP_BOARD)
        by_field = {r["field"]: r for r in repairs}
        self.assertEqual(by_field["next_action"]["to"], "PHASE VERIFY T-261", repairs)

    def test_a_finish_event_for_the_ticket_closes_the_gap_class(self):
        """A ticket whose finish event EXISTS is not a journal gap.

        With T-261 finished, DONE-from-SHIP is the legal pair, so there is no
        illegal pair to repair at all -- the strongest form of "closed".
        """
        finished = dict(_GAP_STATE, transition_from="SHIP", last_event=13)
        self.assertEqual(
            _state_phase_repairs(finished, _AUDAPACK_EVENTS, _GAP_BOARD), []
        )
        # Even with an illegal pair, a finish event for THE task means the
        # journal DID record completion: not this class, no fabricated
        # rollback. The repair must refuse rather than guess.
        stray = dict(_GAP_STATE, transition_from="VERIFY", last_event=13)
        events = [
            *_AUDAPACK_EVENTS,
            _event(14, "finish-" + _B,
                   "ticket finished via SAIOPS -- completion (from SHIP)", "T-261"),
        ]
        repairs = _state_phase_repairs(stray, events, _GAP_BOARD)
        self.assertFalse(
            any(r.get("_class") == "current-done-journal-gap" for r in repairs), repairs
        )

    def test_matrix_G_a_legal_ship_done_pair_is_never_touched(self):
        """T-260's own terminal state is not this defect class."""
        legal = {"phase": "DONE", "task": "none", "transition_from": "SHIP",
                 "last_event": 13, "next_action": "saipen continue"}
        self.assertEqual(_state_phase_repairs(legal, _AUDAPACK_EVENTS, _GAP_BOARD), [])

    def test_matrix_H_the_unscoped_t1318_repair_still_works(self):
        """A taskless STATE keeps the T-1318 global-chain derivation."""
        events = [
            _event(1, "transition-" + "a" * 32, "transition to SCOUT", "T-260"),
            _event(2, "transition-" + "b" * 32, "transition to BUILD", "T-260"),
        ]
        state = {"phase": "IMPL", "transition_from": "DONE", "last_event": 2}
        repairs = _state_phase_repairs(state, events, None)
        self.assertEqual((repairs[0]["from"], repairs[0]["to"]), ("IMPL", "BUILD"), repairs)
        self.assertEqual(repairs[1]["to"], "SCOUT", repairs)

    def test_a_ticket_bound_state_with_no_tagged_history_refuses(self):
        """No fabrication: a task whose own events prove nothing blocks."""
        state = {"phase": "IMPL", "transition_from": "DONE", "task": "T-261",
                 "last_event": 14}
        repairs = _state_phase_repairs(state, _AUDAPACK_EVENTS[:4], _GAP_BOARD)
        self.assertTrue(repairs[0].get("blocked"), repairs)
        self.assertIsNone(repairs[0].get("to"))


# ---------------------------------------------------------------------------
# The CLI carrier: the real downstream shape, end to end (report S10)
# ---------------------------------------------------------------------------

_GAP_LOG = (
    "- 29.09.26 08:00 [E-001] [T-260] [agent: auda] "
    f"[op: claim-{_A}] DEC: claimed via SAIOPS -- owner auda\n"
    "- 29.09.26 08:01 [E-002] [parent: E-001] [T-260] [agent: auda] "
    f"[op: transition-{_B}] RUN: transition to SCOUT -- the generator swap\n"
    "- 29.09.26 08:02 [E-003] [parent: E-002] [T-260] [agent: auda] "
    f"[op: transition-{_C}] RUN: transition to BUILD -- the generator swap\n"
    "- 29.09.26 08:03 [E-004] [parent: E-003] [T-260] [agent: auda] "
    f"[op: transition-{_D}] RUN: transition to VERIFY -- the generator swap\n"
    "- 29.09.26 08:04 [E-005] [parent: E-004] [T-260] [agent: auda] "
    f"[op: checkpoint-{_E}] RUN: VERIFY -- the generator swap gates green\n"
    "- 29.09.26 09:00 [E-006] [parent: E-005] [T-261] [agent: auda] "
    f"[op: claim-{_F}] DEC: claimed via SAIOPS -- owner auda\n"
    "- 29.09.26 09:01 [E-007] [parent: E-006] [T-261] [agent: auda] "
    f"[op: transition-{_G}] RUN: transition to SCOUT -- the parser rewrite\n"
    "- 29.09.26 09:02 [E-008] [parent: E-007] [T-261] [agent: auda] "
    f"[op: transition-{_H}] RUN: transition to BUILD -- the parser rewrite\n"
    "- 29.09.26 09:03 [E-009] [parent: E-008] [T-261] [agent: auda] "
    f"[op: transition-{_I}] RUN: transition to VERIFY -- the parser rewrite\n"
    "- 29.09.26 09:04 [E-010] [parent: E-009] [T-261] [agent: auda] "
    f"[op: checkpoint-{_J}] RUN: VERIFY -- the parser rewrite gates green\n"
    "- 29.09.26 10:00 [E-011] [parent: E-010] [T-260] [agent: auda] "
    f"[op: transition-{_K}] RUN: transition to REVIEW -- the generator swap\n"
    "- 29.09.26 10:01 [E-012] [parent: E-011] [T-260] [agent: auda] "
    f"[op: transition-{_L}] RUN: transition to SHIP -- the generator swap\n"
    "- 29.09.26 10:02 [E-013] [parent: E-012] [T-260] [agent: auda] "
    f"[op: finish-{_M}] DEC: ticket finished via SAIOPS -- completion (from SHIP)\n"
)

_GAP_BOARD_TEXT = (
    "## DOING\n"
    "## TODO\n"
    "## DONE\n"
    "- [x] T-260 [P1] the generator swap | owner: auda "
    "| claim_time: 2026-09-29T10:04:00Z | closure_mode: own_patch | verify: generator gates pass\n"
    "- [x] T-261 [P1] the parser rewrite | owner: auda "
    "| claim_time: 2026-09-29T11:04:00Z | closure_mode: own_patch | verify: parser gates pass\n"
    "## BLOCKED\n"
)


def _gap_state_text(next_action: str) -> str:
    return (
        "---\n"
        "phase: DONE\n"
        "task: T-261\n"
        f'next_action: "{next_action}"\n'
        'blocker: ""\n'
        "transition_from: VERIFY\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 13\n"
        'style_contract: ' + CURRENT_STYLE_CONTRACT + '\n'
        'saipen_home: "{home}"\n'
        "agent: auda\n"
        "requires:\n  - filesystem\n  - python\n"
        "mode: full\n"
        'updated: "2026-09-29T10:02:00Z"\n'
        "---\n"
    )


def _audapack_project(next_action: str = "saipen continue") -> Path:
    from saipen_engine.journal import ensure_project_lineage

    root = Path(tempfile.mkdtemp(prefix="saipen-t1572-")) / "AUDAPACK"
    (root / ".saipen").mkdir(parents=True)
    (root / ".saipen" / "STATE.md").write_text(
        _gap_state_text(next_action).format(
            home=str(_HOME).replace(chr(92), chr(92) * 2)
        ),
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(_GAP_BOARD_TEXT, encoding="utf-8")
    (root / ".saipen" / "LOG.md").write_text(_GAP_LOG, encoding="utf-8")
    ensure_project_lineage(root)
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    return root


class GapRecoveryRouteTests(unittest.TestCase):
    """Matrix C/J/K/L: one bounded route, no dead ends, idempotent."""

    def setUp(self) -> None:
        self.root = _audapack_project()
        self.addCleanup(lambda: shutil.rmtree(self.root.parent, ignore_errors=True))

    def cli(self, *args, crash: dict | None = None) -> dict:
        from saipen_engine.paths import unbound_environment

        env = unbound_environment()
        if crash:
            env.update(crash)
        run = subprocess.run(
            [sys.executable, str(SAIPEN_CLI), *args, "--json"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=600,
        )
        try:
            return json.loads(run.stdout or "{}")
        except json.JSONDecodeError:
            return {"_raw": (run.stdout + run.stderr)[:400], "rc": run.returncode}

    def route(self) -> list[str]:
        answer = self.cli("recover")
        self.assertFalse(answer.get("ok"), answer)
        route = answer.get("canonical_next_command")
        self.assertTrue(route, f"recover named no route out of the gap: {answer}")
        self.assertEqual(route.split()[:3], ["saipen", "recover", "--apply-approved-repair"])
        return route.split()[1:]

    def test_approval_refuses_changed_board_bytes_before_writing(self):
        route = self.route()
        board = self.root / ".saipen" / "BOARD.md"
        board.write_text(board.read_text(encoding="utf-8") + "\nChanged context\n",
                         encoding="utf-8")
        before = {name: (self.root / ".saipen" / name).read_bytes()
                  for name in ("STATE.md", "BOARD.md", "LOG.md")}
        self.assertEqual(self.cli(*route).get("code"), "STALE_APPROVED_REPAIR")
        after = {name: (self.root / ".saipen" / name).read_bytes() for name in before}
        self.assertEqual(before, after)

    def test_matrix_C_recover_names_one_approval_route_from_every_verb(self):
        route = self.route()
        joined = " ".join(route)
        # The route is reachable from the verbs a stranded session reaches
        # for, not only from the one that computed it (no dead ends).
        self.assertEqual(self.cli("continue").get("canonical_next_command", "").split()[:3],
                         ["saipen", "recover", "--apply-approved-repair"])
        self.assertEqual(
            self.cli("start", "a new task").get("canonical_next_command", "").split()[:3],
            ["saipen", "recover", "--apply-approved-repair"],
        )
        # The approval names the gap class explicitly.
        plan = self.cli("recover")
        self.assertIn(
            "current-done-journal-gap",
            json.dumps(plan.get("changed", {})) + json.dumps(plan.get("refused", [])),
            plan,
        )
        self.assertIn(joined.split(None, 2)[-1][:8], " ".join(route))

    def test_matrix_CKL_the_route_converges_and_replay_is_refused(self):
        route = self.route()
        applied = self.cli(*route)
        self.assertTrue(applied.get("ok"), applied)
        self.assertEqual(applied.get("code"), "REPAIRED", applied)

        state = (self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        # T-261's OWN lifecycle, restored: E-009 proves VERIFY, E-008 BUILD.
        self.assertIn("phase: VERIFY", state)
        self.assertIn("transition_from: BUILD", state)
        self.assertIn("task: T-261", state)
        self.assertIn("PHASE VERIFY T-261", state)

        board = (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        lines = board.splitlines()
        t261 = [line for line in lines if "T-261" in line]
        self.assertEqual(len(t261), 1, board)
        self.assertTrue(t261[0].startswith("- [/] "), board)
        self.assertNotIn("closure_mode", t261[0], board)
        self.assertIn("owner: auda", t261[0], board)
        # The reopened ticket sits under ## DOING, between the headers.
        doing = lines.index("## DOING")
        todo = lines.index("## TODO")
        self.assertTrue(doing < lines.index(t261[0]) < todo, board)
        # T-260's real completion is untouched: still [x] under ## DONE.
        t260 = [line for line in lines if "T-260" in line]
        self.assertEqual(len(t260), 1, board)
        self.assertTrue(t260[0].startswith("- [x] "), board)
        self.assertIn("closure_mode: own_patch", t260[0], board)
        done = lines.index("## DONE")
        self.assertTrue(done < lines.index(t260[0]), board)

        verdict = self.cli("validate")
        self.assertEqual(verdict.get("structural_gate"), "pass", verdict)
        self.assertEqual(self.cli("recover").get("code"), "CLEAN")
        self.assertTrue(self.cli("status").get("ok"))
        self.assertTrue(self.cli("continue").get("ok"))
        # Matrix L: replaying the same approval is refused, never re-applied.
        self.assertEqual(self.cli(*route).get("code"), "STALE_APPROVED_REPAIR")

    def test_no_history_is_fabricated_by_the_recovery(self):
        """Acceptance 4: the LOG gains the DEC, nothing else."""
        route = self.route()
        self.assertTrue(self.cli(*route).get("ok"))
        log = (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        # Exactly the events that existed plus ONE reconcile DEC.
        self.assertEqual(len(re.findall(r"\[E-\d+\]", log)), 14, log)
        self.assertTrue(log.startswith(_GAP_LOG), "historical bytes changed")
        self.assertEqual(log.count("transition to SHIP"), 1, log)
        self.assertEqual(log.count("[op: finish-"), 1, log)
        # No SHIP or finish was invented for T-261.
        for line in log.splitlines():
            if "T-261" in line:
                self.assertNotIn("transition to SHIP", line, log)
                self.assertNotIn("[op: finish-", line, log)

    def test_the_original_state_and_board_bytes_survive_as_evidence(self):
        """Acceptance 6: the replaced bytes are preserved, both surfaces."""
        state_before = (self.root / ".saipen" / "STATE.md").read_bytes()
        board_before = (self.root / ".saipen" / "BOARD.md").read_bytes()
        route = self.route()
        self.assertTrue(self.cli(*route).get("ok"))
        recovery = self.root / ".saipen" / "recovery"
        kept_state = [p.read_bytes() for p in recovery.rglob("*.STATE.md")]
        kept_board = [p.read_bytes() for p in recovery.rglob("*.BOARD.md")]
        self.assertIn(state_before, kept_state, "original STATE bytes were not preserved")
        self.assertIn(board_before, kept_board, "original BOARD bytes were not preserved")

    def test_matrix_J_resolve_next_action_cannot_mask_the_gap(self):
        """A legacy next_action must not become the advertised exit."""
        masked = _audapack_project(next_action="re-check the coverage gates")
        self.addCleanup(lambda: shutil.rmtree(masked.parent, ignore_errors=True))

        def masked_cli(*args):
            from saipen_engine.paths import unbound_environment

            run = subprocess.run(
                [sys.executable, str(SAIPEN_CLI), *args, "--json"],
                cwd=str(masked), capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                env=unbound_environment(), timeout=600,
            )
            try:
                return json.loads(run.stdout or "{}")
            except json.JSONDecodeError:
                return {"_raw": (run.stdout + run.stderr)[:400]}

        bare = masked_cli("recover")
        route = bare.get("canonical_next_command", "")
        self.assertEqual(route.split()[:3], ["saipen", "recover", "--apply-approved-repair"],
                         f"recover advertised the masking verb instead: {bare}")

        state_before = (masked / ".saipen" / "STATE.md").read_bytes()
        board_before = (masked / ".saipen" / "BOARD.md").read_bytes()
        supplied = masked_cli("recover", "resolve-next-action", "saipen validate")
        self.assertFalse(supplied.get("ok"), supplied)
        # The refusal names the route that owns the defect, and writes nothing.
        self.assertIn(
            "--apply-approved-repair",
            str(supplied.get("canonical_next_command", "")) + str(supplied.get("detail", "")),
            supplied,
        )
        self.assertEqual((masked / ".saipen" / "STATE.md").read_bytes(), state_before)
        self.assertEqual((masked / ".saipen" / "BOARD.md").read_bytes(), board_before)


class GapCrashPrefixTests(unittest.TestCase):
    """Report S8 / acceptance 10: every crash prefix converges canonically.

    The terminal repair is interrupted for real at each journal stage (the
    CLI child dies via the journal engine's own crash seam). Every partial
    prefix must be already-valid or deterministically recoverable through
    `recover` alone -- never through a manual STATE edit.
    """

    STAGES = ("PREPARE", "GENERIC", "LOG", "BOARD", "STATE", "VERIFIED")

    def _converged_invariants(self, root: Path) -> None:
        state = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("phase: VERIFY", state)
        self.assertIn("transition_from: BUILD", state)
        self.assertIn("task: T-261", state)
        board = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        t261 = [line for line in board.splitlines() if "T-261" in line]
        self.assertEqual(len(t261), 1, board)
        self.assertTrue(t261[0].startswith("- [/] "), board)
        log = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("transition to SHIP"), 1, log)
        self.assertEqual(len(re.findall(r"\[E-\d+\]", log)), 14, log)

    def test_every_crash_prefix_is_deterministically_recoverable(self):
        from saipen_engine.paths import unbound_environment

        for stage in self.STAGES:
            with self.subTest(stage=stage):
                root = _audapack_project()
                self.addCleanup(lambda r=root: shutil.rmtree(r.parent, ignore_errors=True))

                def run_cli(*args, crash=None):
                    env = unbound_environment()
                    if crash:
                        env.update(crash)
                    return subprocess.run(
                        [sys.executable, str(SAIPEN_CLI), *args, "--json"],
                        cwd=str(root), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", env=env, timeout=600,
                    )

                plan = json.loads(
                    run_cli("recover", "--json").stdout or "{}"
                )
                route = plan.get("canonical_next_command", "").split()[1:]
                self.assertTrue(route, plan)

                crashed = run_cli(*route, crash={f"NITRO_CRASH_AFTER_{stage}": "1"})
                self.assertNotEqual(crashed.returncode, 0,
                                    crashed.stdout + crashed.stderr)

                # Convergence through canonical verbs only, bounded attempts.
                settled = None
                for _ in range(4):
                    answer = json.loads(run_cli("recover", "--json").stdout or "{}")
                    settled = answer
                    if answer.get("code") == "CLEAN":
                        break
                    step = answer.get("canonical_next_command") or ""
                    if "--apply-approved-repair" in step:
                        run_cli(*step.split()[1:])
                        continue
                    # A pending interrupted op is settled by recover itself
                    # (RECOVERED) or named with its own resolve route.
                    self.assertTrue(
                        answer.get("ok") or step,
                        f"crash prefix {stage} stranded the project: {answer}",
                    )
                    if step:
                        run_cli(*step.split()[1:])
                self.assertEqual(settled.get("code"), "CLEAN",
                                 f"stage {stage} did not converge: {settled}")
                self._converged_invariants(root)


# ---------------------------------------------------------------------------
# The REAL downstream bytes (T-1574): AUDAPACK .saipen as found 30.09.26
# ---------------------------------------------------------------------------
#
# The report's fixture assumed canonical `transition to BUILD/VERIFY` events
# for T-261. The real journal has none: after the canonical claim (E-2601)
# the agent hand-wrote `RUN: SCOUT`/`RUN: build`/`RUN: VERIFY` lines under
# invented op ids, set STATE to DONE/from VERIFY, moved the row to ## DONE and
# added an `evidence:` field outside the closed BOARD grammar. On those bytes
# the ticket-scoped repair found no tagged transition, refused, and left the
# project READ_ONLY_DIAGNOSIS_ONLY -- stranded exactly as before.

_REAL_LOG = (
    "- 29.09.26 19:22 [E-001] [T-260] [agent: buffy] "
    f"[op: claim-{_A}] DEC: claimed via SAIOPS -- owner buffy\n"
    "- 29.09.26 19:22 [E-002] [parent: E-001] [T-260] [agent: buffy] "
    f"[op: transition-{_B}] RUN: transition to BUILD -- submit fallback\n"
    "- 29.09.26 19:22 [E-003] [parent: E-002] [T-260] [agent: buffy] "
    f"[op: transition-{_C}] RUN: transition to VERIFY -- gates run\n"
    "- 29.09.26 19:22 [E-004] [parent: E-003] [T-260] [agent: buffy] "
    f"[op: transition-{_D}] RUN: transition to REVIEW -- self-review\n"
    "- 29.09.26 19:22 [E-005] [parent: E-004] [T-260] [agent: buffy] "
    f"[op: transition-{_E}] RUN: transition to SHIP -- ship widget 0.0.90\n"
    "- 29.09.26 19:22 [E-006] [parent: E-005] [T-260] [agent: buffy] "
    f"[op: finish-{_F}] DEC: ticket finished via SAIOPS -- completion (from SHIP)\n"
    "- 29.09.26 19:58 [E-007] [parent: E-006] [T-261] [agent: buffy] "
    f"[op: claim-{_G}] DEC: claimed via SAIOPS -- owner buffy\n"
    "- 29.09.26 20:47 [E-008] [parent: E-007] [T-261] [agent: buffy] "
    "[op: scout-4c1f9a2b7e0d4a6c8b1e5f2093d7a4c] RUN: SCOUT -- T-261 adoption split\n"
    "- 29.09.26 20:48 [E-009] [parent: E-008] [T-261] [agent: buffy] "
    "[op: build-7b1e2c9d4a8f3b6e0c5d8a19f4b2e7c] RUN: build -> widget 0.0.91\n"
    "- 29.09.26 20:49 [E-010] [parent: E-009] [T-261] [agent: buffy] "
    "[op: verify-2d8c4f6b0e9a7c1d5f3b8e60a2c94d7e] RUN: VERIFY -- 776 PASS 0 FAIL\n"
)

_REAL_BOARD = (
    "## TODO\n"
    "## DOING\n"
    "## DONE\n"
    "- [x] T-261 [P1] Fix A3 split-brain | verify: adoption split proven "
    "| owner: buffy | claim_time: 2026-09-29T19:58:54Z | closure_mode: own_patch "
    "| evidence: widget 0.0.91; full gate 776 widget PASS, ruff clean\n"
    "- [x] T-260 [P1] Widget READY veto | verify: widget gates pass "
    "| owner: buffy | claim_time: 2026-09-29T19:22:00Z | closure_mode: own_patch\n"
    "## BLOCKED\n"
)

_REAL_NEXT = ("PHASE DONE T-261 -- ship widget 0.0.91 to the Bridge; operator "
              "acceptance is required before the board is closed")


class RealDownstreamShapeTests(unittest.TestCase):
    """Canonical claim + hand-written lines: the claim alone proves SCOUT."""

    def setUp(self) -> None:
        self.root = _audapack_project(next_action=_REAL_NEXT)
        saipen = self.root / ".saipen"
        state = (saipen / "STATE.md").read_text(encoding="utf-8")
        state = state.replace("last_event: 13", "last_event: 10")
        (saipen / "STATE.md").write_text(state.replace("agent: auda", "agent: buffy"),
                                         encoding="utf-8")
        (saipen / "BOARD.md").write_text(_REAL_BOARD, encoding="utf-8")
        (saipen / "LOG.md").write_text(_REAL_LOG, encoding="utf-8")
        self.addCleanup(lambda: shutil.rmtree(self.root.parent, ignore_errors=True))
        self.cli = GapRecoveryRouteTests.cli.__get__(self)

    def test_hand_written_lines_are_not_phase_evidence(self):
        from saipen_engine.log import parse_log_line

        events = [e for e in map(parse_log_line, _REAL_LOG.splitlines()) if e]
        self.assertEqual(_transition_chain(events, 10, ticket="T-261"), [])
        board = {"tickets": {
            "T-261": {"section": "## DONE", "raw": _REAL_BOARD.splitlines()[3],
                      "fields": {"owner": "buffy", "claim_time": "2026-09-29T19:58:54Z",
                                 "closure_mode": "own_patch"}},
            "T-260": {"section": "## DONE",
                      "fields": {"owner": "buffy", "closure_mode": "own_patch"}},
        }}
        state = {"phase": "DONE", "task": "T-261", "transition_from": "VERIFY",
                 "last_event": 10, "next_action": _REAL_NEXT}
        repairs = {r["field"]: r for r in _state_phase_repairs(state, events, board)}
        self.assertEqual(repairs["phase"]["to"], "SCOUT", repairs)
        self.assertEqual(repairs["phase"]["gap"]["last_event"], 7, repairs)
        self.assertEqual(repairs["transition_from"]["to"], "SCOUT", repairs)
        self.assertEqual(repairs["next_action"]["to"], "PHASE SCOUT T-261", repairs)

    def test_the_named_route_converges_on_the_real_bytes(self):
        before = {name: (self.root / ".saipen" / name).read_bytes()
                  for name in ("STATE.md", "BOARD.md", "LOG.md")}
        plan = self.cli("recover")
        route = str(plan.get("canonical_next_command") or "").split()
        self.assertEqual(route[:3], ["saipen", "recover", "--apply-approved-repair"], plan)
        self.assertIn("evidence", str(plan.get("detail")), plan)
        applied = self.cli(*route[1:])
        self.assertEqual(applied.get("code"), "REPAIRED", applied)

        state = (self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("phase: SCOUT", state)
        self.assertIn("transition_from: SCOUT", state)
        self.assertIn('next_action: "PHASE SCOUT T-261"', state)
        row = [line for line in (self.root / ".saipen" / "BOARD.md")
               .read_text(encoding="utf-8").splitlines() if "T-261" in line]
        self.assertEqual(len(row), 1)
        self.assertTrue(row[0].startswith("- [/] T-261"), row)
        self.assertNotIn("evidence:", row[0])
        self.assertNotIn("closure_mode", row[0])
        self.assertIn("claim_time: 2026-09-29T19:58:54Z", row[0])

        self.assertEqual(self.cli("validate").get("structural_gate"), "pass")
        self.assertEqual(self.cli("recover").get("code"), "CLEAN")
        self.assertEqual(self.cli("continue").get("action"), "PHASE SCOUT T-261")
        self.assertEqual(self.cli(*route[1:]).get("code"), "STALE_APPROVED_REPAIR")
        log = (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertTrue(log.startswith(_REAL_LOG), "historical bytes changed")
        self.assertNotIn("transition to SHIP", log[len(_REAL_LOG):])
        kept = {p.name.rsplit(".", 2)[-2]: p.read_bytes()
                for p in (self.root / ".saipen" / "recovery" / "terminal-gap").iterdir()}
        self.assertEqual(kept, {"STATE": before["STATE.md"], "BOARD": before["BOARD.md"],
                                "LOG": before["LOG.md"]})


if __name__ == "__main__":
    unittest.main()

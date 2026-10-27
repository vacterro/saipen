"""Bounded autonomous continuation executor semantics (T-1416).

THE INCIDENT THIS MODULE'S RULES COME FROM
------------------------------------------
`saipen continue` resolved ONE next action and returned it. Everything the
flow did between two model decisions -- finishing a reviewed ticket whose gate
was already green, resuming the parent the closure restores, reaching the next
deterministic route -- came back to the operator as another "continue" prompt.
The measured leak list: SCOUT, BUILD, VERIFY, REVIEW, SHIP, unblock,
retirement, checkpoint, parent resume, Improve lifecycle.

This module owns the SEMANTIC half of the repair: which routed actions may
execute without a model and which must stop. The mechanical drive loop lives
at the CLI boundary (`saipen.py::_continue_chain`), because only that layer
owns the project snapshot, the writer lock and the canonical operation
imports. The split is deliberate: the closed action vocabulary is data here,
not a string list scattered across the CLI.

WHAT MAY AUTO-EXECUTE, AND WHY THE SET IS THIS SMALL
`finish-at-ship`: phase SHIP + this agent's single DOING claim + the routed
action naming that exact ticket. The semantic content (review evidence, source
coverage, closure mode) is already durable; `ticket done` re-runs every gate
before it writes. Nothing is guessed, and a refusal is reported, never
softened. Phase work (SCOUT..REVIEW) is NOT in the set: it needs judgement,
so it is a STOP boundary returned to the model.

`adopt`: T-1436 made dependency resume restore the parent WITHOUT a synthesized
live claim, so the resumed seat may route to `saipen claim T-###` -- the
router's own adoption action, emitted only when the active DOING is UNCLAIMED
or FOREIGN_STALE (a live foreign claim is never adopted). It is the same
mechanical claim the model would run, it re-checks every gate at apply time,
and without it the parent resume T-1416 exists to automate would stop one step
short of the boundary on every cc.

`state_identity` is the fixed-point witness: an execution that succeeds but
leaves phase, task, last_event and BOARD byte-identical did not progress, and
re-running it would burn the whole budget on the same action.
"""

from __future__ import annotations

import hashlib
import os

#: Hard local iteration bound. One iteration = one executed canonical
#: operation. Chosen well above any real deterministic chain (a corridor of
#: nested parent resumes) and far below anything unbounded.
MAX_ITERATIONS = 32

#: Test/ops seam: a caller may LOWER the bound, never raise it past the hard
#: compile-time maximum -- an environment variable that could disable the
#: bound would be the unbounded recursion this executor exists to prevent.
_ENV_BOUND = "SAIPEN_CONTINUE_MAX_ITERATIONS"


def max_iterations() -> int:
    raw = os.environ.get(_ENV_BOUND, "")
    if raw.isdigit():
        value = int(raw)
        if 1 <= value <= MAX_ITERATIONS:
            return value
    return MAX_ITERATIONS


CONTINUE_BUDGET_EXHAUSTED = "CONTINUE_BUDGET_EXHAUSTED"
CONTINUE_FIXED_POINT = "CONTINUE_FIXED_POINT"

#: Closed classification vocabulary.
FINISH_AT_SHIP = "finish-at-ship"
ADOPT = "adopt"
#: SRC-104 / T-1461: projecting a durable operational append is mechanical --
#: class, delta and supersession were recorded when the operator's bytes were
#: captured -- so `cc` executes it instead of stopping to hand it back.
APPLY_APPEND = "apply-append"
#: FUTURE-GATE-01 (T-1614): consuming ONE eligible deferred authority
#: candidate is a mechanical canonical mutation, exactly like ADOPT -- `cc`
#: executes it instead of stopping to hand a gate back as advice. The route
#: names the gate id, and the executor re-checks eligibility at apply time.
PROMOTE_FUTURE_GATE = "promote-future-gate"
#: FUTURE-GATE-01 (T-1614): rebuilding the derived projection and normalizing
#: ONE ambiguous record are bounded mechanical operations on derived state --
#: no ticket, no authority, no operator. `cc` performs them itself instead of
#: handing back "run saipen future refresh" as a required human action.
REFRESH_FUTURE_GATE = "refresh-future-gate"
REFINE_FUTURE_GATE = "refine-future-gate"
#: T-1797 / SRC-257: Auto-consuming an external audit generation in audit/ is
#: mechanical when the session has continuation authority -- no manual routing needed.
APPLY_AUDIT_INGEST = "apply-audit-ingest"
#: T-1798 / SRC-258: Auto-converging install pointer onto verified running engine
#: is mechanical under active continuation authority -- no manual routing needed.
APPLY_REBIND_HOME = "apply-rebind-home"
#: A 45-document corpus must not consume an unbounded autonomous invocation:
#: one refinement per chain, then ordinary routing.
MAX_REFINEMENTS_PER_CHAIN = 1
IDLE_MAINTAIN = "idle-maintain"
REFUSAL = "refusal"
STOP = "boundary"

#: Truthful idle / terminal disposition constants (SAIHANDOFF / T-1807 / T-1619).
NO_ADMISSIBLE_WORK = "no-admissible-work"
ALL_REQUIREMENTS_COMPLETE = "all-requirements-complete"
ALL_WORK_COMPLETE = "all-work-complete"
IDLE_BLOCKED_EXTERNAL = "idle-blocked-external"
IDLE_OPERATOR_REQUIRED = "idle-operator-required"
IDLE_FUTURE_GATED = "idle-future-gated"


def classify_route(routed: dict, state: dict, board: dict) -> str:
    """The ONE semantic classification of a routed action (T-1416).

    Pure: reads the routed dict, the parsed STATE and the parsed BOARD. Any
    action outside the closed set -- including every shell or external string,
    which would never appear as a canonical route -- is a STOP.
    """
    if not routed.get("ok"):
        return REFUSAL
    action = str(routed.get("action") or "")
    reason = str(routed.get("reason") or "")
    if action == "saipen rebind-home --auto" or reason == "rebind-home":
        return APPLY_REBIND_HOME
    if reason == "audit-inbox" and action == "saipen audit ingest":
        return APPLY_AUDIT_INGEST
    if (
        reason == "unprojected-source-append"
        and routed.get("receipt")
        and action == f"saipen source apply-append {routed.get('receipt')}"
    ):
        return APPLY_APPEND
    doing = [t for t in (board.get("tickets") or {}).values() if t.get("section") == "## DOING"]
    # ADOPT (T-1436): the router's own adoption action for an UNCLAIMED or
    # FOREIGN_STALE active DOING -- never a live foreign claim (the router
    # refuses that route and the claim operation re-checks at apply time).
    if reason == "adopt" and len(doing) == 1:
        ticket = str(doing[0].get("id") or "")
        if ticket and action == f"saipen claim {ticket}":
            return ADOPT
    if (
        reason == "future-gate-refresh"
        and routed.get("action_kind") == "FUTURE_GATE_REFRESH"
        and action == "saipen future refresh"
    ):
        return REFRESH_FUTURE_GATE
    if (
        reason == "future-gate-refinement"
        and routed.get("action_kind") == "FUTURE_GATE_REFINEMENT"
        and routed.get("future_gate")
        and action == f"saipen future refine {routed.get('future_gate')}"
    ):
        return REFINE_FUTURE_GATE
    if (
        reason == "future-gate-promotion"
        and routed.get("action_kind") == "FUTURE_GATE_PROMOTION"
        and routed.get("future_gate")
        and action == f"saipen future promote {routed.get('future_gate')}"
    ):
        return PROMOTE_FUTURE_GATE
    if len(doing) == 1:
        ticket = str(doing[0].get("id") or "")
        if (
            state.get("phase") == "SHIP"
            and state.get("task") == ticket
            and action == f"PHASE SHIP {ticket}"
        ):
            return FINISH_AT_SHIP
    if action == "saipen continue" and reason == "maintain":
        if (
            state.get("execution_intent") == "goal"
            and routed.get("stop_reason") == "NO_ADMISSIBLE_WORK"
        ):
            from . import goal_authority

            if not goal_authority.is_continuous_maintenance(state):
                return STOP
        return IDLE_MAINTAIN
    # T-1875 (SRC-304): `maintain` is not the only shape of the idle boundary.
    # When the audit inbox holds ACTIVE layers whose linked Work is externally
    # blocked, the router answers `audit-inbox-unworkable` carrying the SAME
    # NO_ADMISSIBLE_WORK truth. Under a proven continuous-maintenance grant
    # that is exactly acceptance H16 -- the external blocker keeps its own
    # gate and independent authorized improvement still proceeds. Without that
    # grant this stays a STOP: H02 keeps the ordinary goal contract, and the
    # audit blocker is never relabelled as idle maintenance.
    if (
        reason == "audit-inbox-unworkable"
        and routed.get("stop_reason") == "NO_ADMISSIBLE_WORK"
    ):
        from . import goal_authority

        if goal_authority.is_continuous_maintenance(state):
            return IDLE_MAINTAIN
    return STOP


def state_identity(state: dict, board_text: str) -> str:
    """Cheap productive-change witness: phase, task, last_event + BOARD bytes."""
    board_digest = hashlib.sha256((board_text or "").encode("utf-8")).hexdigest()[:16]
    payload = f"{state.get('phase')}|{state.get('task')}|{state.get('last_event')}|{board_digest}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

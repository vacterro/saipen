"""Shared deterministic next-action router (NITRO dogfood II, T-590).

One pure function implements the deterministic parts of CORE section 1.11's
action priority -- RECOVER > UNBLOCK > FINISH > START > MAINTAIN -- from a
parsed STATE + BOARD + recovery state. `saipen status`, `saipen next` and the
context compiler all consume THIS router, never separate routing logic.

It deliberately does NOT decide semantic architecture questions (whether a
transition deserves REVIEW, whether a goal is satisfied); it computes the
exact next EXECUTABLE mechanical action the state demands.
"""

from __future__ import annotations

from pathlib import Path

from . import phases
from .board import parse_board, ticket_is_workable, claim_status
from .result import Result
from .state import parse_state


def _top_workable(board: dict, agent: str | None = None) -> str | None:
    """Deterministic Pick Rule: topmost TODO ticket whose needs are all DONE
    and which no other agent holds under a live claim."""
    tickets = board["tickets"]
    for ticket in tickets.values():
        if ticket_is_workable(ticket, tickets, agent=agent):
            return ticket["id"]
    return None


def route_next(state_text: str, board_text: str,
                pending_ops: list | None = None,
                conflict_ops: list | None = None,
                now: datetime.datetime | None = None) -> dict:
    """Compute the exact next executable action.

    Returns a dict with `action` (an executable mechanical action), `reason`
    (which priority rule fired), and optional `ticket`/`detail`. Never echoes
    STATE.next_action -- it is a projection, not a mirror (NITRO dogfood II).
    `now` (UTC) drives § 1.4 claim-liveness for the active-ticket binding; tests
    inject a fixed instant (P0 claim-ownership truth).
    """
    pending = list(pending_ops or [])
    conflicts = list(conflict_ops or [])
    # A STATE the shared parser cannot read whole is not a routing surface:
    # duplicate keys or a broken fence must never project an executable next
    # action from a partial parse (T-1003 hostile findings). Fail closed.
    from .state import parse_state_or_error
    state, state_error = parse_state_or_error(state_text)
    if state_error:
        return {"ok": False, "action": "saipen status",
                "reason": "state-malformed",
                "detail": f"STATE parse error: {state_error}"}
    # Empty STATE is bootstrap-only (hostile-regression, P1): a file with no
    # frontmatter reads as {} for status display, but it is NOT a routing
    # surface -- there is no phase, no agent, no continuation to project.
    # Only a fresh bootstrap may sit here, and the routed action for a
    # bootstrap is the INIT entry, never an ordinary maintenance/start
    # projection.
    if not state:
        return {"ok": True, "action": "saipen status",
                "reason": "bootstrap",
                "executable_behavior": "RESTATE_AND_STOP",
                "detail": "empty STATE is bootstrap-only; no continuation "
                          "exists yet -- bootstrap via INIT before routing"}
    board = parse_board(board_text)
    phase = state.get("phase")
    task = state.get("task")
    na = state.get("next_action") or ""

    # READ-ONLY MODE outranks everything (T-1003 carrier-loss wave): a state
    # whose mode forbids mutation must never receive a mutating routed action
    # -- no PHASE/SHIP/RUN, and not even recovery (recovery writes). The
    # closed rule lives here once: mode == "read-only" forbids ALL mutation;
    # "full" and "no-publish" both allow local mutation (no-publish only
    # forbids git publish steps, which the router never emits anyway).
    if state.get("mode") == "read-only":
        return {"ok": True, "action": "saipen status",
                "reason": "read-only-mode",
                "executable_behavior": "RESTATE_AND_STOP",
                "detail": "STATE mode is read-only; no mutating next action "
                          "may be routed -- inspect only"}

    # RECOVER outranks everything (after the read-only brake): an unresolved
    # op or conflict must be resolved before any canonical work.
    if conflicts:
        return {"ok": False, "action": "saipen recover",
                "reason": "recovery-conflict",
                "detail": f"unresolved conflict: {', '.join(conflicts)}"}
    if pending:
        return {"ok": False, "action": "saipen recover",
                "reason": "recovery-pending",
                "detail": f"unresolved operation: {', '.join(pending)}"}

    # A board the shared parser cannot read whole (an unrecognized ticket
    # field, a malformed ticket line, a missing heading) is not a work
    # surface: a typo'd `| blockr:` is exactly how a blocker-bearing ticket
    # launders itself into workable, so malformed input must FAIL the route
    # (ok: false, VALIDATION_FAILED) -- never a successful projection from
    # corrupt input. status/next/context propagate the failure; the parser
    # diagnostics stay in `detail` and recovery flags stay truthful.
    if board["errors"]:
        return {"ok": False, "action": "saipen status",
                "reason": "board-malformed",
                "detail": "BOARD parse error(s): "
                          + "; ".join(board["errors"][:3])}

    doing = [t for t in board["tickets"].values()
             if t["section"] == "## DOING"]
    active = doing[0]["id"] if doing else None

    # BINDING (hostile-regression, P0): STATE.task binds BOARD.DOING only where
    # this agent actually OWNS or ADOPTS the active ticket. The ONE
    # claim_status classifier decides: a runtime-fresh FOREIGN_LIVE or INVALID
    # claim changes the rule.
    #   - INVALID (half owner/claim_time pair, non-UTC stamp): fail closed.
    #   - FOREIGN_LIVE: another agent is actively working it; a foreign-owned
    #     DOING with observer STATE.task:none is VALID multi-agent state and
    #     routes NON-MUTATING (observe, do not take over).
    #   - SELF (this agent owns it): binding is mandatory; task:none fails.
    #   - UNCLAIMED / FOREIGN_STALE: adoptable orphan/stale DOING; task:none is
    #     fine and routes to ADOPT it.
    if active:
        cs = claim_status(board["tickets"][active], state.get("agent"), now)
        if cs == "INVALID":
            return {"ok": False, "action": "saipen status",
                    "reason": "binding-mismatch",
                    "detail": f"BOARD.DOING {active} carries an INVALID claim "
                              f"(half owner/claim_time pair or non-UTC stamp); "
                              f"repair the claim before routing"}
        if cs == "FOREIGN_LIVE":
            if task and task != "none":
                return {"ok": False, "action": "saipen status",
                        "reason": "binding-mismatch",
                        "detail": f"STATE.task={task} but BOARD.DOING={active} "
                                  f"is FOREIGN_LIVE (owned by another agent)"}
            return {"ok": True, "action": "saipen status",
                    "reason": "foreign-live",
                    "executable_behavior": "RESTATE_AND_STOP",
                    "detail": f"BOARD.DOING {active} is actively owned by "
                              f"another agent; observe, do not take over"}
        if task and task != "none" and task != active:
            return {"ok": False, "action": "saipen status",
                    "reason": "binding-mismatch",
                    "detail": f"STATE.task={task} but BOARD.DOING={active}; "
                              "repair the split before routing"}
        if cs == "SELF" and (not task or task == "none"):
            return {"ok": False, "action": "saipen status",
                    "reason": "binding-mismatch",
                    "detail": f"STATE.task is none but BOARD.DOING={active} is "
                              f"this agent's own SELF claim; bind STATE.task"}
        if cs in ("UNCLAIMED", "FOREIGN_STALE") and (not task or task == "none"):
            # Adoptable orphan/stale DOING: route to claim it in place.
            return {"ok": True, "action": f"PHASE SCOUT {active}",
                    "reason": "adopt", "ticket": active,
                    "detail": "DOING ticket carries no live own claim; adopt it",
                    "load": load_for_action(f"PHASE SCOUT {active}")}
    elif task and task != "none":
        return {"ok": False, "action": "saipen status",
                "reason": "binding-mismatch",
                "detail": f"STATE.task={task} but no BOARD.DOING ticket; "
                          "repair the split before routing"}

    # WAIT: a legitimate persisted WAIT is a HARD STOP (CORE 1.11 OBEY/UNBLOCK
    # priority). It must never be walked through merely because TODO has
    # workable tickets. The narrow exception is exactly CORE's: DONE + empty
    # TODO + a WAIT that is not one of the explicitly legal DONE brakes may
    # route onward -- a genuine user brake remains a stop with 100 workable
    # tickets.
    if na.startswith("WAIT:"):
        _empty_todo = not any(t["section"] == "## TODO"
                              for t in board["tickets"].values())
        _done_brakes = ("WAIT: blocked", "WAIT: user brake",
                        "WAIT: first-publish", "WAIT: manual-verify",
                        "WAIT: destructive-op")
        _not_done_brake = not na.startswith(_done_brakes)
        if not (phase == "DONE" and _empty_todo and _not_done_brake):
            return {"ok": True, "action": na, "reason": "wait",
                    "executable_behavior": "RESTATE_AND_STOP",
                    "detail": "persisted WAIT is a hard stop; do not route "
                              "past it"}

    # BLOCKED phase: a hard stop, whatever the board holds. UNBLOCK is a
    # routing-priority NAME (CORE 1.11), not necessarily a `ticket unblock`
    # command -- the router must not emit a mutation the executor refuses.
    if phase == "BLOCKED":
        return {"ok": True, "action": "saipen status",
                "reason": "unblock",
                "executable_behavior": "RESTATE_AND_STOP",
                "detail": "phase BLOCKED; resolve the blocker before any "
                          "further work (saipen sub list / status to inspect)"}

    # FINISH: phase in a ticket-bearing phase with an active ticket -> the
    # persisted next_action names the exact phase work; fall back to the
    # persisted value only when it is still a legal PHASE action for the
    # active ticket.
    if active and phase in phases.TICKET_BEARING_PHASES:
        if na.startswith("PHASE ") and task and task == active:
            return {"ok": True, "action": na, "reason": "finish",
                    "ticket": active, "load": load_for_action(na)}
        if na.startswith(("RUN:", "RESUME:")) and task == active:
            return {"ok": True, "action": na, "reason": "finish",
                    "ticket": active, "load": load_for_action(na)}
        return {"ok": True, "action": f"PHASE {phase} {active}",
                "reason": "finish", "ticket": active,
                "load": load_for_action(f"PHASE {phase} {active}")}

    # Crew is an outer convergence target. Once local ticket execution has no
    # immediate continuation, ordinary `cc` returns to crew orchestration from
    # persisted semantics rather than relying on a lucky next_action string.
    if (state.get("execution_intent") == "converge"
            and state.get("converge_target") == "crew"):
        return {"ok": True, "action": "saipen crew",
                "reason": "crew-converge",
                "detail": "active crew target owns continuation"}

    # START: no DOING + a workable TODO -> Pick Rule claims the top ticket.
    if not active:
        top = _top_workable(board, agent=state.get("agent"))
        if top is not None:
            return {"ok": True, "action": f"PHASE SCOUT {top}",
                    "reason": "start", "ticket": top,
                    "detail": "topmost workable ticket",
                    "load": load_for_action(f"PHASE SCOUT {top}")}

    # MAINTAIN: fall through to the persisted next_action only when it is a
    # legal non-ticket action (saipen continue / saipen <verb>), never a stale
    # PHASE echo and never a WAIT -- a WAIT reaching here already failed the
    # hard-stop gate above (the narrow DONE+empty-TODO exception), so it is a
    # stale WAIT to route past, not a brake to restate.
    if na.startswith("saipen ") or na.startswith("RUN:"):
        return {"ok": True, "action": na, "reason": "maintain"}
    return {"ok": True, "action": "saipen continue", "reason": "maintain",
            "detail": "no pending recovery, no active ticket, no workable "
                      "TODO; continue ordinary maintenance"}


ROUTING_FAILURE_CODES = {
    # Recovery conflicts/pending are recovery work: the project holds an
    # unresolved journal.
    "recovery-conflict": "RECOVERY_CONFLICT",
    "recovery-pending": "RECOVERY_REQUIRED",
    # Everything else is a malformed/binding failure: there is NO journal to
    # recover, so recovery_pending must be false and the refusal must be a
    # validation failure -- telling the agent to recover a non-existent op
    # would send it chasing ghosts (T-1003 hostile findings).
    "state-malformed": "VALIDATION_FAILED",
    "binding-mismatch": "VALIDATION_FAILED",
    "board-malformed": "VALIDATION_FAILED",
}


def routing_failure_code(out: dict) -> str:
    """The stable failure code for one route_next result."""
    return ROUTING_FAILURE_CODES.get(
        out.get("reason"), "VALIDATION_FAILED")


def route_next_result(project_root, state_text: str, board_text: str,
                      pending_ops_list: list | None = None,
                      conflict_ops_list: list | None = None) -> Result:
    """route_next wrapped in the stable Result shape for status/next/context."""
    out = route_next(state_text, board_text, pending_ops_list,
                      conflict_ops_list)
    data = {k: v for k, v in out.items() if k != "ok"}
    # Capability surface (hostile-regression, P0#5): a PHASE action names the
    # phase doc it will load (saipen/phases/<phase>.md). A missing or empty
    # phase doc is a bogus checkpoint -- surface it as a routing failure so the
    # agent never boots from a phase that has no contract to execute.
    action = out.get("action")
    if out.get("ok") and isinstance(action, str) and action.startswith("PHASE "):
        load = load_for_action(action)
        if load:
            load_path = Path(project_root) / load
            if not load_path.is_file() or load_path.stat().st_size == 0:
                return Result(
                    ok=False, code="VALIDATION_FAILED",
                    data={"action": action, "load": load,
                          "reason": "phase-doc-missing",
                          "detail": f"phase doc {load} is missing or empty"})
    return Result(ok=bool(out.get("ok")),
                  code=("ROUTED" if out.get("ok")
                        else routing_failure_code(out)),
                  data=data)


def load_for_action(action: str) -> str | None:
    """The phase doc the ROUTED action needs, derived from the action itself
    (NITRO dogfood III, T-591): `next.action` and `next.load` can never
    disagree. For a PHASE <X> [T-###] action the doc is phases/<x>.md; a
    recovery/command/WAIT action carries no phase doc (the command/routing
    owner governs instead).
    """
    if not action or not action.startswith("PHASE "):
        return None
    parts = action.split()
    if len(parts) < 2:
        return None
    phase = parts[1].lower()
    return f"saipen/phases/{phase}.md"

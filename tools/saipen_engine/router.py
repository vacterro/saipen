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

from . import phases
from .board import parse_board, ticket_is_workable
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
               execution_intent: str | None = None) -> dict:
    """Compute the exact next executable action.

    Returns a dict with `action` (an executable mechanical action), `reason`
    (which priority rule fired), and optional `ticket`/`detail`. Never echoes
    STATE.next_action -- it is a projection, not a mirror (NITRO dogfood II).
    """
    pending = list(pending_ops or [])
    conflicts = list(conflict_ops or [])
    state = parse_state(state_text)
    board = parse_board(board_text)
    phase = state.get("phase")
    task = state.get("task")
    na = state.get("next_action") or ""

    # RECOVER outranks everything: an unresolved op or conflict must be
    # resolved before any canonical work.
    if conflicts:
        return {"ok": False, "action": "saipen recover",
                "reason": "recovery-conflict",
                "detail": f"unresolved conflict: {', '.join(conflicts)}"}
    if pending:
        return {"ok": False, "action": "saipen recover",
                "reason": "recovery-pending",
                "detail": f"unresolved operation: {', '.join(pending)}"}

    # A board the shared parser cannot read whole (an unrecognized ticket
    # field, a malformed ticket line) is not a work surface: a typo'd
    # `| blockr:` is exactly how a blocker-bearing ticket launders itself
    # into workable, so malformed input is routed to inspection, never to a
    # ticket.
    if board["errors"]:
        return {"ok": True, "action": "saipen status",
                "reason": "board-malformed",
                "detail": "BOARD parse error(s): "
                          + "; ".join(board["errors"][:3])}

    doing = [t for t in board["tickets"].values()
             if t["section"] == "## DOING"]
    active = doing[0]["id"] if doing else None

    # BINDING: a STATE.task / BOARD.DOING split is structural corruption and
    # must be surfaced, never silently routed past (NITRO dogfood II).
    if active and task and task != active:
        return {"ok": False, "action": "saipen status",
                "reason": "binding-mismatch",
                "detail": f"STATE.task={task} but BOARD.DOING={active}; "
                          "repair the split before routing"}
    if task and task != "none" and not active:
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
                    "ticket": active}
        if na.startswith(("RUN:", "RESUME:")) and task == active:
            return {"ok": True, "action": na, "reason": "finish",
                    "ticket": active}
        return {"ok": True, "action": f"PHASE {phase} {active}",
                "reason": "finish", "ticket": active}

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
                    "detail": "topmost workable ticket"}

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


def route_next_result(project_root, state_text: str, board_text: str,
                      pending_ops_list: list | None = None,
                      conflict_ops_list: list | None = None) -> Result:
    """route_next wrapped in the stable Result shape for status/next/context."""
    out = route_next(state_text, board_text, pending_ops_list,
                     conflict_ops_list)
    data = {k: v for k, v in out.items() if k != "ok"}
    return Result(ok=bool(out.get("ok")),
                  code=("ROUTED" if out.get("ok") else "RECOVERY_CONFLICT"),
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

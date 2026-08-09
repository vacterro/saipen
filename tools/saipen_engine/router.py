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
from .board import parse_board
from .result import Result
from .state import parse_state


def _top_workable(board: dict) -> str | None:
    """Deterministic Pick Rule: topmost TODO ticket whose needs are all DONE."""
    tickets = board["tickets"]
    for ticket in tickets.values():
        if ticket["section"] != "## TODO":
            continue
        if all(need in tickets and tickets[need]["section"] == "## DONE"
               for need in ticket["needs"]):
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

    doing = [t for t in board["tickets"].values()
             if t["section"] == "## DOING"]
    active = doing[0]["id"] if doing else None
    blocker = state.get("blocker") or ""

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

    # UNBLOCK: an active ticket parked in BLOCKED (with a DOING ticket) or a
    # live blocker.
    if active and blocker and blocker.strip():
        return {"ok": True, "action": f"saipen unblock {active}",
                "reason": "unblock", "ticket": active}

    # FINISH: phase in a ticket-bearing phase with an active ticket -> the
    # persisted next_action names the exact phase work; fall back to the
    # persisted value only when it is still a legal PHASE action for the
    # active ticket.
    if active and phase in phases.TICKET_BEARING_PHASES:
        if na.startswith("PHASE ") and task and task == active:
            return {"ok": True, "action": na, "reason": "finish",
                    "ticket": active}
        return {"ok": True, "action": f"PHASE {phase} {active}",
                "reason": "finish", "ticket": active}

    # START: no DOING + a workable TODO -> Pick Rule claims the top ticket.
    if not active:
        top = _top_workable(board)
        if top is not None:
            return {"ok": True, "action": f"PHASE SCOUT {top}",
                    "reason": "start", "ticket": top,
                    "detail": "topmost workable ticket"}

    # MAINTAIN: fall through to the persisted next_action only when it is a
    # legal non-ticket action (saipen continue / saipen <verb>), never a stale
    # PHASE echo.
    if na.startswith("saipen ") or na.startswith("WAIT:"):
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

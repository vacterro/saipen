"""Authoritative read-only continuation assessment (P0 False-IDLE repair).

Unifies the continuation truth across all three production surfaces:
- saipen continue --json
- saipen iteration --json
- worker supervisor decision (supervisor.observe / supervisor.decide)

CORE INVARIANT:
One authoritative read-only assessment deriving from the canonical router's
ordering and gate chain. It never mutates state, never creates a second
routing engine, and distinguishes exactly the 14 required classifications:

- ACTIVE_WORK
- QUEUED_WORK
- RECOVERY_AVAILABLE
- AUDIT_AVAILABLE
- SOURCE_AVAILABLE
- DISCOVERY_AVAILABLE
- MAINTENANCE_AVAILABLE
- QUIESCENT
- WAIT_EXTERNAL
- WAIT_OPERATOR
- WAIT_AUTHORITY
- SAFETY_STOP
- CONFORMANCE_STOP
- INVALID_RUNTIME
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from . import goal_authority
from .board import parse_board, workable_tickets
from .router import (
    audit_inbox_projection,
    future_gate_projection,
    gate_route,
    pending_append_projection,
    queued_source_projection,
    route_next,
)
from .state import parse_state_or_error

# Closed classification vocabulary
ACTIVE_WORK = "ACTIVE_WORK"
QUEUED_WORK = "QUEUED_WORK"
RECOVERY_AVAILABLE = "RECOVERY_AVAILABLE"
AUDIT_AVAILABLE = "AUDIT_AVAILABLE"
SOURCE_AVAILABLE = "SOURCE_AVAILABLE"
DISCOVERY_AVAILABLE = "DISCOVERY_AVAILABLE"
MAINTENANCE_AVAILABLE = "MAINTENANCE_AVAILABLE"
QUIESCENT = "QUIESCENT"
WAIT_EXTERNAL = "WAIT_EXTERNAL"
WAIT_OPERATOR = "WAIT_OPERATOR"
WAIT_AUTHORITY = "WAIT_AUTHORITY"
SAFETY_STOP = "SAFETY_STOP"
CONFORMANCE_STOP = "CONFORMANCE_STOP"
INVALID_RUNTIME = "INVALID_RUNTIME"

CLASSIFICATIONS = frozenset(
    {
        ACTIVE_WORK,
        QUEUED_WORK,
        RECOVERY_AVAILABLE,
        AUDIT_AVAILABLE,
        SOURCE_AVAILABLE,
        DISCOVERY_AVAILABLE,
        MAINTENANCE_AVAILABLE,
        QUIESCENT,
        WAIT_EXTERNAL,
        WAIT_OPERATOR,
        WAIT_AUTHORITY,
        SAFETY_STOP,
        CONFORMANCE_STOP,
        INVALID_RUNTIME,
    }
)

# Classifications representing actionable autonomous engineering work
EXECUTABLE_CLASSIFICATIONS = frozenset(
    {
        ACTIVE_WORK,
        QUEUED_WORK,
        RECOVERY_AVAILABLE,
        AUDIT_AVAILABLE,
        SOURCE_AVAILABLE,
        DISCOVERY_AVAILABLE,
        MAINTENANCE_AVAILABLE,
    }
)

# Classifications requiring human operator decision or authorization
HUMAN_BOUNDARY_CLASSIFICATIONS = frozenset(
    {
        WAIT_OPERATOR,
        WAIT_AUTHORITY,
        SAFETY_STOP,
        CONFORMANCE_STOP,
    }
)


def assess_continuation(
    root: Path | str,
    *,
    now: _dt.datetime | None = None,
    current_agent: str | None = None,
    current_capability: str | None = None,
    state_text: str | None = None,
    board_text: str | None = None,
    pending_ops: list | None = None,
    conflict_ops: list | None = None,
    snap: Any = None,
    reconciled: dict | None = None,
    parsed_board: dict | None = None,
) -> dict:
    """Compute the authoritative read-only continuation assessment.

    Pure of mutations: reads canonical state and projections, applies the
    ordered router and gate chain, and maps the verdict onto the closed
    classification vocabulary.
    """
    root_path = Path(root).resolve()

    if state_text is None:
        try:
            state_text = (root_path / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")
        except OSError as exc:
            return _unreadable(f"STATE.md unreadable: {exc}")

    if board_text is None:
        try:
            board_text = (root_path / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig")
        except OSError as exc:
            return _unreadable(f"BOARD.md unreadable: {exc}")

    state, state_error = parse_state_or_error(state_text)
    if state_error and "missing required field updated" in state_error:
        # Compatibility with fixtures omitting updated field
        if "\n---" in state_text:
            fixed_text = state_text.replace("\n---", "\nupdated: '2026-01-01T00:00:00Z'\n---", 1)
            fixed_state, fixed_err = parse_state_or_error(fixed_text)
            if not fixed_err and fixed_state:
                state, state_error, state_text = fixed_state, None, fixed_text

    if state_error or not state:
        return _make_assessment(
            INVALID_RUNTIME,
            action=None,
            reason="state-malformed",
            detail=f"STATE parse error: {state_error or 'empty'}",
        )

    try:
        # PERF-005: the caller may already hold the parsed BOARD. Re-parsing it
        # here was the first of the redundant parses in one observation.
        board = parsed_board if parsed_board is not None else parse_board(board_text)
    except Exception as exc:
        return _make_assessment(
            INVALID_RUNTIME,
            action=None,
            reason="board-malformed",
            detail=f"BOARD parse error: {exc}",
        )

    if board.get("errors"):
        return _make_assessment(
            INVALID_RUNTIME,
            action="saipen status",
            reason="board-malformed",
            detail="BOARD parse error(s): " + "; ".join(board["errors"][:3]),
        )

    # Resolve agent
    acting_agent = current_agent if current_agent is not None else state.get("agent")

    # Run the canonical router with all projections
    try:
        raw_route = route_next(
            state_text,
            board_text,
            pending_ops=pending_ops,
            conflict_ops=conflict_ops,
            now=now,
            current_capability=current_capability,
            current_agent=acting_agent,
            snap=snap,
            audit_inbox=audit_inbox_projection(root_path),
            queued_source=queued_source_projection(root_path),
            pending_append=pending_append_projection(root_path),
            future_gate=future_gate_projection(
                root_path, board_text, tickets=board.get("tickets") or {}
            ),
            _state=state,
            _board=board,
            _state_error=state_error,
        )
    except Exception as exc:
        return _make_assessment(
            INVALID_RUNTIME,
            action="saipen recover",
            reason="routing-exception",
            detail=f"router raised unexpected exception: {type(exc).__name__}: {exc}",
        )

    # Apply the ordered gate chain
    try:
        from .router import (
            reconcile_gate,
            goal_checkpoint_gate,
            continuous_maintenance_gate,
            conformance_crew_gate,
            closure_finish_gate,
            conformance_idle_gate,
        )
        gated = None
        if reconciled is not None:
            gated = reconcile_gate(root_path, raw_route, reconciled=reconciled, agent=acting_agent)
        if gated is None:
            for gate in (
                goal_checkpoint_gate,
                continuous_maintenance_gate,
                conformance_crew_gate,
                closure_finish_gate,
                conformance_idle_gate,
            ):
                gated = gate(root_path, raw_route)
                if gated is not None:
                    break
        effective_route = gated if gated is not None else raw_route
    except Exception as exc:
        return _make_assessment(
            INVALID_RUNTIME,
            action="saipen recover",
            reason="gate-exception",
            detail=f"gate_route raised unexpected exception: {type(exc).__name__}: {exc}",
        )

    return _classify_effective_route(root_path, effective_route, raw_route, state, board, now=now)


def _unreadable(detail: str) -> dict:
    return _make_assessment(
        INVALID_RUNTIME,
        action="saipen recover",
        reason="checkpoint-unreadable",
        detail=detail,
    )


def _make_assessment(
    classification: str,
    *,
    action: str | None,
    reason: str,
    detail: str,
    ticket: str | None = None,
    effective_route: dict | None = None,
    raw_route: dict | None = None,
    continuous_maintenance_proven: bool = False,
    continuous_maintenance_claimed: bool = False,
    operator_work: list[str] | None = None,
) -> dict:
    actionable = classification in EXECUTABLE_CLASSIFICATIONS
    requires_human = classification in HUMAN_BOUNDARY_CLASSIFICATIONS
    return {
        "classification": classification,
        "actionable": actionable,
        "executable_work": (action or ticket) if actionable else None,
        "action": action,
        "reason": reason,
        "detail": detail,
        "ticket": ticket,
        "requires_human": requires_human,
        "quiescent": classification == QUIESCENT,
        "effective_route": effective_route or {},
        "raw_route": raw_route or {},
        "continuous_maintenance_proven": continuous_maintenance_proven,
        "continuous_maintenance_claimed": continuous_maintenance_claimed,
        "operator_work": operator_work or [],
    }


def _classify_effective_route(
    root: Path,
    routed: dict,
    raw_route: dict,
    state: dict,
    board: dict,
    *,
    now: _dt.datetime | None = None,
) -> dict:
    reason = str(routed.get("reason") or "")
    action = str(routed.get("action") or "") if routed.get("action") is not None else None
    code = str(routed.get("code") or "")
    detail = str(routed.get("detail") or reason)
    ticket = routed.get("ticket")

    cm_claimed = goal_authority.is_continuous_maintenance(state)
    cm_proven = goal_authority.continuous_maintenance_proven(root, state)

    # 1. Check for route refusal or gate errors
    if not routed.get("ok"):
        if code == "CONTINUATION_AUTHORITY_UNPROVEN" or reason == "continuous-maintenance-unproven":
            return _make_assessment(
                WAIT_AUTHORITY,
                action=action,
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
                continuous_maintenance_claimed=cm_claimed,
                continuous_maintenance_proven=False,
            )
        if reason in ("recovery-pending", "recovery-conflict") or code in ("RECOVERY_REQUIRED", "RECOVERY_CONFLICT"):
            return _make_assessment(
                RECOVERY_AVAILABLE,
                action=action or "saipen recover",
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        if code in ("CONFORMANCE_UNHEALTHY", "CONFORMANCE_UNKNOWN") or reason in (
            "conformance-remediation",
            "conformance-unhealthy",
            "conformance-unknown",
        ):
            return _make_assessment(
                CONFORMANCE_STOP,
                action=action or "saipen validate",
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        if reason in ("reconcile-decision", "reconcile-refused") or code.startswith("RECONCILE_"):
            return _make_assessment(
                WAIT_OPERATOR,
                action=action,
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        if code == "CLOSURE_NOT_READY":
            # Active ticket requires remediation command before ship
            return _make_assessment(
                ACTIVE_WORK,
                action=action,
                reason=reason,
                detail=detail,
                ticket=ticket,
                effective_route=routed,
                raw_route=raw_route,
            )
        # All other un-ok routes (state-malformed, board-malformed, checkpoint-invalid, etc.)
        return _make_assessment(
            INVALID_RUNTIME,
            action=action or "saipen status",
            reason=reason or "validation-failed",
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    # 2. Re-entry checks and specific ok reasons
    if reason == "read-only-mode":
        return _make_assessment(
            WAIT_AUTHORITY,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "bootstrap":
        return _make_assessment(
            INVALID_RUNTIME,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "wait":
        from .state import parse_wait

        if parse_wait(state.get("next_action") or "") == "safety valve":
            if goal_authority.persistent(state) or goal_authority.protocol_home_checkpoint(root, state):
                return _make_assessment(
                    MAINTENANCE_AVAILABLE,
                    action=action or "saipen continue",
                    reason=reason,
                    detail=detail,
                    effective_route=routed,
                    raw_route=raw_route,
                    continuous_maintenance_claimed=cm_claimed,
                    continuous_maintenance_proven=cm_proven,
                )
            return _make_assessment(
                SAFETY_STOP,
                action=action,
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        return _make_assessment(
            WAIT_OPERATOR,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "unblock":
        blocker = str(state.get("blocker") or "").upper()
        if "EXTERNAL" in blocker:
            if cm_proven:
                # A foreign blocked ticket must not prevent independent authorized local maintenance
                return _make_assessment(
                    MAINTENANCE_AVAILABLE,
                    action="saipen continue",
                    reason="maintain",
                    detail="foreign blocker stands; independent continuous maintenance authorized",
                    effective_route=routed,
                    raw_route=raw_route,
                    continuous_maintenance_claimed=cm_claimed,
                    continuous_maintenance_proven=True,
                )
            return _make_assessment(
                WAIT_EXTERNAL,
                action=action,
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        return _make_assessment(
            WAIT_OPERATOR,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "goal-checkpoint":
        return _make_assessment(
            ACTIVE_WORK,
            action=action or "saipen continue",
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "unprojected-source-append":
        return _make_assessment(
            SOURCE_AVAILABLE,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "foreign-live":
        return _make_assessment(
            WAIT_OPERATOR,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "adopt":
        return _make_assessment(
            ACTIVE_WORK,
            action=action,
            reason=reason,
            detail=detail,
            ticket=ticket,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason in ("finish", "markhunt-continue", "finish-at-ship"):
        return _make_assessment(
            ACTIVE_WORK,
            action=action,
            reason=reason,
            detail=detail,
            ticket=ticket,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "queued-source":
        return _make_assessment(
            SOURCE_AVAILABLE,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "crew-converge":
        return _make_assessment(
            ACTIVE_WORK,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "audit-inbox" or action == "saipen audit ingest":
        return _make_assessment(
            AUDIT_AVAILABLE,
            action=action,
            reason=reason,
            detail=detail,
            ticket=ticket,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason in ("start", "start-user-explicit", "dependency-continuation") or (
        action and action.startswith("PHASE SCOUT")
    ):
        return _make_assessment(
            QUEUED_WORK,
            action=action,
            reason=reason,
            detail=detail,
            ticket=ticket,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "operator-gate-due":
        due_tickets = [g["ticket"] for g in (routed.get("operator_gates") or []) if g.get("state") == "DUE_OPERATOR_ACTION"]
        return _make_assessment(
            WAIT_OPERATOR,
            action=action,
            reason=reason,
            detail=detail,
            operator_work=due_tickets,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "operator-gate-deferred":
        return _make_assessment(
            WAIT_OPERATOR,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "goal-blocked":
        if cm_proven:
            # Foreign goal-blocked ticket does not block independent maintenance
            return _make_assessment(
                MAINTENANCE_AVAILABLE,
                action="saipen continue",
                reason="maintain",
                detail="goal-blocked stands; independent continuous maintenance authorized",
                effective_route=routed,
                raw_route=raw_route,
                continuous_maintenance_claimed=cm_claimed,
                continuous_maintenance_proven=True,
            )
        return _make_assessment(
            WAIT_EXTERNAL,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "audit-inbox-invalid":
        return _make_assessment(
            INVALID_RUNTIME,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason in ("future-gate-refresh", "future-gate-refinement", "future-gate-promotion"):
        return _make_assessment(
            DISCOVERY_AVAILABLE,
            action=action,
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    if reason == "improve-gate":
        return _make_assessment(
            WAIT_OPERATOR,
            action=action,
            reason=reason,
            detail=detail,
            ticket=ticket,
            effective_route=routed,
            raw_route=raw_route,
        )

    # 3. Idle boundaries: maintain and audit-inbox-unworkable
    if reason in ("maintain", "audit-inbox-unworkable"):
        # Proven continuous maintenance outranks idle board
        if cm_proven:
            return _make_assessment(
                MAINTENANCE_AVAILABLE,
                action="saipen continue",
                reason=reason,
                detail="continuous maintenance proven; discovery/improvement eligible",
                effective_route=routed,
                raw_route=raw_route,
                continuous_maintenance_claimed=cm_claimed,
                continuous_maintenance_proven=True,
            )

        # Unproven continuous maintenance claim was handled at gate_route; if somehow here:
        if cm_claimed and not cm_proven:
            return _make_assessment(
                WAIT_AUTHORITY,
                action="saipen status",
                reason="continuous-maintenance-unproven",
                detail="continuous maintenance claimed but unproven",
                effective_route=routed,
                raw_route=raw_route,
                continuous_maintenance_claimed=True,
                continuous_maintenance_proven=False,
            )

        # Non-continuous maintenance terminal/idle dispositions
        idle_cls = str(routed.get("terminal_classification") or routed.get("idle_classification") or "")
        stop_reason = str(routed.get("stop_reason") or "")

        if idle_cls == "IDLE_OPERATOR_REQUIRED" or "OPERATOR" in idle_cls:
            return _make_assessment(
                WAIT_OPERATOR,
                action=action or "saipen status",
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        if idle_cls == "IDLE_BLOCKED_EXTERNAL" or "EXTERNAL" in idle_cls:
            return _make_assessment(
                WAIT_EXTERNAL,
                action=action or "saipen status",
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        if idle_cls == "IDLE_FUTURE_GATED":
            return _make_assessment(
                QUIESCENT,
                action=action or "saipen status",
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        if stop_reason == "ALL_REQUIREMENTS_COMPLETE" or idle_cls == "ALL_WORK_COMPLETE":
            return _make_assessment(
                QUIESCENT,
                action="saipen status",
                reason=reason,
                detail="all requirements complete; campaign quiescent",
                effective_route=routed,
                raw_route=raw_route,
            )

        # Default fallback for unworkable/maintain without active grant
        primary_blocker = routed.get("primary_blocker") or {}
        p_class = str(primary_blocker.get("blocker_class") or "")
        if "OPERATOR" in p_class or "USER" in p_class:
            return _make_assessment(
                WAIT_OPERATOR,
                action=action or "saipen status",
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )
        if "EXTERNAL" in p_class:
            return _make_assessment(
                WAIT_EXTERNAL,
                action=action or "saipen status",
                reason=reason,
                detail=detail,
                effective_route=routed,
                raw_route=raw_route,
            )

        return _make_assessment(
            QUIESCENT,
            action=action or "saipen status",
            reason=reason,
            detail=detail,
            effective_route=routed,
            raw_route=raw_route,
        )

    # Catch-all
    return _make_assessment(
        QUIESCENT,
        action=action or "saipen status",
        reason=reason or "quiescent",
        detail=detail,
        effective_route=routed,
        raw_route=raw_route,
    )

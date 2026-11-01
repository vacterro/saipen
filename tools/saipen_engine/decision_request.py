"""Canonical Human Decision Request Model & Authority Guard (SRC-257 / T-1797).

Enforces strict human decision boundaries (Phase 5 of SAIHANDOFF 20261014_2009):
- Human decisions are requested ONLY when genuinely required (new authority, STOP reversal,
  dependency override, real hardware interaction, destructive actions, missing provenance).
- Never silently interprets `cc all` or `cc` as unlimited authority to override operator stops.
- Never treats agent-written prose as authenticated operator authorization.
- Emits ONE minimal structured decision request containing:
  - blocked_operation
  - existing_authority
  - missing_authorization
  - consequences_approval
  - consequences_refusal
  - safe_default
  - recording_mechanism
"""

from __future__ import annotations

from typing import Any

REQUIRED_DECISION_FIELDS = (
    "blocked_operation",
    "existing_authority",
    "missing_authorization",
    "consequences_approval",
    "consequences_refusal",
    "safe_default",
    "recording_mechanism",
)


def create_decision_request(
    blocked_operation: str,
    existing_authority: str | dict[str, Any],
    missing_authorization: str,
    consequences_approval: str,
    consequences_refusal: str,
    safe_default: str,
    recording_mechanism: str,
) -> dict[str, Any]:
    """Create a validated canonical human decision request."""
    auth_str = (
        str(existing_authority)
        if not isinstance(existing_authority, dict)
        else f"source={existing_authority.get('authority_source', 'none')} "
        f"scope={existing_authority.get('continuation_authority', 'none')} "
        f"intent={existing_authority.get('execution_intent', 'none')}"
    )

    request = {
        "blocked_operation": str(blocked_operation).strip(),
        "existing_authority": auth_str.strip(),
        "missing_authorization": str(missing_authorization).strip(),
        "consequences_approval": str(consequences_approval).strip(),
        "consequences_refusal": str(consequences_refusal).strip(),
        "safe_default": str(safe_default).strip(),
        "recording_mechanism": str(recording_mechanism).strip(),
    }
    errors = validate_decision_request(request)
    if errors:
        raise ValueError(f"Invalid decision request: {'; '.join(errors)}")
    return request


def validate_decision_request(request: dict[str, Any]) -> list[str]:
    """Validate completeness and non-emptiness of all decision request fields."""
    errors = []
    if not isinstance(request, dict):
        return ["decision request must be a dictionary"]
    for field_name in REQUIRED_DECISION_FIELDS:
        val = request.get(field_name)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"field '{field_name}' must be a non-empty string")
    return errors


def format_decision_request(request: dict[str, Any]) -> str:
    """Format a canonical human decision request for CLI and status output."""
    errors = validate_decision_request(request)
    if errors:
        return f"INVALID_DECISION_REQUEST: {'; '.join(errors)}"
    return (
        "=== OPERATOR DECISION REQUIRED ===\n"
        f"Blocked Operation     : {request['blocked_operation']}\n"
        f"Existing Authority    : {request['existing_authority']}\n"
        f"Missing Authorization : {request['missing_authorization']}\n"
        f"Consequences Approval : {request['consequences_approval']}\n"
        f"Consequences Refusal  : {request['consequences_refusal']}\n"
        f"Safe Default          : {request['safe_default']}\n"
        f"Recording Mechanism   : {request['recording_mechanism']}\n"
        "=================================="
    )




def create_isolated_release_decision_request(
    *,
    action: str,
    reviewed_scope: list[str] | dict[str, Any],
    target_destination: str,
    paths_changed: list[str],
    paths_protected: list[str] | str,
    expected_side_effects: str,
    rollback: str,
    reason_insufficient: str,
    existing_authority: str | dict[str, Any] = "operator_required",
    recording_mechanism: str = "saipen authority capture <signed-operator-capsule>",
) -> dict[str, Any]:
    """Create a structured isolated release decision request covering Section 4 requirements."""
    scope_summary = ", ".join(sorted(reviewed_scope)) if isinstance(reviewed_scope, (list, set)) else str(reviewed_scope)
    changed_summary = ", ".join(sorted(paths_changed))
    protected_summary = (
        f"{len(paths_protected)} staged paths"
        if isinstance(paths_protected, (list, set))
        else str(paths_protected)
    )
    req = {
        "action": str(action).strip(),
        "reviewed_scope": scope_summary,
        "target_destination": str(target_destination).strip(),
        "paths_changed": changed_summary,
        "paths_protected": protected_summary,
        "expected_side_effects": str(expected_side_effects).strip(),
        "rollback": str(rollback).strip(),
        "reason_insufficient": str(reason_insufficient).strip(),
    }
    req.update(
        create_decision_request(
            blocked_operation=f"{action} (target={target_destination})",
            existing_authority=existing_authority,
            missing_authorization=reason_insufficient,
            consequences_approval=f"Execute {action} isolated to {target_destination}; {protected_summary} protected",
            consequences_refusal="Publication remains blocked; foreign staging remains protected",
            safe_default="Preserve existing live index and foreign staging without mutating repository",
            recording_mechanism=recording_mechanism,
        )
    )
    return req

def validate_authority_escalation(
    proposed_reason: str,
    acting_agent: str,
    carrier_witness: str | None = None,
    *,
    provenance: object = None,
    root=None,
    receipt: str | None = None,
) -> tuple[bool, str]:
    """Guard against agent-authored authority escalation (Phase 1 / Phase 5).

    Rejects claims that bare 'cc' or 'cc all' supersedes an operator pause
    or stop, or that unrelated directives grant authority, when not backed
    by genuine operator_carrier provenance.
    """
    reason_lower = proposed_reason.lower()
    is_supersession_claim = (
        "superseded" in reason_lower
        or "unblock" in reason_lower
        or "paused" in reason_lower
        or "override" in reason_lower
    )
    is_continuation_or_unrelated = (
        "cc all" in reason_lower
        or "operator directive superseded: cc" in reason_lower
        or "unrelated" in reason_lower
        or "earlier" in reason_lower
    )

    if is_supersession_claim and is_continuation_or_unrelated:
        from .operator_task import authority_for_provenance

        if not authority_for_provenance(
            provenance, root=root, receipt=receipt, existing_only=True,
        )[
            "preempt_active_work"
        ]:
            return (
                False,
                "AUTHORITY_ESCALATION_REFUSED: bare continuation or unrelated directives "
                "cannot supersede operator pauses without authenticated operator_carrier directive",
            )
    return True, "AUTHORIZED"

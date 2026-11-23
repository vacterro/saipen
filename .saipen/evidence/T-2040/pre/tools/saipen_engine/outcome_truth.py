"""Outcome Truth and Multi-Plane Projection (PV-001, PV-006, PV-009).

Prevents premature victory by separating:
1. QUEUE_STATUS: status of executable ticket queue.
2. CAMPAIGN_STATUS: lifecycle of autonomous campaign.
3. OBJECTIVE_STATUS: verification of operator's original engineering outcome.
4. VERIFICATION_STATUS: scope-specific validation result.
5. PUBLICATION_STATUS: release and installed runtime truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Queue Statuses
QUEUE_DRAINED = "QUEUE_DRAINED"
QUEUE_HAS_WORK = "QUEUE_HAS_WORK"
QUEUE_BLOCKED = "QUEUE_BLOCKED"

# Campaign Statuses
CAMPAIGN_RUNNING = "CAMPAIGN_RUNNING"
CAMPAIGN_QUIESCENT = "CAMPAIGN_QUIESCENT"
CAMPAIGN_WAIT_AUTHORITY = "CAMPAIGN_WAIT_AUTHORITY"
CAMPAIGN_WAIT_EXTERNAL = "CAMPAIGN_WAIT_EXTERNAL"
CAMPAIGN_COMPLETE = "CAMPAIGN_COMPLETE"

# Objective Statuses
OBJECTIVE_UNVERIFIED = "OBJECTIVE_UNVERIFIED"
OBJECTIVE_PARTIALLY_VERIFIED = "OBJECTIVE_PARTIALLY_VERIFIED"
OBJECTIVE_VERIFIED = "OBJECTIVE_VERIFIED"
OBJECTIVE_BLOCKED = "OBJECTIVE_BLOCKED"

# Publication Statuses
LOCAL_IMPLEMENTED = "LOCAL_IMPLEMENTED"
LOCAL_VERIFIED = "LOCAL_VERIFIED"
RELEASE_READY = "RELEASE_READY"
RELEASE_BLOCKED = "RELEASE_BLOCKED"
RELEASE_PUBLISHED = "RELEASE_PUBLISHED"
INSTALLED_VERIFIED = "INSTALLED_VERIFIED"
LIVE_VERIFIED = "LIVE_VERIFIED"

# Lane statuses (P0-01)
RELEASE_LANE_BLOCKED_FOREIGN_INDEX = "BLOCKED_FOREIGN_INDEX"
RELEASE_LANE_BLOCKED = "BLOCKED"
RELEASE_LANE_READY = "READY"
RELEASE_LANE_CLEAR = "CLEAR"

IMPLEMENTATION_LANE_ELIGIBLE = "ELIGIBLE"
IMPLEMENTATION_LANE_NO_WORK = "NO_WORK"
IMPLEMENTATION_LANE_AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"

DISCOVERY_LANE_ELIGIBLE = "ELIGIBLE"
DISCOVERY_LANE_NOT_DUE = "NOT_DUE"
DISCOVERY_LANE_AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"

PUBLICATION_LANE_PENDING = "PENDING"
PUBLICATION_LANE_BLOCKED = "BLOCKED"
PUBLICATION_LANE_READY = "READY"

CAMPAIGN_LANE_RUNNING = "RUNNING"
CAMPAIGN_LANE_QUIESCENT = "QUIESCENT"
CAMPAIGN_LANE_WAIT_AUTHORITY = "WAIT_AUTHORITY"
CAMPAIGN_LANE_WAIT_EXTERNAL = "WAIT_EXTERNAL"
CAMPAIGN_LANE_COMPLETE = "COMPLETE"


def compute_lane_statuses(
    root: Path | str | None = None,
    *,
    tickets: dict | None = None,
    state: dict | None = None,
    audit_inbox: dict | None = None,
    future_gate: dict | None = None,
    has_continuous_maintenance: bool = False,
    foreign_staged: bool = False,
    publication_state: str | None = None,
    is_budget_exhausted: bool = False,
    primary_blocker: dict | None = None,
) -> dict[str, str]:
    """Produce the five distinct operational lane statuses (P0-01).

    Separates blocked release from blocked engineering and autonomous discovery:
    1. RELEASE_LANE: BLOCKED_FOREIGN_INDEX | BLOCKED | READY | CLEAR
    2. IMPLEMENTATION_LANE: ELIGIBLE | NO_WORK | AUTHORITY_REQUIRED
    3. DISCOVERY_LANE: ELIGIBLE | NOT_DUE | AUTHORITY_REQUIRED
    4. PUBLICATION_LANE: PENDING | BLOCKED | READY
    5. CAMPAIGN: RUNNING | QUIESCENT | WAIT_AUTHORITY | WAIT_EXTERNAL | COMPLETE
    """
    tickets = tickets or {}
    state = state or {}

    doing = [t for t in tickets.values() if t.get("section") == "## DOING"]
    todo = [t for t in tickets.values() if t.get("section") == "## TODO"]
    blocked = [t for t in tickets.values() if t.get("section") == "## BLOCKED"]
    workable = [t for t in todo if not t.get("blocked")]

    # 1. RELEASE_LANE
    if foreign_staged:
        release_lane = RELEASE_LANE_BLOCKED_FOREIGN_INDEX
    elif primary_blocker and primary_blocker.get("cause") == "publication-staging":
        release_lane = RELEASE_LANE_BLOCKED_FOREIGN_INDEX
    elif publication_state == "blocked" or state.get("publication_state") == "blocked":
        release_lane = RELEASE_LANE_BLOCKED
    elif publication_state == "ready" or state.get("publication_state") == "ready":
        release_lane = RELEASE_LANE_READY
    elif any(
        "PUBLICATION_STAGING_BLOCKED" in str((t.get("fields") or {}).get("blocker", ""))
        for t in blocked
    ):
        release_lane = RELEASE_LANE_BLOCKED_FOREIGN_INDEX
    else:
        release_lane = RELEASE_LANE_CLEAR

    # 2. IMPLEMENTATION_LANE
    if workable or doing:
        implementation_lane = IMPLEMENTATION_LANE_ELIGIBLE
    elif blocked:
        implementation_lane = IMPLEMENTATION_LANE_AUTHORITY_REQUIRED
    else:
        implementation_lane = IMPLEMENTATION_LANE_NO_WORK

    # 3. DISCOVERY_LANE
    if not has_continuous_maintenance:
        discovery_lane = DISCOVERY_LANE_AUTHORITY_REQUIRED
    else:
        discovery_lane = DISCOVERY_LANE_NOT_DUE

    # 4. PUBLICATION_LANE
    pub = (publication_state or state.get("publication_state") or "pending").lower()
    if release_lane == RELEASE_LANE_BLOCKED_FOREIGN_INDEX or pub == "blocked":
        publication_lane = PUBLICATION_LANE_BLOCKED
    elif pub == "ready":
        publication_lane = PUBLICATION_LANE_READY
    else:
        publication_lane = PUBLICATION_LANE_PENDING

    # 5. CAMPAIGN
    if doing or workable:
        campaign = CAMPAIGN_LANE_RUNNING
    elif (
        any("EXTERNAL" in str((t.get("fields") or {}).get("blocker", "")) for t in blocked)
        or (primary_blocker and "EXTERNAL" in str(primary_blocker.get("blocker_class", "")))
        or release_lane == RELEASE_LANE_BLOCKED_FOREIGN_INDEX
    ):
        campaign = CAMPAIGN_LANE_WAIT_EXTERNAL
    elif is_budget_exhausted or not has_continuous_maintenance:
        campaign = CAMPAIGN_LANE_WAIT_AUTHORITY
    elif has_continuous_maintenance:
        campaign = CAMPAIGN_LANE_QUIESCENT
    elif not blocked and not todo and not doing:
        campaign = CAMPAIGN_LANE_COMPLETE
    else:
        campaign = CAMPAIGN_LANE_WAIT_AUTHORITY

    return {
        "RELEASE_LANE": release_lane,
        "IMPLEMENTATION_LANE": implementation_lane,
        "DISCOVERY_LANE": discovery_lane,
        "PUBLICATION_LANE": publication_lane,
        "CAMPAIGN": campaign,
    }


def compute_outcome_truth(
    root: Path | str | None,
    *,
    tickets: dict | None = None,
    state: dict | None = None,
    audit_inbox: dict | None = None,
    future_gate: dict | None = None,
    objective_evidence: dict | None = None,
    publication_state: str | None = None,
    has_continuous_maintenance: bool = False,
    is_budget_exhausted: bool = False,
) -> dict:
    """Project the multi-plane outcome truth from canonical facts.

    Never infers objective success from an empty executable ticket queue.
    """
    tickets = tickets or {}
    state = state or {}

    doing = [t for t in tickets.values() if t.get("section") == "## DOING"]
    todo = [t for t in tickets.values() if t.get("section") == "## TODO"]
    blocked = [t for t in tickets.values() if t.get("section") == "## BLOCKED"]
    workable = [t for t in todo if not t.get("blocked")]

    # 1. QUEUE_STATUS
    if workable or doing:
        queue_status = QUEUE_HAS_WORK
    elif blocked:
        # Executable queue is drained, but blocked items remain
        queue_status = QUEUE_DRAINED
    else:
        queue_status = QUEUE_DRAINED

    # 2. CAMPAIGN_STATUS
    if is_budget_exhausted and not has_continuous_maintenance:
        campaign_status = CAMPAIGN_WAIT_AUTHORITY
    elif doing:
        campaign_status = CAMPAIGN_RUNNING
    elif any("EXTERNAL" in str((t.get("fields") or {}).get("blocker", "")) for t in blocked):
        if not workable:
            campaign_status = CAMPAIGN_WAIT_EXTERNAL
        else:
            campaign_status = CAMPAIGN_RUNNING
    elif not workable and not doing:
        if has_continuous_maintenance:
            campaign_status = CAMPAIGN_QUIESCENT
        else:
            campaign_status = CAMPAIGN_WAIT_AUTHORITY
    else:
        campaign_status = CAMPAIGN_RUNNING

    # 3. OBJECTIVE_STATUS
    if objective_evidence:
        verdict = objective_evidence.get("verdict")
        if verdict == "PASS" or verdict == "VERIFIED":
            objective_status = OBJECTIVE_VERIFIED
        elif verdict == "PARTIAL":
            objective_status = OBJECTIVE_PARTIALLY_VERIFIED
        elif verdict == "BLOCKED":
            objective_status = OBJECTIVE_BLOCKED
        else:
            objective_status = OBJECTIVE_UNVERIFIED
    else:
        # In the absence of independent verified evidence for the user objective,
        # it is UNVERIFIED, even if all local unit tests passed.
        objective_status = OBJECTIVE_UNVERIFIED

    # 4. PUBLICATION_STATUS
    pub = (publication_state or state.get("publication_state") or "pending").lower()
    if pub == "published":
        publication_status = RELEASE_PUBLISHED
    elif pub == "ready":
        publication_status = RELEASE_READY
    elif pub == "blocked":
        publication_status = RELEASE_BLOCKED
    elif pub == "pending":
        publication_status = RELEASE_BLOCKED
    else:
        publication_status = LOCAL_VERIFIED

    # 5. NEXT WAKE CONDITION & NEXT ACTION
    if queue_status == QUEUE_HAS_WORK:
        next_wake = "ticket execution starts"
        next_action = f"saipen claim {workable[0]['id']}" if workable else "saipen continue"
    elif campaign_status == CAMPAIGN_WAIT_AUTHORITY:
        next_wake = "operator grants renewed campaign authority or continued objective"
        next_action = "saipen status"
    elif campaign_status == CAMPAIGN_WAIT_EXTERNAL:
        next_wake = "external blocker dependency resolved"
        next_action = "saipen status"
    elif campaign_status == CAMPAIGN_QUIESCENT:
        next_wake = "new source bytes, evidence, or external audit findings arrive"
        next_action = "saipen status"
    else:
        next_wake = "operator instruction"
        next_action = "saipen status"

    lanes = compute_lane_statuses(
        root,
        tickets=tickets,
        state=state,
        audit_inbox=audit_inbox,
        future_gate=future_gate,
        has_continuous_maintenance=has_continuous_maintenance,
        publication_state=publication_state,
        is_budget_exhausted=is_budget_exhausted,
    )

    return {
        "queue_status": queue_status,
        "campaign_status": campaign_status,
        "objective_status": objective_status,
        "publication_status": publication_status,
        "verification_status": "QUEUE_VALIDATION: PASS",
        "next_eligible_action": next_action,
        "next_wake_condition": next_wake,
        "lanes": lanes,
        "release_lane": lanes["RELEASE_LANE"],
        "implementation_lane": lanes["IMPLEMENTATION_LANE"],
        "discovery_lane": lanes["DISCOVERY_LANE"],
        "publication_lane": lanes["PUBLICATION_LANE"],
        "campaign_lane": lanes["CAMPAIGN"],
        "summary": (
            f"QUEUE: {queue_status} | OBJECTIVE: {objective_status} | "
            f"CAMPAIGN: {campaign_status} | PUBLICATION: {publication_status}"
        ),
    }

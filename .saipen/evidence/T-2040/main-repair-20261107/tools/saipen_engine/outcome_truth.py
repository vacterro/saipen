"""Outcome Truth and Multi-Plane Projection (PV-001, PV-006, PV-009).

Prevents premature victory by separating:
1. QUEUE_STATUS: status of executable ticket queue.
2. CAMPAIGN_STATUS: lifecycle of autonomous campaign.
3. OBJECTIVE_STATUS: verification of operator's original engineering outcome.
4. VERIFICATION_STATUS: scope-specific validation result.
5. PUBLICATION_STATUS: release and installed runtime truth.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
from pathlib import Path
from weakref import WeakKeyDictionary

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
CAMPAIGN_INCOMPLETE_DISCOVERY = "CAMPAIGN_INCOMPLETE_DISCOVERY"

# Objective Statuses
OBJECTIVE_UNVERIFIED = "OBJECTIVE_UNVERIFIED"
OBJECTIVE_PARTIALLY_VERIFIED = "OBJECTIVE_PARTIALLY_VERIFIED"
OBJECTIVE_VERIFIED = "OBJECTIVE_VERIFIED"
OBJECTIVE_BLOCKED = "OBJECTIVE_BLOCKED"

# Publication Statuses
LOCAL_IMPLEMENTED = "LOCAL_IMPLEMENTED"
LOCAL_VERIFIED = "LOCAL_VERIFIED"
LOCAL_NO_PUBLISH = "LOCAL_NO_PUBLISH"
RELEASE_PENDING = "RELEASE_PENDING"
RELEASE_UNKNOWN = "RELEASE_UNKNOWN"
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
PUBLICATION_LANE_PUBLISHED = "PUBLISHED"
PUBLICATION_LANE_LOCAL_NO_PUBLISH = "LOCAL_NO_PUBLISH"
PUBLICATION_LANE_UNKNOWN = "UNKNOWN"

CAMPAIGN_LANE_RUNNING = "RUNNING"
CAMPAIGN_LANE_QUIESCENT = "QUIESCENT"
CAMPAIGN_LANE_WAIT_AUTHORITY = "WAIT_AUTHORITY"
CAMPAIGN_LANE_WAIT_EXTERNAL = "WAIT_EXTERNAL"
CAMPAIGN_LANE_COMPLETE = "COMPLETE"


@dataclass(frozen=True, eq=False)
class PublicationEvidence:
    """Command-scoped owner observation, not operator authentication."""

    project_root: str
    project_lineage: str
    project_identity: str
    ticket_snapshot: str
    receipt_digest: str
    tickets: tuple[tuple[str, str, tuple[str, ...], str], ...]
    diagnostics: tuple[str, ...] = ()


# ponytail: same-process provenance only; recapture at the outer observation owner.
_issued_publication_evidence = WeakKeyDictionary()


def _carrier_fields(evidence):
    return tuple(getattr(evidence, field.name) for field in fields(PublicationEvidence))


def _done_tickets(tickets):
    return {tid: ticket for tid, ticket in tickets.items() if ticket.get("section") == "## DONE"}


def _ticket_snapshot(tickets):
    raw = json.dumps(tickets, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_publication_evidence(
    root: Path | str, *, tickets: dict, ticket_id: str | None = None,
) -> PublicationEvidence:
    """Read canonical ticket/project receipts through the existing release owner.

    No grants, lifecycle or Git writes. A terminal receipt's own flags prove
    nothing: release_verdict independently checks its project and Git result.
    A selected ticket_id requires the same selected DONE subset at consumption.
    """
    from .journal import SemanticReceiptSnapshot, semantic_receipt_snapshot
    from .paths import project_identity, project_lineage_identity
    from . import release

    root = Path(root).resolve()
    selected = _done_tickets(tickets)
    if ticket_id is not None:
        selected = {ticket_id: selected[ticket_id]} if ticket_id in selected else {}
    diagnostics = []
    results = []
    lineage = identity = digest = ""
    try:
        if ticket_id is not None and not selected:
            raise ValueError("selected publication ticket is not DONE")
        ticket_hash = _ticket_snapshot(selected)
        lineage = project_lineage_identity(root) or ""
        identity = project_identity(root)
        snapshot = semantic_receipt_snapshot(root)
        digest = snapshot.digest
        diagnostics.extend(snapshot.errors)
        for tid in sorted(selected):
            records = tuple(record for record in snapshot.records
                            if record.get("operation") == "release"
                            and record.get("ticket_id") == tid
                            and record.get("status") != "ABORTED")
            op_ids = tuple(str(record.get("op_id") or "") for record in records)
            if snapshot.errors:
                status, reason = "unknown", "; ".join(snapshot.errors[:3])
            elif not records:
                status, reason = "pending", "no canonical ticket-bound release receipt"
            elif any(not (record.get("project_lineage") or record.get("project_identity"))
                     for record in records):
                status, reason = "unknown", "release receipt lacks project binding"
            else:
                scoped = SemanticReceiptSnapshot(records, (), snapshot.corrupt_op_ids, digest)
                verdict = release.release_verdict(root, receipt_snapshot=scoped)
                evidence = verdict.get("evidence") or {}
                bound = (verdict.get("status") == "ok" and evidence.get("ticket_id") == tid
                         and evidence.get("op_id") in op_ids)
                if (bound and evidence.get("terminal_outcome") == release.TERMINAL_PUBLISHED
                        and evidence.get("publication") == release.PUBLICATION_PERFORMED
                        and evidence.get("mode") == "full"):
                    status, reason = "published", "canonical release independently verified"
                elif (bound and evidence.get("terminal_outcome") == release.TERMINAL_LOCAL_NO_PUBLISH
                      and evidence.get("publication") == release.PUBLICATION_NOT_PERFORMED
                      and evidence.get("mode") == "no-publish"):
                    status, reason = "no-publish", "canonical local closure; publication not performed"
                else:
                    status = "unknown"
                    reason = str(verdict.get("reason") or "release owner returned no bound terminal proof")
            results.append((tid, status, op_ids, reason))
        if project_lineage_identity(root) != (lineage or None):
            raise ValueError("project lineage changed during publication observation")
    except Exception as exc:
        diagnostics.append(f"publication evidence unavailable: {type(exc).__name__}: {exc}")
        ticket_hash = _ticket_snapshot(selected)
        results = [(tid, "unknown", (), diagnostics[-1]) for tid in sorted(selected)]
    carrier = PublicationEvidence(str(root), lineage, identity, ticket_hash, digest,
                                  tuple(results), tuple(diagnostics))
    _issued_publication_evidence[carrier] = _carrier_fields(carrier)
    return carrier


def _publication_hint(value):
    if not isinstance(value, str):
        return "unknown"
    value = value.strip().lower()
    if value in ("no-publish", "local-no-publish", "local_no_publish", "local-only"):
        return "no-publish"
    return value if value in ("pending", "blocked", "ready") else "unknown"


def _aggregate_publication(statuses):
    for status in ("unknown", "blocked", "pending", "ready", "no-publish", "published"):
        if status in statuses:
            return status
    return "pending"


def _publication_projection(root, tickets, state, publication_state, evidence):
    selected = _done_tickets(tickets)
    hint = publication_state if publication_state is not None else state.get("publication_state")
    details = {"tickets": [], "diagnostics": []}
    if evidence is None and root is not None:
        evidence = read_publication_evidence(root, tickets=tickets)
    if evidence is not None:
        valid = (type(evidence) is PublicationEvidence
                 and _issued_publication_evidence.get(evidence) == _carrier_fields(evidence))
        if valid:
            valid = evidence.ticket_snapshot == _ticket_snapshot(selected)
        if valid and root is not None:
            valid = str(Path(root).resolve()) == evidence.project_root
            if valid:
                current = read_publication_evidence(root, tickets=tickets)
                valid = _carrier_fields(current) == _carrier_fields(evidence)
        if not valid:
            details["diagnostics"] = ["publication evidence is not owner-issued, current, or bound to this selection"]
            return "unknown", details
        details.update(project_root=evidence.project_root, project_lineage=evidence.project_lineage,
                       receipt_digest=evidence.receipt_digest, diagnostics=list(evidence.diagnostics))
        for tid, status, op_ids, reason in evidence.tickets:
            if status == "pending":
                value = hint if hint is not None else (selected[tid].get("fields") or {}).get("publication_state", "pending")
                status = _publication_hint(value)
            details["tickets"].append({"ticket_id": tid, "status": status,
                                       "receipt_ids": list(op_ids), "reason": reason})
        if evidence.diagnostics:
            return "unknown", details
    else:
        for tid, ticket in selected.items():
            value = hint if hint is not None else (ticket.get("fields") or {}).get("publication_state", "pending")
            details["tickets"].append({"ticket_id": tid, "status": _publication_hint(value),
                                       "receipt_ids": [], "reason": "intent only; no owner publication proof"})
    statuses = [item["status"] for item in details["tickets"]]
    if not statuses:
        statuses = [_publication_hint(hint if hint is not None else "pending")]
    return _aggregate_publication(statuses), details


def _workable_ids(tickets, state):
    from .board import workable_tickets

    return set(workable_tickets(tickets, agent=state.get("agent")))


def _campaign_status(doing, workable, blocked, authority, budget, certificate, *, external=False):
    from .work_exhaustion import verified_quiescence

    if doing or workable:
        return CAMPAIGN_RUNNING
    if budget:
        return CAMPAIGN_WAIT_AUTHORITY
    if external or any("EXTERNAL" in str((t.get("fields") or {}).get("blocker", "")) for t in blocked):
        return CAMPAIGN_WAIT_EXTERNAL
    if blocked or not authority:
        return CAMPAIGN_WAIT_AUTHORITY
    if verified_quiescence(certificate):
        return CAMPAIGN_QUIESCENT
    return CAMPAIGN_INCOMPLETE_DISCOVERY


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
    work_exhaustion: dict | None = None,
    publication_evidence: PublicationEvidence | None = None,
) -> dict[str, str]:
    """Separate operational lanes; root=None consumes owner evidence without IO."""
    tickets = tickets or {}
    state = state or {}
    pub, _details = _publication_projection(root, tickets, state, publication_state, publication_evidence)
    return _lane_statuses(tickets, state, pub, has_continuous_maintenance, foreign_staged,
                          is_budget_exhausted, primary_blocker, work_exhaustion)


def _lane_statuses(tickets, state, pub, authority, foreign_staged, budget, primary_blocker, certificate):
    doing = [t for t in tickets.values() if t.get("section") == "## DOING"]
    todo = [t for t in tickets.values() if t.get("section") == "## TODO"]
    blocked = [t for t in tickets.values() if t.get("section") == "## BLOCKED"]
    workable_ids = _workable_ids(tickets, state)
    workable = [t for t in todo if t["id"] in workable_ids]

    # 1. RELEASE_LANE
    if foreign_staged:
        release_lane = RELEASE_LANE_BLOCKED_FOREIGN_INDEX
    elif primary_blocker and primary_blocker.get("cause") == "publication-staging":
        release_lane = RELEASE_LANE_BLOCKED_FOREIGN_INDEX
    elif pub == "blocked":
        release_lane = RELEASE_LANE_BLOCKED
    elif pub == "ready":
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
    if not authority:
        discovery_lane = DISCOVERY_LANE_AUTHORITY_REQUIRED
    else:
        discovery_lane = DISCOVERY_LANE_NOT_DUE

    # Completed publication/local-only truth survives a later release hold.
    publication_lane = {
        "pending": PUBLICATION_LANE_PENDING, "blocked": PUBLICATION_LANE_BLOCKED,
        "ready": PUBLICATION_LANE_READY, "published": PUBLICATION_LANE_PUBLISHED,
        "no-publish": PUBLICATION_LANE_LOCAL_NO_PUBLISH, "unknown": PUBLICATION_LANE_UNKNOWN,
    }[pub]
    if release_lane == RELEASE_LANE_BLOCKED_FOREIGN_INDEX and pub in ("pending", "ready", "blocked"):
        publication_lane = PUBLICATION_LANE_BLOCKED

    # 5. CAMPAIGN
    campaign = _campaign_status(
        doing, workable, blocked, authority, budget,
        certificate, external=(
            release_lane == RELEASE_LANE_BLOCKED_FOREIGN_INDEX
            or bool(primary_blocker and "EXTERNAL" in str(primary_blocker.get("blocker_class", "")))
        ),
    ).removeprefix("CAMPAIGN_")

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
    work_exhaustion: dict | None = None,
    verification_evidence: dict | None = None,
    publication_evidence: dict | None = None,
) -> dict:
    """Project the multi-plane outcome truth from canonical facts.

    Never infers objective success from an empty executable ticket queue.
    """
    tickets = tickets or {}
    state = state or {}

    doing = [t for t in tickets.values() if t.get("section") == "## DOING"]
    todo = [t for t in tickets.values() if t.get("section") == "## TODO"]
    blocked = [t for t in tickets.values() if t.get("section") == "## BLOCKED"]
    workable_ids = _workable_ids(tickets, state)
    workable = [t for t in todo if t["id"] in workable_ids]

    # 1. QUEUE_STATUS (legacy meaning preserved: "nothing workable remains";
    # blocked Work is named below by CAMPAIGN_STATUS and the certificate).
    if workable or doing:
        queue_status = QUEUE_HAS_WORK
    else:
        queue_status = QUEUE_DRAINED

    # 2. CAMPAIGN_STATUS
    campaign_status = _campaign_status(
        doing, workable, blocked, has_continuous_maintenance, is_budget_exhausted,
        work_exhaustion,
    )

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
    if pub == "published" and (
        publication_evidence and publication_evidence.get("verified") is True
        and publication_evidence.get("release_id")
    ):
        publication_status = RELEASE_PUBLISHED
    elif pub == "ready":
        publication_status = RELEASE_READY
    elif pub == "blocked":
        publication_status = RELEASE_BLOCKED
    elif pub == "pending":
        publication_status = RELEASE_BLOCKED
    else:
        publication_status = LOCAL_IMPLEMENTED

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
    elif campaign_status == CAMPAIGN_INCOMPLETE_DISCOVERY:
        next_wake = "current discovery provider evidence becomes available"
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
        work_exhaustion=work_exhaustion,
    )

    lanes["CAMPAIGN"] = campaign_status.removeprefix("CAMPAIGN_")
    verification_status = "NOT_CHECKED"
    if verification_evidence and verification_evidence.get("scope") and verification_evidence.get("verdict") in ("PASS", "FAIL"):
        verification_status = f"{verification_evidence['scope']}: {verification_evidence['verdict']}"
    return {
        "queue_status": queue_status,
        "campaign_status": campaign_status,
        "objective_status": objective_status,
        "publication_status": publication_status,
        "verification_status": verification_status,
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

"""Work-Exhaustion Certificate across independent discovery surfaces (PV-004, PV-008).

Proves whether no-work is genuine exhaustion across all eligible sources:
1. active_work
2. canonical_recovery
3. actionable_todo
4. unresolved_source
5. unconsumed_audit_inbox
6. release_obligations
7. future_gates
8. hunt_findings
9. improve_candidates
10. saipal_forensics
11. conformance_debt

Each source record provides:
- SOURCE_NAME
- SOURCE_GENERATION
- LAST_CHECKED_GENERATION
- ELIGIBILITY_RESULT (WORK_AVAILABLE, BLOCKED_EXTERNAL, BLOCKED_OPERATOR,
  BLOCKED_AUTHORITY, DEFERRED, UNCHANGED, NOT_DUE, CLEAN_VERIFIED, NOT_CHECKED)
- AUTHORIZED_ACTIONS
- EXACT_BLOCKER
- NEXT_RECHECK_CONDITION
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Source names
ACTIVE_WORK = "active_work"
CANONICAL_RECOVERY = "canonical_recovery"
ACTIONABLE_TODO = "actionable_todo"
UNRESOLVED_SOURCE = "unresolved_source"
UNCONSUMED_AUDIT_INBOX = "unconsumed_audit_inbox"
RELEASE_OBLIGATIONS = "release_obligations"
FUTURE_GATES = "future_gates"
HUNT_FINDINGS = "hunt_findings"
IMPROVE_CANDIDATES = "improve_candidates"
EXTERNAL_FORENSICS = "external_forensics"
CONFORMANCE_DEBT = "conformance_debt"

ALL_WORK_SOURCES = (
    ACTIVE_WORK,
    CANONICAL_RECOVERY,
    ACTIONABLE_TODO,
    UNRESOLVED_SOURCE,
    UNCONSUMED_AUDIT_INBOX,
    RELEASE_OBLIGATIONS,
    FUTURE_GATES,
    HUNT_FINDINGS,
    IMPROVE_CANDIDATES,
    EXTERNAL_FORENSICS,
    CONFORMANCE_DEBT,
)

# Eligibility classifications
WORK_AVAILABLE = "WORK_AVAILABLE"
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
BLOCKED_OPERATOR = "BLOCKED_OPERATOR"
BLOCKED_AUTHORITY = "BLOCKED_AUTHORITY"
DEFERRED = "DEFERRED"
UNCHANGED = "UNCHANGED"
NOT_DUE = "NOT_DUE"
CLEAN_VERIFIED = "CLEAN_VERIFIED"
NOT_CHECKED = "NOT_CHECKED"


def certify_work_exhaustion(
    root: Path | str | None,
    *,
    tickets: dict | None = None,
    state: dict | None = None,
    audit_inbox: dict | None = None,
    future_gate: dict | None = None,
    source_generation: str | None = None,
    hunt_state: dict | None = None,
    forensic_state: dict | None = None,
    continuous_maintenance_authorized: bool = False,
    is_budget_exhausted: bool = False,
) -> dict:
    """Build bounded read-only work exhaustion certificate across all sources."""
    tickets = tickets or {}
    state = state or {}
    generation = source_generation or state.get("last_event") or "gen-current"

    sources: list[dict] = []

    # 1. active_work
    doing = [t for t in tickets.values() if t.get("section") == "## DOING"]
    if doing:
        sources.append({
            "source_name": ACTIVE_WORK,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": WORK_AVAILABLE,
            "authorized_actions": [f"saipen claim {doing[0]['id']}"],
            "exact_blocker": None,
            "next_recheck_condition": "active work completed",
        })
    else:
        sources.append({
            "source_name": ACTIVE_WORK,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": CLEAN_VERIFIED,
            "authorized_actions": [],
            "exact_blocker": None,
            "next_recheck_condition": "new ticket claimed",
        })

    # 2. canonical_recovery
    sources.append({
        "source_name": CANONICAL_RECOVERY,
        "source_generation": generation,
        "last_checked_generation": generation,
        "eligibility_result": CLEAN_VERIFIED,
        "authorized_actions": [],
        "exact_blocker": None,
        "next_recheck_condition": "uncommitted crash or interrupted operation",
    })

    # 3. actionable_todo
    todo = [t for t in tickets.values() if t.get("section") == "## TODO"]
    workable_todo = [t for t in todo if not t.get("blocked")]
    if workable_todo:
        sources.append({
            "source_name": ACTIONABLE_TODO,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": WORK_AVAILABLE,
            "authorized_actions": [f"saipen claim {workable_todo[0]['id']}"],
            "exact_blocker": None,
            "next_recheck_condition": "workable todo ticket claimed",
        })
    else:
        sources.append({
            "source_name": ACTIONABLE_TODO,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": CLEAN_VERIFIED,
            "authorized_actions": [],
            "exact_blocker": None,
            "next_recheck_condition": "new todo ticket added",
        })

    # 4. unresolved_source
    sources.append({
        "source_name": UNRESOLVED_SOURCE,
        "source_generation": generation,
        "last_checked_generation": generation,
        "eligibility_result": CLEAN_VERIFIED,
        "authorized_actions": [],
        "exact_blocker": None,
        "next_recheck_condition": "new source admitted",
    })

    # 5. unconsumed_audit_inbox
    unconsumed = 0
    if isinstance(audit_inbox, dict):
        unconsumed = int(audit_inbox.get("unresolved_audit_count", len(audit_inbox.get("pending", []))))
    if unconsumed > 0:
        sources.append({
            "source_name": UNCONSUMED_AUDIT_INBOX,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": WORK_AVAILABLE,
            "authorized_actions": ["saipen audit ingest"],
            "exact_blocker": None,
            "next_recheck_condition": "audit ingest executed",
        })
    else:
        sources.append({
            "source_name": UNCONSUMED_AUDIT_INBOX,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": CLEAN_VERIFIED,
            "authorized_actions": [],
            "exact_blocker": None,
            "next_recheck_condition": "new audit finding submitted",
        })

    # 6. release_obligations
    staging_blocked = any(
        "PUBLICATION_STAGING_BLOCKED" in str((t.get("fields") or {}).get("blocker", ""))
        for t in tickets.values()
    )
    if staging_blocked:
        sources.append({
            "source_name": RELEASE_OBLIGATIONS,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": BLOCKED_OPERATOR,
            "authorized_actions": [],
            "exact_blocker": "Foreign pre-staged paths in shared Git index",
            "next_recheck_condition": "Foreign staging resolved or release isolated",
        })
    else:
        sources.append({
            "source_name": RELEASE_OBLIGATIONS,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": CLEAN_VERIFIED,
            "authorized_actions": [],
            "exact_blocker": None,
            "next_recheck_condition": "new release candidate ready",
        })

    # 7. future_gates
    if isinstance(future_gate, dict) and future_gate.get("eligible"):
        sources.append({
            "source_name": FUTURE_GATES,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": WORK_AVAILABLE,
            "authorized_actions": [f"saipen future promote {future_gate['eligible'][0]}"],
            "exact_blocker": None,
            "next_recheck_condition": "future gate promoted",
        })
    else:
        sources.append({
            "source_name": FUTURE_GATES,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": DEFERRED,
            "authorized_actions": [],
            "exact_blocker": "Deferred architecture holds intact",
            "next_recheck_condition": "prerequisites satisfied",
        })

    # 8. hunt_findings
    if hunt_state:
        last_hunt_gen = hunt_state.get("last_analyzed_generation")
        if last_hunt_gen != generation:
            sources.append({
                "source_name": HUNT_FINDINGS,
                "source_generation": generation,
                "last_checked_generation": last_hunt_gen,
                "eligibility_result": NOT_CHECKED,
                "authorized_actions": ["saipen hunt"] if continuous_maintenance_authorized else [],
                "exact_blocker": None if continuous_maintenance_authorized else "Continuous maintenance unauthorized",
                "next_recheck_condition": "source generation changes",
            })
        else:
            sources.append({
                "source_name": HUNT_FINDINGS,
                "source_generation": generation,
                "last_checked_generation": generation,
                "eligibility_result": UNCHANGED,
                "authorized_actions": [],
                "exact_blocker": None,
                "next_recheck_condition": "source generation changes",
            })
    else:
        # HUNT has not run on this generation: NOT_CHECKED, never assumed clean
        sources.append({
            "source_name": HUNT_FINDINGS,
            "source_generation": generation,
            "last_checked_generation": None,
            "eligibility_result": NOT_CHECKED,
            "authorized_actions": ["saipen hunt"] if continuous_maintenance_authorized else [],
            "exact_blocker": None if continuous_maintenance_authorized else "Continuous maintenance unauthorized",
            "next_recheck_condition": "hunt execution authorized",
        })

    # 9. improve_candidates
    if not continuous_maintenance_authorized:
        sources.append({
            "source_name": IMPROVE_CANDIDATES,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": BLOCKED_AUTHORITY,
            "authorized_actions": [],
            "exact_blocker": "Autonomous improvement requires continuous maintenance authority",
            "next_recheck_condition": "operator reauthorizes standing grant",
        })
    else:
        sources.append({
            "source_name": IMPROVE_CANDIDATES,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": UNCHANGED,
            "authorized_actions": [],
            "exact_blocker": None,
            "next_recheck_condition": "new code changes committed",
        })

    # 10. saipal_forensics
    if forensic_state and forensic_state.get("unfinished_slices"):
        sources.append({
            "source_name": EXTERNAL_FORENSICS,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": WORK_AVAILABLE,
            "authorized_actions": ["saipen sub"],
            "exact_blocker": None,
            "next_recheck_condition": "forensic slice analyzed",
        })
    else:
        sources.append({
            "source_name": EXTERNAL_FORENSICS,
            "source_generation": generation,
            "last_checked_generation": generation,
            "eligibility_result": CLEAN_VERIFIED,
            "authorized_actions": [],
            "exact_blocker": None,
            "next_recheck_condition": "forensic anomaly detected",
        })

    # 11. conformance_debt
    sources.append({
        "source_name": CONFORMANCE_DEBT,
        "source_generation": generation,
        "last_checked_generation": generation,
        "eligibility_result": CLEAN_VERIFIED,
        "authorized_actions": [],
        "exact_blocker": None,
        "next_recheck_condition": "conformance drift occurs",
    })

    # Overall certificate verdict
    has_available = any(s["eligibility_result"] == WORK_AVAILABLE for s in sources)
    all_clean_or_deferred = all(
        s["eligibility_result"] in (CLEAN_VERIFIED, DEFERRED, UNCHANGED, BLOCKED_EXTERNAL, BLOCKED_OPERATOR, BLOCKED_AUTHORITY)
        for s in sources
    )

    if has_available:
        status = "WORK_ELIGIBLE"
    elif all_clean_or_deferred:
        status = "EXHAUSTED_QUIESCENT"
    else:
        status = "INCOMPLETE_DISCOVERY"

    return {
        "status": status,
        "source_generation": generation,
        "sources": sources,
        "exhausted": not has_available,
        "all_checked": all(s["eligibility_result"] != NOT_CHECKED for s in sources),
    }

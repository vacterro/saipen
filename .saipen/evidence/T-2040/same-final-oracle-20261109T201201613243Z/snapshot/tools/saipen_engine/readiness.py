"""One computed PROJECT READINESS decision, separate from the execution phase.

T-1862 (SRC-294). The measured defect: `saipen status --json` publishes exactly
one lifecycle verdict -- `phase` and `task` from STATE. A project whose last
ticket shipped therefore reads `phase: DONE`, `task: none`, and the payload
carries nothing that can say "but 162 source clauses are still UNKNOWN and
seven tickets are blocked". The operator reads DONE as project completion
because the surface offers no other reading.

Reproduced on the real SAITULS project (read-only):

    phase DONE / task none / top_workable_ticket null
    BOARD: 1 DOING, 2 TODO, 207 DONE, 7 BLOCKED
    intake coverage: 230 requirements, 162 UNKNOWN
    audit/ layers: 2 present, inbox status clean

Nothing there is a SAIPEN defect in itself. `DONE` is the correct lifecycle
verdict for the last *execution* ticket, and every input above is already
correct. What was missing is a per-dimension answer that survives the phase
transition.

THE CONTRACT. Six dimensions are computed independently and never collapsed
into the phase:

    execution      -- the STATE lifecycle verdict, quoted, never rewritten
    work           -- is there runnable / blocked / finished Work
    audit          -- audit inbox layers not yet consumed
    source         -- source coverage that is not terminal
    integrity      -- receipts whose own records cannot be trusted
    authority      -- the continuation authority, quoted, never escalated

and ONE canonical `status` derived from them by a fixed precedence. Execution
phase is an INPUT to the derived status, never its name.

WHAT THIS MODULE MUST NEVER DO, and each is a test in the regression matrix:

* it never writes. It is a projection over already-persisted facts; it opens
  no journal entry, appends no event, and mutates no STATE/BOARD/LOG.
* it never escalates authority. `continuation_authority`, `safety_valve_mode`
  and a `WAIT:` next_action are copied through verbatim. A new audit layer or
  a fresh UNKNOWN clause is information, not an operator cc.
* it never turns a BLOCKED ticket into runnable work, and never counts a
  blocked or deferred clause as a defect.
* it never infers campaign completeness from a finished-ticket count, the last
  SHIP transition, `task: none`, or an empty source inbox.

DEFINITION OF "OUTSTANDING". Reuses the intake vocabulary (`intake.
TERMINAL_DISPOSITIONS`) rather than defining a second one. A requirement is
outstanding when it is ACTIONABLE and either its disposition is non-terminal
or it carries no evidence. A non-actionable clause is never outstanding. A
DUPLICATE disposition is terminal, and one archive reference and its active
counterpart are the same receipt, so neither can be double counted.
"""

from __future__ import annotations


RULE_ID = "T-1862"

#: The derived readiness status. Precedence runs top to bottom: the first
#: condition that holds names the project, so a genuinely accepted project can
#: never be described as merely idle, and an outstanding obligation can never
#: be hidden behind a finished execution phase.
EXECUTION_IDLE = "EXECUTION_IDLE"
WORK_AVAILABLE = "WORK_AVAILABLE"
WORK_BLOCKED = "WORK_BLOCKED"
EXTERNALLY_BLOCKED = "EXTERNALLY_BLOCKED"
AUDIT_OUTSTANDING = "AUDIT_OUTSTANDING"
SOURCE_RECONCILIATION_REQUIRED = "SOURCE_RECONCILIATION_REQUIRED"
INTEGRITY_BLOCKED = "INTEGRITY_BLOCKED"
PROJECT_ACCEPTED = "PROJECT_ACCEPTED"

STATUSES = (
    EXECUTION_IDLE,
    WORK_AVAILABLE,
    WORK_BLOCKED,
    EXTERNALLY_BLOCKED,
    AUDIT_OUTSTANDING,
    SOURCE_RECONCILIATION_REQUIRED,
    INTEGRITY_BLOCKED,
    PROJECT_ACCEPTED,
)

#: Human-readable one-liners. Never a substitute for the machine fields.
HEADLINES = {
    EXECUTION_IDLE: "execution is idle and no obligation is outstanding",
    WORK_AVAILABLE: "Work remains in the backlog",
    WORK_BLOCKED: "the remaining Work is blocked on something outside the engine",
    EXTERNALLY_BLOCKED: "acceptance waits on an external party, not on this engine",
    AUDIT_OUTSTANDING: "an audit layer is waiting to be consumed",
    SOURCE_RECONCILIATION_REQUIRED: "source clauses are not terminal",
    INTEGRITY_BLOCKED: "a source receipt's own records cannot be trusted",
    PROJECT_ACCEPTED: "every declared obligation is terminal and no Work remains",
}

SCHEMA_VERSION = 1


def _board_dimension(tickets: dict, top_workable: str | None) -> dict:
    """Section counts, plus the three states that must never be conflated.

    `open` deliberately INCLUDES `## BLOCKED`. The first version of this
    function counted only DOING+TODO, so a project whose entire remainder was
    blocked satisfied "no open work" and reported PROJECT_ACCEPTED -- the exact
    defect this ticket exists to remove, reproduced inside its own fix. A
    blocked ticket is outstanding Work; it is just not runnable.

    `claimed` is separate from `blocked` for the same reason in the other
    direction: a claimed DOING ticket is being executed, so its presence must
    not be reported as "somebody is blocking us".
    """
    counts = {"doing": 0, "todo": 0, "done": 0, "blocked": 0}
    external = 0
    for ticket in (tickets or {}).values():
        section = str(ticket.get("section") or "")
        if section == "## DOING":
            counts["doing"] += 1
        elif section == "## TODO":
            counts["todo"] += 1
        elif section == "## DONE":
            counts["done"] += 1
        elif section == "## BLOCKED":
            counts["blocked"] += 1
            blocker = str((ticket.get("fields") or {}).get("blocker") or "")
            if blocker.strip().split(" -- ", 1)[0].strip().upper() == "BLOCKED_EXTERNAL":
                external += 1
    return {
        "counts": counts,
        "open": counts["doing"] + counts["todo"] + counts["blocked"],
        "runnable": counts["todo"],
        "claimed": counts["doing"],
        "work_available": bool(top_workable),
        "top_workable": top_workable,
        "blocked": counts["blocked"],
        "blocked_external": external,
    }


def _audit_dimension(inbox: dict | None) -> dict:
    """Layers not yet consumed. A clean inbox is zeroes, never an absence."""
    if not isinstance(inbox, dict):
        return {"known": False, "pending": 0, "invalid": 0, "residue": 0, "clean": None}
    return {
        "known": inbox.get("ok") is True,
        "pending": len(inbox.get("pending") or []),
        "invalid": len(inbox.get("invalid") or []),
        "closed_pending_delete": len(inbox.get("closed_pending_delete") or []),
        "residue": int(inbox.get("residue_count") or 0),
        "clean": inbox.get("clean"),
        "error_state": inbox.get("error_state"),
        "inbox_state": inbox.get("inbox_state"),
    }


def _source_dimension(receipts: list[dict] | None, tombstones: dict) -> dict:
    """Active receipts, their obligations, and how many are not terminal.

    `receipts` is `intake.active_receipts()` (already index+coverage derived).
    `tombstones` is the archive half of the same index: a receipt lives in
    exactly one of the two, so summing both would double count a closed
    receipt. Archived tombstones are reported as counts only, and never as
    outstanding obligations -- a closed receipt's own record says how many
    requirements it carried and how many were unresolved at closure.

    `receipts is None` means the index could not be read, which is NOT zero
    coverage. The first version of this function treated an unreadable index
    as an empty one, so a project whose source records were corrupt could
    report `PROJECT_ACCEPTED` -- "no known obligation" read as "no
    obligation". `receipts_known: False` carries the gap and the derivation
    refuses acceptance on it.
    """
    archived = {
        "receipts": len(tombstones or {}),
        "unresolved_at_closure": sum(
            int((meta or {}).get("unresolved") or 0) for meta in (tombstones or {}).values()
        ),
    }
    if receipts is None:
        return {
            "active_receipts": 0,
            "requirements": 0,
            "outstanding": 0,
            "terminal": 0,
            "archived": archived,
            "receipts_known": False,
        }
    outstanding = 0
    requirements = 0
    active = 0
    for item in receipts:
        active += 1
        requirements += int(item.get("requirements") or 0)
        outstanding += int(item.get("unresolved") or 0)
    return {
        "active_receipts": active,
        "requirements": requirements,
        "outstanding": outstanding,
        "terminal": max(requirements - outstanding, 0),
        "archived": archived,
        "receipts_known": True,
    }


def _integrity_dimension(orphans: dict | None) -> dict:
    if not isinstance(orphans, dict):
        return {"known": False, "orphans": 0, "items": []}
    items = orphans.get("orphans") or []
    return {"known": orphans.get("ok") is True, "orphans": len(items), "items": items[:10]}


def _authority_dimension(state: dict, goal_authority: dict | None) -> dict:
    """Quoted, never interpreted, never escalated.

    Every field here is copied out of durable state or an already-computed
    projection. This function exists so the readiness answer can NAME the
    authority it is bounded by; it never decides that authority differently.
    """
    next_action = str(state.get("next_action") or "")
    return {
        "continuation_authority": state.get("continuation_authority"),
        "authority_source": state.get("authority_source"),
        "authority_until": state.get("authority_until"),
        "safety_valve_mode": state.get("safety_valve_mode"),
        "execution_intent": state.get("execution_intent"),
        "waiting": next_action.startswith("WAIT:"),
        "next_action": next_action or None,
        "goal_authority": goal_authority if isinstance(goal_authority, dict) else None,
    }


def derive(
    *,
    state: dict,
    tickets: dict,
    top_workable: str | None = None,
    inbox: dict | None = None,
    receipts: list[dict] | None = None,
    tombstones: dict | None = None,
    orphans: dict | None = None,
    goal_authority: dict | None = None,
) -> dict:
    """The canonical PROJECT READINESS answer for an already-read project.

    Every argument is a fact the caller already holds; this function performs
    no I/O so it can be unit-tested against a synthetic project and called from
    `status` without a second walk of the same inputs.

    Precedence, highest first:

    1. INTEGRITY_BLOCKED   -- a receipt's own records are untrustworthy. This
       outranks coverage because coverage read from broken records is not
       evidence of anything.
    2. AUDIT_OUTSTANDING   -- an audit layer exists, the inbox is unclean, or
       its classification failed. It outranks source coverage: an unread audit
       can itself be the reason a clause is UNKNOWN.
    3. SOURCE_RECONCILIATION_REQUIRED -- actionable clauses are not terminal.
    4. EXTERNALLY_BLOCKED  -- the only open Work waits on an outside party.
       Kept distinct from WORK_BLOCKED so a reader can tell "someone must
       decide" from "a vendor/CI/credential must answer".
    5. WORK_BLOCKED        -- open Work exists and none of it is runnable.
    6. WORK_AVAILABLE      -- runnable Work exists.
    7. PROJECT_ACCEPTED    -- everything above is empty and the execution phase
       is a terminal one.
    8. EXECUTION_IDLE      -- everything above is empty but the phase is still
       mid-flight, so completion is not claimed.
    """
    phase = str(state.get("phase") or "").upper()
    work = _board_dimension(tickets, top_workable)
    audit = _audit_dimension(inbox)
    source = _source_dimension(receipts, tombstones or {})
    integrity = _integrity_dimension(orphans)
    authority = _authority_dimension(state, goal_authority)

    reasons: list[str] = []
    status: str
    if not integrity["known"]:
        status = INTEGRITY_BLOCKED
        reasons.append("source integrity diagnostic is unavailable; completion cannot be claimed")
    elif integrity["orphans"]:
        status = INTEGRITY_BLOCKED
        reasons.append(f"{integrity['orphans']} source receipt(s) are unreconstructed")
    elif not source["receipts_known"]:
        # Coverage that could not be read is not coverage that is terminal.
        # Named before the audit/source counts because every one of them would
        # read as zero; this is the same false-completion class as counting
        # only DOING+TODO.
        status = INTEGRITY_BLOCKED
        reasons.append("source coverage is unreadable; completion cannot be claimed")
    elif not audit["known"]:
        status = AUDIT_OUTSTANDING
        reasons.append("audit inbox status is unavailable; completion cannot be claimed")
    elif audit["pending"]:
        status = AUDIT_OUTSTANDING
        reasons.append(f"{audit['pending']} audit layer(s) not consumed")
    elif source["outstanding"]:
        status = SOURCE_RECONCILIATION_REQUIRED
        reasons.append(f"{source['outstanding']} actionable source clause(s) not terminal")
    elif audit["invalid"]:
        # An UNREADABLE layer is a real condition with no body left to read.
        # It outranks acceptance and is named honestly, but it is not
        # INTEGRITY_BLOCKED: the source records themselves are intact.
        status = AUDIT_OUTSTANDING
        reasons.append(f"{audit['invalid']} audit layer(s) are invalid or blocked")
    elif audit["residue"] or audit["closed_pending_delete"] or audit["clean"] is not True:
        status = AUDIT_OUTSTANDING
        reasons.append("audit inbox is not clean; completion cannot be claimed")
    elif work["work_available"]:
        status = WORK_AVAILABLE
        reasons.append(f"runnable Work from {work['top_workable']}")
    elif work["claimed"]:
        # A claimed DOING ticket IS being executed. Reporting it as blocked
        # would accuse the project of a stop it is not in.
        status = WORK_AVAILABLE
        reasons.append(f"{work['claimed']} ticket(s) in progress")
    elif work["open"]:
        if work["blocked_external"] and work["blocked_external"] >= work["blocked"]:
            status = EXTERNALLY_BLOCKED
            reasons.append(
                f"{work['blocked_external']} blocked ticket(s) wait on an external party"
            )
        else:
            status = WORK_BLOCKED
            reasons.append(f"{work['open']} open ticket(s), none runnable")
    elif phase in ("DONE", "SHIP"):
        status = PROJECT_ACCEPTED
        reasons.append("no outstanding audit, source or Work obligation")
    else:
        status = EXECUTION_IDLE
        reasons.append(f"phase {phase or 'UNKNOWN'} with nothing outstanding")

    accepted = status == PROJECT_ACCEPTED
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_id": RULE_ID,
        "status": status,
        "headline": HEADLINES[status],
        "accepted": accepted,
        "ready": accepted,
        "reasons": reasons,
        # The execution verdict is QUOTED. Its meaning is unchanged and this
        # field is the one every existing consumer keeps reading.
        "execution": {
            "phase": state.get("phase"),
            "task": state.get("task"),
            "terminal_phase": phase in ("DONE", "SHIP"),
            "claimed_ticket": state.get("task"),
        },
        "dimensions": {
            "work": work,
            "audit": audit,
            "source": source,
            "integrity": integrity,
            "authority": authority,
        },
        # Readiness never grants anything. It is stated in the contract so a
        # consumer cannot read `ready: true` as permission.
        "grants_authority": False,
        "authority_unchanged": True,
    }

"""Evidence-backed exhaustion of the twelve independent discovery surfaces.

Schema 2 narrows `exhausted` to verified, unblocked quiescence. Consumers of
schema 1's weaker queue claim use `no_work_available`; `legacy_status` retains
the old quiescent spelling. Discovery observations never grant authority.
"""

from __future__ import annotations

from pathlib import Path

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
PERSISTENT_GOALS = "persistent_goals"
ALL_WORK_SOURCES = (
    ACTIVE_WORK, CANONICAL_RECOVERY, ACTIONABLE_TODO, UNRESOLVED_SOURCE,
    UNCONSUMED_AUDIT_INBOX, RELEASE_OBLIGATIONS, FUTURE_GATES, HUNT_FINDINGS,
    IMPROVE_CANDIDATES, EXTERNAL_FORENSICS, CONFORMANCE_DEBT, PERSISTENT_GOALS,
)

WORK_AVAILABLE = "WORK_AVAILABLE"
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
BLOCKED_OPERATOR = "BLOCKED_OPERATOR"
BLOCKED_AUTHORITY = "BLOCKED_AUTHORITY"
DEFERRED = "DEFERRED"
UNCHANGED = "UNCHANGED"
NOT_DUE = "NOT_DUE"
CLEAN_VERIFIED = "CLEAN_VERIFIED"
NOT_CHECKED = "NOT_CHECKED"
WORK_ELIGIBLE = "WORK_ELIGIBLE"
VERIFIED_QUIESCENT = "VERIFIED_QUIESCENT"
INCOMPLETE_DISCOVERY = "INCOMPLETE_DISCOVERY"
EXHAUSTED_QUIESCENT = "EXHAUSTED_QUIESCENT"
SCHEMA_VERSION = 2
_RESULTS = frozenset((
    WORK_AVAILABLE, BLOCKED_EXTERNAL, BLOCKED_OPERATOR, BLOCKED_AUTHORITY,
    DEFERRED, UNCHANGED, NOT_DUE, CLEAN_VERIFIED, NOT_CHECKED,
))
_BLOCKERS = (BLOCKED_AUTHORITY, BLOCKED_OPERATOR, BLOCKED_EXTERNAL)


def verified_quiescence(certificate) -> bool:
    """Accept only a complete schema-2 certificate, never a legacy queue flag."""
    if not isinstance(certificate, dict) or not (
        certificate.get("schema_version") == SCHEMA_VERSION
        and certificate.get("status") == VERIFIED_QUIESCENT
        and certificate.get("exhausted") is True
        and certificate.get("all_checked") is True
        and not certificate.get("certificate_errors")
    ):
        return False
    sources = certificate.get("sources")
    if not isinstance(sources, list) or len(sources) != len(ALL_WORK_SOURCES):
        return False
    generation = certificate.get("source_generation")
    return bool(generation) and all(
        isinstance(source, dict)
        and source.get("checked") is True
        and isinstance(source.get("source_name"), str)
        and source.get("eligibility_result") in (CLEAN_VERIFIED, UNCHANGED, NOT_DUE, DEFERRED)
        and source.get("source_generation") == generation
        and source.get("last_checked_generation") == generation
        for source in sources
    ) and {source.get("source_name") for source in sources} == set(ALL_WORK_SOURCES)


def _count(value) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    if type(value) is int and value >= 0:
        return value
    raise ValueError("a nonnegative finding count or list is required")


def _blocker_result(group: dict) -> str:
    klass = group["blocker_class"]
    if "AUTHORITY" in klass:
        return BLOCKED_AUTHORITY
    if group["cause"] == "publication-staging" or "USER" in klass:
        return BLOCKED_OPERATOR
    if klass in ("HELD", "FUTURE_GATE", "FUTURE/STRATEGIC"):
        return DEFERRED
    return NOT_CHECKED if klass == "UNKNOWN" else BLOCKED_EXTERNAL


def _ticket_inventory_valid(tickets) -> bool:
    return isinstance(tickets, dict) and all(
        isinstance(ticket, dict)
        and ticket.get("section") in ("## DOING", "## TODO", "## DONE", "## BLOCKED")
        and isinstance(ticket.get("fields", {}), dict)
        and isinstance(ticket.get("needs", []), (list, tuple))
        and all(isinstance(need, str) for need in ticket.get("needs", []))
        for ticket in tickets.values()
    )


def recovery_identities(inventory) -> list[str]:
    """Accept either canonical journal rows or their projected operation IDs."""
    if not isinstance(inventory, (list, tuple)):
        raise ValueError("recovery inventory must be a list")
    identities = []
    for row in inventory:
        if isinstance(row, dict) and row.get("corrupt"):
            raise ValueError("recovery inventory contains corrupt journals")
        identity = row.get("op_id") if isinstance(row, dict) else row
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("recovery inventory contains an invalid operation identity")
        identities.append(identity)
    return identities


def discovery_evidence(
    root, *, state, tickets, pending_ops=None, conflict_ops=None, now=None,
) -> dict:
    """Read current owner evidence outside the routing/classification layer."""
    from . import conformance, goal_authority, intake, journal, persistent_goal, source_append
    from .board import claim_status, project_blockers, workable_tickets
    from .paths import prove_owned_dir_chain

    state = state if isinstance(state, dict) else {}
    generation = str(state.get("last_event") or "gen-current")
    records = {}

    def record(name, result=NOT_CHECKED, *, actions=(), detail=None, error=None):
        records[name] = {
            "source_generation": generation,
            "last_checked_generation": generation if result != NOT_CHECKED else None,
            "eligibility_result": result, "authorized_actions": list(actions),
            "exact_blocker": detail, "error": error,
        }

    try:
        goals = persistent_goal.list_goals_report(root)
        if not isinstance(goals, dict) or type(goals.get("root_available")) is not bool:
            raise ValueError("goal loader did not supply a valid inventory report")
        normalized = persistent_goal.goal_inventory(goals)
        goals = {**goals, **normalized}
    except Exception as exc:
        goals = {"goals": [], "complete": False, "root_available": False,
                 "errors": [f"goal loader raised {type(exc).__name__}: {exc}"]}
    if goals.get("root_available") is not True:
        for name in (CANONICAL_RECOVERY, UNRESOLVED_SOURCE, CONFORMANCE_DEBT,
                     HUNT_FINDINGS, IMPROVE_CANDIDATES, EXTERNAL_FORENSICS):
            record(name, detail="project root is unavailable")
        return {"persistent_goals": goals, "source_evidence": records,
                "continuous_maintenance_authorized": False}

    try:
        authorized = goal_authority.continuous_maintenance_proven(root, state) is True
    except Exception as exc:
        authorized = False
        record(IMPROVE_CANDIDATES, error=f"authority probe raised {type(exc).__name__}: {exc}")
    evidence = {"persistent_goals": goals, "source_evidence": records,
                "continuous_maintenance_authorized": authorized}
    try:
        if not _ticket_inventory_valid(tickets):
            raise ValueError("ticket inventory must be an object of valid ticket objects")
        workable = workable_tickets(tickets, agent=state.get("agent"), now=now)
        if any(ticket.get("section") == "## DOING" for ticket in tickets.values()) or workable:
            return evidence
    except Exception as exc:
        for name in (CANONICAL_RECOVERY, UNRESOLVED_SOURCE, CONFORMANCE_DEBT,
                     HUNT_FINDINGS, IMPROVE_CANDIDATES, EXTERNAL_FORENSICS):
            record(name, error=f"BOARD discovery raised {type(exc).__name__}: {exc}")
        return evidence

    try:
        if pending_ops is None or conflict_ops is None:
            pending_ops, conflict_ops = journal.scan_pending(root)
        pending_ids = recovery_identities(pending_ops)
        conflict_ids = recovery_identities(conflict_ops)
        record(CANONICAL_RECOVERY,
               WORK_AVAILABLE if pending_ids or conflict_ids else CLEAN_VERIFIED,
               actions=("saipen recover",) if pending_ids or conflict_ids else ())
    except Exception as exc:
        record(CANONICAL_RECOVERY, error=f"recovery discovery raised {type(exc).__name__}: {exc}")

    try:
        project = Path(root)
        for relative in (".saipen/intake", ".saipen/intake/active", ".saipen/intake/appends"):
            directory = project / relative
            prove_owned_dir_chain(directory, ownership_root=project, kind="Source inventory")
            try:
                list(directory.iterdir())
            except FileNotFoundError:
                pass
        rows = intake.active_receipts(root)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("source inventory must be a list of receipt objects")
        orphans = intake.recover_orphans(root)
        if not isinstance(orphans, dict) or orphans.get("ok") is not True or orphans.get("orphans"):
            raise ValueError("source inventory has unreadable or orphaned receipts")
        ledgers = source_append.ledgers(root)
        if not isinstance(ledgers, list):
            raise ValueError("append inventory must be a list")
        for ledger in ledgers:
            if not isinstance(ledger, dict) or ledger.get("error"):
                raise ValueError(f"append ledger unreadable: {ledger!r}")
        appends = source_append.pending_appends(root)
        if not isinstance(appends, list):
            raise ValueError("pending append inventory must be a list")
        unresolved = []
        linked_ids = set()
        unlinked = False
        for row in rows:
            receipt = row["receipt"]
            integrity = intake.verify_integrity(root, receipt)
            if not isinstance(integrity, dict) or integrity.get("ok") is not True:
                raise ValueError(f"{receipt}: source integrity did not verify")
            if row["unresolved"] or not intake.coverage_complete(root, receipt):
                unresolved.append(row)
                meta = intake._read_meta(root, receipt)
                if not isinstance(meta, dict):
                    raise ValueError(f"{receipt}: Source membership is unreadable")
                members = intake.linked_works(meta)
                missing = members - tickets.keys()
                if missing:
                    raise ValueError(f"{receipt}: missing linked Work: {', '.join(sorted(missing))}")
                linked_ids.update(members)
                unlinked |= not members
        linked = [tickets[tid] for tid in sorted(linked_ids)]
        owned = any(
            ticket.get("section") == "## DOING"
            and claim_status(ticket, state.get("agent"), now) in ("SELF", "UNCLAIMED")
            for ticket in linked
        )
        if appends or unlinked or owned or linked_ids.intersection(workable):
            record(UNRESOLVED_SOURCE, WORK_AVAILABLE, actions=("saipen continue",))
        elif unresolved:
            projection = project_blockers(tickets)
            groups = [group for group in projection["groups"] if
                      linked_ids.intersection((*group["root_tickets"], *group["dependent_tickets"]))]
            results = [_blocker_result(group) for group in groups]
            if any(ticket.get("section") == "## DOING" for ticket in linked):
                results.append(BLOCKED_EXTERNAL)
            if not results or NOT_CHECKED in results:
                raise ValueError("unresolved Source has no executable Work or verified root blocker")
            result = next((value for value in _BLOCKERS if value in results), DEFERRED)
            record(UNRESOLVED_SOURCE, result,
                   detail="unresolved Source: " + ", ".join(row["receipt"] for row in unresolved))
        else:
            record(UNRESOLVED_SOURCE, CLEAN_VERIFIED)
    except Exception as exc:
        record(UNRESOLVED_SOURCE, error=f"source discovery raised {type(exc).__name__}: {exc}")

    try:
        observed = conformance.conformance_status(root, now=now)
        status = observed.get("status")
        record(CONFORMANCE_DEBT,
               CLEAN_VERIFIED if status == conformance.STATUS_CURRENT_PASS
               else WORK_AVAILABLE if status == conformance.STATUS_CURRENT_FAIL else NOT_CHECKED,
               actions=("saipen validate",) if status == conformance.STATUS_CURRENT_FAIL else (),
               detail=observed.get("reason") or status)
    except Exception as exc:
        record(CONFORMANCE_DEBT, error=f"conformance discovery raised {type(exc).__name__}: {exc}")

    for name in (HUNT_FINDINGS, IMPROVE_CANDIDATES, EXTERNAL_FORENSICS):
        if name not in records:
            record(name, detail="current-generation analysis result not supplied")
    return evidence


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
    persistent_goals: list | dict | None = None,
    source_evidence: dict | None = None,
    now=None,
    current_agent: str | None = None,
    # Schema-1 check flags remain accepted, but cannot stand in for results.
    recovery_checked: bool = False,
    recovery_pending: bool = False,
    source_checked: bool = False,
    conformance_checked: bool = False,
    improve_checked: bool = False,
) -> dict:
    """Classify supplied observations; only an explicit root loads local goals.

    `source_evidence` holds current source records from discovery owners. A
    record requires eligibility_result, source_generation and matching
    last_checked_generation. Calling a check without its result proves nothing.
    """
    from .board import claim_status, project_blockers, workable_tickets
    from .persistent_goal import goal_inventory, list_goals_report

    errors: list[str] = []
    if state is not None and not isinstance(state, dict):
        errors.append("state: inventory must be an object")
    state = state if isinstance(state, dict) else {}
    generation = str(source_generation or state.get("last_event") or "gen-current")
    evidence = source_evidence if isinstance(source_evidence, dict) else {}
    if source_evidence is not None and not isinstance(source_evidence, dict):
        errors.append("source_evidence: provider records must be an object")
    sources: list[dict] = []
    blocked_obligations: list[dict] = []
    agent = current_agent if current_agent is not None else state.get("agent")

    def add(name, result, actions=(), blocker=None, recheck="new evidence arrives", *, checked=True):
        sources.append({
            "source_name": name, "source_generation": generation,
            "last_checked_generation": generation if checked else None,
            "eligibility_result": result, "authorized_actions": list(actions),
            "exact_blocker": blocker, "next_recheck_condition": recheck,
            "checked": checked,
        })

    def unknown(name, detail="provider result not supplied", actions=()):
        add(name, NOT_CHECKED, actions, detail, "provider supplies current evidence", checked=False)

    def projection_fault(name, projection):
        if not isinstance(projection, dict):
            if projection is not None:
                errors.append(f"{name}: provider result must be an object")
            unknown(name)
            return True
        if projection.get("error") or projection.get("corrupt") or projection.get("ok") is False:
            detail = str(projection.get("error") or projection.get("corrupt") or projection.get("detail") or "provider failed")
            errors.append(f"{name}: {detail}")
            unknown(name, detail)
            return True
        observed = projection.get("source_generation")
        if observed is not None and str(observed) != generation:
            unknown(name, "stale provider generation")
            return True
        return False

    def supplied(name):
        record = evidence.get(name)
        if projection_fault(name, record):
            return
        result = record.get("eligibility_result")
        actions = record.get("authorized_actions", ())
        if not isinstance(actions, (list, tuple)) or any(
            not isinstance(action, str) or not action.strip() for action in actions
        ):
            errors.append(f"{name}: invalid discovery action list")
            unknown(name, "invalid discovery action list")
            return
        if result == NOT_CHECKED:
            unknown(name, str(record.get("exact_blocker") or "discovery did not complete"), actions)
            return
        if (
            not isinstance(result, str) or result not in _RESULTS
            or str(record.get("source_generation")) != generation
            or str(record.get("last_checked_generation")) != generation
        ):
            errors.append(f"{name}: missing, invalid or stale discovery result")
            unknown(name, "missing, invalid or stale discovery result")
            return
        detail = str(record.get("exact_blocker") or "") or None
        if "checked" in record and record["checked"] is not True:
            unknown(name, "provider did not complete the discovery", actions)
            return
        add(name, result, actions, detail,
            record.get("next_recheck_condition") or "new evidence arrives")

    inventory_valid = _ticket_inventory_valid(tickets)
    inventory = tickets if inventory_valid else {}
    if tickets is not None and not inventory_valid:
        errors.append("tickets: inventory must be an object of valid ticket objects")
    doing = [t for t in inventory.values() if t.get("section") == "## DOING"]
    groups = project_blockers(inventory)["groups"]
    for group in groups:
        result = _blocker_result(group)
        blocked_obligations.append({
            "source_name": ACTIVE_WORK, "eligibility_result": result,
            "tickets": group["root_tickets"], "exact_blocker": group["root_cause"],
        })
    if not inventory_valid:
        unknown(ACTIVE_WORK)
    elif doing:
        own = [t for t in doing if claim_status(t, agent, now) in ("SELF", "UNCLAIMED")]
        add(ACTIVE_WORK, WORK_AVAILABLE if own else BLOCKED_EXTERNAL,
            ("saipen continue",) if own else (),
            None if own else "active work belongs to another live or invalid claim")
    elif any(item["eligibility_result"] == NOT_CHECKED for item in blocked_obligations):
        errors.append("active_work: unresolved root blocker evidence")
        unknown(ACTIVE_WORK, "root blocker is not verified")
    elif blocked_obligations:
        result = next((c for c in _BLOCKERS if any(b["eligibility_result"] == c for b in blocked_obligations)), DEFERRED)
        add(ACTIVE_WORK, result, blocker=blocked_obligations[0]["exact_blocker"])
    else:
        add(ACTIVE_WORK, CLEAN_VERIFIED)

    supplied(CANONICAL_RECOVERY)
    if recovery_pending:
        sources[-1].update(eligibility_result=WORK_AVAILABLE, authorized_actions=["saipen recover"])
    if not inventory_valid:
        unknown(ACTIONABLE_TODO)
    else:
        workable = workable_tickets(inventory, agent=agent, now=now)
        todo = [t for t in inventory.values() if t.get("section") == "## TODO"]
        add(ACTIONABLE_TODO, WORK_AVAILABLE if workable else DEFERRED if todo else CLEAN_VERIFIED,
            (f"saipen claim {workable[0]}",) if workable else (),
            "TODO dependencies or claim are not satisfied" if todo and not workable else None)
    supplied(UNRESOLVED_SOURCE)

    if not projection_fault(UNCONSUMED_AUDIT_INBOX, audit_inbox):
        try:
            pending = _count(audit_inbox.get("unresolved_audit_count", audit_inbox.get("pending")))
        except ValueError as exc:
            unknown(UNCONSUMED_AUDIT_INBOX, str(exc))
        else:
            if audit_inbox.get("binding_corrupt"):
                unknown(UNCONSUMED_AUDIT_INBOX, "audit binding is corrupt")
            elif audit_inbox.get("unworkable_active_only"):
                result = BLOCKED_OPERATOR if "OPERATOR" in str(audit_inbox.get("idle_classification")) else BLOCKED_EXTERNAL
                add(UNCONSUMED_AUDIT_INBOX, result, blocker="linked audit work is unworkable")
            elif audit_inbox.get("invalid") or audit_inbox.get("residue") or audit_inbox.get("invalid_only") or audit_inbox.get("residue_only"):
                add(UNCONSUMED_AUDIT_INBOX, BLOCKED_EXTERNAL, blocker="invalid or unresolved audit residue")
            elif pending or audit_inbox.get("closed_pending_delete"):
                add(UNCONSUMED_AUDIT_INBOX, WORK_AVAILABLE, ("saipen audit ingest",))
            else:
                add(UNCONSUMED_AUDIT_INBOX, CLEAN_VERIFIED)

    pending_release = [tid for tid, t in inventory.items() if (t.get("fields") or {}).get("publication_state") == "pending"]
    staging = any(g["cause"] == "publication-staging" for g in groups)
    if not inventory_valid:
        unknown(RELEASE_OBLIGATIONS)
    elif staging or pending_release:
        add(RELEASE_OBLIGATIONS, BLOCKED_OPERATOR if staging else BLOCKED_EXTERNAL,
            blocker="foreign staged release scope" if staging else f"pending publication: {', '.join(pending_release)}",
            recheck="durable release or ownership evidence changes")
    else:
        add(RELEASE_OBLIGATIONS, CLEAN_VERIFIED)

    if not projection_fault(FUTURE_GATES, future_gate):
        fresh = future_gate.get("index_state")
        empty = fresh == "MISSING" and future_gate.get("documents") == [] and not future_gate.get("refresh_required")
        if fresh != "CURRENT" and not empty:
            unknown(FUTURE_GATES, "future inventory missing, stale or unreadable", ("saipen future refresh",))
        elif future_gate.get("eligible"):
            add(FUTURE_GATES, WORK_AVAILABLE, (f"saipen future promote {future_gate['eligible'][0]}",))
        elif future_gate.get("refinable"):
            add(FUTURE_GATES, WORK_AVAILABLE, ("saipen future status",))
        elif any(future_gate.get("counts", {}).values()):
            add(FUTURE_GATES, DEFERRED, blocker="future gate prerequisites or holds remain")
        else:
            add(FUTURE_GATES, CLEAN_VERIFIED)

    if hunt_state is None and HUNT_FINDINGS in evidence:
        supplied(HUNT_FINDINGS)
    elif not projection_fault(HUNT_FINDINGS, hunt_state):
        if str(hunt_state.get("last_analyzed_generation")) != generation:
            unknown(HUNT_FINDINGS, "HUNT has not analyzed the current generation")
        else:
            try:
                findings = _count(hunt_state.get("findings"))
            except ValueError as exc:
                unknown(HUNT_FINDINGS, str(exc))
            else:
                add(HUNT_FINDINGS, WORK_AVAILABLE if findings else UNCHANGED,
                    ("saipen status",) if findings else ())

    supplied(IMPROVE_CANDIDATES)
    if not continuous_maintenance_authorized or is_budget_exhausted:
        sources[-1].update(
            eligibility_result=BLOCKED_AUTHORITY, authorized_actions=[],
            exact_blocker="current continuous maintenance grant is not proven",
            next_recheck_condition="authenticated grant restored within its scope",
        )
    if forensic_state is None and EXTERNAL_FORENSICS in evidence:
        supplied(EXTERNAL_FORENSICS)
    elif not projection_fault(EXTERNAL_FORENSICS, forensic_state):
        try:
            unfinished = _count(forensic_state.get("unfinished_slices"))
        except ValueError as exc:
            unknown(EXTERNAL_FORENSICS, str(exc))
        else:
            add(EXTERNAL_FORENSICS, WORK_AVAILABLE if unfinished else CLEAN_VERIFIED,
                ("saipen sub",) if unfinished else ())
    supplied(CONFORMANCE_DEBT)

    goal_evidence = persistent_goals
    if goal_evidence is None and root is not None:
        try:
            goal_evidence = list_goals_report(root)
        except Exception as exc:
            goal_evidence = {"goals": [], "complete": False, "errors": [f"loader raised {type(exc).__name__}: {exc}"]}
    goals = goal_inventory(goal_evidence)
    errors.extend(f"{PERSISTENT_GOALS}: {e}" for e in goals["errors"])
    errors.extend(f"{PERSISTENT_GOALS}: unreadable {p}" for p in goals["unreadable"])
    active = [g for g in goals["goals"] if not (g.get("paused", False) if isinstance(g, dict) else g.paused)]
    statuses = [g.get("current_status", "ACTIVE") if isinstance(g, dict) else g.current_status for g in active]
    if any(s in ("ACTIVE", "ACTIONABLE_GAPS", "DISCOVERY_REQUIRED", "VERIFICATION_REQUIRED") for s in statuses):
        add(PERSISTENT_GOALS, WORK_AVAILABLE, ("saipen continue",), checked=goals["complete"])
    elif not goals["complete"] or "BLOCKED_BY_EVIDENCE" in statuses:
        unknown(PERSISTENT_GOALS, "goal inventory or evaluation is incomplete")
    elif "WAITING_AUTHORITY" in statuses:
        add(PERSISTENT_GOALS, BLOCKED_AUTHORITY, blocker="goal requires authenticated authority")
    elif "WAITING_DEPENDENCY" in statuses:
        add(PERSISTENT_GOALS, BLOCKED_EXTERNAL, blocker="goal dependency remains unavailable")
    elif "NO_ADMISSIBLE_WORK" in statuses or len(active) < len(goals["goals"]):
        add(PERSISTENT_GOALS, DEFERRED, recheck="goal evaluation evidence or pause state changes")
    else:
        add(PERSISTENT_GOALS, CLEAN_VERIFIED)

    all_checked = all(s["checked"] for s in sources) and not errors
    available = any(s["eligibility_result"] == WORK_AVAILABLE for s in sources)
    blocked = [s for s in sources if s["eligibility_result"] in _BLOCKERS]
    if available:
        status = WORK_ELIGIBLE
    elif not all_checked:
        status = INCOMPLETE_DISCOVERY
    else:
        status = next((c for c in _BLOCKERS if any(s["eligibility_result"] == c for s in blocked)), VERIFIED_QUIESCENT)
    exhausted = status == VERIFIED_QUIESCENT and all_checked
    return {
        "schema_version": SCHEMA_VERSION, "status": status,
        "legacy_status": EXHAUSTED_QUIESCENT if exhausted else status,
        "source_generation": generation, "sources": sources,
        "exhausted": exhausted, "verified_exhausted": exhausted,
        "no_work_available": not available, "all_checked": all_checked,
        "blocked_sources": list(dict.fromkeys(s["source_name"] for s in (*blocked, *blocked_obligations))),
        "blocked_obligations": blocked_obligations, "certificate_errors": errors,
    }

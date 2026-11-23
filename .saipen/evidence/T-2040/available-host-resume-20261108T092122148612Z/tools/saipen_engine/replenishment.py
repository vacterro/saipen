"""Self-Replenishing Task Queue & Goal-Aware Continuation (SRC-367 Section 6 & 7).



When the current ticket queue is empty:

1. Enumerate active persistent goals.

2. Evaluate actual evidence against registered providers.

3. Identify unsatisfied requirements.

4. Produce bounded candidate tasks.

5. Deduplicate against active, pending, completed, superseded, and blocked tickets.

6. Validate scope, dependencies, and authorization.

7. Admit the highest-priority permitted task through canonical intake (operations.ticket_add).

8. Report truthful disposition instead of ambiguous NO_WORK.

"""



from __future__ import annotations



import json

import re

from pathlib import Path

from typing import Any



from .discovery_providers import (

    COMPLETION_UNKNOWN,

    FRESHNESS_UNMEASURED,

    CandidateTask,

    ProviderEvaluation,

    get_provider,

)

from .persistent_goal import (

    PersistentGoal,

    STATUS_ACTIONABLE_GAPS,

    STATUS_ACTIVE,

    STATUS_BLOCKED_BY_EVIDENCE,

    STATUS_SATISFIED,

    STATUS_WAITING_AUTHORITY,

    STATUS_WAITING_DEPENDENCY,

    list_goals,

    save_goal,

    _now_utc,

)





def _parse_board_tickets(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Project canonical descriptions, resolving the existing detail authority."""
    from . import codec
    from .board import parse_board
    from .board_compaction import resolve_detail
    from .journal import hash_file_dependency

    root = Path(root)
    sections: dict[str, list[dict[str, Any]]] = {
        name: [] for name in ("doing", "todo", "done", "blocked")
    }
    board_path = root / ".saipen/BOARD.md"
    if not board_path.is_file():
        return sections
    parsed = parse_board(codec.read_doc(board_path))
    if parsed["errors"]:
        raise ValueError("BOARD parse error(s): " + "; ".join(parsed["errors"][:3]))
    for ticket in parsed["tickets"].values():
        description = ticket["description"]
        reference = str(ticket["fields"].get("detail_ref") or "").strip()
        identity_preconditions = {}
        while reference:
            identity_preconditions[reference] = hash_file_dependency(root / reference)
            detail = resolve_detail(root, reference, expected_ticket_id=ticket["id"])
            metadata = detail["metadata"]
            identity_preconditions[metadata["original_record_path"]] = detail["sha256"][:16]
            original = parse_board(
                "## DOING\n" + detail["original_record"].decode("utf-8").rstrip("\n")
                + "\n## TODO\n## DONE\n## BLOCKED\n"
            )["tickets"][ticket["id"]]
            description = original["description"]
            reference = str(original["fields"].get("detail_ref") or "").strip()
            if _identity_marker(description, "candidate") or not description.endswith("..."):
                break
        sections[ticket["section"][3:].lower()].append({
            "id": ticket["id"], "state": ticket["checkbox"],
            "text": description, "raw": ticket["raw"], "fields": ticket["fields"],
            "needs": ticket["needs"], "root": root,
            "identity_preconditions": identity_preconditions,
        })
    return sections





def _identity_marker(text: str, name: str) -> list[str]:
    """Read complete identity atoms, never a candidate/fingerprint prefix."""
    return re.findall(rf"(?<![\w.-]){re.escape(name)}:\s*([^\s|\[\]]+)", text, re.IGNORECASE)


def _matches_candidate(candidate: CandidateTask, ticket_text: str) -> bool:
    """Match exact goal/candidate identity in descriptions, retaining legacy tags."""
    if not candidate.candidate_id:
        return False
    goals = _identity_marker(ticket_text, "goal")
    if candidate.goal_id:
        if goals:
            if goals != [candidate.goal_id]:
                return False
        elif f"[{candidate.goal_id}]" not in ticket_text:
            return False
    markers = _identity_marker(ticket_text, "candidate")
    if markers:
        return markers == [candidate.candidate_id]
    if candidate.candidate_id in re.findall(r"[\w.-]+", ticket_text):
        return True
    if candidate.target_locator and re.search(
        rf"\b(?:item:|locator:|rva\s*:?\s*){re.escape(candidate.target_locator)}(?![\w.-])",
        ticket_text, re.IGNORECASE,
    ):
        return True
    return bool(candidate.goal_id and candidate.title and re.search(
        rf"(?<!\w){re.escape(candidate.title)}(?!\w)", ticket_text, re.IGNORECASE
    ))





def _is_candidate_duplicate(
    candidate: CandidateTask,
    board_sections: dict[str, list[dict[str, Any]]],
) -> tuple[bool, str | None]:
    """Deduplicate Work; expose one verified authority-only recovery to discovery."""
    for section in ("doing", "todo", "done"):
        for ticket in board_sections[section]:
            if not _matches_candidate(candidate, ticket["text"]):
                continue
            fingerprints = _identity_marker(ticket["text"], "evidence_fp")
            if (section == "done" and candidate.evidence_fingerprint
                    and len(fingerprints) == 1
                    and fingerprints[0] != candidate.evidence_fingerprint):
                continue
            reason = "ALREADY_DONE" if section == "done" else f"ALREADY_IN_{section.upper()}"
            return True, f"{reason}:{ticket['id']}"
    blocked = [ticket for ticket in board_sections["blocked"]
               if _matches_candidate(candidate, ticket["text"])]
    if blocked:
        ticket = blocked[0]
        if len(blocked) == 1 and ticket.get("root") is not None:
            if _maintenance_recovery_preconditions(ticket["root"], candidate, ticket) is not None:
                return False, f"RESTORE_BLOCKED:{ticket['id']}"
        return True, f"ALREADY_BLOCKED:{ticket['id']}"
    return False, None


def _maintenance_recovery_preconditions(
    root: Path, candidate: CandidateTask, ticket: dict[str, Any],
) -> dict[str, str] | None:
    """Prove the narrow recovery boundary without changing Source or Work."""
    from . import codec, goal_authority, intake
    from .board import parse_board
    from .journal import hash_file_dependency
    from .state import parse_state

    fields = ticket["fields"]
    blocker = str(fields.get("blocker") or "")
    head, _, reason = blocker.partition(" -- ")
    if head.strip() != "CONTINUATION_AUTHORITY_UNPROVEN":
        return None
    if (fields.get("blocker_scope", "ticket") != "ticket"
            or any(fields.get(name) for name in ("blocked_on", "retry_not_before", "verify_attempts"))
            or re.search(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", reason)
            or re.search(r"\b(?:external|publication|release|vendor|manual|dependency|"
                         r"dependencies|corrupt|corruption|failure|failures|upstream|network)\b",
                         reason, re.IGNORECASE)):
        return None
    if (not candidate.evidence_fingerprint
            or _identity_marker(ticket["text"], "goal") != [candidate.goal_id]
            or _identity_marker(ticket["text"], "candidate") != [candidate.candidate_id]
            or _identity_marker(ticket["text"], "evidence_fp") != [candidate.evidence_fingerprint]):
        return None
    try:
        preconditions = dict(ticket.get("identity_preconditions") or {})
        for rel in (".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/intake/index.json"):
            preconditions[rel] = hash_file_dependency(root / rel)
        state = parse_state(codec.read_doc(root / ".saipen/STATE.md"))
        board = parse_board(codec.read_doc(root / ".saipen/BOARD.md"))
        current = board["tickets"].get(ticket["id"])
        if board["errors"] or not current or current["raw"] != ticket["raw"]:
            return None
        if (state.get("authority_until") != "continuous_maintenance"
                or goal_authority.budget_exhausted(state)
                or (str(state.get("next_action") or "").startswith("WAIT:")
                    and "CONTINUATION_AUTHORITY_UNPROVEN" not in state["next_action"])):
            return None
        authority = maintenance_authority(root)
        if not authority.get("authorized") or not authority.get("policy_digest"):
            return None
        goals = goal_authority.active_maintenance_goals(root)
        if len(goals) != 1 or goals[0].goal_id != candidate.goal_id:
            return None
        if (goal_authority.maintenance_goal_digest(goals[0]) != authority["policy_digest"]
                or goal_authority.maintenance_policy_drift(root, candidate.goal_id, authority["policy_digest"])
                or candidate.scope.split(":", 1)[0].lower() in goal_authority.MAINTENANCE_EXCLUDED_ACTIONS):
            return None
        dependencies = set(current["needs"]) | set(candidate.needs)
        if any(dep not in board["tickets"] or board["tickets"][dep]["section"] != "## DONE"
               for dep in dependencies):
            return None
        receipts = [item.strip() for item in str(fields.get("source_receipts") or "").split(",")
                    if item.strip()]
        if not receipts:
            return None
        index = intake._read_index(root)
        for receipt in receipts:
            if not intake._valid_receipt_id(receipt):
                return None
            meta_rel = f".saipen/intake/active/{receipt}.meta.json"
            preconditions[meta_rel] = hash_file_dependency(root / meta_rel)
            body = intake.read_body(root, receipt)
            if (not body.get("ok") or body.get("location") != "active"
                    or not intake.is_linked_to(body.get("meta"), ticket["id"])
                    or not intake.is_linked_to(index["active"].get(receipt), ticket["id"])):
                return None
            meta = body["meta"]
            body_rel = intake._canonical_body_rel(root, receipt, meta["source_sha256"], "active")
            preconditions[body_rel] = meta["source_sha256"][:16]
        return preconditions
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _restore_maintenance_candidate(
    root: Path, agent: str, goal: PersistentGoal, candidate: CandidateTask,
    ticket_id: str, *, dry_run: bool,
) -> dict[str, Any]:
    """Use the canonical unblock plan, pinning the Source membership it consumes."""
    from dataclasses import replace
    from . import goal_authority, operations
    from .plan import apply_plan
    from .result import Result

    refused = {"ok": False, "replenished": False, "status": "RECOVERY_BLOCKED",
               "admitted_ticket": ticket_id, "goal_id": goal.goal_id,
               "detail": "existing Work no longer has verified authority-only recovery evidence"}
    try:
        board = _parse_board_tickets(root)
        ticket = next((row for row in board["blocked"] if row["id"] == ticket_id), None)
        if ticket is None:
            return refused
        preconditions = _maintenance_recovery_preconditions(root, candidate, ticket)
        authority = maintenance_authority(root)
        if (preconditions is None or not authority.get("authorized")
                or goal_authority.maintenance_goal_digest(goal) != authority.get("policy_digest")):
            return refused
        plan = operations._ticket_targets(
            root, "unblock", ticket_id, agent,
            f"verified standing maintenance grant for {goal.goal_id}; exact candidate "
            f"{candidate.candidate_id}; pinned Source integrity and dependencies satisfied",
            operations._now(), operations._utc_iso(),
        )
        if isinstance(plan, Result):
            return {**refused, "code": plan.code, "detail": plan.message}
        # Earlier evidence wins: a later canonical read must not launder drift.
        plan = replace(plan, preconditions={**plan.preconditions, **preconditions})
        result = operations._render_plan(plan) if dry_run else apply_plan(root, plan)
        if not result.ok:
            return {**refused, "code": result.code, "detail": result.message}
    except (OSError, ValueError, TypeError, KeyError, operations.CheckpointError) as exc:
        return {**refused, "detail": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True, "replenished": True, "status": "TASK_REPLENISHED",
        "dry_run": dry_run, "reused_work": True, "admitted_ticket": ticket_id,
        "goal_id": goal.goal_id, "candidate": candidate.to_dict(),
        "action": f"PHASE SCOUT {ticket_id}", "next_action": f"PHASE SCOUT {ticket_id}",
        "detail": f"{'would restore' if dry_run else 'restored'} existing Work {ticket_id}",
    }





def evaluate_all_goals(

    root: Path | str,

    *,

    commit: bool = False,

) -> list[tuple[PersistentGoal, ProviderEvaluation]]:

    """Evaluate all active persistent goals against their declared evidence providers.

    

    Pure evaluation by default: does NOT write to disk unless commit=True.

    """

    root = Path(root)

    goals = list_goals(root)

    results: list[tuple[PersistentGoal, ProviderEvaluation]] = []



    for goal in goals:

        if goal.paused:

            continue

        provider = get_provider(goal.evidence_provider)

        if provider is None:

            eval_res = ProviderEvaluation(

                provider_name=goal.evidence_provider,

                provider_kind="UNKNOWN",

                evidence_identity="absent",

                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,

                completeness_status=COMPLETION_UNKNOWN,

                evidence_freshness=FRESHNESS_UNMEASURED,

                blockers=[f"Unknown evidence provider: {goal.evidence_provider}"],

                summary=f"Provider {goal.evidence_provider} is not registered",

            )

        else:

            try:
                eval_res = provider.evaluate(root, goal)
            except Exception as exc:
                eval_res = ProviderEvaluation(
                    provider_name=goal.evidence_provider,
                    provider_kind="UNKNOWN", evidence_identity="unavailable",
                    satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                    completeness_status=COMPLETION_UNKNOWN,
                    evidence_freshness=FRESHNESS_UNMEASURED,
                    blockers=[f"{goal.evidence_provider}: {type(exc).__name__}: {exc}"],
                    summary="Goal discovery failed; completeness is unverified",
                )



        # Update in-memory goal progress

        goal.last_evaluation = _now_utc()

        goal.current_status = eval_res.satisfaction_status

        if eval_res.metrics:

            goal.current_progress = eval_res.metrics

        goal.blockers = eval_res.blockers

        if eval_res.satisfaction_status == STATUS_SATISFIED:

            goal.completion_evidence = {

                "satisfied_at": _now_utc(),

                "evidence_identity": eval_res.evidence_identity,

                "summary": eval_res.summary,

            }

        if commit:

            save_goal(root, goal)

        results.append((goal, eval_res))



    return results





def maintenance_blocker_fingerprint(
    root: Path, *, authority_kind: str, scope: str = "continuous_maintenance"
) -> dict:
    """Evidence-based identity of THIS maintenance-authority WAIT (SRC-392 fifth).

    The agent repeatedly re-ran the same deterministic `goal-waiting-authority`
    diagnostic because nothing named the WAIT's identity or its wake condition.
    This bundles exactly the inputs SRC-392 requires -- blocker code, project
    and goal identity, host capability generation, broker identity, authorization
    proof generation, source tree fingerprint and the verified wake condition --
    into one digest. An unchanged digest means unchanged evidence: the same
    diagnostic command must not be repeated, and a new ticket must not be opened
    merely to re-investigate. Any real change (a new grant, a new goal pivot, a
    repaired broker, fresh source) moves at least one input and therefore the
    digest.

    Never raises: a fingerprint is a diagnostic projection and must not become a
    new failure surface.
    """
    from . import codec, goal_authority
    from .liveness import action_fingerprint
    from .state import parse_state
    from .paths import project_lineage_identity

    def _safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    project = str(root.resolve())
    state = _safe(lambda: parse_state(codec.read_doc(root / ".saipen/STATE.md"))) or {}
    lineage = _safe(lambda: project_lineage_identity(root), "") or ""
    goal_ingress = str(state.get("goal_ingress") or "")
    authority_source = str(state.get("authority_source") or "")

    broker = _safe(lambda: __import__("saipen_engine.host_authority_client", fromlist=["status"]).status())
    broker_id = ""
    broker_generation = ""
    if isinstance(broker, dict):
        broker_id = str(broker.get("instance") or "")
        broker_generation = str(broker.get("generation") or "")

    source_fingerprint = _safe(
        lambda: __import__("saipen_engine.core_unit", fromlist=["tree_fingerprint"]).tree_fingerprint(root),
        "",
    )

    digest = action_fingerprint(
        stage="maintenance-authority",
        action="admit-maintenance-work",
        reason=authority_kind,
        source=source_fingerprint,
        role=f"{project}|{lineage}|{goal_ingress}|{authority_source}|{broker_id}|{broker_generation}|{scope}",
    )
    return {
        "code": "CONTINUATION_AUTHORITY_UNPROVEN",
        "digest": digest,
        "authority_kind": authority_kind,
        "project": project,
        "project_lineage": lineage,
        "goal_ingress": goal_ingress,
        "authority_source": authority_source,
        "scope": scope,
        "broker_instance": broker_id,
        "broker_generation": broker_generation,
        "source_fingerprint": source_fingerprint,
        "wake_condition": (
            "authorized:true returns from maintenance_authority -- a committed "
            "standing maintenance grant for this goal (saipen goal propose, then "
            "operator confirms and applies: saipen goal authorize --file <PATH>)"
        ),
    }


def granted_maintenance_policy_digest(root: Path | str) -> str | None:
    """The canonical policy digest of the SINGLE granted maintenance goal.

    SRC-395 P0. None when the project has no unambiguous active MAINTENANCE
    goal -- in that case there is no granted policy to bind, and the admission
    path performs no drift check (an unauthorized admission is refused by the
    authority gate itself, not by a policy comparison).
    """
    from . import goal_authority

    goals = goal_authority.active_maintenance_goals(root)
    if len(goals) != 1:
        return None
    return goal_authority.maintenance_goal_digest(goals[0])


def maintenance_authority(root: Path) -> dict:
    """Read the existing grant owner; a goal's scope label is never a grant.

    SRC-392 R001: two DIFFERENT authorities are answered here, and conflating
    them is the defect this return value must never reintroduce.

    * A protocol-home identity (SRC-249) permits exactly ONE documented
      exception -- its own goal budget checkpoint clears on `cc` without an
      operator. It does NOT permit discovering or admitting new maintenance
      work, so it is never reported as `authorized`.
    * A separate, operator-approved, scope-bound standing maintenance grant
      (the committed `saipen-goal-continuation` capsule with
      `authority_until: continuous_maintenance`) is what actually permits
      autonomous discovery and admission of new self-maintenance work.

    Only the second kind may return `authorized: True`. The refusal body names
    which of the two is missing so a reader cannot mistake a self-clearing
    budget checkpoint for standing mutation permission.
    """
    from . import codec, goal_authority
    from .state import parse_state

    try:
        state = parse_state(codec.read_doc(root / ".saipen/STATE.md"))
        if goal_authority.continuous_maintenance_proven(root, state):
            # SRC-395 P0: a grant is bound to the granted POLICY, not to the
            # bare fact of authorization. The admission path carries this digest
            # so a goal-file edit landing between this decision and the ticket
            # write is refused instead of riding an already-green proof.
            return {
                "authorized": True,
                "authority_kind": "standing_maintenance_grant",
                "policy_digest": granted_maintenance_policy_digest(root),
            }
        home = goal_authority.protocol_home(root)
        if home:
            # The protocol home is NOT an unproven claim: its budget checkpoint
            # is legitimate and self-clearing. It is still not a maintenance
            # grant, and saying so here is the whole point (SRC-392 R001).
            reason = (
                "Protocol-home identity permits the documented budget-checkpoint "
                "exception only; it does not permit autonomous discovery or "
                "admission of new maintenance work. A separate scope-bound "
                "standing maintenance grant is required."
            )
            authority_kind = "protocol_home_checkpoint_only"
        else:
            reason = "No verified standing maintenance grant is bound to the current goal"
            authority_kind = "none"
    except (OSError, ValueError, TypeError) as exc:
        reason = f"Maintenance grant evidence unavailable: {type(exc).__name__}: {exc}"
        authority_kind = "unavailable"
    return {
        "authorized": False,
        "authority_kind": authority_kind,
        "canonical_next_command": "saipen goal propose",
        "operator_action": (
            "Operaator kinnitab selle projekti ja eesmärgi kohaliku hoolduse kapsli "
            "ning rakendab saipen goal authorize --file <UTF8_FILE>."
        ),
        "required_scope": "continuous_maintenance",
        "project": str(root.resolve()),
        "checkpoint_ticket_limit": goal_authority.GOAL_TICKET_CAP,
        "checkpoint_wave_limit": goal_authority.GOAL_WAVE_CAP,
        "blocker_fingerprint": maintenance_blocker_fingerprint(
            root, authority_kind=authority_kind, scope="continuous_maintenance"
        ),
        "detail": reason,
    }


def replenish_from_goals(

    project_root: Path | str,

    agent: str,

    *,

    as_json: bool = False,

    dry_run: bool = False,

) -> dict[str, Any]:

    """Examine persistent goals and admit the next legitimate bounded task if queue is empty.



    Returns structured outcome dict.

    """

    root = Path(project_root)

    try:
        board = _parse_board_tickets(root)
    except (OSError, ValueError, UnicodeError) as exc:
        return {"ok": False, "replenished": False, "status": "BOARD_INVALID", "detail": str(exc)}

    if board["doing"]:

        return {

            "ok": True,

            "replenished": False,

            "status": "DOING_ACTIVE",

            "active_ticket": board["doing"][0]["id"],

            "detail": f"active ticket {board['doing'][0]['id']} currently in DOING",

        }

    from .board import parse_board, ticket_is_workable

    parsed = parse_board((root / ".saipen/BOARD.md").read_text(encoding="utf-8"))["tickets"]
    runnable = [
        row for row in board["todo"]
        if ticket_is_workable(parsed[row["id"]], parsed, agent=agent)
    ]
    if runnable:

        return {

            "ok": True,

            "replenished": False,

            "status": "TODO_AVAILABLE",

            "next_ticket": runnable[0]["id"],

            "detail": f"workable ticket {runnable[0]['id']} waiting in TODO",

        }



    goals = [g for g in list_goals(root) if not g.paused]

    if not goals:

        return {

            "ok": True,

            "replenished": False,

            "status": "NO_PERSISTENT_GOALS",

            "detail": "no active persistent goals defined for this project",

            "goals_count": 0,

        }



    from .operations import ticket_add



    evaluated = evaluate_all_goals(root, commit=False)

    all_satisfied = True

    any_gaps = False

    candidates_pool: list[tuple[PersistentGoal, CandidateTask]] = []

    reasons_blocked: list[str] = []



    for goal, eval_res in evaluated:

        if eval_res.satisfaction_status != STATUS_SATISFIED:

            all_satisfied = False



        if eval_res.satisfaction_status == STATUS_ACTIONABLE_GAPS:

            any_gaps = True

            for cand in eval_res.actionable_candidates:

                is_dup, dup_reason = _is_candidate_duplicate(cand, board)

                if is_dup:

                    if dup_reason and "BLOCKED" in dup_reason:

                        reasons_blocked.append(f"{cand.candidate_id}:{dup_reason}")

                    continue

                unresolved = [
                    dependency for dependency in cand.needs
                    if dependency not in parsed or parsed[dependency].get("section") != "## DONE"
                ]
                if unresolved:
                    reasons_blocked.append(
                        f"{cand.candidate_id}:WAITING_DEPENDENCY:{','.join(unresolved)}"
                    )
                    continue

                candidates_pool.append((goal, cand))



        if eval_res.blockers:

            reasons_blocked.extend(eval_res.blockers)



    if all_satisfied:

        return {

            "ok": True,

            "replenished": False,

            "status": "GOAL_SATISFIED",

            "detail": "all declared persistent goals are satisfied",

            "goals": [g.to_dict() for g, _ in evaluated],

        }



    if not candidates_pool:

        status = "ALL_CANDIDATES_BLOCKED" if reasons_blocked else ("GOAL_GAPS_UNVERIFIED" if any_gaps else "NO_ADMISSIBLE_WORK")

        return {

            "ok": True,

            "replenished": False,

            "status": status,

            "detail": f"persistent goals remain incomplete but no new admissible task could be selected (blockers: {', '.join(reasons_blocked) if reasons_blocked else 'none'})",

            "blockers": reasons_blocked,

            "goals": [g.to_dict() for g, _ in evaluated],

        }



    # Select candidate with highest priority (P0 > P1 > P2 > P3)

    prio_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

    candidates_pool.sort(key=lambda pair: prio_order.get(pair[1].priority.upper(), 9))

    # Rank permitted work, so an unrelated release candidate cannot starve it.
    denied = []
    maintenance = None
    for selected_goal, selected_task in candidates_pool:
        auth_scope = selected_goal.authorization_scope.upper()
        if auth_scope == "MAINTENANCE":
            if maintenance is None:
                maintenance = maintenance_authority(root)
            if maintenance["authorized"]:
                break
            authority = maintenance
        elif auth_scope in ("RESEARCH", "IMPLEMENTATION", "TEST_CAMPAIGN"):
            break
        else:
            authority = {
                "authorized": False,
                "detail": (
                    f"candidate {selected_task.candidate_id} requires explicit "
                    f"verified authority for scope {auth_scope}"
                ),
            }
        denied.append({
            "ok": True, "replenished": False, "status": "WAITING_AUTHORITY",
            "goal_id": selected_goal.goal_id, "selected_candidate": selected_task.to_dict(),
            **authority,
        })
    else:
        return denied[0]



    # A recoverable duplicate is existing Work, never a replacement admission.
    recoveries = [row for row in board["blocked"]
                  if _matches_candidate(selected_task, row["text"])]
    if recoveries:
        if len(recoveries) != 1:
            return {"ok": False, "replenished": False, "status": "RECOVERY_BLOCKED",
                    "detail": "candidate has ambiguous blocked Work identity"}
        return _restore_maintenance_candidate(
            root, agent, selected_goal, selected_task, recoveries[0]["id"], dry_run=dry_run,
        )

    # Format ticket description and verify text

    fp_tag = f" | evidence_fp: {selected_task.evidence_fingerprint}" if getattr(selected_task, "evidence_fingerprint", None) else ""

    desc = f"{selected_task.title} | goal: {selected_goal.goal_id} | candidate: {selected_task.candidate_id}{fp_tag}"

    verify_text = selected_task.verification



    if dry_run:

        return {

            "ok": True,

            "replenished": True,

            "dry_run": True,

            "status": "TASK_REPLENISHED",

            "goal_id": selected_goal.goal_id,

            "candidate": selected_task.to_dict(),

            "planned_ticket": "T-PLANNED",

            "detail": f"would admit {selected_task.candidate_id} for goal {selected_goal.goal_id}",

        }



    # SRC-395 P0 (TOCTOU): the authority proof above read the goal file at the
    # moment of the decision. Re-read it now, immediately before the write, so a
    # policy edit landing in between refuses this admission instead of riding an
    # already-green proof. Only a granted maintenance admission carries a policy
    # to bind; an unbound scope performs no comparison.
    if maintenance is not None and maintenance.get("authorized"):
        from . import goal_authority

        drift = goal_authority.maintenance_policy_drift(
            root, selected_goal.goal_id, maintenance.get("policy_digest")
        )
        if drift:
            return {
                "ok": False,
                "replenished": False,
                "status": "ADMISSION_POLICY_DRIFT",
                "goal_id": selected_goal.goal_id,
                "candidate": selected_task.to_dict(),
                "blockers": drift,
                "detail": drift[0],
            }

    # Commit ticket admission via SAIOPS

    add_res = ticket_add(

        project_root=root,

        agent=agent,

        priority=selected_task.priority,

        description=desc,

        needs=selected_task.needs,

        verify=verify_text,

        dry_run=False,

    )



    if not add_res.ok:

        return {

            "ok": False,

            "replenished": False,

            "status": "ADMISSION_FAILED",

            "detail": f"ticket_add failed: {add_res.message}",

        }



    admitted_tid = str(add_res.data.get("ticket") or "")



    # Update goal state

    selected_goal.last_discovery = selected_task.candidate_id

    selected_goal.last_evaluation = _now_utc()

    save_goal(root, selected_goal)



    return {

        "ok": True,

        "replenished": True,

        "status": "TASK_REPLENISHED",

        "admitted_ticket": admitted_tid,

        "goal_id": selected_goal.goal_id,

        "candidate": selected_task.to_dict(),

        "action": f"PHASE SCOUT {admitted_tid}",

        "next_action": f"PHASE SCOUT {admitted_tid}",

        "detail": f"admitted task {admitted_tid} ({selected_task.candidate_id}) from persistent goal {selected_goal.goal_id}",

    }


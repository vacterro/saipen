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





def _parse_board_tickets(root: Path) -> dict[str, list[dict[str, str]]]:

    """Parse BOARD into sections: doing, todo, done, blocked."""

    board_path = root / ".saipen" / "BOARD.md"

    sections: dict[str, list[dict[str, str]]] = {

        "doing": [],

        "todo": [],

        "done": [],

        "blocked": [],

    }

    if not board_path.is_file():

        return sections



    current_section: str | None = None

    try:

        lines = board_path.read_text(encoding="utf-8").splitlines()

    except OSError:

        return sections



    import re



    for line in lines:

        line_s = line.strip()

        if line_s == "## DOING":

            current_section = "doing"

            continue

        elif line_s == "## TODO":

            current_section = "todo"

            continue

        elif line_s == "## DONE":

            current_section = "done"

            continue

        elif line_s == "## BLOCKED":

            current_section = "blocked"

            continue

        elif line_s.startswith("## "):

            current_section = None

            continue



        if current_section and line_s.startswith("- ["):

            # Extract ticket ID and text

            m = re.match(r"^-\s*\[([ x/\-])\]\s*(T-\d+)\s*(.*)", line_s)

            if m:

                state, tid, rest = m.groups()

                sections[current_section].append({

                    "id": tid,

                    "state": state,

                    "text": rest,

                    "raw": line_s,

                })

    return sections





def _matches_candidate(candidate: CandidateTask, ticket_text: str) -> bool:

    """Accurately match a candidate task against ticket text without arbitrary substring collisions."""

    text_l = ticket_text.lower()

    needle_id = candidate.candidate_id.lower()

    needle_marker = f"candidate: {needle_id}"

    if needle_marker in text_l:

        return True

    if f"[{needle_id}]" in text_l:

        return True

    words = re.findall(r"[a-z0-9_.-]+", text_l)

    if needle_id in words:

        return True

    if candidate.target_locator:

        loc = candidate.target_locator.lower()

        if (

            f"item:{loc}" in text_l

            or f"locator:{loc}" in text_l

            or f"rva {loc}" in text_l

            or f"rva:{loc}" in text_l

            or (loc.startswith("0x") and loc in text_l)

        ):

            if not candidate.goal_id or candidate.goal_id.lower() in text_l:

                return True

    # Match goal and title if both explicitly appear

    if candidate.goal_id and f"[{candidate.goal_id.lower()}]" in text_l:

        if candidate.title and candidate.title.lower() in text_l:

            return True

    return False





def _is_candidate_duplicate(

    candidate: CandidateTask,

    board_sections: dict[str, list[dict[str, str]]],

) -> tuple[bool, str | None]:

    """Check if a candidate task is already active, pending, done, or blocked on board."""

    # Check DOING & TODO

    for section_name in ("doing", "todo"):

        for t in board_sections[section_name]:

            if _matches_candidate(candidate, t["text"]):

                return True, f"ALREADY_IN_{section_name.upper()}:{t['id']}"



# Check DONE: distinguish genuine replay from new evidence after earlier repair
    for t in board_sections["done"]:
        if _matches_candidate(candidate, t["text"]):
            cand_fp = getattr(candidate, "evidence_fingerprint", None)
            if cand_fp and "evidence_fp:" in t["text"]:
                m_fp = re.search(r"evidence_fp:\s*([a-zA-Z0-9_:-]+)", t["text"])
                if m_fp and m_fp.group(1) != cand_fp:
                    continue  # New evidence generation for the same item
            return True, f"ALREADY_DONE:{t['id']}"



    # Check BLOCKED

    for t in board_sections["blocked"]:

        if _matches_candidate(candidate, t["text"]):

            return True, f"ALREADY_BLOCKED:{t['id']}"



    return False, None





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

    board = _parse_board_tickets(root)

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


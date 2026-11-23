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

    CandidateTask,

    ProviderEvaluation,

    get_provider,

)

from .persistent_goal import (

    PersistentGoal,

    STATUS_ACTIONABLE_GAPS,

    STATUS_ACTIVE,

    STATUS_BLOCKED_BY_EVIDENCE,

    STATUS_NO_ADMISSIBLE_WORK,

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

                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,

                blockers=[f"Unknown evidence provider: {goal.evidence_provider}"],

                summary=f"Provider {goal.evidence_provider} is not registered",

            )

        else:

            eval_res = provider.evaluate(root, goal)



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

    if board["todo"]:

        return {

            "ok": True,

            "replenished": False,

            "status": "TODO_AVAILABLE",

            "next_ticket": board["todo"][0]["id"],

            "detail": f"unclaimed ticket {board['todo'][0]['id']} waiting in TODO",

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

    selected_goal, selected_task = candidates_pool[0]



    # Check authority requirements: e.g. operator_required or destructive scopes

    auth_scope = selected_goal.authorization_scope.upper()

    if auth_scope in ("DESTRUCTIVE", "RELEASE"):

        return {

            "ok": True,

            "replenished": False,

            "status": "WAITING_AUTHORITY",

            "detail": f"candidate {selected_task.candidate_id} requires {auth_scope} authority which must be granted explicitly",

            "selected_candidate": selected_task.to_dict(),

        }



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


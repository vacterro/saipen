"""GOAL-01: one continuation grant, independent of who invokes continue.

STATE records the scope. The existing source/journal owners prove its origin;
an invocation, a remembered request or a convenient counter value proves none.
"""

from __future__ import annotations

import re
from pathlib import Path

FIELDS = ("continuation_authority", "authority_source", "authority_until", "safety_valve_mode")


def grant_fields(source: str) -> dict:
    return dict(zip(FIELDS, ("operator_persistent", source, "goal_complete", "checkpoint")))


def shape_errors(state: dict) -> list[str]:
    present = [key for key in FIELDS if key in state]
    if not present:
        return []  # Legacy goals are bounded; absence never grants persistence.
    if state.get("execution_intent") != "goal":
        return ["continuation authority is legal only with execution_intent goal"]
    if len(present) != len(FIELDS):
        return ["continuation authority requires the complete authority family"]
    from .registry import load_registry, require_mapping

    policy = require_mapping(load_registry(), "goal_authority")
    for field, key in ((FIELDS[0], "continuation"), (FIELDS[2], "until"), (FIELDS[3], "valve")):
        if state.get(field) not in policy[key]:
            return [f"{field} outside its closed enum"]
    persistent = state[FIELDS[0]] == "operator_persistent"
    expected = ("goal_complete", "checkpoint") if persistent else ("budget", "hard_wait")
    if (state[FIELDS[2]], state[FIELDS[3]]) != expected:
        return ["continuation authority has an inconsistent scope/valve tuple"]
    source = state.get("authority_source")
    if not isinstance(source, str) or not re.fullmatch(r"(?:E|SRC)-0*[1-9][0-9]*", source):
        return ["authority_source must name its SRC or GOAL event"]
    if persistent and not re.fullmatch(r"goal-[0-9a-f]{16}", str(state.get("goal_ingress") or "")):
        return ["persistent authority requires its goal_ingress binding"]
    return []


def persistent(state: dict) -> bool:
    return state.get("continuation_authority") == "operator_persistent" and not shape_errors(state)


def prove(root: Path | str, state: dict, *, history_events=None, dependencies=None) -> list[str]:
    """Verify the original grant, not a stronger carrier supplied on a retry."""
    errors = shape_errors(state)
    if errors or not persistent(state):
        return errors
    from . import operator_task

    source = state["authority_source"]
    if not source.startswith("E-"):
        return ["persistent authority requires its canonical goal-entry event"]
    from .journal import Journal, hash_file_dependency, semantic_receipts_for_operation_safe
    from .log import read_history_snapshot

    if history_events is None:
        history_events = read_history_snapshot(Path(root), lean=True).events
    pivots = [event for event in history_events if event.get("taxonomy") == "DEC"
              and str(event.get("text") or "").startswith("goal pivot --")
              and int(event.get("event") or 0) <= int(state.get("last_event") or 0)]
    if not pivots or source != f"E-{pivots[-1]['event']}":
        return ["persistent authority does not name the current goal pivot"]
    records, problems = semantic_receipts_for_operation_safe(Path(root), "goal_entry")
    if problems:
        return ["continuation grant journal is corrupt: " + "; ".join(problems[:2])]
    for record in records:
        metadata = record.get("receipt_metadata")
        grant = metadata.get("goal_authority") if isinstance(metadata, dict) else None
        if not isinstance(grant, dict) or grant.get("authority_source") != source:
            continue
        if (record.get("status") != "COMMITTED"
                or record.get("op_id") != pivots[-1].get("op_id")
                or grant.get("goal_ingress") != state.get("goal_ingress")):
            continue
        if any(grant.get(key) != state[key] for key in FIELDS):
            continue
        if operator_task.authority_for_provenance(grant.get("request_provenance"))["goal_pivot"]:
            if dependencies is not None:
                journal = Journal(Path(root), record["op_id"])
                try:
                    before = hash_file_dependency(journal.manifest)
                    live = journal.read()
                    after = hash_file_dependency(journal.manifest)
                except (OSError, ValueError):
                    return ["continuation grant became unreadable while being read"]
                if live != record or before != after:
                    return ["continuation grant changed while being read"]
                dependencies[journal.manifest.relative_to(Path(root)).as_posix()] = before
            return []
    return ["persistent authority has no committed operator grant for this goal"]


def fresh_cc_provenance() -> dict | None:
    """A declared operator carrier for the resume key, not CLI spelling."""
    from . import operator_task

    for text in ("cc", "\u0441\u0441", "saipen", "saipen continue", "saipen continue --json"):
        provenance = operator_task.witness(text)
        if not provenance.get("code") and operator_task.authority_for_provenance(provenance)[
            "reset_bounded_authority"
        ]:
            return provenance
    return None


def reset_authority(root: Path | str, state: dict, source: str | None = None) -> dict:
    """Decide whether this reset spends an existing grant or a fresh one."""
    from . import operator_task

    if source is not None and not operator_task.authority_for_receipt(
        Path(root), source
    )["reset_bounded_authority"]:
        return {"mode": "wait", "detail": "the named Source has no operator reset authority"}
    if persistent(state):
        errors = prove(root, state)
        return ({"mode": "wait", "detail": "; ".join(errors)} if errors
                else {"mode": "checkpoint", "source": state["authority_source"]})
    if source is not None:
        return {"mode": "reauthorize", "source": source}
    provenance = fresh_cc_provenance()
    if provenance:
        return {"mode": "reauthorize", "source": "operator_carrier", "provenance": provenance}
    return {"mode": "wait", "detail": "bounded run requires a fresh operator cc"}

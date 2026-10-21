"""GOAL-01: one continuation grant, independent of who invokes continue.

STATE records the scope. The existing source/journal owners prove its origin;
an invocation, a remembered request or a convenient counter value proves none.
"""

from __future__ import annotations

import hashlib
import json
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


def protocol_home(root: Path | str) -> bool:
    """SRC-249: the protocol's own repository holds standing operator authority.

    True when the project's canonical lineage is the lineage of the engine
    answering this call: the protocolist working on SAIPEN itself. Its goal
    budget is a self-clearing checkpoint, never a human gate. A consumer
    project, an absent lineage or an unreadable home is not the protocol home.
    """
    from .paths import project_lineage_identity
    from .state import running_home

    try:
        own = project_lineage_identity(root)
        return bool(own) and own == project_lineage_identity(running_home())
    except (OSError, ValueError):
        return False


def protocol_home_checkpoint(root: Path | str, state: dict) -> bool:
    """A tripped goal valve that `cc` clears without an operator (SRC-249)."""
    from .state import parse_wait

    return (
        state.get("execution_intent") == "goal"
        and parse_wait(str(state.get("next_action") or "")) == "safety valve"
        and protocol_home(root)
    )


def _pin_record(root: Path, record: dict, dependencies: dict) -> None:
    from .journal import Journal, hash_file_dependency

    journal = Journal(root, record["op_id"])
    before = hash_file_dependency(journal.manifest)
    live = journal.read()
    if live != record or before != hash_file_dependency(journal.manifest):
        raise ValueError("continuation journal changed while being read")
    dependencies[journal.manifest.relative_to(root).as_posix()] = before


def current_binding(root: Path | str, state: dict, history_events, dependencies: dict) -> dict:
    """Bind a prospective grant to an existing, committed goal, never rename it."""
    from .journal import Journal, hash_file_dependency
    from .cold_recovery import goal_ingress_identity
    from .paths import project_lineage_identity

    root = Path(root)
    if state.get("execution_intent") != "goal":
        raise ValueError("an existing active goal is required")
    identity_path = root / ".saipen/IDENTITY.md"
    before = hash_file_dependency(identity_path)
    lineage = project_lineage_identity(root)
    if not lineage or before != hash_file_dependency(identity_path):
        raise ValueError("canonical project lineage is absent or changed")
    dependencies[".saipen/IDENTITY.md"] = before
    pivots = [
        e
        for e in history_events
        if e.get("taxonomy") == "DEC"
        and str(e.get("text") or "").startswith("goal pivot -- ")
        and int(e.get("event") or 0) <= int(state.get("last_event") or 0)
    ]
    if not pivots:
        raise ValueError("the original goal objective cannot be recovered")
    pivot = pivots[-1]
    original = Journal(root, str(pivot.get("op_id") or "")).read()
    if (
        original.get("status") != "COMMITTED"
        or original.get("operation") not in {"goal", "goal_entry"}
        or original.get("project_lineage") != lineage
    ):
        raise ValueError("the original goal has no committed journal in this project lineage")
    _pin_record(root, original, dependencies)
    event = {
        k: pivot.get(k)
        for k in ("date", "event", "parent", "ticket", "agent", "op_id", "taxonomy", "text")
    }
    digest = hashlib.sha256(
        json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    original_grant = (original.get("receipt_metadata") or {}).get("goal_authority")
    if original_grant is not None and not isinstance(original_grant, dict):
        raise ValueError("the original goal authority metadata is malformed")
    original_grant = original_grant or {}
    ingress = original_grant.get("goal_ingress") or goal_ingress_identity(digest, lineage)
    if not re.fullmatch(r"goal-[0-9a-f]{16}", str(ingress)):
        raise ValueError("the original goal ingress binding is invalid")
    return {
        "kind": "saipen-goal-continuation",
        "project_lineage": lineage,
        **grant_fields(f"E-{pivot['event']}"),
        "goal_objective": pivot["text"][len("goal pivot -- ") :],
        "goal_event_sha256": digest,
        "goal_ingress": ingress,
    }


def parse_capsule(text: str) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate authorization field")
            value[key] = item
        return value

    value = json.loads(text, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("goal authorization must be an explicit JSON capsule")
    return value


def source_proof(
    root: Path | str, receipt: str, binding: dict, dependencies: dict, *, operation=None,
    capability="goal_pivot",
) -> dict:
    """Use SRC-164's immutable origin; a later carrier cannot promote a source."""
    from . import intake, operator_task
    from .distribution import distribution_record_rel, quarantine_body_rel
    from .journal import hash_file_dependency
    from .retirement import RETIRED_DIR

    root = Path(root)
    if not re.fullmatch(r"SRC-[0-9]+", str(receipt)):
        raise ValueError("goal authorization requires its ingress receipt")
    paths = [
        f"{prefix}/{receipt}{suffix}"
        for prefix in (".saipen/intake/active", ".saipen/archive/source", RETIRED_DIR)
        for suffix in (".md", ".meta.json")
    ]
    paths.extend((distribution_record_rel(receipt), quarantine_body_rel(receipt)))
    pins = {p: hash_file_dependency(root / p) for p in paths}
    found = intake.read_body(root, receipt)
    meta = found.get("meta") or {}
    if operation is None:
        authorized = operator_task.authority_for_receipt(root, receipt).get(capability, False)
    else:
        from .host_authority_client import verify_operator_goal

        provenance = meta.get("request_provenance") or {}
        authorized = (
            capability == "goal_pivot"
            and provenance.get("witness") == operator_task.WITNESS_CARRIER
            and verify_operator_goal(
                provenance.get("operator_origin"), project=root, operation=operation,
                grant={key: binding[key] for key in (*FIELDS, "goal_ingress")},
            )
        )
    if (
        not found.get("ok")
        or found.get("location") not in {"active", "archive"}
        or meta.get("source_kind") != "user_instruction"
        or meta.get("status") not in {intake.ACTIVE_STATUS, intake.CLOSED_STATUS}
        or meta.get("projection_policy") != intake.PROJECTION_AUTHORITY_ONLY
        or (found.get("distribution") or {}).get("state") != intake.DISTRIBUTABLE
        or not authorized
        or parse_capsule(found.get("body") or "") != binding
    ):
        raise ValueError("goal authorization source is invalid, revoked or not operator-backed")
    if pins != {p: hash_file_dependency(root / p) for p in paths}:
        raise ValueError("goal authorization source changed while being read")
    dependencies.update(pins)
    return {
        "receipt": receipt,
        "source_sha256": meta["source_sha256"],
        "request_provenance": meta["request_provenance"],
    }


def transition_grant(
    root: Path | str, state: dict, history_events, dependencies: dict
) -> dict | None:
    from .journal import semantic_receipts_for_operation_safe

    root = Path(root)
    records, errors = semantic_receipts_for_operation_safe(root, "goal_authorize")
    if errors:
        raise ValueError("continuation transition journal is corrupt: " + "; ".join(errors[:2]))
    binding = current_binding(root, state, history_events, dependencies)
    for record in records:
        grant = (record.get("receipt_metadata") or {}).get("goal_authority_transition")
        if not isinstance(grant, dict) or grant.get("binding") != binding:
            continue
        if (
            record.get("status") != "COMMITTED"
            or record.get("project_lineage") != binding["project_lineage"]
            or grant.get("goal_ingress") != state.get("goal_ingress")
            or any(binding[key] != state.get(key) for key in FIELDS)
        ):
            continue
        events = [
            e
            for e in history_events
            if e.get("op_id") == record["op_id"]
            and e.get("event") == grant.get("transition_event")
            and e.get("taxonomy") == "DEC"
            and str(e.get("text") or "").startswith("goal authority transition -- ")
            and int(e.get("event") or 0) <= int(state.get("last_event") or 0)
        ]
        if len(events) != 1:
            continue
        source = source_proof(
            root, grant.get("authorization_receipt"), binding, dependencies,
            operation=record["op_id"],
        )
        if source["source_sha256"] != grant.get("authorization_sha256") or source[
            "request_provenance"
        ] != grant.get("request_provenance"):
            raise ValueError("continuation grant disagrees with its original ingress")
        _pin_record(root, record, dependencies)
        return record
    return None

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
        from .host_authority_client import verify_operator_goal

        provenance = grant.get("request_provenance") or {}
        if (provenance.get("witness") == operator_task.WITNESS_CARRIER
                and verify_operator_goal(
                    provenance.get("operator_origin"), project=root, operation=record["op_id"],
                    grant={key: state[key] for key in (*FIELDS, "goal_ingress")},
                )):
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
    try:
        if transition_grant(root, state, history_events,
                            dependencies if dependencies is not None else {}):
            return []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ["continuation authority transition is invalid: " + str(exc)]
    return ["persistent authority has no committed operator grant for this goal"]


def describe(root: Path | str, state: dict, *, history_events=None) -> dict:
    """Explain existing proof; status never captures or upgrades authority."""
    due = state.get("execution_intent") == "goal" and (
        (state.get("goal_waves") or 0) >= 3 or (state.get("goal_tickets") or 0) >= 20
    )
    errors = prove(root, state, history_events=history_events)
    if errors:
        return {
            "state": "invalid",
            "detail": "Persistent authority invalid or revoked: " + "; ".join(errors),
            "original_event": state.get("authority_source"),
            "checkpoint_due": due,
        }
    if persistent(state):
        return {
            "state": "persistent_verified",
            "detail": "Persistent operator authority verified"
            + ("; goal checkpoint reached" if due else ""),
            "original_event": state["authority_source"],
            "checkpoint_due": due,
        }
    if state.get("execution_intent") == "goal" and protocol_home(root):
        return {
            "state": "protocol_home",
            "detail": "Protocol home: the goal budget checkpoint clears itself on cc",
            "original_event": state.get("authority_source"),
            "checkpoint_due": due,
        }
    return {
        "state": "bounded" if state.get("execution_intent") == "goal" else "inactive",
        "detail": "Bounded authority requires operator" if due else "No persistent grant",
        "original_event": state.get("authority_source"),
        "checkpoint_due": due,
    }

def fresh_cc_provenance(root: Path | str | None = None) -> dict | None:
    """A declared operator carrier for the resume key, not CLI spelling."""
    from . import operator_task

    for text in (
        "cc",
        "\u0441\u0441",
        "cc all",
        "\u0441\u0441 all",
        "saipen",
        "saipen continue",
        "saipen continue --json",
    ):
        provenance = operator_task.witness(text, root=root)
        if not provenance.get("code") and operator_task.authority_for_provenance(
            provenance, root=root,
        )["reset_bounded_authority"]:
            return provenance
    return None


def reset_authority(root: Path | str, state: dict, source: str | None = None) -> dict:
    """Decide whether this reset spends an existing grant or a fresh one."""
    from . import operator_task

    home = protocol_home(root)
    if source is not None and not home and not operator_task.authority_for_receipt(
        Path(root), source
    )["reset_bounded_authority"]:
        return {"mode": "wait", "detail": "the named Source has no operator reset authority"}
    if persistent(state):
        errors = prove(root, state)
        return ({"mode": "wait", "detail": "; ".join(errors)} if errors
                else {"mode": "checkpoint", "source": state["authority_source"]})
    if home:
        return {"mode": "reauthorize", "source": "protocol_home"}
    if source is not None:
        return {"mode": "reauthorize", "source": source}
    provenance = fresh_cc_provenance(root=root)
    if provenance:
        return {"mode": "reauthorize", "source": "operator_carrier", "provenance": provenance}
    return {"mode": "wait", "detail": "bounded run requires a fresh operator cc"}


def goal_completion_verdict(
    state: dict,
    tickets: dict,
    audit_inbox: dict | None = None,
    future_gate: dict | None = None,
    now=None,
) -> dict:
    """Truthful goal completion verdict (SAIHANDOFF / T-1619 / MAINTENANCE GOAL-01).

    Distinguishes ALL_REQUIREMENTS_COMPLETE / ALL_WORK_COMPLETE from
    NO_ADMISSIBLE_WORK (IDLE_BLOCKED_EXTERNAL, IDLE_OPERATOR_REQUIRED,
    IDLE_FUTURE_GATED).
    """
    from .board import classify_idle_work

    return classify_idle_work(
        tickets,
        audit_inbox=audit_inbox,
        future_gate=future_gate,
        state=state,
        now=now,
    )

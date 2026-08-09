"""Operations. M1 ships the two read-only ones.

`status` and `next` are the first things a cold agent can ask instead of
reading three complete files and re-deriving the answer by hand. Both are
strictly read-only: they take no lock, write no byte, and run no full validator.

The plan/apply split that the mutating operations will need is already visible
here in miniature — everything is computed from a `ProjectSnapshot` and nothing
touches disk after it is read. When `claim`, `transition` and `checkpoint`
arrive in M3 they take the same snapshot, declare preconditions against it, and
only then reach the journal.

The engine deliberately does not decide semantic work. `next` reports the
mechanically legal action and why it is legal. It never says "rewrite the
Improve architecture because I think that is best" — that is the model's job,
and a Python function pretending to have made that judgement would be exactly
the fuzzy-reasoning-in-deterministic-clothing OPS.md forbids.
"""

from __future__ import annotations

from pathlib import Path

from .board import MalformedLine
from .model import ProjectSnapshot, snapshot
from .paths import ProjectPaths, resolve_project_root
from .phases import (TICKET_BEARING_PHASES, VALID_TRANSITIONS,
                     phase_document, phase_next_action_error,
                     transition_legal)
from .result import Result


def open_project(root: str | Path | None = None) -> ProjectSnapshot:
    """Resolve a project and read one snapshot of it, or refuse."""
    resolved, source = resolve_project_root(explicit=root)
    if resolved is None:
        from .errors import EngineError
        raise EngineError(source, code="VALIDATION_FAILED",
                          next_action="saipen status --project-root PATH")
    snap = snapshot(paths=ProjectPaths(resolved))
    snap.__dict__["root_source"] = source
    return snap


def _fast_state_findings(snap: ProjectSnapshot) -> list[str]:
    """The cross-file invariants a mutation preflight must check.

    Deliberately NOT the full validator: this is the set covering the files
    SAIOPS mutates, so a checkpoint does not pay for a 7k-line conformance run.
    Fast validation is mutation preflight, never release proof — `validate.py`
    still owns the canonical gates.
    """
    findings: list[str] = []
    if snap.state.error:
        findings.append(f"STATE.md {snap.state.error}")
    binding = snap.binding_error()
    if binding:
        findings.append(f"ACTIVE_TICKET_MISMATCH {binding}")
    last_event = snap.last_event_error()
    if last_event:
        findings.append(last_event)
    malformed = [e for e in snap.board.entries if isinstance(e, MalformedLine)]
    for entry in malformed[:3]:
        findings.append(
            f"BOARD.md:{entry.line_no} is not a legal ticket line")
    duplicates = [e for e in snap.board.entries
                  if not isinstance(e, MalformedLine) and e.duplicate_of]
    for entry in duplicates[:3]:
        findings.append(
            f"BOARD.md:{entry.line_no} duplicate ticket {entry.ticket_id}")
    doing = snap.board.doing
    if len(doing) > 1:
        findings.append(
            f"BOARD.md carries {len(doing)} ## DOING tickets; at most one is "
            f"legal")
    if snap.log.malformed:
        line_no, _ = snap.log.malformed[0]
        findings.append(
            f"LOG.md:{line_no} violates the Event Graph skeleton "
            f"({len(snap.log.malformed)} line(s))")
    phase = snap.state.phase
    if phase and phase not in VALID_TRANSITIONS:
        findings.append(f"STATE.phase {phase!r} is not in the phase enum")
    next_action = snap.state.next_action
    if next_action.startswith("PHASE "):
        error = phase_next_action_error(next_action)
        if error:
            findings.append(f"next_action {error}")
    transition_from = snap.state.transition_from
    if phase and transition_from and \
            not transition_legal(transition_from, phase):
        findings.append(
            f"STATE claims {transition_from} -> {phase}, which is not a "
            f"transition CORE section 1.6 allows")
    return findings


def _pending_recovery(snap: ProjectSnapshot) -> list[str]:
    """Unfinished operation journals, if the recovery directory exists.

    M1 writes no journals, so this is always empty here. It is present because
    `status` must surface `recovery_required` from the very first release: a
    field that appears only once something can set it is a field every caller
    learns to ignore.
    """
    directory = snap.paths.recovery_ops
    if not directory.is_dir():
        return []
    pending = []
    for entry in sorted(directory.iterdir()):
        if (entry / "operation.json").is_file():
            pending.append(entry.name)
    return pending


def status(root: str | Path | None = None) -> Result:
    """Read-only projection of everything routing depends on.

    Replaces "read STATE.md, then BOARD.md, then the LOG tail, then work out
    whether they agree" — three files and a judgement call — with one answer.
    """
    snap = open_project(root)
    active = snap.board.active_ticket
    top = snap.board.top_workable()
    pending = _pending_recovery(snap)
    findings = _fast_state_findings(snap)

    data = {
        "project_root": str(snap.root),
        "project_identity": snap.identity,
        "root_source": snap.__dict__.get("root_source", "unknown"),
        "protocol_version": snap.state.fields.get("saipen_version"),
        "schema_version": snap.state.fields.get("schema_version"),
        "phase": snap.state.phase,
        "task": snap.state.task,
        "next_action": snap.state.next_action,
        "blocker": snap.state.blocker,
        "execution_intent": snap.state.execution_intent,
        "agent": snap.state.agent,
        "claimed_ticket": active.ticket_id if active else None,
        "top_workable_ticket": top.ticket_id if top else None,
        "log_tail": f"E-{snap.log_tail}" if snap.log_tail else None,
        "last_event": snap.state.last_event,
        "head": snap.head,
        "fast_state": "PASS" if not findings else "FAIL",
        "fast_state_findings": findings,
        "pending_recovery_ops": pending,
    }
    return Result(ok=True, code="STATUS", data=data,
                  recovery_required=bool(pending))


def next_action(root: str | Path | None = None) -> Result:
    """Read-only routing projection: the executable action and why it is legal.

    `STATE.next_action` is the previous session's pre-computed Pick Rule result.
    This does not replace confirming it — the model still has to look at the
    board — but it hands over the mechanical half already checked: does the
    action parse, does the phase it names exist, is the ticket it names really
    claimed, and which phase document that phase requires.
    """
    snap = open_project(root)
    action = snap.state.next_action.strip()
    active = snap.board.active_ticket
    top = snap.board.top_workable()

    subject: str | None = None
    phase: str | None = None
    legality: list[str] = []
    load: str | None = None

    if action.startswith("PHASE "):
        error = phase_next_action_error(action)
        if error:
            return Result.refuse(
                "VALIDATION_FAILED",
                f"STATE.next_action is not executable: {error}",
                "saipen status")
        parts = action.split()
        phase = parts[1]
        subject = parts[2] if len(parts) > 2 and \
            parts[2].startswith("T-") else None
        load = phase_document(phase)
        source = snap.state.transition_from
        if snap.state.phase == phase:
            legality.append(f"STATE is already in {phase}; the action "
                            f"continues it rather than transitioning")
        elif transition_legal(snap.state.phase, phase):
            legality.append(f"{snap.state.phase} -> {phase} is an edge of the "
                            f"CORE section 1.6 transition table")
        else:
            return Result.refuse(
                "ILLEGAL_TRANSITION",
                f"STATE.next_action names {phase} but {snap.state.phase} -> "
                f"{phase} is not a legal transition (from {source!r})",
                "saipen status")
        if phase in TICKET_BEARING_PHASES:
            if subject is None:
                return Result.refuse(
                    "VALIDATION_FAILED",
                    f"{phase} is ticket-bearing and next_action names no "
                    f"T-###", "saipen status")
            ticket = snap.board.tickets.get(subject)
            if ticket is None:
                return Result.refuse(
                    "TICKET_NOT_FOUND",
                    f"next_action names {subject}, which is not on the board",
                    "saipen status")
            if ticket.is_claimed:
                legality.append(f"{subject} is claimed in {ticket.section}")
            else:
                legality.append(f"{subject} sits in {ticket.section} and is "
                                f"not yet claimed")
    elif action.startswith("WAIT:"):
        legality.append("WAIT: is output verbatim and stops execution "
                        "(CORE section 1.2)")
    elif action:
        legality.append("the action is a command form; CORE section 1.10 "
                        "resolves it, not the engine")

    binding = snap.binding_error()
    if binding:
        return Result.refuse(
            "CONFLICT",
            f"ACTIVE_TICKET_MISMATCH {binding}", "saipen recover")

    dependencies: list[str] = []
    if subject and subject in snap.board.tickets:
        for dep in snap.board.tickets[subject].needs:
            dep_ticket = snap.board.tickets.get(dep)
            state = "missing" if dep_ticket is None else (
                "done" if dep_ticket.is_done else "open")
            dependencies.append(f"{dep}:{state}")

    data = {
        "action": action,
        "ticket": subject or (active.ticket_id if active else None),
        "phase": phase,
        "load": load,
        "legal_because": legality,
        "dependencies": dependencies,
        "top_workable_ticket": top.ticket_id if top else None,
    }
    return Result(ok=True, code="NEXT", data=data)

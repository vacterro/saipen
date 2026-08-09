"""Core operations: claim / transition / checkpoint / ticket lifecycle /
goal / stop (NITRO M3-M5, integrity-repaired).

Every operation is PLAN / APPLY separated around an immutable OperationPlan.

PLAN reads the project snapshot, validates the request, computes the intended
exact bytes for every target (encoding already applied by the codec), and
returns the plan -- writing ZERO bytes. `--dry-run` renders the plan and
nothing else.

APPLY consumes THAT plan object under the writer lock: runs Recovery
preflight, re-checks every declared precondition against the live files
(STALE_STATE refusal), journals PREPARED, applies the ordered targets, verifies
the written result, and only then marks VERIFIED + COMMITTED. The plan's op_id
is the applied op_id; the plan's bytes are the committed bytes. A commit
failure always wins over the semantic success metadata.

STATE is mutated ONLY through owned-field patches (state.patch_state): every
operation declares exactly which keys it owns, everything else is preserved.
There is no `_render_state` anymore.
"""

from __future__ import annotations

import re
import datetime
import uuid
from pathlib import Path

from . import codec, phases
from .board import parse_board, remove_ticket_field, set_ticket_field
from .fast_check import validate_texts
from .journal import hash_bytes
from .log import build_event, log_tail_event
from .plan import OperationPlan, TargetPlan, apply_plan, build_plan
from .result import Result
from .state import parse_state, patch_state

SYNTHETIC_TICKET_IDS = {998, 999}

_TAXONOMIES = {"DEC", "RUN"}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d.%m.%y %H:%M")


def uuid4_hex8() -> str:
    return uuid.uuid4().hex[:8]


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _read(root: Path) -> tuple[dict, dict, dict, dict]:
    """Read STATE/BOARD/LOG docs + their parsed forms (normalised view)."""
    state_doc = codec.read_document(root / ".saipen" / "STATE.md")
    board_doc = codec.read_document(root / ".saipen" / "BOARD.md")
    log_doc = codec.read_document(root / ".saipen" / "LOG.md")
    state = parse_state(state_doc.text_norm)
    board = parse_board(board_doc.text_norm)
    log_tail = log_tail_event(log_doc.text_norm)
    return ({"state": state_doc, "board": board_doc, "log": log_doc},
            state, board, log_tail)


def _target(doc, path: str, role: str, new_text: str) -> TargetPlan:
    """One planned write target: exact bytes + before/after hashes computed
    from the read document and the planned content."""
    from .journal import hash_bytes
    return TargetPlan(path, role, doc.encode(new_text), doc.raw_hash,
                      hash_bytes(doc.encode(new_text)))


def _docs_preconditions(docs: dict, *keys: str) -> dict:
    return {f".saipen/{key.upper()}.md": docs[key].raw_hash for key in keys}


def _event_line(docs: dict, log_tail: int | None, taxonomy: str,
                ticket: str | None, agent: str, message: str,
                now: str, op_id: str | None = None) -> tuple[int, str]:
    if taxonomy not in _TAXONOMIES:
        raise ValueError(f"taxonomy {taxonomy!r} outside {_TAXONOMIES}")
    return build_event(log_tail, taxonomy, message, ticket=ticket,
                       agent=agent, now=now, op_id=op_id)


def _refuse(code: str, detail: str = "", **extra) -> Result:
    return Result(ok=False, code=code, message=detail, data=extra)


# --------------------------------------------------------------------------- claim

def _plan_claim(root: Path, ticket_id: str, agent: str, now: str, utc: str,
                explicit: bool = False) -> OperationPlan | Result:
    op_id = "claim-" + uuid4_hex8()
    docs, state, board, log_tail = _read(root)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]
    if ticket["section"] == "## DOING":
        return _refuse("ALREADY_CLAIMED",
                       f"{ticket_id} is already in ## DOING", ticket=ticket_id)
    if ticket["section"] != "## TODO":
        return _refuse("TICKET_NOT_WORKABLE",
                       f"{ticket_id} is under {ticket['section']}",
                       ticket=ticket_id)
    for need in ticket["needs"]:
        if need not in tickets or tickets[need]["section"] != "## DONE":
            return _refuse("TICKET_NOT_WORKABLE",
                           f"unmet needs: {need}", ticket=ticket_id)
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if doing:
        return _refuse("ALREADY_CLAIMED",
                       f"DOING holds {doing[0]['id']}", ticket=ticket_id)

    if not explicit:
        top_workable = None
        for t in tickets.values():
            if t["section"] != "## TODO":
                continue
            if all(need in tickets and tickets[need]["section"] == "## DONE"
                   for need in t["needs"]):
                top_workable = t["id"]
                break
        if top_workable is None or top_workable != ticket_id:
            return _refuse("NOT_TOP_WORKABLE",
                           f"topmost workable ticket is {top_workable or 'none'}, "
                           f"requested {ticket_id}; use the explicit-claim "
                           "flag to override with evidence",
                           ticket=ticket_id, top_workable=top_workable)

    event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                              f"claimed via SAIOPS -- owner {agent}", now,
                              op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_board = _claim_move(docs["board"].text_norm, ticket_id, agent, utc)
    owned = {
        "phase": "SCOUT",
        "task": ticket_id,
        "next_action": f"PHASE SCOUT {ticket_id}",
        "transition_from": state.get("phase") or "DONE",
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "claim", agent, _identity(root),
        {"operation": "claim", "ticket": ticket_id, "agent": agent,
         "explicit": explicit},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "CLAIMED", "ticket": ticket_id,
         "event_id": f"E-{event}", "phase": "SCOUT",
         "next_action": f"PHASE SCOUT {ticket_id}"},
        op_id=op_id)


def _claim_move(board_text: str, ticket_id: str, agent: str, utc: str) -> str:
    """Surgical claim move: target ticket TODO -> DOING with [/] owner."""
    lines = board_text.splitlines(keepends=True)
    out = []
    ticket_line = None
    doing_idx = None
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("- [ ] " + ticket_id + " "):
            ticket_line = stripped
            continue
        if stripped.startswith("## DOING"):
            doing_idx = len(out)
        out.append(line)
    if ticket_line is None or doing_idx is None:
        raise ValueError("cannot locate ticket or DOING section")
    marked = ticket_line.replace("- [ ] ", "- [/] ", 1).rstrip() + \
        f" | owner: {agent} | claim_time: {utc}"
    out.insert(doing_idx + 1, marked + "\n")
    return "".join(out)


def plan_claim(project_root: Path | str, ticket_id: str, agent: str,
               explicit: bool = False) -> Result:
    now, utc = _now(), _utc_iso()
    plan = _plan_claim(Path(project_root), ticket_id, agent, now, utc,
                       explicit=explicit)
    if isinstance(plan, Result):
        return plan
    return _render_plan(plan)


def apply_claim(project_root: Path | str, ticket_id: str, agent: str,
                explicit: bool = False) -> Result:
    now, utc = _now(), _utc_iso()
    plan = _plan_claim(Path(project_root), ticket_id, agent, now, utc,
                       explicit=explicit)
    if isinstance(plan, Result):
        return plan
    return apply_plan(Path(project_root), plan)


# ------------------------------------------------------------ transition

def _plan_transition(root: Path, destination: str, agent: str,
                     ticket_id: str | None, event_text: str, now: str,
                     utc: str) -> OperationPlan | Result:
    destination = destination.upper()
    op_id = "transition-" + uuid4_hex8()
    docs, state, board, log_tail = _read(root)
    current = state.get("phase")
    if destination not in phases.VALID_TRANSITIONS and \
            destination not in phases.ANY_FROM:
        return _refuse("ILLEGAL_TRANSITION",
                       f"{current} -> {destination}: destination outside the "
                       "phase enum", phase=destination)
    if not phases.transition_legal(current, destination):
        return _refuse("ILLEGAL_TRANSITION",
                       f"{current} -> {destination} is not a legal edge",
                       phase=destination)

    subject = None
    if destination in phases.TICKET_BEARING_PHASES:
        doing = [t for t in board["tickets"].values()
                 if t["section"] == "## DOING"]
        active = doing[0]["id"] if doing else None
        state_task = state.get("task")
        if active is None:
            return _refuse("ACTIVE_TICKET_MISMATCH",
                           f"{destination} is ticket-bearing but no ticket is "
                           "DOING", phase=destination)
        if state_task and active != state_task:
            return _refuse("ACTIVE_TICKET_MISMATCH",
                           f"STATE.task={state_task} but BOARD.DOING={active}",
                           phase=destination)
        if ticket_id is not None and ticket_id != active:
            if ticket_id not in board["tickets"]:
                return _refuse("TICKET_NOT_FOUND", f"{ticket_id} is not on "
                               "the board", ticket=ticket_id)
            return _refuse("ACTIVE_TICKET_MISMATCH",
                           f"requested ticket {ticket_id} != active DOING "
                           f"{active}; a ticket-bearing transition binds the "
                           "exact active DOING ticket", ticket=ticket_id)
        subject = active
        if subject not in board["tickets"]:
            return _refuse("TICKET_NOT_FOUND", f"active ticket {subject} "
                           "missing from the board", ticket=subject)

    event, line = _event_line(docs, log_tail, "RUN", subject, agent,
                              event_text or f"transition to {destination}",
                              now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    if destination in phases.TICKET_BEARING_PHASES:
        na = f"PHASE {destination} {subject}"
    else:
        na = f"PHASE {destination}"
    owned = {
        "phase": destination,
        "next_action": na,
        "transition_from": current,
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    if destination == "DONE":
        owned["task"] = "none"
    new_state = patch_state(docs["state"].text_norm, owned)

    # Goal-counter mechanics (NITRO dogfood II, T-590): a VERIFY -> REVIEW
    # transition under execution_intent: goal is the contract point where a
    # ticket has passed VERIFY. The OPERATION owns the bookkeeping -- it
    # bumps goal_tickets, emits DEC: goal_tickets N->N+1, updates last_event,
    # and writes the WAIT when the valve trips. The model no longer has to
    # remember deterministic accounting.
    if (destination == "REVIEW" and current == "VERIFY"
            and state.get("execution_intent") == "goal"):
        tickets = int(state.get("goal_tickets") or 0)
        new_tickets = tickets + 1
        from .log import build_event as _build_event
        dec_event, dec_line = _build_event(
            event, "DEC",
            f"goal_tickets {tickets}->{new_tickets}", now=now, op_id=op_id)
        new_log = new_log.rstrip("\n") + "\n" + dec_line + "\n"
        cap_reached = new_tickets >= GOAL_TICKET_CAP
        owned["goal_tickets"] = new_tickets
        owned["last_event"] = dec_event
        if cap_reached:
            owned["next_action"] = (
                f"WAIT: safety valve reached ({state.get('goal_waves') or 0} "
                f"waves / {new_tickets} tickets) -- run 'saipen goal' to "
                "continue")
        new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    expected = {"ok": True, "code": "TRANSITIONED", "phase": destination,
                "next_action": na, "event_id": f"E-{event}",
                "ticket": subject}
    if destination == "REVIEW" and current == "VERIFY" \
            and state.get("execution_intent") == "goal":
        expected["goal_tickets"] = int(state.get("goal_tickets") or 0) + 1
    return build_plan(
        "transition", agent, _identity(root),
        {"operation": "transition", "destination": destination,
         "ticket": subject, "agent": agent},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        expected, op_id=op_id)


def transition_phase(project_root: Path | str, destination: str,
                     agent: str, ticket_id: str | None = None,
                     event_text: str = "", dry_run: bool = False) -> Result:
    now, utc = _now(), _utc_iso()
    plan = _plan_transition(Path(project_root), destination, agent, ticket_id,
                            event_text, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(Path(project_root), plan)


# ------------------------------------------------------------- checkpoint

def _plan_checkpoint(root: Path, agent: str, taxonomy: str,
                     ticket_id: str | None, description: str, now: str,
                     utc: str) -> OperationPlan | Result:
    op_id = "checkpoint-" + uuid4_hex8()
    docs, state, board, log_tail = _read(root)
    event, line = _event_line(docs, log_tail, taxonomy.upper(), ticket_id,
                              agent, description, now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "checkpoint", agent, _identity(root),
        {"operation": "checkpoint", "taxonomy": taxonomy.upper(),
         "ticket": ticket_id, "description": description},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "CHECKPOINTED", "event_id": f"E-{event}"},
        op_id=op_id)


def checkpoint(project_root: Path | str, agent: str, taxonomy: str,
               ticket_id: str | None, description: str,
               dry_run: bool = False) -> Result:
    if taxonomy.upper() not in _TAXONOMIES:
        return _refuse("VALIDATION_FAILED",
                       f"taxonomy {taxonomy!r} outside {sorted(_TAXONOMIES)}")
    now, utc = _now(), _utc_iso()
    plan = _plan_checkpoint(Path(project_root), agent, taxonomy, ticket_id,
                            description, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(Path(project_root), plan)


# ---------------------------------------------------------- ticket numbers

def next_ticket_id(board_text: str, log_text: str) -> int:
    """The next canonical production ticket ID, skipping the synthetic
    fixture namespace (T-998/T-999)."""
    ids = [int(m) for m in re.findall(r"\bT-(\d+)\b",
                                      board_text + "\n" + log_text)]
    return max((i for i in ids if i not in SYNTHETIC_TICKET_IDS),
               default=0) + 1


def _insert_todo(board_text: str, line: str) -> str:
    lines = board_text.splitlines(keepends=True)
    todo_idx = next(i for i, ln in enumerate(lines)
                    if ln.startswith("## TODO"))
    lines.insert(todo_idx + 1, line + "\n")
    return "".join(lines)


def _ticket_targets(root: Path, action: str, ticket_id: str, agent: str,
                    payload: str, now: str, utc: str) -> OperationPlan | Result:
    op_id = "ticket-" + uuid4_hex8()
    docs, state, board, log_tail = _read(root)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]

    if action == "done":
        if ticket["section"] != "## DOING":
            return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                           f"done accepts only ## DOING source; {ticket_id} "
                           f"is under {ticket['section']}", ticket=ticket_id)
        if ticket["checkbox"] != "/":
            return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                           f"done requires [/] claim marker, got "
                           f"[{ticket['checkbox']}]", ticket=ticket_id)
        if state.get("task") != ticket_id:
            return _refuse("ACTIVE_TICKET_MISMATCH",
                           f"STATE.task={state.get('task')} but done target "
                           f"is {ticket_id}", ticket=ticket_id)
        target_section, checkbox = "## DONE", "[x]"
    elif action == "block":
        if ticket["section"] not in ("## DOING", "## TODO"):
            return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                           f"block accepts DOING or TODO; {ticket_id} is "
                           f"under {ticket['section']}", ticket=ticket_id)
        target_section, checkbox = "## BLOCKED", "[ ]"
    elif action == "unblock":
        if ticket["section"] != "## BLOCKED":
            return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                           f"unblock accepts only BLOCKED; {ticket_id} is "
                           f"under {ticket['section']}", ticket=ticket_id)
        target_section, checkbox = "## TODO", "[ ]"
    else:
        return _refuse("VALIDATION_FAILED", f"unknown ticket action {action!r}")

    new_board = _move_ticket(docs["board"].text_norm, ticket_id,
                             target_section, checkbox, action, payload)
    event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                              f"ticket {action} via SAIOPS"
                              + (f" -- {payload}" if payload else ""), now,
                              op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "ticket_move", agent, _identity(root),
        {"operation": "ticket_move", "action": action, "ticket": ticket_id},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": action.upper(), "ticket": ticket_id,
         "event_id": f"E-{event}"}, op_id=op_id)


def _move_ticket(board_text: str, ticket_id: str, target_section: str,
                 checkbox: str, action: str, payload: str) -> str:
    lines = board_text.splitlines(keepends=True)
    out = []
    ticket_line = None
    heading_idx = {}
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("- [/] " + ticket_id + " ") or \
           stripped.startswith("- [ ] " + ticket_id + " "):
            ticket_line = stripped
            continue
        for heading in ("## DOING", "## TODO", "## DONE", "## BLOCKED"):
            if stripped.startswith(heading):
                heading_idx[heading] = len(out)
        out.append(line)
    if ticket_line is None:
        raise ValueError(f"cannot locate ticket {ticket_id}")
    target_idx = heading_idx.get(target_section)
    if target_idx is None:
        raise ValueError(f"cannot locate section {target_section}")
    if action == "done":
        marked = ticket_line.replace("- [/] ", "- [x] ", 1)
    elif action == "block":
        marked = ticket_line.replace("- [/] ", "- [ ] ", 1)
        marked = set_ticket_field(marked, "blocker", payload or "blocked")
    elif action == "unblock":
        marked = ticket_line.replace("- [/] ", "- [ ] ", 1)
        marked = remove_ticket_field(marked, "blocker")
    else:  # pragma: no cover
        marked = ticket_line.replace("- [/] ", "- [ ] ", 1)
    out.insert(target_idx + 1, marked.rstrip() + "\n")
    return "".join(out)


def _is_placeholder_verify(verify: str) -> bool:
    """A verify value that proves nothing about DONE (NITRO dogfood II).

    Python owns mechanics, not missing semantic content: a ticket's verify
    clause is the model's DONE proof. Refusing a placeholder keeps a weak
    model from creating mechanically perfect tickets whose completion can
    never be proven.
    """
    cleaned = (verify or "").strip().lower()
    return (not cleaned
            or cleaned in ("tbd", "todo", "verify: tbd", "verify: todo",
                           "tbd -", "todo -", "placeholder")
            or cleaned.startswith("verify:") and len(cleaned) < 12)


def ticket_add(project_root: Path | str, agent: str, priority: str,
               description: str, needs: list[str], verify: str,
               dry_run: bool = False) -> Result:
    root = Path(project_root)
    if not description or not description.strip():
        return _refuse("INCOMPLETE_TICKET",
                       "ticket description is required (semantic input)")
    if _is_placeholder_verify(verify):
        return _refuse("INCOMPLETE_TICKET",
                       "verify is a placeholder; a ticket needs a real DONE "
                       "proof (no TBD/TODO/empty)", verify=verify)
    op_id = "ticket-" + uuid4_hex8()
    now, utc = _now(), _utc_iso()
    docs, state, board, log_tail = _read(root)
    tid = next_ticket_id(docs["board"].text_norm, docs["log"].text_norm)
    for need in needs:
        if need not in board["tickets"]:
            return _refuse("TICKET_NOT_FOUND", f"dangling needs: {need}")
    desc = (f"- [ ] T-{tid} [{priority}] {description}"
            + (f" | needs: {', '.join(needs)}" if needs else "")
            + f" | verify: {verify}")
    new_board = _insert_todo(docs["board"].text_norm, desc)
    event, line = _event_line(docs, log_tail, "DEC", f"T-{tid}", agent,
                              "ticket added via SAIOPS", now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    plan = build_plan(
        "ticket_add", agent, _identity(root),
        {"operation": "ticket_add", "priority": priority,
         "description": description, "needs": needs},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "TICKET_ADDED", "ticket": f"T-{tid}",
         "event_id": f"E-{event}"}, op_id=op_id)
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def ticket_move(project_root: Path | str, action: str, ticket_id: str,
                agent: str, payload: str = "", dry_run: bool = False) -> Result:
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _ticket_targets(root, action, ticket_id, agent, payload, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


# ------------------------------------------------------------------ goal

def _state_only_plan(root: Path, operation: str, agent: str, mutate,
                     event_message: str, expected: dict, now: str,
                     utc: str, owned_keys: set) -> OperationPlan | Result:
    op_id = operation + "-" + uuid4_hex8()
    docs, state, board, log_tail = _read(root)
    event, line = _event_line(docs, log_tail, "DEC", None, agent,
                              event_message, now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_state = mutate(docs["state"].text_norm, event)
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    expected["event_id"] = f"E-{event}"
    return build_plan(
        operation, agent, _identity(root),
        {"operation": operation, "agent": agent},
        _docs_preconditions(docs, "state", "board", "log"),
        targets, expected, op_id=op_id)


def set_goal_intent(project_root: Path | str, agent: str, objective: str,
                    dry_run: bool = False) -> Result:
    """Record a decided goal pivot: execution_intent goal, counters from 0.
    Owns ONLY intent/counters/last_event/updated/agent -- never phase, task or
    next_action. Claiming the top ticket is a separate operation."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()

    def mutate(text: str, event: int) -> str:
        return patch_state(text, {
            "execution_intent": "goal",
            "goal_waves": 0,
            "goal_tickets": 0,
            "last_event": event,
            "updated": utc,
            "agent": agent,
        })

    plan = _state_only_plan(root, "goal", agent, mutate,
                            f"goal pivot -- {objective}",
                            {"ok": True, "code": "GOAL_SET"}, now, utc,
                            {"execution_intent", "goal_waves", "goal_tickets"})
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


GOAL_WAVE_CAP = 3
GOAL_TICKET_CAP = 20


def reauthorize_valve(project_root: Path | str, agent: str,
                      dry_run: bool = False) -> Result:
    """Conditional safety-valve reauthorization: reset BOTH counters to 0 only
    when a counter has tripped its cap. Never grants a fresh budget on a run
    that did not trip the valve."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    docs, state, board, log_tail = _read(root)
    waves = state.get("goal_waves") or 0
    tickets = state.get("goal_tickets") or 0
    if not (state.get("execution_intent") == "goal"
            and (waves >= 3 or tickets >= 20)):
        return _refuse("VALIDATION_FAILED",
                       "valve has not tripped; no fresh budget is owed",
                       goal_waves=waves, goal_tickets=tickets)

    def mutate(text: str, event: int) -> str:
        return patch_state(text, {
            "goal_waves": 0,
            "goal_tickets": 0,
            "last_event": event,
            "updated": utc,
            "agent": agent,
        })

    plan = _state_only_plan(root, "valve", agent, mutate,
                            "goal reauthorized",
                            {"ok": True, "code": "VALVE_REAUTHORIZED"},
                            now, utc,
                            {"goal_waves", "goal_tickets"})
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def stop_checkpoint(project_root: Path | str, agent: str, reason: str = "",
                    dry_run: bool = False) -> Result:
    """The brake: checkpoint the exact current execution with a resumable
    next_action. Never resets phase; never changes intent or counters. The
    human digest is a PLAN TARGET (NITRO dogfood II): it commits inside the
    same journaled transaction as LOG/STATE, so a stop can never report
    STOPPED with a missing/stale digest."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    docs, state, board, log_tail = _read(root)
    task = state.get("task")
    phase = state.get("phase")
    if task and task != "none":
        na = f"PHASE {phase} {task}"
    else:
        na = "saipen continue"

    op_id = "stop-" + uuid4_hex8()
    event, line = _event_line(docs, log_tail, "DEC", None, agent,
                              f"stop checkpoint{': ' + reason if reason else ''}",
                              now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_state = patch_state(docs["state"].text_norm, {
        "next_action": na,
        "last_event": event,
        "updated": utc,
        "agent": agent,
    })
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))
    digest_content = ("done: stopped via SAIOPS checkpoint\n"
                      f"remaining: {task or 'see BOARD'}\n"
                      f"awaiting: {reason or 'nothing'}\n")
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    digest_doc = codec.read_document(root / ".saipen" / "kitchen" / "digest.md")
    targets.append(TargetPlan(".saipen/kitchen/digest.md", "report",
                              digest_doc.encode(digest_content),
                              digest_doc.raw_hash,
                              hash_bytes(digest_doc.encode(digest_content))))
    plan = build_plan(
        "stop", agent, _identity(root),
        {"operation": "stop", "reason": reason},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "STOPPED", "next_action": na,
         "digest": str(root / ".saipen" / "kitchen" / "digest.md")},
        op_id=op_id)
    if dry_run:
        result = _render_plan(plan)
        result.data["digest"] = str(root / ".saipen" / "kitchen" / "digest.md")
        return result
    return apply_plan(root, plan)


# ------------------------------------------------------------------ helpers

def _identity(root: Path) -> str:
    from .paths import project_identity
    return project_identity(root)


def _render_plan(plan: OperationPlan) -> Result:
    """Render an OperationPlan as the dry-run result. Reads nothing live,
    writes nothing."""
    expected = dict(plan.expected)
    expected["op_id"] = plan.op_id
    expected["dry_run"] = True
    expected["changed_files"] = plan.changed_files
    return Result(ok=True, code=expected.get("code", "PLANNED"),
                  data=expected, op_id=plan.op_id,
                  changed_files=plan.changed_files)

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
from .board import (_claim_is_live, escape_ticket_description, parse_board,
                    remove_ticket_field, set_ticket_field,
                    ticket_has_blocker, ticket_is_workable)
from .fast_check import validate_texts
from .journal import hash_bytes
from .log import build_event, log_tail_event
from .plan import OperationPlan, TargetPlan, apply_plan, build_plan
from .result import Result
from .state import parse_state, patch_state

_TAXONOMIES = {"DEC", "RUN"}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d.%m.%y %H:%M")


def uuid4_hex8() -> str:
    return uuid.uuid4().hex[:8]


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _segment_number(path: Path) -> int:
    m = re.match(r"LOG-(\d+)\.md$", path.name)
    return int(m.group(1)) if m else -1


def _read(root: Path) -> tuple[dict, dict, dict, dict]:
    """Read STATE/BOARD/LOG docs + their parsed forms (normalised view)."""
    state_doc = codec.read_document(root / ".saipen" / "STATE.md")
    board_doc = codec.read_document(root / ".saipen" / "BOARD.md")
    log_doc = codec.read_document(root / ".saipen" / "LOG.md")
    state = parse_state(state_doc.text_norm)
    board = parse_board(board_doc.text_norm)
    # Sealed segments are read in ascending NUMERIC id order (LOG-999 before
    # LOG-1000, never a lexicographic sort). log_tail_event returns the actual
    # maximum E-ID across the whole text, so concatenation order can never
    # affect allocation correctness -- a fresh post-seal active log still
    # derives the newest sealed event as its tail.
    _log_text = ""
    _sealed = sorted((root / ".saipen" / "logs").glob("LOG-*.md"),
                     key=_segment_number)
    for _seg in _sealed:
        _log_text += codec.read_document(_seg).text_norm + "\n"
    _log_text += log_doc.text_norm
    log_tail = log_tail_event(_log_text)
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
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]
    if ticket_has_blocker(ticket):
        return _refuse(
            "TICKET_NOT_WORKABLE",
            f"{ticket_id} carries a blocker; explicit priority override does "
            "not override authorization",
            ticket=ticket_id,
        )
    if ticket["section"] == "## DOING":
        return _refuse("ALREADY_CLAIMED",
                       f"{ticket_id} is already in ## DOING", ticket=ticket_id)
    if ticket["section"] != "## TODO":
        return _refuse("TICKET_NOT_WORKABLE",
                       f"{ticket_id} is under {ticket['section']}",
                       ticket=ticket_id)
    if ticket["checkbox"] not in (" ", ""):
        return _refuse("TICKET_NOT_WORKABLE",
                       f"{ticket_id} is [{ticket['checkbox']}] but sits under "
                       f"## TODO -- checkbox/section disagreement is malformed "
                       f"input and cannot be claimed",
                       ticket=ticket_id)
    _tfields = ticket["fields"]
    if _claim_is_live(_tfields.get("owner", ""),
                      _tfields.get("claim_time", ""), agent, None):
        return _refuse("TICKET_NOT_WORKABLE",
                       f"{ticket_id} sits under ## TODO but carries a live "
                       f"claim by {_tfields.get('owner')} -- § 1.4's active "
                       f"claim is not claimable by this agent",
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
            if ticket_is_workable(t, tickets, agent=agent):
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

    # Goal-wave mechanics (NITRO dogfood II, T-590): a HUNT -> ADD transition
    # under execution_intent: goal is the contract point where a
    # HUNT->ADD cycle completes (MAINTENANCE section 2.4). The operation owns
    # the bump: goal_waves N->N+1 with its DEC line, and the valve WAIT.
    elif (destination == "ADD" and current == "HUNT"
          and state.get("execution_intent") == "goal"):
        waves = int(state.get("goal_waves") or 0)
        new_waves = waves + 1
        from .log import build_event as _build_event
        wave_event, wave_line = _build_event(
            event, "DEC",
            f"goal_waves {waves}->{new_waves}", now=now, op_id=op_id)
        new_log = new_log.rstrip("\n") + "\n" + wave_line + "\n"
        cap_reached = new_waves >= GOAL_WAVE_CAP
        owned["goal_waves"] = new_waves
        owned["last_event"] = wave_event
        if cap_reached:
            owned["next_action"] = (
                f"WAIT: safety valve reached ({new_waves} waves / "
                f"{state.get('goal_tickets') or 0} tickets) -- run 'saipen "
                "goal' to continue")
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
    docs, _state, _board, log_tail = _read(root)
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

# BOARD canonical ticket-line shape: a list item whose text starts with the
# checkbox and an uppercase T-NNN. Only these lines are ticket IDENTITY --
# prose that merely mentions "T-900000" in a description or verify clause is
# not a ticket record (T-639/§9).
_BOARD_TICKET_LINE_RE = re.compile(
    r"^-\s*\[[ x/]\]\s*T-(\d+)\b")


def next_ticket_id(board_text: str, log_text: str) -> int:
    """The next canonical production ticket ID, from STRUCTURED records only
    (T-639/§9): canonical BOARD ticket lines (`- [ ] T-###`) and the LOG's
    structured `[T-###]` event field. Prose that merely mentions a T-NNN --
    in a ticket description, a verify clause, or LOG message text -- is never
    ticket identity, so a fixture note like "synthetic T-990" or a
    prose-mentioned T-777 cannot poison allocation. The tiny synthetic-id
    exclusion set is gone; structure is what keeps fixtures out."""
    ids: set[int] = set()
    for line in board_text.splitlines():
        match = _BOARD_TICKET_LINE_RE.match(line.strip())
        if match:
            ids.add(int(match.group(1)))
    from .log import parse_log_line
    for line in log_text.splitlines():
        parsed = parse_log_line(line)
        if parsed is not None and parsed["ticket"]:
            match = re.fullmatch(r"T-(\d+)", parsed["ticket"])
            if match:
                ids.add(int(match.group(1)))
    return (max(ids, default=0) + 1) if ids else 1


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
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]

    if action == "done":
        # `done` is the atomic finish operation, never a raw section move
        # (NITRO dogfood III, T-591); the split it used to leave is now a
        # corruption the fast binding rejects.
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       "done is the atomic finish operation; use finish_ticket "
                       "or `saipen ticket done` (it closes LOG+BOARD+STATE "
                       "together)", ticket=ticket_id)
    elif action == "block":
        if not payload or not payload.strip():
            return _refuse("VALIDATION_FAILED",
                           "block requires the facts/dead ends that justify "
                           "the block", ticket=ticket_id)
        if ticket["section"] not in ("## DOING", "## TODO"):
            return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                           f"block accepts DOING or TODO; {ticket_id} is "
                           f"under {ticket['section']}", ticket=ticket_id)
        target_section, checkbox = "## BLOCKED", "[ ]"
    elif action == "unblock":
        if not payload or not payload.strip():
            return _refuse("VALIDATION_FAILED",
                           "unblock requires the decision/evidence that "
                           "lifts the block", ticket=ticket_id)
        if ticket["section"] != "## BLOCKED":
            return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                           f"unblock accepts only BLOCKED; {ticket_id} is "
                           f"under {ticket['section']}", ticket=ticket_id)
        target_section, checkbox = "## TODO", "[ ]"
    else:
        return _refuse("VALIDATION_FAILED", f"unknown ticket action {action!r}")

    new_board = _move_ticket(docs["board"].text_norm, ticket_id,
                             target_section, checkbox, action, payload)
    # Blocking the ACTIVE DOING ticket parks the current work: the ticket
    # leaves ## DOING, so the execution state must not keep naming it in a
    # ticket-bearing phase, and the block MUST NOT become a session-level
    # phase: BLOCKED -- that state is reserved for when no ticket anywhere is
    # workable (CORE.md § 1.11), carries its own STATE.blocker + WAIT, and
    # contradicts a running goal intent. The block therefore neutralizes the
    # execution state to DONE/task none (the same no-active-ticket form
    # finish_ticket uses) and routes the next_action from the RESULTING
    # board. Blocking a merely-TODO ticket leaves execution state untouched.
    # The ACTIVE case must be provable from the LOG alone: the block event
    # carries an explicit (active) marker so the validator's block-park
    # exception can never be satisfied by a TODO-ticket block event.
    is_active_block = (action == "block"
                       and state.get("task") == ticket_id
                       and ticket["section"] == "## DOING"
                       and state.get("phase") in phases.TICKET_BEARING_PHASES)
    if (action == "block" and ticket["section"] == "## DOING"
            and not is_active_block):
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       f"blocking DOING ticket {ticket_id} requires a "
                       f"ticket-bearing source phase "
                       f"({', '.join(sorted(phases.TICKET_BEARING_PHASES))}); "
                       f"STATE is {state.get('phase')!r} with task "
                       f"{state.get('task')!r}", ticket=ticket_id)
    event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                              f"ticket {action} via SAIOPS"
                              + (" (active)" if is_active_block else "")
                              + (f" -- {payload}" if payload else ""), now,
                              op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    if is_active_block:
        if not state.get("phase"):
            return _refuse("VALIDATION_FAILED",
                           "blocking the active ticket needs a real source "
                           "phase; STATE carries none, so transition_from "
                           "would be fabricated",
                           ticket=ticket_id)
        owned["phase"] = "DONE"
        owned["task"] = "none"
        if str(state.get("next_action") or "").startswith("WAIT:"):
            owned["next_action"] = state.get("next_action")
        else:
            owned["next_action"] = "saipen continue"
        owned["transition_from"] = state.get("phase")
    new_state = patch_state(docs["state"].text_norm, owned)
    # Routing after a structural move must not walk over a hard stop: a
    # safety-valve or user WAIT is preserved, never replaced by a fresh pick.
    # Unblock also re-routes, because moving a line back into ## TODO changes
    # the topmost-workable order the neutral state's next_action points at.
    from .router import route_next
    if action in ("block", "unblock") \
            and not str(state.get("next_action") or "").startswith("WAIT:"):
        _neutral = (state.get("task") in (None, "none")
                    and not any(t["section"] == "## DOING"
                                for t in parse_board(new_board)["tickets"].values()))
        if _neutral or is_active_block:
            routed = route_next(new_state, new_board)
            if routed.get("ok"):
                new_state = patch_state(new_state,
                                        {"next_action": routed["action"]})

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


def _plan_finish_ticket(root: Path, ticket_id: str, agent: str, now: str,
                        utc: str, digest_text: str | None = None,
                        digest_done: str | None = None,
                        digest_awaiting: str | None = None,
                        prefix_run: str | None = None,
                        ) -> OperationPlan | Result:
    """PLAN the ONE atomic ticket-closure operation (NITRO dogfood III).

    Closing a ticket is a cross-file transaction, not choreography: the split
    `transition state; move board ticket; repair next_action` leaves BOARD
    DONE[x] while STATE still names the ticket in a ticket-bearing phase --
    the exact corruption reproduced in DOGFOOD III. ONE OperationPlan owns:

    LOG:   ticket completion event (and, for a release closure, ONE truthful
           RUN event emitted immediately before it -- `prefix_run`, T-994 /
           § 15 -- so the release evidence is written by the SAME canonical
           LOG machinery, never a second writer, and the journal carries a
           single LOG target recovery can verify)
    BOARD: DOING -> DONE, [/] -> [x]
    STATE: phase -> DONE, task -> none, transition_from -> SHIP (the ACTUAL
           previous phase), last_event -> completion event, updated, agent
    NEXT:  computed from the resulting proposed state by the shared router.

    GATE PRECONDITION (NITRO dogfood IV, T-602): the ordinary ticket
    completion requires the ticket to have actually passed its required
    gates -- STATE.phase MUST be SHIP, STATE.task MUST be the ticket, and
    exactly one BOARD.DOING MUST be the ticket. From SCOUT/BUILD/VERIFY/
    REVIEW the finish REFUSEs ILLEGAL_PHASE with zero canonical bytes
    written. `transition_from` records the ACTUAL previous phase -- never a
    fabricated legal-looking DONE source. The SHIP gate cannot be skipped by
    laundering the phase history into a legal-looking final STATE.

    Required preconditions: exactly one BOARD.DOING, STATE.task == that
    ticket, ticket identity matches. No split-state window exists.
    """
    op_id = "finish-" + uuid4_hex8()
    docs, state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]
    if ticket["section"] != "## DOING" or ticket["checkbox"] != "/":
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       f"finish accepts only a ## DOING [/] ticket; "
                       f"{ticket_id} is {ticket['section']} "
                       f"[{ticket['checkbox']}]", ticket=ticket_id)
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if len(doing) != 1:
        return _refuse("ACTIVE_TICKET_MISMATCH",
                       f"finish needs exactly one ## DOING ticket, found "
                       f"{len(doing)}", ticket=ticket_id)
    if state.get("task") != ticket_id:
        return _refuse("ACTIVE_TICKET_MISMATCH",
                       f"STATE.task={state.get('task')} != finished ticket "
                       f"{ticket_id}", ticket=ticket_id)
    prev_phase = state.get("phase") or "DONE"

    # GATE: the canonical closure is SHIP -> DONE (CORE section 1.6). A
    # ticket may only be closed after its required gates (SCOUT/BUILD/VERIFY/
    # REVIEW/SHIP) actually ran in a legal path. The DFA makes SHIP reachable
    # only from REVIEW, and every transition is journaled, so requiring
    # phase == SHIP here IS the gate proof. Refusing from any earlier phase
    # with zero canonical bytes written is what makes skipped gates
    # mechanically impossible (NITRO dogfood IV, T-602).
    if prev_phase != "SHIP":
        return _refuse(
            "ILLEGAL_PHASE",
            f"finish requires phase SHIP (the canonical closure edge "
            f"SHIP -> DONE); actual phase {prev_phase} cannot close a ticket "
            "without its required REVIEW/SHIP gates. Run the ticket through "
            "REVIEW then SHIP first; the gates cannot be skipped by "
            "laundering the phase history",
            ticket=ticket_id, phase=prev_phase)
    closure_from = prev_phase  # the ACTUAL phase: SHIP.

    # One LOG completion event naming the ACTUAL closure phase -- the event
    # is the provenance that the gate chain actually ended at SHIP.
    if prefix_run:
        # ONE truthful RUN event emitted immediately before the completion
        # event, both through the canonical LOG builder (T-994 / § 15). The
        # journal then carries a SINGLE LOG target whose after-bytes recovery
        # can verify -- a second sequential LOG target would defeat per-target
        # before/after classification.
        run_event, run_line = build_event(
            log_tail, "RUN", prefix_run, ticket=ticket_id, agent=agent,
            now=now, op_id=op_id)
        event, line = build_event(
            run_event, "DEC",
            f"ticket finished via SAIOPS -- completion (from {prev_phase})",
            ticket=ticket_id, agent=agent, now=now, op_id=op_id)
        new_log = (docs["log"].text_norm.rstrip("\n") + "\n" + run_line
                   + "\n" + line + "\n")
    else:
        event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                                  f"ticket finished via SAIOPS -- completion "
                                  f"(from {prev_phase})", now, op_id)
        new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"

    # BOARD: DOING -> DONE, [/] -> [x], preserve all other fields.
    new_board = _move_ticket(docs["board"].text_norm, ticket_id, "## DONE",
                             "[x]", "done", "")

    # STATE: phase -> DONE, task -> none, transition_from -> the ACTUAL
    # previous phase (SHIP), and the next_action computed from the RESULTING
    # proposed state.
    owned = {
        "phase": "DONE",
        "task": "none",
        "next_action": "saipen continue",
        "transition_from": closure_from,
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)
    from .router import route_next
    routed = route_next(new_state, new_board)
    if routed.get("ok") and routed.get("action") != "saipen continue":
        new_state = patch_state(new_state, {"next_action": routed["action"]})

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed finish state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    # T-994 / § 16: the release closure OWNS the human digest. ship.md's
    # digest is a PLAN TARGET of the same journaled closure so a ship can
    # never report RELEASED with a stale/missing digest. Ordinary `ticket
    # done` passes no digest and stays LOG+BOARD+STATE only.
    if digest_text is not None:
        digest_doc = codec.read_document(
            root / ".saipen" / "kitchen" / "digest.md")
        targets.append(TargetPlan(
            ".saipen/kitchen/digest.md", "report",
            digest_doc.encode(digest_text),
            digest_doc.raw_hash,
            hash_bytes(digest_doc.encode(digest_text))))
    expected = {"ok": True, "code": "FINISHED", "ticket": ticket_id,
                "event_id": f"E-{event}", "phase": "DONE", "task": "none",
                "next_action": routed.get("action"),
                "transition_from": closure_from}
    if digest_text is not None:
        expected["digest"] = str(root / ".saipen" / "kitchen" / "digest.md")
    return build_plan(
        "finish", agent, _identity(root),
        {"operation": "finish", "ticket": ticket_id},
        _docs_preconditions(docs, "state", "board", "log"),
        targets, expected, op_id=op_id)


def finish_ticket(project_root: Path | str, ticket_id: str, agent: str,
                  dry_run: bool = False,
                  digest_text: str | None = None,
                  digest_done: str | None = None,
                  digest_awaiting: str | None = None,
                  prefix_run: str | None = None) -> Result:
    """Atomically finish a ticket: LOG + BOARD + STATE in ONE journaled plan.
    The public `ticket done` semantics become this operation.

    The release closure passes `digest_text` so the human digest commits in
    the SAME journaled transaction as the ticket closure (T-994 / § 16), and
    `prefix_run` to emit its ONE truthful release RUN event through the same
    canonical LOG builder (§ 15). The `digest_done` / `digest_awaiting` hints
    are reserved for the no-publish digest shape.
    """
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_finish_ticket(root, ticket_id, agent, now, utc,
                               digest_text=digest_text,
                               digest_done=digest_done,
                               digest_awaiting=digest_awaiting,
                               prefix_run=prefix_run)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


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
        marked = set_ticket_field(marked, "blocker",
                                  escape_ticket_description(payload or "blocked"))
    elif action == "unblock":
        marked = ticket_line.replace("- [/] ", "- [ ] ", 1)
        marked = remove_ticket_field(marked, "blocker")
        marked = remove_ticket_field(marked, "verify_attempts")
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
            or (cleaned.startswith("verify:") and len(cleaned) < 12))


def ticket_add(project_root: Path | str, agent: str, priority: str,
               description: str, needs: list[str], verify: str,
               dry_run: bool = False) -> Result:
    root = Path(project_root)
    if not description or not description.strip():
        return _refuse("INCOMPLETE_TICKET",
                       "ticket description is required (semantic input)")
    if "\n" in description or "\r" in description:
        return _refuse("VALIDATION_FAILED",
                       "ticket description may not contain line breaks -- "
                       "one ticket_add must render exactly one ticket line")
    if _is_placeholder_verify(verify):
        return _refuse("INCOMPLETE_TICKET",
                       "verify is a placeholder; a ticket needs a real DONE "
                       "proof (no TBD/TODO/empty)", verify=verify)
    if "\n" in verify or "\r" in verify:
        return _refuse("VALIDATION_FAILED",
                       "verify text may not contain line breaks")
    op_id = "ticket-" + uuid4_hex8()
    now, utc = _now(), _utc_iso()
    docs, _state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]))
    tid = next_ticket_id(docs["board"].text_norm, docs["log"].text_norm)
    for need in needs:
        if need not in board["tickets"]:
            return _refuse("TICKET_NOT_FOUND", f"dangling needs: {need}")
    description = escape_ticket_description(description)
    verify = escape_ticket_description(verify)
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
    """Move a ticket between BOARD sections.

    `done` is NOT a section move: it is the atomic ticket-closure operation
    (NITRO dogfood III, T-591). A standalone `done` here would leave the split
    (BOARD DONE[x] while STATE still names the ticket in a ticket-bearing
    phase) that the composition audit reproduced. `done` delegates to
    finish_ticket so one public operation, one lifecycle meaning.
    """
    if action == "done":
        return finish_ticket(project_root, ticket_id, agent,
                             dry_run=dry_run)
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
    docs, _state, _board, log_tail = _read(root)
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
    _docs, state, _board, _log_tail = _read(root)
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
                            f"goal reauthorized -- goal_waves {waves}->0, "
                            f"goal_tickets {tickets}->0",
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
    docs, state, _board, log_tail = _read(root)
    task = state.get("task")
    phase = state.get("phase")
    na = (f"PHASE {phase} {task}" if task and task != "none"
          else "saipen continue")

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


# ------------------------------------------------------- release scope (T-994)

RELEASE_SCOPE_DIR = ".saipen/kitchen/release_scope"


def _plan_record_scope(root: Path, ticket_id: str, agent: str, paths: list[str],
                       now: str, utc: str) -> OperationPlan | Result:
    """PLAN the exact reviewed release scope for a ticket (T-994 / § 2).

    The scope is the model's EXACT reviewed file list -- never inferred from
    dirty files, never `git add .`. It is bound to the ticket, the project
    identity and the source identity (HEAD + per-path content hashes), so the
    release planner can prove the bytes about to ship are the bytes that were
    reviewed. The record lives under `.saipen/kitchen/release_scope/` and is
    journaled through SAIOPS like any other canonical mutation.
    """
    op_id = "scope-" + uuid4_hex8()
    docs, state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    phase = state.get("phase")
    if phase not in ("REVIEW", "SHIP"):
        return _refuse(
            "ILLEGAL_PHASE",
            f"release scope may be recorded at REVIEW -> SHIP; actual phase "
            f"{phase} cannot name the reviewed scope for a release",
            ticket=ticket_id, phase=phase)
    if state.get("task") != ticket_id:
        return _refuse("ACTIVE_TICKET_MISMATCH",
                       f"STATE.task={state.get('task')} != scope ticket "
                       f"{ticket_id}", ticket=ticket_id)
    tickets = board["tickets"]
    ticket = tickets.get(ticket_id)
    if ticket is None or ticket["section"] != "## DOING":
        return _refuse("TICKET_NOT_FOUND",
                       f"{ticket_id} is not the active ## DOING ticket",
                       ticket=ticket_id)
    clean: list[str] = []
    for raw in paths:
        rel = Path(raw).as_posix()
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return _refuse("PATH_ESCAPE", f"scope path escapes project root: "
                            f"{rel}")
        clean.append(rel)
    clean = sorted(set(clean))
    if not clean:
        return _refuse("SOURCE_SCOPE_MISSING",
                       "release scope cannot be empty; name the exact reviewed "
                       "files", ticket=ticket_id)
    try:
        from freshness import compute_source_identity
        ident = compute_source_identity(root)
    except Exception as exc:
        return _refuse("VALIDATION_FAILED",
                       f"cannot compute source identity for scope binding: "
                       f"{exc}")
    hashes: dict[str, str] = {}
    for rel in clean:
        fp = root / rel
        if not fp.is_file():
            return _refuse("SOURCE_SCOPE_MISSING",
                           f"scope path does not exist: {rel}", ticket=ticket_id)
        hashes[rel] = hash_bytes(fp.read_bytes())
    import json
    record = {
        "schema_version": 1,
        "ticket": ticket_id,
        "project_identity": _identity(root),
        "source_head": ident.source_head,
        "source_tree_fingerprint": ident.source_tree_fingerprint,
        "paths": hashes,
        "recorded_at": utc,
        "op_id": op_id,
    }
    content = json.dumps(record, indent=2, sort_keys=True) + "\n"

    event, line = _event_line(
        docs, log_tail, "DEC", ticket_id, agent,
        f"release scope recorded -- {len(clean)} path(s) bound to "
        f"{ident.source_head[:12]}", now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {"last_event": event, "updated": utc, "agent": agent}
    new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed scope state fails fast validation: "
                       + "; ".join(errors[:5]))

    scope_rel = f"{RELEASE_SCOPE_DIR}/{ticket_id}.json"
    scope_doc = codec.read_document(root / scope_rel)
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
        TargetPlan(scope_rel, "report", scope_doc.encode(content),
                   scope_doc.raw_hash, hash_bytes(scope_doc.encode(content))),
    ]
    return build_plan(
        "scope", agent, _identity(root),
        {"operation": "scope", "ticket": ticket_id, "paths": clean},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "SCOPE_RECORDED", "ticket": ticket_id,
         "paths": clean, "event_id": f"E-{event}",
         "scope": scope_rel},
        op_id=op_id)


def record_scope(project_root: Path | str, ticket_id: str, agent: str,
                 paths: list[str], dry_run: bool = False) -> Result:
    """Journal the exact reviewed release scope for a ticket (T-994 / § 2)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_record_scope(root, ticket_id, agent, paths, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


# ------------------------------------------- first-publish wait (T-994 / § 11)

def _sanitize_remote(url: str) -> str:
    """Endpoint identity without credentials, normalized so `file://V:\\x`
    and `file://V:/x` are the same endpoint (T-994 / § 11)."""
    url = url.strip()
    if "://" in url:
        scheme, rest = url.split("://", 1)
        rest = rest.split("@", 1)[-1]
        return f"{scheme}://{rest.replace(chr(92), '/')}"
    if "@" in url:
        return url.split("@", 1)[-1].replace(chr(92), "/")
    return url.replace(chr(92), "/")


def _plan_first_publish_wait(root: Path, agent: str, remote_name: str,
                             now: str, utc: str) -> OperationPlan | Result:
    """PLAN the canonical first-publish WAIT checkpoint.

    ZERO commit/tag/push: the WAIT is a journaled canonical checkpoint that
    parks STATE.next_action on the exact ship.md line so the decision is
    recoverable evidence, not chat memory.
    """
    op_id = "wait-" + uuid4_hex8()
    docs, state, _board, log_tail = _read(root)
    task = state.get("task")
    remote_name = _sanitize_remote(remote_name)
    message = (f"first-publish -- confirm repo name '{remote_name}' and "
               "public/private before I push")
    event, line = build_event(log_tail, "WAIT", message, ticket=task,
                              agent=agent, now=now, op_id=op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    na = f"WAIT: {message}"
    owned = {"next_action": na, "last_event": event, "updated": utc,
             "agent": agent}
    new_state = patch_state(docs["state"].text_norm, owned)
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed first-publish WAIT state fails fast "
                       "validation: " + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "wait", agent, _identity(root),
        {"operation": "wait", "remote": remote_name},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "FIRST_PUBLISH_WAIT", "next_action": na,
         "event_id": f"E-{event}"},
        op_id=op_id)


def record_first_publish_wait(project_root: Path | str, agent: str,
                              remote_name: str,
                              dry_run: bool = False) -> Result:
    """Park STATE on the canonical first-publish WAIT (T-994 / § 11)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_first_publish_wait(root, agent, remote_name, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _plan_first_publish_confirm(root: Path, agent: str, remote_name: str,
                                visibility: str, now: str,
                                utc: str) -> OperationPlan | Result:
    """PLAN the canonical first-publish confirmation record.

    Confirmation is canonical evidence, never chat memory: the confirming
    agent journal-records the repo name + public/private decision into STATE
    bound to the exact remote identity, so a later `saipen ship` can verify
    the publication is authorized for THIS endpoint.
    """
    op_id = "fpc-" + uuid4_hex8()
    docs, state, _board, log_tail = _read(root)
    na = str(state.get("next_action") or "")
    if not na.startswith("WAIT: first-publish"):
        return _refuse("VALIDATION_FAILED",
                       "first-publish confirmation requires a pending "
                       "first-publish WAIT in STATE.next_action; current "
                       f"next_action is {na!r}")
    if visibility not in ("public", "private"):
        return _refuse("VALIDATION_FAILED",
                       f"visibility {visibility!r} outside public|private")
    remote_name = _sanitize_remote(remote_name)
    task = state.get("task")
    event, line = _event_line(
        docs, log_tail, "DEC", task, agent,
        f"first publish confirmed -- repo '{remote_name}' ({visibility})",
        now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "first_publish_confirmation": f"{remote_name} {visibility}",
        "next_action": (f"PHASE SHIP {task}" if task and task != "none"
                        else "saipen continue"),
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed first-publish confirmation state fails fast "
                       "validation: " + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "fpc", agent, _identity(root),
        {"operation": "fpc", "remote": remote_name, "visibility": visibility},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "FIRST_PUBLISH_CONFIRMED",
         "confirmation": f"{remote_name} {visibility}",
         "event_id": f"E-{event}"},
        op_id=op_id)


def confirm_first_publish(project_root: Path | str, agent: str,
                          remote_name: str, visibility: str,
                          dry_run: bool = False) -> Result:
    """Record canonical first-publish confirmation (T-994 / § 11)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_first_publish_confirm(root, agent, remote_name, visibility,
                                       now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
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

"""Core operations: claim / transition / checkpoint (NITRO M3).

Every operation is PLAN / APPLY separated. PLAN reads the project snapshot and
returns the intended LOG/BOARD/STATE bytes plus a refusal code, writing zero
canonical bytes. APPLY commits the verified plan through the common lock +
write-ahead journal + roll-forward recovery machinery (saipen_engine.journal).

The model never hand-edits STATE/BOARD fields once these operations exist:
it supplies the semantic request (ticket, agent, phase, event text); Python
records it correctly. OPS.md owns the contract.
"""

from __future__ import annotations

import datetime
import re
import uuid
from pathlib import Path

from . import codec
from .board import parse_board
from .journal import run_mutation
from .lock import project_writer_lock
from .log import log_tail_event
from .snapshot import ProjectSnapshot
from .state import parse_state

REQUIRED_HEADINGS = ["## DOING", "## TODO", "## DONE", "## BLOCKED"]

# The canonical transition table (CORE section 1.6), as data. The engine only
# records a legal transition; deciding whether the work deserves REVIEW stays
# the model's job.
VALID_TRANSITIONS = {
    "INIT": {"PLAN", "BLOCKED"},
    "PLAN": {"SCOUT", "BUILD", "DONE", "BLOCKED"},
    "SCOUT": {"BUILD", "BLOCKED"},
    "BUILD": {"VERIFY", "BLOCKED"},
    "VERIFY": {"REVIEW", "SCOUT", "BUILD", "BLOCKED"},
    "REVIEW": {"SHIP", "BUILD", "SCOUT", "BLOCKED"},
    "SHIP": {"DONE", "BUILD", "BLOCKED"},
    "DONE": {"SCOUT", "PLAN", "HUNT", "BLOCKED"},
    "VALIDATE": {"SCOUT", "PLAN", "DONE", "BLOCKED"},
    "HUNT": {"ADD", "PLAN", "SCOUT", "BLOCKED"},
    "MARKHUNT": {"DONE", "BLOCKED"},
    "ADD": {"BUILD", "PLAN", "SCOUT", "DONE", "BLOCKED"},
    "CLEAN": {"DONE", "BLOCKED"},
    "TRANSLATE": {"DONE", "BLOCKED"},
    "PREPARE": {"DONE", "BLOCKED"},
    "BLOCKED": {"PLAN", "SCOUT", "DONE"},
}
TICKET_BEARING_PHASES = {"SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP"}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d.%m.%y %H:%M")


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _alloc_event(log_text: str) -> int:
    tail = log_tail_event(log_text)
    return (tail or 0) + 1


def _claim_targets(root: Path, ticket_id: str, agent: str,
                   now: str, utc: str) -> tuple[list[dict], dict] | None:
    """PLAN a claim. Returns (targets, result) or None with a refusal dict."""
    state_text = codec.read_doc(root / ".saipen" / "STATE.md")
    board_text = codec.read_doc(root / ".saipen" / "BOARD.md")
    log_text = codec.read_doc(root / ".saipen" / "LOG.md")

    state = parse_state(state_text)
    board = parse_board(board_text)
    tickets = board["tickets"]

    if ticket_id not in tickets:
        return None, {"ok": False, "code": "TICKET_NOT_FOUND", "ticket":
                      ticket_id}
    ticket = tickets[ticket_id]
    if ticket["section"] == "## DOING":
        return None, {"ok": False, "code": "ALREADY_CLAIMED",
                      "detail": f"{ticket_id} is already in ## DOING"}
    if ticket["section"] != "## TODO":
        return None, {"ok": False, "code": "TICKET_NOT_WORKABLE",
                      "detail": f"{ticket_id} is under {ticket['section']}"}
    for need in ticket["needs"]:
        if need not in tickets or tickets[need]["section"] != "## DONE":
            return None, {"ok": False, "code": "TICKET_NOT_WORKABLE",
                          "detail": f"unmet needs: {need}"}
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if doing:
        return None, {"ok": False, "code": "ALREADY_CLAIMED",
                      "detail": f"DOING holds {doing[0]['id']}"}

    event = _alloc_event(log_text)
    date_line = now
    new_log = log_text.rstrip("\n") + "\n" + (
        f"- {date_line} [E-{event}] [{ticket_id}] DEC: claimed via SAIOPS "
        f"-- owner {agent}")
    new_state = _render_state(state, ticket_id, agent, event, utc)
    new_board = _move_ticket(board_text, ticket_id, agent, utc)

    targets = [
        {"path": ".saipen/LOG.md", "content": new_log + "\n"},
        {"path": ".saipen/BOARD.md", "content": new_board},
        {"path": ".saipen/STATE.md", "content": new_state},
    ]
    return targets, {"ok": True, "code": "CLAIMED", "ticket": ticket_id,
                     "event_id": f"E-{event}"}


def _render_state(state: dict, ticket_id: str, agent: str, event: int,
                  utc: str) -> str:
    prev_phase = state.get("phase", "DONE")
    lines = ["---",
             "phase: SCOUT",
             f"task: {ticket_id}",
             f'next_action: "PHASE SCOUT {ticket_id}"',
             "blocker: \"\"",
             f"transition_from: {prev_phase}",
             f"saipen_version: {state.get('saipen_version', 7)}",
             f"schema_version: {state.get('schema_version', 3)}",
             f"last_event: {event}",
             f"style_contract: {state.get('style_contract', '')}",
             f"saipen_home: \"{state.get('saipen_home', '')}\"",
             f"agent: {agent}",
             "requires:",
             "  - filesystem",
             "  - git",
             "  - python",
             "mode: full",
             "updated: " + utc,
             "---"]
    return "\n".join(lines) + "\n"


def _move_ticket(board_text: str, ticket_id: str, agent: str,
                 utc: str) -> str:
    """Surgical ticket move: only the target ticket's placement/fields change.

    The board already carries the four canonical headings; the claimed ticket
    line is inserted immediately after the existing `## DOING` heading and
    removed from `## TODO`.
    """
    lines = board_text.splitlines(keepends=True)
    out = []
    ticket_line = None
    doing_idx = None
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("- [ ] " + ticket_id + " "):
            ticket_line = stripped
            continue  # drop from TODO
        if stripped.startswith("## DOING"):
            doing_idx = len(out)
        out.append(line)
    if ticket_line is None or doing_idx is None:
        raise ValueError("cannot locate ticket or DOING section")
    marked = ticket_line.replace("- [ ] ", "- [/] ", 1).rstrip() + \
        f" | owner: {agent} | claim_time: {utc}"
    out.insert(doing_idx + 1, marked + "\n")
    return "".join(out)


def plan_claim(project_root: Path | str, ticket_id: str, agent: str) -> dict:
    """PLAN a claim: intended result or a stable refusal. Zero disk writes."""
    now = _now()
    utc = _utc_iso()
    targets, result = _claim_targets(Path(project_root), ticket_id, agent,
                                     now, utc)
    if targets is None:
        return result
    result["op_id"] = "claim-" + uuid.uuid4().hex[:8]
    result["changed_files"] = [t["path"] for t in targets]
    result["phase"] = "SCOUT"
    result["next_action"] = f"PHASE SCOUT {ticket_id}"
    result["dry_run"] = True
    return result


def apply_claim(project_root: Path | str, ticket_id: str, agent: str) -> dict:
    """APPLY a claim through the lock + journal + roll-forward machinery."""
    root = Path(project_root)
    now = _now()
    utc = _utc_iso()
    targets, result = _claim_targets(root, ticket_id, agent, now, utc)
    if targets is None:
        return result
    op_id = "claim-" + uuid.uuid4().hex[:8]
    snap = ProjectSnapshot.capture(root)
    preconditions = {
        ".saipen/STATE.md": snap.state_hash,
        ".saipen/BOARD.md": snap.board_hash,
        ".saipen/LOG.md": snap.log_hash,
    }
    with project_writer_lock(root):
        commit = run_mutation(root, op_id, agent, snap.project_identity,
                              preconditions, targets)
    result = {**commit, **result}
    result["ticket"] = ticket_id
    return result


def _transition_targets(root: Path, destination: str, agent: str,
                        ticket_id: str | None, event_text: str,
                        now: str, utc: str) -> tuple[list[dict], dict] | None:
    state_text = codec.read_doc(root / ".saipen" / "STATE.md")
    log_text = codec.read_doc(root / ".saipen" / "LOG.md")
    state = parse_state(state_text)
    current = state.get("phase")
    if destination not in VALID_TRANSITIONS.get(current or "", set()):
        return None, {"ok": False, "code": "ILLEGAL_TRANSITION",
                      "detail": f"{current} -> {destination}"}
    if destination in TICKET_BEARING_PHASES and not ticket_id:
        return None, {"ok": False, "code": "ILLEGAL_TRANSITION",
                      "detail": f"{destination} is ticket-bearing and needs "
                                "a T-ID"}
    subject = ticket_id or state.get("task")
    event = _alloc_event(log_text)
    taxonomy = "RUN"
    new_log = log_text.rstrip("\n") + "\n" + (
        f"- {now} [E-{event}]"
        + (f" [{subject}]" if subject else "")
        + f" {taxonomy}: {event_text}")
    prev_phase = current
    new_state = _render_state(state, subject or "none", agent, event, utc)
    lines = new_state.splitlines(keepends=True)
    phase_line = next(i for i, ln in enumerate(lines)
                      if ln.startswith("phase: "))
    lines[phase_line] = f"phase: {destination}\n"
    na = f"saipen {destination.lower()}" if destination not in (
        TICKET_BEARING_PHASES) else f"PHASE {destination} {subject}"
    na_line = next(i for i, ln in enumerate(lines)
                   if ln.startswith("next_action:"))
    lines[na_line] = f'next_action: "{na}"\n'
    tf_line = next(i for i, ln in enumerate(lines)
                   if ln.startswith("transition_from:"))
    lines[tf_line] = f"transition_from: {prev_phase}\n"
    new_state = "".join(lines)
    board_text = codec.read_doc(root / ".saipen" / "BOARD.md")
    targets = [
        {"path": ".saipen/LOG.md", "content": new_log + "\n"},
        {"path": ".saipen/BOARD.md", "content": board_text},
        {"path": ".saipen/STATE.md", "content": new_state},
    ]
    return targets, {"ok": True, "code": "TRANSITIONED", "phase": destination,
                     "event_id": f"E-{event}"}


def transition_phase(project_root: Path | str, destination: str,
                     agent: str, ticket_id: str | None = None,
                     event_text: str = "", dry_run: bool = False) -> dict:
    """Transition to a legal destination phase, journalled. The engine records
    only a legal transition; the model decides whether the work deserves it."""
    root = Path(project_root)
    now = _now()
    utc = _utc_iso()
    targets, result = _transition_targets(
        root, destination.upper(), agent, ticket_id, event_text or
        f"transition to {destination}", now, utc)
    if targets is None:
        return result
    result["op_id"] = "transition-" + uuid.uuid4().hex[:8]
    result["changed_files"] = [t["path"] for t in targets]
    if dry_run:
        result["dry_run"] = True
        return result
    snap = ProjectSnapshot.capture(root)
    preconditions = {
        ".saipen/STATE.md": snap.state_hash,
        ".saipen/LOG.md": snap.log_hash,
    }
    with project_writer_lock(root):
        commit = run_mutation(root, result["op_id"], agent,
                              snap.project_identity, preconditions, targets)
    result = {**commit, **result}
    return result


def checkpoint(project_root: Path | str, agent: str, taxonomy: str,
               ticket_id: str | None, description: str,
               dry_run: bool = False) -> dict:
    """Generic high-frequency checkpoint: one allocated E-ID LOG event plus
    the STATE last_event bump. The model never hand-numbers events."""
    root = Path(project_root)
    now = _now()
    utc = _utc_iso()
    state_text = codec.read_doc(root / ".saipen" / "STATE.md")
    log_text = codec.read_doc(root / ".saipen" / "LOG.md")
    event = _alloc_event(log_text)
    new_log = log_text.rstrip("\n") + "\n" + (
        f"- {now} [E-{event}]"
        + (f" [{ticket_id}]" if ticket_id else "")
        + f" {taxonomy.upper()}: {description}")
    state = parse_state(state_text)
    new_state = _render_state(state, state.get("task") or "none", agent,
                              event, utc)
    board_text = codec.read_doc(root / ".saipen" / "BOARD.md")
    targets = [
        {"path": ".saipen/LOG.md", "content": new_log + "\n"},
        {"path": ".saipen/BOARD.md", "content": board_text},
        {"path": ".saipen/STATE.md", "content": new_state},
    ]
    result = {"ok": True, "code": "CHECKPOINTED", "event_id": f"E-{event}",
              "op_id": "checkpoint-" + uuid.uuid4().hex[:8],
              "changed_files": [t["path"] for t in targets]}
    if dry_run:
        result["dry_run"] = True
        return result
    snap = ProjectSnapshot.capture(root)
    preconditions = {
        ".saipen/STATE.md": snap.state_hash,
        ".saipen/LOG.md": snap.log_hash,
    }
    with project_writer_lock(root):
        commit = run_mutation(root, result["op_id"], agent,
                              snap.project_identity, preconditions, targets)
    result = {**commit, **result}
    return result

SYNTHETIC_TICKET_IDS = {998, 999}


def next_ticket_id(board_text: str, log_text: str) -> int:
    """The next canonical production ticket ID.

    Scans the canonical BOARD and production LOG for T-### and returns
    max+1, excluding the synthetic fixture namespace (T-998/T-999) so a
    regression fixture can never shift the allocator.
    """
    ids = [int(m) for m in re.findall(r"\bT-(\d+)\b", board_text + "\n" + log_text)]
    return max((i for i in ids if i not in SYNTHETIC_TICKET_IDS), default=0) + 1


def _ticket_targets(root: Path, action: str, ticket_id: str, agent: str,
                    payload: str, now: str, utc: str) -> tuple[list[dict], dict] | None:
    state_text = codec.read_doc(root / ".saipen" / "STATE.md")
    board_text = codec.read_doc(root / ".saipen" / "BOARD.md")
    log_text = codec.read_doc(root / ".saipen" / "LOG.md")
    board = parse_board(board_text)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return None, {"ok": False, "code": "TICKET_NOT_FOUND", "ticket": ticket_id}
    target = {"done": "## DONE", "block": "## BLOCKED", "unblock": "## TODO"}[action]
    checkbox = {"done": "[x]", "block": "[ ]", "unblock": "[ ]"}[action]
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
        for h in ("## DOING", "## TODO", "## DONE", "## BLOCKED"):
            if stripped.startswith(h):
                heading_idx[h] = len(out)
        out.append(line)
    if ticket_line is None:
        return None, {"ok": False, "code": "TICKET_NOT_FOUND", "ticket": ticket_id}
    target_idx = heading_idx.get(target)
    if target_idx is None:
        return None, {"ok": False, "code": "VALIDATION_FAILED"}
    mark = ticket_line.replace("- [/] ", "- " + checkbox + " ", 1).replace(
        "- [ ] ", "- " + checkbox + " ", 1)
    if action == "done":
        mark = mark + " | verify: " + (payload or "verified")
    elif action == "block":
        mark = mark + " | blocker: " + (payload or "blocked")
    elif action == "unblock":
        mark = mark.replace(" | blocker:", " | ")
    out.insert(target_idx + 1, mark + "\n")
    event = _alloc_event(log_text)
    new_log = log_text.rstrip("\n") + "\n" + (
        f"- {now} [E-{event}] [{ticket_id}] DEC: ticket {action} via SAIOPS"
        + (f" -- {payload}" if payload else ""))
    state = parse_state(state_text)
    new_state = _render_state(state, state.get("task") or "none", agent,
                              event, utc)
    return [
        {"path": ".saipen/LOG.md", "content": new_log + "\n"},
        {"path": ".saipen/BOARD.md", "content": "".join(out)},
        {"path": ".saipen/STATE.md", "content": new_state},
    ], {"ok": True, "code": action.upper(), "event_id": f"E-{event}"}


def ticket_add(project_root: Path | str, agent: str, priority: str,
               description: str, needs: list[str], verify: str,
               dry_run: bool = False) -> dict:
    """Add a ticket at the top of ## TODO with the next canonical ID."""
    root = Path(project_root)
    now = _now()
    utc = _utc_iso()
    board_text = codec.read_doc(root / ".saipen" / "BOARD.md")
    log_text = codec.read_doc(root / ".saipen" / "LOG.md")
    tid = next_ticket_id(board_text, log_text)
    board = parse_board(board_text)
    for need in needs:
        if need not in board["tickets"]:
            return {"ok": False, "code": "TICKET_NOT_FOUND",
                    "detail": f"dangling needs: {need}"}
    desc = (f"- [ ] T-{tid} [{priority}] {description}"
            + (f" | needs: {', '.join(needs)}" if needs else "")
            + f" | verify: {verify}")
    lines = board_text.splitlines(keepends=True)
    todo_idx = next(i for i, ln in enumerate(lines)
                    if ln.startswith("## TODO"))
    lines.insert(todo_idx + 1, desc + "\n")
    event = _alloc_event(log_text)
    new_log = log_text.rstrip("\n") + "\n" + (
        f"- {now} [E-{event}] [T-{tid}] DEC: ticket added via SAIOPS")
    state = parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))
    new_state = _render_state(state, state.get("task") or "none", agent,
                              event, utc)
    targets = [
        {"path": ".saipen/LOG.md", "content": new_log + "\n"},
        {"path": ".saipen/BOARD.md", "content": "".join(lines)},
        {"path": ".saipen/STATE.md", "content": new_state},
    ]
    result = {"ok": True, "code": "TICKET_ADDED", "ticket": f"T-{tid}",
              "op_id": "ticket-" + uuid.uuid4().hex[:8],
              "changed_files": [t["path"] for t in targets],
              "event_id": f"E-{event}"}
    if dry_run:
        result["dry_run"] = True
        return result
    snap = ProjectSnapshot.capture(root)
    preconditions = {
        ".saipen/STATE.md": snap.state_hash,
        ".saipen/BOARD.md": snap.board_hash,
        ".saipen/LOG.md": snap.log_hash,
    }
    with project_writer_lock(root):
        commit = run_mutation(root, result["op_id"], agent,
                              snap.project_identity, preconditions, targets)
    return {**commit, **result}


def ticket_move(project_root: Path | str, action: str, ticket_id: str,
                agent: str, payload: str = "", dry_run: bool = False) -> dict:
    """done / block / unblock: move exactly one ticket between sections."""
    root = Path(project_root)
    now = _now()
    utc = _utc_iso()
    targets, result = _ticket_targets(root, action, ticket_id, agent,
                                      payload, now, utc)
    if targets is None:
        return result
    result["op_id"] = "ticket-" + uuid.uuid4().hex[:8]
    result["changed_files"] = [t["path"] for t in targets]
    if dry_run:
        result["dry_run"] = True
        return result
    snap = ProjectSnapshot.capture(root)
    preconditions = {
        ".saipen/STATE.md": snap.state_hash,
        ".saipen/BOARD.md": snap.board_hash,
        ".saipen/LOG.md": snap.log_hash,
    }
    with project_writer_lock(root):
        commit = run_mutation(root, result["op_id"], agent,
                              snap.project_identity, preconditions, targets)
    return {**commit, **result}

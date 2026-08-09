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
    result.update(commit)
    result["ticket"] = ticket_id
    return result

#!/usr/bin/env python
"""saipen -- thin adapter over the SAIPEN engine (NITRO).

Read-only commands: `saipen status`, `saipen next`. Mutating commands run
PLAN/APPLY through the engine's lock + journal + recovery machinery:
`claim`, `transition`, `checkpoint`, `ticket add/done/block/unblock`.
`saipen recover` lists and resolves pending operation journals; status and
next derive `recovery_pending` from the real journal state, never a hardcoded
false.

Exit codes: 0 success, 1 refused, 2 usage, 3 not a SAIPEN project.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from saipen_engine import codec, snapshot
from saipen_engine.board import parse_board
from saipen_engine.journal import auto_recover_pending, pending_ops
from saipen_engine.operations import (apply_claim, checkpoint, plan_claim,
                                       ticket_add, ticket_move,
                                       transition_phase)
from saipen_engine.state import parse_state

AGENT = "saipen-cli"

HOME = Path(__file__).resolve().parent.parent
VERSION_FILE = HOME / "VERSION"


def _agent_for(project_root: Path) -> str:
    """The acting seat, inherited from STATE (never invented by the CLI)."""
    state_path = _state_path(project_root)
    if state_path.is_file():
        agent = parse_state(codec.read_doc(state_path)).get("agent")
        if agent:
            return agent
    return AGENT


def _protocol_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _state_path(project_root: Path) -> Path:
    return project_root / ".saipen" / "STATE.md"


def _pending(project_root: Path) -> list[str]:
    return [op["op_id"] for op in pending_ops(project_root)]


def _status(project_root: Path, as_json: bool) -> int:
    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    state = parse_state(codec.read_doc(state_path))
    snap = snapshot.ProjectSnapshot.capture(project_root)
    board = parse_board(codec.read_doc(project_root / ".saipen" / "BOARD.md"))
    doing = [t for t in board["tickets"].values()
             if t["section"] == "## DOING"]
    todo = [t for t in board["tickets"].values() if t["section"] == "## TODO"]
    top_workable = None
    for ticket in todo:
        needs = ticket["needs"]
        if all(n in board["tickets"] and board["tickets"][n]["section"]
               == "## DONE" for n in needs):
            top_workable = ticket["id"]
            break
    pending = _pending(project_root)
    _emit({
        "ok": True,
        "project_identity": snap.project_identity,
        "protocol_version": _protocol_version(),
        "phase": state.get("phase"),
        "task": state.get("task"),
        "next_action": state.get("next_action"),
        "blocker": state.get("blocker"),
        "execution_intent": state.get("execution_intent"),
        "claimed_ticket": doing[0]["id"] if doing else None,
        "top_workable_ticket": top_workable,
        "log_tail_event": snap.log_tail,
        "head": snap.head,
        "board_errors": board["errors"],
        "recovery_pending": bool(pending),
        "pending_ops": pending,
    }, as_json)
    return 0


def _next_action(project_root: Path, as_json: bool) -> int:
    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    state = parse_state(codec.read_doc(state_path))
    na = state.get("next_action") or ""
    phase = (state.get("phase") or "").lower()
    subject = state.get("task")
    pending = _pending(project_root)
    _emit({
        "ok": True,
        "action": na,
        "ticket": subject,
        "load": f"saipen/phases/{phase}.md" if phase else None,
        "recovery_pending": bool(pending),
        "pending_ops": pending,
    }, as_json)
    return 0


def _recover(project_root: Path, as_json: bool) -> int:
    pending = _pending(project_root)
    if not pending:
        _emit({"ok": True, "code": "CLEAN", "pending_ops": []}, as_json)
        return 0
    result = auto_recover_pending(project_root)
    _emit(result, as_json)
    return 0 if result.get("ok") else 1


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not payload.get("ok"):
        print(f"REFUSE [{payload.get('code', 'ERROR')}]")
        return
    if payload.get("code") == "NOT_SAIPEN_PROJECT":
        return
    for key in ("action", "ticket", "load", "phase", "task", "next_action",
                "claimed_ticket", "top_workable_ticket", "log_tail_event",
                "head", "pending_ops", "code"):
        value = payload.get(key)
        if value is not None and value != []:
            print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    as_json = "--json" in args
    dry_run = "--dry-run" in args
    args = [a for a in args if a not in ("--json", "--dry-run")]
    if not args or args[0] in ("-h", "--help"):
        print("usage: saipen (status|next|recover|claim <T-###>|"
              "transition <PHASE> [T-###] [text]|checkpoint <TAXONOMY> "
              "[T-###] [text]|ticket add <PRIORITY> <text>|ticket "
              "done|block|unblock <T-###> [text]) [--dry-run] [--json]")
        return 2
    command = args[0]
    project_root = Path.cwd()
    if command == "status":
        return _status(project_root, as_json)
    if command == "next":
        return _next_action(project_root, as_json)
    if command == "recover":
        return _recover(project_root, as_json)
    if command == "claim":
        if len(args) < 2:
            _emit({"ok": False, "code": "TICKET_NOT_FOUND"}, as_json)
            return 2
        result = plan_claim(project_root, args[1], _agent_for(project_root)) if dry_run \
            else apply_claim(project_root, args[1], _agent_for(project_root))
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command == "transition":
        if len(args) < 2:
            _emit({"ok": False, "code": "ILLEGAL_TRANSITION"}, as_json)
            return 2
        ticket = args[2] if len(args) > 2 and args[2].upper().startswith(
            "T-") else None
        text = " ".join(args[3:] if ticket else args[2:])
        result = transition_phase(project_root, args[1], _agent_for(project_root), ticket, text,
                                  dry_run=dry_run)
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command == "checkpoint":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED"}, as_json)
            return 2
        ticket = args[2] if len(args) > 2 and args[2].upper().startswith(
            "T-") else None
        text = " ".join(args[3:] if ticket else args[2:])
        result = checkpoint(project_root, _agent_for(project_root), args[1], ticket, text,
                            dry_run=dry_run)
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command == "ticket" and len(args) >= 2:
        action = args[1]
        rest = args[2:]
        if action == "add":
            if len(rest) < 2:
                _emit({"ok": False, "code": "VALIDATION_FAILED"}, as_json)
                return 2
            result = ticket_add(project_root, _agent_for(project_root), rest[0], rest[1],
                                [], "verify: TBD", dry_run=dry_run)
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
        if action in ("done", "block", "unblock") and rest:
            result = ticket_move(project_root, action, rest[0], _agent_for(project_root),
                                 " ".join(rest[1:]), dry_run=dry_run)
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
    print(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

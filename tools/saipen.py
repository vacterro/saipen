#!/usr/bin/env python
"""saipen -- thin adapter over the SAIPEN engine (NITRO M1).

Read-only commands today: `saipen status` and `saipen next`. The engine
(``saipen_engine``) is the single implementation; this file is a thin CLI.
Later milestones add `claim` / `transition` / `checkpoint` / `recover` on the
same engine operations (saipen/OPS.md).

Exit codes: 0 success, 2 usage, 3 not a SAIPEN project.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from saipen_engine import codec, snapshot
from saipen_engine.board import parse_board
from saipen_engine.operations import (apply_claim, checkpoint, plan_claim,
                                       transition_phase)
from saipen_engine.state import parse_state

AGENT = "saipen-cli"

HOME = Path(__file__).resolve().parent.parent
VERSION_FILE = HOME / "VERSION"


def _protocol_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _state_path(project_root: Path) -> Path:
    return project_root / ".saipen" / "STATE.md"


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
        "recovery_pending": False,
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
    _emit({
        "ok": True,
        "action": na,
        "ticket": subject,
        "load": f"saipen/phases/{phase}.md" if phase else None,
        "recovery_pending": False,
    }, as_json)
    return 0


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
                "head"):
        value = payload.get(key)
        if value is not None:
            print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    as_json = "--json" in args
    dry_run = "--dry-run" in args
    args = [a for a in args if a not in ("--json", "--dry-run")]
    if not args or args[0] in ("-h", "--help"):
        print("usage: saipen (status|next|claim <T-###>|transition <PHASE> "
              "[T-###] [text]|checkpoint <TAXONOMY> [T-###] [text]) "
              "[--dry-run] [--json]")
        return 2
    command = args[0]
    project_root = Path.cwd()
    if command == "status":
        return _status(project_root, as_json)
    if command == "next":
        return _next_action(project_root, as_json)
    if command == "claim":
        if len(args) < 2:
            _emit({"ok": False, "code": "TICKET_NOT_FOUND"}, as_json)
            return 2
        result = plan_claim(project_root, args[1], AGENT) if dry_run \
            else apply_claim(project_root, args[1], AGENT)
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if command == "transition":
        if len(args) < 2:
            _emit({"ok": False, "code": "ILLEGAL_TRANSITION"}, as_json)
            return 2
        ticket = args[2] if len(args) > 2 and args[2].upper().startswith(
            "T-") else None
        text = " ".join(args[3:] if ticket else args[2:])
        result = transition_phase(project_root, args[1], AGENT, ticket, text,
                                  dry_run=dry_run)
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if command == "checkpoint":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED"}, as_json)
            return 2
        ticket = args[2] if len(args) > 2 and args[2].upper().startswith(
            "T-") else None
        text = " ".join(args[3:] if ticket else args[2:])
        result = checkpoint(project_root, AGENT, args[1], ticket, text,
                            dry_run=dry_run)
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    print(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

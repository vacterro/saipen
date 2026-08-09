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
from saipen_engine.journal import (auto_recover_pending, pending_conflicts,
                                   pending_ops)
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


def _conflicts(project_root: Path) -> list[str]:
    return [op["op_id"] for op in pending_conflicts(project_root)]


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
    conflicts = _conflicts(project_root)
    from saipen_engine.router import route_next
    routed = route_next(codec.read_doc(state_path), codec.read_doc(
        project_root / ".saipen" / "BOARD.md"), pending, conflicts)
    _emit({
        "ok": True,
        "project_identity": snap.project_identity,
        "protocol_version": _protocol_version(),
        "phase": state.get("phase"),
        "task": state.get("task"),
        "next_action": state.get("next_action"),
        "computed_next_action": routed.get("action"),
        "computed_reason": routed.get("reason"),
        "blocker": state.get("blocker"),
        "execution_intent": state.get("execution_intent"),
        "claimed_ticket": doing[0]["id"] if doing else None,
        "top_workable_ticket": top_workable,
        "log_tail_event": snap.log_tail,
        "head": snap.head,
        "board_errors": board["errors"],
        "recovery_pending": bool(pending),
        "recovery_conflict": bool(conflicts),
        "pending_ops": pending,
        "conflict_ops": conflicts,
    }, as_json)
    return 0


def _next_action(project_root: Path, as_json: bool) -> int:
    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    state_text = codec.read_doc(state_path)
    state = parse_state(state_text)
    phase = (state.get("phase") or "").lower()
    subject = state.get("task")
    pending = _pending(project_root)
    conflicts = _conflicts(project_root)
    board_text = codec.read_doc(project_root / ".saipen" / "BOARD.md")
    from saipen_engine.router import route_next
    routed = route_next(state_text, board_text, pending, conflicts)
    if not routed.get("ok"):
        _emit({
            "ok": False,
            "code": "RECOVERY_CONFLICT" if conflicts else "RECOVERY_REQUIRED",
            "action": routed.get("action"),
            "reason": routed.get("reason"),
            "detail": routed.get("detail", ""),
            "recovery_pending": True,
            "recovery_conflict": bool(conflicts),
            "conflict_ops": conflicts,
            "pending_ops": pending,
        }, as_json)
        return 1
    _emit({
        "ok": True,
        "action": routed.get("action"),
        "ticket": routed.get("ticket") or subject,
        "reason": routed.get("reason"),
        "load": f"saipen/phases/{phase}.md" if phase else None,
        "recovery_pending": bool(pending),
        "recovery_conflict": False,
        "pending_ops": pending,
    }, as_json)
    return 0


def _recover(project_root: Path, as_json: bool) -> int:
    conflicts = _conflicts(project_root)
    if conflicts:
        _emit({"ok": False, "code": "CONFLICT",
               "op_ids": conflicts,
               "recovery_required": True,
               "detail": "unresolved conflict(s): " + ", ".join(conflicts)
                         + "; evidence preserved, resolve explicitly before "
                         "further mutation"}, as_json)
        return 1
    pending = _pending(project_root)
    if not pending:
        _emit({"ok": True, "code": "CLEAN", "pending_ops": []}, as_json)
        return 0
    result = auto_recover_pending(project_root)
    _emit(result, as_json)
    return 0 if result.get("ok") else 1


def _sub(project_root: Path, args: list[str], as_json: bool,
         dry_run: bool) -> int:
    """saipen sub list|status|spawn|pause|resume (NITRO M8, journaled)."""
    from saipen_engine.subs import (sub_adopt, sub_clean_preflight, sub_collect,
                                    sub_list, sub_pause, sub_resume, sub_spawn,
                                    sub_status)

    action = args[0]
    if action == "list":
        result = sub_list(project_root)
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if action == "status":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "sub status needs <name>"}, as_json)
            return 2
        result = sub_status(project_root, args[1])
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if action == "spawn":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "sub spawn needs <name>"}, as_json)
            return 2
        state = parse_state(codec.read_doc(_state_path(project_root)))
        saipen_home = state.get("saipen_home") or str(HOME)
        result = sub_spawn(project_root, args[1], saipen_home)
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if action in ("pause", "resume"):
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": f"sub {action} needs <name>"}, as_json)
            return 2
        fn = sub_pause if action == "pause" else sub_resume
        result = fn(project_root, args[1])
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if action == "adopt":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "sub adopt needs <name>"}, as_json)
            return 2
        state = parse_state(codec.read_doc(_state_path(project_root)))
        saipen_home = state.get("saipen_home") or str(HOME)
        result = sub_adopt(project_root, args[1], saipen_home)
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if action == "clean":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "sub clean needs <name>"}, as_json)
            return 2
        result = sub_clean_preflight(project_root, args[1])
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if action == "collect":
        name = args[1] if len(args) > 1 else None
        result = sub_collect(project_root, name)
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    _emit({"ok": False, "code": "VALIDATION_FAILED",
           "detail": f"unknown sub action {action!r}"}, as_json)
    return 2


def _context(project_root: Path, args: list[str], as_json: bool,
             dry_run: bool) -> int:
    """saipen context cold|hot|audit (NITRO M9, read-only)."""
    from saipen_engine.context import context_audit, context_cold, context_hot

    mode = args[0]
    fn = {"cold": context_cold, "hot": context_hot,
          "audit": context_audit}.get(mode)
    if fn is None:
        _emit({"ok": False, "code": "VALIDATION_FAILED",
               "detail": f"unknown context mode {mode!r}; use cold|hot|audit"},
              as_json)
        return 2
    result = fn(project_root)
    if as_json:
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if not result.ok:
        _emit(result.to_dict(), as_json)
        return 1
    if mode == "audit":
        import json
        payload = result.to_dict()
        payload.pop("ok", None)
        payload.pop("code", None)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(result.get("surface", ""), end="")
    return 0


def _userperson(project_root: Path, args: list[str], as_json: bool,
                dry_run: bool) -> int:
    """saipen userperson show/add/remove/reset (NITRO M7, journaled)."""
    from userperson import (merge_profile, parse_profile, profile_path,
                            remove_preference, render_profile,
                            write_profile)

    path = profile_path(project_root)
    action = args[0]
    current_text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
    if action == "show":
        if not current_text:
            _emit({"ok": True, "code": "EMPTY", "preferences": []}, as_json)
            return 0
        if as_json:
            _emit({"ok": True, "code": "SHOW",
                   "preferences": parse_profile(current_text)["preferences"]},
                  as_json)
        else:
            print(current_text, end="")
        return 0
    if action == "reset":
        if not path.is_file():
            _emit({"ok": False, "code": "TICKET_NOT_FOUND",
                   "detail": "no profile to reset"}, as_json)
            return 1
        if "--confirm" not in args:
            _emit({"ok": False, "code": "DESTRUCTIVE_CONFIRMATION_REQUIRED",
                   "detail": "userperson reset deletes the profile; pass "
                             "--confirm to authorize"}, as_json)
            return 1
        if dry_run:
            _emit({"ok": True, "code": "RESET", "dry_run": True}, as_json)
            return 0
        # CORE says reset DELETES the profile; absence is the canonical OFF
        # state. The journal writes targets, so deletion is expressed as a
        # committed empty profile followed by removing the file -- absence is
        # achieved, and the commit is recoverable evidence.
        result = write_profile(project_root, "# USERPERSON\n\n",
                               _agent_for(project_root))
        if result.get("ok"):
            path.unlink(missing_ok=True)
            result["code"] = "RESET"
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if action in ("add", "remove"):
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": f"userperson {action} needs <text>"}, as_json)
            return 2
        category = "general"
        clean_args = []
        idx = 0
        while idx < len(args):
            if args[idx] == "--category" and idx + 1 < len(args):
                category = args[idx + 1]
                idx += 2
            else:
                clean_args.append(args[idx])
                idx += 1
        text = " ".join(clean_args[1:])
        current = parse_profile(current_text)["preferences"] \
            if current_text else []
        if action == "add":
            # The MODEL supplies the distilled category (semantic decision);
            # the writer never invents one (NITRO dogfood II).
            updated = merge_profile(current,
                                    [f"- [{category}] {text}"])
        else:
            updated = remove_preference(current, text)
        new_text = render_profile(updated)
        if new_text == current_text:
            _emit({"ok": True, "code": "UNCHANGED"}, as_json)
            return 0
        result = write_profile(project_root, new_text, _agent_for(project_root))
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    _emit({"ok": False, "code": "VALIDATION_FAILED",
           "detail": f"unknown userperson action {action!r}"}, as_json)
    return 2


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
                _emit({"ok": False, "code": "VALIDATION_FAILED",
                       "detail": "ticket add <PRIORITY> <description> "
                                 "[--verify <text>] [--needs T-X,T-Y]"},
                      as_json)
                return 2
            verify_arg = ""
            needs_arg = []
            clean_rest = []
            idx = 0
            while idx < len(rest):
                if rest[idx] == "--verify" and idx + 1 < len(rest):
                    verify_arg = rest[idx + 1]
                    idx += 2
                elif rest[idx] == "--needs" and idx + 1 < len(rest):
                    needs_arg = [n.strip() for n in rest[idx + 1].split(",")
                                 if n.strip()]
                    idx += 2
                else:
                    clean_rest.append(rest[idx])
                    idx += 1
            if len(clean_rest) < 2:
                _emit({"ok": False, "code": "VALIDATION_FAILED",
                       "detail": "ticket add needs <PRIORITY> <description>"},
                      as_json)
                return 2
            result = ticket_add(project_root, _agent_for(project_root),
                                clean_rest[0], " ".join(clean_rest[1:]),
                                needs_arg, verify_arg, dry_run=dry_run)
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
        if action in ("done", "block", "unblock") and rest:
            result = ticket_move(project_root, action, rest[0], _agent_for(project_root),
                                 " ".join(rest[1:]), dry_run=dry_run)
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
    if command == "userperson" and len(args) >= 1:
        return _userperson(project_root, args[1:], as_json, dry_run)
    if command == "sub" and len(args) >= 1:
        return _sub(project_root, args[1:], as_json, dry_run)
    if command == "context" and len(args) >= 1:
        return _context(project_root, args[1:], as_json, dry_run)
    print(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

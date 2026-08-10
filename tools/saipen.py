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
from saipen_engine.operations import (apply_claim, checkpoint, finish_ticket,
                                       plan_claim, ticket_add, ticket_move,
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
    subject = state.get("task")
    pending = _pending(project_root)
    conflicts = _conflicts(project_root)
    board_text = codec.read_doc(project_root / ".saipen" / "BOARD.md")
    from saipen_engine.router import load_for_action, route_next
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
    load = load_for_action(routed.get("action"))
    _emit({
        "ok": True,
        "action": routed.get("action"),
        "ticket": routed.get("ticket") or subject,
        "reason": routed.get("reason"),
        "load": load,
        "recovery_pending": bool(pending),
        "recovery_conflict": False,
        "pending_ops": pending,
    }, as_json)
    return 0


def _recover(project_root: Path, args: list[str], as_json: bool) -> int:
    # `saipen recover inspect <op_id>` -- read-only conflict inspection.
    if args and args[0] == "inspect":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "recover inspect needs <op_id>"}, as_json)
            return 2
        from saipen_engine.journal import inspect_op
        result = inspect_op(project_root, args[1])
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    # `saipen recover resolve <op_id> [--resolution accept_live|replan]` --
    # the explicit conflict-resolution lifecycle (NITRO dogfood III, T-594).
    if args and args[0] == "resolve":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "recover resolve needs <op_id>"}, as_json)
            return 2
        resolution = "accept_live"
        rest = args[2:]
        if "--resolution" in rest:
            idx = rest.index("--resolution")
            if idx + 1 < len(rest):
                resolution = rest[idx + 1]
        from saipen_engine.journal import resolve_conflict
        result = resolve_conflict(project_root, args[1], resolution,
                                  agent=_agent_for(project_root))
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    conflicts = _conflicts(project_root)
    if conflicts:
        _emit({"ok": False, "code": "CONFLICT",
               "op_ids": conflicts,
               "recovery_required": True,
               "detail": "unresolved conflict(s): " + ", ".join(conflicts)
                         + "; evidence preserved, resolve explicitly (saipen "
                         "recover inspect <op_id> / resolve <op_id> "
                         "--resolution accept_live|replan) before further "
                         "mutation"}, as_json)
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


def _improve(project_root: Path, args: list[str], as_json: bool,
             dry_run: bool) -> int:
    """saipen improve -- the meta-control command family (T-554, T-606,
    DOGFOOD V T-615..T-618).

    Bare `improve` PREPARES the bounded audit assignment (cycle, seat, draft
    report, real source identity, proof levels) and never aliases status.
    `status` derives per-seat visible status read-only and refuses to round
    malformed evidence up to a normal lifecycle state. `submit` appends a RUN
    mechanically, `complete` finishes a report through full validation,
    `sweep-queue` enumerates the exact unswept composite findings, `sweep
    <cycle> <RUN-N/IMP-NNN> <DISPOSITION>` commits a validated Core
    disposition (the finding/run/report/ticket must exist BEFORE write),
    `verify <cycle>` validates the COMPLETE cycle output (delta-only, never a
    new cycle), `cycle-complete <cycle>` runs the full cycle bar and flips
    ACTIVE -> COMPLETE, `clean <cycle>` is archive-with-provenance.
    """
    from improve import (archive_cycle, complete_cycle, cycle_dir,
                         derive_status, resolve_report_path,
                         validate_report, write_sweep_entry)

    from improve import _sweep_records
    import re as _re

    def _state_text(root: Path) -> str:
        st = root / ".saipen" / "STATE.md"
        return st.read_text(encoding="utf-8-sig") if st.is_file() else ""

    def state_phase(root: Path) -> str:
        m = _re.search(r"(?m)^phase:\s*(\S+)", _state_text(root))
        return m.group(1) if m else "?"

    def state_field(root: Path, key: str) -> str:
        m = _re.search(rf"(?m)^{key}:\s*(.*)$", _state_text(root))
        return m.group(1).strip() if m else ""

    def _seat_for_agent(root: Path) -> str:
        m = _re.search(r"(?m)^agent:\s*(\S+)", _state_text(root))
        return (m.group(1) if m else "core").strip() + "-01"

    imp_root = project_root / ".saipen" / "improve"

    def _cycle_statuses() -> list[dict]:
        rows = []
        if not imp_root.is_dir():
            return rows
        from improve import validate_manifest as _vm
        from improve import validate_report as _vr
        from improve import validate_sweep as _vs
        from improve import _report_fresh as _rf
        from improve import _cycle_schema as _cs
        for cycle in sorted(imp_root.iterdir()):
            manifest = cycle / "MANIFEST.md"
            if not manifest.is_file():
                continue
            roster = manifest.read_text(encoding="utf-8-sig")
            sweep = (cycle / "SWEEP.md").read_text(encoding="utf-8-sig") \
                if (cycle / "SWEEP.md").is_file() else ""
            status = "active"
            m = _re.search(r"(?m)^cycle_status:\s*([A-Za-z]+)", roster)
            if m:
                status = m.group(1)
            # DOGFOOD V (T-616): status never rounds corruption up to a
            # normal lifecycle state -- invalid evidence is reported as
            # INVALID_CYCLE / INVALID_REPORT, never as swept.
            manifest_errors = _vm(roster, expected_cycle_id=cycle.name)
            sweep_errors = _vs(sweep) if sweep else []
            invalid = bool(manifest_errors or sweep_errors)
            strict = _cs(manifest) == "strict"
            seats = []
            for block in roster.splitlines():
                if not block.startswith("seat_id:"):
                    continue
                seat = block.split(":", 1)[1].strip()
                report_path = ""
                in_block = False
                for line in roster.splitlines():
                    if line == block:
                        in_block = True
                        continue
                    if line.startswith("seat_id:") and line != block:
                        in_block = False
                    if in_block and line.startswith("report_path:"):
                        report_path = line.split(":", 1)[1].strip()
                if not report_path:
                    seats.append({"seat": seat, "visible": "missing"})
                    continue
                report = cycle / seat / report_path
                report_text = report.read_text(encoding="utf-8-sig") \
                    if report.is_file() else ""
                if not report_text:
                    seats.append({"seat": seat, "visible": "expected"})
                    continue
                # DOGFOOD V (T-620): status applies the SAME report-validation
                # depth the validator applies -- schema AND mechanical source
                # identity (fingerprint format + freshness for strict cycles).
                report_invalid = bool(_vr(report_text)) or bool(
                    _rf(project_root, cycle, report_path, report_text, strict))
                if report_invalid:
                    status_m = _re.search(r"(?m)^report_status:\s*(\S+)",
                                          report_text)
                    seats.append({"seat": seat, "visible": "INVALID_REPORT",
                                  "report_status": status_m.group(1)
                                  if status_m else ""})
                else:
                    derived = derive_status(report_path, roster, report_text,
                                            sweep)
                    seats.append({"seat": seat, **derived})
            rows.append({"cycle": cycle.name, "cycle_status": status,
                         "seats": seats,
                         "invalid": invalid,
                         "manifest_errors": manifest_errors[:3],
                         "sweep_errors": sweep_errors[:3]})
        return rows

    action = args[0] if args else "prepare"
    if action == "prepare":
        # DOGFOOD V (T-617): bare `saipen improve` is the documented
        # meta-control -- it PREPARES the current seat's bounded audit
        # assignment, never an alias for status. It binds the project, finds
        # or mechanically admits the one active cycle, registers this seat,
        # creates the DRAFT report mechanically with the real captured source
        # identity, and returns the exact assignment the current agent must
        # execute. It never changes phase/task/next_action.
        from improve import (allocate_cycle_id, append_run, create_cycle,
                             create_report, register_seat)
        from freshness import compute_source_identity
        try:
            source = compute_source_identity(project_root)
        except Exception as exc:  # noqa: BLE001
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": f"cannot capture mechanical source identity: "
                             f"{exc}"}, as_json)
            return 1
        imp_root = project_root / ".saipen" / "improve"
        active_cycle = None
        if imp_root.is_dir():
            for cycle in sorted(imp_root.iterdir()):
                manifest = cycle / "MANIFEST.md"
                if not manifest.is_file():
                    continue
                roster = manifest.read_text(encoding="utf-8-sig")
                if _re.search(r"(?m)^cycle_status:\s*active\s*$", roster):
                    active_cycle = cycle.name
                    break
        project_key = None
        try:
            from improve import portable_project_key
            project_key = portable_project_key(project_root)
        except Exception:  # noqa: BLE001
            project_key = "project"
        if active_cycle is None:
            new_id = allocate_cycle_id(project_root, project_key)
            try:
                create_cycle(project_root, new_id)
                active_cycle = new_id
            except ValueError as exc:
                _emit({"ok": False, "code": "VALIDATION_FAILED",
                       "detail": f"cannot admit an Improve cycle: {exc}"},
                      as_json)
                return 1
        cycle = cycle_dir(project_root, active_cycle)
        seat_id = _seat_for_agent(project_root)
        project_name = "SAIPEN"
        report_ident = f"saipen_improve_{project_name}.md"
        from improve import _seat_blocks, _field as _imp_field
        roster = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        registered = any(_imp_field(b, "seat_id") == seat_id
                         and _imp_field(b, "report_path") == report_ident
                         for b in _seat_blocks(roster))
        if not registered:
            try:
                register_seat(cycle, seat_id, "core", report_ident)
            except ValueError as exc:
                _emit({"ok": False, "code": "VALIDATION_FAILED",
                       "detail": f"cannot register seat {seat_id}: {exc}"},
                      as_json)
                return 1
        report_path = cycle / seat_id / report_ident
        report_created = False
        if not report_path.is_file():
            try:
                report_path = create_report(
                    project_root, active_cycle, seat_id, project_name,
                    agent=_seat_for_agent(project_root), role="core",
                    model_or_runtime="deepseek-reasoner",
                    protocol_fingerprint="ded-4ae736e4",
                    context_scope=f"SAIPEN audit, phase "
                                  f"{state_phase(project_root)}")
                report_created = True
            except ValueError as exc:
                _emit({"ok": False, "code": "VALIDATION_FAILED",
                       "detail": f"cannot create the seat report: {exc}"},
                      as_json)
                return 1
        _emit({
            "ok": True, "code": "IMPROVE_AUDIT_ASSIGNMENT",
            "cycle_id": active_cycle,
            "seat_id": seat_id,
            "report_path": report_path.relative_to(project_root).as_posix(),
            "report_created": report_created,
            "source": {"source_head": source.source_head,
                       "source_tree_fingerprint": source.source_tree_fingerprint,
                       "discovery_model": source.discovery_model},
            "scope": {"phase": state_phase(project_root),
                      "task": state_field(project_root, "task")},
            "proof_levels": ["UNIT", "COMPOSITION", "CANONICAL", "GATE",
                             "PROVENANCE"],
            "schema": "cycle + seat/report + RUN-N/IMP-NNN composite finding "
                      "ref; dispositions go to SWEEP.md via saipen improve "
                      "sweep; report completion via saipen improve complete",
            "write_boundary": "RUNs append via saipen improve submit; report "
                              "completion via saipen improve complete; no raw "
                              "report/MANIFEST/SWEEP editing",
            "next": f"perform the semantic audit, then: saipen improve submit "
                    f"{active_cycle} {seat_id} {project_name} <findings.json>",
        }, as_json)
        return 0
    if action == "submit":
        # DOGFOOD V (T-617): structured report submission -- the current agent
        # supplies the semantic RUN text in a JSON file, Python appends the
        # RUN mechanically through append_run (validated, journaled).
        if len(args) < 5:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "improve submit needs <cycle> <seat> <project> "
                             "<findings.json>"}, as_json)
            return 2
        from improve import append_run as _append_run
        from improve import resolve_report_path as _resolve_report_path
        cycle = cycle_dir(project_root, args[1])
        payload = Path(args[4])
        if not payload.is_file():
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": f"findings file not found: {args[4]}"}, as_json)
            return 2
        import json as _json
        try:
            data = _json.loads(payload.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": f"findings file is not valid JSON: {exc}"},
                  as_json)
            return 2
        run_text = data.get("run_text", "")
        if not run_text.strip():
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "findings payload needs a non-empty run_text "
                             "field"}, as_json)
            return 2
        report = _resolve_report_path(project_root, args[1], args[2],
                                      args[3])
        try:
            result = _append_run(report, run_text)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": str(exc)}, as_json)
            return 1
    if action == "complete":
        # DOGFOOD V (T-616): mechanical report completion -- full validation,
        # then draft -> complete, journaled and immutable.
        if len(args) < 4:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "improve complete needs <cycle> <seat> <project>"},
                  as_json)
            return 2
        from improve import complete_report as _complete_report
        from improve import resolve_report_path as _resolve_report_path
        report = _resolve_report_path(project_root, args[1], args[2], args[3])
        try:
            result = _complete_report(report)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": str(exc)}, as_json)
            return 1
    if action == "sweep-queue":
        # DOGFOOD V (T-617): deterministic enumeration of the unswept finding
        # queue -- read-only; the semantic adjudication stays Core-owned.
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "improve sweep-queue needs <cycle_id>"}, as_json)
            return 2
        from improve import (composite_finding_ref, parse_report, verify_cycle,
                             _seat_blocks, _field as _imp_field)
        cycle = cycle_dir(project_root, args[1])
        precheck = verify_cycle(cycle)
        roster = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        sweep = (cycle / "SWEEP.md").read_text(encoding="utf-8-sig") \
            if (cycle / "SWEEP.md").is_file() else ""
        disposed = {(r.run(), r.imp()) for r in _sweep_records(sweep)}
        queue = []
        for block in _seat_blocks(roster):
            if _imp_field(block, "availability") == "unavailable":
                continue
            seat_id = _imp_field(block, "seat_id")
            report_ident = _imp_field(block, "report_path")
            report = cycle / seat_id / report_ident
            if not report.is_file():
                continue
            for finding in parse_report(
                    report.read_text(encoding="utf-8-sig")).findings:
                if (finding.run, finding.imp) in disposed:
                    continue
                queue.append({
                    "finding_ref": composite_finding_ref(
                        cycle.name, seat_id, report_ident, finding.run,
                        finding.imp),
                    "run": finding.run, "imp": finding.imp,
                    "report": report_ident,
                    "severity": finding.severity, "class": finding.cls,
                    "expected": finding.expected, "actual": finding.actual,
                    "evidence": finding.evidence,
                })
        _emit({"ok": True, "code": "IMPROVE_SWEEP_QUEUE",
               "cycle": args[1], "queue": queue,
               "precheck_errors": precheck[:5],
               "note": "semantic adjudication (reproduce/classify/dedupe/"
                       "decide) is Core-owned; commit each decision via "
                       "saipen improve sweep"}, as_json)
        return 0
    if action == "status":
        rows = _cycle_statuses()
        if as_json:
            _emit({"ok": True, "code": "IMPROVE_STATUS",
                   "cycles": rows}, as_json)
        else:
            for row in rows:
                print(f"{row['cycle']} ({row['cycle_status']})")
                for seat in row["seats"]:
                    print(f"  {seat['seat']}: {seat.get('visible', '?')}"
                          + (f" (report_status "
                             f"{seat.get('report_status')})"
                             if seat.get("report_status") else "")
                          + (f" missing={seat.get('missing')}"
                             if seat.get("missing") else ""))
        return 0
    if action == "verify":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "improve verify needs <cycle_id>"}, as_json)
            return 2
        cycle = cycle_dir(project_root, args[1])
        # DOGFOOD V (T-616): verify validates the COMPLETE cycle output --
        # strict manifest, every expected report full-valid, exact composite
        # sweep coverage -- never whether individual files merely resemble
        # writable intermediate targets. A report that only says
        # `report_status: complete` can never PASS this.
        from improve import verify_cycle
        errors = verify_cycle(cycle)
        if errors:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "; ".join(errors[:5]),
                   "delta_only": True}, as_json)
            return 1
        _emit({"ok": True, "code": "IMPROVE_VERIFY_PASS",
               "delta_only": True, "cycle": args[1]}, as_json)
        return 0
    if action == "sweep":
        if len(args) < 4:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "improve sweep needs <cycle> <finding_ref> "
                             "<disposition> [--ticket T-###] [--report "
                             "<ident>] [--reproduced y|n] where finding_ref "
                             "is RUN-N/IMP-NNN (strict) or IMP-NNN (legacy)"},
                  as_json)
            return 2
        cycle = cycle_dir(project_root, args[1])
        finding_ref, disposition = args[2], args[3]
        run = None
        import re as _re
        _fm = _re.fullmatch(r"(?:RUN-(\d+)/)?IMP-(\d+)", finding_ref)
        if not _fm:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": f"finding_ref {finding_ref!r} is not "
                             "RUN-N/IMP-NNN or IMP-NNN"}, as_json)
            return 2
        run_raw, imp_id = _fm.group(1), _fm.group(2)
        ticket = "-"
        report = "-"
        reproduced = "-"
        rest = args[4:]
        while rest:
            if rest[0] == "--ticket" and len(rest) > 1:
                ticket, rest = rest[1], rest[2:]
            elif rest[0] == "--report" and len(rest) > 1:
                report, rest = rest[1], rest[2:]
            elif rest[0] == "--reproduced" and len(rest) > 1:
                reproduced, rest = rest[1], rest[2:]
            else:
                rest = rest[1:]
        if dry_run:
            _emit({"ok": True, "code": "IMPROVE_SWEEP_PLAN",
                   "cycle": args[1], "finding_ref": finding_ref,
                   "disposition": disposition}, as_json)
            return 0
        try:
            entry = {"imp_id": imp_id, "disposition": disposition,
                     "ticket": ticket, "report": report,
                     "reproduced": reproduced}
            if run_raw is not None:
                entry["run"] = f"RUN-{run_raw}"
            result = write_sweep_entry(cycle, entry)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": str(exc)}, as_json)
            return 1
    if action == "cycle-complete":
        # DOGFOOD V (T-616): mechanical cycle completion through the public
        # path -- full cycle bar (strict manifest, every report full-valid,
        # exact composite sweep coverage), then ACTIVE -> COMPLETE.
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "improve cycle-complete needs <cycle_id>"},
                  as_json)
            return 2
        cycle = cycle_dir(project_root, args[1])
        try:
            result = complete_cycle(cycle)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": str(exc)}, as_json)
            return 1
    if action == "abort":
        # DOGFOOD V (T-621): mechanical abort for a stuck draft cycle -- the
        # journaled exit for an active cycle whose report cannot complete.
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "improve abort needs <cycle_id>"}, as_json)
            return 2
        from improve import abort_cycle as _abort_cycle
        cycle = cycle_dir(project_root, args[1])
        try:
            result = _abort_cycle(cycle)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": str(exc)}, as_json)
            return 1
    if action == "clean":
        if len(args) < 2:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": "improve clean needs <cycle_id>"}, as_json)
            return 2
        cycle = cycle_dir(project_root, args[1])
        # archive-with-provenance: only a COMPLETE (fully swept) cycle may be
        # archived; the sweep ledger + reports are preserved verbatim.
        if dry_run:
            _emit({"ok": True, "code": "IMPROVE_CLEAN_PLAN",
                   "cycle": args[1], "archive_only": True}, as_json)
            return 0
        try:
            result = archive_cycle(cycle)
            _emit({"ok": result.get("ok", False),
                   "code": "IMPROVE_CLEAN" if result.get("ok")
                   else "VALIDATION_FAILED",
                   "cycle": args[1],
                   "archive_only": True,
                   "detail": result.get("message", "")}, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED",
                   "detail": str(exc), "archive_only": True}, as_json)
            return 1
    _emit({"ok": False, "code": "VALIDATION_FAILED",
           "detail": f"unknown saipen improve action {action!r}; use "
                     "prepare|status|submit|complete|sweep|sweep-queue|"
                     "verify|cycle-complete|abort|clean"}, as_json)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    as_json = "--json" in args
    dry_run = "--dry-run" in args
    args = [a for a in args if a not in ("--json", "--dry-run")]
    if not args or args[0] in ("-h", "--help"):
        print("usage: saipen (status|next|recover|claim <T-###>|"
              "transition <PHASE> [T-###] [text]|checkpoint <TAXONOMY> "
              "[T-###] [text]|ticket add <PRIORITY> <text>|ticket "
              "done|block|unblock <T-###> [text]|improve|improve "
              "status|improve sweep <cycle> <RUN-N/IMP-NNN> <DISPOSITION> "
               "|improve sweep-queue <cycle>|improve submit <cycle> <seat> "
               "<project> <findings.json>|improve complete <cycle> <seat> "
               "<project>|improve verify <cycle>|improve cycle-complete "
               "<cycle>|improve abort <cycle>|improve clean <cycle>|"
               "userperson|sub|context) [--dry-run] [--json]")
        return 2
    command = args[0]
    project_root = Path.cwd()
    if command == "status":
        return _status(project_root, as_json)
    if command == "next":
        return _next_action(project_root, as_json)
    if command == "recover":
        return _recover(project_root, args[1:], as_json)
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
        if action == "done" and rest:
            # `ticket done` IS the canonical atomic finish operation (NITRO
            # dogfood III, T-591): LOG + BOARD + STATE close in ONE plan, so a
            # successful completion can never leave the old split
            # (BOARD DONE[x] while STATE names the ticket in a ticket-bearing
            # phase). block/unblock stay surgical moves.
            result = finish_ticket(project_root, rest[0],
                                   _agent_for(project_root),
                                   dry_run=dry_run)
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
        if action in ("block", "unblock") and rest:
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
    if command == "improve":
        return _improve(project_root, args[1:], as_json, dry_run)
    print(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

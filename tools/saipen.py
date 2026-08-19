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
import os
import re
import sys
from pathlib import Path

from saipen_engine import codec, snapshot
from saipen_engine.board import parse_board, ticket_is_workable
from saipen_engine.journal import auto_recover_pending, pending_conflicts, pending_ops
from saipen_engine.operations import (
    apply_claim,
    checkpoint,
    finish_ticket,
    plan_claim,
    ticket_add,
    ticket_move,
    transition_phase,
)
from saipen_engine.paths import resolve_project_root
from saipen_engine.state import parse_state, parse_state_or_error

AGENT = "saipen-cli"

HOME = Path(__file__).resolve().parent.parent
VERSION_FILE = HOME / "VERSION"

# The ONE canonical actor resolver (T-1006): bare CLI INHERITS STATE.agent
# -- the seat CORE.md section 1.4 defines -- and an explicit `--agent <id>`
# is a genuine-handover request that MUST log a DEC naming old -> new before
# any mutation. STATE.agent is never invented by the CLI; only an explicit
# override replaces the inherited seat.
_AGENT_OVERRIDE: str | None = None


def _agent_for(project_root: Path) -> str:
    """The canonical acting seat (T-1006).

    An explicit `--agent <id>` override wins (the handover is logged by
    `handover_agent` before any mutation); otherwise the seat is INHERITED
    from persisted STATE.agent -- a returning agent keeps the seat, and only a
    genuinely different actor changes it (CORE.md section 1.4, BOOT.md).
    `AGENT` is the fallback only for a project with no persisted agent."""
    if _AGENT_OVERRIDE is not None:
        return _AGENT_OVERRIDE
    state_path = _state_path(project_root)
    if state_path.is_file():
        state, _ = parse_state_or_error(codec.read_doc(state_path))
        if state and state.get("agent"):
            return state["agent"]
    return AGENT


# T-1006: ONE canonical, subcommand-aware mutation classifier. This table is
# the SINGLE authority the handover gate consults to decide whether a command
# may write canonical state (and therefore must perform the A -> B handover
# before its dependent writes). The dispatcher below still routes each command
# through its own branch -- the classifier is NOT a second dispatcher, it is
# the gate the dispatcher defers to for the handover decision. Keep the two in
# agreement: the table-driven regression in run_scenarios.py proves every
# public command's classification matches the dispatcher's read-only vs
# mutating behavior, so a drift between them fails loudly.
#
# Authoritative public-surface semantics (verified against the dispatcher):
#   status / next / context / recover inspect ......... READ_ONLY
#   claim / transition / checkpoint / ticket * ........ MUTATING
#   userperson show ................................... READ_ONLY
#   userperson add|remove|reset ....................... MUTATING
#   sub list|status .................................. READ_ONLY
#   sub sync|spawn|adopt|pause|resume|clean|
#      collect|dispose ............................... MUTATING
#   recover resolve / bare recover (replay) .......... MUTATING
#   rebind-home / crew / scope / fpc / ship / push ... MUTATING
#   improve (bare prepare) / submit / complete / sweep /
#      cycle-complete / abort / clean ................ MUTATING
#   improve status / sweep-queue / verify ............ READ_ONLY
_MUTATING_TOPLEVEL = frozenset(
    {
        "claim",
        "transition",
        "checkpoint",
        "ticket",
        "rebind-home",
        "crew",
        "scope",
        "first-publish-confirm",
        "fpc",
        "ship",
        "push",
    }
)
_MUTATING_USERPERSON = frozenset({"add", "remove", "reset"})
_MUTATING_SUB = frozenset(
    {"sync", "spawn", "adopt", "pause", "resume", "clean", "collect", "dispose"}
)
_MUTATING_IMPROVE = frozenset({"submit", "complete", "sweep", "cycle-complete", "abort", "clean"})
_READ_ONLY_RECOVER = frozenset({"inspect"})


def _command_mutates(command: str, rest: list[str]) -> bool:
    """Does this invocation write canonical state? (T-1006 handover gate.)

    Subcommand-aware and authoritative: the dispatcher routes AFTER this
    verdict, so a read-only projection under `--agent B` never hands over
    persistent ownership, never appends LOG, never updates STATE, and never
    creates recovery operations. Mutating invocations perform the canonical
    A -> B handover immediately before their dependent writes (T-1014: only
    after the concrete action's syntax/arity validation has passed, so a
    malformed invocation stays zero-write).
    """
    sub = rest[0] if rest and not rest[0].startswith("-") else None
    if command in _MUTATING_TOPLEVEL:
        return True
    if command == "userperson":
        # `show` is a read-only projection; add/remove/reset mutate.
        return sub in _MUTATING_USERPERSON
    if command == "sub":
        # list/status are read-only; the rest mutate the sub roster.
        return sub in _MUTATING_SUB
    if command == "recover":
        # inspect is read-only; `resolve` mutates recovery state, and a bare
        # `recover` may replay pending operations and therefore mutate.
        return sub not in _READ_ONLY_RECOVER
    if command == "improve":
        if sub is None:
            # Bare `improve` PREPARES the audit seat/cycle/report -- mutating.
            return True
        # verify/status/sweep-queue are read-only; the rest mutate.
        return sub in _MUTATING_IMPROVE
    return False


def _ensure_handover(project_root: Path, as_json: bool, dry_run: bool) -> int | None:
    """T-1014: perform the A -> B seat handover ONLY immediately before an
    admissible mutation executes -- never before the concrete action's
    syntax/arity validation has passed.

    Returns None when the seat is settled (no override, override equals the
    persisted seat, or the handover itself succeeded); returns an exit code
    after emitting a structured refusal when the handover fails. Callers
    short-circuit with that code. A malformed/unknown invocation never
    reaches this helper, so it stays ownership-zero-write.
    """
    if _AGENT_OVERRIDE is None:
        return None
    state_path = _state_path(project_root)
    if not state_path.is_file():
        return None
    state, _state_err = parse_state_or_error(codec.read_doc(state_path))
    if state and state.get("agent") == _AGENT_OVERRIDE:
        return None
    from saipen_engine.operations import handover_agent

    ho = handover_agent(project_root, _AGENT_OVERRIDE, dry_run=dry_run)
    if not ho.ok:
        _emit(ho.to_dict(), as_json)
        return 1
    return None


_TERMINAL_RESULT_RE = re.compile(r"->\s*(PASS|FAIL)\s*$")


def _validator_terminal_result(txt: str) -> str:
    """The canonical terminal result of a validator RUN event, or UNKNOWN
    (second-wave P2).

    Only an EXACT `-> PASS` / `-> FAIL` terminal token counts as a result.
    Anything else -- `NOT PASS`, `BYPASS`, `PASSING`, mixed failure prose, or a
    missing terminal token -- is UNKNOWN and is never promoted to a conformance
    PASS."""
    m = _TERMINAL_RESULT_RE.search(txt)
    if not m:
        return "UNKNOWN"
    return "PASS" if m.group(1) == "PASS" else "FAIL"


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


def _pending_state(project_root: Path) -> tuple[list[str], list[str]]:
    """ONE recovery-manifest traversal for both subsets (T-1004 pending):
    every public command obtains a single scan and passes both lists
    downstream instead of rescanning per projection."""
    from saipen_engine.journal import scan_pending

    pending, conflicts = scan_pending(project_root)
    return ([op["op_id"] for op in pending], [op["op_id"] for op in conflicts])


def _scan_full(project_root: Path) -> tuple[list[str], list[str], list[dict]]:
    """ONE recovery-manifest traversal for pending ids, conflicts AND the
    structured corrupt records (T-1014). status/next/recover previously ran
    `_pending_state` followed by `_corrupt_evidence`, traversing the
    recovery tree twice per command; one scan serves all three projections,
    so every command sees exactly one manifest snapshot."""
    from saipen_engine.journal import scan_pending

    pending, conflicts = scan_pending(project_root)
    return (
        [op["op_id"] for op in pending],
        [op["op_id"] for op in conflicts],
        [op for op in pending if op.get("corrupt")],
    )


def _corrupt_evidence(project_root: Path) -> list[dict]:
    """The STRUCTURED corrupt recovery records, record shape preserved.

    `_pending_state` flattens the scan into bare op_ids for routing, which
    silently drops `corrupt`/`detail` -- the only evidence that distinguishes a
    malformed journal from an ordinary pending op (hostile-regression, P1#6).
    Every public projection (status / next / recover / preflight) reads THIS so
    they all agree on CORRUPT_JOURNAL instead of one reporting a healthy
    surface."""
    return _scan_full(project_root)[2]


def _corrupt_refusal(corrupt: list[dict]) -> dict:
    """The ONE shared CORRUPT_JOURNAL refusal payload (P1#6)."""
    return {
        "ok": False,
        "code": "CORRUPT_JOURNAL",
        "op_ids": [op["op_id"] for op in corrupt],
        "recovery_required": True,
        "corrupt": [
            {"op_id": op["op_id"], "status": op.get("status"), "detail": op.get("detail", "")}
            for op in corrupt
        ],
        "detail": f"corrupt recovery evidence {corrupt[0]['op_id']} "
        f"({corrupt[0].get('detail', '')}) -- resolve it "
        f"explicitly before any further canonical write",
    }


def _negotiate_capability(project_root: Path) -> str:
    """Negotiate the CURRENT-SESSION capability at the public command boundary
    (hostile-regression, P0#4).

    The persisted STATE.mode is ONLY the LAST handshake outcome and MUST NOT
    prove current write authority -- a stale read-only must not suppress a
    newly writable session, nor a stale full publish into a newly read-only
    one. The live session negotiates a fresh capability through the ONE shared
    negotiator and injects it into routing/release/crew; the persisted mode
    stays historical. `project_root` is accepted so the signature stays stable
    for callers, and deliberately UNUSED: reading the project's own STATE here
    is exactly the fail-open this closes."""
    from saipen_engine.capability import negotiate_capability

    return negotiate_capability()


def _status(project_root: Path, as_json: bool) -> int:
    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    state_text = codec.read_doc(state_path)
    state, state_error = parse_state_or_error(state_text)
    if state_error:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"state-malformed: {state_error}"},
            as_json,
        )
        return 1
    try:
        snap = snapshot.ProjectSnapshot.capture(project_root)
    except (OSError, ValueError) as exc:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"history-ownership: {exc}"},
            as_json,
        )
        return 1
    board_path = project_root / ".saipen" / "BOARD.md"
    board_text = codec.read_doc(board_path) if board_path.is_file() else ""
    board = parse_board(board_text) if board_path.is_file() else {"tickets": {}, "errors": []}
    doing = [t for t in board["tickets"].values() if t["section"] == "## DOING"]
    todo = [t for t in board["tickets"].values() if t["section"] == "## TODO"]
    done_tickets = [t for t in board["tickets"].values() if t["section"] == "## DONE"]
    blocked_tickets = [t for t in board["tickets"].values() if t["section"] == "## BLOCKED"]

    top_workable = None
    if not board["errors"]:
        for ticket in todo:
            if ticket_is_workable(ticket, board["tickets"], agent=_agent_for(project_root)):
                top_workable = ticket["id"]
                break
    # T-1014: ONE recovery-manifest traversal serves pending/conflicts and
    # the structured corrupt records; P1#6 still refuses CORRUPT_JOURNAL with
    # the STRUCTURED record (op_id + detail) before any projection.
    pending, conflicts, _corrupt = _scan_full(project_root)
    if _corrupt:
        _emit(_corrupt_refusal(_corrupt), as_json)
        return 1
    from saipen_engine.router import route_next, routing_failure_code

    # P0#4: the freshly negotiated current-session capability gates routing --
    # a read-only session routes RESTATE_AND_STOP, never a mutating action.
    # T-1006: routing judges claim truth against the canonical acting seat.
    routed = route_next(
        state_text,
        board_text,
        pending,
        conflicts,
        current_capability=_negotiate_capability(project_root),
        current_agent=_agent_for(project_root),
    )
    if not routed.get("ok") and routing_failure_code(routed) == "VALIDATION_FAILED":
        # A malformed/binding failure must NOT project a healthy surface from
        # corrupt input (T-1003): status fails closed with the router's
        # diagnostics while the recovery flags stay truthful.
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "action": routed.get("action"),
                "reason": routed.get("reason"),
                "detail": routed.get("detail", ""),
                "board_errors": board["errors"],
                "recovery_pending": bool(pending),
                "recovery_conflict": bool(conflicts),
                "conflict_ops": conflicts,
                "pending_ops": pending,
            },
            as_json,
        )
        return 1

    from saipen_engine.board import blocker_class

    waiting_on_you: list[str] = []
    next_act = state.get("next_action") or ""
    if next_act.startswith("WAIT:"):
        waiting_on_you.append(next_act)
    for bt in blocked_tickets:
        # Human waits live in the parsed BOARD field map (`fields`), never at
        # the ticket-record level -- `ticket["fields"]["blocker"]` is the
        # canonical home of `| blocker:` (T-1003 hostile findings).
        b_text = bt.get("fields", {}).get("blocker") or ""
        b_cls = blocker_class(b_text)
        if b_cls in ("WAIT_USER_CONFIRMATION", "WAIT_USER_DECISION") or b_text.startswith(
            "WAIT_USER"
        ):
            waiting_on_you.append(f"{bt['id']}: {b_text}")

    # T-1014: the parsed events come from the SAME one-pass ProjectSnapshot
    # that supplied log_hash/log_tail/head -- status never reopens the complete
    # LOG history for evidence after capturing the snapshot once.
    # T-1021: ONE backward pass over the shared history computes the verdict
    # for every DONE ticket (was one independent reverse scan per ticket).
    from saipen_engine.log import bulk_verification_evidence

    history_events = snap.history_events
    # DONE proof: a successful RUN event ASSOCIATED WITH THE TICKET.
    claimed_but_unproven: list[str] = []
    verdicts = bulk_verification_evidence(history_events, [dt["id"] for dt in done_tickets])
    for dt in done_tickets:
        if not verdicts[dt["id"]][0]:
            claimed_but_unproven.append(dt["id"])

    conformance: str | None = None
    for ev in reversed(history_events):
        txt = ev.get("text", "")
        tax = ev.get("taxonomy", "")
        if tax == "RUN" and ("validate.py" in txt or "validate.sh" in txt or "validate.ps1" in txt):
            m_date = ev.get("date") or ""
            # Second-wave P2: parse ONLY the canonical terminal result of the
            # validator RUN (`-> PASS` / `-> FAIL` as an exact result token).
            # A substring test would promote free event text like `NOT PASS`,
            # `BYPASS`, `PASSING` or mixed failure prose to a conformance PASS
            # although no exact successful result was recorded. Noncanonical
            # text stays UNKNOWN/raw and is never promoted to PASS.
            res = _validator_terminal_result(txt)
            conformance = f"{res} ({m_date})" if m_date else res
            break

    staleness: str | None = None
    updated_str = state.get("updated")
    if updated_str:
        import datetime

        try:
            clean_ts = updated_str.replace("Z", "+00:00")
            dt_updated = datetime.datetime.fromisoformat(clean_ts)
            dt_now = datetime.datetime.now(datetime.timezone.utc)
            delta = dt_now - dt_updated
            total_seconds = int(delta.total_seconds())
            if total_seconds >= 3600:
                hours = total_seconds // 3600
                days = hours // 24
                staleness = f"{days}d ago" if days > 0 else f"{hours}h ago"
        except (ValueError, TypeError):
            pass

    payload = {
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
    }
    if waiting_on_you:
        payload["waiting_on_you"] = waiting_on_you
    if claimed_but_unproven:
        payload["claimed_but_unproven"] = claimed_but_unproven
    if conformance is not None:
        payload["conformance"] = conformance
    if staleness is not None:
        payload["staleness"] = staleness

    _emit(payload, as_json)
    return 0


def _next_action(project_root: Path, as_json: bool) -> int:
    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    state_text = codec.read_doc(state_path)
    from saipen_engine.state import parse_state_or_error

    state, state_error = parse_state_or_error(state_text)
    if state_error:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"state-malformed: {state_error}"},
            as_json,
        )
        return 1
    subject = state.get("task")
    # T-1014: ONE recovery-manifest traversal (pending + conflicts + corrupt).
    pending, conflicts, _corrupt = _scan_full(project_root)
    if _corrupt:
        _emit(_corrupt_refusal(_corrupt), as_json)
        return 1
    board_text = codec.read_doc(project_root / ".saipen" / "BOARD.md")
    from saipen_engine.router import load_for_action, route_next, routing_failure_code

    # P0#4: the freshly negotiated current-session capability gates routing.
    # T-1006: routing judges claim truth against the canonical acting seat.
    routed = route_next(
        state_text,
        board_text,
        pending,
        conflicts,
        current_capability=_negotiate_capability(project_root),
        current_agent=_agent_for(project_root),
    )
    if not routed.get("ok"):
        # The router owns the stable failure code: recovery conflicts/pending
        # are RECOVERY_*; malformed/binding failures are VALIDATION_FAILED
        # with recovery_pending strictly false (there is no journal to
        # recover -- T-1003 hostile findings).
        _emit(
            {
                "ok": False,
                "code": routing_failure_code(routed),
                "action": routed.get("action"),
                "reason": routed.get("reason"),
                "detail": routed.get("detail", ""),
                "recovery_pending": bool(pending),
                "recovery_conflict": bool(conflicts),
                "conflict_ops": conflicts,
                "pending_ops": pending,
            },
            as_json,
        )
        return 1
    load = load_for_action(routed.get("action"))
    _emit(
        {
            "ok": True,
            "action": routed.get("action"),
            "ticket": routed.get("ticket") or subject,
            "reason": routed.get("reason"),
            "load": load,
            "recovery_pending": bool(pending),
            "recovery_conflict": False,
            "pending_ops": pending,
        },
        as_json,
    )
    return 0


def _recover(project_root: Path, args: list[str], as_json: bool, dry_run: bool = False) -> int:
    # `saipen recover inspect <op_id>` -- read-only conflict inspection.
    # Closed grammar: exactly one positional <op_id> (hostile-regression, P0#1).
    if args and args[0] == "inspect":
        if len(args) != 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "recover inspect requires exactly <op_id>",
                },
                as_json,
            )
            return 2
        from saipen_engine.journal import inspect_op

        result = inspect_op(project_root, args[1])
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    # `saipen recover resolve <op_id> [--resolution accept_live|replan]` --
    # the explicit conflict-resolution lifecycle (NITRO dogfood III, T-594).
    # Closed grammar (hostile-regression, P0#1): exactly `<op_id>` OR
    # `<op_id> --resolution <accept_live|replan>`. Unknown/surplus tokens and a
    # missing/unknown --resolution value are refused here; resolve_conflict is
    # NEVER called with a defaulted accept_live from malformed input.
    if args and args[0] == "resolve":
        rest = args[1:]
        if len(rest) == 0:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "recover resolve needs <op_id>",
                },
                as_json,
            )
            return 2
        op_id = rest[0]
        extra = rest[1:]
        resolution = "accept_live"
        if extra:
            if extra[0] == "--resolution":
                if len(extra) != 2:
                    _emit(
                        {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": "usage: recover resolve <op_id> "
                            "--resolution <accept_live|replan>",
                        },
                        as_json,
                    )
                    return 2
                if extra[1] not in ("accept_live", "replan"):
                    _emit(
                        {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": f"unknown resolution {extra[1]!r}; use accept_live|replan",
                        },
                        as_json,
                    )
                    return 2
                resolution = extra[1]
            else:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"unexpected token {extra[0]!r}; usage: "
                        "recover resolve <op_id> "
                        "[--resolution <accept_live|replan>]",
                    },
                    as_json,
                )
                return 2
        from saipen_engine.journal import resolve_conflict

        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = resolve_conflict(project_root, op_id, resolution, agent=_agent_for(project_root))
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    pending, conflicts, _corrupt = _scan_full(project_root)
    if conflicts:
        _emit(
            {
                "ok": False,
                "code": "CONFLICT",
                "op_ids": conflicts,
                "recovery_required": True,
                "detail": "unresolved conflict(s): "
                + ", ".join(conflicts)
                + "; evidence preserved, resolve explicitly (saipen "
                "recover inspect <op_id> / resolve <op_id> "
                "--resolution accept_live|replan) before further "
                "mutation",
            },
            as_json,
        )
        return 1
    if not pending:
        _emit({"ok": True, "code": "CLEAN", "pending_ops": []}, as_json)
        return 0
    # Refuse corrupt recovery evidence as CORRUPT_JOURNAL BEFORE any replay
    # (hostile-regression, P1#6): a scan_pending record marked corrupt:true --
    # e.g. a symlinked OPS_DIR or an unreadable entry -- must never be replayed
    # as a normal op_id (which surfaced a generic VALIDATION_FAILED). The
    # STRUCTURED record survives to the refusal via the ONE shared payload every
    # projection uses (already scanned above by `_scan_full`, T-1014).
    if _corrupt:
        _emit(_corrupt_refusal(_corrupt), as_json)
        return 1
    result = auto_recover_pending(project_root)
    _emit(result, as_json)
    return 0 if result.get("ok") else 1


def _sub(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:
    """saipen sub list|status|spawn|adopt|pause|resume|sync|clean|collect|
    dispose.

    Strict grammar (SAICREW G): `list`/`sync` take zero positional args;
    `status`/`spawn`/`adopt`/`pause`/`resume`/`clean` take exactly one;
    `collect` takes zero or one; `dispose` takes one name plus an optional
    package id. Unknown or surplus tokens are a structured
    VALIDATION_FAILED with ZERO writes -- ignored garbage is never accepted
    as implied semantics. Every mutator honors --dry-run (same validation,
    same proposed outcome, ZERO writes/LOG/STATE/MANIFEST/journal).
    """
    from saipen_engine.subs import (
        sub_adopt,
        sub_clean,
        sub_collect,
        sub_disposition,
        sub_list,
        sub_pause,
        sub_resume,
        sub_spawn,
        sub_status,
        sub_sync,
    )

    if not args:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "sub needs an action: list|sync|status|spawn|adopt|"
                "pause|resume|clean|collect|dispose",
            },
            as_json,
        )
        return 2
    action = args[0]
    rest = args[1:]
    grammar = {
        "list": (0, 0),
        "sync": (0, 0),
        "status": (1, 1),
        "spawn": (1, 1),
        "adopt": (1, 1),
        "pause": (1, 1),
        "resume": (1, 1),
        "clean": (1, 1),
        "collect": (0, 1),
        "dispose": (1, 2),
    }
    if action not in grammar:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"unknown sub action {action!r}; use "
                "list|sync|status|spawn|adopt|pause|resume|clean|"
                "collect|dispose",
            },
            as_json,
        )
        return 2
    minimum, maximum = grammar[action]
    if len(rest) < minimum or len(rest) > maximum:
        wanted = f"exactly {minimum}" if minimum == maximum else f"at most {maximum}"
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"sub {action} takes {wanted} positional "
                f"argument(s); surplus: {' '.join(rest[maximum:])}",
            },
            as_json,
        )
        return 2
    state = parse_state(codec.read_doc(_state_path(project_root)))
    saipen_home = state.get("saipen_home") or ""
    if action in ("sync", "spawn", "adopt") and not saipen_home:
        _emit(
            {
                "ok": False,
                "code": "HOME_REQUIRED",
                "detail": "STATE.saipen_home is required; project root is "
                "not installation provenance",
            },
            as_json,
        )
        return 1
    # T-1006: sub mutators persist the CANONICAL acting seat (inherited
    # STATE.agent or explicit --agent), never a hardcoded CLI identity.
    actor = _agent_for(project_root)

    def _run(thunk):
        """One sub-action execution with the structured CLI boundary
        (T-1013): a residual path-length/host filesystem failure (an ID that
        passes every safe-ID check yet still breaks the host path budget) is
        a zero-write VALIDATION_FAILED refusal, never a traceback.

        T-1014: mutating sub actions perform the seat handover ONLY here --
        after grammar validation has passed, immediately before the mutation.
        list/status are read-only and never hand over."""
        if action not in ("list", "status"):
            _rc = _ensure_handover(project_root, as_json, dry_run)
            if _rc is not None:
                return _rc
        try:
            result = thunk()
        except OSError as exc:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"sub {action} failed on the filesystem: {type(exc).__name__}: {exc}",
                },
                as_json,
            )
            return 1
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1

    if action == "list":
        return _run(lambda: sub_list(project_root))
    if action == "sync":
        return _run(lambda: sub_sync(project_root, saipen_home, agent=actor, dry_run=dry_run))
    if action == "status":
        return _run(lambda: sub_status(project_root, rest[0]))
    if action == "spawn":
        return _run(
            lambda: sub_spawn(project_root, rest[0], saipen_home, agent=actor, dry_run=dry_run)
        )
    if action == "adopt":
        return _run(
            lambda: sub_adopt(project_root, rest[0], saipen_home, agent=actor, dry_run=dry_run)
        )
    if action in ("pause", "resume"):
        fn = sub_pause if action == "pause" else sub_resume
        return _run(lambda: fn(project_root, rest[0], agent=actor, dry_run=dry_run))
    if action == "clean":
        return _run(lambda: sub_clean(project_root, rest[0], agent=actor, dry_run=dry_run))
    if action == "collect":
        name = rest[0] if rest else None
        return _run(lambda: sub_collect(project_root, name, agent=actor, dry_run=dry_run))
    if action == "dispose":
        package_id = rest[1] if len(rest) > 1 else None
        return _run(
            lambda: sub_disposition(project_root, rest[0], package_id, agent=actor, dry_run=dry_run)
        )
    return 2


def _crew(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:
    """saipen crew -- the serial full-platoon convergence circuit (SAICREW).

    `--dry-run` derives the full circuit, shows per-role health and the first
    unsatisfied stage, and writes NOTHING. Apply persists
    `execution_intent: converge` + `converge_target: crew`, runs the
    mechanical transitions (sub sync + required instances), and hands the
    semantic stage work back to the agent; `saipen crew`/`cc` then resumes
    the same target. The launcher scripts stay an OPTIONAL manual multi-window
    helper -- never `saipen crew` semantics.
    """
    if args:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "crew accepts no positional arguments; surplus: " + " ".join(args),
            },
            as_json,
        )
        return 2
    from saipen_engine.crew import crew_apply, crew_plan

    # P0#4: inject the freshly negotiated current-session capability so a
    # read-only session cannot close a crew release. Second-wave P0: the
    # acting identity is the SESSION agent, never persisted STATE.agent.
    capability = _negotiate_capability(project_root)
    if dry_run:
        plan = crew_plan(
            project_root, current_capability=capability, current_agent=_agent_for(project_root)
        )
        _emit(
            {
                "ok": plan.get("ok"),
                "code": "CREW_PLAN",
                "crew_complete": plan.get("crew_complete"),
                "action_required": plan.get("action_required"),
                "dry_run": True,
                **plan,
            },
            as_json,
        )
        # Item 21: a valid nonterminal plan (work remains) is NOT a command
        # failure -- ok:true / exit 0. Nonzero exit is reserved for a
        # structurally invalid or refused derivation.
        return 0 if plan.get("ok") else 1
    _rc = _ensure_handover(project_root, as_json, dry_run)
    if _rc is not None:
        return _rc
    result = crew_apply(
        project_root, current_capability=capability, current_agent=_agent_for(project_root)
    )
    _emit(result.to_dict(), as_json)
    return 0 if result.ok else 1


def _context(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:
    """saipen context cold|hot|audit (NITRO M9, read-only)."""
    if not args:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "context needs a mode: cold|hot|audit",
            },
            as_json,
        )
        return 2
    if len(args) > 1:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"context accepts exactly one mode; surplus: {' '.join(args[1:])}",
            },
            as_json,
        )
        return 2
    from saipen_engine.context import context_audit, context_cold, context_hot
    from saipen_engine.log import HistoryOwnershipError

    mode = args[0]
    fn = {"cold": context_cold, "hot": context_hot, "audit": context_audit}.get(mode)
    if fn is None:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"unknown context mode {mode!r}; use cold|hot|audit",
            },
            as_json,
        )
        return 2
    try:
        # Second-wave P0: the projection routes as the SESSION agent, so
        # `context hot --agent B` reports A's live claim as FOREIGN instead of
        # impersonating A. audit has no routing surface and takes no agent.
        if mode == "audit":
            result = fn(project_root)
        else:
            result = fn(project_root, current_agent=_agent_for(project_root))
    except (HistoryOwnershipError, OSError) as exc:
        # Deterministic read-only failure contract (second-wave P1): a
        # symlinked/unreadable history node or canonical file must surface as
        # structured VALIDATION_FAILED with the reason, never a traceback.
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"history-ownership: {type(exc).__name__}: {exc}",
            },
            as_json,
        )
        return 1
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


def _userperson(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:
    """saipen userperson show/add/remove/reset (NITRO M7, journaled)."""
    if not args:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "userperson needs an action: show|add|remove|reset",
            },
            as_json,
        )
        return 2
    from userperson import (
        merge_profile,
        parse_profile,
        profile_path,
        remove_preference,
        render_profile,
        reset_profile,
        validate_profile,
        write_profile,
    )

    path = profile_path(project_root)
    action = args[0]
    current_text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
    if action == "show":
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"userperson show accepts no arguments; surplus: {' '.join(args[1:])}", # noqa: E501
                },
                as_json,
            )
            return 2
        if not current_text:
            _emit({"ok": True, "code": "EMPTY", "preferences": []}, as_json)
            return 0
        if as_json:
            # Validate BEFORE semantic parsing: a malformed source must
            # surface as invalid, never as a partial preference list that
            # hides the lines the lenient parser dropped (T-1003).
            profile_errors = validate_profile(current_text)
            if profile_errors:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "USERPERSON profile is malformed: "
                        + "; ".join(profile_errors[:5]),
                    },
                    as_json,
                )
                return 1
            _emit(
                {
                    "ok": True,
                    "code": "SHOW",
                    "preferences": parse_profile(current_text)["preferences"],
                },
                as_json,
            )
        else:
            print(current_text, end="")
        return 0
    if action == "reset":
        surplus = [a for a in args[1:] if a != "--confirm"]
        if surplus:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"userperson reset accepts only --confirm; surplus: {' '.join(surplus)}", # noqa: E501
                },
                as_json,
            )
            return 2
        if not path.is_file():
            _emit(
                {"ok": False, "code": "TICKET_NOT_FOUND", "detail": "no profile to reset"}, as_json
            )
            return 1
        if "--confirm" not in args:
            _emit(
                {
                    "ok": False,
                    "code": "DESTRUCTIVE_CONFIRMATION_REQUIRED",
                    "detail": "userperson reset deletes the profile; pass --confirm to authorize",
                },
                as_json,
            )
            return 1
        if dry_run:
            _emit({"ok": True, "code": "RESET", "dry_run": True}, as_json)
            return 0
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        # CORE says reset DELETES the profile; absence is the canonical OFF
        # state. One journaled delete_file target (real before_hash, empty
        # after_hash) -- NO post-commit unlink, so a crash between COMMIT and
        # unlink can never leave a state recovery cannot complete (T-1003
        # operational integrity). Recovery COMMITTED always means absent.
        result = reset_profile(project_root, _agent_for(project_root))
        if result.get("ok"):
            result["code"] = "RESET"
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if action in ("add", "remove"):
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"userperson {action} needs <text>",
                },
                as_json,
            )
            return 2
        category = "general"
        category_supplied = False
        clean_args = []
        idx = 0
        while idx < len(args):
            if args[idx] == "--category" and idx + 1 < len(args):
                category = args[idx + 1]
                category_supplied = True
                idx += 2
            else:
                clean_args.append(args[idx])
                idx += 1
        text = " ".join(clean_args[1:])
        from userperson import _redact_credentials

        text = _redact_credentials(text)
        if not text.strip():
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"userperson {action} needs non-empty text",
                },
                as_json,
            )
            return 2
        # Validate ANY existing profile BEFORE semantic parsing: a malformed
        # source must refuse with ZERO journal/write -- add/remove must never
        # silently rewrite the file without the lines the lenient parser
        # dropped (T-1003 source corruption -> data loss).
        if current_text:
            profile_errors = validate_profile(current_text)
            if profile_errors:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "existing USERPERSON profile is malformed; "
                        "refusing to mutate it: " + "; ".join(profile_errors[:5]),
                    },
                    as_json,
                )
                return 1
        current = parse_profile(current_text)["preferences"] if current_text else []
        if action == "add":
            updated = merge_profile(current, [f"- [{category}] {text}"])
        else:
            updated, refusal = remove_preference(
                current, text, category if category_supplied else None
            )
            if refusal:
                _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": refusal}, as_json)
                return 1
        new_text = render_profile(updated)
        if new_text == current_text:
            _emit({"ok": True, "code": "UNCHANGED"}, as_json)
            return 0
        if dry_run:
            _emit(
                {
                    "ok": True,
                    "code": "PREFERENCE_PLAN",
                    "action": action,
                    "text": text,
                    "category": category if action == "add" else None,
                    "dry_run": True,
                },
                as_json,
            )
            return 0
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = write_profile(project_root, new_text, _agent_for(project_root))
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    _emit(
        {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"unknown userperson action {action!r}",
        },
        as_json,
    )
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
    for key in (
        "action",
        "ticket",
        "load",
        "phase",
        "task",
        "next_action",
        "claimed_ticket",
        "top_workable_ticket",
        "log_tail_event",
        "head",
        "pending_ops",
        "code",
    ):
        value = payload.get(key)
        if value is not None and value != []:
            print(f"{key}: {value}")
    if payload.get("waiting_on_you"):
        print(f"Waiting on you: {'; '.join(payload['waiting_on_you'])}")
    if payload.get("claimed_but_unproven"):
        print(f"Claimed but unproven: {', '.join(payload['claimed_but_unproven'])}")
    if payload.get("conformance"):
        print(f"Conformance: {payload['conformance']}")
    if payload.get("staleness"):
        print(f"Staleness: {payload['staleness']}")


def _canonical_proof_levels() -> list[str]:
    """Read SAICRITIC's ordered proof vocabulary from its canonical table."""
    candidates = (HOME / "saipen" / "SAICRITIC.md", HOME / "SAICRITIC.md")
    critic = next((path for path in candidates if path.is_file()), None)
    if critic is None:
        raise ValueError("SAICRITIC.md is missing from the protocol install")
    text = critic.read_text(encoding="utf-8-sig")
    start = text.find("## What it does")
    end = text.find("\n## ", start + 3)
    section = text[start : end if end >= 0 else None]
    levels = re.findall(r"(?m)^\| ([A-Z]+) \|", section)
    if not levels or len(levels) != len(set(levels)):
        raise ValueError("SAICRITIC proof vocabulary is missing or duplicated")
    return levels


def _runtime_identity() -> str:
    """The runtime identifier supplied by the adapter/environment, else unknown
    (T-992/§5). This is an untrusted input, never mechanically detected model
    identity: it is stripped, bounded, and control-free before use, and a
    value that cannot be made safe becomes the truthful neutral 'unknown'."""
    import re as _re

    value = os.environ.get("SAIPEN_RUNTIME", "") or ""
    value = value.strip()
    if not value or len(value) > 128:
        return "unknown"
    if _re.search(r"[\x00-\x1f\x7f]", value):
        return "unknown"
    return value


def _improve(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:
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
    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    state, state_error = parse_state_or_error(codec.read_doc(state_path))
    if state_error:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"state-malformed: {state_error}"},
            as_json,
        )
        return 1

    from improve import archive_cycle, complete_cycle, cycle_dir, derive_status, write_sweep_entry

    from improve import _sweep_records
    import re as _re

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
        from improve import _field as _imp_field

        for cycle in sorted(imp_root.iterdir()):
            manifest = cycle / "MANIFEST.md"
            if not manifest.is_file():
                continue
            roster = manifest.read_text(encoding="utf-8-sig")
            sweep = (
                (cycle / "SWEEP.md").read_text(encoding="utf-8-sig")
                if (cycle / "SWEEP.md").is_file()
                else ""
            )
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
                roster_role = ""
                in_block = False
                for line in roster.splitlines():
                    if line == block:
                        in_block = True
                        continue
                    if line.startswith("seat_id:") and line != block:
                        in_block = False
                    if in_block and line.startswith("report_path:"):
                        report_path = line.split(":", 1)[1].strip()
                    if in_block and line.startswith("role:"):
                        roster_role = line.split(":", 1)[1].strip()
                if not report_path:
                    seats.append({"seat": seat, "role": roster_role, "visible": "missing"})
                    continue
                report = cycle / seat / report_path
                report_text = report.read_text(encoding="utf-8-sig") if report.is_file() else ""
                if not report_text:
                    seats.append({"seat": seat, "role": roster_role, "visible": "expected"})
                    continue
                # DOGFOOD V (T-620): status applies the SAME report-validation
                # depth the validator applies -- schema AND mechanical source
                # identity (fingerprint format + freshness for strict cycles).
                report_role = _imp_field(report_text, "role")
                report_errors = _vr(report_text, strict=strict)
                if report_role != roster_role:
                    report_errors.append(
                        f"roster/report role mismatch: {roster_role!r} != {report_role!r}"
                    )
                report_errors.extend(_rf(project_root, cycle, report_path, report_text, strict))
                if report_errors:
                    status_m = _re.search(r"(?m)^report_status:\s*(\S+)", report_text)
                    seats.append(
                        {
                            "seat": seat,
                            "role": roster_role,
                            "visible": "INVALID_REPORT",
                            "report_status": status_m.group(1) if status_m else "",
                            "errors": report_errors[:3],
                        }
                    )
                else:
                    derived = derive_status(report_path, roster, report_text, sweep, seat_id=seat)
                    seats.append({"seat": seat, "role": roster_role, **derived})
            rows.append(
                {
                    "cycle": cycle.name,
                    "cycle_status": status,
                    "seats": seats,
                    "invalid": invalid,
                    "manifest_errors": manifest_errors[:3],
                    "sweep_errors": sweep_errors[:3],
                }
            )
        return rows

    action = args[0] if args and not args[0].startswith("--") else None
    if action is None:
        # DOGFOOD V (T-617): bare `saipen improve` is the documented
        # meta-control -- it PREPARES the current seat's bounded audit
        # assignment, never an alias for status. It binds the project, finds
        # or mechanically admits the one active cycle, registers this seat,
        # creates the DRAFT report mechanically with the real captured source
        # identity, and returns the exact assignment the current agent must
        # execute. It never changes phase/task/next_action.
        try:
            proof_levels = _canonical_proof_levels()
        except (OSError, ValueError) as exc:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"cannot load canonical SAICRITIC proof vocabulary: {exc}",
                },
                as_json,
            )
            return 1
        role = "core"
        session_id = None
        explicit_new = False
        rest = list(args)
        while rest:
            if rest[0] == "--role" and len(rest) > 1:
                role, rest = rest[1], rest[2:]
            elif rest[0] == "--session" and len(rest) > 1:
                session_id, rest = rest[1], rest[2:]
            elif rest[0] == "--new-seat":
                explicit_new, rest = True, rest[1:]
            else:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"unknown or incomplete Improve prepare option {rest[0]!r}",
                    },
                    as_json,
                )
                return 2
        if session_id is not None and explicit_new:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "--session and --new-seat are mutually exclusive",
                },
                as_json,
            )
            return 2
        from improve import ImproveError, prepare_audit_seat
        from improve import installed_protocol_fingerprint as _proto_fp

        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        try:
            runtime = _runtime_identity()
            fingerprint = _proto_fp(HOME)
            prepared = prepare_audit_seat(
                project_root,
                agent_family=state.get("agent") or "agent",
                role=role,
                session_id=session_id,
                project_name="SAIPEN",
                model_or_runtime=runtime,
                protocol_fingerprint=fingerprint,
                context_scope=f"SAIPEN audit, phase {state.get('phase') or '?'}",
                context_available="partial",
                dry_run=dry_run,
            )
        except ImproveError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}, as_json)
            return 1
        if not prepared.get("ok"):
            _emit(prepared, as_json)
            return 1
        active_cycle = prepared["cycle_id"]
        seat_id = prepared["seat_id"]
        report_path = Path(prepared["report_path"])
        _emit(
            {
                "ok": True,
                "code": "IMPROVE_AUDIT_ASSIGNMENT",
                "op_id": prepared.get("op_id"),
                "cycle_id": active_cycle,
                "seat_id": seat_id,
                "role": prepared["role"],
                "report_path": report_path.relative_to(project_root).as_posix(),
                "report_created": prepared["report_created"],
                "resumed": prepared["resumed"],
                "dry_run": bool(prepared.get("dry_run")),
                "source": {
                    "source_head": prepared["source_head"],
                    "source_tree_fingerprint": prepared["source_tree_fingerprint"],
                    "discovery_model": prepared["discovery_model"],
                },
                "scope": {"phase": state.get("phase") or "?", "task": state.get("task") or ""},
                "proof_levels": proof_levels,
                "schema": "cycle + seat/report + RUN-N/IMP-NNN composite finding "
                "ref; dispositions go to SWEEP.md via saipen improve "
                "sweep; report completion via saipen improve complete",
                "write_boundary": "RUNs append via saipen improve submit; report "
                "completion via saipen improve complete; no raw "
                "report/MANIFEST/SWEEP editing",
                "next": f"perform the semantic audit, then: saipen improve submit "
                f"{active_cycle} {seat_id} SAIPEN <findings.json>",
            },
            as_json,
        )
        return 0
    if action == "submit":
        # DOGFOOD V (T-617): structured report submission -- the current agent
        # supplies the semantic RUN text in a JSON file, Python appends the
        # RUN mechanically through append_run (validated, journaled).
        if len(args) < 5:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "improve submit needs <cycle> <seat> <project> <findings.json>",
                },
                as_json,
            )
            return 2
        if len(args) > 5:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"improve submit takes <cycle> <seat> <project> "
                    f"<findings.json>; unsupported surplus argument "
                    f"{args[5]!r}",
                },
                as_json,
            )
            return 2
        from improve import append_run as _append_run
        from improve import resolve_report_path as _resolve_report_path

        cycle = cycle_dir(project_root, args[1])
        payload = Path(args[4])
        if not payload.is_file():
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"findings file not found: {args[4]}",
                },
                as_json,
            )
            return 2
        import json as _json

        try:
            data = _json.loads(payload.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"findings file is not valid JSON: {exc}",
                },
                as_json,
            )
            return 2
        # Shape-check before any .get(): array/scalar/null payloads would
        # otherwise crash with a raw AttributeError instead of a structured
        # refusal, and a non-string run_text must never reach .strip().
        if not isinstance(data, dict):
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "findings payload must be a JSON object with a run_text field",
                },
                as_json,
            )
            return 2
        run_text = data.get("run_text")
        if not isinstance(run_text, str) or not run_text.strip():
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "findings payload needs a non-empty string run_text field",
                },
                as_json,
            )
            return 2
        report = _resolve_report_path(project_root, args[1], args[2], args[3])
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        try:
            result = _append_run(report, run_text)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}, as_json)
            return 1
    if action == "complete":
        # DOGFOOD V (T-616): mechanical report completion -- full validation,
        # then draft -> complete, journaled and immutable.
        if len(args) < 4:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "improve complete needs <cycle> <seat> <project>",
                },
                as_json,
            )
            return 2
        from improve import complete_report as _complete_report
        from improve import resolve_report_path as _resolve_report_path

        report = _resolve_report_path(project_root, args[1], args[2], args[3])
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        try:
            result = _complete_report(report)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}, as_json)
            return 1
    if action == "sweep-queue":
        # DOGFOOD V (T-617): deterministic enumeration of the unswept finding
        # queue -- read-only; the semantic adjudication stays Core-owned.
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "improve sweep-queue needs <cycle_id>",
                },
                as_json,
            )
            return 2
        from improve import (
            composite_finding_ref,
            parse_report,
            verify_cycle,
            _report_ledger_keys,
            _seat_blocks,
            _field as _imp_field,
        )

        cycle = cycle_dir(project_root, args[1])
        precheck = verify_cycle(cycle)
        roster = (cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
        sweep = (
            (cycle / "SWEEP.md").read_text(encoding="utf-8-sig")
            if (cycle / "SWEEP.md").is_file()
            else ""
        )
        disposed = list(_sweep_records(sweep))
        queue = []
        for block in _seat_blocks(roster):
            if _imp_field(block, "availability") == "unavailable":
                continue
            seat_id = _imp_field(block, "seat_id")
            report_ident = _imp_field(block, "report_path")
            report_keys = _report_ledger_keys(roster, seat_id, report_ident)
            report = cycle / seat_id / report_ident
            if not report.is_file():
                continue
            for finding in parse_report(report.read_text(encoding="utf-8-sig")).findings:
                if any(
                    record.report in report_keys
                    and record.run() == finding.run
                    and record.imp() == finding.imp
                    for record in disposed
                ):
                    continue
                queue.append(
                    {
                        "finding_ref": composite_finding_ref(
                            cycle.name, seat_id, report_ident, finding.run, finding.imp
                        ),
                        "run": finding.run,
                        "imp": finding.imp,
                        "report": f"{seat_id}/{report_ident}",
                        "severity": finding.severity,
                        "class": finding.cls,
                        "expected": finding.expected,
                        "actual": finding.actual,
                        "evidence": finding.evidence,
                    }
                )
        _emit(
            {
                "ok": True,
                "code": "IMPROVE_SWEEP_QUEUE",
                "cycle": args[1],
                "queue": queue,
                "precheck_errors": precheck[:5],
                "note": "semantic adjudication (reproduce/classify/dedupe/"
                "decide) is Core-owned; commit each decision via "
                "saipen improve sweep",
            },
            as_json,
        )
        return 0
    if action == "status":
        rows = _cycle_statuses()
        if as_json:
            _emit({"ok": True, "code": "IMPROVE_STATUS", "cycles": rows}, as_json)
        else:
            for row in rows:
                print(f"{row['cycle']} ({row['cycle_status']})")
                for seat in row["seats"]:
                    print(
                        f"  {seat['seat']}: {seat.get('visible', '?')}"
                        + (
                            f" (report_status {seat.get('report_status')})"
                            if seat.get("report_status")
                            else ""
                        )
                        + (f" missing={seat.get('missing')}" if seat.get("missing") else "")
                    )
        return 0
    if action == "verify":
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "improve verify needs <cycle_id>",
                },
                as_json,
            )
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
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "; ".join(errors[:5]),
                    "delta_only": True,
                },
                as_json,
            )
            return 1
        _emit(
            {"ok": True, "code": "IMPROVE_VERIFY_PASS", "delta_only": True, "cycle": args[1]},
            as_json,
        )
        return 0
    if action == "sweep":
        if len(args) < 4:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "improve sweep needs <cycle> <finding_ref> "
                    "<disposition> [--ticket T-###] [--report "
                    "<ident>] [--reproduced y|n] where finding_ref "
                    "is RUN-N/IMP-NNN (strict) or IMP-NNN (legacy)",
                },
                as_json,
            )
            return 2
        cycle = cycle_dir(project_root, args[1])
        finding_ref, disposition = args[2], args[3]
        _run = None
        import re as _re

        _fm = _re.fullmatch(r"(?:RUN-(\d+)/)?IMP-(\d+)", finding_ref)
        if not _fm:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"finding_ref {finding_ref!r} is not RUN-N/IMP-NNN or IMP-NNN",
                },
                as_json,
            )
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
            _emit(
                {
                    "ok": True,
                    "code": "IMPROVE_SWEEP_PLAN",
                    "cycle": args[1],
                    "finding_ref": finding_ref,
                    "disposition": disposition,
                },
                as_json,
            )
            return 0
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        try:
            entry = {
                "imp_id": imp_id,
                "disposition": disposition,
                "ticket": ticket,
                "report": report,
                "reproduced": reproduced,
            }
            if run_raw is not None:
                entry["run"] = f"RUN-{run_raw}"
            result = write_sweep_entry(cycle, entry)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}, as_json)
            return 1
    if action == "cycle-complete":
        # DOGFOOD V (T-616): mechanical cycle completion through the public
        # path -- full cycle bar (strict manifest, every report full-valid,
        # exact composite sweep coverage), then ACTIVE -> COMPLETE.
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "improve cycle-complete needs <cycle_id>",
                },
                as_json,
            )
            return 2
        cycle = cycle_dir(project_root, args[1])
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        try:
            result = complete_cycle(cycle)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}, as_json)
            return 1
    if action == "abort":
        # DOGFOOD V (T-621): mechanical abort for a stuck draft cycle -- the
        # journaled exit for an active cycle whose report cannot complete.
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "improve abort needs <cycle_id>",
                },
                as_json,
            )
            return 2
        from improve import abort_cycle as _abort_cycle

        cycle = cycle_dir(project_root, args[1])
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        try:
            result = _abort_cycle(cycle)
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}, as_json)
            return 1
    if action == "clean":
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "improve clean needs <cycle_id>",
                },
                as_json,
            )
            return 2
        cycle = cycle_dir(project_root, args[1])
        # archive-with-provenance: only a COMPLETE (fully swept) cycle may be
        # archived; the sweep ledger + reports are preserved verbatim.
        if dry_run:
            _emit(
                {"ok": True, "code": "IMPROVE_CLEAN_PLAN", "cycle": args[1], "archive_only": True},
                as_json,
            )
            return 0
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        try:
            result = archive_cycle(cycle)
            _emit(
                {
                    "ok": result.get("ok", False),
                    "code": "IMPROVE_CLEAN" if result.get("ok") else "VALIDATION_FAILED",
                    "cycle": args[1],
                    "archive_only": True,
                    "detail": result.get("message", ""),
                },
                as_json,
            )
            return 0 if result.get("ok") else 1
        except ValueError as exc:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": str(exc),
                    "archive_only": True,
                },
                as_json,
            )
            return 1
    _emit(
        {
            "ok": False,
            "code": "UNKNOWN_ACTION",
            "detail": f"unknown saipen improve action {action!r}; use "
            "status|submit|complete|sweep|sweep-queue|"
            "verify|cycle-complete|abort|clean",
        },
        as_json,
    )
    return 2


def _public_improve(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:
    """Normalize expected Improve writer contention at the public boundary."""
    try:
        return _improve(project_root, args, as_json, dry_run)
    except PermissionError as exc:
        if str(exc) == "WRITER_BUSY":
            _emit(
                {
                    "ok": False,
                    "code": "WRITER_BUSY",
                    "detail": "another live writer holds the project lock",
                },
                as_json,
            )
            return 1
        raise


def main(argv: list[str] | None = None) -> int:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    if "--" in raw_args:
        dd_idx = raw_args.index("--")
        before_dashdash = raw_args[:dd_idx]
        after_dashdash = raw_args[dd_idx + 1 :]
    else:
        before_dashdash = raw_args
        after_dashdash = []

    as_json = "--json" in before_dashdash
    dry_run = "--dry-run" in before_dashdash
    project_root_opt: str | None = None

    clean_before: list[str] = []
    i = 0
    agent_opt: str | None = None
    while i < len(before_dashdash):
        arg = before_dashdash[i]
        if arg in ("--json", "--dry-run"):
            i += 1
        elif arg == "--agent" and i + 1 < len(before_dashdash):
            agent_opt = before_dashdash[i + 1]
            i += 2
        elif arg.startswith("--agent="):
            agent_opt = arg.split("=", 1)[1]
            i += 1
        elif arg == "--project-root" and i + 1 < len(before_dashdash):
            project_root_opt = before_dashdash[i + 1]
            i += 2
        elif arg.startswith("--project-root="):
            project_root_opt = arg.split("=", 1)[1]
            i += 1
        else:
            clean_before.append(arg)
            i += 1

    args = clean_before + (["--", *after_dashdash] if "--" in raw_args else [])

    # T-1006: an explicit `--agent <id>` is a GENUINE-HANDOVER request; the
    # bare CLI (override None) inherits the persisted STATE.agent seat. The
    # mandatory old -> new DEC is written by handover_agent before the first
    # mutating command below dispatches.
    global _AGENT_OVERRIDE # noqa: PLW0603
    _AGENT_OVERRIDE = agent_opt.strip() if agent_opt and agent_opt.strip() else None

    if not args or args[0] in ("-h", "--help"):
        usage_msg = (
            "usage: saipen (status|next|recover|claim <T-###>|"
            "transition <PHASE> [T-###] [text]|checkpoint <TAXONOMY> "
            "[T-###] [text]|ticket add <PRIORITY> <text>|ticket "
            "done <T-###>|ticket block <T-###> <reason>|ticket "
            "unblock <T-###> <decision>|improve|improve "
            "status|improve sweep <cycle> <RUN-N/IMP-NNN> <DISPOSITION> "
            "|improve sweep-queue <cycle>|improve submit <cycle> <seat> "
            "<project> <findings.json>|improve complete <cycle> <seat> "
            "<project>|improve verify <cycle>|improve cycle-complete "
            "<cycle>|improve abort <cycle>|improve clean <cycle>|"
            "ship|push|scope <T-###> <path>...|first-publish-confirm "
            "<name> <public|private>|userperson|sub|rebind-home "
            "<candidate-home>|context) [--dry-run] "
            "[--json] [--project-root PATH] [--agent ID]"
        )
        if as_json:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": usage_msg}, as_json)
        else:
            print(usage_msg)
        return 2

    project_root, root_reason = resolve_project_root(
        Path.cwd().resolve(), explicit=project_root_opt
    )
    if project_root is None:
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT", "detail": root_reason}, as_json)
        return 3

    command = args[0]

    # T-1006/T-1014: an explicit --agent override is a genuine handover, but
    # it is deferred -- `_ensure_handover` runs only immediately before an
    # admissible mutation, after the concrete action's syntax/arity
    # validation has passed. A malformed/unknown invocation therefore stays
    # ownership-zero-write; read-only projections route under the resolved
    # actor without touching disk.

    if command == "status":
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"status accepts no arguments; surplus: {' '.join(args[1:])}",
                },
                as_json,
            )
            return 2
        return _status(project_root, as_json)
    if command == "next":
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"next accepts no arguments; surplus: {' '.join(args[1:])}",
                },
                as_json,
            )
            return 2
        return _next_action(project_root, as_json)
    if command == "recover":
        return _recover(project_root, args[1:], as_json, dry_run)
    if command == "claim":
        if len(args) < 2:
            _emit(
                {"ok": False, "code": "VALIDATION_FAILED", "detail": "claim needs <T-###>"}, as_json
            )
            return 2
        if len(args) > 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"claim takes <T-###>; surplus: {' '.join(args[2:])}",
                },
                as_json,
            )
            return 2
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = (
            plan_claim(project_root, args[1], _agent_for(project_root))
            if dry_run
            else apply_claim(project_root, args[1], _agent_for(project_root))
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command == "transition":
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "ILLEGAL_TRANSITION",
                    "detail": "transition needs <PHASE> [T-###] [text]",
                },
                as_json,
            )
            return 2
        ticket = args[2] if len(args) > 2 and args[2].upper().startswith("T-") else None
        text = " ".join(args[3:] if ticket else args[2:])
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = transition_phase(
            project_root, args[1], _agent_for(project_root), ticket, text, dry_run=dry_run
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command == "checkpoint":
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "checkpoint needs <TAXONOMY> [T-###] [text]",
                },
                as_json,
            )
            return 2
        ticket = args[2] if len(args) > 2 and args[2].upper().startswith("T-") else None
        text = " ".join(args[3:] if ticket else args[2:])
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = checkpoint(
            project_root, _agent_for(project_root), args[1], ticket, text, dry_run=dry_run
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command == "ticket":
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "ticket needs an action: add|done|block|unblock",
                },
                as_json,
            )
            return 2
        action = args[1]
        rest = args[2:]
        if action == "add":
            if len(rest) < 2:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "ticket add <PRIORITY> <description> "
                        "[--verify <text>] [--needs T-X,T-Y]",
                    },
                    as_json,
                )
                return 2
            verify_arg = ""
            needs_arg = []
            has_verify = False
            has_needs = False

            if "--" in rest:
                dd_idx = rest.index("--")
                pre_dd = rest[:dd_idx]
                post_dd = rest[dd_idx + 1 :]
            else:
                pre_dd = rest
                post_dd = []

            clean_rest = []
            idx = 0
            while idx < len(pre_dd):
                if pre_dd[idx] == "--verify":
                    if has_verify:
                        _emit(
                            {
                                "ok": False,
                                "code": "VALIDATION_FAILED",
                                "detail": "duplicate --verify option",
                            },
                            as_json,
                        )
                        return 2
                    if idx + 1 >= len(pre_dd):
                        _emit(
                            {
                                "ok": False,
                                "code": "VALIDATION_FAILED",
                                "detail": "dangling --verify option",
                            },
                            as_json,
                        )
                        return 2
                    verify_arg = pre_dd[idx + 1]
                    has_verify = True
                    idx += 2
                elif pre_dd[idx] == "--needs":
                    if has_needs:
                        _emit(
                            {
                                "ok": False,
                                "code": "VALIDATION_FAILED",
                                "detail": "duplicate --needs option",
                            },
                            as_json,
                        )
                        return 2
                    if idx + 1 >= len(pre_dd):
                        _emit(
                            {
                                "ok": False,
                                "code": "VALIDATION_FAILED",
                                "detail": "dangling --needs option",
                            },
                            as_json,
                        )
                        return 2
                    needs_arg = [n.strip() for n in pre_dd[idx + 1].split(",") if n.strip()]
                    has_needs = True
                    idx += 2
                elif pre_dd[idx].startswith("--"):
                    _emit(
                        {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": f"unknown option {pre_dd[idx]}",
                        },
                        as_json,
                    )
                    return 2
                else:
                    clean_rest.append(pre_dd[idx])
                    idx += 1

            clean_rest.extend(post_dd)

            if len(clean_rest) < 2:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "ticket add needs <PRIORITY> <description>",
                    },
                    as_json,
                )
                return 2
            _rc = _ensure_handover(project_root, as_json, dry_run)
            if _rc is not None:
                return _rc
            result = ticket_add(
                project_root,
                _agent_for(project_root),
                clean_rest[0],
                " ".join(clean_rest[1:]),
                needs_arg,
                verify_arg,
                dry_run=dry_run,
            )
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
        if action == "done":
            if not rest:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "ticket done needs <T-###>",
                    },
                    as_json,
                )
                return 2
            if len(rest) > 1:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"ticket done takes <T-###>; surplus: {' '.join(rest[1:])}",
                    },
                    as_json,
                )
                return 2
            _rc = _ensure_handover(project_root, as_json, dry_run)
            if _rc is not None:
                return _rc
            result = finish_ticket(project_root, rest[0], _agent_for(project_root), dry_run=dry_run)
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
        if action in ("block", "unblock"):
            if not rest:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"ticket {action} needs <T-###> [reason/decision]",
                    },
                    as_json,
                )
                return 2
            _rc = _ensure_handover(project_root, as_json, dry_run)
            if _rc is not None:
                return _rc
            result = ticket_move(
                project_root,
                action,
                rest[0],
                _agent_for(project_root),
                " ".join(rest[1:]),
                dry_run=dry_run,
            )
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"unknown ticket action {action!r}",
            },
            as_json,
        )
        return 2
    if command == "userperson":
        return _userperson(project_root, args[1:], as_json, dry_run)
    if command == "sub":
        return _sub(project_root, args[1:], as_json, dry_run)
    if command == "rebind-home":
        if len(args) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "HOME_REQUIRED",
                    "detail": "rebind-home needs <candidate-home-path>",
                },
                as_json,
            )
            return 2
        if len(args) > 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"rebind-home takes <candidate-home-path>; surplus: {' '.join(args[2:])}", # noqa: E501
                },
                as_json,
            )
            return 2
        from saipen_engine.operations import rebind_saipen_home

        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = rebind_saipen_home(
            project_root, _agent_for(project_root), args[1], dry_run=dry_run
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command == "crew":
        return _crew(project_root, args[1:], as_json, dry_run)
    if command == "context":
        return _context(project_root, args[1:], as_json, dry_run)
    if command == "improve":
        return _public_improve(project_root, args[1:], as_json, dry_run)
    if command == "scope":
        if len(args) < 3:
            _emit(
                {
                    "ok": False,
                    "code": "SOURCE_SCOPE_MISSING",
                    "detail": "scope needs <T-###> <path> [path ...]",
                },
                as_json,
            )
            return 2
        from saipen_engine.operations import record_scope

        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = record_scope(
            project_root, args[1], _agent_for(project_root), args[2:], dry_run=dry_run
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command in ("first-publish-confirm", "fpc"):
        if len(args) != 3:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "first-publish-confirm needs <name> <public|private>",
                },
                as_json,
            )
            return 2
        from saipen_engine.operations import confirm_first_publish

        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = confirm_first_publish(
            project_root, _agent_for(project_root), args[1], args[2], dry_run=dry_run
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command in ("ship", "push"):
        surplus = [a for a in args[1:] if not a.startswith("--")]
        unknown_flags = [a for a in args[1:] if a.startswith("--")]
        if surplus or unknown_flags:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": (
                        f"{command} accepts no arguments; surplus: "
                        f"{' '.join(surplus + unknown_flags)}"
                    ),
                },
                as_json,
            )
            return 2
        from saipen_engine.release import ReleaseRefusal, execute_release, plan_release

        try:
            # P0#4: inject the freshly negotiated current-session capability so
            # a read-only session cannot PLAN a release. Second-wave P0: the
            # acting identity is the SESSION agent, never persisted STATE.agent.
            plan = plan_release(
                project_root,
                command,
                dry_run=dry_run,
                current_capability=_negotiate_capability(project_root),
                current_agent=_agent_for(project_root),
            )
        except ReleaseRefusal as exc:
            _emit({"ok": False, "code": exc.code, "detail": exc.detail}, as_json)
            return 1
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}, as_json)
            return 1
        _rc = _ensure_handover(project_root, as_json, dry_run)
        if _rc is not None:
            return _rc
        result = execute_release(project_root, plan)
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if as_json:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"unknown command: {command}"},
            as_json,
        )
    else:
        print(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

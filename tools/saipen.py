#!/usr/bin/env python
# ruff: noqa: E402
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
from contextlib import suppress
from pathlib import Path

# Public commands promise not to dirty the project merely by importing their
# implementation. Set this before importing project modules so ``tt`` and all
# other read-only routes cannot create ``__pycache__``/``.pyc`` artifacts.
sys.dont_write_bytecode = True

from saipen_engine import codec, snapshot
from saipen_engine.board import parse_board, ticket_is_workable
from saipen_engine.commands import load_shortcut_table, resolve_shortcut
from saipen_engine.journal import auto_recover_pending
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
# The canonical protocol home this adapter ships from: the shortcut table and
# its Cyrillic-twin normalization are read from here through the ONE shared
# engine resolver -- never re-declared in this file (no Cyrillic literal, no
# second confusable map, no hardcoded twin dictionary may live below).
PROTOCOL_DIR = HOME / "saipen"

# The ONE canonical actor resolver (T-1006): bare CLI INHERITS STATE.agent
# -- the seat CORE.md section 1.4 defines -- and an explicit `--agent <id>`
# is a genuine-handover request that MUST log a DEC naming old -> new before
# any mutation. STATE.agent is never invented by the CLI; only an explicit
# override replaces the inherited seat.
_AGENT_OVERRIDE: str | None = None

# Adaptive Runtime Wave 1: optional runtime metadata is telemetry for this
# invocation.  It is deliberately separate from `_AGENT_OVERRIDE`, which owns
# the acting seat/handover identity.  The projection is read-only and never
# persists this value into project state.
_RUNTIME_INFO_OVERRIDE: str | None = None

# CORE § 1.10 (Cyrillic-twin incident): when the invoked command resolved
# through the shared shortcut resolver, EVERY payload this adapter emits
# carries `route` -- the canonical Latin key the raw token landed on. The
# agreement property is then mechanical: whatever the resolver declares,
# every branch's output (success or refusal) names its route, so output can
# never silently disagree with resolution. Set once in main(); None when the
# invocation was not a declared shortcut (direct verbs stay untagged).
_ROUTE_ECHO: str | None = None


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
#   status / next / context / runtime / recover inspect  READ_ONLY
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
#   focus / ff ........................................ READ_ONLY
#   cut / xx target ................................... READ_ONLY preview
#   cut / xx confirm .................................. MUTATING
#   build / vv ........................................ MUTATING
#   undo / zz ......................................... READ_ONLY preview
#   undo / zz confirm ................................. MUTATING
#   permissions ....................................... READ_ONLY
#   explain-next ...................................... READ_ONLY
#   source status|show ................................ READ_ONLY
#   source capture|req|disp|close|archive|purge ....... MUTATING
_MUTATING_TOPLEVEL = frozenset(
    {
        "claim",
        "transition",
        "checkpoint",
        "ticket",
        "goal",
        # CORE § 1.10 shortcut rows with mutating destinations: gg -> goal,
        # hh -> hunt, aa -> markhunt, pp -> sub spawn saipython. `sss` is
        # read-only (status) and deliberately absent; ss/dd/tt/ccc have no
        # deterministic CLI executor and refuse before any write.
        "gg",
        "hh",
        "aa",
        "pp",
        "continue",
        "cc",
        "rebind-home",
        "crew",
        "autonomous-crew",
        "sc",
        "prepare",
        "prepare-translate",
        "qq",
        "ee",
        "ship-wiki",
        "ship-translate",
        "qqq",
        "eee",
        "scope",
        "first-publish-confirm",
        "fpc",
        "ship",
        "push",
        # AUTO-003: CORE section 1.10 phase-trigger verbs mutate STATE (phase
        # transition). They are recognized canonical commands -- never rejected
        # as unknown, which previously tempted a weak model to improvise a
        # destructive substitute (`saipen clean` -> `sub clean saihunt`).
        "clean",
        "hunt",
        "markhunt",
        "translate",
        "validate",
        "plan",
        "build",
        "vv",
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
    if command in ("focus", "ff"):
        return False
    if command in ("cut", "xx"):
        return (
            sub == "confirm"
            and len(rest) == 4
            and bool(rest[1].strip())
            and rest[2] == "--"
            and bool(rest[3].strip())
        )
    if command in ("undo", "zz"):
        return (
            sub == "confirm"
            and len(rest) >= 4
            and rest[2] == "--reason"
            and bool(" ".join(rest[3:]).strip())
        )
    if command in ("build", "vv"):
        return bool(" ".join(rest).strip())
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


def _ensure_handover(
    project_root: Path, as_json: bool, dry_run: bool, allow_dead_home: bool = False
) -> int | None:
    """Deferred handover hook (CORE-003).

    The A -> B seat handover is FOLDED into each admitting mutation
    transaction by the operations layer: when the acting agent differs
    from persisted STATE.agent, the mutation's own DEC includes the
    old -> new ownership edge. This avoids a separate pre-write that
    could orphan a handover DEC when the dependent mutation is rejected.
    This helper is retained for import stability and performs no disk
    write; the fold is implemented in operations._event_line_with_handover.
    """
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


def _same_install_path(a: Path, b: Path) -> bool:
    """Path identity that tolerates Windows case and separator drift."""
    left, right = str(a), str(b)
    if os.name == "nt":
        left, right = left.lower().replace("/", "\\"), right.lower().replace("/", "\\")
    return left == right


def _runtime_drift_payload(project_root: Path, command: str) -> dict | None:
    """T-1159: diagnose stale-installed-runtime drift on an unknown command.

    The observed incident: a project booted against SAIPEN home A was driven
    with an OLDER install B whose adapter lacked `continue`, producing a bare
    ``unknown command`` that invited improvisation. When the project's own
    `saipen_home` names an install other than the executing runtime, the
    unknown command is reported as RUNTIME_DRIFT with both versions and the
    exact safe action -- never silently reinterpreted, never auto-migrated.
    """
    state_path = _state_path(project_root)
    if not state_path.is_file():
        return None
    try:
        head = state_path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    except OSError:
        return None
    match = re.search(
        r"^saipen_home:\s*\"?([^\"\r\n]+?)\"?\s*$", head, re.MULTILINE | re.IGNORECASE
    )
    if not match:
        return None
    other_raw = match.group(1).strip()
    if not other_raw:
        return None
    mine = HOME.resolve()
    other = Path(other_raw)
    with suppress(OSError):
        other = other.resolve()
    if _same_install_path(other, mine):
        return None

    def _version_at(path: Path) -> str:
        try:
            return (path / "VERSION").read_text(encoding="utf-8-sig").strip()
        except OSError:
            return "unavailable"

    runner = other / "tools" / "saipen.py"
    return {
        "ok": False,
        "code": "RUNTIME_DRIFT",
        "command": command,
        "runtime": {"home": str(mine), "version": _version_at(mine)},
        "project_protocol": {"home": str(other), "version": _version_at(other)},
        "detail": (
            f"command {command!r} is not implemented by this runtime, and this "
            "project's saipen_home points at a DIFFERENT SAIPEN install; this "
            "is runtime drift between the installed skill/runtime and the "
            "project protocol, not a project error (CORE § 1.10)"
        ),
        "action": (
            f"drive this project through {runner} if it exists (the project's "
            f"own protocol home), or from a trusted install run "
            f"`saipen rebind-home {other}`; no silent fallback to different "
            "semantics is performed"
        ),
    }


def _state_path(project_root: Path) -> Path:
    return project_root / ".saipen" / "STATE.md"


def _scan_full(project_root: Path) -> tuple[list[str], list[str], list[dict]]:
    """ONE recovery-manifest traversal for pending ids, conflicts AND the
    structured corrupt records (T-1014). One scan serves all three
    projections, so every command sees exactly one manifest snapshot."""
    from saipen_engine.journal import scan_pending

    pending, conflicts = scan_pending(project_root)
    return (
        [op["op_id"] for op in pending],
        [op["op_id"] for op in conflicts],
        [op for op in pending if op.get("corrupt")],
    )


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


def _capability_refusal(as_json: bool) -> int:
    """Emit the read-only capability refusal and return exit 1 (CORE-002).

    Called AFTER the concrete command's syntax/arity validation has passed
    but BEFORE any real write/handover/journal creation, so a malformed
    mutating invocation still gets its specific VALIDATION_FAILED message
    and stays zero-write, while a syntactically valid mutating invocation
    under a read-only session is refused deterministically.
    """
    _emit(
        {
            "ok": False,
            "code": "CAPABILITY_DENIED",
            "detail": "current session capability is read-only; no mutating "
            "command may proceed without --dry-run",
        },
        as_json,
    )
    return 1


def _parked_work(board_tickets: dict, state: dict) -> list[str]:
    """The complete parked-work summary (CORE-006).

    Every `## BLOCKED` ticket, any untriaged `[MARKHUNT]` finding, and a
    live `WAIT:` from STATE. Deduplicated, read-only, zero-write.
    """
    parked: list[str] = []
    seen: set[str] = set()
    for tid, ticket in board_tickets.items():
        if ticket.get("section") == "## BLOCKED":
            blocker = ticket.get("fields", {}).get("blocker", "")
            label = f"{tid} blocked: {blocker}" if blocker else f"{tid} blocked"
            if tid not in seen:
                parked.append(label)
                seen.add(tid)
    # A live STATE WAIT carries a live stuck signal.
    wait = state.get("wait")
    if wait and str(wait).strip():
        key = f"WAIT: {wait}"
        if key not in seen:
            parked.append(key)
            seen.add(key)
    # Untriaged [MARKHUNT] findings: any BLOCKED ticket whose blocker text
    # references an untriaged markhunt finding.
    for tid, ticket in board_tickets.items():
        blocker = ticket.get("fields", {}).get("blocker", "")
        if "[MARKHUNT]" in blocker.upper() and tid not in seen:
            parked.append(f"{tid} untriaged [MARKHUNT]")
            seen.add(tid)
    return parked


def _permissions(project_root: Path, as_json: bool) -> int:
    """T-1160: read-only effect-authorization diagnostic (P2).

    Explains, per effect: the POLICY in force and where it came from, what
    the HOST enforcement actually is (UNAVAILABLE unless declared), whether
    the combination leaves an ENFORCEMENT_GAP, and the tool/adapter effect
    contracts. Also reports the current dirty worktree through the cheap
    read-only Git delta. It NEVER claims a sandbox it cannot see.
    """
    from saipen_engine.capability import negotiate_capability
    from saipen_engine.effects import (
        TOOL_GUARANTEED_EFFECTS,
        TOOL_POSSIBLE_EFFECTS,
        assess_enforcement_gap,
        load_policy,
        tree_snapshot,
    )

    capability = negotiate_capability()
    loaded = load_policy(project_root, capability=capability)
    gap = assess_enforcement_gap(loaded["policy"])
    tree = tree_snapshot(project_root)
    payload = {
        "ok": True,
        "code": "PERMISSIONS",
        "capability": capability,
        "policy_source": loaded["source"],
        "policy_overrides": loaded["overrides"],
        "policy": loaded["policy"],
        "host_enforcement": gap["host"],
        "strict_effects": gap["policy_strict_effects"],
        "enforcement_gap": gap["gap"],
        "enforcement_verdict": gap["verdict"],
        "tool_contracts": {
            "guaranteed": {k: list(v) for k, v in TOOL_GUARANTEED_EFFECTS.items()},
            "possible": {k: list(v) for k, v in TOOL_POSSIBLE_EFFECTS.items()},
            "note": "possible effects are capability, not observation",
        },
        "worktree_delta": {"status": tree["status"], "paths": list(tree["paths"])},
    }
    if as_json:
        _emit(payload, True)
        return 0
    print(f"session capability : {capability}")
    print(f"policy source      : {payload['policy_source']}")
    if payload["policy_overrides"]:
        for override in payload["policy_overrides"]:
            print(f"  override         : {override}")
    for effect in sorted(payload["policy"]):
        marker = " *" if payload["policy"][effect] != "ALLOW" else ""
        print(f"  {effect:<18} {payload['policy'][effect]}{marker}")
    print(f"host enforcement   : {gap['host']['strength']} ({gap['host']['note']})")
    if gap["gap"]:
        strict = ", ".join(gap["policy_strict_effects"])
        print("ENFORCEMENT_GAP    : policy is stricter than enforced reality")
        print(f"  strict effects   : {strict}")
        print("  indirect execution paths may bypass tool-specific approval")
    print(
        f"worktree delta     : {tree['status']}"
        + (f" ({len(tree['paths'])} changed)" if tree["paths"] else "")
    )
    return 0


def _runtime(project_root: Path, as_json: bool) -> int:
    """Adaptive Runtime Wave-1 read-only identity/capability projection."""
    from saipen_engine.runtime import RuntimeInfoError, runtime_projection

    try:
        projection = runtime_projection(
            _agent_for(project_root), explicit_path=_RUNTIME_INFO_OVERRIDE
        )
    except RuntimeInfoError as exc:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": str(exc),
            },
            as_json,
        )
        return 1

    payload = {"ok": True, "code": "RUNTIME", **projection}
    if as_json:
        _emit(payload, True)
        return 0
    print("SAIPEN runtime (read-only)")
    print(f"agent seat : {projection['agent']}")
    print(f"metadata   : {projection['runtime_info_source']}")
    for field in ("harness", "provider", "model", "variant"):
        print(f"{field:<10} : {projection[field] or 'UNKNOWN'}")
    print("capabilities:")
    for name, value in projection["capabilities"].items():
        rendered = "UNKNOWN" if value is None else str(value).lower()
        print(f"  {name:<28} {rendered}")
    return 0


def _status(project_root: Path, as_json: bool) -> int:
    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    try:
        snap = snapshot.ProjectSnapshot.capture(project_root)
    except (OSError, ValueError) as exc:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"history-ownership: {exc}"},
            as_json,
        )
        return 1
    state_text = snap.state_text
    board_text = snap.board_text
    state, state_error = parse_state_or_error(state_text)
    if state_error:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"state-malformed: {state_error}"},
            as_json,
        )
        return 1
    board = parse_board(board_text)
    doing = [t for t in board["tickets"].values() if t["section"] == "## DOING"]
    todo = [t for t in board["tickets"].values() if t["section"] == "## TODO"]
    done_tickets = [t for t in board["tickets"].values() if t["section"] == "## DONE"]
    blocked_tickets = [t for t in board["tickets"].values() if t["section"] == "## BLOCKED"]

    top_workable = None
    resolved_agent = (
        _AGENT_OVERRIDE if _AGENT_OVERRIDE is not None else (state.get("agent") or AGENT)
    )
    if not board["errors"]:
        for ticket in todo:
            if ticket_is_workable(ticket, board["tickets"], agent=resolved_agent):
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
        current_agent=resolved_agent,
        snap=snap,
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
    # Restore Milestones are a separate, optional authority domain.  Status
    # reads bounded metadata only; full payload integrity belongs to create,
    # undo and validate, never the common `sss` hot path.
    from saipen_engine.controls import milestone_status

    payload["milestone"] = milestone_status(project_root)
    parked = _parked_work(board["tickets"], state)
    if parked:
        payload["parked_work"] = parked
    if waiting_on_you:
        payload["waiting_on_you"] = waiting_on_you
    if claimed_but_unproven:
        payload["claimed_but_unproven"] = claimed_but_unproven
    if conformance is not None:
        payload["conformance"] = conformance
    if staleness is not None:
        payload["staleness"] = staleness

    # §8 Conformance Closure: the authoritative current-conformance status,
    # derived from the canonical validator receipt, not from prose in the LOG.
    # `conformance` (above) is the legacy history-derived hint; this is the
    # load-bearing truth that gates terminal/crew closure.
    try:
        from saipen_engine.conformance import conformance_status

        payload["conformance_status"] = conformance_status(project_root, gate="core")
    except Exception as exc:
        # Conformance is load-bearing terminal truth.  A projection may never
        # report ok:true while silently omitting it because evidence decoding
        # failed unexpectedly.
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"conformance-status: {type(exc).__name__}: {exc}",
            },
            as_json,
        )
        return 1

    _emit(payload, as_json)
    return 0


def _next_action(project_root: Path, as_json: bool) -> int:
    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    # T-1014: ONE recovery-manifest traversal (pending + conflicts + corrupt).
    pending, conflicts, _corrupt = _scan_full(project_root)
    if _corrupt:
        _emit(_corrupt_refusal(_corrupt), as_json)
        return 1
    try:
        snap = snapshot.ProjectSnapshot.capture(project_root)
    except (OSError, ValueError) as exc:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"history-ownership: {exc}"},
            as_json,
        )
        return 1
    state_text = snap.state_text
    board_text = snap.board_text
    from saipen_engine.state import parse_state_or_error

    state, state_error = parse_state_or_error(state_text)
    if state_error:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"state-malformed: {state_error}"},
            as_json,
        )
        return 1
    subject = state.get("task")
    board = parse_board(board_text)
    parked = _parked_work(board["tickets"], state)
    from saipen_engine.router import load_for_action, route_next, routing_failure_code

    # P0#4: the freshly negotiated current-session capability gates routing.
    # T-1006: routing judges claim truth against the canonical acting seat.
    resolved_agent = (
        _AGENT_OVERRIDE if _AGENT_OVERRIDE is not None else (state.get("agent") or AGENT)
    )
    routed = route_next(
        state_text,
        board_text,
        pending,
        conflicts,
        current_capability=_negotiate_capability(project_root),
        current_agent=resolved_agent,
        snap=snap,
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
                "parked_work": parked or None,
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
            "execution_intent": state.get("execution_intent") or "normal",
            "converge_target": state.get("converge_target"),
            "goal_waves": state.get("goal_waves"),
            "goal_tickets": state.get("goal_tickets"),
            "recovery_pending": bool(pending),
            "recovery_conflict": False,
            "pending_ops": pending,
            "parked_work": parked or None,
        },
        as_json,
    )
    return 0


def _explain_next(project_root: Path, as_json: bool) -> int:
    """T-1161: read-only decision-trace diagnostic (P2).

    Routes the same next action `next`/`cc` would take, then classifies WHO
    owns it via the closed disposition vocabulary. Makes the no-human-courier
    law inspectable: candidates, selected action, authority, and exactly why
    the human is or is not required. Writes nothing.
    """
    from saipen_engine.disposition import classify_carrier

    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    pending, conflicts, _corrupt = _scan_full(project_root)
    if _corrupt:
        _emit(_corrupt_refusal(_corrupt), as_json)
        return 1
    try:
        snap = snapshot.ProjectSnapshot.capture(project_root)
    except (OSError, ValueError) as exc:
        _emit(
            {"ok": False, "code": "VALIDATION_FAILED", "detail": f"history-ownership: {exc}"},
            as_json,
        )
        return 1
    state_text = snap.state_text
    board_text = snap.board_text
    from saipen_engine.state import parse_state_or_error

    state, state_error = parse_state_or_error(state_text)
    if state_error:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"state-malformed: {state_error}",
            },
            as_json,
        )
        return 1
    parked = _parked_work(parse_board(board_text)["tickets"], state)
    from saipen_engine.router import route_next, routing_failure_code

    resolved_agent = (
        _AGENT_OVERRIDE if _AGENT_OVERRIDE is not None else (state.get("agent") or AGENT)
    )
    routed = route_next(
        state_text,
        board_text,
        pending,
        conflicts,
        current_capability=_negotiate_capability(project_root),
        current_agent=resolved_agent,
        snap=snap,
    )
    if not routed.get("ok"):
        carrier = {
            "code": routing_failure_code(routed),
            "action": routed.get("action"),
            "reason": routed.get("reason"),
            "next_action": routed.get("action"),
            "recovery_pending": bool(pending),
        }
    else:
        carrier = {
            "ok": True,
            "code": "ROUTED",
            "action": routed.get("action"),
            "reason": routed.get("reason"),
            "next_action": routed.get("action"),
            "terminal": False,
            "requires_human": bool(routed.get("requires_human")),
            "execute_in_current_agent": True,
        }
    verdict = classify_carrier(carrier)
    payload = {
        "ok": True,
        "code": "EXPLAIN_NEXT",
        "state": {
            "phase": state.get("phase"),
            "task": state.get("task"),
            "execution_intent": state.get("execution_intent") or "normal",
            "converge_target": state.get("converge_target"),
        },
        "carrier": {k: v for k, v in carrier.items() if v is not None},
        "disposition": verdict["disposition"],
        "owner": "user" if verdict["requires_human"] else "agent",
        "human_required": verdict["requires_human"],
        "why": verdict["reason"],
        "selected_action": verdict["action"],
        "parked_work": parked or None,
        "note": (
            "internal sequencing alternatives never create a human decision; "
            "WAIT_USER requires human-owned information or authority"
        ),
    }
    _emit(payload, as_json)
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

        if dry_run:
            _emit(
                {
                    "ok": False,
                    "code": "DRY_RUN_UNSUPPORTED",
                    "detail": "dry_run not supported for recovery mutations",
                },
                as_json,
            )
            return 1
        if _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run=False)
        if _ho is not None:
            return _ho
        result = resolve_conflict(project_root, op_id, resolution, agent=_agent_for(project_root))
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    # W2-001/W2-002 (audit fdc73e06): bare recovery is a MUTATION with a
    # closed grammar. Any non-empty argument list that is not exactly
    # `inspect <op_id>` / `resolve <op_id> ...` is VALIDATION_FAILED with
    # zero writes -- a stray token must never silently authorize replay.
    if args and args[0] not in ("inspect", "resolve"):
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "recover takes no arguments (bare recover), or "
                "`inspect <op_id>` / `resolve <op_id> [--resolution "
                "accept_live|replan]`; unexpected: " + " ".join(args),
            },
            as_json,
        )
        return 2
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
    # W2-001 (audit fdc73e06): automatic replay is a mutating writer and must
    # carry the same session mutation boundary as `recover resolve` -- dry-run
    # is zero-write, a read-only session refuses, and the acting seat is the
    # canonical resolver. A bare `recover --dry-run` previously replayed the
    # operation and wrote canonical bytes.
    if dry_run:
        _emit(
            {
                "ok": False,
                "code": "DRY_RUN_UNSUPPORTED",
                "detail": "dry_run not supported for recovery mutations",
                "pending_ops": pending,
            },
            as_json,
        )
        return 1
    if _negotiate_capability(project_root) == "read-only":
        return _capability_refusal(as_json)
    _ho = _ensure_handover(project_root, as_json, dry_run=False)
    if _ho is not None:
        return _ho
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

    # CORE-002: list/status are read-only; all other sub actions mutate and
    # must respect the live read-only capability gate.
    if action not in ("list", "status") and not dry_run:
        if _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho

    def _run(thunk):
        """One sub-action execution with the structured CLI boundary
        (T-1013): a residual path-length/host filesystem failure (an ID that
        passes every safe-ID check yet still breaks the host path budget) is
        a zero-write VALIDATION_FAILED refusal, never a traceback.

        T-1014: mutating sub actions previously performed the seat handover
        here, but the acting seat now folds into the op's own admissible
        transaction (W2-001) -- a rejected command writes nothing.
        list/status are read-only and never hand over."""
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
    semantic stage work back to the agent; `saipen crew`/`sc` then resumes
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
    try:
        if dry_run:
            plan = crew_plan(
                project_root,
                current_capability=capability,
                current_agent=_agent_for(project_root),
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
        result = crew_apply(
            project_root,
            current_capability=capability,
            current_agent=_agent_for(project_root),
        )
    except ValueError as exc:
        from userperson import UserpersonError

        if isinstance(exc, UserpersonError):
            _emit(
                {
                    "ok": False,
                    "code": exc.code,
                    "scope": exc.scope,
                    "detail": exc.detail,
                },
                as_json,
            )
            return 1
        raise
    payload = result.to_dict()
    payload.update(_crew_liveness(project_root, result, capability=capability, dry_run=dry_run))
    _emit(payload, as_json)
    return 0 if result.ok else 1


def _crew_liveness(
    project_root: Path, result: object, *, capability: str | None, dry_run: bool
) -> dict:
    """T-1159: cross-invocation liveness for actionable crew carriers.

    An actionable carrier (one that carries `action_fingerprint`: the
    CREW_BLOCKED routing carrier and the RUN_ROLE-style `CREW_ACTION` handback)
    is recorded in a rebuildable `.saipen/cache/` projection. The SAME
    fingerprint twice in a row means the previous actionable answer produced
    NO qualifying state change -- reported as CREW_STALLED instead of being
    silently re-printed forever. Any carrier without a fingerprint is engine
    progress (a mechanical stage executed, or the circuit finished) and clears
    the projection. Read-only sessions and --dry-run never write it.
    """
    if dry_run or capability == "read-only":
        return {}
    from saipen_engine.liveness import clear as liveness_clear
    from saipen_engine.liveness import record_actionable

    data = getattr(result, "data", None) or {}
    fingerprint = data.get("action_fingerprint")
    if not fingerprint:
        liveness_clear(project_root)
        return {}
    verdict = record_actionable(project_root, str(fingerprint))
    if verdict["stalled"]:
        return {
            "liveness": {
                "stalled": True,
                "stall_repeats": verdict["stall_repeats"],
                "verdict": "CREW_STALLED",
                "detail": (
                    "the same actionable crew state was returned again with no "
                    "qualifying state change since the previous identical "
                    "carrier; this is an execution/conformance failure, not a "
                    "user-action requirement -- do not poll"
                ),
            }
        }
    return {}


def _exact_no_args(command: str, args: list[str], as_json: bool) -> int | None:
    """Fail a closed zero-argument command grammar before its handler runs."""
    if not args:
        return None
    _emit(
        {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"{command} accepts no arguments; surplus: {' '.join(args)}",
        },
        as_json,
    )
    return 2


def _continue(
    project_root: Path,
    args: list[str],
    as_json: bool,
    dry_run: bool,
    *,
    shortcut: bool = False,
) -> int:
    """Resume the persisted execution intent through the canonical router.

    Goal resumes its existing objective (and reauthorizes only a tripped
    safety valve), converge keeps its durable target, and normal enters the
    plain ``done`` convergence contract. This command deliberately does not
    call the crew executor: crew is only one possible persisted converge
    target and is routed by ``route_next`` when that target actually owns the
    run.
    """
    if args:
        detail = (
            "Use: gg <objective>"
            if shortcut
            else "continue accepts no positional arguments; surplus: " + " ".join(args)
        )
        if shortcut and not as_json:
            # CORE section 1.10 owns this exact shortcut response. Do not
            # decorate it with the generic REFUSE envelope.
            print(detail)
        else:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": detail}, as_json)
        return 2

    state_path = _state_path(project_root)
    if not state_path.is_file():
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT"}, as_json)
        return 3
    state, state_error = parse_state_or_error(codec.read_doc(state_path))
    if state_error:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"state-malformed: {state_error}",
            },
            as_json,
        )
        return 1

    execution_intent = state.get("execution_intent") or "normal"
    actor = _agent_for(project_root)
    if execution_intent == "normal":
        from saipen_engine.operations import set_converge_intent

        result = set_converge_intent(
            project_root,
            actor,
            "done",
            dry_run=dry_run,
            required_source_intent="normal",
        )
        if dry_run or not result.ok:
            payload = result.to_dict()
            payload["dry_run"] = dry_run
            if result.ok:
                payload.update(
                    {
                        "execution_intent": "converge",
                        "converge_target": "done",
                    }
                )
            _emit(payload, as_json)
            return 0 if result.ok else 1
        return _next_action(project_root, as_json)

    if execution_intent == "goal":
        waves = state.get("goal_waves") or 0
        tickets = state.get("goal_tickets") or 0
        if waves >= 3 or tickets >= 20:
            from saipen_engine.operations import reauthorize_valve

            result = reauthorize_valve(project_root, actor, dry_run=dry_run)
            if dry_run or not result.ok:
                payload = result.to_dict()
                payload["dry_run"] = dry_run
                if result.ok:
                    payload.update(
                        {
                            "execution_intent": "goal",
                            "goal_waves": 0,
                            "goal_tickets": 0,
                        }
                    )
                _emit(payload, as_json)
                return 0 if result.ok else 1

    # Goal (untripped or freshly reauthorized) and converge both derive the
    # next action from the same STATE/BOARD/complete-LOG snapshot as `next`.
    return _next_action(project_root, as_json)


def _source(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:
    """T-1162: lossless source receipts.

    Subcommands:
      capture           capture a large audit/instruction verbatim (mutating)
      status <SRC>      read-only projection (identity, work, coverage)
      show <SRC>        forensic body retrieval (active or archived)
      recover           read-only orphan-receipt crash diagnostic
      req <SRC> <RID> <class> <text...>   add a normalized requirement
      disp <SRC> <RID> <DISPOSITION> [--work T-x] [--evidence E-y]
      close <SRC>       close ONLY when coverage is terminal (mutating)
      archive <SRC>     move a CLOSED receipt to cold storage (mutating)
      purge <SRC>       hard purge, tombstone retained (mutating, explicit)

    SOURCE BODY IS DATA: captured text is never routed as a command.
    """
    from saipen_engine import intake

    if not args:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "source needs a subcommand: capture|status|show|req|"
                "disp|close|archive|purge|recover",
            },
            as_json,
        )
        return 2
    action = args[0]
    rest = args[1:]
    if action in ("capture", "close", "archive", "purge", "req", "disp"):
        if dry_run:
            _emit(
                {
                    "ok": True,
                    "code": "SOURCE_DRY_RUN",
                    "action": action,
                    "detail": "no writes performed",
                },
                as_json,
            )
            return 0
        if _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)

    if action == "capture":
        # Body from --file, stdin (piped), or positional args. Recognized
        # flags are removed wherever they appear; `--` makes all following
        # tokens opaque body data.
        transport_transform = "none"
        kind = "user_instruction"
        work = None
        amends = None
        file_path = None
        body_tokens = []
        opaque = False
        i = 0
        while i < len(rest):
            token = rest[i]
            if opaque:
                body_tokens.append(token)
                i += 1
                continue
            if token == "--":
                opaque = True
                i += 1
                continue
            if token in ("--file", "--kind", "--work", "--amends"):
                if i + 1 >= len(rest):
                    _emit(
                        {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": f"{token} needs a value",
                        },
                        as_json,
                    )
                    return 2
                value = rest[i + 1]
                if token == "--file":
                    file_path = value
                elif token == "--kind":
                    kind = value
                elif token == "--work":
                    work = value
                else:
                    amends = value
                i += 2
                continue
            if token.startswith("--"):
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"unknown flag {token!r}",
                    },
                    as_json,
                )
                return 2
            body_tokens.append(token)
            i += 1
        if file_path and body_tokens:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": ("source capture accepts either --file or body text, not both"),
                },
                as_json,
            )
            return 2
        if file_path:
            try:
                body = Path(file_path).read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"cannot read file: {exc}",
                    },
                    as_json,
                )
                return 1
        else:
            if not body_tokens and not sys.stdin.isatty():
                try:
                    body = sys.stdin.buffer.read().decode("utf-8")
                except UnicodeDecodeError as exc:
                    _emit(
                        {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": f"stdin is not UTF-8: {exc}",
                        },
                        as_json,
                    )
                    return 1
            elif body_tokens:
                body = " ".join(body_tokens)
                transport_transform = "argv_join_spaces"
            else:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": ("source capture needs a body (args, --file, or piped stdin)"),
                    },
                    as_json,
                )
                return 2
        result = intake.capture(
            project_root,
            body,
            source_kind=kind,
            work=work,
            amends=amends,
            transport_transform=transport_transform,
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1

    if action == "status":
        if len(rest) != 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "source status needs <SRC-ID>",
                },
                as_json,
            )
            return 2
        result = intake.status(project_root, rest[0])
        _emit(result, as_json)
        return 0 if result.get("ok") else 1

    if action == "recover":
        if rest:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "source recover accepts no arguments",
                },
                as_json,
            )
            return 2
        _emit(intake.recover_orphans(project_root), as_json)
        return 0

    if action == "show":
        if len(rest) != 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "source show needs <SRC-ID>",
                },
                as_json,
            )
            return 2
        result = intake.read_body(project_root, rest[0])
        if as_json:
            _emit(result, True)
            return 0 if result.get("ok") else 1
        if not result.get("ok"):
            _emit(result, as_json)
            return 1
        print(result["body"])
        return 0

    if action == "req":
        if len(rest) < 4:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "source req needs <SRC> <RID> <class> <text...>",
                },
                as_json,
            )
            return 2
        receipt_id, rid, clause_class = rest[0], rest[1], rest[2]
        text = " ".join(rest[3:])
        result = intake.add_requirement(
            project_root,
            receipt_id,
            rid=rid,
            text=text,
            clause_class=clause_class,
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1

    if action == "disp":
        if len(rest) < 3:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": (
                        "source disp needs <SRC> <RID> <DISPOSITION> [--work T-x] [--evidence E-y]"
                    ),
                },
                as_json,
            )
            return 2
        receipt_id, rid, disposition = rest[0], rest[1], rest[2]
        work = evidence = verification = None
        i = 3
        while i < len(rest):
            if rest[i] == "--work" and i + 1 < len(rest):
                work = rest[i + 1]
                i += 2
            elif rest[i] == "--evidence" and i + 1 < len(rest):
                evidence = rest[i + 1]
                i += 2
            elif rest[i] == "--verification" and i + 1 < len(rest):
                verification = rest[i + 1]
                i += 2
            else:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"unknown flag {rest[i]!r}",
                    },
                    as_json,
                )
                return 2
        result = intake.set_disposition(
            project_root,
            receipt_id,
            rid,
            disposition,
            work=work,
            evidence=evidence,
            verification=verification,
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1

    if action == "close":
        if len(rest) != 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "source close needs <SRC-ID>",
                },
                as_json,
            )
            return 2
        result = intake.close_receipt(project_root, rest[0])
        _emit(result, as_json)
        return 0 if result.get("ok") else 1

    if action == "archive":
        if len(rest) != 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "source archive needs <SRC-ID>",
                },
                as_json,
            )
            return 2
        result = intake.archive_receipt(project_root, rest[0])
        _emit(result, as_json)
        return 0 if result.get("ok") else 1

    if action == "purge":
        if len(rest) != 2 or rest[1] != "--confirm":
            _emit(
                {
                    "ok": False,
                    "code": "CONFIRMATION_REQUIRED",
                    "detail": "source purge needs <SRC-ID> --confirm",
                },
                as_json,
            )
            return 2
        result = intake.purge_receipt(project_root, rest[0])
        _emit(result, as_json)
        return 0 if result.get("ok") else 1

    _emit(
        {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"unknown source subcommand {action!r}",
        },
        as_json,
    )
    return 2


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


def _attempt(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:
    """saipen attempt open|close (T-1148, journaled Work/Attempt lifecycle)."""
    from saipen_engine.attempt import RESULTS, RESULT_STOP_MATRIX, STOP_REASONS

    if not args or args[0] not in ("open", "close"):
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "attempt needs an action: open | close <RESULT> <STOP> "
                "[--evidence E-1,E-2] [--unknown 'text']",
            },
            as_json,
        )
        return 2
    action = args[0]
    rest = args[1:]
    result = stop = None
    evidence: list[str] = []
    unknown: str | None = None
    if action == "close":
        positional: list[str] = []
        i = 0
        while i < len(rest):
            arg = rest[i]
            if arg == "--evidence":
                if i + 1 >= len(rest):
                    _emit(
                        {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": "dangling --evidence option",
                        },
                        as_json,
                    )
                    return 2
                evidence = [e.strip() for e in rest[i + 1].split(",") if e.strip()]
                i += 2
            elif arg == "--unknown":
                if i + 1 >= len(rest):
                    _emit(
                        {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": "dangling --unknown option",
                        },
                        as_json,
                    )
                    return 2
                unknown = rest[i + 1]
                i += 2
            elif arg.startswith("--"):
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"unknown option {arg}",
                    },
                    as_json,
                )
                return 2
            else:
                positional.append(arg)
                i += 1
        if len(positional) != 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "attempt close takes exactly <RESULT> <STOP> "
                    f"(surplus/missing: {' '.join(positional)})",
                },
                as_json,
            )
            return 2
        result, stop = positional
    elif rest:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"attempt open accepts no arguments; surplus: {' '.join(rest)}",
            },
            as_json,
        )
        return 2

    # Fail fast on the closed vocabularies BEFORE any capability/handover work,
    # so a typo'd result never burns an op_id or a handover DEC.
    if action == "close":
        if result not in RESULTS:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"result {result!r} outside the closed vocabulary "
                    f"{'|'.join(RESULTS)}",
                },
                as_json,
            )
            return 2
        if stop not in STOP_REASONS:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"stop reason {stop!r} outside the closed vocabulary "
                    f"{'|'.join(STOP_REASONS)}",
                },
                as_json,
            )
            return 2
        if stop not in RESULT_STOP_MATRIX[result]:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"result {result} cannot pair with stop {stop}; "
                    f"allowed stops: {'|'.join(RESULT_STOP_MATRIX[result])}",
                },
                as_json,
            )
            return 2

    if not dry_run and _negotiate_capability(project_root) == "read-only":
        return _capability_refusal(as_json)
    _ho = _ensure_handover(project_root, as_json, dry_run)
    if _ho is not None:
        return _ho
    from saipen_engine.operations import attempt_lifecycle

    out = attempt_lifecycle(
        project_root,
        _agent_for(project_root),
        action,
        result=result,
        stop=stop,
        evidence=evidence or None,
        unknown=unknown,
        dry_run=dry_run,
    )
    payload = out.to_dict() if hasattr(out, "to_dict") else dict(out)
    _emit(payload, as_json)
    return 0 if payload.get("ok") else 1


def _brief(project_root: Path, as_json: bool) -> int:
    """saipen brief (T-1148): derived cold-handoff projection. Read-only."""
    from saipen_engine.context import brief_projection
    from saipen_engine.log import HistoryOwnershipError

    try:
        result = brief_projection(project_root)
    except (HistoryOwnershipError, OSError) as exc:
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"history-ownership: {type(exc).__name__}: {exc}",
            },
            as_json,
        )
        return 1
    if not result.ok:
        _emit(result.to_dict(), as_json)
        return 1
    if as_json:
        _emit(result.get("json"), as_json)
    else:
        print(result.get("surface", ""), end="")
    return 0


def _userperson_scope(args: list[str]) -> tuple[str, list[str], str | None]:
    """Extract one USERPERSON scope regardless of flag position."""
    flags = [item for item in args if item in ("--project", "--global", "--effective")]
    unique = set(flags)
    if len(flags) != len(unique) or len(unique) > 1:
        return "", args, "choose exactly one of --project, --global, or --effective"
    scope = flags[0][2:] if flags else "project"
    return scope, [item for item in args if item not in unique], None


def _userperson(project_root: Path | None, args: list[str], as_json: bool, dry_run: bool) -> int:
    """USERPERSON project/global/effective management."""
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
        UserpersonError,
        effective_profile,
        load_global_profile,
        load_project_profile,
        merge_profile,
        mutate_global_profile,
        profile_fingerprint,
        remove_preference,
        render_profile,
        reset_profile,
        write_profile,
    )

    action = args[0]
    scope, clean_args, scope_error = _userperson_scope(args[1:])
    if scope_error:
        _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": scope_error}, as_json)
        return 2
    args = [action, *clean_args]
    if scope == "effective" and action != "show":
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "--effective is read-only and valid only with userperson show",
            },
            as_json,
        )
        return 2
    if scope in ("project", "effective") and project_root is None:
        _emit(
            {
                "ok": False,
                "code": "NOT_SAIPEN_PROJECT",
                "detail": f"userperson --{scope} requires a bound SAIPEN project",
            },
            as_json,
        )
        return 3

    try:
        if scope == "effective":
            if len(args) != 1:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "userperson show --effective accepts no other arguments",
                    },
                    as_json,
                )
                return 2
            effective = effective_profile(project_root)
            payload = {
                "ok": True,
                "code": "SHOW",
                "scope": "effective",
                "active": effective["active"],
                "global": effective["global"],
                "project": effective["project"],
                "effective_fingerprint": effective["effective_fingerprint"],
                "preferences": effective["preferences"],
            }
            if as_json:
                _emit(payload, True)
            else:
                print("USERPERSON scope: effective")
                print(f"active: {str(effective['active']).lower()}")
                print(f"effective_fingerprint: {effective['effective_fingerprint']}")
                for preference in effective["preferences"]:
                    print(
                        f"- [{preference['category']}] {preference['text']} "
                        f"(source: {preference['source']})"
                    )
            return 0
        source = load_global_profile() if scope == "global" else load_project_profile(project_root)
    except UserpersonError as exc:
        _emit(
            {
                "ok": False,
                "code": exc.code,
                "scope": exc.scope,
                "detail": exc.detail,
            },
            as_json,
        )
        return 1
    current_text = source["text"]

    if action == "show":
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"userperson show accepts no arguments; surplus: {' '.join(args[1:])}",  # noqa: E501
                },
                as_json,
            )
            return 2
        if as_json:
            _emit(
                {
                    "ok": True,
                    "code": "SHOW" if source["present"] else "EMPTY",
                    "scope": scope,
                    "present": source["present"],
                    "fingerprint": source["fingerprint"],
                    "preferences": source["preferences"],
                },
                as_json,
            )
        else:
            print(f"USERPERSON scope: {scope}")
            if current_text:
                from userperson import _redact_credentials

                print(_redact_credentials(current_text), end="")
        return 0

    if action == "reset":
        surplus = [a for a in args[1:] if a != "--confirm"]
        if surplus:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"userperson reset accepts only --confirm; surplus: {' '.join(surplus)}",  # noqa: E501
                },
                as_json,
            )
            return 2
        if not source["present"]:
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
            _emit(
                {"ok": True, "code": "RESET", "scope": scope, "dry_run": True},
                as_json,
            )
            return 0
        if scope == "global":
            result = mutate_global_profile("reset")
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        if _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
        # CORE says reset DELETES the profile; absence is the canonical OFF
        # state. One journaled delete_file target (real before_hash, empty
        # after_hash) -- NO post-commit unlink, so a crash between COMMIT and
        # unlink can never leave a state recovery cannot complete (T-1003
        # operational integrity). Recovery COMMITTED always means absent.
        result = reset_profile(project_root, _agent_for(project_root))
        if result.get("ok"):
            result["code"] = "RESET"
            result["scope"] = "project"
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
            if args[idx] == "--category":
                if idx + 1 >= len(args) or args[idx + 1].startswith("--"):
                    _emit(
                        {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": "--category needs a non-option value",
                        },
                        as_json,
                    )
                    return 2
                category = args[idx + 1]
                category_supplied = True
                idx += 2
            elif args[idx].startswith("--"):
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": f"unknown userperson option {args[idx]!r}",
                    },
                    as_json,
                )
                return 2
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
        current = source["preferences"]
        if scope == "global" and action == "remove" and not source["present"]:
            _emit(
                {"ok": True, "code": "UNCHANGED", "scope": "global"},
                as_json,
            )
            return 0
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
            _emit({"ok": True, "code": "UNCHANGED", "scope": scope}, as_json)
            return 0
        if dry_run:
            _emit(
                {
                    "ok": True,
                    "code": "PREFERENCE_PLAN",
                    "action": action,
                    "text": text,
                    "category": category if action == "add" else None,
                    "scope": scope,
                    "dry_run": True,
                },
                as_json,
            )
            return 0
        if scope == "global":
            result = mutate_global_profile(
                action,
                text=text,
                category=category if action == "add" or category_supplied else None,
            )
            _emit(result, as_json)
            return 0 if result.get("ok") else 1
        if _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
        result = write_profile(project_root, new_text, _agent_for(project_root))
        result["scope"] = "project"
        if result.get("ok"):
            result["fingerprint"] = profile_fingerprint(new_text)
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
    if _ROUTE_ECHO is not None:
        # Route echo: the invocation resolved through the shared shortcut
        # resolver, so every emitted payload names its canonical route. This
        # is presentation metadata only -- routing itself already happened.
        payload = {**payload, "route": _ROUTE_ECHO}
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
        "route",
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
    milestone = payload.get("milestone")
    if isinstance(milestone, dict) and milestone.get("current"):
        print(f"CHECKPOINT: {milestone['current']}  {milestone.get('label') or ''}".rstrip())
        if milestone.get("parent"):
            parent_label = milestone.get("parent_label") or ""
            print(f"PARENT: {milestone['parent']}  {parent_label}".rstrip())
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
            try:
                roster = manifest.read_text(encoding="utf-8-sig")
                sweep = (
                    (cycle / "SWEEP.md").read_text(encoding="utf-8-sig")
                    if (cycle / "SWEEP.md").is_file()
                    else ""
                )
            except (UnicodeDecodeError, LookupError, OSError):
                rows.append(
                    {
                        "cycle": cycle.name,
                        "cycle_status": "INVALID_CYCLE",
                        "seats": [],
                        "invalid": True,
                        "manifest_errors": ["MANIFEST/SWEEP not valid UTF-8"],
                        "sweep_errors": [],
                    }
                )
                continue
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
                try:
                    report_text = report.read_text(encoding="utf-8-sig") if report.is_file() else ""
                except (UnicodeDecodeError, LookupError, OSError):
                    seats.append(
                        {
                            "seat": seat,
                            "role": roster_role,
                            "visible": "INVALID_REPORT",
                            "report_status": "",
                            "errors": ["report not valid UTF-8"],
                        }
                    )
                    continue
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
    # W2-003 (audit fdc73e06): the improve MUTATORS (submit/complete/
    # cycle-complete/abort) previously ran to completion under `--dry-run`,
    # writing RUN appends, report completion and cycle transitions despite a
    # dry-run session. Only `prepare` and `clean` support dry-run; every other
    # mutation refuses with zero writes. The check runs BEFORE any mutation
    # planning, so the session boundary holds even when a later branch would
    # have failed on its own (fail-first is still zero-write).
    if dry_run and action in ("submit", "complete", "cycle-complete", "abort"):
        _emit(
            {
                "ok": False,
                "code": "DRY_RUN_UNSUPPORTED",
                "detail": f"dry_run not supported for improve mutator {action!r}; "
                "prepare and clean are the only dry-run-capable improve actions",
            },
            as_json,
        )
        return 1
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
        # W2-004 (audit fdc73e06): closed grammar -- exactly
        # `<cycle> <seat> <project>`; surplus tokens are refused, never
        # silently ignored.
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
        if len(args) > 4:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"improve complete takes <cycle> <seat> <project>; "
                    f"unsupported surplus argument {args[4]!r}",
                },
                as_json,
            )
            return 2
        from improve import complete_report as _complete_report
        from improve import resolve_report_path as _resolve_report_path

        report = _resolve_report_path(project_root, args[1], args[2], args[3])
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
        if len(args) > 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"improve cycle-complete takes <cycle_id>; unsupported "
                    f"surplus argument {args[2]!r}",
                },
                as_json,
            )
            return 2
        cycle = cycle_dir(project_root, args[1])
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
        if len(args) > 2:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"improve abort takes <cycle_id>; unsupported "
                    f"surplus argument {args[2]!r}",
                },
                as_json,
            )
            return 2
        from improve import abort_cycle as _abort_cycle

        cycle = cycle_dir(project_root, args[1])
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
    # CORE-002: verify/status/sweep-queue are read-only; bare improve and
    # submit/complete/sweep/cycle-complete/abort/clean mutate and must
    # respect the live read-only capability gate.
    if not dry_run and _command_mutates("improve", args):
        if _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
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
    global _ROUTE_ECHO  # noqa: PLW0603
    # ``main`` is normally one process/one invocation, but tests and embedded
    # callers may invoke it repeatedly. Route evidence belongs to THIS raw
    # command only; never let a previous shortcut label a later direct verb.
    _ROUTE_ECHO = None
    raw_args = list(argv if argv is not None else sys.argv[1:])
    if "--" in raw_args:
        dd_idx = raw_args.index("--")
        before_dashdash = raw_args[:dd_idx]
        after_dashdash = raw_args[dd_idx + 1 :]
    else:
        before_dashdash = raw_args
        after_dashdash = []

    as_json = "--json" in before_dashdash
    if as_json and hasattr(sys.stdout, "reconfigure"):
        # Windows shells frequently inherit an ANSI code page. JSON is UTF-8;
        # a read-only focus result containing a Unicode filename must not die
        # while printing after all reasoning already succeeded.
        with suppress(OSError, ValueError):
            sys.stdout.reconfigure(encoding="utf-8")
    dry_run = "--dry-run" in before_dashdash
    project_root_opt: str | None = None
    runtime_info_opt: str | None = None
    option_error: str | None = None

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
        elif arg == "--runtime-info":
            if i + 1 >= len(before_dashdash) or before_dashdash[i + 1].startswith("--"):
                option_error = "--runtime-info requires a JSON file path"
                i += 1
            elif runtime_info_opt is not None:
                option_error = "--runtime-info may be supplied only once"
                i += 2
            else:
                runtime_info_opt = before_dashdash[i + 1]
                i += 2
        elif arg.startswith("--runtime-info="):
            if runtime_info_opt is not None:
                option_error = "--runtime-info may be supplied only once"
            else:
                runtime_info_opt = arg.split("=", 1)[1]
                if not runtime_info_opt.strip():
                    option_error = "--runtime-info requires a JSON file path"
            i += 1
        else:
            clean_before.append(arg)
            i += 1

    args = clean_before + (["--", *after_dashdash] if "--" in raw_args else [])

    # T-1006: an explicit `--agent <id>` is a GENUINE-HANDOVER request; the
    # bare CLI (override None) inherits the persisted STATE.agent seat. The
    # mandatory old -> new DEC is written by handover_agent before the first
    # mutating command below dispatches.
    global _AGENT_OVERRIDE, _RUNTIME_INFO_OVERRIDE  # noqa: PLW0603
    _AGENT_OVERRIDE = agent_opt.strip() if agent_opt and agent_opt.strip() else None
    _RUNTIME_INFO_OVERRIDE = runtime_info_opt

    if option_error:
        _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": option_error}, as_json)
        return 2

    # CORE-004: bare `saipen` (only global options, no command) is the
    # canonical resume family -- equivalent to `continue`/`cc` (CORE § 1.10).
    # Explicit `-h`/`--help` stays a usage/exit-2 path and does NOT resume.
    if args and args[0] in ("-h", "--help"):
        usage_msg = (
            "usage: saipen (status|next|runtime|recover|claim <T-###>|"
            "transition <PHASE> [T-###] [text]|checkpoint <TAXONOMY> "
            "[T-###] [text]|goal <text>|ticket add <PRIORITY> <text>|ticket "
            "done <T-###>|ticket block <T-###> <reason>|ticket "
            "unblock <T-###> <decision>|improve|improve "
            "status|improve sweep <cycle> <RUN-N/IMP-NNN> <DISPOSITION> "
            "|improve sweep-queue <cycle>|improve submit <cycle> <seat> "
            "<project> <findings.json>|improve complete <cycle> <seat> "
            "<project>|improve verify <cycle>|improve cycle-complete "
            "<cycle>|improve abort <cycle>|improve clean <cycle>|"
            "ship|push|scope <T-###> <path>...|first-publish-confirm "
            "<name> <public|private>|userperson show "
            "[--project|--global|--effective]|userperson add|remove <text> "
            "[--category NAME] [--project|--global]|userperson reset "
            "[--project|--global] --confirm|sub|rebind-home "
            "<candidate-home>|context|attempt open|attempt close <RESULT> "
            "<STOP>|brief|focus [text]|build <directive>|cut <target>|"
            "cut confirm <CUT-ID>|undo|undo confirm <CP-ID> --reason <text>) "
            "[--dry-run] "
            "[--json] [--project-root PATH] [--agent ID] [--runtime-info JSON-FILE]"
        )
        if as_json:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": usage_msg}, as_json)
        else:
            print(usage_msg)
        return 2

    # Global USERPERSON belongs to user configuration, not project memory.
    # Dispatch it before project-root resolution so it works from an ordinary
    # directory and never invents/loads STATE, BOARD, LOG, or a project lock.
    if args and args[0] == "userperson" and len(args) >= 2:
        _scope, _clean, _scope_error = _userperson_scope(args[2:])
        if _scope == "global" or _scope_error:
            return _userperson(None, args[1:], as_json, dry_run)

    project_root, root_reason = resolve_project_root(
        Path.cwd().resolve(), explicit=project_root_opt
    )
    if project_root is None:
        _emit({"ok": False, "code": "NOT_SAIPEN_PROJECT", "detail": root_reason}, as_json)
        return 3

    # CORE-004: a genuinely bare invocation (no command after global option
    # parsing) resumes through the same `_continue` path as `continue`/`cc`.
    if not args:
        if _RUNTIME_INFO_OVERRIDE is not None:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "--runtime-info requires the read-only runtime command in Wave 1",
                },
                as_json,
            )
            return 2
        return _continue(
            project_root,
            [],
            as_json,
            dry_run,
            shortcut=False,
        )

    command = args[0]

    if _RUNTIME_INFO_OVERRIDE is not None and command != "runtime":
        _emit(
            {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "Wave-1 --runtime-info is valid only with the read-only runtime command",
            },
            as_json,
        )
        return 2

    # CORE § 1.10 (Cyrillic-twin incident): whole-message shortcut resolution
    # is MECHANICAL and happens FIRST -- before any dispatch branch, before
    # any conversational interpretation. The raw token is normalized through
    # the ONE shared engine resolver: Unicode-CODEPOINT substitution, never
    # keyboard-position substitution. Cyrillic double-es normalizes to Latin
    # "cc" (CONTINUE); it can never become Latin "ss" (STOP), because "s" is
    # not a fold target and no Cyrillic character maps to it, which is also
    # why the ss/sss rows have no Cyrillic twins at all. Dispatch then
    # proceeds exactly as if the Latin row had been typed, and this file
    # deliberately holds no Cyrillic literal, no confusable map and no twin
    # dictionary for the resolver to drift from. A resolver that cannot load
    # CORE.md returns None for everything: every token then fails closed at
    # its own branch or at the unknown-command refusal -- a failed lookup is
    # NEVER guessed into a command.
    _canonical_shortcut = resolve_shortcut(command, table=load_shortcut_table(PROTOCOL_DIR))
    if _canonical_shortcut is not None:
        args = [_canonical_shortcut, *args[1:]]
        command = _canonical_shortcut
        _ROUTE_ECHO = _canonical_shortcut

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
    if command == "runtime":
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "runtime accepts no command arguments; surplus: "
                    + " ".join(args[1:]),
                },
                as_json,
            )
            return 2
        return _runtime(project_root, as_json)
    if command == "permissions":
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "permissions accepts no arguments; surplus: " + " ".join(args[1:]),
                },
                as_json,
            )
            return 2
        return _permissions(project_root, as_json)
    if command == "explain-next":
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "explain-next accepts no arguments; surplus: " + " ".join(args[1:]),
                },
                as_json,
            )
            return 2
        return _explain_next(project_root, as_json)
    if command == "sss":
        # CORE § 1.10: `sss` routes to read-only status -- the exact same
        # surface as `status`, reached through the shared normalization above
        # for its Cyrillic twin. Never a write, never a phase change.
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"sss accepts no arguments; surplus: {' '.join(args[1:])}",
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
    if command in ("focus", "ff"):
        from saipen_engine.controls import focus_projection

        result = focus_projection(project_root, " ".join(args[1:]))
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command in ("build", "vv"):
        if len(args) < 2 or not " ".join(args[1:]).strip():
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "Use: vv <build directive>",
                },
                as_json,
            )
            return 2
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        from saipen_engine.controls import directive_entry

        result = directive_entry(
            project_root,
            _agent_for(project_root),
            " ".join(args[1:]),
            kind="build",
            dry_run=dry_run,
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command in ("cut", "xx"):
        from saipen_engine.controls import confirm_cut, cut_preview, decode_agent_plan

        rest = args[1:]
        if not rest:
            _emit(
                {"ok": False, "code": "VALIDATION_FAILED", "detail": "Use: xx <cut target>"},
                as_json,
            )
            return 2
        if rest[0] != "confirm":
            result = cut_preview(project_root, " ".join(rest))
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
        if len(rest) < 2 or not rest[1].startswith("CUT-"):
            _emit(
                {
                    "ok": False,
                    "code": "DESTRUCTIVE_CONFIRMATION_REQUIRED",
                    "detail": "Use: xx confirm <CUT-ID>",
                },
                as_json,
            )
            return 2
        # The user-facing form stays `xx confirm CUT-ID`.  Fuzzy impact
        # analysis belongs to the agent, which transports its exact resolved
        # plan after `--`; preview itself wrote nothing and held no lock.
        if "--" not in rest:
            _emit(
                {
                    "ok": False,
                    "code": "DESTRUCTIVE_CONFIRMATION_REQUIRED",
                    "detail": (
                        "CUT-ID recognized; agent-resolved impact plan is not "
                        "present in this session"
                    ),
                    "cut_id": rest[1],
                },
                as_json,
            )
            return 1
        marker = rest.index("--")
        if marker != 2 or len(rest) != 4 or len(after_dashdash) != 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "mechanical cut confirmation needs one encoded plan after --",
                },
                as_json,
            )
            return 2
        try:
            plan = decode_agent_plan(rest[3])
        except ValueError as exc:
            _emit({"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}, as_json)
            return 2
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        result = confirm_cut(
            project_root,
            _agent_for(project_root),
            rest[1],
            plan,
            dry_run=dry_run,
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command in ("undo", "zz"):
        from saipen_engine.controls import undo_confirm, undo_preview

        rest = args[1:]
        if not rest:
            result = undo_preview(project_root)
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1
        if rest[0] != "confirm" or len(rest) < 2:
            _emit(
                {
                    "ok": False,
                    "code": "DESTRUCTIVE_CONFIRMATION_REQUIRED",
                    "detail": "Use: zz confirm <CP-ID> --reason <one sentence>",
                },
                as_json,
            )
            return 2
        if "--reason" not in rest[2:]:
            _emit(
                {
                    "ok": False,
                    "code": "DESTRUCTIVE_CONFIRMATION_REQUIRED",
                    "detail": "undo confirmation requires --reason <one sentence>",
                },
                as_json,
            )
            return 2
        reason_at = rest.index("--reason")
        reason = " ".join(rest[reason_at + 1 :]).strip()
        if reason_at != 2 or not reason:
            _emit(
                {
                    "ok": False,
                    "code": "DESTRUCTIVE_CONFIRMATION_REQUIRED",
                    "detail": "undo confirmation requires one bounded reason after --reason",
                },
                as_json,
            )
            return 2
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        result = undo_confirm(
            project_root,
            _agent_for(project_root),
            rest[1],
            reason,
            dry_run=dry_run,
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
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
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
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
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
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
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
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
            if not dry_run and _negotiate_capability(project_root) == "read-only":
                return _capability_refusal(as_json)
            _ho = _ensure_handover(project_root, as_json, dry_run)
            if _ho is not None:
                return _ho
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
            if not dry_run and _negotiate_capability(project_root) == "read-only":
                return _capability_refusal(as_json)
            _ho = _ensure_handover(project_root, as_json, dry_run)
            if _ho is not None:
                return _ho
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
            if not dry_run and _negotiate_capability(project_root) == "read-only":
                return _capability_refusal(as_json)
            _ho = _ensure_handover(project_root, as_json, dry_run)
            if _ho is not None:
                return _ho
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
    if command in ("goal", "gg"):
        if len(args) < 2 or not args[1].strip():
            # CORE-005: bare `goal`/`gg` is zero-write and emits exactly
            # `Use: gg <objective text>` (CORE § 1.10).
            if as_json:
                _emit(
                    {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "Use: gg <objective text>",
                    },
                    as_json,
                )
            else:
                print("Use: gg <objective text>")
            return 2
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
        from saipen_engine.operations import goal_entry

        result = goal_entry(
            project_root, _agent_for(project_root), " ".join(args[1:]), dry_run=dry_run
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
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
                    "detail": f"rebind-home takes <candidate-home-path>; surplus: {' '.join(args[2:])}",  # noqa: E501
                },
                as_json,
            )
            return 2
        from saipen_engine.operations import rebind_saipen_home

        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
        result = rebind_saipen_home(
            project_root, _agent_for(project_root), args[1], dry_run=dry_run
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1
    if command == "crew":
        return _crew(project_root, args[1:], as_json, dry_run)
    if command == "context":
        return _context(project_root, args[1:], as_json, dry_run)
    if command == "attempt":
        return _attempt(project_root, args[1:], as_json, dry_run)
    if command == "source":
        try:
            return _source(project_root, args[1:], as_json, dry_run)
        except (OSError, PermissionError, ValueError) as exc:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"source receipt validation: {exc}",
                },
                as_json,
            )
            return 1
    if command == "brief":
        surplus = [a for a in args[1:] if a != "--json"]
        if surplus:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"brief accepts no arguments; surplus: {' '.join(surplus)}",
                },
                as_json,
            )
            return 2
        return _brief(project_root, as_json)
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

        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
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

        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
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
        result = execute_release(project_root, plan)
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    # ── Autonomous command closure (SAIPEN intent handlers) ────────
    # qq/ee/qqq/eee are protocol semantic operations, not CLI aliases.

    # AUTO-003: CORE section 1.10 phase-trigger verbs. These MUST be
    # recognized as canonical commands, never rejected as "unknown command"
    # which would cause a weak model to improvise a destructive substitute
    # (e.g. `saipen clean` -> `sub clean saihunt`). Each verb routes to the
    # canonical phase trigger (transition_phase / dedicated semantic).
    _PHASE_VERBS = frozenset({"clean", "hunt", "markhunt", "translate", "validate"})
    # CORE § 1.10 repeated-letter rows routing to phase triggers. They are
    # the SAME transitions as the spelled-out verbs -- identical gates,
    # identical writes -- reached through the shared shortcut normalization.
    _SHORTCUT_PHASE_TRIGGERS = {"hh": "HUNT", "aa": "MARKHUNT"}
    if command in _PHASE_VERBS or command in _SHORTCUT_PHASE_TRIGGERS:
        phase = _SHORTCUT_PHASE_TRIGGERS.get(command) or command.upper()
        surplus = args[1:]
        if surplus:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"{command} accepts no arguments; surplus: {' '.join(surplus)}",
                },
                as_json,
            )
            return 2
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
        result = transition_phase(
            project_root,
            phase,
            _agent_for(project_root),
            ticket_id=None,
            event_text="",
            dry_run=dry_run,
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1

    if command in ("plan", "dd"):
        # CORE section 1.10: explicit PLAN trigger; `dd` is the closed shortcut alias.
        # `dd` accepts optional free text exactly like `plan`; destination validates.
        if not dry_run and _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        _ho = _ensure_handover(project_root, as_json, dry_run)
        if _ho is not None:
            return _ho
        text = " ".join(args[1:]) if len(args) > 1 else ""
        result = transition_phase(
            project_root,
            "PLAN",
            _agent_for(project_root),
            ticket_id=None,
            event_text=text,
            dry_run=dry_run,
        )
        _emit(result.to_dict(), as_json)
        return 0 if result.ok else 1

    if command == "qq":
        refused = _exact_no_args(command, args[1:], as_json)
        if refused is not None:
            return refused
        from saipen_engine.intent import ensure_producer_ready

        result = ensure_producer_ready(
            project_root,
            "saiwiki",
            dry_run=dry_run,
            current_capability=_negotiate_capability(project_root),
            current_agent=_agent_for(project_root),
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if command == "prepare":
        invalid_producer = len(args) == 2 and (not args[1].strip() or args[1].startswith("-"))
        if len(args) > 2 or invalid_producer:
            surplus = args[2:] if len(args) > 2 else args[1:]
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "prepare accepts at most one producer name; invalid/surplus: "
                    + " ".join(surplus),
                },
                as_json,
            )
            return 2
        from saipen_engine.intent import ensure_producer_ready

        result = ensure_producer_ready(
            project_root,
            args[1] if len(args) == 2 else "saiwiki",
            dry_run=dry_run,
            current_capability=_negotiate_capability(project_root),
            current_agent=_agent_for(project_root),
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if command in ("ee", "prepare-translate"):
        refused = _exact_no_args(command, args[1:], as_json)
        if refused is not None:
            return refused
        from saipen_engine.intent import ensure_producer_ready

        result = ensure_producer_ready(
            project_root,
            "saitranslate",
            dry_run=dry_run,
            current_capability=_negotiate_capability(project_root),
            current_agent=_agent_for(project_root),
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if command in ("qqq", "ship-wiki"):
        refused = _exact_no_args(command, args[1:], as_json)
        if refused is not None:
            return refused
        from saipen_engine.intent import collect_and_ship_producer

        result = collect_and_ship_producer(
            project_root,
            "saiwiki",
            dry_run=dry_run,
            current_capability=_negotiate_capability(project_root),
            current_agent=_agent_for(project_root),
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if command in ("eee", "ship-translate"):
        refused = _exact_no_args(command, args[1:], as_json)
        if refused is not None:
            return refused
        from saipen_engine.intent import collect_and_ship_producer

        result = collect_and_ship_producer(
            project_root,
            "saitranslate",
            dry_run=dry_run,
            current_capability=_negotiate_capability(project_root),
            current_agent=_agent_for(project_root),
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
    if command == "pp":
        # CORE § 1.10: `pp` routes to exactly `saipen sub spawn saipython`.
        # No extra arguments -- the row is a closed route, not a family.
        refused = _exact_no_args(command, args[1:], as_json)
        if refused is not None:
            return refused
        return _sub(project_root, ["spawn", "saipython"], as_json, dry_run)
    if command in ("sc", "autonomous-crew"):
        return _crew(project_root, args[1:], as_json, dry_run)
    if command in ("cc", "continue"):
        return _continue(
            project_root,
            args[1:],
            as_json,
            dry_run,
            shortcut=command == "cc",
        )
    if command in ("stop", "ss"):
        # CORE § 1.10: `ss` routes to `saipen stop` -- checkpoint, digest, halt.
        # Exact one nonterminal STOP carrier; read-only sessions emit chat lines.
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"stop accepts no arguments; surplus: {' '.join(args[1:])}",
                },
                as_json,
            )
            return 2
        from saipen_engine.operations import stop_checkpoint

        capability = _negotiate_capability(project_root)
        projection_only = dry_run or capability == "read-only"
        result = stop_checkpoint(
            project_root,
            _agent_for(project_root),
            dry_run=projection_only,
        )
        payload = result.to_dict()
        payload["dry_run"] = dry_run
        payload["route"] = command
        if capability == "read-only":
            payload["mode"] = "read-only"
        if result.ok:
            payload["operation_code"] = payload.get("code")
            payload["code"] = "STOP"
            payload["detail"] = (
                "read-only stop projection"
                if capability == "read-only"
                else ("dry-run stop projection" if dry_run else "stop checkpoint committed")
            )
        _emit(payload, as_json)
        return 0 if result.ok else 1
    if command in ("test", "tt"):
        # CORE § 1.10: `tt` routes to `saipen test` -- read-only suite report.
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"test accepts no arguments; surplus: {' '.join(args[1:])}",
                },
                as_json,
            )
            return 2
        from saipen_engine.test_runner import canonical_test_plan, run_canonical_suite

        if dry_run:
            _emit(
                {
                    "ok": True,
                    "code": "TEST_PLAN",
                    "detail": "canonical test families planned; zero suites executed",
                    "families": canonical_test_plan(project_root),
                    "dry_run": True,
                    "route": command,
                },
                as_json,
            )
            return 0
        try:
            report = run_canonical_suite(project_root)
            ok = report["ok"]
            _emit(
                {
                    "ok": ok,
                    "code": "TEST_REPORT",
                    "detail": "canonical test families executed in an isolated copy",
                    "families": report["families"],
                    "route": command,
                },
                as_json,
            )
            return 0 if ok else 1
        except Exception as exc:
            _emit(
                {"ok": False, "code": "TEST_REPORT", "detail": f"test harness error: {exc}"},
                as_json,
            )
            return 1
    if command == "ccc":
        # CORE § 1.10: `ccc` is `saipen continue` with converge_target: ship,
        # then SHIP, then stages J-M. Minimal deterministic entry per Wave 1:
        # validate, checkpoint active work, set converge ship, clear goal counters,
        # write pre-SHIP source marker, return nonterminal carrier.
        if len(args) > 1:
            _emit(
                {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"ccc accepts no arguments; surplus: {' '.join(args[1:])}",
                },
                as_json,
            )
            return 2
        if _negotiate_capability(project_root) == "read-only":
            return _capability_refusal(as_json)
        from saipen_engine.operations import enter_ship_convergence

        result = enter_ship_convergence(
            project_root,
            _agent_for(project_root),
            dry_run=dry_run,
        )
        payload = result.to_dict()
        payload["dry_run"] = dry_run
        if result.ok:
            payload.update(
                {
                    "execution_intent": "converge",
                    "converge_target": "ship",
                    "route": command,
                }
            )
        _emit(payload, as_json)
        return 0 if result.ok else 1
    # CORE § 1.10 fail-closed floor: a token that IS a declared shortcut but
    # has no deterministic executor in this adapter is REFUSED with its exact
    # canonical route named -- never "unknown command" (which invites a weak
    # model to improvise a substitute, the AUTO-003 defect), and never a
    # guessed partial execution. Cyrillic twins are already folded above, so
    # this refusal is identical for a row and its twin by construction.
    _shortcut_table = load_shortcut_table(PROTOCOL_DIR)
    if command in _shortcut_table:
        _emit(
            {
                "ok": False,
                "code": "SHORTCUT_NOT_EXECUTABLE",
                "detail": f"{command} resolves to `{_shortcut_table[command]}` "
                "(CORE § 1.10); this deterministic adapter implements no "
                "executor for that row -- execute the exact row's semantics "
                "at the agent layer, never a guessed substitute",
            },
            as_json,
        )
        return 1
    # T-1159: an unknown command in a project whose `saipen_home` names a
    # DIFFERENT SAIPEN install than the one executing is runtime drift (the
    # observed stale-installed-skill incident), never a bare project error.
    drift = _runtime_drift_payload(project_root, command)
    if drift is not None:
        _emit(drift, as_json)
        if not as_json:
            print("SAIPEN RUNTIME DRIFT")
            print(
                f"Project protocol: {drift['project_protocol']['home']} "
                f"(v{drift['project_protocol']['version']})"
            )
            print(f"Runtime protocol: {drift['runtime']['home']} (v{drift['runtime']['version']})")
            print(f"Command required by project: {command}")
            print("Runtime cannot execute it safely.")
            print(f"Action: {drift['action']}")
        return 2
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

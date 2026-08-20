"""Fast proposed-state validation (NITRO integrity).

Every mutating SAIOPS operation validates its IN-MEMORY proposed result before
the journal is ever PREPARED, and re-runs the cross-file invariants on the live
files after writing before VERIFIED is marked. This module is that check. It is
FAST and deliberate: it covers exactly what SAIOPS can mutate and refuses a
mutation whose proposed state would not survive the release gate.

The full tools/validate.py remains the release/gate proof; this is
transactional safety, not a replacement.
"""

from __future__ import annotations

import re

from . import phases
from .board import board_semantic_errors, parse_board, claim_status, board_graph_errors
from .log import parse_log_line, log_tail_event
from .state import _current_schema_version, is_absolute_home


def _log_errors(log_text: str) -> list[str]:
    errors = []
    seen: set[int] = set()
    parents: set[int] = set()
    prev = None
    for lineno, line in enumerate(log_text.splitlines(), 1):
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        parsed = parse_log_line(line)
        if parsed is None:
            errors.append(f"LOG.md:{lineno} not a legal event line")
            continue
        event = parsed["event"]
        if event in seen:
            errors.append(f"LOG.md:{lineno} duplicate event E-{event}")
        seen.add(event)
        if prev is not None and event != prev + 1:
            errors.append(f"LOG.md:{lineno} E-{event} breaks monotonicity after E-{prev}")
        prev = event
        if parsed["parent"] is not None:
            parents.add(parsed["parent"])
            if parsed["parent"] >= event:
                errors.append(
                    f"LOG.md:{lineno} parent E-{parsed['parent']} is not older than E-{event}"
                )
    return errors



def validate_checkpoint_surface(
    state_text: str,
    board_text: str,
    snap,
    current_agent: str | None = None,
    *,
    _state=None,
    _board=None,
    _state_error=None,
) -> list[str]:
    """Validate the read-only checkpoint surface using the already captured snapshot.
    Used by status/next/context to apply the SAME transactional invariant set before routing.

    PERF-004: ``_state``/``_board``/``_state_error`` let the caller reuse a single
    parse of STATE/BOARD instead of re-parsing them here (``route_next`` now parses
    once and passes the result). When omitted, the surface is parsed from the raw
    text exactly as before, so every external caller keeps the raw-text entry point
    and behavior is unchanged."""
    errors: list[str] = []

    from .floor import state_board_floor, board_floor
    floor_errors = state_board_floor(state_text, board_text) + board_floor(board_text)
    if floor_errors:
        errors.extend(f"FLOOR: {e}" for e in floor_errors)

    from .state import parse_state_or_error

    if _state is not None or _state_error is not None:
        state, state_error = _state, _state_error
    else:
        state, state_error = parse_state_or_error(state_text)
    if state_error:
        errors.append(f"STATE proposed malformed: {state_error}")
        return errors
    missing = [
        k
        for k in (
            "phase",
            "task",
            "next_action",
            "blocker",
            "agent",
            "saipen_version",
            "mode",
            "updated",
        )
        if k not in state
    ]
    for key in missing:
        errors.append(f"STATE proposed missing required field {key}")
    phase = state.get("phase")
    if phase not in phases.VALID_TRANSITIONS and phase not in phases.ANY_FROM:
        errors.append(f"STATE proposed phase {phase!r} outside the enum")
    na = state.get("next_action")
    if isinstance(na, str):
        if na.startswith("PHASE "):
            error = phases.phase_next_action_error(na)
            if error:
                errors.append(f"STATE proposed next_action invalid: {error}")
        else:
            prefixes = ("WAIT:", "saipen ", "RUN:", "RESUME:")
            if not na.startswith(prefixes):
                errors.append(
                    f"STATE proposed next_action {na!r} does not "
                    "start with WAIT:/saipen /PHASE /RUN:/RESUME:"
                )
        subject = state.get("task")
        m = re.match(r"^PHASE\s+([A-Za-z_-]+)(?:\s+(T-\d+))?", na.strip())
        if (
            m
            and m.group(2)
            and subject
            and m.group(2) != subject
            and phase in phases.TICKET_BEARING_PHASES
        ):
            errors.append(f"STATE proposed next_action names {m.group(2)} but task is {subject}")
    intent = state.get("execution_intent")
    if intent == "goal":
        if "goal_waves" not in state or "goal_tickets" not in state:
            errors.append("STATE proposed intent=goal without goal_waves/goal_tickets")
        if "converge_target" in state:
            errors.append("STATE proposed intent=goal with converge_target")
    elif intent == "converge":
        if state.get("converge_target") not in ("done", "ship", "crew"):
            errors.append("STATE proposed intent=converge without target done|ship|crew")
        if "goal_waves" in state or "goal_tickets" in state:
            errors.append("STATE proposed intent=converge with goal counters")
    elif intent in (None, "normal"):
        if "goal_waves" in state or "goal_tickets" in state:
            errors.append("STATE proposed non-goal intent with goal counters")
        if "converge_target" in state:
            errors.append("STATE proposed non-converge intent with converge_target")
    elif intent not in (None, "normal", "converge"):
        errors.append(f"STATE proposed execution_intent {intent!r} outside normal|goal|converge")
    if state.get("phase") and state.get("transition_from") and state.get("phase") != "INIT":
        tf = state.get("transition_from")
    if tf not in phases.VALID_TRANSITIONS and tf not in phases.ANY_FROM:
        errors.append(f"STATE proposed transition_from {tf!r} outside the enum")

    board = _board if _board is not None else parse_board(board_text)
    errors.extend(f"BOARD: {e}" for e in board["errors"])
    tickets = board["tickets"]
    for ge in board_graph_errors(tickets):
        errors.append(f"BOARD: {ge}")
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if len(doing) > 1:
        errors.append("BOARD proposed has more than one ## DOING ticket")
    for ticket in tickets.values():
        for semantic in board_semantic_errors(ticket):
            errors.append(f"BOARD proposed {semantic}")
        for need in ticket["needs"]:
            if ticket["section"] == "## DOING" and tickets[need]["section"] != "## DONE":
                errors.append(f"BOARD proposed {ticket['id']} needs {need} which is not DONE")

    from .log import snapshot_contract_errors
    errors.extend(f"LOG: {e}" for e in snapshot_contract_errors(snap.history))

    tail = snap.history.tail
    last_event = state.get("last_event")
    _csv = _current_schema_version(state.get("saipen_home"))
    if _csv is not None and state.get("schema_version") == _csv and tail is not None:
        if last_event is None:
            errors.append(
                "current-schema STATE requires last_event matching the "
                "LOG tail; last_event is absent"
            )
        elif not isinstance(last_event, int) or last_event != tail:
            errors.append(f"STATE proposed last_event {last_event} != LOG tail {tail}")
    elif last_event is not None and tail is not None and last_event != tail:
        errors.append(f"STATE proposed last_event {last_event} != LOG tail {tail}")

    _home = state.get("saipen_home")
    if _csv is not None and state.get("schema_version") == _csv and _home:
        import pathlib
        if not is_absolute_home(str(_home)):
            errors.append(f"current-schema STATE requires absolute saipen_home, got {_home!r}")

    task = state.get("task")
    active = doing[0]["id"] if doing else None
    phase = state.get("phase")
    ticket_bearing = phase in phases.TICKET_BEARING_PHASES

    if ticket_bearing:
        if not active:
            errors.append(
                f"STATE proposed phase {phase} is ticket-bearing but BOARD has no ## DOING ticket"
            )
        if not task or task == "none":
            errors.append(
                f"STATE proposed phase {phase} is ticket-bearing but task is not a real T-###"
            )
        elif active and task != active:
            errors.append(f"STATE proposed task {task} != BOARD DOING {active}")
        na = state.get("next_action")
        if isinstance(na, str):
            m = re.match(r"^PHASE\s+([A-Za-z_-]+)(?:\s+(T-\d+))?", na.strip())
            if m and m.group(2) and active and m.group(2) != active:
                errors.append(
                    f"STATE proposed next_action names "
                    f"{m.group(2)} but the active DOING ticket is "
                    f"{active}"
                )
    else:
        if active:
            _cs = claim_status(doing[0], current_agent or state.get("agent"))
            if _cs in ("SELF", "INVALID"):
                errors.append(
                    f"STATE proposed phase {phase} is not ticket-bearing "
                    "but BOARD has a ## DOING ticket; a DOING ticket "
                    "requires a ticket-bearing phase (a completed "
                    "ticket's execution state must be closed, not "
                    "left in a non-ticket phase)"
                )
        if task and task != "none":
            errors.append(
                f"STATE proposed phase {phase} is not ticket-bearing "
                f"but task is {task!r}; task must be none outside a "
                "ticket-bearing phase"
            )
    return errors


def validate_texts(
    state_text: str, board_text: str, log_text: str, current_agent: str | None = None
) -> list[str]:
    """Validate the proposed STATE/BOARD/LOG texts. Returns every error.

    `current_agent` is the CURRENT-SESSION actor (second-wave P0). Claim
    classification and the active-DOING structural check are judged relative
    to THIS identity, never to persisted STATE.agent -- that field is
    historical last-writer evidence. A session B viewing an A-owned DOING
    under a non-ticket-bearing phase is valid multi-agent state (FOREIGN),
    not the SELF-corruption the check exists to catch. When None (a caller
    that does not know its own identity), the historical value is used for
    backward compatibility; the CLI/adapters always supply the session
    identity."""
    errors: list[str] = []

    from .floor import raw_floor

    floor_errors = raw_floor(state_text, board_text, log_text)
    if floor_errors:
        errors.extend(f"FLOOR: {e}" for e in floor_errors)

    from .state import parse_state_or_error

    state, state_error = parse_state_or_error(state_text)
    if state_error:
        errors.append(f"STATE proposed malformed: {state_error}")
        return errors
    missing = [
        k
        for k in (
            "phase",
            "task",
            "next_action",
            "blocker",
            "agent",
            "saipen_version",
            "mode",
            "updated",
        )
        if k not in state
    ]
    for key in missing:
        errors.append(f"STATE proposed missing required field {key}")
    phase = state.get("phase")
    if phase not in phases.VALID_TRANSITIONS and phase not in phases.ANY_FROM:
        errors.append(f"STATE proposed phase {phase!r} outside the enum")
    na = state.get("next_action")
    if isinstance(na, str):
        if na.startswith("PHASE "):
            error = phases.phase_next_action_error(na)
            if error:
                errors.append(f"STATE proposed next_action invalid: {error}")
        else:
            prefixes = ("WAIT:", "saipen ", "RUN:", "RESUME:")
            if not na.startswith(prefixes):
                errors.append(
                    f"STATE proposed next_action {na!r} does not "
                    "start with WAIT:/saipen /PHASE /RUN:/RESUME:"
                )
        # A PHASE next_action naming a ticket must agree with the active task
        # ONLY in a ticket-bearing phase, where task is the active DOING
        # ticket. In a non-ticket-bearing phase (DONE after closure) task is
        # none and next_action legitimately names the next workable ticket --
        # the router's START projection, not a task-binding violation.
        subject = state.get("task")
        m = re.match(r"^PHASE\s+([A-Za-z_-]+)(?:\s+(T-\d+))?", na.strip())
        if (
            m
            and m.group(2)
            and subject
            and m.group(2) != subject
            and phase in phases.TICKET_BEARING_PHASES
        ):
            errors.append(f"STATE proposed next_action names {m.group(2)} but task is {subject}")
    intent = state.get("execution_intent")
    if intent == "goal":
        if "goal_waves" not in state or "goal_tickets" not in state:
            errors.append("STATE proposed intent=goal without goal_waves/goal_tickets")
        if "converge_target" in state:
            errors.append("STATE proposed intent=goal with converge_target")
    elif intent == "converge":
        if state.get("converge_target") not in ("done", "ship", "crew"):
            errors.append("STATE proposed intent=converge without target done|ship|crew")
        if "goal_waves" in state or "goal_tickets" in state:
            errors.append("STATE proposed intent=converge with goal counters")
    elif intent in (None, "normal"):
        if "goal_waves" in state or "goal_tickets" in state:
            errors.append("STATE proposed non-goal intent with goal counters")
        if "converge_target" in state:
            errors.append("STATE proposed non-converge intent with converge_target")
    elif intent not in (None, "normal", "converge"):
        errors.append(f"STATE proposed execution_intent {intent!r} outside normal|goal|converge")
    if state.get("phase") and state.get("transition_from") and state.get("phase") != "INIT":
        tf = state.get("transition_from")
        if tf not in phases.VALID_TRANSITIONS and tf not in phases.ANY_FROM:
            errors.append(f"STATE proposed transition_from {tf!r} outside the enum")

    board = parse_board(board_text)
    errors.extend(f"BOARD: {e}" for e in board["errors"])
    tickets = board["tickets"]
    # ONE shared DAG primitive (hostile-regression, 4th-wave P1#4): dangling
    # needs: references AND needs: cycles, used here, in validate.py and in the
    # router before Pick Rule evaluation. A cyclic all-TODO graph is corrupt work
    # state, never merely 'no workable ticket'.
    for ge in board_graph_errors(tickets):
        errors.append(f"BOARD: {ge}")
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if len(doing) > 1:
        errors.append("BOARD proposed has more than one ## DOING ticket")
    for ticket in tickets.values():
        # ONE shared BOARD lifecycle invariant set (T-1003): the
        # transactional verifier and the canonical validator must reject the
        # same checkbox/section/evidence mismatches, or an unrelated mutation
        # can COMMIT a board the release gate later rejects.
        for semantic in board_semantic_errors(ticket):
            errors.append(f"BOARD proposed {semantic}")
        for need in ticket["needs"]:
            if ticket["section"] == "## DOING" and tickets[need]["section"] != "## DONE":
                errors.append(f"BOARD proposed {ticket['id']} needs {need} which is not DONE")

    errors.extend(f"LOG: {e}" for e in _log_errors(log_text))

    tail = log_tail_event(log_text)
    last_event = state.get("last_event")
    # Current-schema states (schema_version == the installed schema's
    # x-current-schema-version) MUST carry a last_event that matches the LOG tail
    # when the LOG has events (hostile-regression, P0#2): the cross-file fast gate
    # enforces the same marker the release gate requires, so the two never disagree.
    # Legacy schemas keep their looser handling below.
    _csv = _current_schema_version(state.get("saipen_home"))
    if _csv is not None and state.get("schema_version") == _csv and tail is not None:
        if last_event is None:
            errors.append(
                "current-schema STATE requires last_event matching the "
                "LOG tail; last_event is absent"
            )
        elif not isinstance(last_event, int) or last_event != tail:
            errors.append(f"STATE proposed last_event {last_event} != LOG tail {tail}")
    elif last_event is not None and tail is not None and last_event != tail:
        errors.append(f"STATE proposed last_event {last_event} != LOG tail {tail}")

    _home = state.get("saipen_home")
    if _csv is not None and state.get("schema_version") == _csv and _home:
        import pathlib
        if not is_absolute_home(str(_home)):
            errors.append(f"current-schema STATE requires absolute saipen_home, got {_home!r}")

    # Active-ticket binding (NITRO dogfood III, T-591): the one-way check
    # "BOARD has DOING and STATE has task and they differ" is not a proof of
    # the actual invariant. For every ticket-bearing phase the binding is
    # bidirectional: exactly one BOARD.DOING must exist, STATE.task must be a
    # real T-### equal to it, and next_action's ticket subject must equal it.
    # Any ticket-bearing phase with task:none, no DOING, a mismatched task, or
    # a next_action naming a different ticket is structural corruption.
    task = state.get("task")
    active = doing[0]["id"] if doing else None
    phase = state.get("phase")
    ticket_bearing = phase in phases.TICKET_BEARING_PHASES

    if ticket_bearing:
        if not active:
            errors.append(
                f"STATE proposed phase {phase} is ticket-bearing but BOARD has no ## DOING ticket"
            )
        if not task or task == "none":
            errors.append(
                f"STATE proposed phase {phase} is ticket-bearing but task is not a real T-###"
            )
        elif active and task != active:
            errors.append(f"STATE proposed task {task} != BOARD DOING {active}")
        na = state.get("next_action")
        if isinstance(na, str):
            m = re.match(r"^PHASE\s+([A-Za-z_-]+)(?:\s+(T-\d+))?", na.strip())
            if m and m.group(2) and active and m.group(2) != active:
                errors.append(
                    f"STATE proposed next_action names "
                    f"{m.group(2)} but the active DOING ticket is "
                    f"{active}"
                )
    else:
        if active:
            # A DOING ticket that is UNCLAIMED / FOREIGN_STALE / FOREIGN_LIVE is
            # owned by nobody or by another agent; an observer in a non-ticket-
            # bearing phase (e.g. DONE / task:none) is valid multi-agent state and
            # must NOT be rejected here (P0 claim-ownership truth: one classifier
            # decides). Only a SELF or INVALID DOING under a non-ticket-bearing
            # phase is structural corruption.
            _cs = claim_status(doing[0], current_agent or state.get("agent"))
            if _cs in ("SELF", "INVALID"):
                errors.append(
                    f"STATE proposed phase {phase} is not ticket-bearing "
                    "but BOARD has a ## DOING ticket; a DOING ticket "
                    "requires a ticket-bearing phase (a completed "
                    "ticket's execution state must be closed, not "
                    "left in a non-ticket phase)"
                )
        if task and task != "none":
            errors.append(
                f"STATE proposed phase {phase} is not ticket-bearing "
                f"but task is {task!r}; task must be none outside a "
                "ticket-bearing phase"
            )
    return errors


def validate_project(root, current_agent: str | None = None) -> list[str]:
    """Validate the live canonical files (post-write / recovery verification)."""
    errors: list[str] = []
    from pathlib import Path

    root = Path(root)
    from . import codec

    # Encoding is diagnosed before anything is parsed, exactly like the
    # release gate (hostile-regression, P1): a UTF-16 or BOM-carrying
    # checkpoint file is what PowerShell 5.1's Set-Content produces by
    # default, and the consequences differ by tool -- the portable floor
    # matches nothing, a BOM alone breaks `^---` so the frontmatter parses
    # as empty. One named error beats three unrelated symptoms, and a
    # post-write verification must refuse a commit that wrote one.
    for name in ("STATE.md", "BOARD.md", "LOG.md"):
        path = root / ".saipen" / name
        if not path.is_file():
            continue
        enc = codec.encoding_of(path)
        if enc != "utf-8":
            errors.append(
                f".saipen/{name} is {enc}, not plain UTF-8 -- every SAIPEN "
                "tool reads it byte-wise and will fail differently; rewrite "
                "as UTF-8 without a BOM (KNOWLEDGE/traps.md)"
            )
    state = codec.read_doc(root / ".saipen" / "STATE.md")
    board = codec.read_doc(root / ".saipen" / "BOARD.md")
    log = codec.read_doc(root / ".saipen" / "LOG.md")
    errors.extend(validate_texts(state, board, log, current_agent=current_agent))
    # The COMPLETE sealed+active ledger must be internally valid (legal syntax,
    # unique E-IDs, contiguous parent chain, parent existence, order) -- not
    # just the active segment (hostile-regression, P0#2). A void sealed log is
    # what once let a mutation PLAN against a record that did not exist, so the
    # live verification must FAIL it too.
    from .log import history_contract_errors

    errors.extend(f"LOG: {e}" for e in history_contract_errors(root))
    return errors

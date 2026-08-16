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
from .board import board_semantic_errors, parse_board, claim_status
from .log import parse_log_line, log_tail_event
from .state import parse_state


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
            errors.append(f"LOG.md:{lineno} E-{event} breaks monotonicity "
                          f"after E-{prev}")
        prev = event
        if parsed["parent"] is not None:
            parents.add(parsed["parent"])
            if parsed["parent"] >= event:
                errors.append(f"LOG.md:{lineno} parent E-{parsed['parent']} "
                              f"is not older than E-{event}")
    return errors


def validate_texts(state_text: str, board_text: str, log_text: str) -> list[str]:
    """Validate the proposed STATE/BOARD/LOG texts. Returns every error."""
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
    missing = [k for k in ("phase", "task", "next_action", "blocker", "agent",
                           "saipen_version", "mode", "updated")
               if k not in state]
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
                errors.append(f"STATE proposed next_action {na!r} does not "
                              "start with WAIT:/saipen /PHASE /RUN:/RESUME:")
        # A PHASE next_action naming a ticket must agree with the active task
        # ONLY in a ticket-bearing phase, where task is the active DOING
        # ticket. In a non-ticket-bearing phase (DONE after closure) task is
        # none and next_action legitimately names the next workable ticket --
        # the router's START projection, not a task-binding violation.
        subject = state.get("task")
        m = re.match(r"^PHASE\s+([A-Za-z_-]+)(?:\s+(T-\d+))?", na.strip())
        if (m and m.group(2) and subject and m.group(2) != subject
                and phase in phases.TICKET_BEARING_PHASES):
            errors.append(f"STATE proposed next_action names {m.group(2)} "
                          f"but task is {subject}")
    intent = state.get("execution_intent")
    if intent == "goal":
        if "goal_waves" not in state or "goal_tickets" not in state:
            errors.append("STATE proposed intent=goal without goal_waves/"
                          "goal_tickets")
        if "converge_target" in state:
            errors.append("STATE proposed intent=goal with converge_target")
    elif intent == "converge":
        if state.get("converge_target") not in ("done", "ship", "crew"):
            errors.append("STATE proposed intent=converge without target "
                          "done|ship|crew")
        if "goal_waves" in state or "goal_tickets" in state:
            errors.append("STATE proposed intent=converge with goal counters")
    elif intent in (None, "normal"):
        if "goal_waves" in state or "goal_tickets" in state:
            errors.append("STATE proposed non-goal intent with goal counters")
        if "converge_target" in state:
            errors.append("STATE proposed non-converge intent with "
                          "converge_target")
    elif intent not in (None, "normal", "converge"):
        errors.append(f"STATE proposed execution_intent {intent!r} outside "
                      "normal|goal|converge")
    if state.get("phase") and state.get("transition_from") and state.get(
            "phase") != "INIT":
        tf = state.get("transition_from")
        if tf not in phases.VALID_TRANSITIONS and tf not in phases.ANY_FROM:
            errors.append(f"STATE proposed transition_from {tf!r} outside "
                          "the enum")

    board = parse_board(board_text)
    errors.extend(f"BOARD: {e}" for e in board["errors"])
    tickets = board["tickets"]
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
            if need not in tickets:
                errors.append(f"BOARD proposed {ticket['id']} needs "
                              f"nonexistent {need}")
            elif (ticket["section"] == "## DOING"
                  and tickets[need]["section"] != "## DONE"):
                errors.append(f"BOARD proposed {ticket['id']} needs {need} "
                              f"which is not DONE")

    errors.extend(f"LOG: {e}" for e in _log_errors(log_text))

    tail = log_tail_event(log_text)
    last_event = state.get("last_event")
    if last_event is not None and tail is not None and last_event != tail:
        errors.append(f"STATE proposed last_event {last_event} != LOG tail "
                      f"{tail}")

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
            errors.append(f"STATE proposed phase {phase} is ticket-bearing "
                          "but BOARD has no ## DOING ticket")
        if not task or task == "none":
            errors.append(f"STATE proposed phase {phase} is ticket-bearing "
                          "but task is not a real T-###")
        elif active and task != active:
            errors.append(f"STATE proposed task {task} != BOARD DOING "
                          f"{active}")
        na = state.get("next_action")
        if isinstance(na, str):
            m = re.match(r"^PHASE\s+([A-Za-z_-]+)(?:\s+(T-\d+))?",
                         na.strip())
            if m and m.group(2) and active and m.group(2) != active:
                errors.append(f"STATE proposed next_action names "
                              f"{m.group(2)} but the active DOING ticket is "
                              f"{active}")
    else:
        if active:
            # A DOING ticket that is UNCLAIMED / FOREIGN_STALE / FOREIGN_LIVE is
            # owned by nobody or by another agent; an observer in a non-ticket-
            # bearing phase (e.g. DONE / task:none) is valid multi-agent state and
            # must NOT be rejected here (P0 claim-ownership truth: one classifier
            # decides). Only a SELF or INVALID DOING under a non-ticket-bearing
            # phase is structural corruption.
            _cs = claim_status(doing[0], state.get("agent"))
            if _cs in ("SELF", "INVALID"):
                errors.append(
                    f"STATE proposed phase {phase} is not ticket-bearing "
                    "but BOARD has a ## DOING ticket; a DOING ticket "
                    "requires a ticket-bearing phase (a completed "
                    "ticket's execution state must be closed, not "
                    "left in a non-ticket phase)")
        if task and task != "none":
            errors.append(f"STATE proposed phase {phase} is not ticket-bearing "
                          f"but task is {task!r}; task must be none outside a "
                          "ticket-bearing phase")
    return errors


def validate_project(root) -> list[str]:
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
                "as UTF-8 without a BOM (KNOWLEDGE/traps.md)")
    state = codec.read_doc(root / ".saipen" / "STATE.md")
    board = codec.read_doc(root / ".saipen" / "BOARD.md")
    log = codec.read_doc(root / ".saipen" / "LOG.md")
    errors.extend(validate_texts(state, board, log))
    return errors

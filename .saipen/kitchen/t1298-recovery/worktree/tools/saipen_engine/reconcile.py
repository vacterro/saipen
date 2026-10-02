"""Protocol-state reconciliation (CORE-002).

CORE.md section 1.2 / OPS.md section 357-370 make BOARD checkbox presentation
*and* the deterministic STATE metadata -- `last_event`, the goal counters,
`schema_version` and `style_contract` -- reconciliation-owned. Recovery and
continuation share this reconciliation before validation, and `CLEAN` is a
statement about that WHOLE owned surface: OPS forbids reporting CLEAN while
repairable drift remains.

The first implementation of this module repaired BOARD checkboxes only, under a
direct `_atomic_write`, and returned `CLEAN` the moment no checkbox differed. A
STATE whose `last_event` disagreed with the LOG tail was therefore certified
clean and the very next `continue` failed validation. This module now:

  * derives the complete repair set from the authoritative BOARD/LOG/current
    intent, covering every reconciliation-owned field;
  * computes all target bytes first and runs the SAME complete-surface fast
    invariants the post-write gate uses against the *proposal*;
  * commits LOG + BOARD + STATE through one journaled OperationPlan/CAS
    transaction under the writer lock, with a DEC trace for the repair;
  * renders the identical plan under `dry_run` with zero writes.

There is deliberately no BOARD-only write path left: a partial repair that
reports CLEAN is the exact failure this module exists to prevent.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .board import parse_board

_SECTION_BOX = {
    "## TODO": " ",
    "## BLOCKED": " ",
    "## DOING": "/",
    "## DONE": "x",
}
_TICKET_BOX_RE = re.compile(r"^(\s*- \[)([ x/])(\])")

# CORE section 1.5: two LOG lines are goal MARKERS -- the `DEC: goal pivot`
# line a new objective writes, and the `DEC: goal reauthorized` line section
# 2.4 requires from a re-authorizing `cc`.
_GOAL_MARKER_RE = re.compile(r"^goal (?:pivot|reauthorized)\b")
# CORE section 1.5: "Only increments are completion events -- a marker's own
# `N->0` records the reset, it is not a wave or a ticket."
_GOAL_INCREMENT_RE = re.compile(r"^goal_(waves|tickets) (\d+)->(\d+)$")

# The STATE keys reconciliation owns, in the order they are reported.
_OWNED_COUNTERS = ("goal_waves", "goal_tickets")


def _checkbox_drifts(board_text: str) -> list[dict]:
    drifts: list[dict] = []
    section = ""
    parsed = parse_board(board_text)
    ticket_section = {
        ticket_id: ticket.get("section", "")
        for ticket_id, ticket in parsed.get("tickets", {}).items()
    }
    for offset, line in enumerate(board_text.splitlines(), 1):
        if line.startswith("## "):
            section = line.strip()
            continue
        match = _TICKET_BOX_RE.match(line)
        if not match or section not in _SECTION_BOX:
            continue
        want = _SECTION_BOX[section]
        if match.group(2) != want:
            tid = re.match(rf"^\s*- \[{re.escape(match.group(2))}\] (T-\d+)", line)
            drifts.append(
                {
                    "line": offset,
                    "section": section,
                    "checkbox": match.group(2),
                    "expected": want,
                    "ticket": tid.group(1) if tid else None,
                    "from_board": ticket_section.get(tid.group(1) if tid else "") == section,
                }
            )
    return drifts


def _apply_checkbox_repairs(board_text: str, drifts: list[dict]) -> str:
    targets = {drift["line"]: drift["expected"] for drift in drifts}
    lines = board_text.splitlines(keepends=True)
    for lineno, box in targets.items():
        lines[lineno - 1] = _TICKET_BOX_RE.sub(rf"\g<1>{box}\g<3>", lines[lineno - 1], count=1)
    return "".join(lines)


def _derived_goal_counters(events) -> dict[str, int]:
    """Rebuild the goal counters exactly as CORE section 1.5 Recovery requires.

    The rebuilt count is the NUMBER OF INCREMENT EVENTS SINCE THE NEWEST GOAL
    MARKER -- not the `to` value of the last bump line. Both halves matter:

      * Two lines are markers, not one: the `DEC: goal pivot` line and the
        `DEC: goal reauthorized` line. Counting from the pivot alone rebuilds
        every bump a later re-authorization already cancelled, handing the run
        back a tripped valve the human cleared.
      * Only increments count. A marker's own `N->0` records the reset; it is
        not a wave or a ticket.

    The pivot line may have been sealed away if enough LOG activity happened
    since, so this walks the COMPLETE history the caller supplies (sealed
    segments plus the active LOG) -- the same walk section 1.5 mandates rather
    than the active file alone.
    """
    counts = {"goal_waves": 0, "goal_tickets": 0}
    for event in events:
        if event.get("taxonomy") != "DEC":
            continue
        text = (event.get("text") or "").strip()
        if _GOAL_MARKER_RE.match(text):
            counts = {"goal_waves": 0, "goal_tickets": 0}
            continue
        match = _GOAL_INCREMENT_RE.match(text)
        if match and int(match.group(3)) > int(match.group(2)):
            counts["goal_" + match.group(1)] += 1
    return counts


def _state_marker_repairs(state: dict, tail: int | None) -> list[dict]:
    """Repairs for the reconciliation-owned STATE freshness/schema markers."""
    from .state import running_schema_version, running_style_token

    repairs: list[dict] = []
    have = state.get("last_event")
    if tail is not None and have != tail:
        repairs.append(
            {
                "field": "last_event",
                "from": have,
                "to": tail,
                "surface": "state",
                "reason": "STATE freshness marker must equal the LOG tail (CORE section 1.2)",
            }
        )
    current_schema = running_schema_version()
    token = running_style_token()
    have_schema = state.get("schema_version")
    have_schema_int = (
        have_schema
        if isinstance(have_schema, int) and not isinstance(have_schema, bool)
        else None
    )
    if current_schema is not None and (
        have_schema_int is None or have_schema_int < current_schema
    ):
        repairs.append(
            {
                "field": "schema_version",
                "from": have_schema,
                "to": current_schema,
                "surface": "state",
                "reason": "readable legacy revision must upgrade to the current schema",
            }
        )
    # The style marker is enforced whenever it is present OR whenever the
    # schema moves: a token that disagrees with STYLE.md means the checkpoint
    # was written against a contract that is not the installed one.
    if token and state.get("style_contract") != token and (
        have_schema_int is None or have_schema_int <= (current_schema or have_schema_int)
    ):
        repairs.append(
            {
                "field": "style_contract",
                "from": state.get("style_contract"),
                "to": token,
                "surface": "state",
                "reason": "voice marker must equal the installed STYLE.md boot marker",
            }
        )
    return repairs


_GOAL_WAVES_CAP = 3
_GOAL_TICKETS_CAP = 20


def _state_counter_repairs(state: dict, events) -> list[dict]:
    """Repairs for the goal counters, owned only while the intent is `goal`.

    CORE-001 (audit-all3): the representation is the truth, and any non-equal
    counter must produce a repair or an explicit refusal the validator cannot
    silently ignore.

      * BELOW the rebuilt count -- the section 1.5 crash signature (a bump
        reached the LOG and never STATE). Repaired upward. Doing so can only
        trip the safety valve EARLIER, which section 2.4 calls deliberate
        and conservative.
      * ABOVE the rebuilt count but still BELOW the safety cap -- an ordinary
        ahead mismatch (e.g. derived=0/state=1). Repaired DOWNWARD to the
        canonical evidence.
      * AT or OVER the safety cap while canonical history is lower -- the
        tripped safety valve. NEVER repaired downward (that would silently
        clear a valve the human has not re-authorized) and never certified
        CLEAN: returned as a `refuse` repair the caller turns into an explicit
        non-CLEAN classification requiring the reauthorization path.
      * ABSENT -- initialized from the evidence (including to 0).
    """
    if state.get("execution_intent") != "goal":
        return []
    rebuilt = _derived_goal_counters(events)
    cap = {
        "goal_waves": _GOAL_WAVES_CAP,
        "goal_tickets": _GOAL_TICKETS_CAP,
    }
    repairs: list[dict] = []
    for field in _OWNED_COUNTERS:
        have = state.get(field)
        want = rebuilt.get(field, 0)
        if isinstance(have, bool) or not isinstance(have, int):
            if have is None:
                repairs.append(
                    {
                        "field": field,
                        "from": None,
                        "to": want,
                        "surface": "state",
                        "reason": "goal counter absent under goal intent; initialized from "
                        "the section 1.5 rebuild (CORE section 1.2)",
                    }
                )
            elif have is not None:
                repairs.append(
                    {
                        "field": field,
                        "from": have,
                        "to": want,
                        "surface": "state",
                        "reason": "goal counter is malformed (non-integer); rebuilt from "
                        "the section 1.5 evidence (CORE section 1.2)",
                    }
                )
            continue
        if have == want:
            continue
        if want > have:
            repairs.append(
                {
                    "field": field,
                    "from": have,
                    "to": want,
                    "surface": "state",
                    "reason": "goal counter behind the section 1.5 rebuild -- a bump reached "
                    "the LOG and never reached STATE (CORE section 1.5)",
                }
            )
            continue
        if have >= cap[field]:
            repairs.append(
                {
                    "field": field,
                    "from": have,
                    "to": want,
                    "surface": "state",
                    "reason": "goal counter is at/over the safety cap while canonical "
                    "history is lower -- never silently cleared without "
                    "re-authorization (CORE section 2.4)",
                    "refuse": True,
                }
            )
            continue
        repairs.append(
            {
                "field": field,
                "from": have,
                "to": want,
                "surface": "state",
                "reason": "goal counter ahead of the section 1.5 rebuild but under the "
                "safety cap -- reconciled down to canonical evidence (CORE-001)",
            }
        )
    return repairs


def _tripped_valve_repairs(state: dict) -> list[dict]:
    """The tripped valve is an invariant, not a side effect of counter drift.

    `_state_counter_repairs` only notices a valve while the counter DISAGREES
    with canonical history. The ordinary way a valve trips is by honest
    counting -- `have == want == 20` -- and that path hits the equality
    `continue`, emits nothing, and lets the whole reconciliation certify CLEAN
    over a run that MAINTENANCE section 2.4 says must be paused.

    Witnessed (T-1181): `validate.py` reported `execution_intent: goal with
    goal_waves=0/goal_tickets=20 is the tripped safety valve (caps 3/20), but
    next_action='PHASE SHIP T-1242'` while `saipen continue`'s reconciliation
    returned CLEAN on the same STATE in the same minute. Two gates, one
    condition, opposite answers.

    So the counters are read directly against the caps, and the field checked
    is `next_action` -- reconciliation-owned, and the one field section 2.4
    requires the trip to be visible in. The grammar is not respelled here:
    `state._SAFETY_VALVE_RE` already owns it, and a second spelling of a
    verbatim protocol string is a second thing to drift.

    Never repaired silently. A tripped valve is the human's to clear through
    `cc`, so this returns a `refuse` repair -- the same shape the at-cap
    counter case uses -- which the caller turns into RECONCILE_REAUTH_REQUIRED.
    """
    from .state import _SAFETY_VALVE_RE

    if state.get("execution_intent") != "goal":
        return []

    caps = {"goal_waves": _GOAL_WAVES_CAP, "goal_tickets": _GOAL_TICKETS_CAP}
    tripped = {
        field: value
        for field, cap in caps.items()
        if isinstance((value := state.get(field)), int)
        and not isinstance(value, bool)
        and value >= cap
    }
    if not tripped:
        return []

    waves = state.get("goal_waves") or 0
    tickets = state.get("goal_tickets") or 0
    want = f"WAIT: safety valve reached ({waves} waves / {tickets} tickets) -- run 'cc' to continue"

    have = state.get("next_action")
    if isinstance(have, str) and _SAFETY_VALVE_RE.match(have.removeprefix("WAIT: ").strip()):
        # Already stating the pause. The counters stay at the cap on purpose --
        # they ARE the tripped condition, and tidying them walks past the valve.
        return []

    named = ", ".join(f"{field}={value}" for field, value in sorted(tripped.items()))
    return [
        {
            "field": "next_action",
            "from": have,
            "to": want,
            "surface": "state",
            "reason": (
                f"safety valve tripped ({named}) but next_action does not state the pause -- "
                "MAINTENANCE section 2.4 requires the section 1.2 WAIT form, and `cc` is the "
                "only re-authorization; reconciliation must not certify CLEAN over it"
            ),
            "refuse": True,
        }
    ]


def _repair_summary(board_drifts: list[dict], state_repairs: list[dict]) -> str:
    parts: list[str] = []
    if board_drifts:
        parts.append(f"{len(board_drifts)} board checkbox drift(s)")
    for repair in state_repairs:
        parts.append(f"{repair['field']} {repair['from']!r}->{repair['to']!r}")
    return "; ".join(parts)


def reconcile_protocol_state(root: Path | str, agent: str, *, dry_run: bool = False) -> dict:
    """Derive, validate and (unless dry_run) commit the complete repair set."""
    project_root = Path(root)
    try:
        from .operations import (
            _docs_preconditions,
            _event_line,
            _identity,
            _read,
            _target,
        )
        from .fast_check import validate_texts
        from .plan import apply_plan, build_plan
    except ImportError as exc:  # pragma: no cover - import graph is static
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}

    try:
        docs, state, _board, log_tail = _read(project_root, allow_malformed_state=True)
    except Exception as exc:
        # CheckpointError / HomeDeadError / OSError all mean the surface cannot
        # be reconciled mechanically. Refuse loudly -- none of them is the
        # absence of drift.
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}

    events = docs["_history"].events if docs.get("_history") is not None else ()
    state_text = docs["state"].text_norm
    board_text = docs["board"].text_norm
    # Present only when the strict contract refused its own STATE -- i.e. the
    # drift is severe enough that the repair set is the last chance before the
    # surface is declared unreconcileable. Reported, never silently healed.
    strict_state_error = docs.get("_state_error", "")

    board_drifts = _checkbox_drifts(board_text)
    state_repairs = (
        _state_marker_repairs(state, log_tail)
        + _state_counter_repairs(state, events)
        + _tripped_valve_repairs(state)
    )
    refused_repairs = [r for r in state_repairs if r.get("refuse")]
    if refused_repairs:
        # CORE-001: an at/over-cap counter while canonical history is lower
        # cannot be CLEANed and cannot be auto-repaired. Surface the refusal
        # explicitly so the run cannot pretend the valve was never tripped.
        return {
            "ok": False,
            "code": "RECONCILE_REAUTH_REQUIRED",
            "detail": "; ".join(
                f"{r['field']} {r['from']!r}->{r['to']!r} ({r['reason']})"
                for r in refused_repairs
            ),
            "changed": {"board": [], "state": state_repairs},
            "refused": refused_repairs,
            "strict_state_error": strict_state_error or None,
            "dry_run": dry_run,
        }
    if not (board_drifts or state_repairs):
        # Nothing the reconciliation owns differs. A STATE that is still red by
        # the strict contract is then NOT drift -- it is damage this operation
        # does not own, and certifying CLEAN over it would be the exact lie
        # CORE-002 exists to kill.
        if strict_state_error:
            return {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"state-malformed: {strict_state_error}",
                "changed": {"board": [], "state": []},
                "strict_state_error": strict_state_error or None,
                "dry_run": dry_run,
            }
        return {
            "ok": True,
            "code": "CLEAN",
            "changed": [],
            "strict_state_error": None,
            "dry_run": dry_run,
        }

    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%d.%m.%y %H:%M")
    utc = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    op_id = "reconcile-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S%f")
    # The DEC names the DRIFT that was detected -- `last_event 2->1` means
    # "STATE claimed 2, the LOG tail is 1". The value actually persisted is the
    # tail AFTER this trace is appended, because the repair's own DEC is then
    # the newest event; the drift it reports is the one it was asked to fix.
    description = "reconcile protocol state -- " + _repair_summary(board_drifts, state_repairs)
    event, line = _event_line(
        docs, log_tail, "DEC", None, agent, description, stamp, op_id
    )
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_board = _apply_checkbox_repairs(board_text, board_drifts) if board_drifts else board_text

    from .state import patch_state

    owned = {repair["field"]: repair["to"] for repair in state_repairs}
    owned["last_event"] = event
    owned["updated"] = utc
    owned["agent"] = agent
    try:
        new_state = patch_state(state_text, owned)
    except ValueError as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}

    # ONE complete-surface validation of the PROPOSAL -- the same invariants the
    # post-write gate runs. A proposal that cannot pass is never committed, and
    # a surface that cannot be made clean is reported rather than certified.
    errors = validate_texts(
        new_state,
        new_board,
        new_log,
        current_agent=agent,
        sealed_events=docs.get("_history"),
    )
    if errors:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": "proposed reconciliation fails fast validation: " + "; ".join(errors[:5]),
            "changed": {"board": board_drifts, "state": state_repairs},
            "strict_state_error": strict_state_error or None,
            "dry_run": dry_run,
        }

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
    ]
    if board_drifts:
        targets.append(_target(docs["board"], ".saipen/BOARD.md", "board", new_board))
    targets.append(_target(docs["state"], ".saipen/STATE.md", "state", new_state))

    plan = build_plan(
        "reconcile",
        agent,
        _identity(project_root),
        {
            "operation": "reconcile",
            "board_drifts": len(board_drifts),
            "state_repairs": [repair["field"] for repair in state_repairs],
            "event": event,
        },
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "REPAIRED", "event_id": f"E-{event}"},
        op_id=op_id,
    )

    if dry_run:
        return {
            "ok": True,
            "code": "REPAIR_REQUIRED",
            "changed": {"board": board_drifts, "state": state_repairs},
            "targets": [target.path for target in targets],
            "planned_event": f"E-{event}",
            "detail": description,
            "strict_state_error": strict_state_error or None,
            "dry_run": True,
        }

    applied = apply_plan(project_root, plan)
    if not applied.get("ok"):
        return {
            "ok": False,
            "code": applied.get("code", "VALIDATION_FAILED"),
            "detail": applied.get("message", ""),
            "changed": {"board": board_drifts, "state": state_repairs},
            "dry_run": False,
        }
    return {
        "ok": True,
        "code": "REPAIRED",
        "changed": {"board": board_drifts, "state": state_repairs},
        "targets": [target.path for target in targets],
        "event": f"E-{event}",
        "agent": agent,
        "strict_state_error": strict_state_error or None,
        "dry_run": False,
    }

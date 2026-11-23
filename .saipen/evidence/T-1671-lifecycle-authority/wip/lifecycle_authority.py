"""Lifecycle authority: canonical state that no journaled operation produced.

Defect class this owns (T-1671, SRC-192). An executor that could not reach the
SAIPEN control route wrote STATE, BOARD and LOG by hand in the documented field
shapes: a `## DONE` row with `closure_mode`, RFC-shaped LOG events, a STATE
whose `last_event` named its own hand-typed tail. Every reader accepted the
bytes because they parse. The phantom-DONE and journal-gap recoveries already
in `reconcile` judge a closure by BOARD fields and by LOG prose, and both are
exactly what a hand can type.

What a hand cannot type is an operation record. Every canonical operation
appends its LOG event with an `[op: ...]` id and leaves a journal record under
the recovery tree, and every operation that appends an event also writes
`STATE.last_event`. So the newest LOG event whose id resolves to a record -- the
FLOOR -- is the last point this checkout can prove an operation reached, and
two facts above it have no operation behind them:

  * `state-ahead-of-journal`: `STATE.last_event` names an event above the
    floor. Only an operation moves that marker, and the event it names would
    be the operation's own.
  * `terminal-without-operation`: a `## DONE` ticket is named by an event above
    the floor and no closure operation stands behind it at or below the floor.

The boundary is self-establishing, like every provenance boundary here: with no
ledger on the checkout (a fresh clone, a consumer copy) or no resolvable event
at all, the verdict is UNAVAILABLE, never a finding. History at or below the
floor is never judged, so closures that predate this contract are untouched --
and because no operation may build on an unauthorized head (`operations._read`
refuses), a new hand-written head can never sink below a later floor unseen.

Not covered, and named so nobody reads it as covered: a BOARD row flipped to
DONE with no LOG event and no STATE change leaves no trace this module reads.
Closing that needs the journal to record the terminal set it wrote.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

#: The refusal code, registered in REGISTRY.json `error_codes`.
CODE = "UNAUTHORIZED_LIFECYCLE_WRITE"

#: The `_read(observe=...)` damage class a recovery planner names to see an
#: unauthorized head instead of being refused by it.
OBSERVABLE = "lifecycle_authority"

AUTHORIZED = "AUTHORIZED"
UNAVAILABLE = "UNAVAILABLE"
UNAUTHORIZED = "UNAUTHORIZED"

STATE_AHEAD = "state-ahead-of-journal"
TERMINAL_UNBACKED = "terminal-without-operation"

#: The recovery class every repair atom of this module carries.
REPAIR_CLASS = "unauthorized-lifecycle-write"

#: Operation classes that move a ticket into `## DONE` (or let an existing
#: closure stand: `reconcile-` carries the legacy attestation and adoption
#: decisions). A ticket with one of these at or below the floor was closed by
#: an operation, and a hand-written note about it afterwards is only a note.
CLOSURE_OP_CLASSES = (
    "finish-",
    "supersede-",
    "resolve-external-",
    "retire-",
    "crew-defer-",
    "crew-closure-",
    "reconcile-",
)

#: Newest events examined while looking for the floor. The floor is normally
#: the newest event itself; the bound only caps a pathological tail.
_TAIL_WINDOW = 4096

_TARGET_RE = re.compile(r"\[target: (T-\d+)\]")


def _event_number(event: dict) -> int | None:
    number = event.get("event")
    if isinstance(number, int) and not isinstance(number, bool):
        return number
    return None


def _resolver(root: Path):
    """`(ledger_present, resolves)` for this checkout.

    The cheap answer is a directory probe for the one id asked about; the full
    ledger (which also reads the settled index that survives compaction) is
    loaded once, and only for an id the probe did not find.
    """
    from .journal import OPS_DIR, SETTLED_DIR, resolvable_op_ids

    ops = root / OPS_DIR
    settled = root / SETTLED_DIR
    present = ops.is_dir() or settled.is_dir()
    full: list[set[str]] = []

    def resolves(op_id: str | None) -> bool:
        if not op_id or op_id in (".", "..") or "/" in op_id or "\\" in op_id:
            return False
        if os.path.exists(ops / op_id) or os.path.exists(settled / op_id):
            return True
        if not full:
            full.append(resolvable_op_ids(root))
        return op_id in full[0]

    return present, resolves


def _closed_by_operation(events, ticket: str, floor: int) -> bool:
    """Does a closure operation stand behind this ticket at or below the floor?

    Scoped to the ticket's newest canonical claim, for the reason
    `reconcile._ticket_epoch` gives: an older completion never authorizes a
    lifecycle that was claimed again after it.
    """
    epoch = 0
    closures: list[int] = []
    for event in events:
        number = _event_number(event)
        if number is None or number > floor or event.get("ticket") != ticket:
            continue
        op_id = str(event.get("op_id") or "")
        if op_id.startswith("claim-") and str(event.get("text") or "").startswith(
            "claimed via SAIOPS"
        ):
            epoch = max(epoch, number)
        elif op_id.startswith(CLOSURE_OP_CLASSES):
            closures.append(number)
    return any(number >= epoch for number in closures)


def assess(root: Path | str, state: dict | None, board: dict | None, events) -> dict:
    """The lifecycle-authority verdict for the live canonical files.

    `events` is the complete parsed history (sealed and active), as
    `log.read_history_snapshot(...).events` returns it. Read-only.
    """
    root = Path(root)
    verdict = {"status": UNAVAILABLE, "floor": None, "head": [], "findings": [], "detail": ""}
    numbered = [event for event in (events or ()) if _event_number(event) is not None]
    if not numbered:
        return verdict
    present, resolves = _resolver(root)
    if not present:
        return verdict
    tail = sorted(numbered[-_TAIL_WINDOW:], key=_event_number, reverse=True)
    floor = None
    head: list[dict] = []
    for event in tail:
        if resolves(event.get("op_id")):
            floor = _event_number(event)
            break
        head.append(event)
    if floor is None:
        return verdict
    verdict["floor"] = floor
    verdict["head"] = sorted(_event_number(event) for event in head)
    findings: list[dict] = []
    last_event = (state or {}).get("last_event")
    if isinstance(last_event, int) and not isinstance(last_event, bool) and last_event > floor:
        findings.append(
            {
                "rule": STATE_AHEAD,
                "last_event": last_event,
                "floor": floor,
                "detail": (
                    f"STATE.last_event is E-{last_event}, above E-{floor}, the newest "
                    "event an operation record stands behind -- only an operation "
                    "moves that marker, so STATE was advanced by hand"
                ),
            }
        )
    named: dict[str, list[int]] = {}
    for event in head:
        tickets = {event.get("ticket")} | set(_TARGET_RE.findall(event.get("text") or ""))
        for ticket in tickets:
            if ticket:
                named.setdefault(ticket, []).append(_event_number(event))
    for ticket, ticket_events in sorted(named.items()):
        row = ((board or {}).get("tickets") or {}).get(ticket)
        if not isinstance(row, dict) or row.get("section") != "## DONE":
            continue
        if _closed_by_operation(numbered, ticket, floor):
            continue
        shown = ", ".join(f"E-{number}" for number in sorted(ticket_events)[:4])
        findings.append(
            {
                "rule": TERMINAL_UNBACKED,
                "ticket": ticket,
                "events": sorted(ticket_events),
                "floor": floor,
                "detail": (
                    f"{ticket} sits under ## DONE on the word of {shown}, written "
                    f"above E-{floor} with no operation record, and no closure "
                    "operation stands behind it -- the completion was typed, not run"
                ),
            }
        )
    verdict["findings"] = findings
    verdict["status"] = UNAUTHORIZED if findings else AUTHORIZED
    verdict["detail"] = "; ".join(finding["detail"] for finding in findings[:3])
    return verdict


def refusal_detail(verdict: dict) -> str:
    """One line for a refusal: what is unauthorized and the command that owns it."""
    return (
        "lifecycle-authority: "
        + verdict.get("detail", "")
        + " -- canonical lifecycle state exists only through an operation; "
        "`saipen recover` names the journaled repair that reopens what no "
        "operation closed"
    )

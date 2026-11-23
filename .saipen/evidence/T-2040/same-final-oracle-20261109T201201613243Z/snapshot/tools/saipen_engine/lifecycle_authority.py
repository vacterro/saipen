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

A typed head may also BREAK the ledger: an executor that replaces one of its
own lines leaves a parent edge into nothing, every strict reader refuses
HISTORY_LEDGER_CORRUPT, and nothing above ever runs (T-1679, measured live on
the same project the same night). The floor is still provable -- it needs the
events and the journal, not a valid parent chain -- so the tail quarantine may
cut at the floor where it used to cut only at `STATE.last_event`, a marker the
same hand had moved. The lines leave the LOG for the quarantine's evidence
copy, and the quarantine's own event names the `## DONE` rows they closed; a
row so named and still closed by no operation is `terminal-without-operation`
exactly as if its lines were still above the floor.

A hand may also leave the LOG and STATE alone and move a row under `## DONE`
in BOARD.md only (T-1673). Nothing above the floor names it, so the two rules
above cannot see it. Every committed plan that writes BOARD.md therefore leaves
a baseline (`record_terminal`): the BOARD bytes' digest and the `## DONE` set
they held. When the live BOARD no longer matches that digest, a ticket in the
live `## DONE` set and not in the baseline is `terminal-without-operation`
unless a closure operation stands behind it -- which is also what keeps a
writer that commits outside `plan.apply_plan` (a release closure, a recovery
replay) from ever reading as a hand. An edit that moves no ticket into
`## DONE` is not judged. With no baseline (a fresh clone, history older than
this contract) the rule is unavailable, never a finding.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

#: The class this module names, in every refusal detail, finding and trace.
CLASS = "UNAUTHORIZED_LIFECYCLE_WRITE"

#: The terminal baseline of the newest committed BOARD write (T-1673).
#: Machine-local like the journal it summarizes; rewritten under the writer lock.
TERMINAL_BASELINE = ".saipen/recovery/board-terminal.json"

#: The refusal CODE: the class itself, registered in REGISTRY.json
#: `error_codes` (T-1676). Until the route budgets replaced the aggregate cap
#: (T-1670) it rode PROTOCOL_STATE_INVALID and named the class only in the
#: detail; a host now routes on the code alone.
CODE = CLASS

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

#: Operation classes that move a ticket into `## DONE`. A ticket with one of
#: these at or below the floor was closed by an operation, and a hand-written
#: note about it afterwards is only a note. `reconcile-` is not in the set: it
#: writes adoptions and repairs too, so it counts only when its text is the
#: operator's attestation that a completion stands (`_closed_by_operation`).
CLOSURE_OP_CLASSES = (
    "finish-",
    "supersede-",
    "resolve-external-",
    "retire-",
    "crew-defer-",
    "crew-closure-",
)

#: The quarantine event that records a typed head cut at the journal floor, and
#: the phrase that introduces the `## DONE` rows its lines had closed. Written
#: by `operations.quarantine_log_tail`, read back by `assess`: once the lines
#: are out of the LOG this event is the only durable trace of what they claimed.
QUARANTINE_OP_CLASS = "quarantine-log-tail-"
TYPED_HEAD_MARKER = "typed head quarantined"
ROWS_PHRASE = "rows they closed: "
_ROWS_RE = re.compile(re.escape(ROWS_PHRASE) + r"((?:T-\d+)(?:, T-\d+)*)")

#: The duplicate-id decision is the one repair every later repair waits for
#: (`reconcile` refuses to aim a BOARD write through a duplicated id), so it
#: must run on an unauthorized head too. Its own event would then become the
#: floor and bury the typed closures above the old one, so it carries them:
#: the rows that head had closed, in the quarantine's grammar, read back by
#: `assess` until an operation closes or reopens each one (T-1761).
CARRY_OP_CLASS = "duplicate-id-"
CARRY_MARKER = "typed head carried"

#: Newest events examined while looking for the floor. The floor is normally
#: the newest event itself; the bound only caps a pathological tail.
_TAIL_WINDOW = 4096

_TARGET_RE = re.compile(r"\[target: (T-\d+)\]")

#: `log.LEGACY_DONE_ATTESTATION`, restated here because `log` imports nothing
#: from this module and must not start to; the test module pins the two equal.
_ATTESTATION = "legacy completion attested"


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
        text = str(event.get("text") or "")
        if op_id.startswith("claim-") and text.startswith("claimed via SAIOPS"):
            epoch = max(epoch, number)
        elif op_id.startswith(CLOSURE_OP_CLASSES) or (
            op_id.startswith("reconcile-") and _ATTESTATION in text
        ):
            closures.append(number)
    return any(number >= epoch for number in closures)


def journal_floor(root: Path | str, events) -> tuple[int | None, list[dict]]:
    """`(floor, head)`: the newest event a journal record stands behind, and
    the events above it, newest first. `(None, [])` when this checkout cannot
    say -- no ledger, no numbered event, or nothing in the tail that resolves.

    It asks nothing of the parent chain, so it answers on a ledger the
    immutable-ledger contract refuses, which is where the quarantine needs it.
    """
    numbered = [event for event in (events or ()) if _event_number(event) is not None]
    if not numbered:
        return None, []
    present, resolves = _resolver(Path(root))
    if not present:
        return None, []
    head: list[dict] = []
    for event in sorted(numbered[-_TAIL_WINDOW:], key=_event_number, reverse=True):
        if resolves(event.get("op_id")):
            return _event_number(event), head
        head.append(event)
    return None, []


def named_tickets(event: dict) -> set[str]:
    """Every ticket one event speaks for: its tag and its `[target: ...]`."""
    named = set(_TARGET_RE.findall(event.get("text") or ""))
    if event.get("ticket"):
        named.add(event["ticket"])
    return named


def _under_done(board: dict | None, ticket: str) -> bool:
    """Does any record of this id sit under `## DONE`?

    The row the parser kept, or a record it dropped for the duplicated key
    (T-1761): a hand that types a second record of a live id under `## DONE`
    does not hide that closure behind the first.
    """
    row = ((board or {}).get("tickets") or {}).get(ticket)
    if not isinstance(row, dict):
        return False
    return row.get("section") == "## DONE" or "## DONE" in (row.get("shadowed") or ())


def typed_rows(head_events, board: dict | None, events, floor: int) -> list[str]:
    """The `## DONE` rows a typed head closed: named by its events, closed by
    no operation at or below the floor."""
    numbered = [event for event in (events or ()) if _event_number(event) is not None]
    rows: list[str] = []
    for ticket in sorted({name for event in head_events for name in named_tickets(event)}):
        if not _under_done(board, ticket):
            continue
        if not _closed_by_operation(numbered, ticket, floor):
            rows.append(ticket)
    return rows


def quarantine_note(floor: int, lines: int, rows: list[str]) -> str:
    """The head of the quarantine DEC for a typed head; `assess` parses it."""
    return (
        f"{TYPED_HEAD_MARKER} above E-{floor}: {lines} line(s) carried no operation "
        "record and no operation ever bound them; "
        + ROWS_PHRASE
        + (", ".join(rows) if rows else "none")
    )


def carried_rows(verdict: dict | None, reassigned: str | None = None) -> list[str]:
    """The rows an operation must carry when it commits over this verdict.

    Every `## DONE` row the unauthorized head speaks for, and `reassigned`:
    the new id of a record renamed while it sat under `## DONE`. No
    operation ever closed that id, and the typed lines name the old one, so
    without it a typed row would leave the verdict by changing its name.
    Empty on any other verdict: an authorized head has nothing to carry.
    """
    if not isinstance(verdict, dict) or verdict.get("status") != UNAUTHORIZED:
        return []
    rows = {
        finding["ticket"]
        for finding in verdict.get("findings") or ()
        if finding.get("rule") == TERMINAL_UNBACKED and finding.get("ticket")
    }
    if reassigned:
        rows.add(reassigned)
    return sorted(rows, key=lambda name: int(name.split("-")[1]))


def carry_note(rows: list[str]) -> str:
    """The clause a carrying operation appends to its DEC; `assess` parses it."""
    return f"{CARRY_MARKER} past this decision; " + ROWS_PHRASE + ", ".join(rows)


def assess(root: Path | str, state: dict | None, board: dict | None, events) -> dict:
    """The lifecycle-authority verdict for the live canonical files.

    `events` is the complete parsed history (sealed and active), as
    `log.read_history_snapshot(...).events` returns it. Read-only.
    """
    root = Path(root)
    verdict = {"status": UNAVAILABLE, "floor": None, "head": [], "findings": [], "detail": ""}
    numbered = [event for event in (events or ()) if _event_number(event) is not None]
    floor, head = journal_floor(root, numbered)
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
        for ticket in named_tickets(event):
            named.setdefault(ticket, []).append(_event_number(event))
    # A typed head that was quarantined left the LOG; its quarantine event
    # carries the rows it had closed, and speaks for them until an operation
    # closes or reopens each one.
    quarantined: dict[str, int] = {}
    carried: set[int] = set()
    for event in numbered:
        text = str(event.get("text") or "")
        op_id = str(event.get("op_id") or "")
        carrying = op_id.startswith(CARRY_OP_CLASS) and CARRY_MARKER in text
        if carrying:
            carried.add(_event_number(event))
        if _event_number(event) <= floor and (
            carrying or (op_id.startswith(QUARANTINE_OP_CLASS) and TYPED_HEAD_MARKER in text)
        ):
            match = _ROWS_RE.search(text)
            for ticket in match.group(1).split(", ") if match else ():
                quarantined[ticket] = _event_number(event)
    for ticket, number in sorted(quarantined.items()):
        if ticket in named:
            continue
        if not _under_done(board, ticket):
            continue
        if _closed_by_operation(numbered, ticket, floor):
            continue
        findings.append(
            {
                "rule": TERMINAL_UNBACKED,
                "ticket": ticket,
                "events": [number],
                "floor": floor,
                "detail": (
                    f"{ticket} sits under ## DONE on the word of a typed head that "
                    f"E-{number} {'carried' if number in carried else 'quarantined'}, "
                    "and no closure operation stands behind it -- the completion "
                    "was typed, not run"
                ),
            }
        )
    for ticket in _board_only_moves(root, board):
        if ticket in named or ticket in quarantined:
            continue
        if _closed_by_operation(numbered, ticket, floor):
            continue
        findings.append(
            {
                "rule": TERMINAL_UNBACKED,
                "ticket": ticket,
                "events": [],
                "floor": floor,
                "origin": "board-only",
                "detail": (
                    f"{ticket} sits under ## DONE after an edit of BOARD.md that no "
                    "LOG event records, and no closure operation stands behind it -- "
                    "the completion was typed, not run"
                ),
            }
        )
    for ticket, ticket_events in sorted(named.items()):
        if not _under_done(board, ticket):
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


def _board_digest(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()[:16]


def _done_set(board: dict | None) -> set[str]:
    return {tid for tid in ((board or {}).get("tickets") or {}) if _under_done(board, tid)}


def record_terminal(root: Path | str) -> None:
    """Write the terminal baseline for the BOARD.md that is live right now.

    Called by `plan.apply_plan` under the writer lock after a commit that wrote
    BOARD.md. Best effort: a baseline that cannot be written leaves the older
    one, and the rule falls back to the closure operations it already checks.
    """
    import json

    from .board import parse_board

    root = Path(root)
    try:
        raw = (root / ".saipen" / "BOARD.md").read_bytes()
        done = sorted(_done_set(parse_board(raw.decode("utf-8-sig"))))
        target = root / TERMINAL_BASELINE
        target.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(
            {"schema": 1, "board_sha256_16": _board_digest(raw), "done": done},
            sort_keys=True,
        )
        temporary = target.with_name(f".{target.name}.{os.getpid()}")
        temporary.write_text(body + chr(10), encoding="utf-8")
        os.replace(temporary, target)
    except (OSError, ValueError, UnicodeDecodeError):
        return


def _terminal_baseline(root: Path) -> dict | None:
    import json

    try:
        payload = json.loads((root / TERMINAL_BASELINE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("board_sha256_16"), str)
        or not isinstance(payload.get("done"), list)
    ):
        return None
    return payload


def _board_only_moves(root: Path, board: dict | None) -> list[str]:
    """Tickets moved into `## DONE` by a BOARD.md edit no baseline covers."""
    baseline = _terminal_baseline(root)
    if baseline is None or board is None:
        return []
    try:
        raw = (root / ".saipen" / "BOARD.md").read_bytes()
    except OSError:
        return []
    if _board_digest(raw) == baseline["board_sha256_16"]:
        return []
    return sorted(_done_set(board) - {str(item) for item in baseline["done"]})


def refusal_detail(verdict: dict) -> str:
    """One line for a refusal: what is unauthorized and the command that owns it."""
    return (
        f"lifecycle-authority: {CLASS} -- "
        + verdict.get("detail", "")
        + " -- canonical lifecycle state exists only through an operation; "
        "`saipen recover` names the journaled repair that reopens what no "
        "operation closed"
    )

"""Which closed BOARD records a CLEAN scrub may prune (T-1640).

`phases/clean.md` step 1 told an agent to prune old `## DONE` entries, and the
validator repeated it on every run as `board-soft-cap`. No agent could: the
BOARD is a protected canonical file and no engine verb pruned a record. The
last scrub that did happen (18.09.26, by hand, before the guard) restored five
validator FAILs on the way, because its retention rule looked one hop off the
live sections and a kept row went on naming a pruned one.

This module is the retention rule, stated once and read by both the operation
that prunes (`operations.scrub_board`) and the validator finding that asks for
it. A closed record is KEPT while any of these holds:

  reference  a record that stays names it in `needs:`, `blocked_on:`,
             `superseded_by:` or `implementation_source:` -- every edge a
             validator resolves on the BOARD, followed transitively, because a
             kept record's own references must keep resolving;
  receipt    an ACTIVE source receipt names it (primary or member Work, or a
             coverage clause bound to it), or its own `source_receipts:` names
             an ACTIVE receipt: the row is that Work's existence record and
             the receipt's later verbs look it up. An unconsumed captured audit
             binding also holds its Work row after Source closure, because
             journaled consumption still checks that the Work is DONE;
  gate       a PROMOTED future gate still names it as a slice ticket: the gate
             is resolved on the BOARD by every core gate run, and the row is
             the implementation record that resolution reads;
  unproven   the complete LOG history holds no closing event for it, so the
             BOARD row is the only record that it closed at all.

Everything else in `## DONE` is closed-ticket text nothing reads from the
BOARD any more. It is moved, never dropped: the operation writes the pruned
rows verbatim under `SCRUB_EVIDENCE_ROOT` in the plan that removes them.

The cap this replaces measured the whole file against ~16 KB. No route could
ever meet that on a project whose open work alone is larger -- this
repository's live rows were 55 KB when it was measured -- so the number is
restated against what a scrub can actually clear: the prunable text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

#: Where a scrub keeps the rows it pruned, one directory per operation.
SCRUB_EVIDENCE_ROOT = ".saipen/recovery/board-scrub"

#: Prunable closed-ticket text past this is due for a scrub, and under it is
#: left alone: recent closed rows are cheap context on a small board.
SCRUB_DUE_BYTES = 16 * 1024

#: Operations that move a record to `## DONE`. An event of one of these
#: classes bearing the ticket's id is the permanent LOG evidence
#: `phases/clean.md` requires before the row may leave the BOARD.
CLOSING_OP_CLASSES = (
    "finish-",
    "supersede-",
    "resolve-external-",
    "crew-defer-",
    "clear-wait-role-",
)

_TICKET_RE = re.compile(r"\bT-\d+\b")
_RECEIPT_RE = re.compile(r"\bSRC-\d+\b")
#: Scalar fields of a kept record whose ids a validator resolves on the BOARD.
_REFERENCE_FIELDS = ("blocked_on", "superseded_by", "implementation_source")


@dataclass(frozen=True)
class Selection:
    """What one scrub of one BOARD would prune and what it would keep."""

    #: Closed records to prune, in BOARD order.
    pruned: tuple[str, ...]
    #: Their size in the BOARD, counting one line terminator per record.
    pruned_bytes: int
    #: Every closed record that stays -> the guard that keeps it.
    kept: dict[str, str]

    @property
    def due(self) -> bool:
        return self.pruned_bytes > SCRUB_DUE_BYTES

    def kept_by(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for guard in self.kept.values():
            counts[guard] = counts.get(guard, 0) + 1
        return dict(sorted(counts.items()))


def closed_in_history(events, ticket_ids) -> set[str]:
    """The ids among `ticket_ids` that a closing operation wrote an event for."""
    wanted = set(ticket_ids)
    proven: set[str] = set()
    for event in events:
        ticket = event.get("ticket")
        if ticket in wanted and str(event.get("op_id") or "").startswith(CLOSING_OP_CLASSES):
            proven.add(ticket)
    return proven


def _receipts_named(ticket: dict) -> set[str]:
    return set(_RECEIPT_RE.findall(str((ticket.get("fields") or {}).get("source_receipts") or "")))


def _references(ticket: dict, by_receipt: dict[str, set[str]]) -> set[str]:
    """Every record this one names through an edge a validator resolves."""
    fields = ticket.get("fields") or {}
    named = set(ticket.get("needs") or [])
    for key in _REFERENCE_FIELDS:
        value = str(fields.get(key) or "")
        named.update(_TICKET_RE.findall(value))
        if key == "implementation_source":
            # A Source is provenance, not publication: the resolver follows it
            # to the Work it produced, so that Work is named here too.
            for receipt in _RECEIPT_RE.findall(value):
                named.update(by_receipt.get(receipt, ()))
    return named


#: The promoted-gate ledger. A slice ticket named there is still read by
#: `future_gate.validate_future_gate` on every core gate run.
FUTURE_INDEX = ".saipen/future/index.json"


def gated_tickets(root: Path | str) -> set[str]:
    """Slice tickets a PROMOTED future gate still pins, for DIAGNOSTICS (T-2071).

    A gate record outlives the BOARD row it names: after promotion the slice
    ticket is the evidence that the gate's implementation exists, and
    `future_gate` resolves it on the BOARD every run. The scrub retention rule
    did not read the ledger, so it pruned T-1936 -- a DONE row FG-0046 pinned --
    and the gate then reported a broken link over a slice the LOG proves
    complete. Reading the ledger here keeps that row while the gate is in
    force; an unreadable ledger pins nothing, because a broken file must not
    silently freeze the whole DONE section.

    That fail-open reading is sound only where nothing is destroyed. A caller
    that PRUNES must use `collect_inputs`, which raises when the ledger cannot
    prove the gate set (T-2096) instead of reading "unreadable" as "no gates".
    """
    path = Path(root) / FUTURE_INDEX
    try:
        index = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return set()
    gated: set[str] = set()
    for gate in index.get("gates") or ():
        if not isinstance(gate, dict) or str(gate.get("state") or "") != "PROMOTED":
            continue
        for record in gate.get("slices") or ():
            if not isinstance(record, dict):
                continue
            ticket = str(record.get("ticket") or "")
            if re.fullmatch(r"T-\d+", ticket):
                gated.add(ticket)
    return gated


class ScrubInputsUnknown(ValueError):
    """A mandatory retention input cannot be read, so nothing is called prunable."""


@dataclass(frozen=True)
class RetentionInputs:
    """Every read-only input `select` needs besides the BOARD and its history."""

    active_receipts: frozenset[str]
    receipt_works: frozenset[str]
    gated: frozenset[str]


def _gate_pins(root: Path) -> tuple[set[str], str | None]:
    """`(PROMOTED slice tickets, unknown reason)` from the canonical ledger.

    The owner module decides what the ledger is: absence, corruption, schema
    drift and a malformed record are each named, never collapsed into "no
    gates". `None` is returned only when absence is provable -- no index and
    no corpus to index.
    """
    from . import future_gate

    root = Path(root)
    index = future_gate.load_index(root)
    if index is None:
        try:
            documents = future_gate.read_documents(root)
        except (OSError, ValueError) as exc:
            return set(), f"the future-gate corpus cannot be read: {exc}"
        if documents:
            return set(), (
                f"{len(documents)} future-gate document(s) are not indexed, so the "
                "slice tickets they pin are unknown -- run `saipen future refresh`"
            )
        return set(), None
    if index.get("corrupt"):
        return set(), (
            f"the future-gate index is unreadable ({index['corrupt']}), so the "
            "slice tickets it pins are unknown -- run `saipen future refresh`"
        )
    try:
        schema_ok = int(index.get("schema") or 0) == future_gate.SCHEMA_VERSION
    except (TypeError, ValueError):
        schema_ok = False
    if not schema_ok:
        return set(), (
            f"the future-gate index carries schema {index.get('schema')!r}, expected "
            f"{future_gate.SCHEMA_VERSION}, so the slice tickets it pins are unknown"
        )
    gates = index.get("gates")
    if gates is None:
        gates = []
    if not isinstance(gates, list):
        return set(), "the future-gate index holds a malformed gates member"
    gated: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            return set(), "the future-gate index holds a malformed gate record"
        if str(gate.get("state") or "") != future_gate.PROMOTED:
            continue
        slices = gate.get("slices")
        if slices is None:
            slices = []
        if not isinstance(slices, list):
            return set(), f"promoted gate {gate.get('id')!r} carries malformed slices"
        for record in slices:
            if not isinstance(record, dict):
                return set(), f"promoted gate {gate.get('id')!r} carries a malformed slice"
            ticket = str(record.get("ticket") or "")
            if re.fullmatch(r"T-\d+", ticket):
                gated.add(ticket)
    return gated, None


def collect_inputs(root: Path | str) -> RetentionInputs:
    """Read every retention input ONCE, refusing on data that cannot be proved.

    The validator finding and the canonical operation both call this and then
    `select`, so the row a CLEAN plan removes and the row the warning counts
    are the same decision over the same bytes (T-2096). Receipts raise from
    their owner; the gate ledger raises here. `gated_tickets` keeps the
    fail-open diagnostic reading, which is never used to destroy anything.
    """
    from .intake import active_receipt_works

    active, works = active_receipt_works(root)
    gated, unknown = _gate_pins(Path(root))
    if unknown is not None:
        raise ScrubInputsUnknown(unknown)
    return RetentionInputs(frozenset(active), frozenset(works), frozenset(gated))


def select(
    tickets: dict,
    events,
    active_receipts: set[str],
    receipt_works: set[str],
    gated: set[str] | frozenset[str] = frozenset(),
) -> Selection:
    """Apply the retention rule to one parsed BOARD.

    Pure: `tickets` is `parse_board(...)["tickets"]`, `events` the complete
    history, and the two sets are `intake.active_receipt_works`. Nothing is read from
    disk here, so the operation plans on exactly the documents it will bind.
    """
    done = [tid for tid, ticket in tickets.items() if ticket.get("section") == "## DONE"]
    proven = closed_in_history(events, done)
    by_receipt: dict[str, set[str]] = {}
    for tid, ticket in tickets.items():
        for receipt in _receipts_named(ticket):
            by_receipt.setdefault(receipt, set()).add(tid)

    kept: dict[str, str] = {}
    frontier = [tid for tid, ticket in tickets.items() if ticket.get("section") != "## DONE"]
    for tid in done:
        if tid in receipt_works or _receipts_named(tickets[tid]) & active_receipts:
            kept[tid] = "receipt"
        elif tid in gated:
            kept[tid] = "gate"
        elif tid not in proven:
            kept[tid] = "unproven"
    frontier.extend(kept)
    while frontier:
        for named in _references(tickets[frontier.pop()], by_receipt):
            if named in kept or tickets.get(named, {}).get("section") != "## DONE":
                continue
            kept[named] = "reference"
            frontier.append(named)

    pruned = sorted(
        (tid for tid in done if tid not in kept), key=lambda tid: tickets[tid].get("line_no") or 0
    )
    size = sum(len(str(tickets[tid].get("raw") or "").encode("utf-8")) + 1 for tid in pruned)
    return Selection(tuple(pruned), size, kept)


#: One BOARD record line and the ticket id it opens with.
_ROW_RE = re.compile(r"^\s*[-*]\s*\[[ x/]\]\s*(T-\d+)\b")


def pruned_rows(root: Path, ticket_ids) -> dict[str, tuple[str, str]]:
    """The verbatim rows earlier scrubs moved for these ids (T-2050).

    Returns ``{ticket: (row_text, evidence_path)}``. A scrub removes whole
    physical lines, so the row a restore puts back is the same bytes the BOARD
    held -- nothing is re-rendered and no field is reconstructed. Newest scrub
    wins when a row was pruned twice.
    """
    wanted = {str(tid) for tid in ticket_ids if re.fullmatch(r"T-\d+", str(tid))}
    found: dict[str, tuple[str, str]] = {}
    if not wanted:
        return found
    base = Path(root) / SCRUB_EVIDENCE_ROOT
    if not base.is_dir():
        return found
    for evidence in sorted(base.glob("*/BOARD.md")):
        try:
            text = evidence.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            match = _ROW_RE.match(line)
            if match and match.group(1) in wanted:
                found[match.group(1)] = (line, evidence.relative_to(root).as_posix())
    return found


def restored_board_text(text: str, rows) -> str:
    """Insert verbatim closed records at the head of ``## DONE``.

    Every other byte of the document is preserved: the rows are already
    complete lines in this document's own shape, and only their position
    changes. Raises ``ValueError`` when there is no closed section to restore
    into, so a caller never guesses where a closed record belongs.
    """
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    heading = next(
        (index for index, line in enumerate(lines) if line.strip() == "## DONE"), None
    )
    if heading is None:
        raise ValueError("the BOARD has no ## DONE section to restore into")
    body = list(rows)
    if not body:
        return text
    return eol.join(lines[: heading + 1] + body + lines[heading + 1 :])

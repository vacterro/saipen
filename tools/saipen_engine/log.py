"""LOG event parsing -- the shared primitive."""

from __future__ import annotations

import re

import hashlib
from dataclasses import dataclass
from pathlib import Path

LOG_RE = re.compile(
    r"^- (\d{2}[./]\d{2}[./]\d{2} \d{2}:\d{2} )?"
    r"\[E-(\d+)\]"
    r"(?: \[parent: E-(\d+)\])?"
    r"(?: \[(T-[^\]]*)\])?"
    r"(?: \[agent: ([^\]]+)\])?"
    r"(?: \[op: ([^\]]+)\])?"
    r" ([A-Z]+): (.*)$")


def parse_log_line(line: str) -> dict | None:
    """Parse one LOG line into {date, event, parent, ticket, agent, op_id,
    taxonomy, text} or None. The optional RFC § 1.2 date is captured (not
    discarded) so consumers can report the event's own timestamp."""
    m = LOG_RE.match(line)
    if not m:
        return None
    return {
        "date": m.group(1).rstrip() if m.group(1) else None,
        "event": int(m.group(2)),
        "parent": int(m.group(3)) if m.group(3) else None,
        "ticket": m.group(4),
        "agent": m.group(5),
        "op_id": m.group(6),
        "taxonomy": m.group(7),
        "text": m.group(8),
    }


def _segment_number(path: Path | str) -> int:
    name = Path(path).name
    m = re.match(r"^LOG-(\d+)\.md$", name)
    return int(m.group(1)) if m else -1


def history_paths(project_root: Path | str) -> list[Path]:
    """All canonical LOG paths in strict numeric order: sealed LOG-N + active LOG.md."""
    root = Path(project_root)
    logs_dir = root / ".saipen" / "logs"
    sealed = []
    if logs_dir.is_dir():
        for p in logs_dir.iterdir():
            if p.is_file() and _segment_number(p) >= 0:
                sealed.append(p)
        sealed.sort(key=_segment_number)
    active = root / ".saipen" / "LOG.md"
    return [*sealed, active]


@dataclass(frozen=True)
class HistorySnapshot:
    """ONE non-persistent pass over the complete LOG history.

    Holds the exact raw-byte hash, the combined LF-normalised text, the
    global max E-ID and the parsed events -- all derived from a single
    read of every numeric sealed segment + active LOG. Consumers request
    one snapshot per command and reuse it; nothing is cached across
    commands, so append/seal changes are immediately visible.
    """
    hash: str
    text: str
    tail: int | None
    events: tuple[dict, ...]


def _normalised_doc_text(raw: bytes) -> str:
    """Decode exactly as `codec.read_doc` would (LF-normalised text)."""
    from . import codec
    text, _encoding, _bom = codec._decode(raw)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_history_snapshot(project_root: Path | str) -> HistorySnapshot:
    """One pass over the complete LOG history (sealed + active).

    Each segment file is opened exactly once; the exact raw bytes feed the
    hash and the decoded text feeds parsing and the combined text. Event
    ordering and parser semantics are identical to the historical
    per-consumer readers.
    """
    root = Path(project_root)
    h = hashlib.sha256()
    chunks: list[str] = []
    events: list[dict] = []
    for p in history_paths(root):
        if not p.is_file():
            continue
        raw = p.read_bytes()
        h.update(raw)
        text = _normalised_doc_text(raw)
        chunks.append(text)
        for line in text.splitlines():
            parsed = parse_log_line(line)
            if parsed is not None:
                events.append(parsed)
    tail = None
    for ev in events:
        if tail is None or ev["event"] > tail:
            tail = ev["event"]
    return HistorySnapshot(
        hash=h.hexdigest()[:16],
        text="\n".join(chunks),
        tail=tail,
        events=tuple(events),
    )


def read_history(project_root: Path | str) -> str:
    """The complete combined LOG text across sealed segments and active LOG.md."""
    return read_history_snapshot(project_root).text


def read_history_events(project_root: Path | str) -> list[dict]:
    """All parsed events across the complete LOG history."""
    return list(read_history_snapshot(project_root).events)


def history_hash(project_root: Path | str) -> str:
    """Deterministic hash over all history files (sealed + active)."""
    return read_history_snapshot(project_root).hash


def history_log_tail(project_root: Path | str) -> int | None:
    """The global max E-ID across all sealed segments and active LOG.md."""
    return read_history_snapshot(project_root).tail


def log_tail_event(text: str) -> int | None:
    """The actual maximum E-### across the LOG text (sealed + active as one).

    Order-independent by contract: allocation correctness never depends on
    line or file ordering, so E-100 followed by E-9 is still 100 (red control).
    """
    highest = None
    for line in text.splitlines():
        parsed = parse_log_line(line)
        if parsed is not None:
            event = parsed["event"]
            if highest is None or event > highest:
                highest = event
    return highest


VALID_TAXONOMIES = frozenset({
    "DEC", "RUN", "WAIT", "REVERT", "NOTE", "OPS",
})


def build_event(tail: int | None, taxonomy: str, message: str,
                ticket: str | None = None,
                agent: str | None = None,
                now: str | None = None,
                op_id: str | None = None) -> tuple[int, str]:
    """The ONE mechanical LOG event builder (NITRO integrity).

    Given the current LOG tail E-N, allocates E-(N+1) with parent E-N, renders
    the full line skeleton (date, E-ID, parent, optional ticket/agent/op_id,
    taxonomy, payload), and returns (event_id, line) WITHOUT the trailing
    newline. Every operation uses this; no caller hand-concatenates LOG
    structure.

    `op_id` is the SAIOPS operation provenance marker: structural mutations
    carry `[op: <op_id>]` so post-migration validator/audit can detect a
    manual structural edit that bypassed the engine.

    `now` is a "dd.MM.yy HH:mm" timestamp; the caller supplies it so PLAN and
    APPLY of one operation share one frozen clock.
    """
    if taxonomy not in VALID_TAXONOMIES:
        raise ValueError(
            f"taxonomy {taxonomy!r} outside {sorted(VALID_TAXONOMIES)}")
    if now is None:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%d.%m.%y %H:%M")
    event = (tail or 0) + 1
    parts = [f"- {now} [E-{event}]"]
    if tail:
        parts.append(f"[parent: E-{tail}]")
    if ticket:
        parts.append(f"[{ticket}]")
    if agent:
        parts.append(f"[agent: {agent}]")
    if op_id:
        parts.append(f"[op: {op_id}]")
    parts.append(f"{taxonomy}: {message}")
    return event, " ".join(parts)


_VERIFY_BOUNDARY_RE = re.compile(r"^transition to VERIFY(?: -- .*)?$")
_VERIFY_BOUNDARY_PREFIX = "transition to VERIFY -- "
_NEGATION_RE = re.compile(r"\bNOT\s+(?:PASS|MANUAL-VERIFY)\b",
                          re.IGNORECASE)
_PASS_TOKEN_RE = re.compile(r"\bPASS\b")
_MANUAL_TOKEN_RE = re.compile(r"\bMANUAL-VERIFY\b")


def _is_verify_boundary(ev: dict) -> bool:
    """True iff `ev` is the EXACT machine-owned VERIFY entry marker.

    The boundary text is owned by the engine (`_plan_transition` always
    writes `transition to VERIFY`, optionally followed by ` -- <reason>`).
    A transition whose marker was replaced by caller-supplied prose is NOT
    a boundary: the engine can no longer tell where verification started,
    so the ticket is unproven (hostile-regression, machine-owned grammar).
    """
    txt = ev.get("text", "")
    return txt == "transition to VERIFY" or txt.startswith(
        _VERIFY_BOUNDARY_PREFIX)


def verification_evidence(ticket_id: str, events: list[dict]) -> tuple[bool, str]:
    """Classify verification evidence for a ticket (hostile-regression).

    Machine-owned grammar. Searches backwards from the end of the history:

    - the boundary is the LATEST exact VERIFY entry marker
      (`transition to VERIFY` or `transition to VERIFY -- <reason>`) for
      this ticket; a replaced/forged marker is not a boundary;
    - only RUN events for the ticket AFTER that boundary count (the
      current verification cycle);
    - negative evidence wins: `FAIL`, `NOT PASS` or `NOT MANUAL-VERIFY`
      fails immediately;
    - PASS evidence is the exact `PASS` token (word-boundary, so e.g.
      COMPASS never matches) with the exact `conf: high` marker; an
      explicit `conf: low`/`conf: med` disqualifies;
    - MANUAL-VERIFY evidence is the exact `MANUAL-VERIFY` token not
      negated;
    - no boundary or no evidence after it -> unproven/failed.
    """
    if not ticket_id:
        return False, "no ticket id provided"

    verify_start_idx = None
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.get("ticket") == ticket_id and ev.get("taxonomy") == "RUN":
            if _is_verify_boundary(ev):
                verify_start_idx = i
                break
    if verify_start_idx is None:
        return False, "no current-cycle VERIFY boundary"

    for i in range(len(events) - 1, verify_start_idx - 1, -1):
        ev = events[i]
        if ev.get("ticket") != ticket_id or ev.get("taxonomy") != "RUN":
            continue
        txt = ev.get("text", "")
        if "FAIL" in txt or _NEGATION_RE.search(txt):
            return False, txt
        if _MANUAL_TOKEN_RE.search(txt):
            return True, txt
        if _PASS_TOKEN_RE.search(txt):
            if "conf: low" in txt or "conf: med" in txt:
                return False, txt
            if "conf: high" in txt:
                return True, txt

    return False, "unproven/failed"

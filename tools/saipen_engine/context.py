"""Context compiler -- saipen context cold/hot/audit (NITRO M9).

Consumes the NOW-TRUSTWORTHY mechanical layer: the engine's parsers
(saipen_engine.state/board/log), ProjectSnapshot, and the phase DFA. It emits
BOUNDED compact surfaces a cold/hot agent consumes instead of re-reading raw
canonical files. All read-only: zero bytes written.

- `context cold`: the minimal cold-start surface (STATE fields + BOARD ticket
  map + LOG tail + phase-doc routing) as a compact deterministic artifact.
- `context hot`: the current-work surface (status + next + active ticket +
  recent LOG events + recovery state).
- `context audit`: a bounded bytes/tokens accounting per source, with the
  repeated-unchanged-bytes line called out (the NITRO token-optimization
  priority: fresh reasoning surface over nominal cached count).

The compiler NEVER re-parses: every field is derived through the shared
parsers/snapshot, so it cannot drift from what the engine sees.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import codec, phases
from .board import parse_board
from .log import log_tail_event, parse_log_line
from .result import Result
from .snapshot import ProjectSnapshot
from .state import parse_state

_TAIL_EVENTS = 12


def _tokens(text: str) -> int:
    """Rough deterministic token estimate: words + punctuation clusters."""
    words = len(re.findall(r"\b\w+\b", text))
    symbols = len(re.findall(r"[^\w\s]", text))
    return words + symbols


def _bytes(text: str) -> int:
    """REAL UTF-8 byte count -- len(str) counts characters, not bytes, and
    this protocol is multilingual (NITRO dogfood II)."""
    return len(text.encode("utf-8"))


def _bounded(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... (truncated {len(text) - limit} chars)"


def _state_fields(state: dict) -> str:
    lines = []
    for key in ("phase", "task", "next_action", "blocker", "agent",
                "execution_intent", "goal_waves", "goal_tickets",
                "last_event", "updated"):
        if key in state:
            lines.append(f"{key}: {state[key]}")
    return "\n".join(lines)


def _board_map(board: dict, full_ticket: str | None = None) -> str:
    """Board projection: FULL exact text for the one ticket the model must
    execute (never truncated: needs + verify + description preserved), compact
    one-line map for the rest (NITRO dogfood II)."""
    lines = []
    for section in ("## DOING", "## TODO", "## BLOCKED", "## DONE"):
        tickets = [t for t in board["tickets"].values()
                   if t["section"] == section]
        lines.append(f"{section} ({len(tickets)})")
        for ticket in tickets:
            if full_ticket and ticket["id"] == full_ticket:
                lines.append(f"  - {ticket['raw'].strip()}")
                continue
            desc = (ticket["description"] or "").replace(" | ", " / ")
            lines.append(f"  - {ticket['id']} [{ticket['checkbox']}] "
                         f"{desc[:80]}")
        if len(tickets) > 8:
            lines.append(f"  ... +{len(tickets) - 8} more")
    return "\n".join(lines)


def _log_tail(log_text: str, count: int = _TAIL_EVENTS) -> str:
    events = [line for line in log_text.splitlines()
              if parse_log_line(line) is not None]
    return "\n".join(events[-count:]) if events else "(no events)"


def context_cold(project_root: Path | str, limit: int = 4000) -> Result:
    """Minimal cold-start surface: STATE + exact next ticket + compact BOARD
    map + LOG tail + routing. Uses the SHARED router (NITRO dogfood II), so
    it cannot echo a stale next_action."""
    root = Path(project_root)
    state_text = codec.read_doc(root / ".saipen" / "STATE.md")
    board_text = codec.read_doc(root / ".saipen" / "BOARD.md")
    log_text = codec.read_doc(root / ".saipen" / "LOG.md")
    state = parse_state(state_text)
    board = parse_board(board_text)
    phase = state.get("phase", "DONE")
    doc = f"saipen/phases/{str(phase).lower()}.md" if phase else ""
    from .journal import pending_conflicts, pending_ops
    pending = [op["op_id"] for op in pending_ops(root)]
    conflicts = [op["op_id"] for op in pending_conflicts(root)]
    from .router import route_next
    routed = route_next(state_text, board_text, pending, conflicts)
    next_ticket = routed.get("ticket")
    out = [
        "# SAIPEN COLD CONTEXT",
        "",
        "## STATE",
        _state_fields(state),
        "",
        "## ROUTED NEXT",
        f"action: {routed.get('action')}",
        f"reason: {routed.get('reason')}",
        f"ticket: {next_ticket or 'none'}",
        "",
        "## BOARD",
        _board_map(board, full_ticket=next_ticket),
        "",
        "## LOG TAIL",
        _log_tail(log_text),
        "",
        "## ROUTING",
        f"phase_doc: {doc}",
        f"recovery_pending: {bool(pending)}",
        f"recovery_conflict: {bool(conflicts)}",
        f"conflict_ops: {', '.join(conflicts) or 'none'}",
    ]
    body = "\n".join(out) + "\n"
    return Result(ok=True, code="CONTEXT_COLD", data={
        "surface": _bounded(body, limit),
        "bytes": _bytes(body),
        "characters": len(body),
        "tokens": _tokens(body),
    })


def context_hot(project_root: Path | str, limit: int = 3000) -> Result:
    """Current-work surface: STATE + computed next + active ticket + recent
    LOG + recovery state. Shares the router (NITRO dogfood II)."""
    root = Path(project_root)
    snap = ProjectSnapshot.capture(root)
    state_text = codec.read_doc(root / ".saipen" / "STATE.md")
    board_text = codec.read_doc(root / ".saipen" / "BOARD.md")
    log_text = codec.read_doc(root / ".saipen" / "LOG.md")
    state = parse_state(state_text)
    board = parse_board(board_text)
    doing = [t for t in board["tickets"].values()
             if t["section"] == "## DOING"]
    from .journal import pending_conflicts, pending_ops
    pending = [op["op_id"] for op in pending_ops(root)]
    conflicts = [op["op_id"] for op in pending_conflicts(root)]
    from .router import route_next
    routed = route_next(state_text, board_text, pending, conflicts)
    out = [
        "# SAIPEN HOT CONTEXT",
        "",
        "## NOW",
        _state_fields(state),
        f"claimed_ticket: {doing[0]['id'] if doing else None}",
        "",
        "## COMPUTED NEXT",
        f"action: {routed.get('action')}",
        f"reason: {routed.get('reason')}",
        f"ticket: {routed.get('ticket') or 'none'}",
        "",
        "## RECENT LOG",
        _log_tail(log_text),
        "",
        "## MACHINE",
        f"recovery_pending: {bool(pending)}",
        f"recovery_conflict: {bool(conflicts)}",
        f"pending_ops: {', '.join(pending) or 'none'}",
        f"log_tail_event: {snap.log_tail}",
    ]
    body = "\n".join(out) + "\n"
    return Result(ok=True, code="CONTEXT_HOT", data={
        "surface": _bounded(body, limit),
        "bytes": _bytes(body),
        "characters": len(body),
        "tokens": _tokens(body),
    })


def context_audit(project_root: Path | str) -> Result:
    """Bytes/tokens accounting per source with an HONEST projection metric.

    `projection_reduction_bytes` = raw canonical bytes minus cold-surface
    bytes: it measures what the projection omits, NOT what is "unchanged"
    across revisions (NITRO dogfood II renames the old dishonest
    repeated_unchanged_bytes)."""
    root = Path(project_root)
    sources = {
        "STATE.md": codec.read_doc(root / ".saipen" / "STATE.md"),
        "BOARD.md": codec.read_doc(root / ".saipen" / "BOARD.md"),
        "LOG.md (active)": codec.read_doc(root / ".saipen" / "LOG.md"),
    }
    snap = ProjectSnapshot.capture(root)
    from .journal import pending_ops
    pending = len(pending_ops(root))
    rows = []
    for name, text in sources.items():
        rows.append({
            "source": name,
            "bytes": _bytes(text),
            "characters": len(text),
            "tokens": _tokens(text),
        })
    total_bytes = sum(r["bytes"] for r in rows)
    cold = context_cold(root)
    hot = context_hot(root)
    audit = {
        "sources": rows,
        "total_bytes": total_bytes,
        "cold_surface": {"bytes": cold.get("bytes"), "tokens": cold.get(
            "tokens")},
        "hot_surface": {"bytes": hot.get("bytes"), "tokens": hot.get("tokens")},
        "projection_reduction_bytes": total_bytes - cold.get("bytes", 0),
        "note": ("projection_reduction_bytes = raw canonical bytes minus "
                 "cold-surface bytes; it measures what the projection omits, "
                 "never 'unchanged across revisions' (no historical comparison "
                 "is made)"),
        "log_tail_event": snap.log_tail,
        "recovery_pending": pending,
    }
    return Result(ok=True, code="CONTEXT_AUDIT", data=audit)

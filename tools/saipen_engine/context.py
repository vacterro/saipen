"""Context compiler -- saipen context cold/hot/audit (NITRO M9 + IV, T-600).

Consumes the NOW-TRUSTWORTHY mechanical layer: the engine's parsers
(saipen_engine.state/board/log), ProjectSnapshot, and the phase DFA. It emits
BOUNDED compact surfaces a cold/hot agent consumes instead of re-reading raw
canonical files. All read-only: zero bytes written.

- `context cold`: the minimal cold-start surface (STATE fields + exact next
  ticket + BOARD orientation map + LOG tail + phase-doc routing) as a compact
  deterministic artifact.
- `context hot`: the current-work surface (status + next + active ticket +
  recent LOG events + recovery state).
- `context audit`: a bounded bytes/tokens accounting per source, with an
  HONEST projection metric (projection_reduction_bytes = raw canonical bytes
  minus cold-surface bytes -- never a claim about "unchanged" revisions).

PROJECTION INTEGRITY (NITRO dogfood IV, T-600):

- STRUCTURAL BUDGETING, never global string chopping. Mandatory sections are
  emitted in FULL and are never truncated away; only the optional orientation
  (BOARD MAP) and bounded evidence (LOG tail) shrink, in that priority order.
  Priority: recovery/conflict > computed next action > exact full active/next
  ticket > STATE essentials > required routed phase doc > exact needs/verify >
  bounded LOG evidence > optional BOARD orientation.
- The exact routed/active ticket lives in a protected `## NEXT TICKET`
  section OUTSIDE any orientation truncation; the BOARD MAP is a bounded
  orientation that at most shows N non-protected entries and then a truthful
  `... +K more`.
- METRICS DESCRIBE THE EMITTED SURFACE. bytes == len(surface.encode('utf-8')),
  characters == len(surface), tokens are estimated from the exact surface.
  pre_bound_bytes / truncation_bytes are reported SEPARATELY as projection
  economics, never labeled as model-visible bytes.

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
_BOARD_CAP = 8


def _tokens(text: str) -> int:
    """Rough deterministic token estimate: words + punctuation clusters."""
    words = len(re.findall(r"\b\w+\b", text))
    symbols = len(re.findall(r"[^\w\s]", text))
    return words + symbols


def _bytes(text: str) -> int:
    """REAL UTF-8 byte count -- len(str) counts characters, not bytes, and
    this protocol is multilingual (NITRO dogfood II)."""
    return len(text.encode("utf-8"))


def _state_fields(state: dict) -> str:
    lines = []
    for key in ("phase", "task", "next_action", "blocker", "agent",
                "execution_intent", "goal_waves", "goal_tickets",
                "last_event", "updated"):
        if key in state:
            lines.append(f"{key}: {state[key]}")
    return "\n".join(lines)


def _board_map(board: dict, full_ticket: str | None = None,
               cap: int = _BOARD_CAP) -> str:
    """Board ORIENTATION projection, TRUTHFULLY bounded (NITRO dogfood IV,
    T-600).

    At most `cap` NON-protected entries are emitted per section, followed by
    a truthful `... +K more` naming the exact number omitted. The exact
    routed/active ticket is a protected exception: it is ALWAYS emitted in
    full (raw line, needs + verify + description intact) and never counts
    against the cap. The old projection printed every ticket AND then
    '+N more' -- logically false; this one prints N, then names the real K.
    """
    lines = []
    for section in ("## DOING", "## TODO", "## BLOCKED", "## DONE"):
        tickets = [t for t in board["tickets"].values()
                   if t["section"] == section]
        lines.append(f"{section} ({len(tickets)})")
        emitted = 0
        skipped = 0
        for ticket in tickets:
            if full_ticket and ticket["id"] == full_ticket:
                lines.append(f"  - {ticket['raw'].strip()}")
                continue
            if emitted >= cap:
                skipped += 1
                continue
            desc = (ticket["description"] or "").replace(" | ", " / ")
            lines.append(f"  - {ticket['id']} [{ticket['checkbox']}] "
                         f"{desc[:80]}")
            emitted += 1
        if skipped:
            lines.append(f"  ... +{skipped} more")
    return "\n".join(lines)


def _next_ticket_section(board: dict, ticket_id: str | None) -> str:
    """The PROTECTED exact-ticket section (NITRO dogfood IV, T-600).

    The complete canonical ticket line -- ID, priority, description, needs,
    verify, blocker -- emitted in full and OUTSIDE any orientation
    truncation. The next ticket can never disappear because DONE history was
    long."""
    if not ticket_id or ticket_id not in board["tickets"]:
        return "no routed ticket"
    return board["tickets"][ticket_id]["raw"].strip()


def _log_tail(log_text: str, count: int = _TAIL_EVENTS) -> str:
    events = [line for line in log_text.splitlines()
              if parse_log_line(line) is not None]
    return "\n".join(events[-count:]) if events else "(no events)"


def _fit(fixed: str, limit: int, board_fn, log_fn) -> tuple[str, str]:
    """STRUCTURAL budgeting (NITRO dogfood IV, T-600).

    `fixed` is the concatenated mandatory prefix -- recovery/conflict, computed
    next action, exact next ticket, STATE essentials, routed phase doc,
    needs/verify -- and is NEVER truncated. The BOARD orientation is the most
    optional section, so it shrinks FIRST (down to its protected-exception
    form); only when it is gone does the bounded LOG evidence shrink. If the
    mandatory prefix alone exceeds the limit, it is still emitted in full: the
    budget is a projection target, never a license to cut the instruction
    required to execute the task. Returns (board_text, log_text).
    """
    for board_cap in (8, 6, 4, 2, 0):
        board_text = board_fn(board_cap)
        log_full = log_fn(12)
        if len(fixed) + len(board_text) + len(log_full) <= limit:
            return board_text, log_full
    for log_count in (12, 10, 8, 6, 4, 2, 0):
        log_text = log_fn(log_count)
        if len(fixed) + len(board_fn(0)) + len(log_text) <= limit:
            return board_fn(0), log_text
    return board_fn(0), log_fn(0)


def context_cold(project_root: Path | str, limit: int = 4000) -> Result:
    """Minimal cold-start surface with STRUCTURAL budgeting.

    Uses the SHARED router (NITRO dogfood II), so it cannot echo a stale
    next_action. Metrics describe the FINAL emitted surface: bytes ==
    len(surface.encode('utf-8')), characters == len(surface) (NITRO dogfood
    IV, T-600)."""
    root = Path(project_root)
    state_text = codec.read_doc(root / ".saipen" / "STATE.md")
    board_text = codec.read_doc(root / ".saipen" / "BOARD.md")
    log_text = codec.read_doc(root / ".saipen" / "LOG.md")
    state = parse_state(state_text)
    board = parse_board(board_text)
    from .journal import pending_conflicts, pending_ops
    pending = [op["op_id"] for op in pending_ops(root)]
    conflicts = [op["op_id"] for op in pending_conflicts(root)]
    from .router import load_for_action, route_next
    routed = route_next(state_text, board_text, pending, conflicts)
    next_ticket = routed.get("ticket")
    # phase_doc derives from the ROUTED action, never from the persisted
    # STATE.phase -- action and instructions can never disagree.
    phase_doc = load_for_action(routed.get("action"))

    # MANDATORY prefix (never truncated): recovery/conflict, computed next
    # action, the exact full next ticket (needs + verify included), STATE
    # essentials, routed phase doc.
    mandatory = [
        "## RECOVERY",
        f"recovery_pending: {bool(pending)}",
        f"recovery_conflict: {bool(conflicts)}",
        f"conflict_ops: {', '.join(conflicts) or 'none'}",
        "",
        "## ROUTED NEXT",
        f"action: {routed.get('action')}",
        f"reason: {routed.get('reason')}",
        f"ticket: {next_ticket or 'none'}",
        "",
        "## NEXT TICKET",
        _next_ticket_section(board, next_ticket),
        "",
        "## STATE",
        _state_fields(state),
        "",
        "## ROUTING",
        f"phase_doc: {phase_doc}",
    ]
    fixed = "\n".join(mandatory) + "\n"

    # FULL unbounded body, for the honest pre-bound economics.
    full_body = fixed + "\n" + (
        "## LOG TAIL\n" + _log_tail(log_text) + "\n"
        "## BOARD MAP\n" + _board_map(board, full_ticket=next_ticket) + "\n")

    # STRUCTURAL fit: BOARD orientation shrinks before LOG evidence.
    board_part, log_part = _fit(
        fixed, limit,
        lambda cap: _board_map(board, full_ticket=next_ticket, cap=cap),
        lambda count: _log_tail(log_text, count))
    body = fixed + "\n" + (
        "## LOG TAIL\n" + log_part + "\n"
        "## BOARD MAP\n" + board_part + "\n")
    pre_bound = len(full_body.encode("utf-8"))
    emitted = len(body.encode("utf-8"))
    return Result(ok=True, code="CONTEXT_COLD", data={
        "surface": body,
        "bytes": emitted,
        "characters": len(body),
        "tokens": _tokens(body),
        "pre_bound_bytes": pre_bound,
        "truncation_bytes": max(0, pre_bound - emitted),
    })


def context_hot(project_root: Path | str, limit: int = 3000) -> Result:
    """Current-work surface: STATE + computed next + active ticket + recent
    LOG + recovery state. Shares the router (NITRO dogfood II); metrics
    describe the emitted surface (NITRO dogfood IV, T-600)."""
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

    fixed = "\n".join([
        "## NOW",
        _state_fields(state),
        f"claimed_ticket: {doing[0]['id'] if doing else None}",
        "",
        "## COMPUTED NEXT",
        f"action: {routed.get('action')}",
        f"reason: {routed.get('reason')}",
        f"ticket: {routed.get('ticket') or 'none'}",
        "",
        "## MACHINE",
        f"recovery_pending: {bool(pending)}",
        f"recovery_conflict: {bool(conflicts)}",
        f"pending_ops: {', '.join(pending) or 'none'}",
        f"log_tail_event: {snap.log_tail}",
    ]) + "\n"
    full_body = fixed + "\n## RECENT LOG\n" + _log_tail(log_text) + "\n"
    log_part = _log_tail(log_text)
    # STRUCTURAL fit: RECENT LOG is the only optional section in hot.
    for count in (12, 10, 8, 6, 4, 2, 0):
        log_part = _log_tail(log_text, count)
        if len(fixed) + len(log_part) <= limit:
            break
    body = fixed + "\n## RECENT LOG\n" + log_part + "\n"
    pre_bound = len(full_body.encode("utf-8"))
    emitted = len(body.encode("utf-8"))
    return Result(ok=True, code="CONTEXT_HOT", data={
        "surface": body,
        "bytes": emitted,
        "characters": len(body),
        "tokens": _tokens(body),
        "pre_bound_bytes": pre_bound,
        "truncation_bytes": max(0, pre_bound - emitted),
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

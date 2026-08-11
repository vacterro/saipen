"""LOG event parsing -- the shared primitive."""

from __future__ import annotations

import re

LOG_RE = re.compile(
    r"^- (?:\d{2}[./]\d{2}[./]\d{2} \d{2}:\d{2} )?"
    r"\[E-(\d+)\]"
    r"(?: \[parent: E-(\d+)\])?"
    r"(?: \[(T-[^\]]*)\])?"
    r"(?: \[agent: ([^\]]+)\])?"
    r"(?: \[op: ([^\]]+)\])?"
    r" ([A-Z]+): (.*)$")


def parse_log_line(line: str) -> dict | None:
    """Parse one LOG line into {event, parent, ticket, agent, op_id, taxonomy,
    text} or None."""
    m = LOG_RE.match(line)
    if not m:
        return None
    return {
        "event": int(m.group(1)),
        "parent": int(m.group(2)) if m.group(2) else None,
        "ticket": m.group(3),
        "agent": m.group(4),
        "op_id": m.group(5),
        "taxonomy": m.group(6),
        "text": m.group(7),
    }


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

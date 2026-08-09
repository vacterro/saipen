"""LOG event parsing -- the shared primitive."""

from __future__ import annotations

import re

LOG_RE = re.compile(
    r"^- (?:\d{2}[./]\d{2}[./]\d{2} \d{2}:\d{2} )?"
    r"\[E-(\d+)\]"
    r"(?: \[parent: E-(\d+)\])?"
    r"(?: \[(T-[^\]]*)\])?"
    r"(?: \[agent: [^\]]+\])?"
    r" ([A-Z]+): (.*)$")


def parse_log_line(line: str) -> dict | None:
    """Parse one LOG line into {event, parent, ticket, taxonomy, text} or None."""
    m = LOG_RE.match(line)
    if not m:
        return None
    return {
        "event": int(m.group(1)),
        "parent": int(m.group(2)) if m.group(2) else None,
        "ticket": m.group(3),
        "taxonomy": m.group(4),
        "text": m.group(5),
    }


def log_tail_event(text: str) -> int | None:
    """The highest E-### in the LOG text (sealed + active read as one)."""
    highest = None
    for line in text.splitlines():
        parsed = parse_log_line(line)
        if parsed is not None:
            highest = parsed["event"]
    return highest

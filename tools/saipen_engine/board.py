"""BOARD ticket parsing -- the shared primitive."""

from __future__ import annotations

import re

REQUIRED_HEADINGS = ["## DOING", "## TODO", "## DONE", "## BLOCKED"]
TICKET_RE = re.compile(r"^- \[([ x/])\] (T-\d+)\s+(.*)$")
PIPE_SENTINEL = "\x00"
KNOWN_FIELDS = frozenset({"needs", "owner", "claim_time", "blocker", "verify",
                          "review_passes", "verify_attempts",
                          "source_reports"})


def parse_board(text: str) -> dict:
    """Walk the board into a ticket map.

    Returns {"tickets": {tid: {...}}, "headings": [...], "errors": [...]}.
    Mirrors the validator's walk exactly so the engine and validate.py cannot
    drift apart. A ticket line preserves its raw text for surgical mutation.
    """
    tickets = {}
    headings = []
    errors = []
    section = None
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            section = line.strip()
            headings.append(section)
            continue
        if not line.strip():
            continue
        if line.lstrip().startswith("- ["):
            m = TICKET_RE.match(line.strip().replace("\\|", PIPE_SENTINEL))
            if not m:
                errors.append(
                    f"BOARD.md:{line_no} ticket-ish line doesn't match "
                    f"RFC section 1.2 shape `- [ ] T-### description`")
                continue
            checkbox, tid, rest = m.groups()
            parts = [p.strip() for p in rest.split(" | ")]
            needs, fields = [], {}
            for part in parts[1:]:
                fm = re.match(r"^([a-z_]+):\s*(.*)$", part)
                if not fm or fm.group(1) not in KNOWN_FIELDS:
                    errors.append(
                        f"BOARD.md:{line_no} ticket {tid} has unrecognized "
                        f"field {part!r}")
                    continue
                fields[fm.group(1)] = fm.group(2)
                if fm.group(1) == "needs":
                    needs = re.findall(r"T-\d+", fm.group(2))
            if tid in tickets:
                errors.append(f"BOARD.md:{line_no} duplicate ticket ID {tid}")
                continue
            tickets[tid] = {
                "id": tid,
                "section": section,
                "line_no": line_no,
                "checkbox": checkbox,
                "needs": needs,
                "fields": fields,
                "raw": line,
                "description": parts[0] if parts else "",
            }
    return {"tickets": tickets, "headings": headings, "errors": errors}


def _fields_split(raw: str) -> list[str]:
    """Split a ticket line into checkbox/prefix and pipe-delimited fields,
    honouring `\\|` escapes."""
    return raw.replace("\\|", PIPE_SENTINEL).split(" | ")


def _fields_join(parts: list[str]) -> str:
    return " | ".join(parts).replace(PIPE_SENTINEL, "\\|")


def set_ticket_field(raw: str, field: str, value: str) -> str:
    """Replace or append `field: value` on a ticket line, preserving every
    other field byte-for-byte."""
    parts = _fields_split(raw)
    out = []
    replaced = False
    pattern = re.compile(rf"^{re.escape(field)}:\s*")
    for part in parts:
        if part.startswith("- ") or pattern.match(part):
            if pattern.match(part):
                if not replaced:
                    out.append(f"{field}: {value}")
                    replaced = True
                    continue
            out.append(part)
            continue
        out.append(part)
    if not replaced:
        out.append(f"{field}: {value}")
    return _fields_join(out)


def remove_ticket_field(raw: str, field: str) -> str:
    """Remove exactly `| field: <value>` structurally. The leftover value
    cannot survive as free text."""
    parts = _fields_split(raw)
    pattern = re.compile(rf"^{re.escape(field)}:\s*")
    kept = [part for part in parts if not pattern.match(part)]
    return _fields_join(kept)

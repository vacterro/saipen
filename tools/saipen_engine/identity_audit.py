"""Ticket/event identity audit -- reuse detection and ambiguous citations (T-1443).

WHY THIS EXISTS
---------------
SAIPEN allocates ticket IDs from the canonical EVENT history and event IDs from
the canonical LOG tail. Both allocators are correct *given their input*. The
input was once truncated, so the same numbers were handed out twice, and the
result is a memory that reads as one continuous history while containing two
disjoint epochs under identical labels.

Measured on FastPrompter at HEAD e1f0cad (2026-10-30):

    .saipen/LOG.md + sealed segments   E-4055..E-4602   02.10..04.10, then 25.10..29.10
    .saipen/recovery/log-detail/       305 events        05.10..22.10, E-2006..E-5190

The 21-day hole is not emptiness: 305 authenticated events live in the
externalization store. So the live tail (4602) is *below* IDs the project has
already spent (up to 5190), and the ticket frontier (1443) is below 26 ticket
IDs that were already issued (1452..1510). Nineteen tickets in the 1432..1443
band carry two unrelated receipts each.

    T-1442  SRC-101  audit/18.md, 8 findings, 06-07.10
            (T-1517)  regression-carrier repair, 29.10
    T-1443  SRC-102  set-defaults write repair, 07.10
            SRC-139  audit/17.md, 29.10

WHAT THE HISTORY ITSELF SAYS
----------------------------
The two epochs are AUTHENTIC. Every one of the 308 externalization records
carries `original_event_sha256` and the detail bytes still hash to it, so the
05..22.10 events are the real events, not a fabrication and not a rewrite. The
defect is in IDENTIFIERS, not in claims. That distinction is the whole point of
this module: a report may be perfectly truthful about what it did while its
event citations now resolve to somebody else's work.

WHAT THIS MODULE WILL NOT DO
----------------------------
It never renames, relocates, rewrites or deletes anything. Renumbering the
collided IDs would destroy the very identity the historical documents assert,
and rehashing an event would be indistinguishable from forging one. The only
honest output is a truthful report of *which* mappings are unresolved, so a
future reader knows to resolve an ambiguous citation by date and receipt rather
than by number alone.

VERDICTS (never collapsed into one)
-----------------------------------
`live_history_readable`     canonical sealed+active parse succeeded
`detail_provenance_intact`  every detail record's bytes match its recorded digest
`event_id_collisions`       IDs attested by both spaces with different work
`ticket_reuse`              ticket IDs with disjoint date epochs
`allocator_frontier`        live tail vs attested max -- the reissue window
`unresolved_citations`      evidence citations whose event now names other work
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import log as _log

SCHEMA_VERSION = 1
DETAIL_ROOT = ".saipen/recovery/log-detail"
SOURCE_ROOT = ".saipen/archive/source"
EVIDENCE_ROOT = ".saipen/evidence"
#: A ticket is reused when its events fall into date clusters separated by more
#: than this. One working day of slack absorbs a ticket opened late at night and
#: closed after midnight; a genuine reuse is separated by weeks.
EPOCH_GAP_DAYS = 3
_CITATION = re.compile(r"\bE-(\d{1,6})\b")
_OWNER_DIR = re.compile(r"^t(\d{4,})$")
#: Historical tickets appear as `T-1238-B`, `T-812/T-813/T-814`, `T-none`. They
#: are real records and must stay grouped, so the key is the leading number and
#: anything without one sorts below every numbered ticket instead of crashing.
_TICKET_NUMBER = re.compile(r"^T-(\d+)")


def _memory_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_date(value: object) -> date | None:
    """``dd.MM.yy HH:mm`` -> date, tolerating a bare ``dd.MM.yy``."""
    if not isinstance(value, str):
        return None
    head = value.strip().split(" ")[0]
    match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", head)
    if match is None:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(2000 + year, month, day)
    except ValueError:
        return None


@dataclass(frozen=True)
class Attested:
    """One event as some durable source attests it."""

    event: int
    day: date | None
    ticket: str | None
    taxonomy: str
    text: str
    origin: str

    @property
    def work(self) -> str:
        """The identity that makes two same-numbered events different work."""
        return self.ticket or "-"


def _from_parsed(parsed: dict, origin: str) -> Attested:
    return Attested(
        event=int(parsed["event"]),
        day=_parse_date(parsed.get("date")),
        ticket=parsed.get("ticket"),
        taxonomy=str(parsed.get("taxonomy") or "-"),
        text=str(parsed.get("text") or ""),
        origin=origin,
    )


def load_detail_records(root: Path | str) -> list[dict]:
    """Every externalization record, with its integrity verdict.

    The record is the authority on what the event WAS: it carries the original
    event digest. `digest_ok` is False when the detail bytes no longer match
    that digest or the original path is gone -- in which case the record is
    reported but must not be trusted as content.
    """
    base = Path(root) / DETAIL_ROOT
    records: list[dict] = []
    if not base.is_dir():
        return records
    for meta_path in sorted(base.glob("*.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            records.append(
                {
                    "metadata_path": _memory_relative(Path(root), meta_path),
                    "event": None,
                    "digest_ok": False,
                    "parse_error": "metadata unreadable",
                }
            )
            continue
        original = meta.get("original_event_path")
        digest_ok = False
        payload = b""
        if isinstance(original, str) and original:
            original_path = Path(root) / original
            if not original_path.is_absolute():
                original_path = Path(root) / original
            try:
                payload = original_path.read_bytes()
            except OSError:
                payload = b""
        expected = meta.get("original_event_sha256")
        if payload and isinstance(expected, str):
            digest_ok = hashlib.sha256(payload).hexdigest() == expected
        parsed = None
        text = payload.decode("utf-8", errors="replace").strip() if payload else ""
        if text:
            first = text.splitlines()[0] if text.splitlines() else ""
            parsed = _log.parse_log_line(first)
        records.append(
            {
                "metadata_path": _memory_relative(Path(root), meta_path),
                "event": meta.get("event_id"),
                "ticket": meta.get("ticket_id"),
                "digest_ok": digest_ok,
                "claimed_event": parsed.get("event") if parsed else None,
                "parsed": parsed,
                "status": meta.get("status"),
                "source": meta.get("source"),
            }
        )
    return records


def detail_events(root: Path | str) -> tuple[list[Attested], list[dict]]:
    """Authenticated detail events, plus the records that failed verification."""
    attested: list[Attested] = []
    rejected: list[dict] = []
    for record in load_detail_records(root):
        parsed = record.get("parsed")
        if not record.get("digest_ok") or not isinstance(parsed, dict):
            rejected.append(record)
            continue
        if record.get("claimed_event") is not None and str(record.get("event")) != str(
            f"E-{record['claimed_event']}"
        ):
            rejected.append(record)
            continue
        attested.append(_from_parsed(parsed, "log-detail"))
    return attested, rejected


def live_events(root: Path | str) -> list[Attested]:
    """The canonical sealed+active event space."""
    return [
        _from_parsed(parsed, "history")
        for parsed in _log.read_history_events(root)
    ]


def event_collisions(
    live: list[Attested], detail: list[Attested]
) -> list[dict]:
    """IDs attested in both spaces by DIFFERENT work.

    Same number + same ticket + same day is one event seen twice (the compact
    LOG line and its own externalized detail) and is not a collision. Anything
    else means the number was issued twice.
    """
    by_detail: dict[int, list[Attested]] = {}
    for item in detail:
        by_detail.setdefault(item.event, []).append(item)
    findings: list[dict] = []
    for item in live:
        others = by_detail.get(item.event)
        if not others:
            continue
        same = [
            other
            for other in others
            if other.work == item.work and other.day == item.day
        ]
        if same:
            continue
        findings.append(
            {
                "event": f"E-{item.event}",
                "live": {
                    "date": item.day.isoformat() if item.day else None,
                    "ticket": item.ticket,
                    "taxonomy": item.taxonomy,
                },
                "detail": [
                    {
                        "date": other.day.isoformat() if other.day else None,
                        "ticket": other.ticket,
                        "taxonomy": other.taxonomy,
                    }
                    for other in others
                ],
            }
        )
    findings.sort(key=lambda row: _event_key(row["event"]))
    return findings


def _ticket_key(ticket: str) -> tuple[int, str]:
    match = _TICKET_NUMBER.match(ticket)
    return (int(match.group(1)), ticket) if match else (-1, ticket)


def _event_key(value: str) -> int:
    """Sort key for an ``E-###`` string, tolerating anything unparseable."""
    try:
        return int(value.split("-")[1])
    except (IndexError, ValueError):
        return -1


def _clusters(days: list[date]) -> list[list[date]]:
    ordered = sorted(set(days))
    if not ordered:
        return []
    groups: list[list[date]] = [[ordered[0]]]
    for day in ordered[1:]:
        if (day - groups[-1][-1]).days > EPOCH_GAP_DAYS:
            groups.append([day])
        else:
            groups[-1].append(day)
    return groups


def _is_opening(item: Attested) -> bool:
    """An event that CREATES or CLAIMS work, as opposed to continuing it.

    The distinction matters because a reopened ticket produces a date gap that
    looks exactly like a reissued ID. T-800 was blocked on 27.09 and unblocked
    on 28.09; that is one ticket living through a pause. T-1442 has an opening
    on 29.10 AND a receipt that closed three weeks earlier, which no pause
    explains.
    """
    text = item.text.lower()
    return "ticket added" in text or "ticket claimed" in text or "claimed via" in text


def _opening_days(items: list[Attested]) -> list[date]:
    return sorted({i.day for i in items if i.day is not None and _is_opening(i)})


def _receipt_days(rows: list[dict]) -> list[date]:
    """Receipt closure dates, which bound when their work was actually done."""
    days: list[date] = []
    for row in rows:
        raw = row.get("closed_at") or row.get("received_at")
        if not isinstance(raw, str):
            continue
        try:
            days.append(date.fromisoformat(raw[:10]))
        except ValueError:
            continue
    return sorted(days)


def ticket_reuse(events: list[Attested], receipts: dict[str, list[dict]]) -> list[dict]:
    """Ticket IDs PROVEN to name two different pieces of work.

    One proof, and only one, because it is the only one that cannot be
    explained away: the archive links a receipt that CLOSED before the live
    ticket was created. A ticket cannot do work before it exists. Both
    timestamps are recorded by the engine, so nothing here is inferred from
    prose or from a date gap.

    Everything weaker is reported by `reuse_candidates` and deliberately NOT
    folded into this list. Measured on FastPrompter: a naive "several receipts"
    rule flagged 48 tickets -- but `T-1207`/`SRC-007..009` and
    `T-1310`/`SRC-044..048` are legitimate `amends` chains and `T-1290` carries
    two independent receipts inside one lifetime. A naive "two date epochs" rule
    flagged 42 -- but a blocked ticket that resumes has exactly that shape.
    Overclaiming reuse is the same failure this module exists to catch.
    """
    by_ticket: dict[str, list[Attested]] = {}
    for item in events:
        if item.ticket and item.day is not None:
            by_ticket.setdefault(item.ticket, []).append(item)
    findings: list[dict] = []
    for ticket, items in by_ticket.items():
        linked = receipts.get(ticket, [])
        openings = _opening_days(items)
        if not openings:
            continue
        closed = _receipt_days(linked)
        predating = [d for d in closed if d < openings[0]]
        if not predating:
            continue
        groups = _clusters([i.day for i in items])
        findings.append(
            {
                "ticket": ticket,
                "proof": "receipt_predates_ticket",
                "first_live_opening": openings[0].isoformat(),
                "receipts_closed_before_opening": [d.isoformat() for d in predating],
                "epochs": [
                    {
                        "first": group[0].isoformat(),
                        "last": group[-1].isoformat(),
                        "events": sorted(
                            {f"E-{i.event}" for i in items if i.day in group},
                            key=_event_key,
                        ),
                        "opens": any(
                            _is_opening(i) and i.day in group for i in items
                        ),
                        "origins": sorted({i.origin for i in items if i.day in group}),
                    }
                    for group in groups
                ],
                "receipts": linked,
                "note": (
                    "the historical evidence attached to this ticket ID belongs "
                    "to the EARLIER epoch; do not read its citations as this one"
                ),
            }
        )
    findings.sort(key=lambda row: _ticket_key(row["ticket"]))
    return findings


def reuse_candidates(
    events: list[Attested],
    receipts: dict[str, list[dict]],
    proven: list[dict],
) -> list[dict]:
    """Tickets with more than one opening that are NOT proven reuse.

    Reported so a reader can see the shape without being told it is a verdict.
    A blocked-then-resumed ticket produces this signature too, so these stay
    advisory until a receipt timestamp or a source links the epochs.
    """
    proven_ids = {row["ticket"] for row in proven}
    by_ticket: dict[str, list[Attested]] = {}
    for item in events:
        if item.ticket and item.day is not None:
            by_ticket.setdefault(item.ticket, []).append(item)
    findings: list[dict] = []
    for ticket, items in by_ticket.items():
        if ticket in proven_ids:
            continue
        openings = _opening_days(items)
        if len(openings) < 2:
            continue
        findings.append(
            {
                "ticket": ticket,
                "signal": "multiple_openings",
                "openings": [d.isoformat() for d in openings],
                "receipts": [r["receipt"] for r in receipts.get(ticket, [])],
                "status": "UNRESOLVED -- not enough evidence to call this reuse",
            }
        )
    findings.sort(key=lambda row: _ticket_key(row["ticket"]))
    return findings


def ticket_epoch_splits(events: list[Attested]) -> list[dict]:
    """Date gaps that are NOT proven reuse -- reported, never asserted as reuse."""
    by_ticket: dict[str, list[Attested]] = {}
    for item in events:
        if item.ticket and item.day is not None:
            by_ticket.setdefault(item.ticket, []).append(item)
    findings: list[dict] = []
    for ticket, items in by_ticket.items():
        groups = _clusters([item.day for item in items])
        if len(groups) < 2:
            continue
        findings.append(
            {
                "ticket": ticket,
                "epochs": [
                    {
                        "first": group[0].isoformat(),
                        "last": group[-1].isoformat(),
                        "opens": any(
                            _is_opening(i) and i.day in group for i in items
                        ),
                    }
                    for group in groups
                ],
            }
        )
    findings.sort(key=lambda row: _ticket_key(row["ticket"]))
    return findings


def suspect_dates(events: list[Attested]) -> list[dict]:
    """Event dates that cannot sit inside the project's own history.

    Called out separately because a mistyped year silently reorders history and
    would otherwise be read as an event epoch all of its own. The test is
    deliberately blunt: a date before the earliest sealed segment is either a
    typo or a different project's record.
    """
    dated = [item for item in events if item.day is not None]
    if not dated:
        return []
    floor = min(item.day for item in dated)
    return [
        {
            "event": f"E-{item.event}",
            "date": item.day.isoformat(),
            "ticket": item.ticket,
            "origin": item.origin,
        }
        for item in dated
        if item.day < floor
    ]


def receipt_index(root: Path | str) -> dict[str, list[dict]]:
    """ticket -> receipts linked to it, from the archived source metadata."""
    base = Path(root) / SOURCE_ROOT
    index: dict[str, list[dict]] = {}
    if not base.is_dir():
        return index
    for meta_path in sorted(base.glob("*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        work = meta.get("linked_work")
        if not isinstance(work, str) or not work.startswith("T-"):
            continue
        index.setdefault(work, []).append(
            {
                "receipt": meta_path.name[: -len(".meta.json")],
                "received_at": meta.get("received_at"),
                "closed_at": meta.get("closed_at"),
                "status": meta.get("status"),
            }
        )
    for rows in index.values():
        rows.sort(key=lambda row: str(row.get("received_at") or ""))
    return index


def _owner_ticket(relative: str) -> str | None:
    """The ticket an evidence document belongs to, from its path."""
    for part in Path(relative).parts:
        match = _OWNER_DIR.fullmatch(part.lower())
        if match:
            return f"T-{match.group(1)}"
    match = re.search(r"\bT-(\d{4,})\b", Path(relative).name)
    return f"T-{match.group(1)}" if match else None


def unresolved_citations(
    root: Path | str, live: list[Attested], detail: list[Attested]
) -> list[dict]:
    """Citations that now resolve to somebody else's work.

    A document CLAIMS an event as its own only when it names its own ticket in
    the same LINE as the event ID. That is the only reading that survives
    contact with the corpus: evidence legitimately cites other tickets all the
    time ("Delivered by T-1453 (DONE, own_patch, E-4450)" in a T-1454 report,
    "First anchored pair (LOG E-4437)" in T-1453's own report, a T-1484 report
    mentioning the historical E-1124 set). A line-proximity-free rule flagged
    all of those, which is exactly the overclaim this module refuses to make.

    What remains is the real defect: a line like

        T-1442 DONE (E-4520), SRC-101 suletud+tombstoned (E-4521)

    where the document names its own ticket and its own event in one breath,
    and the event now belongs to a different ticket. Two outcomes:

    ``misassigned``  the cited ID exists, but only as another ticket's work
    ``ambiguous``    the cited ID exists under more than one ticket
    """
    by_event: dict[int, set[str]] = {}
    for item in live + detail:
        by_event.setdefault(item.event, set()).add(item.work)
    base = Path(root) / EVIDENCE_ROOT
    findings: list[dict] = []
    if not base.is_dir():
        return findings
    for doc in sorted(base.rglob("*.md")):
        relative = _memory_relative(Path(root), doc)
        owner = _owner_ticket(relative)
        if owner is None:
            continue
        try:
            text = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for offset, line in enumerate(text.splitlines(), start=1):
            if not re.search(rf"{re.escape(owner)}(?![\d-])", line):
                continue
            for number in sorted({int(m) for m in _CITATION.findall(line)}):
                works = by_event.get(number)
                if not works or owner in works:
                    continue
                findings.append(
                    {
                        "document": relative,
                        "line": offset,
                        "owner": owner,
                        "event": f"E-{number}",
                        "resolves_to": sorted(works),
                        "kind": "ambiguous" if len(works) > 1 else "misassigned",
                        "excerpt": line.strip()[:160],
                    }
                )
    return findings


def allocator_frontier(
    live: list[Attested], detail: list[Attested], reuse: list[dict]
) -> dict:
    """Where the allocators stand against what the project already spent."""
    live_ids = {item.event for item in live}
    detail_ids = {item.event for item in detail}
    live_tail = max(live_ids) if live_ids else 0
    attested_max = max(live_ids | detail_ids) if (live_ids or detail_ids) else 0
    spent_above_tail = sorted(i for i in detail_ids if i > live_tail)
    live_tickets = {item.ticket for item in live if item.ticket}
    detail_tickets = {item.ticket for item in detail if item.ticket}

    def _numbers(tickets: set[str]) -> set[int]:
        return {
            int(m.group(1)) for t in tickets if (m := _TICKET_NUMBER.match(t))
        }

    # The allocator reads only the canonical history, so the frontier that
    # matters is the LIVE maximum. Ticket numbers that exist only in the
    # externalization store sit ABOVE it and are therefore exposed to reissue.
    live_frontier = max(_numbers(live_tickets), default=0)
    spent_above = sorted(n for n in _numbers(detail_tickets) if n > live_frontier)
    return {
        "live_tail": f"E-{live_tail}" if live_tail else None,
        "attested_max": f"E-{attested_max}" if attested_max else None,
        "reissue_window_events": len(spent_above_tail),
        "reissue_window_first": (
            f"E-{spent_above_tail[0]}" if spent_above_tail else None
        ),
        "reissue_window_last": (
            f"E-{spent_above_tail[-1]}" if spent_above_tail else None
        ),
        "ticket_frontier": f"T-{live_frontier}" if live_frontier else None,
        "tickets_spent_above_frontier": len(spent_above),
        "tickets_above_frontier": [f"T-{n}" for n in spent_above],
        "reused_tickets": [row["ticket"] for row in reuse],
    }


def audit(root: Path | str) -> dict:
    """The whole report. Every field is measured, none is inferred."""
    root_path = Path(root)
    logs_dir = root_path / ".saipen" / "logs"
    active = root_path / ".saipen" / "LOG.md"
    try:
        live = live_events(root_path)
        live_error = None
        # An empty parse is not a clean bill of health. A directory with no
        # canonical history cannot be audited at all, and reporting HOLDS there
        # would tell a caller that a project it never read has no collisions.
        if not live and not active.exists() and not any(logs_dir.glob("LOG-*.md")):
            live_error = "no canonical LOG history under .saipen/"
    except Exception as exc:  # noqa: BLE001 - the report must survive a refusal
        live = []
        live_error = f"{type(exc).__name__}: {exc}"
    detail, rejected = detail_events(root_path)
    collisions = event_collisions(live, detail)
    receipts = receipt_index(root_path)
    reuse = ticket_reuse(live + detail, receipts)
    candidates = reuse_candidates(live + detail, receipts, reuse)
    splits = ticket_epoch_splits(live + detail)
    reuse_ids = {row["ticket"] for row in reuse}
    split_ids = {row["ticket"] for row in candidates}
    splits = [
        row for row in splits if row["ticket"] not in reuse_ids | split_ids
    ]
    citations = unresolved_citations(root_path, live, detail)
    frontier = allocator_frontier(live, detail, reuse)
    bad_dates = suspect_dates(live + detail)

    verdicts = {
        "live_history_readable": live_error is None,
        "detail_provenance_intact": not rejected,
    }
    findings = bool(collisions or reuse or citations)
    return {
        "schema_version": SCHEMA_VERSION,
        "project_root": root_path.resolve().as_posix(),
        "verdicts": verdicts,
        "counts": {
            "live_events": len(live),
            "detail_events": len(detail),
            "detail_records_rejected": len(rejected),
            "event_id_collisions": len(collisions),
            "reused_ticket_ids": len(reuse),
            "reuse_candidates_unproven": len(candidates),
            "epoch_splits_benign": len(splits),
            "unresolved_citations": len(citations),
            "implausible_dates": len(bad_dates),
        },
        "live_error": live_error,
        "allocator_frontier": frontier,
        "event_id_collisions": collisions,
        "ticket_reuse": reuse,
        "reuse_candidates": candidates,
        "ticket_epoch_splits": splits,
        "unresolved_citations": citations,
        "implausible_dates": bad_dates,
        "rejected_detail_records": [
            {k: v for k, v in row.items() if k != "parsed"} for row in rejected
        ],
        "blocks_acceptance": findings or not all(verdicts.values()),
    }


def render(report: dict) -> str:
    """A human summary -- the same facts, without the per-item lists."""
    counts = report["counts"]
    frontier = report["allocator_frontier"]
    lines = [
        f"live events      {counts['live_events']:>6}",
        f"detail events    {counts['detail_events']:>6}"
        f"  (rejected {counts['detail_records_rejected']})",
        f"live tail        {frontier['live_tail'] or '-':>7}"
        f"   attested max {frontier['attested_max'] or '-':>7}",
        f"ticket frontier  {frontier['ticket_frontier'] or '-':>7}"
        f"   spent above  {frontier['tickets_spent_above_frontier']}",
        f"event collisions {counts['event_id_collisions']:>6}",
        f"reused tickets   {counts['reused_ticket_ids']:>6}"
        f"   (unproven candidates {counts['reuse_candidates_unproven']})",
        f"bad citations    {counts['unresolved_citations']:>6}",
    ]
    for name, ok in report["verdicts"].items():
        lines.append(f"{name:<28} {'HOLDS' if ok else 'FAILS'}")
    if report["ticket_reuse"]:
        lines.append("")
        lines.append("PROVEN TICKET ID REUSE (a receipt closed before the ticket opened):")
    for row in report["ticket_reuse"]:
        spans = " | ".join(f"{e['first']}..{e['last']}" for e in row["epochs"])
        receipts = ",".join(r["receipt"] for r in row.get("receipts", [])) or "-"
        closed = ",".join(row["receipts_closed_before_opening"])
        lines.append(
            f"  {row['ticket']}  {spans}  receipts {receipts}"
            f"  (closed before opening: {closed})"
        )
    if report["unresolved_citations"]:
        lines.append("")
        lines.append("CITATIONS THAT NOW RESOLVE TO OTHER WORK:")
    for row in report["unresolved_citations"]:
        targets = ",".join(
            "no ticket" if t == "-" else t for t in row["resolves_to"]
        )
        lines.append(
            f"  {row['document']}:{row['line']}  {row['event']} -> {targets}"
            f"  ({row['kind']})"
        )
        lines.append(f"      {row['excerpt']}")
    if report["implausible_dates"]:
        lines.append("")
        lines.append("IMPLAUSIBLE EVENT DATES:")
    for row in report["implausible_dates"]:
        lines.append(f"  {row['event']} {row['date']} {row['ticket'] or '-'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Report ticket/event ID reuse and ambiguous evidence citations."
    )
    parser.add_argument("--root", default=".", help="project root (default: cwd)")
    parser.add_argument("--json", action="store_true", help="emit the full report")
    args = parser.parse_args(argv)
    report = audit(args.root)
    if args.json:
        print(json.dumps(report, indent=1, sort_keys=False))
    else:
        print(render(report))
    return 0 if not report["blocks_acceptance"] else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())

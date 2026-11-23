"""T-1679: a typed head that also breaks the ledger contract. patch_t1679.py <tree-root>"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def patch(rel: str, edits: list[tuple[str, str]]) -> None:
    path = ROOT / rel
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        assert text.count(old) == 1, (rel, text.count(old), old[:90])
        text = text.replace(old, new)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", rel, "crlf" if crlf else "lf")


# ---------------------------------------------------------------- lifecycle_authority
patch(
    "tools/saipen_engine/lifecycle_authority.py",
    [
        (
            '''Not covered, and named so nobody reads it as covered: a BOARD row flipped to
DONE with no LOG event and no STATE change leaves no trace this module reads.
Closing that needs the journal to record the terminal set it wrote.
"""
''',
            '''A typed head may also BREAK the ledger: an executor that replaces one of its
own lines leaves a parent edge into nothing, every strict reader refuses
HISTORY_LEDGER_CORRUPT, and nothing above ever runs (T-1679, measured live on
the same project the same night). The floor is still provable -- it needs the
events and the journal, not a valid parent chain -- so the tail quarantine may
cut at the floor where it used to cut only at `STATE.last_event`, a marker the
same hand had moved. The lines leave the LOG for the quarantine's evidence
copy, and the quarantine's own event names the `## DONE` rows they closed; a
row so named and still closed by no operation is `terminal-without-operation`
exactly as if its lines were still above the floor.

Not covered, and named so nobody reads it as covered: a BOARD row flipped to
DONE with no LOG event and no STATE change leaves no trace this module reads.
Closing that needs the journal to record the terminal set it wrote.
"""
''',
        ),
        (
            '''#: Operation classes that move a ticket into `## DONE` (or let an existing
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
''',
            '''#: Operation classes that move a ticket into `## DONE`. A ticket with one of
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
_ROWS_RE = re.compile(re.escape(ROWS_PHRASE) + r"((?:T-\\d+)(?:, T-\\d+)*)")
''',
        ),
        (
            '''        op_id = str(event.get("op_id") or "")
        if op_id.startswith("claim-") and str(event.get("text") or "").startswith(
            "claimed via SAIOPS"
        ):
            epoch = max(epoch, number)
        elif op_id.startswith(CLOSURE_OP_CLASSES):
            closures.append(number)
    return any(number >= epoch for number in closures)
''',
            '''        op_id = str(event.get("op_id") or "")
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


def typed_rows(head_events, board: dict | None, events, floor: int) -> list[str]:
    """The `## DONE` rows a typed head closed: named by its events, closed by
    no operation at or below the floor."""
    numbered = [event for event in (events or ()) if _event_number(event) is not None]
    rows: list[str] = []
    for ticket in sorted({name for event in head_events for name in named_tickets(event)}):
        row = ((board or {}).get("tickets") or {}).get(ticket)
        if not isinstance(row, dict) or row.get("section") != "## DONE":
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
''',
        ),
        (
            '''    root = Path(root)
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
''',
            '''    root = Path(root)
    verdict = {"status": UNAVAILABLE, "floor": None, "head": [], "findings": [], "detail": ""}
    numbered = [event for event in (events or ()) if _event_number(event) is not None]
    floor, head = journal_floor(root, numbered)
    if floor is None:
        return verdict
''',
        ),
        (
            '''    named: dict[str, list[int]] = {}
    for event in head:
        tickets = {event.get("ticket")} | set(_TARGET_RE.findall(event.get("text") or ""))
        for ticket in tickets:
            if ticket:
                named.setdefault(ticket, []).append(_event_number(event))
    for ticket, ticket_events in sorted(named.items()):
''',
            '''    named: dict[str, list[int]] = {}
    for event in head:
        for ticket in named_tickets(event):
            named.setdefault(ticket, []).append(_event_number(event))
    # A typed head that was quarantined left the LOG; its quarantine event
    # carries the rows it had closed, and speaks for them until an operation
    # closes or reopens each one.
    quarantined: dict[str, int] = {}
    for event in numbered:
        text = str(event.get("text") or "")
        if (
            _event_number(event) <= floor
            and str(event.get("op_id") or "").startswith(QUARANTINE_OP_CLASS)
            and TYPED_HEAD_MARKER in text
        ):
            match = _ROWS_RE.search(text)
            for ticket in match.group(1).split(", ") if match else ():
                quarantined[ticket] = _event_number(event)
    for ticket, number in sorted(quarantined.items()):
        if ticket in named:
            continue
        row = ((board or {}).get("tickets") or {}).get(ticket)
        if not isinstance(row, dict) or row.get("section") != "## DONE":
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
                    f"E-{number} quarantined, and no closure operation stands behind "
                    "it -- the completion was typed, not run"
                ),
            }
        )
    for ticket, ticket_events in sorted(named.items()):
''',
        ),
    ],
)

# _ATTESTATION constant: import-free, the literal lives in log.py
patch(
    "tools/saipen_engine/lifecycle_authority.py",
    [(
        '''_TARGET_RE = re.compile(r"\\[target: (T-\\d+)\\]")
''',
        '''_TARGET_RE = re.compile(r"\\[target: (T-\\d+)\\]")

#: `log.LEGACY_DONE_ATTESTATION`, restated here because `log` imports nothing
#: from this module and must not start to; the test module pins the two equal.
_ATTESTATION = "legacy completion attested"
''',
    )],
)

# ---------------------------------------------------------------- log.foreign_tail_cut
patch(
    "tools/saipen_engine/log.py",
    [
        (
            '''    anchor_line: int
    kept_text: str
    suffix_lines: tuple[str, ...]
    claimed_ids: tuple[int, ...]
    non_event_lines: int
    snapshot: HistorySnapshot
''',
            '''    anchor_line: int
    kept_text: str
    suffix_lines: tuple[str, ...]
    claimed_ids: tuple[int, ...]
    non_event_lines: int
    snapshot: HistorySnapshot
    #: Set when the cut is bound by the journal floor instead of
    #: `STATE.last_event` (T-1679): the suffix is a typed head, not a stray tail.
    journal_floor: int | None = None
''',
        ),
        (
            '''def foreign_tail_cut(
    snapshot: HistorySnapshot, active_text: str, last_event: int | None
) -> tuple[ForeignTail | None, str | None]:
''',
            '''def foreign_tail_cut(
    snapshot: HistorySnapshot,
    active_text: str,
    last_event: int | None,
    journal_floor: int | None = None,
) -> tuple[ForeignTail | None, str | None]:
''',
        ),
        (
            '''    * the ledger WITHOUT the suffix passes the complete immutable-ledger
      contract. Damage anywhere else is not a tail problem.
    """
    if last_event is None:
        return None, "STATE.last_event is unset, so there is no checkpointed boundary to cut at"
    lines = active_text.splitlines()
''',
            '''    * the ledger WITHOUT the suffix passes the complete immutable-ledger
      contract. Damage anywhere else is not a tail problem.

    THE JOURNAL BOUND (T-1679). `last_event` is only a boundary while an
    operation wrote it. An executor that types its own lifecycle moves that
    marker onto its own lines, and when it also breaks the parent chain the
    proof above refuses twice over: the typed lines sit at or below the
    marker, so nothing is "suffix", and the ledger is void. `journal_floor`
    is the newest event a journal record stands behind
    (`lifecycle_authority.journal_floor`), supplied by the caller that owns
    the journal. When it lies below `last_event` it is the boundary, and the
    third condition does not apply: an event above the floor cannot be "a
    genuine event whose checkpoint never landed", because a genuine event has
    an operation record and the floor is by definition the newest one that
    does.
    """
    journal = journal_floor is not None and (last_event is None or journal_floor < last_event)
    if journal:
        last_event = journal_floor
    if last_event is None:
        return None, "STATE.last_event is unset, so there is no checkpointed boundary to cut at"
    lines = active_text.splitlines()
''',
        ),
        (
            '''        if declared > last_event:
            return None, (
''',
            '''        if declared > last_event and not journal:
            return None, (
''',
        ),
        (
            '''            claimed_ids=tuple(claimed),
            non_event_lines=len(foreign) - len(claimed),
            snapshot=clean,
        ),
        None,
    )
''',
            '''            claimed_ids=tuple(claimed),
            non_event_lines=len(foreign) - len(claimed),
            snapshot=clean,
            journal_floor=journal_floor if journal else None,
        ),
        None,
    )
''',
        ),
    ],
)

# ---------------------------------------------------------------- operations
patch(
    "tools/saipen_engine/operations.py",
    [
        (
            '''TAIL_QUARANTINE_OBSERVABLE = ("foreign_tail",)
''',
            '''#:
#: T-1679 adds two classes this one caller may look past, because a typed head
#: brings them with it: a STATE the same hand left malformed, and the
#: unauthorized marker the cut itself is about to replace. The quarantine
#: writes the LOG without the suffix and its own event becomes `last_event`;
#: the rows the suffix closed are named in that event for the reconciliation
#: that follows (`lifecycle_authority.quarantine_note`).
TAIL_QUARANTINE_OBSERVABLE = ("foreign_tail", "state", "lifecycle_authority")
''',
        ),
        (
            '''            foreign_tail, foreign_tail_refusal = foreign_tail_cut(
                snapshot, log_doc.text_norm, _bound
            )
''',
            '''            from .lifecycle_authority import journal_floor as _journal_floor

            foreign_tail, foreign_tail_refusal = foreign_tail_cut(
                snapshot,
                log_doc.text_norm,
                _bound,
                journal_floor=_journal_floor(root, snapshot.events)[0],
            )
''',
        ),
        (
            '''    op_id = "quarantine-log-tail-" + uuid4_hex()
    evidence = f"{QUARANTINE_EVIDENCE_ROOT}/{op_id}/LOG.md"
    preserved_bytes = docs["log"].encode(docs["log"].text_norm)
    digest = hashlib.sha256(preserved_bytes).hexdigest()
    preserved = TargetPlan(evidence, "generic", preserved_bytes, "", hash_bytes(preserved_bytes))
    claimed = ", ".join(f"E-{eid}" for eid in cut.claimed_ids[:6]) or "none"
    if len(cut.claimed_ids) > 6:
        claimed += f" (+{len(cut.claimed_ids) - 6})"
    task = state.get("task")

    def mutate(text: str, event: int) -> str:
        return patch_state(text, {"last_event": event, "updated": utc, "agent": agent})

    plan = _state_only_plan(
        root,
        "quarantine_log_tail",
        agent,
        mutate,
        f"LOG foreign tail quarantined: {len(cut.suffix_lines)} line(s) after the "
        f"checkpointed tail at LOG.md:{cut.anchor_line} were never bound by a checkpoint "
        f"(claimed ids {claimed}, all at or below the tail; {cut.non_event_lines} "
        f"non-event line(s)). Original LOG preserved at {evidence} sha256:{digest[:16]}",
''',
            '''    op_id = "quarantine-log-tail-" + uuid4_hex()
    evidence = f"{QUARANTINE_EVIDENCE_ROOT}/{op_id}/LOG.md"
    preserved_bytes = docs["log"].encode(docs["log"].text_norm)
    digest = hashlib.sha256(preserved_bytes).hexdigest()
    preserved = TargetPlan(evidence, "generic", preserved_bytes, "", hash_bytes(preserved_bytes))
    claimed = ", ".join(f"E-{eid}" for eid in cut.claimed_ids[:6]) or "none"
    if len(cut.claimed_ids) > 6:
        claimed += f" (+{len(cut.claimed_ids) - 6})"
    task = state.get("task")
    message = (
        f"LOG foreign tail quarantined: {len(cut.suffix_lines)} line(s) after the "
        f"checkpointed tail at LOG.md:{cut.anchor_line} were never bound by a checkpoint "
        f"(claimed ids {claimed}, all at or below the tail; {cut.non_event_lines} "
        f"non-event line(s)). Original LOG preserved at {evidence} sha256:{digest[:16]}"
    )
    if cut.journal_floor is not None:
        # T-1679: a typed head, cut at the journal floor. Its lines leave the
        # LOG, so the rows they closed are named HERE -- this event is what the
        # reconciliation that follows reads to reopen them. The event carries
        # no ticket tag: STATE.task was typed by the same hand.
        from . import lifecycle_authority as _lifecycle_authority
        from .log import parse_log_line as _parse_cut_line

        cut_events = [
            parsed for parsed in map(_parse_cut_line, cut.suffix_lines) if parsed is not None
        ]
        rows = _lifecycle_authority.typed_rows(
            cut_events, _board, cut.snapshot.events, cut.journal_floor
        )
        message = (
            _lifecycle_authority.quarantine_note(cut.journal_floor, len(cut.suffix_lines), rows)
            + f". Claimed ids {claimed}; {cut.non_event_lines} non-event line(s). "
            f"Original LOG preserved at {evidence} sha256:{digest[:16]}"
        )
        task = None

    def mutate(text: str, event: int) -> str:
        return patch_state(text, {"last_event": event, "updated": utc, "agent": agent})

    plan = _state_only_plan(
        root,
        "quarantine_log_tail",
        agent,
        mutate,
        message,
''',
        ),
        (
            '''            "claimed_ids": [f"E-{eid}" for eid in cut.claimed_ids],
            "non_event_lines": cut.non_event_lines,
            "evidence_path": evidence,
            "evidence_sha256": digest,
        },
''',
            '''            "claimed_ids": [f"E-{eid}" for eid in cut.claimed_ids],
            "non_event_lines": cut.non_event_lines,
            "evidence_path": evidence,
            "evidence_sha256": digest,
            "journal_floor": cut.journal_floor,
        },
''',
        ),
    ],
)

# ---------------------------------------------------------------- reconcile trace
patch(
    "tools/saipen_engine/reconcile.py",
    [(
        '''    head = verdict.get("head") or []
    span = "no event"
    if head:
        span = f"E-{head[0]}" + (f"..E-{head[-1]}" if len(head) > 1 else "")
    plan["trace"] = (
        f"lifecycle authority: {span} above E-{floor} carry no operation record "
        "(written by hand); kept as history, nothing stands on their word"
        + ("; reopened " + ", ".join(unbacked) if unbacked else "")
    )
    return plan
''',
        '''    head = verdict.get("head") or []
    if head:
        span = f"E-{head[0]}" + (f"..E-{head[-1]}" if len(head) > 1 else "")
        plan["trace"] = (
            f"lifecycle authority: {span} above E-{floor} carry no operation record "
            "(written by hand); kept as history, nothing stands on their word"
        )
    else:
        # T-1679: the typed lines were quarantined; their event named the rows.
        plan["trace"] = (
            "lifecycle authority: rows closed by a quarantined typed head have no "
            "operation behind them"
        )
    if unbacked:
        plan["trace"] += "; reopened " + ", ".join(unbacked)
    return plan
''',
    )],
)

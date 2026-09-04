"""LOG event parsing -- the shared primitive."""

from __future__ import annotations

import re

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LOG_RE = re.compile(
    r"^- (\d{2}[./]\d{2}[./]\d{2} \d{2}:\d{2} )?"
    r"\[E-(\d+)\]"
    r"(?: \[parent: E-(\d+)\])?"
    r"(?: \[(T-[^\]]*)\])?"
    r"(?: \[agent: ([^\]]+)\])?"
    r"(?: \[op: ([^\]]+)\])?"
    r" ([A-Z]+): (.*)$"
)


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


def _is_reparse(info) -> bool:
    """Windows reparse point (junction/symlink/symlinked-dir) probe."""
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


class HistoryOwnershipError(ValueError):
    """A canonical history node is a symlink/junction/reparse or a non-regular
    file, or its container is (second-wave P1).

    History identity is ownership-safe: `is_dir()/is_file()/read_bytes()` all
    FOLLOW symlink/reparse nodes, which would let a history consume evidence
    outside the project. Refusing before reading keeps external bytes out of
    the digest and the ledger."""

    pass


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


def _validate_history_ownership(root: Path, logs_dir: Path) -> list[Path]:
    """lstat every canonical history node and reject symlink/junction/reparse
    or non-regular files BEFORE any bytes are read (second-wave P1).

    Returns the validated immutable list of paths in numeric order to avoid
    duplicate stat/enumeration.
    """
    try:
        logs_info = logs_dir.lstat()
    except FileNotFoundError:
        logs_info = None  # genuinely absent logs dir -> no sealed container
    except OSError as exc:
        raise HistoryOwnershipError(
            f"logs container .saipen/logs unreadable ({type(exc).__name__}): {exc}"
        )
    if logs_info is not None:
        if os.path.islink(logs_dir) or _is_reparse(logs_info):
            raise HistoryOwnershipError(
                "logs container .saipen/logs is a symlink/junction/reparse "
                "point; refusing to read history from outside the project"
            )
        if not stat.S_ISDIR(logs_info.st_mode):
            raise HistoryOwnershipError(
                ".saipen/logs exists but is not a directory; refusing to read history through it"
            )

    sealed = []
    if logs_info is not None:
        for p in logs_dir.iterdir():
            if _segment_number(p) >= 0:
                sealed.append(p)
        sealed.sort(key=_segment_number)

    active = root / ".saipen" / "LOG.md"
    paths = [*sealed, active]

    for p in paths:
        try:
            info = p.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise HistoryOwnershipError(
                f"history node {p.name} unreadable ({type(exc).__name__}): {exc}"
            )
        if os.path.islink(p) or _is_reparse(info) or not stat.S_ISREG(info.st_mode):
            raise HistoryOwnershipError(
                f"history node {p.name} is a symlink/junction/reparse or "
                f"non-regular file; refusing to read external bytes"
            )
    return paths


def _require_canonical_active_log(path: Path, raw: bytes) -> None:
    """Apply checkpoint encoding law only to the active LOG segment."""
    if path.name != "LOG.md":
        return
    from . import codec

    if not codec.is_canonical_encoding(raw):
        raise HistoryOwnershipError("active LOG.md is not canonical UTF-8 without a BOM")


@dataclass(frozen=True)
class HistorySnapshot:
    """ONE non-persistent pass over the complete LOG history.

    Holds the exact raw-byte hash, the combined LF-normalised text, the
    global max E-ID, the parsed events and the `file:line` of every line that
    is NEITHER blank, a heading, nor a legal event -- all derived from a single
    read of every numeric sealed segment + active LOG. Consumers request
    one snapshot per command and reuse it; nothing is cached across
    commands, so append/seal changes are immediately visible.

    `illegal_lines` exists because a snapshot that only collects what PARSES
    cannot tell "no events here" from "a forged line the parser refused": the
    immutable-ledger contract (P0#2) needs both halves out of the same pass.
    """

    hash: str
    text: str
    tail: int | None
    events: tuple[dict, ...]
    illegal_lines: tuple[str, ...] = ()
    # The EXACT raw event lines, retained from the SAME single parse pass
    # (T-1014): every line `parse_log_line` accepted, in file order. Context
    # projections reuse these verbatim instead of re-parsing `text` a second
    # time, so the complete history is parsed exactly once per capture.
    event_lines: tuple[str, ...] = ()
    # PERF-004: the highest ticket ID referenced anywhere in the complete
    # history (sealed + active), computed during the same single parse pass.
    # Ticket IDs that exist ONLY in sealed history remain permanently
    # reserved, so allocation must never consult only the active LOG/BOARD.
    max_ticket_id: int = 0


def _normalised_doc_text(raw: bytes) -> str:
    """Decode exactly as `codec.read_doc` would (LF-normalised text)."""
    from . import codec

    text, _encoding, _bom = codec._decode(raw)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_history_snapshot(
    project_root: Path | str, *, lean: bool = False
) -> HistorySnapshot:
    """One pass over the complete LOG history (sealed + active).

    Each segment file is opened exactly once; the exact raw bytes feed the
    hash and the decoded text feeds parsing and the combined text. Event
    ordering and parser semantics are identical to the historical
    per-consumer readers.

    Second-wave P1 ownership: every canonical history node is lstat-checked
    first and symlink/junction/reparse/non-regular nodes are refused before
    any bytes are read (HistoryOwnershipError), so history can never consume
    evidence from outside the project. The digest is FRAMED per node --
    canonical relative path + raw length + raw bytes -- so different segment
    layouts with identical concatenation, a resegment, or an added empty
    numeric segment all change the hash.

    PERF-005: `lean=True` omits the O(history-text) `text` and `event_lines`
    renderings that read-only routing commands never consume, while keeping
    hash, tail, parsed events, illegal-line diagnostics and max_ticket_id.
    The hash framing, read count and parse pass are byte-identical either way.
    """
    root = Path(project_root)
    logs_dir = root / ".saipen" / "logs"
    valid_paths = _validate_history_ownership(root, logs_dir)
    h = hashlib.sha256()
    chunks: list[str] = []
    events: list[dict] = []
    event_lines: list[str] = []
    illegal: list[str] = []
    max_ticket_id = 0
    for p in valid_paths:
        try:
            raw = p.read_bytes()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise HistoryOwnershipError(
                f"history node {p.name} unreadable ({type(exc).__name__}): {exc}"
            )
        _require_canonical_active_log(p, raw)
        rel = p.relative_to(root).as_posix()
        # FRAMED digest identity (second-wave P1): canonical relative path,
        # then raw length, then raw bytes -- so resegmenting, renaming, or
        # adding an empty numeric segment all change the hash, and two
        # different segment layouts cannot collide on concatenation alone.
        h.update(rel.encode("utf-8"))
        h.update(str(len(raw)).encode("ascii"))
        h.update(raw)
        text = _normalised_doc_text(raw)
        if not lean:
            chunks.append(text)
        for idx, line in enumerate(text.splitlines()):
            parsed = parse_log_line(line)
            if parsed is not None:
                events.append(parsed)
                # Retain the ORIGINAL legal raw line in the same pass (T-1014)
                # so context projections reuse it verbatim -- no second parse.
                if not lean:
                    event_lines.append(line)
                # PERF-004: derive the history-wide max ticket ID during the
                # authoritative parse. A ticket ref in old sealed history keeps
                # its ID reserved forever.
                t = parsed.get("ticket")
                if t:
                    m = re.match(r"T-(\d+)$", t)
                    if m:
                        tid = int(m.group(1))
                        if tid > max_ticket_id:
                            max_ticket_id = tid
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            illegal.append(f"{p.name}:{idx + 1}: not a legal LOG event: {stripped[:80]!r}")
    tail = None
    for ev in events:
        if tail is None or ev["event"] > tail:
            tail = ev["event"]
    return HistorySnapshot(
        hash=h.hexdigest()[:16],
        text="" if lean else "\n".join(chunks),
        tail=tail,
        events=tuple(events),
        illegal_lines=tuple(illegal),
        event_lines=() if lean else tuple(event_lines),
        max_ticket_id=max_ticket_id,
    )


def read_history_snapshot_and_logs_digest(
    project_root: Path | str,
    retain_text: bool = True,
) -> tuple[HistorySnapshot, str]:
    """ONE pass over the complete LOG history (sealed + active) that ALSO computes
    the sealed-LOG dependency digest -- the two reads a mutation PLAN used to do
    separately (``read_history_snapshot`` + ``hash_tree_dependency``) collapsed into
    a single content read of every segment (PERF-003).

    Each segment file is opened exactly ONCE. Its raw bytes feed BOTH:
      * the framed history hash (identical framing to ``read_history_snapshot``), and
      * the framed ``saipen-delete-tree-v1`` digest over ``.saipen/logs`` (identical
        framing and sentinels to ``hash_tree_dependency``), via a ``read_file``
        resolver so no second content read happens.

    Returns ``(snapshot, logs_digest)`` where ``logs_digest`` is byte-for-byte what
    ``hash_tree_dependency(root / ".saipen" / "logs")`` returns -- so APPLY's
    under-lock STALE_STATE recheck still compares the same value, it is simply
    computed once. Second-wave P1 ownership is enforced first
    (``HistoryOwnershipError``) and the digest contract is unchanged, so no
    Core/Second-Wave invariant weakens.

    The framed history hash and the ``event_lines`` are identical to
    ``read_history_snapshot``, so context/status projections that reuse the snapshot
    are unaffected.
    """
    root = Path(project_root)
    logs_dir = root / ".saipen" / "logs"
    valid_paths = _validate_history_ownership(root, logs_dir)
    h = hashlib.sha256()
    chunks: list[str] = []
    events: list[dict] = []
    event_lines: list[str] = []
    illegal: list[str] = []
    max_ticket_id = 0
    # PERF-001: cache raw bytes ONLY for paths inside `logs_dir` so the
    # subsequent `hash_tree_dependency(logs_dir, ...)` call -- which walks
    # exactly that directory -- is fed from memory instead of re-reading
    # every sealed segment a second time. The active LOG.md lives outside
    # `logs_dir` and is never visited by the delete-tree walker, so it is
    # deliberately not cached (it is consumed only by the snapshot above).
    sealed_cache: dict[Path, bytes] = {}
    for p in valid_paths:
        try:
            raw = p.read_bytes()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise HistoryOwnershipError(
                f"history node {p.name} unreadable ({type(exc).__name__}): {exc}"
            ) from exc
        _require_canonical_active_log(p, raw)
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(str(len(raw)).encode("ascii"))
        h.update(raw)
        text = _normalised_doc_text(raw)
        if retain_text:
            chunks.append(text)
        for idx, line in enumerate(text.splitlines()):
            parsed = parse_log_line(line)
            if parsed is not None:
                events.append(parsed)
                for candidate in re.findall(r"\[T-(\d+)\]", line):
                    tid = int(candidate)
                    if tid > max_ticket_id:
                        max_ticket_id = tid
                event_lines.append(line)
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            illegal.append(f"{p.name}:{idx + 1}: not a legal LOG event: {stripped[:80]!r}")
        if p.is_relative_to(logs_dir):
            sealed_cache[p] = raw
        del raw
    tail = None
    for ev in events:
        if tail is None or ev["event"] > tail:
            tail = ev["event"]
    snapshot = HistorySnapshot(
        hash=h.hexdigest()[:16],
        text="\n".join(chunks) if retain_text else "",
        tail=tail,
        events=tuple(events),
        illegal_lines=tuple(illegal),
        event_lines=tuple(event_lines),
        max_ticket_id=max_ticket_id,
    )
    from .journal import hash_tree_dependency

    def _read_sealed(candidate: Path) -> bytes:
        cached = sealed_cache.get(Path(candidate))
        if cached is not None:
            return cached
        return Path(candidate).read_bytes()

    logs_digest = hash_tree_dependency(logs_dir, read_file=_read_sealed)
    return snapshot, logs_digest


def read_history(project_root: Path | str) -> str:
    """The complete combined LOG text across sealed segments and active LOG.md."""
    return read_history_snapshot(project_root).text


def read_history_events(project_root: Path | str) -> list[dict]:
    """All parsed events across the complete LOG history."""
    return list(read_history_snapshot(project_root).events)


def snapshot_contract_errors(snapshot: "HistorySnapshot") -> list[str]:
    """The immutable-ledger contract, proved from an EXISTING snapshot.

    THE immutable-ledger contract (P0#2). A planner takes ONE snapshot and
    derives the ledger verdict, the syntax report and the E-ID tail from it, so
    the evidence a mutation is planned against and the evidence it was validated
    against are literally the same bytes -- never a second, possibly different
    read.

    Proves, over the complete sealed + active history:
      * legal syntax -- no forged/broken line masquerading as an event;
      * uniqueness -- each E-ID appears exactly once in the whole ledger;
      * order -- E-IDs strictly increase (a replayed event is caught);
      * parentage -- every parent E-ID exists and is strictly older.
    """
    errors: list[str] = list(snapshot.illegal_lines[:4])
    seen: dict[int, int] = {}
    for ev in snapshot.events:
        seen[ev["event"]] = seen.get(ev["event"], 0) + 1
    dupes = sorted(e for e, count in seen.items() if count > 1)
    if dupes:
        errors.append(
            "duplicate E-ID(s) in complete history: " + ", ".join(f"E-{e}" for e in dupes[:10])
        )
    prev: int | None = None
    for ev in snapshot.events:
        eid = ev["event"]
        parent = ev["parent"]
        if parent is not None:
            if parent not in seen:
                errors.append(f"E-{eid} parent E-{parent} does not exist in the ledger")
            elif parent >= eid:
                errors.append(f"E-{eid} parent E-{parent} is not older than E-{eid}")
        if prev is not None and eid <= prev:
            errors.append(f"E-{eid} is not greater than preceding E-{prev} (out of order)")
        prev = eid
    return errors


def history_contract_errors(project_root: Path | str) -> list[str]:
    """Validate the COMPLETE LOG history as one immutable ledger, before any
    planning (hostile-regression, P0#2).

    Every event across the sealed segments + active LOG.md is checked for:
      * legal syntax -- it parses under the shared LOG_RE (no forged/broken
        line masquerading as an event);
      * uniqueness -- each E-ID appears exactly once across the whole ledger;
      * order -- the ledger is strictly monotonically increasing (a replayed
        or mis-ordered event is caught);
      * parent existence + ordering -- every parent E-ID resolves inside the
        ledger and is strictly older than its child (a broken or fabricated
        parent edge is caught).

    A void ledger would otherwise let a mutation PLAN against a trusted record
    that does not exist, so the planner must refuse before any canonical
    write. Syntax errors are reported with their file:line so the corruption is
    exactly located.

    ONE implementation: this is `snapshot_contract_errors` over a fresh
    snapshot, which is the same call the planner makes -- the validator and the
    planner can never disagree about what a valid ledger is."""
    return snapshot_contract_errors(read_history_snapshot(project_root))


def read_history_snapshot_strict(project_root: Path | str) -> tuple[HistorySnapshot, list[str]]:
    """One snapshot pass plus the full ledger contract, from that ONE pass.

    Consumers that PLAN call this once and reuse the snapshot for tail/evidence
    instead of re-reading the history piecemeal (hostile-regression, P0#2)."""
    snapshot = read_history_snapshot(project_root)
    return snapshot, snapshot_contract_errors(snapshot)


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


VALID_TAXONOMIES = frozenset(
    {
        "DEC",
        "RUN",
        "WAIT",
        "REVERT",
        "NOTE",
        "OPS",
    }
)


def build_event(
    tail: int | None,
    taxonomy: str,
    message: str,
    ticket: str | None = None,
    agent: str | None = None,
    now: str | None = None,
    op_id: str | None = None,
) -> tuple[int, str]:
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
        raise ValueError(f"taxonomy {taxonomy!r} outside {sorted(VALID_TAXONOMIES)}")
    if now is None:
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc).strftime("%d.%m.%y %H:%M")
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
_NEGATION_RE = re.compile(r"\bNOT\s+(?:PASS|MANUAL-VERIFY)\b", re.IGNORECASE)
_PASS_TOKEN_RE = re.compile(r"\bPASS\b")

# CORE-003: a manual verification RESULT, not the appearance of the words.
#
# This used to be `\bMANUAL-VERIFY\b` searched anywhere in the body, so the
# procedural instruction `phases/verify.md` REQUIRES an agent to record --
# "MANUAL-VERIFY STEPS + EXPECTED", written precisely because a human has not
# verified anything yet -- satisfied the gate. So did any sentence that merely
# mentioned the token: `some prose that merely mentions MANUAL-VERIFY in
# passing` classified as successful verification. Human confirmation had become
# a magic substring.
#
# `structural_marker_events` in this same module already names that class --
# Narrative Authority Leakage -- and already prescribes the cure: authority
# belongs to a marker that BEGINS the event text, not one contained in it. The
# rule existed; the verification grammar had simply never been held to it.
#
# So the marker is anchored and it carries an explicit verdict. Steps, requests
# and prose are none of these and classify as nothing at all.
_MANUAL_RESULT_RE = re.compile(r"^MANUAL-VERIFY RESULT:\s*(PASS|FAIL)\b")
MANUAL_RESULT_PREFIX = "MANUAL-VERIFY RESULT: "

# T-1241: a FAILURE CLAIM, not the mere appearance of the letters. The old
# test was `"FAIL" in txt`, so the canonical zero-failure summary every gate in
# this repository prints -- `validate.py --gate core 0 FAIL` -- read as
# negative evidence, and VERIFY could not reach REVIEW until someone wrote a
# second, weaker event that avoided the word. The grammar must keep
# negative-evidence-wins (a real failure can never be talked past) while
# recognising that a count of zero in front of the token is the OPPOSITE of a
# failure. Anything not provably zero stays a failure.
_ZERO_FAIL_RE = re.compile(r"\b(?:0|no|zero)\s+FAIL(?:S|ED|URE|URES)?\b", re.IGNORECASE)
_FAIL_TOKEN_RE = re.compile(r"\bFAIL(?:S|ED|URE|URES)?\b", re.IGNORECASE)


def _claims_failure(text: str) -> bool:
    """Does this event text CLAIM a failure? (T-1241)

    Every `FAIL` token has to be accounted for. A text is failure-free only
    when each occurrence is one of the zero-count forms; a single unexplained
    token -- `1 FAIL`, `FAILED`, a bare `FAIL:` prefix -- is a failure claim.
    An evidence grammar that must guess should guess toward failure, so the
    comparison is a count, not a "contains a zero form somewhere" test: a line
    reading `0 FAIL on core, 3 FAIL on ship` is a failure.
    """
    if _NEGATION_RE.search(text):
        return True
    total = len(_FAIL_TOKEN_RE.findall(text))
    if not total:
        return False
    return total > len(_ZERO_FAIL_RE.findall(text))


# CORE-001: the regression channel is NOT the ordinary verification channel.
# A `REGRESSION-EVIDENCE FAIL ...` record is the REQUIRED red half of a pair --
# an agent recording it is complying, not reporting that the cycle failed --
# but `_claims_failure` sees the word and vetoes. The two classifiers answer
# different questions over the same LOG, so the ordinary one steps over the
# other one's records rather than guessing about them. `regression_evidence`
# reads exactly these, and nothing else reads them at all.
def _is_regression_evidence(text: str) -> bool:
    from .oracle import parse_evidence

    return parse_evidence(text) is not None


def _is_verify_boundary(ev: dict) -> bool:
    """True iff `ev` is the EXACT machine-owned VERIFY entry marker.

    The boundary text is owned by the engine (`_plan_transition` always
    writes `transition to VERIFY`, optionally followed by ` -- <reason>`).
    A transition whose marker was replaced by caller-supplied prose is NOT
    a boundary: the engine can no longer tell where verification started,
    so the ticket is unproven (hostile-regression, machine-owned grammar).
    """
    txt = ev.get("text", "")
    return txt == "transition to VERIFY" or txt.startswith(_VERIFY_BOUNDARY_PREFIX)


def regression_evidence(ticket_id: str, events: list[dict]) -> tuple[bool, str]:
    """`(admissible, reason)` for a ticket that owes a regression PAIR.

    CORE-001. `verification_evidence` above answers "did something green happen
    in this cycle" and cannot answer "did the IMPLEMENTATION cause it" -- it
    reads free-form text and never compares an oracle to a subject. A ticket
    declaring `regression: required` needs both answers, so this is the second
    half, scoped exactly the same way: the current VERIFY cycle only, bounded
    by the latest machine-owned boundary, taxonomy RUN, ticket-scoped.

    Reuses `oracle.regression_pair_verdict` rather than re-deciding: one
    arithmetic, one place, so the gate and the module cannot drift.
    """
    from .oracle import parse_evidence, regression_evidence_verdict

    if not ticket_id:
        return False, "no ticket id provided"
    boundary = None
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if (
            ev.get("ticket") == ticket_id
            and ev.get("taxonomy") == "RUN"
            and _is_verify_boundary(ev)
        ):
            boundary = i
            break
    if boundary is None:
        return False, "no current-cycle VERIFY boundary"

    records = []
    for ev in events[boundary:]:
        if ev.get("ticket") != ticket_id or ev.get("taxonomy") != "RUN":
            continue
        record = parse_evidence(ev.get("text", ""))
        if record is not None:
            records.append(record)
    verdict = regression_evidence_verdict(records)
    return bool(verdict.get("admissible")), f"{verdict['code']}: {verdict['reason']}"


def structural_marker_events(
    events,
    marker: str,
    taxonomies=("RUN",),
    *,
    after_event: int = 0,
) -> list[int]:
    """Event ids where `marker` is ACTUAL AUTHORITY, not prose that mentions it.

    Narrative Authority Leakage is this repository's most expensive recurring
    defect: a validator searches free text for a magic phrase, and any line that
    merely DISCUSSES the phrase silently acquires the power the phrase carries.
    Two instances have cost real work.

    The timestamp-inversion amnesty was one boolean over the whole corpus --
    "does any segment anywhere contain this sentence" -- so three sealed DEC
    lines from July 2026 disarmed the inversion check for every line written
    afterwards, and it reported nothing for five weeks. Repairing it, the SCOUT
    checkpoint that quoted the marker while diagnosing it disarmed the check
    again, one level up.

    The clean-HUNT marker was the same shape and still live when this was
    written: 28 LOG lines contain `hunt -> clean @` and only 24 are the
    canonical record. The other four are prose -- a note and two checkpoints
    discussing it -- and each of them alone activated the converge prohibition
    without a HUNT having run.

    Three conditions, and dropping any one reopens the class:

    * TAXONOMY -- authority belongs to the record type that carries it. A `RUN`
      reporting an action is not a `DEC` deciding one, and prose about either
      is neither.
    * ANCHORING -- the marker must BEGIN the event text. A sentence containing
      it is describing it. This is the same rule `_is_verify_boundary` already
      applies to the VERIFY boundary, generalized rather than re-invented.
    * BOUNDING -- `after_event` scopes the authority to events at or after a
      named point, so an exception cannot cover work that had not happened when
      it was granted. A suppressor whose scope is "the file" cannot expire.

    Returns the event ids, so a caller can bound its own decision against them
    rather than collapsing the answer to a boolean it cannot scope.
    """
    if not marker:
        return []
    allowed = tuple(taxonomies)
    found: list[int] = []
    for ev in events:
        if ev.get("taxonomy") not in allowed:
            continue
        event_id = ev.get("event")
        if not isinstance(event_id, int) or event_id < after_event:
            continue
        if (ev.get("text") or "").startswith(marker):
            found.append(event_id)
    return found


def verification_evidence(ticket_id: str, events: list[dict]) -> tuple[bool, str]:
    """Classify verification evidence for a ticket (hostile-regression).

    Machine-owned grammar. Searches backwards from the end of the history:

    - the boundary is the LATEST exact VERIFY entry marker
      (`transition to VERIFY` or `transition to VERIFY -- <reason>`) for
      this ticket; a replaced/forged marker is not a boundary;
    - only RUN events for the ticket AFTER that boundary count (the
      current verification cycle);
    - negative evidence wins: a FAILURE CLAIM (`_claims_failure`), `NOT PASS`
      or `NOT MANUAL-VERIFY` fails immediately. A zero count in front of the
      token (`0 FAIL`, `no failures`) is not a claim (T-1241);
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
        if _is_regression_evidence(txt):
            continue
        if _claims_failure(txt):
            return False, txt
        manual = _MANUAL_RESULT_RE.match(txt.strip())
        if manual is not None:
            # An explicit human verdict, either way. A recorded FAIL is
            # negative evidence, not "keep looking for something greener".
            return manual.group(1) == "PASS", txt
        if _PASS_TOKEN_RE.search(txt):
            if "conf: low" in txt or "conf: med" in txt:
                return False, txt
            if "conf: high" in txt:
                return True, txt

    return False, "unproven/failed"


def bulk_verification_evidence(
    events: list[dict], ticket_ids: Iterable[str]
) -> dict[str, tuple[bool, str]]:
    """ONE backward pass computing the verdict for EVERY requested ticket
    (perf wave T-1021).

    `verification_evidence` reverse-scans the full shared history once per
    ticket, so a status with many DONE tickets costs O(tickets * events).
    This helper walks the SAME event list backward exactly once and applies
    the IDENTICAL grammar per ticket:

    - the boundary for a ticket is its latest exact VERIFY marker; events
      older than it are out of the current cycle;
    - while walking newest-first, the first decisive RUN event after the
      boundary decides (negative evidence wins, then MANUAL-VERIFY, then
      PASS with exact `conf: high`);
    - the boundary event itself is scanned for decisive tokens exactly as
      the single-ticket helper does (its scan is inclusive of the boundary);
    - no boundary or no decisive evidence after it -> unproven/failed with
      the same reason strings.

    Returns {ticket_id: (ok, reason)} for every requested id, byte-for-byte
    the same (ok, reason) the single-ticket helper would return.

    The pass is single-sweep: while walking newest-first, the first decisive
    RUN event per ticket is tentatively stored as pending evidence; the
    verdict is finalized when the ticket's NEWEST VERIFY boundary is reached
    (evidence older than the boundary is out of cycle, and a ticket with no
    boundary is unproven regardless of pending evidence -- exactly the
    single-ticket early return).
    """
    wanted = set(ticket_ids)
    verdicts: dict[str, tuple[bool, str]] = {}
    boundary_seen: set[str] = set()
    pending: dict[str, tuple[bool, str]] = {}
    for ev in reversed(events):
        if ev.get("taxonomy") != "RUN":
            continue
        tid = ev.get("ticket")
        if tid not in wanted or tid in verdicts:
            continue
        if tid in boundary_seen:
            continue  # older than the newest VERIFY boundary: out of cycle
        txt = ev.get("text", "")
        if _is_regression_evidence(txt):
            continue
        decisive = None
        if _claims_failure(txt):
            decisive = (False, txt)
        elif _MANUAL_RESULT_RE.match(txt.strip()):
            decisive = (_MANUAL_RESULT_RE.match(txt.strip()).group(1) == "PASS", txt)
        elif _PASS_TOKEN_RE.search(txt):
            if "conf: low" in txt or "conf: med" in txt:
                decisive = (False, txt)
            elif "conf: high" in txt:
                decisive = (True, txt)
        if _is_verify_boundary(ev):
            # The NEWEST boundary closes the cycle; the boundary event itself
            # is inside the scan (single-ticket scans it inclusively), so it
            # may still be the decisive evidence when nothing newer is.
            boundary_seen.add(tid)
            if decisive is not None and tid not in pending:
                pending[tid] = decisive
            verdicts[tid] = pending.get(tid) or (False, "unproven/failed")
            continue
        if decisive is not None and tid not in pending:
            pending[tid] = decisive
    for tid in wanted:
        if tid not in verdicts:
            verdicts[tid] = (
                False,
                "no current-cycle VERIFY boundary"
                if tid not in boundary_seen
                else "unproven/failed",
            )
    return verdicts

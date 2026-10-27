"""FUTURE GATE: deferred authority candidates, index projection and promotion.

``future_gate/**.md`` holds the human documents. ``.saipen/future/index.json``
is the machine-owned projection that routing reads: identity, lifecycle,
readiness inputs and slice closure -- nothing a routing decision can be read
off arbitrary long prose.

Reads are side-effect free.  Only :func:`write_index` and :func:`promote`
write, and both are explicit operations.

`FUTURE.md` (Rule FUTURE-GATE-01) is the normative owner.  This module is the
enforcement: a gate is a DEFERRED AUTHORITY CANDIDATE, never active Work,
never a rule source, never implementation authority until promotion.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import (
    prove_owned_dir_chain,
    prove_owned_regular,
    read_bound_regular_bytes,
    safe_atomic_write_bytes,
)

GATE_REL = Path("future_gate")
INDEX_REL = Path(".saipen/future/index.json")
RECORDS_REL = Path(".saipen/future/records")
DOC_MARKER = "<!-- SAIPEN FUTURE GATE v1 -->"
INDEX_MARKER = "saipen-future-index-v1"
RECORD_MARKER = "saipen-future-record-v1"
#: v2 adds the corpus witness (FUTURE.md section 2) and the reviewed-record
#: side-car (section 8). An index written under v1 carries no witness and is
#: therefore STALE until the next refresh -- the honest verdict, not a crash.
SCHEMA_VERSION = 2

#: Lifecycle states.  `NEEDS_REVIEW` is the honest verdict for an ambiguous
#: historical record -- never `ELIGIBLE` by guess (FUTURE.md section 1).
RECORDED = "RECORDED"
DEFERRED = "DEFERRED"
INELIGIBLE = "INELIGIBLE"
ELIGIBLE = "ELIGIBLE"
PROMOTED = "PROMOTED"
NEEDS_REVIEW = "NEEDS_REVIEW"
STATES = frozenset({RECORDED, DEFERRED, INELIGIBLE, ELIGIBLE, PROMOTED, NEEDS_REVIEW})
#: Only these are live routing candidates.
CANDIDATE_STATES = frozenset({RECORDED, DEFERRED, ELIGIBLE})
#: Terminal once reached; never re-enters the candidate class.
TERMINAL_STATES = frozenset({INELIGIBLE, PROMOTED})
#: Prefix of the header values `add` writes for the author to replace. A
#: placeholder declares nothing: readiness reads it as an absent field, so a
#: gate cannot mature before its author names its slice and evidence (T-1638).
PLACEHOLDER = "TODO --"

#: Index freshness (FUTURE.md section 2). A STALE index is NOT an empty queue:
#: it means the corpus moved and the projection has not caught up, and routing
#: must refresh before it may fall through to HUNT/ADD.
CURRENT = "CURRENT"
STALE = "STALE"
MISSING = "MISSING"
CORRUPT = "CORRUPT"

BASES = ("measured", "reproduced", "speculative")
CLOSURES = ("done", "superseded", "rejected", "obsolete")
UNRESOLVED = "open"

_FIELDS = frozenset(
    {
        "id",
        "title",
        "state",
        "priority",
        "basis",
        "estimate",
        "slice",
        "needs",
        "evidence",
        "recorded",
    }
)
_STATUS_RE = re.compile(r"(?im)^\s*(?:#+\s*)?status\s*:\s*(?P<value>.+?)\s*$")
_H1_RE = re.compile(r"(?m)^#[ \t]+(.+?)[ \t]*$")
_TITLE_RE = re.compile(r"(?m)^title:[ \t]*(?P<value>.+?)[ \t]*$")
_TICKET_RE = re.compile(r"^T-\d+$")
_ID_RE = re.compile(r"^FG-(\d{4})$")
_MAX_TEXT = 256 * 1024
_MAX_DOC_BYTES = 512 * 1024
_MAX_INDEX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class GateDocument:
    """One parsed future-gate document."""

    path: str
    title: str
    declared_id: str | None
    state: str | None
    priority: str | None
    basis: str | None
    estimate: int | None
    slice: str | None
    needs: tuple[str, ...]
    evidence: tuple[str, ...]
    declared_status: str | None
    machine_readable: bool
    digest: str
    problems: tuple[str, ...] = ()
    #: Bounded normalized text, read ONLY by bounded refinement. Routing never
    #: sees it and never reparses prose for a decision.
    text: str = ""


@dataclass
class Gate:
    """One projected gate record -- the only shape routing consumes."""

    id: str
    path: str | None
    title: str
    state: str
    priority: str | None = None
    basis: str | None = None
    estimate: int | None = None
    slice: str | None = None
    needs: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    recorded_at: str | None = None
    declared_status: str | None = None
    machine_readable: bool = False
    digest: str | None = None
    present: bool = True
    identity_source: str = "index-assigned"
    reviewed: bool = False
    slices: list[dict] = field(default_factory=list)
    reasons: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()
    #: The document digest an `ELIGIBLE` state was proved on. A stored
    #: maturation is valid only for those bytes (T-1638).
    matured_digest: str | None = None

    @property
    def open_slices(self) -> list[dict]:
        return [s for s in self.slices if str(s.get("closure") or UNRESOLVED) == UNRESOLVED]

    @property
    def closed(self) -> bool:
        """A gate closes only when every slice is resolved."""
        return self.state == PROMOTED and bool(self.slices) and not self.open_slices

    def as_dict(self) -> dict:
        out = {
            "id": self.id,
            "path": self.path,
            "title": self.title,
            "state": self.state,
            "machine_readable": self.machine_readable,
            "present": self.present,
            "identity_source": self.identity_source,
            "reviewed": self.reviewed,
        }
        for key in (
            "priority",
            "basis",
            "estimate",
            "slice",
            "recorded_at",
            "declared_status",
            "digest",
            "matured_digest",
        ):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.needs:
            out["needs"] = list(self.needs)
        if self.evidence:
            out["evidence"] = list(self.evidence)
        if self.slices:
            out["slices"] = list(self.slices)
        if self.reasons:
            out["reasons"] = list(self.reasons)
        if self.problems:
            out["problems"] = list(self.problems)
        return out

    @classmethod
    def from_dict(cls, raw: dict) -> "Gate":
        return cls(
            id=str(raw.get("id") or ""),
            path=raw.get("path"),
            title=str(raw.get("title") or ""),
            state=str(raw.get("state") or NEEDS_REVIEW),
            priority=raw.get("priority"),
            basis=raw.get("basis"),
            estimate=raw.get("estimate"),
            slice=raw.get("slice"),
            needs=tuple(raw.get("needs") or ()),
            evidence=tuple(raw.get("evidence") or ()),
            recorded_at=raw.get("recorded_at"),
            declared_status=raw.get("declared_status"),
            machine_readable=bool(raw.get("machine_readable")),
            digest=raw.get("digest"),
            present=bool(raw.get("present", True)),
            identity_source=str(raw.get("identity_source") or "index-assigned"),
            reviewed=bool(raw.get("reviewed")),
            slices=list(raw.get("slices") or []),
            reasons=tuple(raw.get("reasons") or ()),
            problems=tuple(raw.get("problems") or []),
            matured_digest=raw.get("matured_digest"),
        )


# ---------------------------------------------------------------- parsing


def _norm_title(value: str) -> str:
    return " ".join(value.replace("|", " ").split()).casefold()


def _csv(value: str, field_name: str) -> tuple[str, ...]:
    items = []
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        if "|" in item or "\n" in item:
            raise ValueError(f"{field_name} entry contains a delimiter")
        items.append(item)
    return tuple(items)


def parse_document(text: str, path: str) -> GateDocument:
    """Parse one future-gate document into its machine-readable fields.

    A document without the v1 marker is NOT malformed -- it is the historical
    corpus, classified `NEEDS_REVIEW`. That is a truth, not a failure, and it
    is why routing never reparses prose.
    """
    rel = path.replace("\\", "/")
    normalized = "\n".join(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    digest = hashlib.sha256(normalized.strip().encode("utf-8")).hexdigest()
    problems: list[str] = []
    status = _STATUS_RE.search(normalized)
    declared_status = " ".join(status.group("value").split()) if status else None
    machine = normalized.lstrip().startswith(DOC_MARKER)
    h1 = _H1_RE.search(normalized)
    header_title = _TITLE_RE.search(normalized)
    title = (header_title.group("value") if header_title else (h1.group(1) if h1 else rel)).strip()
    if not machine:
        return GateDocument(
            path=rel,
            title=title[:200],
            declared_id=None,
            state=None,
            priority=None,
            basis=None,
            estimate=None,
            slice=None,
            needs=(),
            evidence=(),
            declared_status=declared_status,
            machine_readable=False,
            digest=digest,
            problems=("no machine header; historical record needs review",),
            text=normalized[:_MAX_TEXT],
        )
    lines = normalized.lstrip().split("\n")
    fields: dict[str, str] = {}
    cursor = 1
    while cursor < len(lines) and lines[cursor].strip():
        key, sep, value = lines[cursor].partition(":")
        key = key.strip()
        if not sep or key not in _FIELDS:
            problems.append(f"invalid header line {cursor + 1}: {lines[cursor][:80]!r}")
            cursor += 1
            continue
        if key in fields:
            problems.append(f"duplicate field {key}")
        fields[key] = value.strip()
        cursor += 1
    declared_id = fields.get("id")
    if declared_id is not None and not _ID_RE.match(declared_id):
        problems.append(f"malformed id {declared_id!r}")
        declared_id = None
    state = fields.get("state")
    if state is not None and state not in STATES:
        problems.append(f"unknown state {state!r}")
        state = None
    priority = fields.get("priority")
    if priority is not None and not re.fullmatch(r"P[0-3]", priority):
        problems.append(f"unknown priority {priority!r}")
        priority = None
    basis = fields.get("basis")
    if basis is not None and basis not in BASES:
        problems.append(f"unknown basis {basis!r}")
        basis = None
    estimate = None
    if fields.get("estimate"):
        if re.fullmatch(r"\d+", fields["estimate"]):
            estimate = int(fields["estimate"])
        else:
            problems.append("estimate must be a non-negative integer count of slices")
    needs: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    try:
        if fields.get("needs") and fields["needs"].strip().casefold() != "none":
            needs = _csv(fields["needs"], "needs")
            for item in needs:
                if not _TICKET_RE.match(item):
                    problems.append(f"needs entry {item!r} is not a ticket id")
        if fields.get("evidence"):
            evidence = _csv(fields["evidence"], "evidence")
    except ValueError as exc:
        problems.append(str(exc))
    if not fields.get("slice"):
        problems.append("slice is required: one bounded unit per promotion")
    return GateDocument(
        path=rel,
        title=(fields.get("title") or title)[:200],
        declared_id=declared_id,
        state=state or DEFERRED,
        priority=priority,
        basis=basis,
        estimate=estimate,
        slice=fields.get("slice") or None,
        needs=needs,
        evidence=evidence,
        declared_status=declared_status,
        machine_readable=True,
        digest=digest,
        problems=tuple(problems),
        text=normalized[:_MAX_TEXT],
    )


def _read_owned(path: Path, root: Path, *, max_bytes: int = _MAX_DOC_BYTES) -> bytes:
    prove_owned_dir_chain(path.parent, kind="future gate path", ownership_root=root)
    witnessed = prove_owned_regular(path, kind="future gate document")
    return read_bound_regular_bytes(path, witnessed, max_bytes=max_bytes)


def _document_paths(root: Path) -> list[Path]:
    gate_dir = root / GATE_REL
    if not os.path.lexists(gate_dir):
        return []
    prove_owned_dir_chain(gate_dir, kind="future_gate", ownership_root=root)
    if not gate_dir.is_dir():
        raise ValueError(f"future_gate is not a directory: {gate_dir}")
    paths = [
        path
        for path in gate_dir.rglob("*.md")
        if path.is_file() and path.suffix.casefold() == ".md" and not path.is_symlink()
    ]
    for path in paths:
        prove_owned_regular(path, kind="future gate document")
    return sorted(paths, key=lambda item: item.relative_to(gate_dir).as_posix().casefold())


def read_documents(root: Path | str) -> list[GateDocument]:
    root = Path(root).resolve()
    docs = []
    for path in _document_paths(root):
        rel = path.relative_to(root).as_posix()
        try:
            raw = _read_owned(path, root)
        except (OSError, ValueError):
            # An unreadable document is a truthful unknown, never a crash in
            # the middle of routing and never silently dropped.
            docs.append(
                GateDocument(
                    path=rel,
                    title=rel,
                    declared_id=None,
                    state=None,
                    priority=None,
                    basis=None,
                    estimate=None,
                    slice=None,
                    needs=(),
                    evidence=(),
                    declared_status=None,
                    machine_readable=False,
                    digest="",
                    problems=("document unreadable",),
                )
            )
            continue
        docs.append(parse_document(raw.decode("utf-8", errors="replace"), rel))
    return docs


# ---------------------------------------------------------------- index I/O


def index_path(root: Path | str) -> Path:
    return Path(root).resolve() / INDEX_REL


def _index_bytes(index: dict) -> bytes:
    return (json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_index(root: Path | str) -> dict | None:
    """The persisted projection, or None when absent/unreadable.

    `None` means UNINDEXED -- never "empty" and never "nothing is ready". A
    corrupt index is reported as corrupt, not silently treated as empty.
    """
    path = index_path(root)
    if not path.exists():
        return None
    try:
        witnessed = prove_owned_regular(path, kind="future gate index")
        raw = read_bound_regular_bytes(path, witnessed, max_bytes=_MAX_INDEX_BYTES)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        return {"marker": INDEX_MARKER, "corrupt": f"{type(exc).__name__}: {exc}", "gates": []}
    if not isinstance(data, dict) or data.get("marker") != INDEX_MARKER:
        return {"marker": INDEX_MARKER, "corrupt": "unrecognized index marker", "gates": []}
    data.setdefault("gates", [])
    return data


def write_index(root: Path | str, index: dict) -> Path:
    root = Path(root).resolve()
    path = root / INDEX_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    prove_owned_dir_chain(path.parent, kind="future gate index dir", ownership_root=root)
    safe_atomic_write_bytes(
        path, _index_bytes(index), kind="future gate index", ownership_root=root
    )
    return path


def _assign_id(index: dict) -> str:
    used = {
        int(match.group(1))
        for raw in index.get("gates") or []
        if (match := _ID_RE.match(str(raw.get("id") or "")))
    }
    nxt = max(used) + 1 if used else 1
    while nxt in used:
        nxt += 1
    return f"FG-{nxt:04d}"


def _initial_state(doc: GateDocument, prior: dict | None) -> str:
    """The lifecycle state a freshly parsed document starts from.

    An explicit `NEEDS_REVIEW` is a human truth the projection must not
    overwrite: an ambiguous record is never a live candidate. Otherwise the
    machine owner keeps what it already proved (`ELIGIBLE`/`PROMOTED`/terminal),
    then the document's own declaration, then the default split -- a
    machine-readable document is a live candidate, a historical one is
    truthfully UNKNOWN. Nothing here is ever `ELIGIBLE` by guess.
    """
    if doc.state == NEEDS_REVIEW:
        return NEEDS_REVIEW
    prior_state = str(prior.get("state")) if prior and prior.get("state") in STATES else None
    if prior_state == ELIGIBLE and prior.get("matured_digest") != doc.digest:
        # Maturation was proved on other bytes (or by an engine that bound
        # none): the document's own declaration decides again, and the next
        # evaluation re-proves readiness for these bytes.
        prior_state = None
    if prior_state and prior_state not in (RECORDED, DEFERRED):
        return prior_state
    if doc.state in STATES:
        return doc.state
    return DEFERRED if doc.machine_readable else NEEDS_REVIEW


def build_index(root: Path | str, *, previous: dict | None = None) -> dict:
    """Return the exact index bytes' payload for current documents; write nothing.

    Incremental by identity, not by path: a renamed or moved document keeps
    its `FG-####` and its lifecycle facts. Identity is reconciled by declared
    id, then content digest, then normalized title -- filename alone decides
    nothing.
    """
    root = Path(root).resolve()
    previous = previous if previous is not None else {}
    old_by_id: dict[str, dict] = {}
    old_by_digest: dict[str, dict] = {}
    old_by_title: dict[str, dict] = {}
    for raw in previous.get("gates") or []:
        gid = str(raw.get("id") or "")
        if gid:
            old_by_id[gid] = raw
        if raw.get("digest"):
            old_by_digest[str(raw["digest"])] = raw
        if raw.get("title"):
            old_by_title[_norm_title(str(raw["title"]))] = raw

    documents = read_documents(root)
    records = load_records(root)
    claimed: set[str] = set()
    gates: list[dict] = []
    for doc in documents:
        prior = None
        source = "index-assigned"
        for candidate in (
            (old_by_id.get(doc.declared_id) if doc.declared_id else None),
            old_by_digest.get(doc.digest) if doc.digest else None,
            old_by_title.get(_norm_title(doc.title)),
        ):
            if candidate is not None and str(candidate.get("id")) not in claimed:
                prior = candidate
                break
        if prior is None and doc.declared_id:
            gid = doc.declared_id
        elif prior is not None:
            gid = str(prior.get("id"))
            source = (
                "document-header"
                if doc.declared_id == gid
                else ("digest" if prior.get("digest") == doc.digest else "title")
            )
        else:
            gid = _assign_id({"gates": [g for g in gates]})
        if gid in claimed:
            continue
        claimed.add(gid)
        state = _initial_state(doc, prior)
        # A reviewed legacy record supplies machine lifecycle facts the
        # document could not carry (section 8). It binds to the digest it
        # reviewed: edited bytes invalidate the verdict rather than inheriting
        # it, and a v1 document keeps declaring its own state.
        reviewed = False
        review_reasons: list[str] = []
        record = records.get(gid)
        if record is not None and not doc.machine_readable:
            if record.get("digest") and record.get("digest") != doc.digest:
                state = NEEDS_REVIEW
                review_reasons = [
                    "reviewed record is stale for current bytes; refine again"
                ]
            elif record.get("verdict") in STATES:
                reviewed = True
                if state in (ELIGIBLE, PROMOTED, INELIGIBLE):
                    # Activation policy: a lived state outranks the historical
                    # review verdict. The review classifies the bytes once; it
                    # must not demote a matured (ELIGIBLE), promoted, or
                    # retired gate back to DEFERRED on every refresh, or
                    # maturation would flap forever instead of converging.
                    review_reasons = []
                else:
                    state = str(record["verdict"])
                    review_reasons = [
                        str(record.get("reason") or "reviewed legacy record")
                    ]
        if doc.problems and state == DEFERRED and not reviewed:
            state = NEEDS_REVIEW
        entry: dict = {
                **{
                    key: value
                    for key, value in (
                        ("priority", doc.priority),
                        ("basis", doc.basis),
                        ("estimate", doc.estimate),
                        ("slice", doc.slice),
                    )
                    if value is not None
                },
                "id": gid,
                "path": doc.path,
                "title": doc.title,
                "state": state,
                "machine_readable": doc.machine_readable,
                "digest": doc.digest,
                "identity_source": source,
                "present": True,
                "reviewed": reviewed or None,
                "needs": list(doc.needs),
                "evidence": list(doc.evidence),
                "declared_status": doc.declared_status,
                "recorded_at": (prior or {}).get("recorded_at"),
                # Carried only while it binds these bytes; a declared or
                # unbound ELIGIBLE is re-proved by `evaluate`, never laundered.
                "matured_digest": (
                    doc.digest
                    if state == ELIGIBLE and (prior or {}).get("matured_digest") == doc.digest
                    else None
                ),
                "slices": list((prior or {}).get("slices") or []),
                "reasons": review_reasons or list((prior or {}).get("reasons") or []),
                # A reviewed record IS the machine authority for an unmarked
                # document: the missing header stops being a blocker once a
                # verdict is bound to these exact bytes.
                "problems": [p for p in doc.problems if not reviewed],
        }
        if reviewed:
            # The reviewed record, not the prose, supplies machine facts for a
            # legacy document: identity of the bounded slice and its evidence.
            for key in ("priority", "basis", "estimate", "slice"):
                if (record or {}).get("facts", {}).get(key) not in (None, ""):
                    entry[key] = record["facts"][key]
            for key in ("needs", "evidence"):
                if (record or {}).get("facts", {}).get(key):
                    entry[key] = list(record["facts"][key])
        gates.append(entry)
        gates[-1] = {k: v for k, v in gates[-1].items() if v not in ([], None)}
    # A document that vanished keeps its record: dropping it would erase
    # provenance and silently resurrect a retired gate as a fresh candidate.
    live_digests = {g.get("digest") for g in gates if g.get("digest")}
    live_paths = {g.get("path") for g in gates}
    for raw in previous.get("gates") or []:
        gid = str(raw.get("id") or "")
        if not gid or gid in claimed:
            continue
        if raw.get("digest") in live_digests or raw.get("path") in live_paths:
            continue
        gates.append({**raw, "present": False, "state": str(raw.get("state") or NEEDS_REVIEW)})
    gates.sort(key=lambda item: str(item.get("id")))
    return {
        "marker": INDEX_MARKER,
        "schema": SCHEMA_VERSION,
        "witness": corpus_witness(documents),
        "corpus": {
            "documents": sum(1 for g in gates if g.get("present")),
            "absent": sum(1 for g in gates if not g.get("present")),
            "machine_readable": sum(1 for g in gates if g.get("machine_readable")),
        },
        "gates": gates,
    }


def reconcile_slice_closures(
    root: Path | str, board_tickets: dict | None = None
) -> dict:
    """Advance every promoted slice whose ticket is `## DONE` on BOARD.

    T-1937. A promoted gate's slice carries `closure: open`, and FUTURE.md §1
    says the gate closes when every slice is DONE/SUPERSEDED/REJECTED/OBSOLETE.
    Nothing wrote that transition: `record_slice` is called only by
    `saipen future promote` and with the default `open`, so a promoted gate was
    INELIGIBLE for ever and its slice could never resolve. This is the missing
    writer, and it is a DERIVATION, not a claim:

    * the closure is read from the BOARD, never from a caller's prose -- a
      ticket is either `[x]` under `## DONE` or it is not;
    * a ticket that is merely absent from BOARD does NOT close a slice. Only a
      proven DONE does, because absence could as easily be a corrupted parse;
    * a superseded ticket closes as `superseded`; everything else stays `open`.
    """
    root = Path(root)
    index = load_index(root)
    if not index or index.get("corrupt"):
        return {"ok": False, "code": "FUTURE_INDEX_UNREADABLE", "changes": []}

    if board_tickets is None:
        from .board import parse_board

        board_path = root / ".saipen" / "BOARD.md"
        try:
            text = board_path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            # A tree with no BOARD proves no ticket DONE, which is exactly the
            # conservative answer: nothing closes. `refresh` must stay usable
            # on a corpus-only fixture (it is the projection builder), so an
            # absent memory file is not an error here.
            board_tickets = {}
        else:
            board = parse_board(text)
            if board.get("errors"):
                return {
                    "ok": False,
                    "code": "BOARD_MALFORMED",
                    "changes": [],
                    "detail": "; ".join(board["errors"][:3]),
                }
            board_tickets = board["tickets"]

    done: set[str] = set()
    superseded: set[str] = set()
    rejected: set[str] = set()
    for ticket_id, ticket in (board_tickets or {}).items():
        fields = ticket.get("fields") or {}
        if str(ticket.get("section") or "") != "## DONE":
            continue
        done.add(str(ticket_id))
        mode = str(fields.get("closure_mode") or "")
        if mode == "superseded_verified":
            superseded.add(str(ticket_id))
        elif mode == "finding_invalidated":
            # T-1938: `finding_invalidated` asserts NO delta was owed -- the
            # finding was disproven and nothing was implemented (operations.py,
            # `implementation_delta: none`). Recording that as `done` would tell
            # every later reader the slice's work exists when it never did.
            # `rejected` is the vocabulary FUTURE.md section 1 already defines
            # for a slice that will not be implemented.
            rejected.add(str(ticket_id))

    changes: list[dict] = []
    mutated = False
    for gate in index.get("gates") or []:
        if not isinstance(gate, dict) or not isinstance(gate.get("slices"), list):
            continue
        for slice_record in gate["slices"]:
            if not isinstance(slice_record, dict):
                continue
            if str(slice_record.get("closure") or UNRESOLVED) != UNRESOLVED:
                continue
            ticket = str(slice_record.get("ticket") or "")
            if not ticket or ticket not in done:
                continue
            if ticket in superseded:
                resolved = "superseded"
            elif ticket in rejected:
                resolved = "rejected"
            else:
                resolved = "done"
            slice_record["closure"] = resolved
            changes.append({"gate": gate.get("id"), "ticket": ticket, "closure": resolved})
            mutated = True

    if mutated:
        write_index(root, index)
    return {
        "ok": True,
        "code": "FUTURE_SLICES_RECONCILED",
        "changes": changes,
        "mutation": "index" if mutated else "none",
    }


def refresh(root: Path | str) -> tuple[dict, Path]:
    """Reconcile the index with the corpus and persist it.

    T-1937: the rebuild carries BOARD's DONE truth into slice closures. A
    rebuild that only re-hashed documents left every promoted slice `open`, so
    a gate whose Work was long finished still answered INELIGIBLE for ever.
    """
    root = Path(root).resolve()
    previous = load_index(root)
    index = build_index(root, previous=previous)
    path = write_index(root, index)
    reconcile_slice_closures(root)
    return load_index(root) or index, path


# ---------------------------------------------------------------- freshness


def corpus_witness(documents: list[GateDocument]) -> dict:
    """A bounded mechanical identity for the corpus as it is right now.

    Derived from the canonical relative path AND the content digest of every
    document, plus the count and the schema. A rename, an addition, a deletion
    or a content mutation all change it; directory mtime does not, and a
    basename never decides identity.
    """
    entries = sorted(f"{doc.path}\x1f{doc.digest}" for doc in documents)
    return {
        "schema": SCHEMA_VERSION,
        "documents": len(entries),
        "unreadable": sum(1 for doc in documents if not doc.digest),
        "fingerprint": hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest(),
    }


def freshness(root: Path | str) -> dict:
    """Classify the projection against the corpus: CURRENT/STALE/MISSING/CORRUPT.

    Read-only and bounded: it hashes the corpus, it never reparses Markdown
    semantics and never writes. This is the only thing that tells routing
    "there is no future work" apart from "nobody has looked yet".
    """
    root = Path(root).resolve()
    index = load_index(root)
    if index is None:
        return {
            "state": MISSING,
            "reason": "future_gate/ is not indexed; the corpus is unknown, not empty",
            "documents": len(read_documents(root)),
            "indexed": 0,
        }
    if index.get("corrupt"):
        return {
            "state": CORRUPT,
            "reason": (
                f"future gate index is unreadable ({index['corrupt']}); a derived "
                "projection is recoverable from the corpus"
            ),
            "documents": len(read_documents(root)),
            "indexed": 0,
        }
    witness = corpus_witness(read_documents(root))
    prior = index.get("witness")
    indexed = sum(1 for raw in index.get("gates") or [] if raw.get("present"))
    base = {"documents": witness["documents"], "indexed": indexed, "witness": witness}
    if not isinstance(prior, dict):
        return {
            **base,
            "state": STALE,
            "reason": "index carries no corpus witness; it was written under an older schema",
        }
    if int(prior.get("schema") or 0) != SCHEMA_VERSION:
        return {**base, "state": STALE, "reason": "index schema drift; rebuild the projection"}
    if (
        prior.get("fingerprint") != witness["fingerprint"]
        # No `or -1` sentinel here: it would swallow the honest zero. An empty
        # corpus has no documents, so `0 or -1` is -1 and can never equal 0 --
        # the projection would be STALE forever and routing would refresh it
        # on every poll. An absent or non-integer count still fails this
        # comparison, which is the STALE verdict it deserves.
        or prior.get("documents") != witness["documents"]
    ):
        return {
            **base,
            "state": STALE,
            "reason": (
                f"corpus changed since the index was built "
                f"({indexed} indexed document(s), {witness['documents']} on disk)"
            ),
        }
    return {**base, "state": CURRENT, "reason": "index matches the corpus"}


def refresh_if_needed(root: Path | str) -> dict:
    """Rebuild the projection when it is not CURRENT; write nothing when it is.

    The bounded mechanical repair writable continuation performs on its own.
    """
    root = Path(root).resolve()
    before = freshness(root)
    if before["state"] == CURRENT:
        return {"refreshed": False, "before": before, "after": before}
    index, path = refresh(root)
    after = freshness(root)
    return {
        "refreshed": True,
        "before": before,
        "after": after,
        "index": index,
        "path": str(path),
        "detail": (
            f"future gate projection was {before['state']} ({before.get('reason')}); "
            f"rebuilt {after['documents']} document(s)"
        ),
    }


# ---------------------------------------------------------------- records
#: Legacy side-car authority (FUTURE.md section 8). A reviewed historical
#: document needs no inline v1 header: the machine-owned record supplies the
#: lifecycle facts the prose could never be trusted to state as machine truth.
#: It binds to the document digest it reviewed, so edited bytes invalidate it.

_IMPLEMENTED_BY_RE = re.compile(r"(?i)\bimplemented\s+(?:by|as|through|in)\s+(T-\d+)")
_PARTIAL_IMPLEMENTED_RE = re.compile(
    r"(?i)\bpart(?:ial|ially)?\b[^\n]{0,60}?\bimplemented\b[^\n]{0,60}?(T-\d+)"
)
_NOT_IMPLEMENTED_RE = re.compile(r"(?i)\bnot\s+(?:yet\s+)?implemented\b")
_ARCHITECTURE_RE = re.compile(
    r"(?i)\bkeep[_\- ]?gated\b|\bfuture[_\- ]?architecture\b"
    r"|\barchitecture[_\- ]?seed\b|\barchitecture only\b"
)
_NOT_AUTHORIZED_RE = re.compile(r"(?i)\bnot\s+authori[sz]ed\b")
_FOLLOW_UP_RE = re.compile(r"(?i)\bfollow[_\- ]?up\b")
_DECLARED_DEFERRED_RE = re.compile(
    r"(?i)^\s*(?:#+\s*)?status\s*:\s*(?:proposal|deferred|registered)\b"
)


def records_dir(root: Path | str) -> Path:
    return Path(root).resolve() / RECORDS_REL


def record_path(root: Path | str, gate_id: str) -> Path:
    if not _ID_RE.match(str(gate_id)):
        raise ValueError(f"malformed gate id {gate_id!r}")
    return records_dir(root) / f"{gate_id}.json"


def load_record(root: Path | str, gate_id: str) -> dict | None:
    """One reviewed record, or None. Never raises on an absent side-car."""
    path = record_path(root, gate_id)
    if not os.path.lexists(path):
        return None
    try:
        witnessed = prove_owned_regular(path, kind="future gate record")
        raw = read_bound_regular_bytes(path, witnessed, max_bytes=_MAX_INDEX_BYTES)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(data, dict) or data.get("marker") != RECORD_MARKER:
        return None
    return data


def load_records(root: Path | str) -> dict[str, dict]:
    """Every readable reviewed record, keyed by gate id."""
    directory = records_dir(root)
    if not directory.is_dir():
        return {}
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("FG-*.json")):
        record = load_record(root, path.stem)
        if record is not None:
            out[path.stem] = record
    return out


def write_record(root: Path | str, gate_id: str, record: dict) -> Path:
    root = Path(root).resolve()
    path = record_path(root, gate_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    prove_owned_dir_chain(path.parent, kind="future gate records dir", ownership_root=root)
    payload = {**record, "marker": RECORD_MARKER, "gate": gate_id, "schema": SCHEMA_VERSION}
    safe_atomic_write_bytes(
        path,
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        kind="future gate record",
        ownership_root=root,
    )
    return path


def classify_legacy(
    document: GateDocument, board_tickets: dict | None = None
) -> tuple[str, str]:
    """Normalize ONE historical document's lifecycle facts from its own text.

    Closed vocabulary, explicit verdicts only, and every terminal claim is
    verified against canonical Work before it is recorded: a document that
    says `IMPLEMENTED by T-1373` is resolved only when T-1373 is `## DONE` on
    BOARD. Ambiguity stays `NEEDS_REVIEW` -- refinement records what the text
    already says, it never grants implementation authority.
    """
    match = _IMPLEMENTED_BY_RE.search(document.text or "")
    if match and not _NOT_IMPLEMENTED_RE.search(match.group(0)):
        ticket = match.group(1)
        entry = (board_tickets or {}).get(ticket)
        if entry is not None and entry.get("section") == "## DONE":
            return INELIGIBLE, f"already implemented by {ticket} (verified ## DONE on BOARD)"
        return NEEDS_REVIEW, (
            f"claims implementation by {ticket}, which is not ## DONE on BOARD; "
            "verify the named Work before any classification"
        )
    partial = _PARTIAL_IMPLEMENTED_RE.search(document.text or "")
    if partial:
        return DEFERRED, (
            f"part implemented by {partial.group(1)}; the residual stays deferred "
            "until a bounded slice is named"
        )
    if _NOT_IMPLEMENTED_RE.search(document.text or ""):
        return DEFERRED, "explicitly recorded as not implemented; preserved deferred intent"
    if _ARCHITECTURE_RE.search(document.text or ""):
        return DEFERRED, (
            "broad architecture record; kept gated until one bounded slice is named"
        )
    if _NOT_AUTHORIZED_RE.search(document.text or ""):
        return DEFERRED, "recorded, explicitly not authorized for implementation"
    if _FOLLOW_UP_RE.search(document.text or ""):
        return DEFERRED, "recorded follow-up work; preserved deferred intent"
    if _DECLARED_DEFERRED_RE.search(document.declared_status or "") or _DECLARED_DEFERRED_RE.search(
        document.text or ""
    ):
        return DEFERRED, f"declared status {document.declared_status or 'deferred'}"
    return NEEDS_REVIEW, "no explicit historical status found; review before any promotion"


def refine(
    root: Path | str,
    gate_id: str,
    *,
    board_tickets: dict | None = None,
    slice_text: str | None = None,
    evidence: tuple[str, ...] = (),
) -> dict:
    """Inspect ONE gate document and record its machine lifecycle verdict.

    Bounded by construction: it reads one document, classifies it with the
    closed vocabulary and writes the reviewed record plus the index entry. It
    is NOT implementation -- a refined gate is still deferred unless readiness
    proves otherwise, and promotion stays with the ordinary Source/Work ingress.
    """
    root = Path(root).resolve()
    index = load_index(root)
    if index is None or index.get("corrupt"):
        raise ValueError("future gate index is unreadable; run `saipen future refresh` first")
    gate = get_gate(root, gate_id)
    if not gate.present:
        return {
            "ok": False,
            "code": "FUTURE_GATE_ABSENT",
            "gate": gate_id,
            "detail": f"{gate_id} has no document on disk; refinement has nothing to read",
        }
    # An ambiguous record is the normal subject; a gate whose verdict is already
    # known can still be refined ONCE more to bind the facts it never declared.
    facts_supplied = bool(slice_text and evidence)
    if gate.state in (INELIGIBLE, PROMOTED) or (gate.state != NEEDS_REVIEW and not facts_supplied):
        return {
            "ok": True,
            "code": "FUTURE_GATE_NOT_AMBIGUOUS",
            "gate": gate_id,
            "state": gate.state,
            "detail": f"{gate_id} is {gate.state}, not NEEDS_REVIEW; nothing to refine",
        }
    document = next((doc for doc in read_documents(root) if doc.path == gate.path), None)
    if document is None:
        raise ValueError(f"{gate_id} names {gate.path!r}, which is not on disk")
    verdict, reason = classify_legacy(document, board_tickets)
    previous = load_record(root, gate_id) or {}
    facts: dict[str, object] = dict(previous.get("facts") or {})
    if slice_text and evidence:
        facts.update({"slice": slice_text, "evidence": list(evidence)})
    write_record(
        root,
        gate_id,
        {
            "path": document.path,
            "digest": document.digest,
            "verdict": verdict,
            "reason": reason,
            "declared_status": document.declared_status,
            "title": document.title,
            "facts": facts,
            "reviewed": True,
        },
    )
    gate.state = verdict
    gate.reasons = (reason,)
    gate.reviewed = True
    # The index entry carries the bound facts immediately: a refinement that
    # needs a second command to become visible is not a refinement.
    if facts.get("slice"):
        gate.slice = str(facts["slice"])
    if facts.get("evidence"):
        gate.evidence = tuple(str(ref) for ref in facts["evidence"])
    gate.problems = tuple(p for p in gate.problems if "no machine header" not in p)
    _replace(index, gate)
    write_index(root, index)
    return {
        "ok": True,
        "code": "FUTURE_GATE_REFINED",
        "gate": gate_id,
        "state": verdict,
        "path": document.path,
        "reason": reason,
        "detail": (
            f"{gate_id} refined to {verdict} from its own recorded status: {reason}; "
            "readiness and the ordinary promotion rules still apply"
        ),
    }


# ---------------------------------------------------------------- readiness


def bound_tickets(gate: Gate) -> list[str]:
    """The tickets promotion bound to `gate`, read from its slice records.

    Ownership of gate work is a machine fact (T-1641): the slice record
    `record_slice` writes when promotion creates the Work. A ticket whose text
    merely cites the gate id -- a defect report about the gate, a note -- binds
    nothing. Reading a mention as ownership flagged every such report as a
    duplicate implementation ticket and held the gate back for it.
    """
    bound: list[str] = []
    for slice_record in gate.slices:
        tid = str(slice_record.get("ticket") or "")
        if tid and tid not in bound:
            bound.append(tid)
    return bound


def _live_holders(gate: Gate, board_tickets: dict | None) -> list[tuple[str, str]]:
    """`(ticket, section)` for every bound ticket that is on BOARD and not DONE."""
    holders = []
    for tid in bound_tickets(gate):
        entry = (board_tickets or {}).get(tid)
        if entry is not None and entry.get("section") != "## DONE":
            holders.append((tid, str(entry.get("section"))))
    return holders


def readiness(
    gate: Gate, root: Path, board_tickets: dict | None = None
) -> tuple[str, tuple[str, ...]]:
    """Return `(verdict, reasons)` for one gate under FUTURE.md section 4.

    Mechanical only: every condition is checkable from the record plus the
    repository, so "eligible" never rests on a reading of prose.
    """
    root = Path(root)
    reasons: list[str] = []
    if gate.state in TERMINAL_STATES:
        return INELIGIBLE, (f"state {gate.state} is terminal",)
    if gate.state == NEEDS_REVIEW:
        return INELIGIBLE, ("historical record is ambiguous; review before any promotion",)
    if not gate.machine_readable and not gate.reviewed:
        return INELIGIBLE, ("no machine header; not routable",)
    if gate.open_slices:
        return INELIGIBLE, (f"{len(gate.open_slices)} slice(s) still open on a promoted gate",)
    if not gate.slice or gate.slice.startswith(PLACEHOLDER):
        reasons.append("no bounded slice declared")
    evidence = [ref for ref in gate.evidence if not ref.startswith(PLACEHOLDER)]
    if not evidence:
        reasons.append("no evidence reference")
    else:
        for ref in evidence:
            if _TICKET_RE.match(ref):
                continue
            if not (root / ref).exists():
                reasons.append(f"evidence path does not exist: {ref}")
    for ticket in gate.needs:
        entry = (board_tickets or {}).get(ticket)
        if entry is None:
            reasons.append(f"prerequisite {ticket} is not on BOARD")
        elif entry.get("section") != "## DONE":
            reasons.append(f"prerequisite {ticket} is {entry.get('section')}, not DONE")
    for tid, section in _live_holders(gate, board_tickets):
        reasons.append(f"{tid} already holds a slice of this gate and is {section}")
    if gate.problems:
        reasons.extend(gate.problems)
    if reasons:
        return INELIGIBLE, tuple(reasons)
    return ELIGIBLE, ()


def _priority_rank(gate: Gate) -> int:
    if gate.priority and re.fullmatch(r"P[0-3]", gate.priority):
        return int(gate.priority[1])
    return 9


def _basis_rank(gate: Gate) -> int:
    try:
        return BASES.index(gate.basis or "speculative")
    except ValueError:
        return len(BASES)


def select(
    gates: list[Gate], root: Path, board_tickets: dict | None = None
) -> tuple[Gate | None, list[dict]]:
    """Deterministic single selection (FUTURE.md section 6). Never two gates."""
    eligible: list[tuple[tuple, Gate]] = []
    evaluated: list[dict] = []
    for gate in gates:
        verdict, reasons = readiness(gate, root, board_tickets)
        evaluated.append({"id": gate.id, "verdict": verdict, "reasons": list(reasons)})
        if verdict != ELIGIBLE:
            continue
        done_tickets = {
            tid: entry
            for tid, entry in (board_tickets or {}).items()
            if entry.get("section") == "## DONE"
        }
        # prerequisite-unblocked AND tied to completed recent Work: the gate
        # whose prerequisites finished most recently ranks above one that
        # merely has prerequisites.
        recency = 0
        for tid in gate.needs:
            pos = sorted(done_tickets).index(tid) if tid in done_tickets else -1
            recency = max(recency, pos + 1)
        sort_key = (
            _priority_rank(gate),
            -recency,
            _basis_rank(gate),
            gate.estimate if gate.estimate is not None else 10**6,
            gate.recorded_at or "",
            gate.id,
        )
        eligible.append((sort_key, gate))
    if not eligible:
        return None, evaluated
    eligible.sort(key=lambda item: item[0])
    return eligible[0][1], evaluated


# ---------------------------------------------------------------- projection


def projection(project_root, board_tickets: dict | None = None) -> dict | None:
    """The read-only routing projection, or None when nothing is actionable.

    Never fabricates readiness. It also never claims the queue is EMPTY when it
    has merely not been looked at: a missing, corrupt or stale projection is
    reported as such with the mechanical repair it needs, so routing can
    refresh before -- never instead of -- the HUNT -> ADD fallthrough.
    """
    if project_root is None:
        return None
    root = Path(project_root)
    fresh = freshness(root)
    if fresh["state"] != CURRENT:
        index = load_index(root) or {}
        # MISSING over an EMPTY corpus is the one honest "there is nothing here":
        # there is nothing to discover, so nothing is repaired and every rung
        # below the Future layer is reached exactly as it was before.
        empty_corpus = fresh["state"] == MISSING and not fresh.get("documents")
        return {
            "indexed": bool(fresh["indexed"]),
            "index_state": fresh["state"],
            "future_documents_changed": not empty_corpus and fresh["state"] in (STALE, MISSING),
            "refresh_required": not empty_corpus,
            "eligible": [],
            "refinable": [],
            "counts": {},
            "documents": fresh.get("documents"),
            "canonical_next_action": "" if empty_corpus else "saipen future refresh",
            "detail": (
                "future_gate/ holds no documents: there is no future work to index, "
                "nothing to refresh, and routing below the Future layer is unchanged"
                if empty_corpus
                else f"future gate projection is {fresh['state']}: {fresh['reason']}. "
                "A stale or unreadable projection is not an empty one and is never "
                "proof that no future work exists -- refresh it before idle routing "
                "invents fresh work"
            ),
        }
    index = load_index(root) or {}
    gates = [Gate.from_dict(raw) for raw in index.get("gates") or []]
    counts = {state: sum(1 for g in gates if g.state == state) for state in sorted(STATES)}
    live = [g for g in gates if g.present and g.state in CANDIDATE_STATES]
    chosen, evaluated = select(live, root, board_tickets)
    # A reviewed record is machine truth about those bytes: it is offered for
    # refinement exactly once, so a corpus can never spin on one verdict.
    ambiguous = sorted(
        g.id for g in gates if g.present and g.state == NEEDS_REVIEW and not g.reviewed
    )
    base = {
        "indexed": True,
        "index_state": CURRENT,
        "future_documents_changed": False,
        "refresh_required": False,
        "refinable": ambiguous,
        "counts": counts,
        "evaluated": evaluated,
        "documents": fresh.get("documents"),
    }
    if chosen is None:
        return {
            **base,
            "eligible": [],
            "detail": (
                f"no eligible future gate among {len(live)} live candidate(s); "
                + (
                    f"{len(ambiguous)} record(s) still need bounded refinement"
                    if ambiguous
                    else "no record needs refinement"
                )
            ),
        }
    return {
        **base,
        "eligible": [chosen.id],
        "gate": chosen.as_dict(),
        "action": f"saipen future promote {chosen.id}",
        "detail": (
            f"{chosen.id} is ELIGIBLE: {chosen.slice} "
            f"(promotion binds one bounded slice; run `saipen future promote {chosen.id}`)"
        ),
    }


def status(root: Path | str, board_tickets: dict | None = None) -> dict:
    root = Path(root)
    fresh = freshness(root)
    index = load_index(root)
    if index is None:
        return {
            "indexed": False,
            "index_state": MISSING,
            "future_documents_changed": True,
            "counts": {},
            "gates": [],
            "detail": fresh["reason"],
        }
    if index.get("corrupt"):
        return {
            "indexed": False,
            "index_state": CORRUPT,
            "corrupt": index["corrupt"],
            "future_documents_changed": True,
            "counts": {},
            "gates": [],
            "detail": fresh["reason"],
        }
    gates = [Gate.from_dict(raw) for raw in index.get("gates") or []]
    live = [g for g in gates if g.present and g.state in CANDIDATE_STATES]
    chosen, evaluated = select(live, root, board_tickets)
    return {
        "indexed": True,
        "index_state": fresh["state"],
        "future_documents_changed": fresh["state"] == STALE,
        "counts": {state: sum(1 for g in gates if g.state == state) for state in sorted(STATES)},
        "gates": [g.as_dict() for g in gates],
        "evaluated": evaluated,
        "next": chosen.id if chosen else None,
    }


def get_gate(root: Path | str, gate_id: str) -> Gate:
    index = load_index(root)
    if not index or index.get("corrupt"):
        raise ValueError("future gate index is unreadable")
    for raw in index.get("gates") or []:
        if str(raw.get("id")) == gate_id:
            return Gate.from_dict(raw)
    raise ValueError(f"{gate_id} is not in the future gate index")


# ---------------------------------------------------------------- projection writes


def _replace(raw_index: dict, gate: Gate) -> None:
    gates = raw_index.setdefault("gates", [])
    for position, raw in enumerate(gates):
        if str(raw.get("id")) == gate.id:
            gates[position] = gate.as_dict()
            return
    gates.append(gate.as_dict())
    gates.sort(key=lambda item: str(item.get("id")))
    raw_index["corpus"] = {
        "documents": sum(1 for g in gates if g.get("present")),
        "absent": sum(1 for g in gates if not g.get("present")),
        "machine_readable": sum(1 for g in gates if g.get("machine_readable")),
    }


def evaluate(root: Path | str, board_tickets: dict | None = None, *, write: bool = True) -> dict:
    """Recompute each candidate gate's verdict and persist the reasons.

    Readiness is derived, not stored twice: the index keeps the verdict's
    reasons so an operator sees WHY, and the deterministic recompute means a
    stale verdict can never survive as readiness.

    A failed condition is NOT a lifecycle transition. A gate whose prerequisite
    is still TODO stays `DEFERRED` with the reason attached -- demoting it to
    the terminal `INELIGIBLE` would retire a perfectly good candidate for one
    unmet condition. `INELIGIBLE` and `NEEDS_REVIEW` are classifications made
    at intake, never side effects of a readiness check.

    Activation policy (T-1618). A reviewed `DEFERRED` gate whose conditions
    become true matures deterministically: `select` already routes on live
    readiness verdicts (never on stored state alone), so the gate is offered
    before HUNT on the first routing pass after its last prerequisite closes,
    and this function persists the `ELIGIBLE` state with cleared reasons.
    Maturation is monotone for the bytes it was proved on -- `refresh` keeps a
    lived `ELIGIBLE`/`PROMOTED`/terminal state over the historical review
    verdict, so BOARD flips and repeated passes converge instead of
    reconsidering forever. `ELIGIBLE` binds `matured_digest`: changed bytes, or
    an `ELIGIBLE` no proof bound, are re-proved here (T-1638). A review
    classifies its exact bytes once; it never demotes them on a later pass.
    """
    root = Path(root)
    index = load_index(root)
    if index is None or index.get("corrupt"):
        raise ValueError("future gate index is unreadable; run `saipen future refresh` first")
    gates = [Gate.from_dict(raw) for raw in index.get("gates") or []]
    changed = False
    for gate in gates:
        if not gate.present or gate.state not in CANDIDATE_STATES:
            continue
        touched = False
        if gate.state == ELIGIBLE and gate.matured_digest != gate.digest:
            # A maturation not bound to these bytes is re-proved, not trusted
            # (T-1638): it re-matures below in this same pass when it holds.
            gate.state = DEFERRED
            gate.matured_digest = None
            touched = True
        verdict, reasons = readiness(gate, root, board_tickets)
        touched = touched or gate.reasons != tuple(reasons)
        gate.reasons = reasons
        if verdict == ELIGIBLE and gate.state != ELIGIBLE:
            gate.state = ELIGIBLE
            gate.matured_digest = gate.digest
            touched = True
        if touched:
            changed = True
            _replace(index, gate)
    if write and changed:
        write_index(root, index)
    return status(root, board_tickets)


def add(
    root: Path | str,
    title: str,
    body: str,
    *,
    priority: str = "P2",
    evidence: tuple[str, ...] = (),
) -> Path:
    """Record a new gate document from an explicit operator statement."""
    root = Path(root)
    gate_dir = root / GATE_REL
    gate_dir.mkdir(parents=True, exist_ok=True)
    index = load_index(root)
    gate_id = _assign_id(index if index and not index.get("corrupt") else {"gates": []})
    slug = re.sub(r"[^a-z0-9]+", "-", _norm_title(title)).strip("-")[:60] or "gate"
    path = gate_dir / f"{gate_id}_{slug}.md"
    if path.exists():
        raise ValueError(f"{path.name} already exists")
    lines = [
        DOC_MARKER,
        f"id: {gate_id}",
        f"title: {title}",
        "state: DEFERRED",
        f"priority: {priority}",
        "basis: measured",
        "estimate: 1",
        f"slice: {PLACEHOLDER} name the ONE bounded unit this gate may promote",
        "needs: none",
        "evidence: "
        + (", ".join(evidence) if evidence else f"{PLACEHOLDER} reference an existing path"),
        "",
        f"# {title}",
        "",
        body.strip(),
        "",
        "Deferred authority candidate. Not Work, not a rule source, not",
        "implementation authority until `saipen future promote`.",
        "",
    ]
    prove_owned_dir_chain(gate_dir, kind="future_gate", ownership_root=root)
    safe_atomic_write_bytes(
        path,
        "\n".join(lines).encode("utf-8"),
        kind="future gate document",
        ownership_root=root,
    )
    return path


def promote(
    root: Path | str, gate_id: str, *, board_tickets: dict | None = None
) -> dict:
    """Bind ONE bounded slice of `gate_id` to canonical Work.

    Returns a plan -- the caller routes it through the ordinary Source/Work
    ingress (`entry.start_work`), which is the only authority allowed to
    create a ticket. This function never writes a BOARD line itself, so a
    duplicate request for the same gate is idempotent at the ingress owner
    rather than double-filed here.
    """
    root = Path(root)
    gate = get_gate(root, gate_id)
    verdict, reasons = readiness(gate, root, board_tickets)
    if verdict != ELIGIBLE:
        # A refusal is a verdict, never a retirement: the reasons are recorded
        # so the operator sees WHY, and the gate keeps its lifecycle state until
        # its owner (intake classification) decides otherwise.
        gate.reasons = reasons
        index = load_index(root)
        if index and not index.get("corrupt"):
            _replace(index, gate)
            write_index(root, index)
        return {
            "ok": False,
            "code": "FUTURE_GATE_NOT_ELIGIBLE",
            "gate": gate_id,
            "reasons": list(reasons),
            "detail": f"{gate_id} is not eligible for promotion: " + "; ".join(reasons),
        }
    return {
        "ok": True,
        "code": "FUTURE_GATE_READY",
        "gate": gate_id,
        "title": gate.title,
        "slice": gate.slice,
        "evidence": list(gate.evidence),
        "digest": gate.digest,
        "request_text": f"{gate.title} -- future gate {gate_id}, one bounded slice: {gate.slice}",
        "detail": (
            f"{gate_id} is ELIGIBLE; promote exactly this slice through the "
            f"ordinary Source/Work ingress (`saipen start --receipt SRC-###`) and "
            f"leave the residual deferred"
        ),
    }


def record_slice(
    root: Path | str,
    gate_id: str,
    *,
    ticket: str,
    closure: str = UNRESOLVED,
    digest: str | None = None,
) -> dict:
    """Bind a promoted slice to its ticket and update the gate's lifecycle."""
    root = Path(root)
    if closure not in (UNRESOLVED, *CLOSURES):
        raise ValueError(f"unknown slice closure {closure!r}")
    index = load_index(root)
    if not index or index.get("corrupt"):
        raise ValueError("future gate index is unreadable")
    gate = get_gate(root, gate_id)
    gate.state = PROMOTED
    gate.slices = [
        slice_record
        for slice_record in gate.slices
        if not (slice_record.get("ticket") == ticket and slice_record.get("slice") == gate.slice)
    ]
    gate.slices.append(
        {"ticket": ticket, "slice": gate.slice, "closure": closure, "digest": digest or gate.digest}
    )
    _replace(index, gate)
    write_index(root, index)
    return gate.as_dict()


# ---------------------------------------------------------------- validation


def validate_future_gate(
    root: Path | str, board_tickets: dict | None = None
) -> dict:
    """Check the future-gate surface against FUTURE.md; returns findings.

    Ten rules, each mechanical:

    1. an unreadable index is never an empty one;
    2. a missing index over a non-empty corpus is UNINDEXED, not READY;
    3. no two records claim the same id, path or digest -- one identity, once;
    4. a record's state agrees with what it proves (no contradictory pair);
    5. a resolved gate is not READY and never re-enters the candidate class;
    6. an unpromoted gate cannot own active implementation, and a promoted one
       links to canonical Work that still exists on BOARD; ownership is the
       slice record, so one live ticket holds one slice of one gate and a
       ticket that only cites a gate id owns nothing;
    7. the historical corpus is classified truthfully and nothing was
       destroyed: every present record has its document, and every document on
       disk is in the index;
    8: the shipped projection is neither corrupt nor schema-drifted -- a
       derived index is recoverable from the corpus, so an unreadable one is
       drift, never an empty queue;
    9: the projection corpus witness still matches the corpus, so a rename, an
       addition, a deletion or an edit is visible rather than invisible;
    10: a reviewed legacy record binds to the bytes it reviewed, carries a known
       verdict, and names a gate the index knows.
    """
    root = Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    index = load_index(root)
    documents = read_documents(root)
    fresh = freshness(root)
    if index is None:
        if documents:
            warnings.append(
                f"{len(documents)} future-gate document(s) are not indexed; run "
                "`saipen future refresh` (unindexed is truthful, never READY)"
            )
        return {"errors": errors, "warnings": warnings, "indexed": False, "counts": {}}
    if index.get("corrupt"):
        errors.append(
            f"future gate index is unreadable ({index['corrupt']}); an unreadable "
            "index is never an empty one -- run `saipen future refresh`"
        )
        return {"errors": errors, "warnings": warnings, "indexed": False, "counts": {}}
    if int(index.get("schema") or 0) != SCHEMA_VERSION:
        errors.append(
            f"future gate index carries schema {index.get('schema')!r}, expected "
            f"{SCHEMA_VERSION}: the projection drifted from its owner; rebuild it"
        )
    if fresh["state"] == STALE:
        warnings.append(
            f"future-gate-corpus-drift: {fresh['reason']}; ordinary continuation "
            "refreshes the projection before idle routing falls through to HUNT"
        )
    raw_gates = [Gate.from_dict(raw) for raw in index.get("gates") or []]
    counts = {state: sum(1 for g in raw_gates if g.state == state) for state in sorted(STATES)}

    # 10: a reviewed record is machine truth about specific bytes.
    known_ids = {g.id for g in raw_gates}
    digests = {g.path: g.digest for g in raw_gates if g.path and g.digest}
    for gate_id, record in sorted(load_records(root).items()):
        if gate_id not in known_ids:
            warnings.append(
                f"future gate record {gate_id}.json names no indexed gate; the record "
                "is orphaned derived state"
            )
            continue
        verdict = str(record.get("verdict") or "")
        if verdict not in STATES:
            errors.append(
                f"future gate record {gate_id}.json carries unknown verdict {verdict!r}"
            )
            continue
        recorded = str(record.get("digest") or "")
        current = digests.get(str(record.get("path") or ""))
        if recorded and current and recorded != current:
            warnings.append(
                f"future gate record {gate_id}.json reviews bytes the document no longer "
                "has; refine again before trusting its verdict"
            )

    # 3: one identity, once.
    for field_name, label in (("id", "id"), ("path", "document"), ("digest", "digest")):
        seen: dict[str, str] = {}
        for gate in raw_gates:
            value = getattr(gate, field_name, None)
            if not value:
                continue
            owner = seen.setdefault(str(value), gate.id)
            if owner != gate.id:
                errors.append(
                    f"future gate {gate.id} and {owner} share the same {label} {value!r}: "
                    "identity is reconciled per record, never twice"
                )

    # 7: the corpus is intact and truthfully classified.
    indexed_paths = {g.path for g in raw_gates if g.path}
    for gate in raw_gates:
        if gate.present and gate.path and not (root / gate.path).is_file():
            errors.append(
                f"future gate {gate.id} is indexed as present but {gate.path} does not exist"
            )
    for doc in documents:
        if doc.path not in indexed_paths:
            errors.append(
                f"future gate document {doc.path} is on disk but absent from the index"
            )

    for gate in raw_gates:
        # 4: a record's state must agree with what it proves.
        if gate.state not in STATES:
            errors.append(f"future gate {gate.id} carries unknown state {gate.state!r}")
            continue
        if not gate.machine_readable and not gate.reviewed and gate.state in CANDIDATE_STATES:
            errors.append(
                f"future gate {gate.id} has no machine header but is {gate.state}: an "
                "ambiguous historical record is NEEDS_REVIEW, never a live candidate"
            )
        if gate.open_slices and gate.state != PROMOTED:
            errors.append(
                f"future gate {gate.id} has {len(gate.open_slices)} open slice(s) but is "
                f"{gate.state}: a promoted slice is the only thing that opens one"
            )
        # 5: a resolved gate is not READY.
        if gate.closed and gate.state in CANDIDATE_STATES:
            errors.append(f"future gate {gate.id} is closed yet still {gate.state}")
        if gate.state in CANDIDATE_STATES:
            verdict, _reasons = readiness(gate, root, board_tickets)
            if verdict == ELIGIBLE and gate.state == DEFERRED:
                warnings.append(
                    f"future gate {gate.id} proves ELIGIBLE but is still DEFERRED; "
                    "`saipen future refresh` records the proven verdict"
                )
            if not gate.machine_readable:
                continue
        # 6: implementation authority follows promotion.
        for slice_record in gate.slices:
            tid = str(slice_record.get("ticket") or "")
            if not tid:
                errors.append(f"future gate {gate.id} records a slice with no ticket")
            elif board_tickets is not None and tid not in board_tickets:
                errors.append(
                    f"future gate {gate.id} names slice ticket {tid}, which is not on BOARD"
                )
    if board_tickets:
        held: dict[str, list[str]] = {}
        for gate in raw_gates:
            live = [tid for tid, _section in _live_holders(gate, board_tickets)]
            for tid in live:
                held.setdefault(tid, []).append(gate.id)
                if gate.state != PROMOTED:
                    errors.append(
                        f"BOARD ticket {tid} works on future gate {gate.id}, which is "
                        f"{gate.state}: an unpromoted gate cannot own active "
                        "implementation (it is a duplicate ticket, not a second slice)"
                    )
            by_slice: dict[str, list[str]] = {}
            for slice_record in gate.open_slices:
                tid = str(slice_record.get("ticket") or "")
                if tid in live:
                    by_slice.setdefault(str(slice_record.get("slice") or ""), []).append(tid)
            for tids in by_slice.values():
                if len(set(tids)) > 1:
                    errors.append(
                        f"future gate {gate.id} binds one slice to {', '.join(sorted(set(tids)))}: "
                        "the later ticket is a duplicate, not a second slice"
                    )
        for tid, gate_ids in sorted(held.items()):
            if len(gate_ids) > 1:
                errors.append(
                    f"BOARD ticket {tid} is bound as a slice of {', '.join(gate_ids)}: "
                    "one ticket takes one bounded slice of one gate"
                )
    return {
        "errors": errors,
        "warnings": warnings,
        "indexed": True,
        "counts": counts,
        "documents": len(documents),
    }
"""Lossless source receipts (T-1162, INC-LOSSY-WORK-SUMMARY-001).

A large user audit must survive model switches, context loss, session death
and cold continuation WITHOUT being reduced to a lossy BOARD summary. The
law (CORE § 1.10): PRESERVE THE SOURCE BEFORE INTERPRETING THE SOURCE;
BOARD MAY SUMMARIZE INTENT, BOARD MUST NEVER BE THE ONLY SURVIVING COPY OF
DETAILED INTENT.

Storage (all under ``.saipen/intake/``):

    active/SRC-###.md        immutable verbatim source body
    active/SRC-###.meta.json metadata sidecar (digest, kind, status, work)
    coverage/SRC-###.json    coverage ledger (requirement -> disposition)
    tombstones/SRC-###.json  small closed record (no body)
    ../archive/source/SRC-###.md+.meta cold body + metadata (excluded from hot scans)
    index.json               active + tombstone projection (rebuildable)

Invariants:

- SOURCE IS DATA. The body is opaque content during capture and is never
  routed as a command (a source containing "saipen ship" must not ship).
- DURABILITY PRECEDES INTERPRETATION: body + digest are written BEFORE any
  Work linkage commits.
- receipt_id is stable protocol identity; source_sha256 is content identity.
- EXACT canonical digest dedupes; near-duplicate is a new source; amendments
  are new immutable receipts linked ``amends``.
- CLOSED requires full terminal disposition on every actionable requirement
  (coverage ledger), never merely a green parent ticket.
- Integrity check recomputes the body digest; mismatch fails closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

from .journal import _atomic_write, owned_target_path
from .lock import project_writer_lock
from .paths import (
    prove_owned_dir_chain,
    prove_owned_regular,
    read_bound_regular_bytes,
    safe_unlink_owned,
)

ACTIVE_STATUS = "ACTIVE"
CLOSED_STATUS = "CLOSED"
SUPERSEDED_STATUS = "SUPERSEDED"
INVALID_STATUS = "INVALID"
ARCHIVED_STATUS = "ARCHIVED"

STATUSES = (ACTIVE_STATUS, CLOSED_STATUS, SUPERSEDED_STATUS, INVALID_STATUS)

SOURCE_KINDS = (
    "user_audit",
    "user_instruction",
    "implementation_mission",
    "review_handoff",
    "external_audit",
    "imported_spec",
    "corrective_followup",
)

INTENT_RE = re.compile(r"^(SRC-\d+)$")

# Requirement clause classes (agent-normalized, recorded durably).
CLAUSE_CLASSES = (
    "requirement",
    "invariant",
    "non-goal",
    "acceptance-criterion",
    "context",
    "example",
    "rationale",
    "open-question",
)

# Dispositions (terminal = enough evidence to close the source).
TERMINAL_DISPOSITIONS = {
    "IMPLEMENTED",
    "VERIFIED",
    "REJECTED",
    "DUPLICATE",
    "SUPERSEDED",
    "NOT_APPLICABLE",
}
ALL_DISPOSITIONS = TERMINAL_DISPOSITIONS | {"BLOCKED", "DEFERRED", "UNKNOWN"}
ACTIONABLE_CLASSES = {
    "requirement",
    "invariant",
    "non-goal",
    "acceptance-criterion",
    "open-question",
}

SCHEMA_VERSION = 1
INDEX_FIELDS = ("schema_version", "next_id", "active", "tombstones")


def capture_worthy(body: str, *, source_kind: str | None = None, explicit: bool = False) -> dict:
    """Bounded intake classification; length alone can never force capture."""
    if explicit:
        return {"capture_required": True, "reason": "explicit"}
    if source_kind in set(SOURCE_KINDS) - {"user_instruction"}:
        return {"capture_required": True, "reason": f"source_kind:{source_kind}"}
    text = body if isinstance(body, str) else ""
    heading = bool(
        re.search(
            r"(?im)^\s*(?:#{1,6}\s*)?(?:audit|mission|implementation mission|"
            r"implementation handoff|"
            r"review handoff|requirements?|acceptance criteria|specification)\b",
            text,
        )
    )
    sections = len(re.findall(r"(?m)^\s*(?:#{1,6}\s+|\d+[.)]\s+)", text))
    conditions = len(
        re.findall(
            r"(?i)\b(?:must|must not|required|expected|acceptance|invariant|"
            r"do not|never|always|verify|test)\b",
            text,
        )
    )
    required = heading and sections >= 2 and conditions >= 3
    return {
        "capture_required": required,
        "reason": "recognized-high-information-workflow" if required else "ordinary-input",
        "signals": {"heading": heading, "sections": sections, "conditions": conditions},
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _looks_sensitive(text: str) -> bool:
    """Conservative metadata signal; never redacts or echoes the source."""
    return bool(
        re.search(
            r"(?im)\b(?:api[_-]?key|access[_-]?token|password|secret)\b\s*[:=]\s*\S+",
            text,
        )
    )


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return os.path.islink(path) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _safe_path(root: Path, rel: str, *, expect_file: bool = False) -> Path:
    """Resolve one project-owned intake path without following hostile nodes."""
    path = owned_target_path(root, rel, kind="source-receipt")
    current = root
    for part in Path(rel).parts[:-1]:
        current = current / part
        if current.exists() and (_is_link_or_reparse(current) or not current.is_dir()):
            raise ValueError(f"unsafe source-receipt container: {current}")
    if path.exists():
        info = os.lstat(path)
        if _is_link_or_reparse(path) or (expect_file and not stat.S_ISREG(info.st_mode)):
            raise ValueError(f"unsafe source-receipt node: {path}")
    return path


# Bounded ownership-safe read caps for every intake authority file. These are
# generous safety ceilings (far above any legitimate receipt) so a hostile or
# corrupted authority can never force an unbounded descriptor read.
_INDEX_MAX = 4 * 1024 * 1024
_META_MAX = 1024 * 1024
_LEDGER_MAX = 8 * 1024 * 1024
_BODY_MAX = 64 * 1024 * 1024
_BOARD_MAX = 8 * 1024 * 1024


def _read_owned_file(
    root: Path, rel: str, *, kind: str = "source authority", max_bytes: int
) -> bytes:
    """Bounded ownership-safe read of ONE project-owned authority file.

    This is the single reader every intake READ path routes through (CORE-002):
    index, active metadata/body, Contract, coverage, tombstones, archive
    metadata/body, and the BOARD state consulted by intake.

    ``_safe_path`` proves every existing ancestor AND the final node with
    no-follow lstat (refuses symlink/junction/reparse/non-regular topology and
    any escape from the project root); ``prove_owned_regular`` re-witnesses the
    exact final node; ``read_bound_regular_bytes`` reads through a descriptor
    bound to that exact node, closing the lstat/open race and refusing any
    pivot or oversized authority.

    Raises ``FileNotFoundError`` when absent and ``ValueError`` (or its
    ``InvalidIdError`` subclass) on any unsafe/racing/oversized topology.
    """
    path = _safe_path(root, rel, expect_file=True)
    expected = prove_owned_regular(path, kind=kind)
    return read_bound_regular_bytes(path, expected, max_bytes=max_bytes)


def _valid_receipt_id(receipt_id: str) -> bool:
    return bool(INTENT_RE.fullmatch(receipt_id))


def _invalid_receipt_id(receipt_id: str) -> dict:
    return {"ok": False, "code": "INVALID_ID", "detail": receipt_id}


def _index_path(root: Path) -> Path:
    return root / ".saipen" / "intake" / "index.json"


def _active_dir(root: Path) -> Path:
    return root / ".saipen" / "intake" / "active"


def _coverage_dir(root: Path) -> Path:
    return root / ".saipen" / "intake" / "coverage"


def _tombstone_dir(root: Path) -> Path:
    return root / ".saipen" / "intake" / "tombstones"


def _archive_dir(root: Path) -> Path:
    return root / ".saipen" / "archive" / "source"


def _contract_dir(root: Path) -> Path:
    return root / ".saipen" / "intake" / "contracts"


def _read_index(root: Path) -> dict:
    try:
        raw = _read_owned_file(
            root, ".saipen/intake/index.json", kind="source intake index", max_bytes=_INDEX_MAX
        )
    except FileNotFoundError:
        return {"active": {}, "tombstones": {}, "next_id": 1}
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"malformed source intake index: {exc}") from exc
    if not isinstance(doc, dict):
        doc = {}
    for field in ("active", "tombstones"):
        if not isinstance(doc.get(field), dict):
            doc[field] = {}
    if not isinstance(doc.get("next_id"), int):
        doc["next_id"] = 1
    return doc


def _write_index(root: Path, index: dict) -> None:
    index["schema_version"] = SCHEMA_VERSION
    path = _safe_path(root, ".saipen/intake/index.json", expect_file=True)
    _atomic_write(path, _json_bytes(index), ownership_root=root)


def _read_meta(root: Path, receipt_id: str) -> dict | None:
    if not _valid_receipt_id(receipt_id):
        raise ValueError(f"invalid source receipt id: {receipt_id!r}")
    rel = f".saipen/intake/active/{receipt_id}.meta.json"
    try:
        raw = _read_owned_file(root, rel, kind="source receipt metadata", max_bytes=_META_MAX)
    except FileNotFoundError:
        return None
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"malformed source metadata {receipt_id}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"malformed source metadata {receipt_id}: root is not an object")
    return doc


def _write_meta(root: Path, receipt_id: str, meta: dict) -> None:
    path = _safe_path(root, f".saipen/intake/active/{receipt_id}.meta.json", expect_file=True)
    _atomic_write(path, _json_bytes(meta), ownership_root=root)


def _write_body(root: Path, receipt_id: str, body: str) -> None:
    path = _safe_path(root, f".saipen/intake/active/{receipt_id}.md", expect_file=True)
    if path.exists():
        raise ValueError(f"immutable source body already exists: {receipt_id}")
    _atomic_write(path, body.encode("utf-8"), ownership_root=root)


def _coverage_path(root: Path, receipt_id: str) -> Path:
    if not _valid_receipt_id(receipt_id):
        raise ValueError(f"invalid source receipt id: {receipt_id!r}")
    return _coverage_dir(root) / f"{receipt_id}.json"


def _read_coverage(root: Path, receipt_id: str) -> dict:
    rel = f".saipen/intake/coverage/{receipt_id}.json"
    try:
        raw = _read_owned_file(root, rel, kind="source coverage ledger", max_bytes=_LEDGER_MAX)
    except FileNotFoundError:
        return {"requirements": {}}
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"malformed source coverage {receipt_id}: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("requirements"), dict):
        raise ValueError(f"malformed source coverage {receipt_id}: requirements is not an object")
    return doc


def _write_coverage(root: Path, receipt_id: str, ledger: dict) -> None:
    path = _safe_path(root, f".saipen/intake/coverage/{receipt_id}.json", expect_file=True)
    _atomic_write(path, _json_bytes(ledger), ownership_root=root)


def _contract_path(root: Path, receipt_id: str) -> Path:
    if not _valid_receipt_id(receipt_id):
        raise ValueError(f"invalid source receipt id: {receipt_id!r}")
    return _contract_dir(root) / f"{receipt_id}.json"


def _read_contract(root: Path, receipt_id: str) -> dict | None:
    rel = f".saipen/intake/contracts/{receipt_id}.json"
    try:
        raw = _read_owned_file(root, rel, kind="source Work Contract", max_bytes=_LEDGER_MAX)
    except FileNotFoundError:
        return None
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"malformed source Work Contract {receipt_id}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"malformed source Work Contract {receipt_id}: root is not an object")
    return value


def _write_contract(root: Path, receipt_id: str, contract: dict) -> None:
    path = _safe_path(root, f".saipen/intake/contracts/{receipt_id}.json", expect_file=True)
    _atomic_write(path, _json_bytes(contract), ownership_root=root)


def _write_contract_revision(root: Path, receipt_id: str, contract: dict) -> None:
    revision = int(contract.get("interpretation_revision", 0))
    path = _safe_path(
        root,
        f".saipen/intake/contracts/{receipt_id}.r{revision:03d}.json",
        expect_file=True,
    )
    if path.exists():
        raise ValueError(f"contract revision already exists: {receipt_id} r{revision}")
    _atomic_write(path, _json_bytes(contract), ownership_root=root)


def _write_tombstone(root: Path, receipt_id: str, tombstone: dict) -> None:
    path = _safe_path(root, f".saipen/intake/tombstones/{receipt_id}.json", expect_file=True)
    _atomic_write(path, _json_bytes(tombstone), ownership_root=root)


def _link_board_projection(root: Path, work: str, receipt_id: str) -> dict:
    """Compact BOARD link written only after source authority is durable."""
    from . import codec
    from .board import parse_board, set_ticket_field

    path = _safe_path(root, ".saipen/BOARD.md", expect_file=True)
    try:
        raw = _read_owned_file(
            root, ".saipen/BOARD.md", kind="source BOARD authority", max_bytes=_BOARD_MAX
        )
        document = codec.read_document(path, raw=raw)
        text = document.text_norm
    except (OSError, ValueError) as exc:
        return {"ok": False, "code": "ORPHAN_RECEIPT", "detail": str(exc)}
    board = parse_board(text)
    ticket = board.get("tickets", {}).get(work)
    if not ticket:
        return {
            "ok": False,
            "code": "ORPHAN_RECEIPT",
            "detail": f"source durable but linked Work {work} is missing",
        }
    existing = [
        value.strip()
        for value in str(ticket.get("fields", {}).get("source_receipts") or "").split(",")
        if value.strip()
    ]
    if receipt_id in existing:
        return {"ok": True, "code": "SOURCE_LINKED", "work": work}
    existing.append(receipt_id)
    replacement = set_ticket_field(ticket["raw"], "source_receipts", ",".join(existing))
    updated = text.replace(ticket["raw"], replacement, 1)
    if updated == text:
        return {
            "ok": False,
            "code": "ORPHAN_RECEIPT",
            "detail": f"could not project {receipt_id} onto BOARD {work}",
        }
    _atomic_write(path, document.encode(updated), ownership_root=root)
    return {"ok": True, "code": "SOURCE_LINKED", "work": work}


def _board_source_links(root: Path) -> dict[str, set[str]]:
    """Return the reverse BOARD projection: Work -> durable receipt IDs."""
    from . import codec
    from .board import parse_board

    raw = _read_owned_file(
        root, ".saipen/BOARD.md", kind="source BOARD authority", max_bytes=_BOARD_MAX
    )
    document = codec.read_document(root / ".saipen" / "BOARD.md", raw=raw)
    board = parse_board(document.text_norm)
    if board.get("errors"):
        raise ValueError("BOARD parse error: " + "; ".join(board["errors"][:3]))
    result: dict[str, set[str]] = {}
    for work, ticket in board.get("tickets", {}).items():
        values = {
            value.strip()
            for value in str(ticket.get("fields", {}).get("source_receipts") or "").split(",")
            if value.strip()
        }
        if values:
            result[work] = values
    return result


def _board_has_work(root: Path, work: str) -> bool:
    """Canonical BOARD authority check (CORE-004): does `work` exist?

    Only this canonical projection may authorize a durable Work linkage.
    Reads through the bounded ownership-safe reader and never through a raw
    pathname, so a hostile/racing BOARD is refused rather than consulted.
    """
    if not work:
        return False
    try:
        from .board import parse_board

        raw = _read_owned_file(
            root, ".saipen/BOARD.md", kind="source BOARD authority", max_bytes=_BOARD_MAX
        )
        board = parse_board(raw.decode("utf-8-sig"))
    except (OSError, ValueError):
        return False
    return work in board.get("tickets", {})


def _amends_resolvable(root: Path, amends: str) -> bool:
    """CORE-004: an `amends` target must name an existing receipt identity
    across the active OR tombstone history before it is made authoritative.
    A dangling amendment reference is never committed to durable metadata."""
    if not _valid_receipt_id(amends):
        return False
    index = _read_index(root)
    if amends in index.get("active", {}):
        return True
    return amends in index.get("tombstones", {})


def _contract_integrity(root: Path, receipt_id: str, meta: dict) -> dict:
    """Bind the derived Contract and coverage ledger to one source digest."""
    contract = _read_contract(root, receipt_id)
    if not contract or contract.get("source_sha256") != meta.get("source_sha256"):
        return {"ok": False, "code": "CONTRACT_DRIFT", "receipt": receipt_id}
    ledger = _read_coverage(root, receipt_id)
    clauses = contract.get("clauses")
    requirements = ledger.get("requirements")
    if not isinstance(clauses, dict) or not isinstance(requirements, dict):
        return {
            "ok": False,
            "code": "CONTRACT_DRIFT",
            "receipt": receipt_id,
            "detail": "Contract clauses or coverage requirements are not objects",
        }
    if set(clauses) != set(requirements):
        return {
            "ok": False,
            "code": "CONTRACT_DRIFT",
            "receipt": receipt_id,
            "detail": "Contract and coverage clause identities differ",
        }
    return {"ok": True, "code": "CONTRACT_INTEGRITY_OK", "receipt": receipt_id}


def _find_exact_duplicate(root: Path, digest: str) -> dict | None:
    index = _read_index(root)
    for receipt_id in index.get("active", {}):
        meta = _read_meta(root, receipt_id)
        if meta and meta.get("source_sha256") == digest:
            integrity = verify_integrity(root, receipt_id)
            if not integrity["ok"]:
                return {"receipt_id": receipt_id, "meta": meta, "invalid": integrity}
            return {"receipt_id": receipt_id, "meta": meta}
    for receipt_id, tomb in index.get("tombstones", {}).items():
        if tomb.get("source_sha256") == digest:
            return {"receipt_id": receipt_id, "tombstone": tomb, "closed": True}
    # Crash window: body durable, process died before metadata/index commit.
    # Exact retry must adopt this orphan instead of allocating SRC-N+1.
    active = _active_dir(root)
    if active.is_dir() and not _is_link_or_reparse(active):
        for body_path in sorted(active.glob("SRC-*.md")):
            receipt_id = body_path.stem
            if not INTENT_RE.fullmatch(receipt_id) or _is_link_or_reparse(body_path):
                continue
            try:
                raw = _read_owned_file(
                    root,
                    f".saipen/intake/active/{receipt_id}.md",
                    kind="source body",
                    max_bytes=_BODY_MAX,
                )
                if hashlib.sha256(raw).hexdigest() == digest:
                    return {"receipt_id": receipt_id, "orphan": True}
            except (OSError, ValueError):
                continue
    return None


def _next_receipt_id(root: Path, index: dict) -> str:
    used: set[int] = set()
    for collection in (index.get("active", {}), index.get("tombstones", {})):
        for receipt_id in collection:
            if INTENT_RE.fullmatch(receipt_id):
                used.add(int(receipt_id.split("-", 1)[1]))
    for directory in (_active_dir(root), _archive_dir(root), _tombstone_dir(root)):
        if not directory.is_dir() or _is_link_or_reparse(directory):
            continue
        for path in directory.glob("SRC-*.*"):
            match = re.match(r"SRC-(\d+)", path.name)
            if match:
                used.add(int(match.group(1)))
    value = max(int(index.get("next_id", 1)), max(used, default=0) + 1)
    while value in used:
        value += 1
    index["next_id"] = value + 1
    return f"SRC-{value:03d}"


def capture(
    root: Path | str,
    body: str,
    *,
    source_kind: str = "user_instruction",
    work: str | None = None,
    amends: str | None = None,
    force: bool = False,
    transport_transform: str = "none",
    newline_normalization: str = "none",
) -> dict:
    """Capture an authoritative source VERBATIM before any interpretation.

    Idempotent: an exact canonical digest returns the existing receipt
    (duplicate=true) and never creates a second one. Body is written first,
    then metadata, then the index -- so a crash after the body leaves a
    detectable orphan that recovery can reconcile, and a crash before any
    durable write loses nothing.
    """
    root = Path(root)
    if not isinstance(body, str) or not body:
        return {"ok": False, "code": "INVALID_SOURCE", "detail": "empty source body"}
    if source_kind not in SOURCE_KINDS:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"unknown source kind {source_kind!r}",
        }
    if work is not None and not re.fullmatch(r"T-\d+", work):
        return {"ok": False, "code": "INVALID_ID", "detail": f"work {work!r}"}
    if amends and not INTENT_RE.fullmatch(amends):
        return {"ok": False, "code": "INVALID_ID", "detail": f"amends {amends!r}"}
    digest = _sha256(body)
    try:
        with project_writer_lock(root):
            existing = _find_exact_duplicate(root, digest)
            if existing and not force:
                if existing.get("invalid"):
                    return existing["invalid"]
                if existing.get("closed"):
                    return {
                        "ok": True,
                        "code": "SOURCE_DUPLICATE_CLOSED",
                        "receipt": existing["receipt_id"],
                        "source_sha256": digest,
                        "status": CLOSED_STATUS,
                        "closure": existing.get("tombstone"),
                    }
                if not existing.get("orphan"):
                    meta = existing.get("meta") or {}
                    linked_work = meta.get("linked_work")
                    if work and linked_work and linked_work != work:
                        return {
                            "ok": False,
                            "code": "SOURCE_WORK_CONFLICT",
                            "receipt": existing["receipt_id"],
                            "linked_work": linked_work,
                            "requested_work": work,
                        }
                    if amends and not _amends_resolvable(root, amends):
                        return {
                            "ok": False,
                            "code": "VALIDATION_FAILED",
                            "detail": f"amends references unknown receipt {amends}",
                        }
                    if work and not linked_work:
                        if not _board_has_work(root, work):
                            return {
                                "ok": False,
                                "code": "ORPHAN_RECEIPT",
                                "receipt": existing["receipt_id"],
                                "detail": f"linked Work {work} is missing from BOARD",
                            }
                        linked_work = work
                        meta["linked_work"] = work
                        _write_meta(root, existing["receipt_id"], meta)
                        index = _read_index(root)
                        index["active"][existing["receipt_id"]]["linked_work"] = work
                        _write_index(root, index)
                    linkage = (
                        _link_board_projection(root, linked_work, existing["receipt_id"])
                        if linked_work
                        else {"ok": True}
                    )
                    if not linkage.get("ok"):
                        return {
                            "ok": False,
                            "code": "ORPHAN_RECEIPT",
                            "receipt": existing["receipt_id"],
                            "detail": linkage.get("detail"),
                        }
                    return {
                        "ok": True,
                        "code": "SOURCE_DUPLICATE",
                        "receipt": existing["receipt_id"],
                        "source_sha256": digest,
                        "status": meta.get("status", ACTIVE_STATUS),
                        "linked_work": linked_work,
                        "coverage": coverage_summary(root, existing["receipt_id"]),
                    }

            index = _read_index(root)
            receipt_id = (
                existing["receipt_id"]
                if existing and existing.get("orphan") and not force
                else _next_receipt_id(root, index)
            )
            if amends and not _amends_resolvable(root, amends):
                return {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"amends references unknown receipt {amends}",
                }
            # CORE-004: never commit an invalid Work reference as authoritative.
            # The canonical BOARD decides whether `work` may be linked. A
            # missing/invalid Work leaves the captured source recoverably
            # UNLINKED (linked_work stays None in durable metadata + index);
            # a later exact retry with the correct Work attaches it.
            linked_work = work if (work and _board_has_work(root, work)) else None
            meta = {
                "receipt_id": receipt_id,
                "received_at": _utc(),
                "source_kind": source_kind,
                "source_sha256": digest,
                "status": ACTIVE_STATUS,
                "linked_work": linked_work,
                "sensitive": _looks_sensitive(body),
                "schema_version": SCHEMA_VERSION,
                "transport": {
                    "source_encoding": "utf-8",
                    "newline_normalization": newline_normalization,
                    "transport_transform": transport_transform,
                },
            }
            if amends:
                meta["amends"] = amends

            # CRASH ORDER: body first, verified readback, then metadata,
            # contract/coverage, finally the discoverability index.
            if not (existing and existing.get("orphan") and not force):
                _write_body(root, receipt_id, body)
            try:
                raw_body = _read_owned_file(
                    root,
                    f".saipen/intake/active/{receipt_id}.md",
                    kind="source body",
                    max_bytes=_BODY_MAX,
                )
            except (ValueError, OSError) as exc:
                return {"ok": False, "code": "SOURCE_CORRUPTION", "detail": str(exc)}
            actual = hashlib.sha256(raw_body).hexdigest()
            if actual != digest:
                return {
                    "ok": False,
                    "code": "SOURCE_CORRUPTION",
                    "recorded": digest,
                    "actual": actual,
                }
            _write_meta(root, receipt_id, meta)
            _write_contract(
                root,
                receipt_id,
                {
                    "schema_version": SCHEMA_VERSION,
                    "derived_from": receipt_id,
                    "source_sha256": digest,
                    "derived_at": None,
                    "interpretation_revision": 0,
                    "clauses": {},
                },
            )
            _write_coverage(
                root,
                receipt_id,
                {"schema_version": SCHEMA_VERSION, "requirements": {}},
            )
            index["active"][receipt_id] = {
                "source_sha256": digest,
                "linked_work": linked_work,
            }
            _write_index(root, index)
            linkage = (
                _link_board_projection(root, linked_work, receipt_id)
                if linked_work is not None
                else {"ok": True}
            )
            return {
                "ok": bool(linkage.get("ok")),
                "code": "ORPHAN_RECEIPT_RECOVERED"
                if existing and existing.get("orphan") and not force
                else (
                    "SOURCE_RECEIVED"
                    if linkage.get("ok")
                    else linkage.get("code", "ORPHAN_RECEIPT")
                ),
                "receipt": receipt_id,
                "source_sha256": digest,
                "status": ACTIVE_STATUS,
                "linked_work": linked_work,
                "duplicate": False,
                "requirements": 0,
                "sensitive": meta["sensitive"],
                "detail": linkage.get("detail"),
            }
    except (OSError, PermissionError, ValueError) as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}


def add_requirement(
    root: Path | str, receipt_id: str, *, rid: str, text: str, clause_class: str = "requirement"
) -> dict:
    root = Path(root)
    if not INTENT_RE.fullmatch(receipt_id):
        return {"ok": False, "code": "INVALID_ID", "detail": receipt_id}
    if re.fullmatch(r"R\d+", rid):
        rid = f"{receipt_id}:{rid}"
    if not re.fullmatch(rf"{re.escape(receipt_id)}:R\d+", rid):
        return {"ok": False, "code": "INVALID_ID", "detail": rid}
    if not text.strip():
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": "empty clause text"}
    if clause_class not in CLAUSE_CLASSES:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"unknown clause class {clause_class!r}",
        }
    try:
        with project_writer_lock(root):
            meta = _read_meta(root, receipt_id)
            if not meta:
                return {
                    "ok": False,
                    "code": "TICKET_NOT_FOUND",
                    "detail": f"no active receipt {receipt_id}",
                }
            integrity = verify_integrity(root, receipt_id)
            if not integrity["ok"]:
                return integrity
            ledger = _read_coverage(root, receipt_id)
            if rid in ledger["requirements"]:
                return {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"requirement {rid} exists",
                }
            clause = {
                "class": clause_class,
                "text": text,
                "actionable": clause_class in ACTIONABLE_CLASSES,
                "disposition": "UNKNOWN",
                "work": meta.get("linked_work"),
                "evidence": None,
                "verification": None,
            }
            ledger["requirements"][rid] = clause
            contract = _read_contract(root, receipt_id)
            if not contract or contract.get("source_sha256") != meta.get("source_sha256"):
                return {
                    "ok": False,
                    "code": "CONTRACT_DRIFT",
                    "detail": "contract missing or source digest mismatch",
                }
            contract["interpretation_revision"] = (
                int(contract.get("interpretation_revision", 0)) + 1
            )
            contract["derived_at"] = _utc()
            contract.setdefault("clauses", {})[rid] = {
                "class": clause_class,
                "text": text,
                "actionable": clause_class in ACTIONABLE_CLASSES,
            }
            _write_contract(root, receipt_id, contract)
            _write_contract_revision(root, receipt_id, contract)
            _write_coverage(root, receipt_id, ledger)
            return {"ok": True, "code": "REQUIREMENT_ADDED", "receipt": receipt_id, "rid": rid}
    except (OSError, PermissionError, ValueError) as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}


def set_disposition(
    root: Path | str,
    receipt_id: str,
    rid: str,
    disposition: str,
    *,
    work: str | None = None,
    evidence: str | None = None,
    verification: str | None = None,
) -> dict:
    root = Path(root)
    if not _valid_receipt_id(receipt_id):
        return _invalid_receipt_id(receipt_id)
    if disposition not in ALL_DISPOSITIONS:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": f"disposition {disposition!r}"}
    if re.fullmatch(r"R\d+", rid):
        rid = f"{receipt_id}:{rid}"
    try:
        with project_writer_lock(root):
            integrity = verify_integrity(root, receipt_id)
            if not integrity["ok"]:
                return integrity
            ledger = _read_coverage(root, receipt_id)
            if rid not in ledger["requirements"]:
                return {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": f"unknown requirement {rid}",
                }
            entry = ledger["requirements"][rid]
            if disposition in TERMINAL_DISPOSITIONS and entry.get("actionable", True):
                if not evidence:
                    return {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "terminal actionable disposition requires evidence",
                    }
                if disposition in {"IMPLEMENTED", "VERIFIED"} and not verification:
                    return {
                        "ok": False,
                        "code": "VALIDATION_FAILED",
                        "detail": "implemented/verified disposition requires verification",
                    }
            entry["disposition"] = disposition
            if work:
                entry["work"] = work
            if evidence:
                entry["evidence"] = evidence
            if verification:
                entry["verification"] = verification
            _write_coverage(root, receipt_id, ledger)
            return {
                "ok": True,
                "code": "COVERAGE_UPDATED",
                "receipt": receipt_id,
                "rid": rid,
                "disposition": disposition,
            }
    except (OSError, PermissionError, ValueError) as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}


def coverage_summary(root: Path | str, receipt_id: str) -> dict:
    root = Path(root)
    ledger = _read_coverage(root, receipt_id)
    requirements = ledger["requirements"]
    counts: dict[str, int] = {}
    for entry in requirements.values():
        disp = entry.get("disposition", "UNKNOWN")
        counts[disp] = counts.get(disp, 0) + 1
    actionable = {
        rid: entry
        for rid, entry in requirements.items()
        if entry.get("actionable", entry.get("class") in ACTIONABLE_CLASSES)
    }
    unresolved = [
        rid
        for rid, entry in actionable.items()
        if entry.get("disposition") not in TERMINAL_DISPOSITIONS
        or not entry.get("evidence")
        or (
            entry.get("disposition") in {"IMPLEMENTED", "VERIFIED"}
            and not entry.get("verification")
        )
    ]
    return {
        "receipt": receipt_id,
        "requirements": len(requirements),
        "actionable": len(actionable),
        "terminal": len(actionable) - len(unresolved),
        "dispositions": counts,
        "unresolved": unresolved,
    }


def coverage_complete(root: Path | str, receipt_id: str) -> bool:
    summary = coverage_summary(root, receipt_id)
    return summary["actionable"] > 0 and not summary["unresolved"]


def verify_integrity(root: Path | str, receipt_id: str) -> dict:
    """Reread boundary gate: stored body digest MUST equal recorded digest."""
    root = Path(root)
    if not _valid_receipt_id(receipt_id):
        return _invalid_receipt_id(receipt_id)
    meta = _read_meta(root, receipt_id)
    if not meta:
        return {"ok": False, "code": "INVALID", "detail": "receipt metadata missing"}
    rel = f".saipen/intake/active/{receipt_id}.md"
    try:
        body = _read_owned_file(root, rel, kind="source body", max_bytes=_BODY_MAX)
    except FileNotFoundError:
        return {"ok": False, "code": "INVALID", "detail": "receipt body missing"}
    except (ValueError, OSError) as exc:
        return {"ok": False, "code": "SOURCE_CORRUPTION", "detail": str(exc)}
    actual = hashlib.sha256(body).hexdigest()
    if actual != meta.get("source_sha256"):
        return {
            "ok": False,
            "code": "SOURCE_CORRUPTION",
            "recorded": meta.get("source_sha256"),
            "actual": actual,
        }
    return {"ok": True, "code": "SOURCE_INTEGRITY_OK", "receipt": receipt_id}


def _work_is_done(root: Path, work: str | None) -> bool:
    if not work:
        return True
    try:
        from .board import parse_board

        raw = _read_owned_file(
            root, ".saipen/BOARD.md", kind="source BOARD authority", max_bytes=_BOARD_MAX
        )
        board = parse_board(raw.decode("utf-8-sig"))
    except (OSError, ValueError):
        return False
    ticket = board.get("tickets", {}).get(work)
    return bool(ticket and ticket.get("section") == "## DONE")


def work_closure_gate(root: Path | str, work: str) -> dict:
    """Mechanical DONE/SHIP gate for every active receipt linked to Work."""
    root = Path(root)
    try:
        index = _read_index(root)
        board_links = _board_source_links(root).get(work, set())
    except (OSError, ValueError) as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc), "work": work}
    active_linked: set[str] = set()
    for receipt_id in index.get("active", {}):
        meta = _read_meta(root, receipt_id)
        if not meta or meta.get("linked_work") != work:
            continue
        active_linked.add(receipt_id)
    missing_projection = active_linked - board_links
    if missing_projection:
        receipt_id = min(missing_projection)
        return {
            "ok": False,
            "code": "SOURCE_LINKAGE_MISSING",
            "receipt": receipt_id,
            "work": work,
        }
    linked: list[str] = []
    for receipt_id in sorted(board_links):
        if not _valid_receipt_id(receipt_id):
            return _invalid_receipt_id(receipt_id) | {"work": work}
        meta = _read_meta(root, receipt_id) if receipt_id in index.get("active", {}) else None
        if not meta:
            tomb = index.get("tombstones", {}).get(receipt_id)
            if (
                isinstance(tomb, dict)
                and tomb.get("status") == CLOSED_STATUS
                and tomb.get("linked_work") == work
            ):
                linked.append(receipt_id)
                continue
            return {
                "ok": False,
                "code": "SOURCE_RECEIPT_MISSING",
                "receipt": receipt_id,
                "work": work,
            }
        if meta.get("linked_work") != work:
            return {
                "ok": False,
                "code": "SOURCE_LINKAGE_DRIFT",
                "receipt": receipt_id,
                "work": work,
            }
        linked.append(receipt_id)
        integrity = verify_integrity(root, receipt_id)
        if not integrity["ok"]:
            return integrity | {"receipt": receipt_id, "work": work}
        contract_gate = _contract_integrity(root, receipt_id, meta)
        if not contract_gate["ok"]:
            return contract_gate | {"work": work}
        summary = coverage_summary(root, receipt_id)
        if not coverage_complete(root, receipt_id):
            return {
                "ok": False,
                "code": "SOURCE_UNRESOLVED",
                "receipt": receipt_id,
                "work": work,
                "coverage": summary,
            }
    return {"ok": True, "code": "SOURCE_COVERAGE_COMPLETE", "work": work, "receipts": linked}


def boundary_gate(root: Path | str, work: str, boundary: str) -> dict:
    """Real targeted original-body read at meaningful execution boundaries."""
    root = Path(root)
    try:
        index = _read_index(root)
        board_links = _board_source_links(root).get(work, set())
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": str(exc),
            "boundary": boundary,
        }
    checked: list[str] = []
    for receipt_id in sorted(board_links):
        if not _valid_receipt_id(receipt_id):
            return _invalid_receipt_id(receipt_id) | {"boundary": boundary}
        meta = _read_meta(root, receipt_id) if receipt_id in index.get("active", {}) else None
        if not meta:
            return {
                "ok": False,
                "code": "SOURCE_RECEIPT_MISSING",
                "receipt": receipt_id,
                "boundary": boundary,
            }
        if meta.get("linked_work") != work:
            return {
                "ok": False,
                "code": "SOURCE_LINKAGE_DRIFT",
                "receipt": receipt_id,
                "boundary": boundary,
            }
        integrity = verify_integrity(root, receipt_id)
        if not integrity["ok"]:
            return integrity | {"receipt": receipt_id, "boundary": boundary}
        contract_gate = _contract_integrity(root, receipt_id, meta)
        if not contract_gate["ok"]:
            return contract_gate | {"boundary": boundary}
        checked.append(receipt_id)
    return {
        "ok": True,
        "code": "SOURCE_REREAD_OK",
        "boundary": boundary,
        "receipts": checked,
    }


def release_gate(root: Path | str, current_work: str | None = None) -> dict:
    """Fail ship closed while authoritative active source scope is unresolved."""
    root = Path(root)
    try:
        board_links = _board_source_links(root)
    except (OSError, ValueError) as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}
    checked: set[str] = set()
    for work in sorted(board_links):
        gate = work_closure_gate(root, work)
        if not gate.get("ok"):
            return gate
        checked.update(gate.get("receipts", []))
        if work != current_work and not _work_is_done(root, work):
            return {
                "ok": False,
                "code": "SOURCE_WORK_ACTIVE",
                "work": work,
            }
    receipts = active_receipts(root)
    for item in receipts:
        receipt_id = item["receipt"]
        if receipt_id in checked:
            continue
        integrity = verify_integrity(root, receipt_id)
        gate = (
            integrity
            if not integrity["ok"]
            else {
                "ok": coverage_complete(root, receipt_id),
                "code": "SOURCE_COVERAGE_COMPLETE"
                if coverage_complete(root, receipt_id)
                else "SOURCE_UNRESOLVED",
            }
        )
        if not gate.get("ok"):
            return gate | {"receipt": receipt_id}
        linked = item.get("linked_work")
        if linked and linked != current_work and not _work_is_done(root, linked):
            return {
                "ok": False,
                "code": "SOURCE_WORK_ACTIVE",
                "receipt": receipt_id,
                "work": linked,
            }
    return {
        "ok": True,
        "code": "SOURCE_RELEASE_COVERAGE_COMPLETE",
        "receipts": sorted(checked | {item["receipt"] for item in receipts}),
    }


def _is_archive_commit_pending(root: Path, receipt_id: str, index: dict) -> bool:
    """True when `receipt_id` sits in an interrupted close (CORE-003): still
    indexed as active, the active surface is cleared, and complete archived
    artifacts are present. This is the resumable crash state the close
    transaction must settle before it can be retried."""
    if not isinstance(index.get("active", {}).get(receipt_id), dict):
        return False
    active_present = []
    for active_rel in (
        f".saipen/intake/active/{receipt_id}.md",
        f".saipen/intake/active/{receipt_id}.meta.json",
    ):
        try:
            _read_owned_file(root, active_rel, kind="source receipt probe", max_bytes=_META_MAX)
        except FileNotFoundError:
            active_present.append(False)
            continue
        except (ValueError, OSError):
            return False
        active_present.append(True)
    for archived_rel in (
        f".saipen/archive/source/{receipt_id}.md",
        f".saipen/archive/source/{receipt_id}.meta.json",
    ):
        try:
            _read_owned_file(root, archived_rel, kind="source archive probe", max_bytes=_META_MAX)
        except FileNotFoundError:
            return False
        except (ValueError, OSError):
            return False
    return not all(active_present)


def _settle_archive_commit(root: Path, receipt_id: str, index: dict) -> dict | None:
    """Settle an ARCHIVE_COMMIT_PENDING close transaction (CORE-003).

    Never infers closure from an archive body alone: it verifies the archived
    body digest and the archived Contract/coverage ledger against the
    still-indexed projection, reconstructs and writes the EXACT tombstone from
    the archived metadata (which retains the close evidence), then atomically
    settles the index active->tombstone. Returns the ``SOURCE_CLOSED`` result
    on success, a stable refusal on any evidence failure, or None when the
    receipt is not in a pending-close state.
    """
    projection = index.get("active", {}).get(receipt_id)
    if not isinstance(projection, dict):
        return None
    try:
        archived_meta_raw = _read_owned_file(
            root,
            f".saipen/archive/source/{receipt_id}.meta.json",
            kind="source archive metadata",
            max_bytes=_META_MAX,
        )
        archived_meta = json.loads(archived_meta_raw.decode("utf-8-sig"))
    except FileNotFoundError:
        return None
    except (ValueError, OSError) as exc:
        return {"ok": False, "code": "SOURCE_CORRUPTION", "detail": str(exc)}
    if not isinstance(archived_meta, dict):
        return {
            "ok": False,
            "code": "SOURCE_CORRUPTION",
            "detail": "archive metadata not an object",
        }
    try:
        _archive_closed_locked(root, receipt_id, archived_meta)
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "code": "ARCHIVE_COMMIT_PENDING",
            "receipt": receipt_id,
            "detail": str(exc),
        }
    expected_digest = projection.get("source_sha256")
    if archived_meta.get("source_sha256") != expected_digest:
        return {
            "ok": False,
            "code": "SOURCE_CORRUPTION",
            "detail": f"archived metadata digest {receipt_id} drift",
        }
    try:
        archived_body = _read_owned_file(
            root,
            f".saipen/archive/source/{receipt_id}.md",
            kind="source body",
            max_bytes=_BODY_MAX,
        )
    except (ValueError, OSError) as exc:
        return {"ok": False, "code": "SOURCE_CORRUPTION", "detail": str(exc)}
    if hashlib.sha256(archived_body).hexdigest() != expected_digest:
        return {
            "ok": False,
            "code": "SOURCE_CORRUPTION",
            "detail": f"archived body {receipt_id} digest mismatch",
        }
    try:
        archived_contract_raw = _read_owned_file(
            root,
            f".saipen/archive/source/{receipt_id}.contract.json",
            kind="source Work Contract",
            max_bytes=_LEDGER_MAX,
        )
        archived_contract = json.loads(archived_contract_raw.decode("utf-8-sig"))
    except (FileNotFoundError, OSError, ValueError):
        archived_contract = None
    if (
        not isinstance(archived_contract, dict)
        or archived_contract.get("source_sha256") != expected_digest
    ):
        return {
            "ok": False,
            "code": "CONTRACT_DRIFT",
            "receipt": receipt_id,
            "detail": "archived Contract digest drift",
        }
    try:
        archived_cov_raw = _read_owned_file(
            root,
            f".saipen/archive/source/{receipt_id}.coverage.json",
            kind="source coverage ledger",
            max_bytes=_LEDGER_MAX,
        )
        archived_cov = json.loads(archived_cov_raw.decode("utf-8-sig"))
    except (FileNotFoundError, OSError, ValueError):
        archived_cov = {"requirements": {}}
    requirements = archived_cov.get("requirements", {}) if isinstance(archived_cov, dict) else {}
    actionable = sum(
        bool(entry.get("actionable", entry.get("class") in ACTIONABLE_CLASSES))
        for entry in requirements.values()
    )
    tombstone = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "source_sha256": expected_digest,
        "linked_work": archived_meta.get("linked_work"),
        "status": CLOSED_STATUS,
        "closed_at": archived_meta.get("closed_at"),
        "closure_event": archived_meta.get("closure_event"),
        "archive_ref": f".saipen/archive/source/{receipt_id}.md",
        "requirements": len(requirements),
        "actionable": actionable,
        "unresolved": 0,
    }
    _write_tombstone(root, receipt_id, tombstone)
    index["active"].pop(receipt_id, None)
    index["tombstones"][receipt_id] = tombstone
    _write_index(root, index)
    return {
        "ok": True,
        "code": "SOURCE_CLOSED",
        "receipt": receipt_id,
        "status": CLOSED_STATUS,
        "archive_ref": tombstone["archive_ref"],
        "recovered": True,
    }


def _move_archive_artifact(
    root: Path,
    source: Path,
    destination: Path,
    *,
    label: str,
    required: bool,
) -> None:
    """Idempotently complete one owned active->archive move."""
    try:
        source_stat = prove_owned_regular(source, kind=f"active {label}")
    except FileNotFoundError:
        source_stat = None
    try:
        destination_stat = prove_owned_regular(destination, kind=f"archived {label}")
    except FileNotFoundError:
        destination_stat = None
    if source_stat is not None and destination_stat is not None:
        source_raw = read_bound_regular_bytes(source, source_stat, max_bytes=_BODY_MAX)
        destination_raw = read_bound_regular_bytes(
            destination, destination_stat, max_bytes=_BODY_MAX
        )
        if source_raw != destination_raw:
            raise ValueError(f"active and archived {label} disagree for {source.name}")
        safe_unlink_owned(source, kind=f"duplicate active {label}", ownership_root=root)
        return
    if source_stat is None:
        if destination_stat is not None or not required:
            return
        raise ValueError(f"both active and archived {label} are missing for {source.name}")
    prove_owned_dir_chain(destination.parent, kind=f"archive {label}", ownership_root=root)
    os.replace(source, destination)


def _archive_closed_locked(root: Path, receipt_id: str, meta: dict) -> dict:
    archive = _archive_dir(root)
    body = _safe_path(root, f".saipen/intake/active/{receipt_id}.md", expect_file=True)
    active_meta = _safe_path(
        root, f".saipen/intake/active/{receipt_id}.meta.json", expect_file=True
    )
    archive_body = _safe_path(root, f".saipen/archive/source/{receipt_id}.md", expect_file=True)
    archive_meta = _safe_path(
        root, f".saipen/archive/source/{receipt_id}.meta.json", expect_file=True
    )
    archive.mkdir(parents=True, exist_ok=True)
    meta = dict(meta)
    meta["storage_status"] = ARCHIVED_STATUS
    meta["archive_ref"] = f".saipen/archive/source/{receipt_id}.md"
    _atomic_write(archive_meta, _json_bytes(meta), ownership_root=root)
    _move_archive_artifact(root, body, archive_body, label="source body", required=True)
    safe_unlink_owned(active_meta, kind="active source metadata", ownership_root=root)
    for label, path in (
        ("coverage", _coverage_path(root, receipt_id)),
        ("contract", _contract_path(root, receipt_id)),
    ):
        destination = _safe_path(
            root,
            f".saipen/archive/source/{receipt_id}.{label}.json",
            expect_file=True,
        )
        _move_archive_artifact(root, path, destination, label=label, required=True)
    for revision in sorted(_contract_dir(root).glob(f"{receipt_id}.r*.json")):
        if revision.is_file() and not _is_link_or_reparse(revision):
            destination = _safe_path(
                root, f".saipen/archive/source/{revision.name}", expect_file=True
            )
            _move_archive_artifact(
                root, revision, destination, label="contract revision", required=False
            )
    return {
        "ok": True,
        "code": "SOURCE_ARCHIVED",
        "receipt": receipt_id,
        "archive_ref": meta["archive_ref"],
    }


def close_receipt(root: Path | str, receipt_id: str, *, closure_event: str | None = None) -> dict:
    """Close only with full terminal coverage; then leave the hot surface."""
    root = Path(root)
    if not _valid_receipt_id(receipt_id):
        return _invalid_receipt_id(receipt_id)
    try:
        with project_writer_lock(root):
            index = _read_index(root)
            if _is_archive_commit_pending(root, receipt_id, index):
                settled = _settle_archive_commit(root, receipt_id, index)
                if settled is not None:
                    return settled
            meta = _read_meta(root, receipt_id)
            if not meta:
                return {"ok": False, "code": "TICKET_NOT_FOUND", "detail": receipt_id}
            integrity = verify_integrity(root, receipt_id)
            if not integrity["ok"]:
                return integrity
            contract_gate = _contract_integrity(root, receipt_id, meta)
            if not contract_gate["ok"]:
                return contract_gate
            summary = coverage_summary(root, receipt_id)
            if not coverage_complete(root, receipt_id):
                return {
                    "ok": False,
                    "code": "SOURCE_UNRESOLVED",
                    "detail": f"unresolved: {summary['unresolved']}",
                    "coverage": summary,
                }
            if not _work_is_done(root, meta.get("linked_work")):
                return {
                    "ok": False,
                    "code": "SOURCE_WORK_ACTIVE",
                    "detail": f"linked Work {meta.get('linked_work')} is not DONE",
                }
            closed_at = _utc()
            meta["status"] = CLOSED_STATUS
            meta["closed_at"] = closed_at
            meta["reread_at"] = closed_at
            meta["closure_event"] = closure_event
            tombstone = {
                "schema_version": SCHEMA_VERSION,
                "receipt_id": receipt_id,
                "source_sha256": meta["source_sha256"],
                "linked_work": meta.get("linked_work"),
                "status": CLOSED_STATUS,
                "closed_at": closed_at,
                "closure_event": closure_event,
                "archive_ref": f".saipen/archive/source/{receipt_id}.md",
                "requirements": summary["requirements"],
                "actionable": summary["actionable"],
                "unresolved": 0,
            }
            archived = _archive_closed_locked(root, receipt_id, meta)
            index = _read_index(root)
            index["active"].pop(receipt_id, None)
            index["tombstones"][receipt_id] = tombstone
            _write_tombstone(root, receipt_id, tombstone)
            _write_index(root, index)
            return {
                "ok": True,
                "code": "SOURCE_CLOSED",
                "receipt": receipt_id,
                "closure_event": closure_event,
                "status": CLOSED_STATUS,
                "archive_ref": archived["archive_ref"],
            }
    except (OSError, PermissionError, ValueError) as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}


def archive_receipt(root: Path | str, receipt_id: str) -> dict:
    """Move a CLOSED receipt out of the active surface into cold storage."""
    root = Path(root)
    if not _valid_receipt_id(receipt_id):
        return _invalid_receipt_id(receipt_id)
    try:
        with project_writer_lock(root):
            index = _read_index(root)
            if _is_archive_commit_pending(root, receipt_id, index):
                settled = _settle_archive_commit(root, receipt_id, index)
                if settled is not None:
                    return settled
            meta = _read_meta(root, receipt_id)
            if not meta:
                tomb = _read_index(root).get("tombstones", {}).get(receipt_id)
                if tomb and (_archive_dir(root) / f"{receipt_id}.md").is_file():
                    return {
                        "ok": True,
                        "code": "ALREADY_SATISFIED",
                        "receipt": receipt_id,
                        "archive_ref": tomb.get("archive_ref"),
                    }
                return {"ok": False, "code": "TICKET_NOT_FOUND", "detail": receipt_id}
            if meta.get("status") != CLOSED_STATUS:
                return {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "detail": "only CLOSED receipts archive",
                }
            archived = _archive_closed_locked(root, receipt_id, meta)
            index = _read_index(root)
            index["active"].pop(receipt_id, None)
            tomb = index.get("tombstones", {}).get(receipt_id)
            if tomb is None:
                tomb = {
                    "schema_version": SCHEMA_VERSION,
                    "receipt_id": receipt_id,
                    "source_sha256": meta.get("source_sha256"),
                    "linked_work": meta.get("linked_work"),
                    "status": CLOSED_STATUS,
                    "closed_at": meta.get("closed_at"),
                    "closure_event": meta.get("closure_event"),
                    "archive_ref": f".saipen/archive/source/{receipt_id}.md",
                    "requirements": 0,
                    "actionable": 0,
                    "unresolved": 0,
                }
                index["tombstones"][receipt_id] = tomb
                _write_tombstone(root, receipt_id, tomb)
            _write_index(root, index)
            return {
                "ok": True,
                "code": "SOURCE_ARCHIVED",
                "receipt": receipt_id,
                "archive_ref": archived["archive_ref"],
            }
    except (OSError, PermissionError, ValueError) as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}


def purge_receipt(root: Path | str, receipt_id: str) -> dict:
    """Optional hard purge: keep the tombstone, remove the cold body."""
    root = Path(root)
    if not _valid_receipt_id(receipt_id):
        return _invalid_receipt_id(receipt_id)
    try:
        with project_writer_lock(root):
            index = _read_index(root)
            tomb = index.get("tombstones", {}).get(receipt_id)
            if not tomb:
                return {"ok": False, "code": "TICKET_NOT_FOUND", "detail": receipt_id}
            for suffix in (".md", ".meta.json", ".coverage.json", ".contract.json"):
                path = _safe_path(
                    root, f".saipen/archive/source/{receipt_id}{suffix}", expect_file=True
                )
                safe_unlink_owned(path, kind="purged source archive", ownership_root=root)
            for revision in _archive_dir(root).glob(f"{receipt_id}.r*.json"):
                if revision.is_file() and not _is_link_or_reparse(revision):
                    safe_unlink_owned(
                        revision,
                        kind="purged source contract revision",
                        ownership_root=root,
                    )
            tomb["purged"] = True
            tomb["purged_at"] = _utc()
            index["tombstones"][receipt_id] = tomb
            _write_tombstone(root, receipt_id, tomb)
            _write_index(root, index)
            return {"ok": True, "code": "SOURCE_PURGED", "receipt": receipt_id}
    except (OSError, PermissionError, ValueError) as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}


def read_body(root: Path | str, receipt_id: str) -> dict:
    """Forensic retrieval: active or archived body, explicitly requested."""
    root = Path(root)
    if not _valid_receipt_id(receipt_id):
        return _invalid_receipt_id(receipt_id)
    try:
        meta = _read_meta(root, receipt_id)
        location = "active"
        rel = f".saipen/intake/active/{receipt_id}.md"
        if not meta:
            # Tombstoned/archived: look in cold storage only on explicit request.
            archive_meta_rel = f".saipen/archive/source/{receipt_id}.meta.json"
            try:
                raw_meta = _read_owned_file(
                    root, archive_meta_rel, kind="source archive metadata", max_bytes=_META_MAX
                )
                meta = json.loads(raw_meta.decode("utf-8-sig"))
                location = "archive"
                rel = f".saipen/archive/source/{receipt_id}.md"
            except (FileNotFoundError, OSError, ValueError):
                meta = None
    except (ValueError, OSError) as exc:
        return {"ok": False, "code": "SOURCE_CORRUPTION", "detail": str(exc)}
    if not meta:
        tomb = _read_index(root).get("tombstones", {}).get(receipt_id)
        if tomb and tomb.get("purged"):
            return {
                "ok": False,
                "code": "SOURCE_PURGED",
                "detail": "body removed by purge; tombstone retains digest/closure",
            }
        return {"ok": False, "code": "TICKET_NOT_FOUND", "detail": receipt_id}
    try:
        raw = _read_owned_file(root, rel, kind="source body", max_bytes=_BODY_MAX)
        body = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "code": "INVALID", "detail": "source body is not UTF-8"}
    except FileNotFoundError:
        return {
            "ok": False,
            "code": "SOURCE_PURGED",
            "detail": "body removed by purge; tombstone retains digest/closure",
        }
    except (ValueError, OSError) as exc:
        return {"ok": False, "code": "SOURCE_CORRUPTION", "detail": str(exc)}
    actual = hashlib.sha256(raw).hexdigest()
    if actual != meta.get("source_sha256"):
        return {
            "ok": False,
            "code": "SOURCE_CORRUPTION",
            "recorded": meta.get("source_sha256"),
            "actual": actual,
        }
    return {"ok": True, "receipt": receipt_id, "location": location, "body": body, "meta": meta}


def status(root: Path | str, receipt_id: str) -> dict:
    root = Path(root)
    if not _valid_receipt_id(receipt_id):
        return _invalid_receipt_id(receipt_id)
    try:
        meta = _read_meta(root, receipt_id)
    except (ValueError, OSError) as exc:
        return {"ok": False, "code": "SOURCE_CORRUPTION", "detail": str(exc)}
    location = "active"
    if not meta:
        try:
            raw = _read_owned_file(
                root,
                f".saipen/archive/source/{receipt_id}.meta.json",
                kind="source archive metadata",
                max_bytes=_META_MAX,
            )
            meta = json.loads(raw.decode("utf-8-sig"))
            location = "archive"
        except (FileNotFoundError, OSError, ValueError):
            tomb = _read_index(root).get("tombstones", {}).get(receipt_id)
            if tomb:
                return {
                    "ok": True,
                    "receipt": receipt_id,
                    "status": tomb.get("status"),
                    "location": "purged" if tomb.get("purged") else "tombstone",
                    "source_sha256": tomb.get("source_sha256"),
                    "linked_work": tomb.get("linked_work"),
                    "closure_event": tomb.get("closure_event"),
                    "coverage": {
                        "requirements": tomb.get("requirements", 0),
                        "actionable": tomb.get("actionable", 0),
                        "terminal": tomb.get("actionable", 0),
                        "unresolved": [],
                    },
                }
            return {"ok": False, "code": "TICKET_NOT_FOUND", "detail": receipt_id}
    if location == "archive":
        try:
            raw = _read_owned_file(
                root,
                f".saipen/archive/source/{receipt_id}.coverage.json",
                kind="source archive coverage",
                max_bytes=_LEDGER_MAX,
            )
            archived_ledger = json.loads(raw.decode("utf-8-sig"))
        except (FileNotFoundError, OSError, ValueError):
            archived_ledger = {"requirements": {}}
        requirements = archived_ledger.get("requirements", {})
        summary = {
            "receipt": receipt_id,
            "requirements": len(requirements),
            "actionable": sum(
                bool(entry.get("actionable", entry.get("class") in ACTIONABLE_CLASSES))
                for entry in requirements.values()
            ),
            "terminal": sum(
                bool(entry.get("actionable", entry.get("class") in ACTIONABLE_CLASSES))
                and entry.get("disposition") in TERMINAL_DISPOSITIONS
                for entry in requirements.values()
            ),
            "unresolved": [],
        }
    else:
        summary = coverage_summary(root, receipt_id)
    return {
        "ok": True,
        "receipt": receipt_id,
        "status": meta.get("status"),
        "location": location,
        "source_kind": meta.get("source_kind"),
        "source_sha256": meta.get("source_sha256"),
        "linked_work": meta.get("linked_work"),
        "amends": meta.get("amends"),
        "closure_event": meta.get("closure_event"),
        "coverage": summary,
    }


def active_receipts(root: Path | str, *, work: str | None = None) -> list[dict]:
    """Cheap hot projection: index + metadata only; never opens source bodies."""
    root = Path(root)
    result = []
    for receipt_id in sorted(_read_index(root).get("active", {})):
        if not _valid_receipt_id(receipt_id):
            raise ValueError(f"invalid source receipt id: {receipt_id!r}")
        meta = _read_meta(root, receipt_id)
        if not meta or (work is not None and meta.get("linked_work") != work):
            continue
        summary = coverage_summary(root, receipt_id)
        result.append(
            {
                "receipt": receipt_id,
                "source_sha256": meta.get("source_sha256"),
                "linked_work": meta.get("linked_work"),
                "requirements": summary["requirements"],
                "terminal": summary["terminal"],
                "unresolved": len(summary["unresolved"]),
            }
        )
    return result


def recover_orphans(root: Path | str) -> dict:
    """Read-only crash diagnostic; never deletes or invents source intent."""
    root = Path(root)
    index = _read_index(root)
    indexed = set(index.get("active", {}))
    orphans = []
    for receipt_id in sorted(indexed):
        if not _valid_receipt_id(receipt_id):
            continue
        try:
            _read_owned_file(
                root,
                f".saipen/intake/active/{receipt_id}.md",
                kind="source body",
                max_bytes=_BODY_MAX,
            )
            active_body = True
        except FileNotFoundError:
            active_body = False
        except (ValueError, OSError):
            active_body = True
        try:
            _read_owned_file(
                root,
                f".saipen/archive/source/{receipt_id}.md",
                kind="source body",
                max_bytes=_BODY_MAX,
            )
            archived_body = True
        except FileNotFoundError:
            archived_body = False
        except (ValueError, OSError):
            archived_body = False
        if not active_body and archived_body:
            orphans.append(
                {
                    "receipt": receipt_id,
                    "state": "ARCHIVE_COMMIT_PENDING",
                    "source_sha256": index["active"][receipt_id].get("source_sha256"),
                }
            )
    active = _active_dir(root)
    if active.is_dir() and not _is_link_or_reparse(active):
        for body in sorted(active.glob("SRC-*.md")):
            receipt_id = body.stem
            if receipt_id not in indexed or not _read_meta(root, receipt_id):
                try:
                    raw = _read_owned_file(
                        root,
                        f".saipen/intake/active/{receipt_id}.md",
                        kind="source body",
                        max_bytes=_BODY_MAX,
                    )
                    digest = hashlib.sha256(raw).hexdigest()
                except (OSError, ValueError):
                    digest = None
                orphans.append(
                    {
                        "receipt": receipt_id,
                        "state": "ORPHAN_RECEIPT",
                        "source_sha256": digest,
                    }
                )
    return {"ok": True, "code": "ORPHAN_RECEIPTS", "orphans": orphans}


def validate_project(root: Path | str) -> list[str]:
    """Structural validation only; no LLM-level semantic interpretation."""
    root = Path(root)
    index_path = _index_path(root)
    try:
        board_links = _board_source_links(root)
    except (OSError, ValueError) as exc:
        return [f"source receipt BOARD projection unreadable: {exc}"]
    if not index_path.exists():
        return [
            f"BOARD Work {work} references missing source receipt {receipt_id}"
            for work, receipts in board_links.items()
            for receipt_id in sorted(receipts)
        ]
    errors: list[str] = []
    try:
        raw = _read_owned_file(
            root, ".saipen/intake/index.json", kind="source intake index", max_bytes=_INDEX_MAX
        )
        index = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(index, dict):
            raise ValueError("index root is not an object")
        if not isinstance(index.get("active"), dict) or not isinstance(
            index.get("tombstones"), dict
        ):
            raise ValueError("index active/tombstones are not objects")
    except (OSError, ValueError) as exc:
        return [f"source intake index unreadable: {exc}"]
    seen_digests: dict[str, str] = {}
    for receipt_id, projection in index.get("active", {}).items():
        if not INTENT_RE.fullmatch(receipt_id):
            errors.append(f"invalid source receipt id {receipt_id!r}")
            continue
        meta = _read_meta(root, receipt_id)
        if not meta:
            errors.append(f"active receipt {receipt_id} has no metadata")
            continue
        if meta.get("status") == CLOSED_STATUS:
            errors.append(f"closed receipt {receipt_id} remains in active surface")
        integrity = verify_integrity(root, receipt_id)
        if not integrity["ok"]:
            errors.append(f"active receipt {receipt_id}: {integrity['code']}")
        digest = meta.get("source_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"active receipt {receipt_id} has invalid source_sha256")
        elif digest in seen_digests:
            errors.append(
                f"exact duplicate active receipts {seen_digests[digest]} and {receipt_id}"
            )
        else:
            seen_digests[digest] = receipt_id
        if projection.get("source_sha256") != digest:
            errors.append(f"active receipt {receipt_id} index digest drift")
        contract = _read_contract(root, receipt_id)
        if not contract:
            errors.append(f"active receipt {receipt_id} has no Work Contract")
        elif contract.get("source_sha256") != digest:
            errors.append(f"active receipt {receipt_id} CONTRACT_DRIFT")
        else:
            contract_ids = set(contract.get("clauses", {}))
            coverage_ids = set(_read_coverage(root, receipt_id).get("requirements", {}))
            if contract_ids != coverage_ids:
                errors.append(
                    f"active receipt {receipt_id} contract/coverage clause drift: "
                    f"contract={len(contract_ids)} coverage={len(coverage_ids)}"
                )
            revision = int(contract.get("interpretation_revision", 0))
            if revision > 0:
                revision_path = _contract_dir(root) / f"{receipt_id}.r{revision:03d}.json"
                if not revision_path.is_file() or _is_link_or_reparse(revision_path):
                    errors.append(
                        f"active receipt {receipt_id} contract revision r{revision:03d} missing"
                    )
        linked = meta.get("linked_work")
        if linked:
            try:
                from .board import parse_board

                raw_board = _read_owned_file(
                    root,
                    ".saipen/BOARD.md",
                    kind="source BOARD authority",
                    max_bytes=_BOARD_MAX,
                )
                board = parse_board(raw_board.decode("utf-8-sig"))
                ticket = board.get("tickets", {}).get(linked)
            except (OSError, ValueError):
                ticket = None
            if ticket is None:
                errors.append(f"active receipt {receipt_id} references missing Work {linked}")
            else:
                projected = {
                    value.strip()
                    for value in str(ticket.get("fields", {}).get("source_receipts") or "").split(
                        ","
                    )
                    if value.strip()
                }
                if receipt_id not in projected:
                    errors.append(
                        f"active receipt {receipt_id} linkage missing from BOARD Work {linked}"
                    )
                if ticket.get("section") == "## DONE" and not coverage_complete(root, receipt_id):
                    errors.append(f"DONE Work {linked} has unresolved source receipt {receipt_id}")
        amends = meta.get("amends")
        if amends:
            if not _valid_receipt_id(amends):
                errors.append(f"active receipt {receipt_id} has invalid amends {amends!r}")
            elif amends not in index.get("active", {}) and amends not in index.get(
                "tombstones", {}
            ):
                errors.append(
                    f"active receipt {receipt_id} references missing amended receipt {amends}"
                )
    for receipt_id, tomb in index.get("tombstones", {}).items():
        if receipt_id in index.get("active", {}):
            errors.append(f"receipt {receipt_id} is both active and tombstoned")
        if tomb.get("status") != CLOSED_STATUS or tomb.get("unresolved") != 0:
            errors.append(f"tombstone {receipt_id} lacks verified closed coverage")
        expected_archive = f".saipen/archive/source/{receipt_id}.md"
        if tomb.get("archive_ref") != expected_archive:
            errors.append(f"tombstone {receipt_id} has invalid archive_ref")
        tomb_path = _tombstone_dir(root) / f"{receipt_id}.json"
        if not tomb_path.is_file() or _is_link_or_reparse(tomb_path):
            errors.append(f"tombstone {receipt_id} file missing or unsafe")
        if not tomb.get("purged") and not (_archive_dir(root) / f"{receipt_id}.md").is_file():
            errors.append(f"tombstone {receipt_id} archive body missing")
    known_receipts = set(index.get("active", {})) | set(index.get("tombstones", {}))
    for work, receipts in board_links.items():
        for receipt_id in sorted(receipts):
            if receipt_id not in known_receipts:
                errors.append(f"BOARD Work {work} references missing source receipt {receipt_id}")
    for orphan in recover_orphans(root)["orphans"]:
        errors.append(f"ORPHAN_RECEIPT {orphan['receipt']}")
    return errors

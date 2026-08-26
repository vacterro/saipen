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
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from .journal import _atomic_write, owned_target_path
from .lock import project_writer_lock

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


def capture_worthy(
    body: str, *, source_kind: str | None = None, explicit: bool = False
) -> dict:
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
    path = _index_path(root)
    if not path.exists():
        return {"active": {}, "tombstones": {}, "next_id": 1}
    if path.exists() and (_is_link_or_reparse(path) or not path.is_file()):
        raise ValueError(f"unsafe source intake index: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
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
    _atomic_write(path, _json_bytes(index))


def _read_meta(root: Path, receipt_id: str) -> dict | None:
    if not _valid_receipt_id(receipt_id):
        raise ValueError(f"invalid source receipt id: {receipt_id!r}")
    path = _active_dir(root) / f"{receipt_id}.meta.json"
    if not path.exists():
        return None
    if path.exists() and (_is_link_or_reparse(path) or not path.is_file()):
        raise ValueError(f"unsafe source receipt metadata: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"malformed source metadata {receipt_id}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"malformed source metadata {receipt_id}: root is not an object")
    return doc


def _write_meta(root: Path, receipt_id: str, meta: dict) -> None:
    path = _safe_path(root, f".saipen/intake/active/{receipt_id}.meta.json", expect_file=True)
    _atomic_write(path, _json_bytes(meta))


def _write_body(root: Path, receipt_id: str, body: str) -> None:
    path = _safe_path(root, f".saipen/intake/active/{receipt_id}.md", expect_file=True)
    if path.exists():
        raise ValueError(f"immutable source body already exists: {receipt_id}")
    _atomic_write(path, body.encode("utf-8"))


def _coverage_path(root: Path, receipt_id: str) -> Path:
    if not _valid_receipt_id(receipt_id):
        raise ValueError(f"invalid source receipt id: {receipt_id!r}")
    return _coverage_dir(root) / f"{receipt_id}.json"


def _read_coverage(root: Path, receipt_id: str) -> dict:
    path = _coverage_path(root, receipt_id)
    if not path.exists():
        return {"requirements": {}}
    if path.exists() and (_is_link_or_reparse(path) or not path.is_file()):
        raise ValueError(f"unsafe source coverage ledger: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"malformed source coverage {receipt_id}: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("requirements"), dict):
        raise ValueError(f"malformed source coverage {receipt_id}: requirements is not an object")
    return doc


def _write_coverage(root: Path, receipt_id: str, ledger: dict) -> None:
    path = _safe_path(root, f".saipen/intake/coverage/{receipt_id}.json", expect_file=True)
    _atomic_write(path, _json_bytes(ledger))


def _contract_path(root: Path, receipt_id: str) -> Path:
    if not _valid_receipt_id(receipt_id):
        raise ValueError(f"invalid source receipt id: {receipt_id!r}")
    return _contract_dir(root) / f"{receipt_id}.json"


def _read_contract(root: Path, receipt_id: str) -> dict | None:
    path = _contract_path(root, receipt_id)
    if not path.exists():
        return None
    if path.exists() and (_is_link_or_reparse(path) or not path.is_file()):
        raise ValueError(f"unsafe source Work Contract: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"malformed source Work Contract {receipt_id}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"malformed source Work Contract {receipt_id}: root is not an object")
    return value


def _write_contract(root: Path, receipt_id: str, contract: dict) -> None:
    path = _safe_path(root, f".saipen/intake/contracts/{receipt_id}.json", expect_file=True)
    _atomic_write(path, _json_bytes(contract))


def _write_contract_revision(root: Path, receipt_id: str, contract: dict) -> None:
    revision = int(contract.get("interpretation_revision", 0))
    path = _safe_path(
        root,
        f".saipen/intake/contracts/{receipt_id}.r{revision:03d}.json",
        expect_file=True,
    )
    if path.exists():
        raise ValueError(f"contract revision already exists: {receipt_id} r{revision}")
    _atomic_write(path, _json_bytes(contract))


def _write_tombstone(root: Path, receipt_id: str, tombstone: dict) -> None:
    path = _safe_path(root, f".saipen/intake/tombstones/{receipt_id}.json", expect_file=True)
    _atomic_write(path, _json_bytes(tombstone))


def _link_board_projection(root: Path, work: str, receipt_id: str) -> dict:
    """Compact BOARD link written only after source authority is durable."""
    from . import codec
    from .board import parse_board, set_ticket_field

    path = _safe_path(root, ".saipen/BOARD.md", expect_file=True)
    try:
        document = codec.read_document(path)
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
    _atomic_write(path, document.encode(updated))
    return {"ok": True, "code": "SOURCE_LINKED", "work": work}


def _board_source_links(root: Path) -> dict[str, set[str]]:
    """Return the reverse BOARD projection: Work -> durable receipt IDs."""
    from . import codec
    from .board import parse_board

    path = _safe_path(root, ".saipen/BOARD.md", expect_file=True)
    document = codec.read_document(path)
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
                if hashlib.sha256(body_path.read_bytes()).hexdigest() == digest:
                    return {"receipt_id": receipt_id, "orphan": True}
            except OSError:
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
                    if work and not linked_work:
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
            meta = {
                "receipt_id": receipt_id,
                "received_at": _utc(),
                "source_kind": source_kind,
                "source_sha256": digest,
                "status": ACTIVE_STATUS,
                "linked_work": work,
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
            actual = hashlib.sha256(
                (_active_dir(root) / f"{receipt_id}.md").read_bytes()
            ).hexdigest()
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
                "linked_work": work,
            }
            _write_index(root, index)
            linkage = (
                _link_board_projection(root, work, receipt_id) if work is not None else {"ok": True}
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
                "linked_work": work,
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
    body_path = _active_dir(root) / f"{receipt_id}.md"
    try:
        body = body_path.read_bytes()
    except OSError:
        return {"ok": False, "code": "INVALID", "detail": "receipt body missing"}
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

        board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig"))
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
    _atomic_write(archive_meta, _json_bytes(meta))
    os.replace(body, archive_body)
    with suppress(FileNotFoundError):
        active_meta.unlink()
    for label, path in (
        ("coverage", _coverage_path(root, receipt_id)),
        ("contract", _contract_path(root, receipt_id)),
    ):
        if path.is_file() and not _is_link_or_reparse(path):
            destination = _safe_path(
                root,
                f".saipen/archive/source/{receipt_id}.{label}.json",
                expect_file=True,
            )
            os.replace(path, destination)
    for revision in sorted(_contract_dir(root).glob(f"{receipt_id}.r*.json")):
        if revision.is_file() and not _is_link_or_reparse(revision):
            destination = _safe_path(
                root, f".saipen/archive/source/{revision.name}", expect_file=True
            )
            os.replace(revision, destination)
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
            _write_tombstone(root, receipt_id, tombstone)
            index = _read_index(root)
            index["active"].pop(receipt_id, None)
            index["tombstones"][receipt_id] = tombstone
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
            return _archive_closed_locked(root, receipt_id, meta)
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
                with suppress(FileNotFoundError):
                    path.unlink()
            for revision in _archive_dir(root).glob(f"{receipt_id}.r*.json"):
                if revision.is_file() and not _is_link_or_reparse(revision):
                    revision.unlink()
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
    meta = _read_meta(root, receipt_id)
    location = "active"
    body_path = _safe_path(
        root, f".saipen/intake/active/{receipt_id}.md", expect_file=True
    )
    if not meta:
        # Tombstoned/archived: look in cold storage only on explicit request.
        try:
            archive_meta = _safe_path(
                root,
                f".saipen/archive/source/{receipt_id}.meta.json",
                expect_file=True,
            )
            meta = json.loads(archive_meta.read_text(encoding="utf-8-sig"))
            location = "archive"
            body_path = _safe_path(
                root, f".saipen/archive/source/{receipt_id}.md", expect_file=True
            )
        except (OSError, ValueError):
            meta = None
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
        raw = body_path.read_bytes()
        body = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "code": "INVALID", "detail": "source body is not UTF-8"}
    except OSError:
        return {
            "ok": False,
            "code": "SOURCE_PURGED",
            "detail": "body removed by purge; tombstone retains digest/closure",
        }
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
    meta = _read_meta(root, receipt_id)
    location = "active"
    if not meta:
        try:
            archive_meta = _safe_path(
                root,
                f".saipen/archive/source/{receipt_id}.meta.json",
                expect_file=True,
            )
            meta = json.loads(archive_meta.read_text(encoding="utf-8-sig"))
            location = "archive"
        except (OSError, ValueError):
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
            archive_coverage = _safe_path(
                root,
                f".saipen/archive/source/{receipt_id}.coverage.json",
                expect_file=True,
            )
            archived_ledger = json.loads(archive_coverage.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
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
        active_body = _active_dir(root) / f"{receipt_id}.md"
        archived_body = _archive_dir(root) / f"{receipt_id}.md"
        if not active_body.is_file() and archived_body.is_file():
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
                    digest = hashlib.sha256(body.read_bytes()).hexdigest()
                except OSError:
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
    if _is_link_or_reparse(index_path) or not index_path.is_file():
        return [f"source intake index unsafe: {index_path}"]
    errors: list[str] = []
    try:
        index = json.loads(index_path.read_text(encoding="utf-8-sig"))
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

                board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig"))
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
                errors.append(
                    f"BOARD Work {work} references missing source receipt {receipt_id}"
                )
    for orphan in recover_orphans(root)["orphans"]:
        errors.append(f"ORPHAN_RECEIPT {orphan['receipt']}")
    return errors

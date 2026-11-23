"""Re-derive intake-index authority from carriers that are still on disk (T-2051).

The index lost the entries for receipts whose complete bundles still sit in
`.saipen/archive/source/`, so BOARD rows kept naming identities the index could
not resolve: `BOARD Work T-x references missing source receipt SRC-y`, a FAIL
with no verb behind it. Nothing had to be invented or purged -- the carriers
were never gone, only the index did not admit them.

This module classifies every unresolved reference against the carriers that
actually exist and derives a tombstone ONLY from a bundle the canonical reader
(`intake._closed_archive_bundle`) can prove end to end: identity, digests,
archive reference, contract/coverage agreement, revision chain, terminal
coverage. Anything it cannot prove is reported as `NO_EVIDENCE` with the exact
missing carrier, which is a terminal blocker rather than a guess.

Read-only. `operations.reconcile_source_index` is the journaled writer.
"""

from __future__ import annotations

import json
from pathlib import Path

ARCHIVE_REL = ".saipen/archive/source"
CARRIERS = ("meta.json", "contract.json", "coverage.json", "md")
RECOVERABLE = "RECOVERABLE"
RESUME_CARRIER = "RESUME_CARRIER"
REPAIR_DRIFT = "REPAIR_DRIFT"
NO_EVIDENCE = "NO_EVIDENCE"
#: States the journaled writer may act on. `RESUME_CARRIER` is the idempotent
#: half-state a crash between the projection write and the carrier write leaves
#: behind: the index already names a record whose carrier file is absent.
RECOVERABLE_STATES = (RECOVERABLE, RESUME_CARRIER, REPAIR_DRIFT)


def _carrier_rel(receipt_id: str) -> str:
    return f".saipen/intake/tombstones/{receipt_id}.json"


def _is_other_authority(projection: object) -> bool:
    """Retired and purged records are not closed-archive projections."""
    if not isinstance(projection, dict):
        return True
    if projection.get("purged"):
        return True
    from .retirement import is_retired_tombstone

    try:
        return bool(is_retired_tombstone(projection))
    except (OSError, ValueError):
        return True


def _pair_is_consistent(root: Path | str, receipt_id: str, projection: object) -> bool:
    """Is the index projection and its tombstone carrier the same record?

    Only a consistent pair is out of scope. A missing carrier or a carrier that
    disagrees is exactly the half-state this command exists to settle.
    """
    path = Path(root) / _carrier_rel(receipt_id)
    if not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) == projection
    except (OSError, ValueError):
        return False


def carrier_state(root: Path | str, receipt_id: str) -> dict[str, bool]:
    base = Path(root) / ARCHIVE_REL
    return {name: (base / f"{receipt_id}.{name}").exists() for name in CARRIERS}


def derived_tombstone(root: Path | str, receipt_id: str) -> dict:
    """Derive a closed-archive tombstone from the bytes already on disk.

    Raises `ValueError` carrying the precise reason the bundle cannot be
    proven. No field is defaulted, inferred from the BOARD, or copied from a
    neighbouring receipt: every value comes out of the canonical reader.
    """
    from . import intake

    meta_path = Path(root) / ARCHIVE_REL / f"{receipt_id}.meta.json"
    try:
        raw = meta_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise ValueError(
            f"no archived bundle carrier: {ARCHIVE_REL}/{receipt_id}.meta.json"
        ) from exc
    except OSError as exc:
        raise ValueError(f"archived bundle unreadable: {exc}") from exc
    try:
        meta = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"archived metadata is not valid JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError("archived metadata is not an object")
    projection = {
        "source_sha256": meta.get("source_sha256"),
        "linked_work": meta.get("linked_work"),
    }
    verified, contract, _coverage, summary = intake._closed_archive_bundle(
        root, receipt_id, projection
    )
    clauses = contract.get("clauses")
    if not isinstance(clauses, dict):
        raise ValueError(f"archived Contract {receipt_id} carries no clause map")
    tombstone = {
        "actionable": summary["actionable"],
        "archive_ref": verified.get("archive_ref"),
        "closed_at": verified.get("closed_at"),
        "closure_event": verified.get("closure_event"),
        "linked_work": verified.get("linked_work"),
        "receipt_id": receipt_id,
        "requirements": summary["requirements"],
        "schema_version": 1,
        "source_sha256": verified.get("source_sha256"),
        "status": "CLOSED",
        "unresolved": 0,
    }
    if len(clauses) != tombstone["requirements"]:
        raise ValueError(
            f"archived Contract {receipt_id} clause count disagrees with its coverage ledger"
        )
    # Close-time wrote the record twice: the tombstone carrier and its index
    # projection. Where the carrier survived and the projection did not, the
    # carrier is the older artifact and the one to restore -- but only after
    # every field this derivation actually proved agrees with it. Its extra
    # fields are close-time facts this reader does not rederive, so they are
    # carried, never invented.
    carrier_path = Path(root) / _carrier_rel(receipt_id)
    if carrier_path.is_file():
        try:
            carrier = json.loads(carrier_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"tombstone carrier unreadable: {exc}") from exc
        if not isinstance(carrier, dict):
            raise ValueError("tombstone carrier is not an object")
        mismatch = sorted(
            field
            for field, value in tombstone.items()
            if carrier.get(field) != value
        )
        if mismatch:
            raise ValueError(
                "tombstone carrier disagrees with its archived bundle on "
                + ", ".join(mismatch)
            )
        return carrier
    return tombstone


def plan(root: Path | str) -> dict:
    """Read-only: classify every unresolved BOARD -> receipt reference."""
    from . import intake

    root = Path(root)
    try:
        links = intake._board_source_links(root)
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"BOARD source projection unreadable: {exc}",
            "entries": [],
            "counts": {},
        }
    try:
        index = intake._read_index(root)
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"source intake index unreadable: {exc}",
            "entries": [],
            "counts": {},
        }
    active = set(index.get("active") or {})
    tombstones = index.get("tombstones") or {}
    references: dict[str, list[str]] = {}
    for work, receipts in links.items():
        for receipt_id in sorted(receipts):
            if receipt_id in active:
                continue
            if receipt_id in tombstones:
                # A retired or purged record is a different authority entirely:
                # it was never a closed-archive bundle, so this reader has
                # nothing to say about it and must not re-derive one.
                if _is_other_authority(tombstones[receipt_id]):
                    continue
                if _pair_is_consistent(root, receipt_id, tombstones[receipt_id]):
                    continue
            references.setdefault(receipt_id, []).append(work)
    entries: list[dict] = []
    for receipt_id in sorted(references):
        carriers = carrier_state(root, receipt_id)
        entry = {
            "receipt_id": receipt_id,
            "referenced_by": sorted(references[receipt_id]),
            "carriers": carriers,
            "present_carriers": sorted(name for name, ok in carriers.items() if ok),
            "carrier_present": (root / _carrier_rel(receipt_id)).exists(),
        }
        try:
            tombstone = derived_tombstone(root, receipt_id)
        except (OSError, ValueError) as exc:
            entry["state"] = NO_EVIDENCE
            entry["missing_proof"] = str(exc)
            entry["tombstone"] = None
        else:
            entry["missing_proof"] = None
            entry["tombstone"] = tombstone
            if receipt_id not in tombstones:
                entry["state"] = RECOVERABLE
            elif tombstones[receipt_id] == tombstone:
                entry["state"] = RESUME_CARRIER
            elif entry["carrier_present"]:
                entry["state"] = REPAIR_DRIFT
                entry["missing_proof"] = (
                    "the index projection disagrees with the tombstone carrier that close-time "
                    "wrote beside it; the carrier is restored"
                )
            else:
                entry["state"] = NO_EVIDENCE
                entry["missing_proof"] = (
                    "the index already records this receipt differently from its archived "
                    "bundle, so one of the two carries a real conflict"
                )
        entries.append(entry)
    recoverable = [entry for entry in entries if entry["state"] in RECOVERABLE_STATES]
    blocked = [entry for entry in entries if entry["state"] not in RECOVERABLE_STATES]
    return {
        "ok": True,
        "code": "SOURCE_INDEX_PLAN" if entries else "NOTHING_TO_RECONCILE",
        "detail": (
            f"{len(recoverable)} reference(s) can be re-registered from a proven archived "
            f"bundle; {len(blocked)} have no carrier on disk"
        ),
        "entries": entries,
        "recoverable": [entry["receipt_id"] for entry in recoverable],
        "no_evidence": [entry["receipt_id"] for entry in blocked],
        "counts": {
            "references": len(entries),
            RECOVERABLE: len(recoverable),
            NO_EVIDENCE: len(blocked),
        },
    }

"""Audit Inbox -- external transport adapter into Source Intake (T-1227).

`SOURCE-AUDIT-INBOX-01`. The canonical inbox is exactly `<project-root>/audit/`
and its canonical layers are DIRECT regular files matching `^[1-9][0-9]*\\.md$`.
Nothing else in that directory is an audit layer, nothing else is ever read,
captured or deleted, and the scan never recurses.

This module is TRANSPORT ONLY. It enumerates layers, snapshots one safely,
hashes it, classifies its generation against the existing Source Receipt
lifecycle, projects the next inbox action read-only, and plans the
hash-guarded journaled deletion of a layer whose receipt is proven CLOSED.
It owns NO semantic interpretation of audit prose (Source Contract/Coverage
own that), NO BOARD policy, and NO routing logic (the router asks; this
module answers structurally).

Generation identity is `relative_path + SHA-256 of the exact file bytes`.
NEVER mtime: extraction, copy, sync, checkout and restore all move mtime
without changing meaning, and a content-bound identity is the only one that
makes "never delete bytes the closure did not prove" decidable.

SOURCE BODY IS DATA: an audit containing `saipen ship` is text, never a
command invocation. Nothing here parses the body for semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import intake
from .journal import _atomic_write, hash_bytes, owned_target_path
from .paths import prove_owned_dir_chain, prove_owned_regular, read_bound_regular_bytes
from .plan import semantic_payload_hash

RULE_ID = "SOURCE-AUDIT-INBOX-01"
SCHEMA_VERSION = 1
AUDIT_DIRNAME = "audit"
LAYER_RE = re.compile(r"^[1-9][0-9]*\.md$")
BINDING_REL = ".saipen/intake/audit_inbox.json"
SOURCE_KIND = "external_audit"
MAX_LAYER_BYTES = intake._BODY_MAX

# Bounded generation vocabulary. The Source Receipt lifecycle stays
# authoritative; these names describe only the TRANSPORT state of one
# path+digest generation.
NEW = "NEW"
ACTIVE = "ACTIVE"
BLOCKED = "BLOCKED"
CLOSED_PENDING_DELETE = "CLOSED_PENDING_DELETE"
DELETED = "DELETED"
INVALID = "INVALID"
MISSING_AFTER_CAPTURE = "MISSING_AFTER_CAPTURE"

GENERATION_STATES = (
    NEW,
    ACTIVE,
    BLOCKED,
    CLOSED_PENDING_DELETE,
    DELETED,
    INVALID,
    MISSING_AFTER_CAPTURE,
)

# The narrow migration class the EOL-only equivalence binding may consider.
# A general source is never bound across a byte difference.
_MIGRATION_KINDS = ("external_audit", "user_audit", "implementation_mission")

_EXACT = "exact"
_LEGACY_EOL = "legacy_transport_equivalent"


# --------------------------------------------------------------------------
# scanning + safe snapshot
# --------------------------------------------------------------------------


def audit_dir(root: Path | str) -> Path:
    return Path(root) / AUDIT_DIRNAME


def layer_number(name: str) -> int | None:
    """The positive layer number of a canonical filename, else None."""
    if not LAYER_RE.fullmatch(name):
        return None
    return int(name[:-3])


def scan_layers(root: Path | str) -> list[dict]:
    """Canonical layers, lowest number first.

    Direct entries only -- `audit/done/1.md` is not a layer. Zero-padded
    (`01.md`), non-numeric (`notes.md`) and non-Markdown (`1.txt`) names are
    foreign files: ignored here and therefore never deleted by cleanup.
    An absent or unsafe `audit/` directory is a normal empty inbox.
    """
    root = Path(root)
    directory = audit_dir(root)
    try:
        prove_owned_dir_chain(directory, kind="audit inbox", ownership_root=root)
    except ValueError:
        return []
    if not directory.is_dir():
        return []
    layers: list[dict] = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    for entry in entries:
        number = layer_number(entry.name)
        if number is None:
            continue
        layers.append(
            {
                "layer": number,
                "rel": f"{AUDIT_DIRNAME}/{entry.name}",
                "name": entry.name,
            }
        )
    layers.sort(key=lambda item: item["layer"])
    return layers


def _invalid(reason: str, detail: str) -> dict:
    return {"ok": False, "code": "AUDIT_LAYER_INVALID", "reason": reason, "detail": detail}


def snapshot_layer(root: Path | str, rel: str) -> dict:
    """One bounded, witnessed read of an audit layer.

    Proves the final node is an owned regular file (a symlink/junction/reparse
    layer is refused wherever it points), bounds the read by the source-body
    limit, requires valid UTF-8 and hashes the EXACT witnessed bytes. Every
    refusal is a truthful diagnostic -- an invalid layer is never captured and
    never deleted.
    """
    root = Path(root)
    if layer_number(Path(rel).name) is None or Path(rel).parent.as_posix() != AUDIT_DIRNAME:
        return _invalid("noncanonical", f"{rel} is not a canonical audit layer")
    try:
        owned_target_path(root, rel, kind="audit layer")
    except Exception as exc:  # InvalidIdError and friends: refuse, never guess
        return _invalid("unsafe-path", str(exc))
    # Containment is proved above through the canonical resolver, but the READ
    # must use the LITERAL path: `owned_target_path` collapses symlinks, so a
    # layer that is a link to another file inside the project would resolve to
    # its target and be witnessed as a plain regular file. The no-follow lstat
    # below has to see the link itself in order to refuse it.
    path = root / Path(rel)
    try:
        witnessed = prove_owned_regular(path, kind="audit layer")
    except FileNotFoundError:
        return {"ok": False, "code": "AUDIT_LAYER_ABSENT", "reason": "absent", "detail": rel}
    except ValueError as exc:
        return _invalid("unsafe-node", str(exc))
    if witnessed.st_size > MAX_LAYER_BYTES:
        return _invalid(
            "oversize", f"{rel} is {witnessed.st_size} bytes, over the {MAX_LAYER_BYTES} limit"
        )
    try:
        raw = read_bound_regular_bytes(path, witnessed, max_bytes=MAX_LAYER_BYTES)
    except ValueError as exc:
        return _invalid("unstable-read", str(exc))
    except OSError as exc:
        return _invalid("unreadable", str(exc))
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return _invalid("not-utf8", str(exc))
    if not text:
        return _invalid("empty", f"{rel} is empty")
    return {
        "ok": True,
        "rel": rel,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "text": text,
    }


# --------------------------------------------------------------------------
# durable binding projection (NOT a source of Work truth)
# --------------------------------------------------------------------------


def read_binding(root: Path | str) -> dict:
    """The path+digest -> receipt binding. Rebuildable operational projection."""
    root = Path(root)
    path = root / Path(BINDING_REL)
    empty = {"schema_version": SCHEMA_VERSION, "layers": {}}
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return empty
    except OSError:
        return empty
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return empty
    if not isinstance(doc, dict) or not isinstance(doc.get("layers"), dict):
        return empty
    doc.setdefault("schema_version", SCHEMA_VERSION)
    return doc


def _binding_bytes(doc: dict) -> bytes:
    doc = dict(doc)
    doc["schema_version"] = SCHEMA_VERSION
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_binding(root: Path | str, doc: dict) -> None:
    root = Path(root)
    path = owned_target_path(root, BINDING_REL, kind="audit inbox binding")
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, _binding_bytes(doc), ownership_root=root)


def _binding_precondition(root: Path) -> str:
    path = root / Path(BINDING_REL)
    try:
        return hash_bytes(path.read_bytes())
    except OSError:
        return ""


# --------------------------------------------------------------------------
# receipt lookup
# --------------------------------------------------------------------------


def _index(root: Path) -> dict:
    try:
        return intake._read_index(root)
    except (OSError, ValueError):
        return {"active": {}, "tombstones": {}}


def receipt_for_digest(root: Path | str, digest: str) -> dict | None:
    """The existing receipt whose EXACT source digest is `digest`, if any.

    Index-only: no source body is opened. Source Intake deduplication stays
    the authority -- this is the cheap read-only projection of it.
    """
    index = _index(Path(root))
    for receipt_id, record in sorted((index.get("active") or {}).items()):
        if isinstance(record, dict) and record.get("source_sha256") == digest:
            return {"receipt_id": receipt_id, "status": intake.ACTIVE_STATUS, "record": record}
    for receipt_id, record in sorted((index.get("tombstones") or {}).items()):
        if isinstance(record, dict) and record.get("source_sha256") == digest:
            return {"receipt_id": receipt_id, "status": intake.CLOSED_STATUS, "record": record}
    return None


def _normalize_eol(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _eol_only_difference(left: str, right: str) -> bool:
    """True when two texts differ by CR/LF bytes ALONE.

    Deliberately narrow: equal after line-ending normalization AND identical
    once every CR/LF is removed. No whitespace trimming, no Markdown
    normalization, no case folding, no Unicode normalization, no similarity.
    """
    if left == right:
        return False
    if _normalize_eol(left) != _normalize_eol(right):
        return False
    strip = str.maketrans("", "", "\r\n")
    return left.translate(strip) == right.translate(strip)


def eol_equivalent_receipt(root: Path | str, text: str) -> dict | None:
    """The single active receipt an inbox layer may bind to across CR/LF only.

    Migration compatibility for audit material captured before the inbox
    existed. Returns None unless EXACTLY ONE eligible active receipt of a
    migration source class differs from `text` by line endings alone --
    ambiguity refuses rather than guesses, and the receipt digest is never
    rewritten.
    """
    root = Path(root)
    index = _index(root)
    matches: list[dict] = []
    for receipt_id in sorted(index.get("active") or {}):
        try:
            meta = intake._read_meta(root, receipt_id)
        except (OSError, ValueError):
            continue
        if not meta or meta.get("source_kind") not in _MIGRATION_KINDS:
            continue
        if meta.get("status") != intake.ACTIVE_STATUS:
            continue
        body = intake.read_body(root, receipt_id)
        if not body.get("ok"):
            continue
        candidate = body.get("body")
        if not isinstance(candidate, str):
            continue
        if _eol_only_difference(text, candidate):
            matches.append(
                {
                    "receipt_id": receipt_id,
                    "receipt_sha256": meta.get("source_sha256"),
                    "linked_work": meta.get("linked_work"),
                }
            )
    if len(matches) != 1:
        return None
    return matches[0]


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------


def classify(root: Path | str) -> dict:
    """Read-only generation classification of the whole inbox.

    Writes nothing and opens no source body: an ACTIVE/CLOSED verdict comes
    from the intake index + receipt metadata, never from re-reading receipts.
    """
    root = Path(root)
    binding = read_binding(root)
    bound = binding.get("layers") or {}
    layers: list[dict] = []
    seen: set[str] = set()
    for entry in scan_layers(root):
        rel = entry["rel"]
        seen.add(rel)
        record = bound.get(rel) if isinstance(bound.get(rel), dict) else None
        snap = snapshot_layer(root, rel)
        if not snap.get("ok"):
            if snap.get("code") == "AUDIT_LAYER_ABSENT":
                # Raced away between scan and read: not a layer this pass.
                continue
            layers.append(
                {
                    "layer": entry["layer"],
                    "rel": rel,
                    "state": INVALID,
                    "reason": snap.get("reason"),
                    "detail": snap.get("detail"),
                    "receipt_id": (record or {}).get("receipt_id"),
                }
            )
            continue
        digest = snap["sha256"]
        generation = 1
        receipt_id = None
        binding_kind = None
        if record and record.get("file_sha256") == digest:
            receipt_id = record.get("receipt_id")
            binding_kind = record.get("binding")
            generation = int(record.get("generation") or 1)
        elif record:
            # Same path, different bytes: a NEW generation, whatever the old
            # one settled to. Never reuse the previous receipt binding.
            generation = int(record.get("generation") or 1) + 1
        item = {
            "layer": entry["layer"],
            "rel": rel,
            "sha256": digest,
            "size_bytes": snap["size_bytes"],
            "generation": generation,
            "binding": binding_kind,
            "receipt_id": receipt_id,
            "linked_work": None,
            "state": NEW,
        }
        if receipt_id is None:
            found = receipt_for_digest(root, digest)
            if found:
                receipt_id = found["receipt_id"]
                item["receipt_id"] = receipt_id
                item["binding"] = _EXACT
        if receipt_id is None:
            layers.append(item)
            continue
        status = intake.status(root, receipt_id)
        if not status.get("ok"):
            item["state"] = NEW
            item["receipt_id"] = None
            item["detail"] = status.get("detail", "bound receipt unreadable")
            layers.append(item)
            continue
        item["linked_work"] = status.get("linked_work")
        item["coverage"] = status.get("coverage")
        receipt_status = status.get("status")
        if receipt_status == intake.CLOSED_STATUS:
            item["state"] = CLOSED_PENDING_DELETE
        elif receipt_status == intake.ACTIVE_STATUS:
            item["state"] = ACTIVE
        else:
            item["state"] = BLOCKED
            item["detail"] = f"bound receipt is {receipt_status}"
        layers.append(item)

    # Bindings whose transport file is gone. The Source Receipt is already
    # durable authority: a vanished ACTIVE transport is a DIAGNOSTIC, never a
    # reason to lose Work; a vanished closed one is settled cleanup.
    orphans: list[dict] = []
    for rel, record in sorted(bound.items()):
        if rel in seen or not isinstance(record, dict):
            continue
        state = record.get("state")
        orphans.append(
            {
                "rel": rel,
                "layer": record.get("layer"),
                "receipt_id": record.get("receipt_id"),
                "linked_work": record.get("linked_work"),
                "sha256": record.get("file_sha256"),
                "state": (
                    DELETED
                    if state in (DELETED, CLOSED_PENDING_DELETE)
                    else MISSING_AFTER_CAPTURE
                ),
            }
        )
    return {"layers": layers, "orphans": orphans}


# --------------------------------------------------------------------------
# read-only routing projection
# --------------------------------------------------------------------------


def projection(root: Path | str) -> dict | None:
    """What the Audit Inbox would own at the routing stage. Writes nothing.

    Returns None when the inbox holds nothing at all. Ordering is: settle a
    proven-closed layer first, then the lowest-numbered WORKABLE layer. A
    BLOCKED/INVALID lower layer is retained and reported but never starves a
    later workable one.
    """
    state = classify(root)
    layers = state["layers"]
    if not layers and not state["orphans"]:
        return None
    invalid = [item for item in layers if item["state"] in (INVALID, BLOCKED)]
    base = {
        "rule_id": RULE_ID,
        "pending": [item["layer"] for item in layers if item["state"] in (NEW, ACTIVE)],
        "closed_pending_delete": [
            item["layer"] for item in layers if item["state"] == CLOSED_PENDING_DELETE
        ],
        "invalid": [
            {"layer": item["layer"], "reason": item.get("reason") or item.get("detail")}
            for item in invalid
        ],
    }
    for item in layers:
        if item["state"] == CLOSED_PENDING_DELETE:
            return {
                **base,
                "action": "saipen audit ingest",
                "layer": item["layer"],
                "path": item["rel"],
                "receipt": item["receipt_id"],
                "work": item.get("linked_work"),
                "detail": (
                    f"{item['rel']} source {item['receipt_id']} is CLOSED and unchanged; "
                    "settle the journaled cleanup"
                ),
            }
    for item in layers:
        if item["state"] != ACTIVE:
            continue
        work = item.get("linked_work")
        if not work:
            return {
                **base,
                "action": "saipen audit ingest",
                "layer": item["layer"],
                "path": item["rel"],
                "receipt": item["receipt_id"],
                "detail": f"{item['rel']} is captured as {item['receipt_id']} but carries no Work",
            }
        return {
            **base,
            "action": f"PHASE SCOUT {work}",
            "layer": item["layer"],
            "path": item["rel"],
            "receipt": item["receipt_id"],
            "work": work,
            "detail": f"{item['rel']} owns continuation through {work}",
        }
    for item in layers:
        if item["state"] == NEW:
            return {
                **base,
                "action": "saipen audit ingest",
                "layer": item["layer"],
                "path": item["rel"],
                "detail": f"{item['rel']} is an unconsumed audit generation",
            }
    if invalid:
        return {
            **base,
            "action": "saipen audit status",
            "invalid_only": True,
            "detail": "audit inbox holds only invalid layer(s); it is not idle",
        }
    return None


def status(root: Path | str) -> dict:
    """Compact operator projection. Never dumps audit body text."""
    state = classify(root)
    routed = projection(root)
    layers = state["layers"]
    return {
        "ok": True,
        "code": "AUDIT_INBOX_STATUS",
        "rule_id": RULE_ID,
        "directory": AUDIT_DIRNAME,
        "pending": [
            {
                "layer": item["layer"],
                "path": item["rel"],
                "state": item["state"],
                "receipt": item.get("receipt_id"),
                "work": item.get("linked_work"),
                "sha256": item.get("sha256"),
            }
            for item in layers
        ],
        "closed_pending_delete": [
            item["layer"] for item in layers if item["state"] == CLOSED_PENDING_DELETE
        ],
        "invalid": [
            {"layer": item["layer"], "reason": item.get("reason") or item.get("detail")}
            for item in layers
            if item["state"] in (INVALID, BLOCKED)
        ],
        "orphans": state["orphans"],
        "next": routed,
        "last_allocated_id": _last_allocated_id(root),
    }


def _last_allocated_id(root: Path | str) -> int | None:
    """The highest layer number the shared enqueue allocator has handed out."""
    try:
        from .audit_enqueue import read_allocator

        next_id = read_allocator(root)["next_id"]
    except Exception:
        return None
    return next_id - 1 if next_id > 1 else None


def provenance_trace(root: Path | str, layer: int | None = None) -> dict:
    """Read-only audit -> receipt -> Work -> disposition trace (T-1232).

    Built from the durable binding plus the Source index, so it SURVIVES the
    consumed file: a layer whose bytes were journaled away still answers who
    produced it, which finding id they used, which receipt carried it, which
    Work closed it and how. Never opens an audit body, never exposes anything
    about the project beyond those links.
    """
    root = Path(root)
    index = _index(root)
    rows: list[dict] = []
    for rel, record in sorted((read_binding(root).get("layers") or {}).items()):
        if not isinstance(record, dict):
            continue
        if layer is not None and record.get("layer") != layer:
            continue
        receipt_id = record.get("receipt_id")
        entry = (index.get("active") or {}).get(receipt_id)
        tomb = (index.get("tombstones") or {}).get(receipt_id)
        source = entry if isinstance(entry, dict) else tomb if isinstance(tomb, dict) else {}
        provenance = record.get("provenance") or {}
        rows.append(
            {
                "layer": record.get("layer"),
                "path": rel,
                "sha256": record.get("file_sha256"),
                "transport_state": record.get("state"),
                "receipt": receipt_id,
                "receipt_status": source.get("status"),
                "work": record.get("linked_work") or source.get("linked_work"),
                "closure_event": source.get("closure_event"),
                "producer": (provenance.get("claims") or {}).get("producer"),
                "producer_item_id": (provenance.get("claims") or {}).get("producer_item_id"),
                "producer_claims_trusted": False,
                "maintainer_verdict": provenance.get("maintainer_verdict"),
            }
        )
    return {
        "ok": True,
        "code": "AUDIT_PROVENANCE_TRACE",
        "rule_id": RULE_ID,
        "rows": rows,
    }


# --------------------------------------------------------------------------
# capture (transport -> Source Intake)
# --------------------------------------------------------------------------


def _utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bind_layer(
    root: Path | str,
    rel: str,
    *,
    layer: int,
    generation: int,
    file_sha256: str,
    size_bytes: int,
    receipt_id: str,
    receipt_sha256: str,
    binding: str,
    linked_work: str | None,
    state: str,
    provenance: dict | None = None,
) -> dict:
    """Persist one generation binding. Never a second source of Work truth.

    T-1232: the binding record is where producer provenance lives, and it is
    kept for the layer's whole life -- including after the file is consumed and
    deleted, when the record's `state` becomes DELETED but its identity, digest,
    receipt, Work and producer claims stay readable. Deleting the bytes must
    not delete the answer to "who reported this and what came of it".
    """
    root = Path(root)
    doc = read_binding(root)
    layers = doc.setdefault("layers", {})
    previous = layers.get(rel) if isinstance(layers.get(rel), dict) else {}
    record = {
        "layer": layer,
        "generation": generation,
        "file_sha256": file_sha256,
        "receipt_sha256": receipt_sha256,
        "binding": binding,
        "size_bytes": size_bytes,
        "receipt_id": receipt_id,
        "linked_work": linked_work,
        "state": state,
        "captured_at": previous.get("captured_at") or _utc(),
        "closed_at": previous.get("closed_at"),
    }
    # Provenance is written ONCE, at capture, and never revised by a later
    # binding update: a producer that could rewrite its own claims after the
    # fact would make the trace worthless.
    carried = previous.get("provenance") or provenance
    if carried:
        record["provenance"] = carried
    layers[rel] = record
    write_binding(root, doc)
    return record


def reconcile_bootstrap(root: Path | str) -> list[dict]:
    """Bind pre-inbox audit layers to the Work they ALREADY own.

    The three layers in this repository were converted into canonical Work by
    hand before the automatic consumer existed. Activating the inbox must not
    see them as new external work and manufacture duplicate receipts or
    duplicate tickets. Every layer whose exact digest already resolves to a
    receipt gets its durable binding written here -- a reconciliation of
    existing truth, never a capture. Returns the bindings it wrote.
    """
    root = Path(root)
    bound = read_binding(root).get("layers") or {}
    written: list[dict] = []
    for item in classify(root)["layers"]:
        rel = item["rel"]
        if isinstance(bound.get(rel), dict) or not item.get("receipt_id"):
            continue
        state = item["state"] if item["state"] in GENERATION_STATES else NEW
        record = bind_layer(
            root,
            rel,
            layer=item["layer"],
            generation=item["generation"],
            file_sha256=item["sha256"],
            size_bytes=item["size_bytes"],
            receipt_id=item["receipt_id"],
            receipt_sha256=item["sha256"],
            binding=item.get("binding") or _EXACT,
            linked_work=item.get("linked_work"),
            state=state,
        )
        written.append({"rel": rel, **record})
    return written


def capture_layer(root: Path | str, rel: str, *, work: str | None = None) -> dict:
    """Capture one canonical layer through the EXISTING Source Intake.

    Exact-digest dedupe is Source Intake's; the EOL-only migration binding is
    tried only when no exact receipt exists, and it records BOTH digests
    without ever rewriting the receipt's own.
    """
    root = Path(root)
    snap = snapshot_layer(root, rel)
    if not snap.get("ok"):
        return snap
    digest = snap["sha256"]
    exact = receipt_for_digest(root, digest)
    if exact and exact["status"] == intake.CLOSED_STATUS:
        return {
            "ok": True,
            "code": "SOURCE_DUPLICATE_CLOSED",
            "receipt": exact["receipt_id"],
            "source_sha256": digest,
            "file_sha256": digest,
            "binding": _EXACT,
            "snapshot": snap,
        }
    if not exact:
        legacy = eol_equivalent_receipt(root, snap["text"])
        if legacy:
            return {
                "ok": True,
                "code": "SOURCE_LEGACY_TRANSPORT_EQUIVALENT",
                "receipt": legacy["receipt_id"],
                "source_sha256": legacy["receipt_sha256"],
                "file_sha256": digest,
                "linked_work": legacy.get("linked_work"),
                "binding": _LEGACY_EOL,
                "snapshot": snap,
            }
    captured = intake.capture(root, snap["text"], source_kind=SOURCE_KIND, work=work)
    if not captured.get("ok"):
        return captured
    captured["file_sha256"] = digest
    captured["binding"] = _EXACT
    captured["snapshot"] = snap
    captured["provenance"] = layer_provenance(snap["text"])
    return captured


def layer_provenance(text: str) -> dict | None:
    """Producer CLAIMS carried by an optional envelope, or None (T-1231).

    Reading is pure: the envelope is inside the bytes the digest already
    covers, so this cannot move a generation identity. A malformed envelope
    yields a record that says so instead of blocking capture -- a producer's
    metadata bug must never make a real finding undeliverable.
    """
    from . import audit_envelope

    parsed = audit_envelope.parse(text)
    if not parsed["present"]:
        return None
    record = {
        "envelope": "malformed" if not parsed["ok"] else "valid",
        # Every value below is what the PRODUCER asserts. No routing,
        # ordering, priority or deletion decision may read them.
        "claims": parsed["fields"],
        "maintainer_verdict": parsed["maintainer_verdict"],
    }
    if not parsed["ok"]:
        record["reason"] = parsed.get("reason")
    return record


# --------------------------------------------------------------------------
# hash-guarded journaled deletion
# --------------------------------------------------------------------------


def delete_gate(root: Path | str, rel: str) -> dict:
    """Prove a layer may be deleted. Every failure keeps the file.

    The gate is: canonical layer -> bound receipt -> receipt CLOSED with a
    tombstone -> linked Work terminal -> current bytes STILL equal the
    captured generation.
    """
    root = Path(root)
    binding = read_binding(root)
    record = (binding.get("layers") or {}).get(rel)
    snap = snapshot_layer(root, rel)
    if not isinstance(record, dict):
        # No durable binding yet: a pre-inbox layer whose EXACT digest already
        # resolves to a receipt is still bound truth, not an unknown file.
        # Derive the binding from that identity rather than refusing (the
        # migration case) -- an unresolvable layer still refuses.
        derived = (
            receipt_for_digest(root, snap["sha256"]) if snap.get("ok") else None
        )
        if not derived:
            return {
                "ok": False,
                "code": "AUDIT_NOT_BOUND",
                "detail": f"{rel} has no inbox binding",
            }
        number = layer_number(Path(rel).name)
        record = {
            "layer": number,
            "generation": 1,
            "file_sha256": snap["sha256"],
            "receipt_sha256": snap["sha256"],
            "binding": _EXACT,
            "size_bytes": snap["size_bytes"],
            "receipt_id": derived["receipt_id"],
            "linked_work": (derived.get("record") or {}).get("linked_work"),
            "state": CLOSED_PENDING_DELETE,
            "captured_at": None,
            "closed_at": None,
        }
    receipt_id = record.get("receipt_id")
    if not receipt_id:
        return {"ok": False, "code": "AUDIT_NOT_BOUND", "detail": f"{rel} binds no receipt"}
    if snap.get("code") == "AUDIT_LAYER_ABSENT":
        # Idempotent cleanup: the transport is already gone.
        return {
            "ok": True,
            "code": "AUDIT_ALREADY_ABSENT",
            "receipt": receipt_id,
            "rel": rel,
            "record": record,
        }
    if not snap.get("ok"):
        return snap
    if snap["sha256"] != record.get("file_sha256"):
        return {
            "ok": False,
            "code": "AUDIT_GENERATION_CHANGED",
            "detail": (
                f"{rel} now digests {snap['sha256'][:12]} but the closed generation was "
                f"{str(record.get('file_sha256'))[:12]}; the current bytes are a NEW "
                "generation and are never deleted as cleanup for the old one"
            ),
            "receipt": receipt_id,
            "current_sha256": snap["sha256"],
            "captured_sha256": record.get("file_sha256"),
        }
    status_out = intake.status(root, receipt_id)
    if not status_out.get("ok"):
        return {"ok": False, "code": "SOURCE_CORRUPTION", "detail": status_out.get("detail", "")}
    if status_out.get("status") != intake.CLOSED_STATUS:
        return {
            "ok": False,
            "code": "SOURCE_UNRESOLVED",
            "detail": f"{receipt_id} is {status_out.get('status')}, not CLOSED",
            "receipt": receipt_id,
        }
    linked_work = status_out.get("linked_work") or record.get("linked_work")
    if linked_work and not intake._work_is_done(root, linked_work):
        return {
            "ok": False,
            "code": "SOURCE_UNRESOLVED",
            "detail": f"linked Work {linked_work} is not DONE",
            "receipt": receipt_id,
        }
    return {
        "ok": True,
        "code": "AUDIT_DELETE_READY",
        "receipt": receipt_id,
        "rel": rel,
        "record": record,
        "sha256": snap["sha256"],
        "linked_work": linked_work,
        "coverage": status_out.get("coverage"),
        "snapshot": snap,
    }


def _closure_message(gate: dict) -> str:
    coverage = gate.get("coverage") or {}
    actionable = coverage.get("actionable", 0)
    terminal = coverage.get("terminal", 0)
    return (
        f"AUDIT_INBOX_CLOSED {gate['rel']} sha256={str(gate.get('sha256') or '')[:16]} "
        f"{gate['receipt']} {gate.get('linked_work') or '-'} "
        f"coverage={terminal}/{actionable}"
    )


def consume_layer(root: Path | str, rel: str, agent: str, *, dry_run: bool = False) -> dict:
    """Delete exactly one proven-closed layer through the canonical journal.

    The delete is an irreversible filesystem effect, so it goes through
    `run_mutation` with `operation="audit_inbox.consume"`: the prepared record
    carries the canonical path, the expected digest, the receipt, the linked
    Work and the binding transition BEFORE the first destructive byte. Crash
    before delete replays; crash after delete before COMMITTED settles
    idempotently; changed bytes on recovery CONFLICT instead of deleting.
    """
    from . import operations
    from .journal import run_mutation
    from .paths import project_identity as _project_identity

    root = Path(root)
    gate = delete_gate(root, rel)
    if not gate.get("ok"):
        return gate
    record = dict(gate["record"])
    already_absent = gate.get("code") == "AUDIT_ALREADY_ABSENT"
    if already_absent and record.get("state") == DELETED:
        # Already settled. Repeating cleanup must be a silent success, not a
        # second journaled operation writing another LOG line for a file that
        # was consumed once.
        return {
            "ok": True,
            "code": "AUDIT_CONSUMED",
            "layer": record.get("layer"),
            "path": rel,
            "receipt": gate["receipt"],
            "work": gate.get("linked_work"),
            "sha256": record.get("file_sha256"),
            "already_absent": True,
            "settled": True,
        }
    record["state"] = DELETED
    record["closed_at"] = record.get("closed_at") or _utc()
    binding_doc = read_binding(root)
    binding_doc.setdefault("layers", {})[rel] = record
    binding_bytes = _binding_bytes(binding_doc)

    docs, state, _board, log_tail = operations._read(root)
    op_id = "audit-consume-" + hash_bytes(
        f"{rel}:{record.get('file_sha256')}".encode("utf-8")
    )[:16]
    now, utc = operations._now(), operations._utc_iso()
    event, line = operations._event_line(
        docs,
        log_tail,
        "RUN",
        gate.get("linked_work"),
        agent,
        operations._fold_handover(state, agent, _closure_message(gate)),
        now,
        op_id,
    )
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_state = operations.patch_state(
        docs["state"].text_norm, {"last_event": event, "updated": utc, "agent": agent}
    )
    errors = operations.validate_texts(
        new_state,
        docs["board"].text_norm,
        new_log,
        current_agent=agent,
        sealed_events=docs["_history"],
    )
    if errors:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": "audit consume fails fast validation: " + "; ".join(errors[:5]),
        }

    targets: list[dict] = []
    preconditions: dict[str, str] = {}
    if not already_absent:
        targets.append(
            {
                "path": rel,
                "role": "generic",
                "action": "delete_file",
                "content": b"",
                "before_hash": hash_bytes((root / Path(rel)).read_bytes()),
                "after_hash": "",
            }
        )
        preconditions[rel] = targets[0]["before_hash"]
    binding_before = _binding_precondition(root)
    targets.append(
        {
            "path": BINDING_REL,
            "role": "generic",
            "action": "write",
            "content": binding_bytes,
            "before_hash": binding_before,
            "after_hash": hash_bytes(binding_bytes),
        }
    )
    preconditions[BINDING_REL] = binding_before
    for key, role, text in (
        ("log", "log", new_log),
        ("state", "state", new_state),
    ):
        doc = docs[key]
        content = doc.encode(text)
        targets.append(
            {
                "path": f".saipen/{key.upper()}.md",
                "role": role,
                "action": "write",
                "content": content,
                "before_hash": doc.raw_hash,
                "after_hash": hash_bytes(content),
            }
        )
        preconditions[f".saipen/{key.upper()}.md"] = doc.raw_hash

    expected = {
        "ok": True,
        "code": "AUDIT_CONSUMED",
        "layer": record.get("layer"),
        "path": rel,
        "receipt": gate["receipt"],
        "work": gate.get("linked_work"),
        "sha256": record.get("file_sha256"),
        "event_id": f"E-{event}",
        "op_id": op_id,
        "already_absent": already_absent,
    }
    if dry_run:
        return {
            **expected,
            "code": "AUDIT_CONSUME_PLAN",
            "dry_run": True,
            "targets": [t["path"] for t in targets],
        }
    from . import fast_check
    from .lock import project_writer_lock

    with project_writer_lock(root):
        committed = run_mutation(
            root,
            op_id,
            "audit_inbox.consume",
            agent,
            _project_identity(root),
            semantic_payload_hash(
                {
                    "operation": "audit_inbox.consume",
                    "path": rel,
                    "file_sha256": record.get("file_sha256"),
                    "receipt": gate["receipt"],
                    "work": gate.get("linked_work"),
                }
            ),
            targets,
            preconditions=preconditions,
            verify=fast_check.validate_project,
            verification_policy="core_fast",
        )
    if not committed.get("ok"):
        return {
            "ok": False,
            "code": committed.get("code", "VALIDATION_FAILED"),
            "op_id": op_id,
            "detail": committed.get("detail", "audit consume commit failed"),
            "recovery_required": bool(committed.get("recovery_required")),
        }
    return expected

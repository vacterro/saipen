"""Shared audit enqueue producer API -- SOURCE-AUDIT-ENQUEUE-01 (T-1230).

ONE constrained writer for every producer (a human script, AUDAPACK, a future
SAIPAL) that wants to put an audit in front of SAIPEN. The producer supplies
BYTES and an operation id; it never supplies a path, never names a layer
number, and can touch nothing else in the project.

Why an allocator file rather than "lowest free number": a deleted layer's
number must never come back. `audit/3.md` consumed and journaled away is a
DIFFERENT thing from a new audit that happens to land on 3, and every
provenance record downstream (receipt, tombstone, LOG line) keys on that
number plus a digest. First-free-gap allocation makes those records ambiguous
the first time an audit is consumed.

Durability shape is reserve-then-place, in that order:

  1. under the writer lock: read allocator, reconcile against the directory,
     persist ``{op -> {layer, state: RESERVED}}`` AND the advanced ``next_id``;
  2. still under the lock: write a temp file beside the target, fsync it,
     refuse if the target exists, ``os.replace`` it into place;
  3. persist ``state: COMMITTED`` with the digest.

A crash between 1 and 2 burns one id and leaves no file -- the retry with the
same ``producer_operation_id`` finds its RESERVED record and finishes the SAME
id. A crash between 2 and 3 leaves a complete canonical layer whose record
still says RESERVED -- the retry sees the file, verifies the digest, and
promotes the record. Neither path allocates twice, and no consumer ever sees
partial bytes because the temp file is not a canonical layer name.

TRANSPORT ONLY, exactly like `audit_inbox`: nothing here parses the audit
body, derives Work, writes BOARD/STATE/LOG, or trusts one producer claim.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

from . import audit_inbox
from .journal import _atomic_write, owned_target_path
from .lock import FileLockBusy, FileWriterLock
from .paths import prove_owned_dir_chain
from .safeid import InvalidIdError, validate_safe_id

RULE_ID = "SOURCE-AUDIT-ENQUEUE-01"
SCHEMA_VERSION = 1
ALLOCATOR_REL = ".saipen/intake/audit_allocator.json"
LOCK_REL = ".saipen/locks/audit-allocator.lock"

RESERVED = "RESERVED"
COMMITTED = "COMMITTED"

# A producer name is a path-safe id AND a lowercase-ish stable token: the name
# ends up in provenance records that a human reads, so `SAIPAL` and `saipal`
# being two producers would be a bug, not a feature.
_PRODUCER_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

_TEMP_PREFIX = ".enqueue-"

# The OS file lock is the CROSS-PROCESS writer. Inside one process the lock
# module deliberately refuses a second holder outright rather than queueing,
# so two threads of one producer would see WRITER_BUSY on a perfectly legal
# pair of enqueues. This guard makes same-process callers queue instead, and
# it is taken BEFORE the file lock so the two orders can never invert.
_PROCESS_GUARD = threading.Lock()

# T-1244: the wait is bounded. The guard used to be taken before an OS lock
# acquired with `blocking=True`, which waits forever -- so a foreign process
# holding the allocator lock parked the holding thread inside the OS call
# while it owned the guard, and every other same-process producer queued
# behind it with no diagnostic and no bound. Waiting is still correct
# (two simultaneous producers must get N and N+1, not a refusal a correct
# producer has to retry), so the fix is a deadline rather than a non-blocking
# acquire: one deadline covers the guard and the file lock together, and
# exhausting it returns the WRITER_BUSY this API already speaks.
LOCK_TIMEOUT_ENV = "SAIPEN_AUDIT_ENQUEUE_LOCK_TIMEOUT"
DEFAULT_LOCK_TIMEOUT = 30.0
_LOCK_RETRY_SLEEP = 0.02


class _AllocatorBusy(Exception):
    """The allocator lock stayed held for the whole bounded wait."""


def lock_timeout() -> float:
    """Seconds to wait for the allocator before reporting WRITER_BUSY.

    Overridable through the environment so a test can prove the refusal
    without sitting through the production wait. A non-numeric or
    non-positive value is the default, never an unbounded wait.
    """
    raw = os.environ.get(LOCK_TIMEOUT_ENV)
    if raw is None:
        return DEFAULT_LOCK_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT
    return value if value > 0 else DEFAULT_LOCK_TIMEOUT


@contextlib.contextmanager
def _allocator_lock(root: Path, timeout: float):
    """Hold the allocator across allocation and placement, or refuse in time.

    The guard is never held across an unbounded wait: it is taken with the
    same deadline the file lock gets, and both halves report which one ran out
    so a stuck enqueue names its cause instead of hanging.
    """
    deadline = time.monotonic() + timeout
    if not _PROCESS_GUARD.acquire(timeout=timeout):
        raise _AllocatorBusy(
            f"another thread in this process held the audit allocator guard "
            f"for the full {timeout:g}s wait"
        )
    try:
        while True:
            candidate = FileWriterLock(root / Path(LOCK_REL), root, blocking=False)
            try:
                candidate.acquire()
            except FileLockBusy:
                if time.monotonic() >= deadline:
                    raise _AllocatorBusy(
                        f"another process held {LOCK_REL} for the full {timeout:g}s wait"
                    ) from None
                time.sleep(_LOCK_RETRY_SLEEP)
                continue
            lock = candidate
            break
        try:
            yield lock
        finally:
            lock.release()
    finally:
        _PROCESS_GUARD.release()


def layer_digest(body: bytes) -> str:
    """The generation digest of an audit layer.

    Full SHA-256, deliberately not `journal.hash_bytes` (which truncates to 16
    hex for CAS tokens): this value has to equal what `audit_inbox` computes
    for the same file, or the consumer would treat every API-created layer as
    a different generation than the one the producer was told about.
    """
    return hashlib.sha256(body).hexdigest()


def _fail(code: str, detail: str) -> dict:
    return {"ok": False, "code": code, "detail": detail}


def allocator_path(root: Path | str) -> Path:
    return owned_target_path(Path(root), ALLOCATOR_REL, kind="audit allocator")


def read_allocator(root: Path | str) -> dict:
    """The allocator document. Absent/corrupt reads as empty, never as an error.

    The allocator is an operational projection, not canonical truth: the
    canonical facts are the files in `audit/` and the Source receipts. A
    corrupt allocator therefore must not wedge enqueue -- `_reconcile` rebuilds
    the floor from the directory, so the worst a lost allocator costs is the
    idempotency memory of in-flight operations.
    """
    empty = {"schema_version": SCHEMA_VERSION, "next_id": 1, "operations": {}}
    try:
        raw = (Path(root) / Path(ALLOCATOR_REL)).read_bytes()
    except OSError:
        return empty
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return empty
    if not isinstance(doc, dict):
        return empty
    if not isinstance(doc.get("operations"), dict):
        return empty
    next_id = doc.get("next_id")
    if not isinstance(next_id, int) or isinstance(next_id, bool) or next_id < 1:
        return empty
    doc["schema_version"] = SCHEMA_VERSION
    return doc


def write_allocator(root: Path | str, doc: dict) -> None:
    root = Path(root)
    path = allocator_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(doc)
    payload["schema_version"] = SCHEMA_VERSION
    _atomic_write(
        path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        ownership_root=root,
    )


def _op_key(producer: str, operation_id: str) -> str:
    return f"{producer} {operation_id}"


def _reconcile(root: Path, doc: dict) -> dict:
    """Raise the allocator floor above every number this project has ever used.

    Three sources, and all three matter:

    * files on disk -- a manual `audit/99.md` drop is legitimate transport, so
      the allocator steps over it rather than planning to overwrite it;
    * this allocator's own operation records;
    * the AUDIT INBOX BINDING -- the durable record of layers that were
      captured and then consumed. Those files are gone from the directory, so a
      disk scan alone would happily hand number 3 back out, and every
      provenance record that keys on `audit/3.md` would then name two different
      audits. A consumed number is spent forever; that is the entire reason
      this allocator exists rather than a first-free-gap search.
    """
    highest = 0
    for item in audit_inbox.scan_layers(root):
        highest = max(highest, item["layer"])
    for record in doc["operations"].values():
        layer = record.get("layer")
        if isinstance(layer, int) and not isinstance(layer, bool):
            highest = max(highest, layer)
    for record in (audit_inbox.read_binding(root).get("layers") or {}).values():
        if not isinstance(record, dict):
            continue
        layer = record.get("layer")
        if isinstance(layer, int) and not isinstance(layer, bool):
            highest = max(highest, layer)
    if doc["next_id"] <= highest:
        doc["next_id"] = highest + 1
    return doc


def _validate_inputs(producer, operation_id, item_id, body):
    if not isinstance(producer, str) or not _PRODUCER_RE.match(producer):
        return _fail(
            "VALIDATION_FAILED",
            f"producer {producer!r} is not a stable lowercase token ([a-z][a-z0-9_-]{{0,31}})",
        )
    for name, value in (("producer_operation_id", operation_id), ("producer_item_id", item_id)):
        if value is None and name == "producer_item_id":
            continue
        try:
            validate_safe_id(value, kind=name)
        except InvalidIdError as exc:
            return _fail("INVALID_ID", str(exc))
    if isinstance(body, str):
        body = body.encode("utf-8")
    if not isinstance(body, (bytes, bytearray)):
        return _fail("VALIDATION_FAILED", "audit body must be bytes or str")
    body = bytes(body)
    if not body.strip():
        return _fail("VALIDATION_FAILED", "audit body is empty")
    if len(body) > audit_inbox.MAX_LAYER_BYTES:
        return _fail(
            "VALIDATION_FAILED",
            f"audit body is {len(body)} bytes; the layer bound is "
            f"{audit_inbox.MAX_LAYER_BYTES}",
        )
    return body


def _result(root: Path, record: dict, *, idempotent: bool) -> dict:
    rel = f"{audit_inbox.AUDIT_DIRNAME}/{record['layer']}.md"
    present = (Path(root) / Path(rel)).is_file()
    return {
        "ok": True,
        "code": "AUDIT_ENQUEUED",
        "rule_id": RULE_ID,
        "layer": record["layer"],
        "rel": rel,
        "sha256": record.get("sha256"),
        "producer": record.get("producer"),
        "producer_operation_id": record.get("producer_operation_id"),
        "producer_item_id": record.get("producer_item_id"),
        "created_at": record.get("created_at"),
        "idempotent": idempotent,
        "present": present,
    }


def _place(root: Path, layer: int, body: bytes) -> dict | None:
    """Write `audit/<layer>.md` atomically. Returns a failure dict or None."""
    directory = audit_inbox.audit_dir(root)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        prove_owned_dir_chain(directory, kind="audit inbox", ownership_root=root)
    except (OSError, ValueError) as exc:
        return _fail("PATH_ESCAPE", f"audit inbox is not an owned directory: {exc}")
    try:
        target = owned_target_path(root, f"{audit_inbox.AUDIT_DIRNAME}/{layer}.md", kind="layer")
    except InvalidIdError as exc:
        return _fail("PATH_ESCAPE", str(exc))
    if target.exists():
        return _fail(
            "CONFLICT",
            f"{target.name} already exists; enqueue never overwrites a layer",
        )
    temp = directory / f"{_TEMP_PREFIX}{layer}.tmp"
    try:
        # O_BINARY matters: on Windows `os.open` without it opens in TEXT
        # mode and rewrites every newline into CRLF, so the layer on disk
        # would not be the bytes the producer handed us and its SHA-256
        # would not be the one this call returned.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
        handle = os.open(temp, flags, 0o600)
        try:
            os.write(handle, body)
            os.fsync(handle)
        finally:
            os.close(handle)
        os.replace(temp, target)
    except OSError as exc:
        with contextlib.suppress(OSError):
            temp.unlink()
        return _fail("VALIDATION_FAILED", f"could not place audit layer {layer}: {exc}")
    return None


def enqueue(
    root: Path | str,
    *,
    producer: str,
    body: bytes | str,
    producer_operation_id: str,
    producer_item_id: str | None = None,
) -> dict:
    """Place one producer audit as the next canonical layer. Idempotent per op."""
    root = Path(root)
    checked = _validate_inputs(producer, producer_operation_id, producer_item_id, body)
    if isinstance(checked, dict):
        return checked
    body = checked
    digest = layer_digest(body)
    key = _op_key(producer, producer_operation_id)

    try:
        # BLOCKING: two producers enqueueing at the same moment must both
        # succeed with N and N+1. A non-blocking refusal would make a correct
        # producer retry a correct call, which is the failure this API exists
        # to remove. The lock covers allocation and placement only -- never
        # analysis, never Source processing.
        with _allocator_lock(root, lock_timeout()):
            doc = _reconcile(root, read_allocator(root))
            record = doc["operations"].get(key)

            if isinstance(record, dict) and isinstance(record.get("layer"), int):
                # RETRY. The op already owns a number; finish that number or
                # report it. A retry with DIFFERENT bytes is a producer bug,
                # not a second audit -- refuse rather than silently keeping
                # whichever call happened to win.
                if record.get("sha256") not in (None, digest):
                    return _fail(
                        "CONFLICT",
                        f"producer_operation_id {producer_operation_id!r} already enqueued "
                        f"{record['sha256']}; a retry cannot change the audit body",
                    )
                target = root / audit_inbox.AUDIT_DIRNAME / f"{record['layer']}.md"
                if target.is_file():
                    if record.get("state") != COMMITTED:
                        record.update(state=COMMITTED, sha256=digest)
                        write_allocator(root, doc)
                    return _result(root, record, idempotent=True)
                if record.get("state") == COMMITTED:
                    # The layer was consumed by the journaled cleanup. That is
                    # a completed enqueue, not a missing one: report the
                    # original allocation and place nothing.
                    return _result(root, record, idempotent=True)
                failure = _place(root, record["layer"], body)
                if failure is not None:
                    return failure
                record.update(state=COMMITTED, sha256=digest)
                write_allocator(root, doc)
                return _result(root, record, idempotent=True)

            layer = doc["next_id"]
            record = {
                "layer": layer,
                "producer": producer,
                "producer_operation_id": producer_operation_id,
                "producer_item_id": producer_item_id,
                "created_at": audit_inbox._utc(),
                "sha256": digest,
                "state": RESERVED,
            }
            doc["operations"][key] = record
            doc["next_id"] = layer + 1
            write_allocator(root, doc)

            failure = _place(root, layer, body)
            if failure is not None:
                # A REFUSAL is not a crash. Drop the reservation so the
                # operation is not poisoned forever by transient external
                # state, but leave `next_id` advanced -- the id is spent
                # either way, and reuse is the one thing this allocator
                # exists to prevent.
                doc["operations"].pop(key, None)
                write_allocator(root, doc)
                return failure
            record["state"] = COMMITTED
            write_allocator(root, doc)
            return _result(root, record, idempotent=False)
    except _AllocatorBusy as exc:
        return _fail("WRITER_BUSY", str(exc))
    except FileLockBusy as exc:
        return _fail("WRITER_BUSY", f"another audit enqueue holds the allocator lock: {exc}")
    except (OSError, ValueError) as exc:
        return _fail("VALIDATION_FAILED", f"audit enqueue failed: {exc}")


def status(root: Path | str) -> dict:
    """Read-only allocator projection. No audit body text, ever."""
    doc = read_allocator(root)
    operations = doc["operations"]
    return {
        "ok": True,
        "code": "AUDIT_ALLOCATOR_STATUS",
        "rule_id": RULE_ID,
        "next_id": doc["next_id"],
        "last_allocated_id": doc["next_id"] - 1 if doc["next_id"] > 1 else None,
        "operations": len(operations),
        "reserved": sum(1 for r in operations.values() if r.get("state") == RESERVED),
    }

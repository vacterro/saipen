"""Typed SAIPAL backend adapter for SAIPEN autonomous campaign (Block 4 & Block 5).

Logical interface:
- probe()
- discover()
- start_or_resume()
- checkpoint()
- collect_findings()
- collect_publication_receipts()
- get_dispositions()
- classify_retry()
- get_next_eligibility()

Result classifications:
- ANALYSIS_PROGRESS
- NEW_QUALIFIED_FINDINGS
- NO_NEW_EVIDENCE
- STAGED_PUBLICATION
- DELIVERED_PUBLICATION
- SOURCE_NOT_ENROLLED
- RUNTIME_UNAVAILABLE
- AUTHORITY_REQUIRED
- ANALYSIS_BLOCKED
- RETRYABLE_FAILURE
- PERMANENT_FAILURE
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path

from . import audit_enqueue, lock, paths, saipal_report_stream
from .process_tree import ProcessTree

# Result classifications
ANALYSIS_PROGRESS = "ANALYSIS_PROGRESS"
NEW_QUALIFIED_FINDINGS = "NEW_QUALIFIED_FINDINGS"
NO_NEW_EVIDENCE = "NO_NEW_EVIDENCE"
STAGED_PUBLICATION = "STAGED_PUBLICATION"
DELIVERED_PUBLICATION = "DELIVERED_PUBLICATION"
SOURCE_NOT_ENROLLED = "SOURCE_NOT_ENROLLED"
RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"
ANALYSIS_BLOCKED = "ANALYSIS_BLOCKED"
RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
PERMANENT_FAILURE = "PERMANENT_FAILURE"
BACKEND_PROTOCOL_ERROR = "BACKEND_PROTOCOL_ERROR"
BACKEND_RESOURCE_LIMIT = "BACKEND_RESOURCE_LIMIT"
BACKEND_TIMEOUT_SECONDS = 30.0
MAX_BACKEND_STDOUT_BYTES = 4 * 1024 * 1024
MAX_BACKEND_STDERR_BYTES = 256 * 1024
MAX_HISTORY_RECORD_BYTES = 4 * 1024 * 1024

# PERF-004: the report transport is bounded but not limited to one in-memory
# document. A report larger than MAX_BACKEND_STDOUT_BYTES is still a VALID
# report -- refusing it outright made "large valid report" indistinguishable
# from a broken one. Report reads therefore get a larger spool ceiling and are
# parsed incrementally: only one top-level value is held at a time, and the
# findings array is consumed element by element.
REPORT_SPOOL_LIMIT_BYTES = 64 * 1024 * 1024
MAX_REPORT_VALUE_BYTES = 4 * 1024 * 1024
REPORT_STREAM_CHUNK_CHARS = 64 * 1024
REPORT_PAGE_DEFAULT = 250
REPORT_PAGE_MAX = 5000

# PERF-005: acknowledgment batches live in an append-only journal instead of a
# re-serialised id set in the cursor, and compaction only happens once the file
# has grown past this floor so a normal walk pays one small append per batch.
ACK_JOURNAL_NAME = "saipal_ack_journal.jsonl"
ACK_JOURNAL_COMPACT_BYTES = 64 * 1024

# Two correct producers appending at once must both be RECORDED, not have one
# refused: HISTORY_BUSY is the answer for a log that stayed locked for the whole
# bounded wait, not for ordinary contention. The audit allocator learned this
# first (T-1244); the history writer needs the same bounded retry or a burst of
# concurrent receipt writes loses legitimate records.
HISTORY_LOCK_TIMEOUT_ENV = "SAIPEN_SAIPAL_HISTORY_LOCK_TIMEOUT"
DEFAULT_HISTORY_LOCK_TIMEOUT = 30.0
_HISTORY_LOCK_RETRY_SLEEP = 0.02


def _history_lock_timeout() -> float:
    raw = os.environ.get(HISTORY_LOCK_TIMEOUT_ENV)
    if raw is None:
        return DEFAULT_HISTORY_LOCK_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_HISTORY_LOCK_TIMEOUT
    return value if value > 0 else DEFAULT_HISTORY_LOCK_TIMEOUT


@contextlib.contextmanager
def _history_write_lock(root: Path):
    path = Path(root) / ".saipen" / "locks" / "saipal-history.lock"
    deadline = time.monotonic() + _history_lock_timeout()
    while True:
        candidate = lock.FileWriterLock(path, root, blocking=False)
        try:
            candidate.acquire()
        except lock.FileLockBusy:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_HISTORY_LOCK_RETRY_SLEEP)
            continue
        try:
            yield candidate
        finally:
            with suppress(Exception):
                candidate.release()
        return


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def _load_json(raw):
    return json.loads(raw, object_pairs_hook=_json_object, parse_constant=_reject_constant)


def _backend_capture(cmd: list[str], *, stdout_limit: int = MAX_BACKEND_STDOUT_BYTES) -> dict:
    """Spool output outside Python memory; parse only complete bounded responses.

    ``stdout_limit`` lets the report transport declare its own, larger spool
    ceiling: PERF-004 distinguishes "too large to accept" from "large but
    valid", and only the caller knows which limit applies.

    The stdout spool is TRANSFERRED to the caller on success, not closed here:
    a report consumer reads it as a stream so peak memory stays at one finding
    instead of one response. Every failure path closes it.
    """
    stdout = tempfile.TemporaryFile()  # noqa: SIM115 -- ownership transfers to caller
    stderr = tempfile.TemporaryFile()  # noqa: SIM115 -- ownership transfers to caller
    keep_stdout = False
    try:
        with ProcessTree() as tree:
            process = tree.start(cmd, stdout=stdout, stderr=stderr)
            deadline = time.monotonic() + BACKEND_TIMEOUT_SECONDS
            timed_out = False
            while True:
                sizes = (os.fstat(stdout.fileno()).st_size, os.fstat(stderr.fileno()).st_size)
                if sizes[0] > stdout_limit or sizes[1] > MAX_BACKEND_STDERR_BYTES:
                    return _output_limit(sizes)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    process.wait(timeout=min(0.05, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
            # Reap descendants too, before reading the final immutable capture.
        if timed_out:
            return {
                "ok": False,
                "status": RETRYABLE_FAILURE,
                "transport_status": "TIMEOUT",
                "protocol_status": "UNOBSERVED",
                "operation_status": "UNKNOWN",
                "outcome_unknown": True,
                "error": "SAIPAL command deadline reached",
            }
        sizes = (os.fstat(stdout.fileno()).st_size, os.fstat(stderr.fileno()).st_size)
        if sizes[0] > stdout_limit or sizes[1] > MAX_BACKEND_STDERR_BYTES:
            return _output_limit(sizes)
        stdout.seek(0)
        stderr.seek(0)
        stderr_bytes = stderr.read(sizes[1])
        keep_stdout = True
        return {
            "ok": True,
            "returncode": process.returncode,
            "stdout_file": stdout,
            "stdout_bytes_len": sizes[0],
            "stderr": stderr_bytes,
        }
    finally:
        with suppress(Exception):
            stderr.close()
        if not keep_stdout:
            with suppress(Exception):
                stdout.close()


def _output_limit(sizes: tuple[int, int]) -> dict:
    return {
        "ok": False,
        "status": BACKEND_RESOURCE_LIMIT,
        "transport_status": "RESOURCE_LIMIT",
        "protocol_status": "UNOBSERVED",
        "operation_status": "UNKNOWN",
        "outcome_unknown": True,
        "stdout_bytes": sizes[0],
        "stderr_bytes": sizes[1],
        "error": "Backend output exceeds the declared transport limit; no partial report accepted",
    }



def _report_row_error(row: object) -> str | None:
    """The per-finding half of the report schema, in one place.

    PERF-004 validates findings while streaming them, so the row rules cannot
    live only in the materialised validator: two copies would drift and one
    path would accept what the other refuses.
    """
    if not isinstance(row, dict):
        return "Backend report requires object findings and an object counts field"
    if (
        not isinstance(row.get("finding_id"), str)
        or not row["finding_id"].strip()
        or not isinstance(row.get("state"), str)
        or not row["state"].strip()
    ):
        return "Backend report has invalid finding identities or counters"
    return None


def _finding_content_digest(row: dict) -> str:
    """The identity of one finding's CONTENT, excluding its name.

    W2-006: an id is a name, not a description. Rewriting `audit_body` under an
    unchanged id must change the corpus identity, or a cursor can treat a
    materially different report as the same one.
    """
    return hashlib.sha256(
        json.dumps(
            {k: v for k, v in row.items() if k != "finding_id"},
            sort_keys=True,
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class _CorpusIdentity:
    """A canonical, order-independent digest of a report corpus in O(1) memory.

    W2-006 requires the identity to cover finding CONTENT, not just ids. The
    obvious implementation -- collect ``[id, content_digest]`` pairs and sort
    them -- retains one entry per finding, which is exactly the residency
    PERF-004 has to remove: measured at 2000/20000 findings it grew 1.16 MB ->
    10.2 MB, i.e. the corpus was still resident, just as metadata.

    An accumulator gives the same guarantees without the list. Each finding
    contributes a 256-bit value to a commutative sum, so the result is
    independent of order (the sorted form ignored order too), and it changes
    when a id, content, state or evidence field changes. The count is folded in
    separately, so adding or removing a finding cannot be hidden by a
    compensating change elsewhere.
    """

    __slots__ = ("_sum", "count")

    MODULUS = 1 << 256

    def __init__(self) -> None:
        self.count = 0
        self._sum = 0

    def add(self, row: dict) -> None:
        material = json.dumps(
            [str(row.get("finding_id") or ""), _finding_content_digest(row)],
            sort_keys=True,
        ).encode("utf-8")
        self._sum = (
            self._sum + int.from_bytes(hashlib.sha256(material).digest(), "big")
        ) % self.MODULUS
        self.count += 1

    def digest(self) -> str:
        body = f"{self.count}:{self._sum:064x}".encode("ascii")
        return hashlib.sha256(body).hexdigest()


def _stream_report_validation(reader) -> tuple[dict, _CorpusIdentity, int]:
    """Phase A of PERF-004: validate a whole report without keeping it.

    Returns ``(envelope, corpus_identity, count)``. The identity is an O(1)
    accumulator, so the resident set after this call is the transport spool and
    a handful of integers -- never one object per finding. Any schema defect
    raises ``ValueError`` here, before a single finding can be published.
    """
    corpus = _CorpusIdentity()

    def sink(row) -> None:
        error = _report_row_error(row)
        if error:
            raise ValueError(error)
        corpus.add(row)

    envelope, count = saipal_report_stream.parse_report(reader, sink)
    if count != corpus.count:
        raise ValueError("Backend report finding count disagrees with its payload")
    return envelope, corpus, count


def _report_identity(envelope: dict, corpus: _CorpusIdentity, transport_bytes) -> dict:
    """The stable identity of one report corpus, shared by every page."""
    corpus_digest = corpus.digest()
    digest = hashlib.sha256(
        json.dumps(envelope, sort_keys=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "source_digest": f"{digest}:{corpus_digest}",
        "envelope_digest": digest,
        "corpus_digest": corpus_digest,
        "transport_bytes": transport_bytes,
        "total_findings": corpus.count,
    }


class _ValidatedReport:
    """One fully validated report whose only durable copy is its spool.

    PERF-004: the findings of a validated report must not live in the adapter.
    Phase A (`_open_report`) reads the captured spool once, validates every row
    and the envelope, and keeps only identity metadata. Phase B re-reads the
    SAME verified bytes in pages, so the resident set is one finding plus one
    page instead of the whole corpus. The spool -- which the transport already
    bounds at ``REPORT_SPOOL_LIMIT_BYTES`` -- is the paged copy; nothing is
    re-fetched from the backend and no second copy is written to disk.
    """

    def __init__(self, spool, envelope: dict, corpus: "_CorpusIdentity", identity: dict,
                 transport_bytes: int | None) -> None:
        self._spool = spool
        self.envelope = envelope
        self._corpus = corpus
        self.identity = identity
        self.transport_bytes = transport_bytes
        self._consumed = False

    @property
    def total_findings(self) -> int:
        return self._corpus.count

    def _reader(self):
        self._spool.seek(0)
        return io.TextIOWrapper(self._spool, encoding="utf-8", newline="")

    def iter_pages(self, page_size: int):
        """Yield successive finding pages, one corpus pass, bounded residency.

        The spool is released when the walk finishes, raises, or the consumer
        abandons the generator, so a cancelled pagination leaves no descriptor
        behind.
        """
        if self._consumed:
            raise RuntimeError("a validated report is paged exactly once")
        self._consumed = True
        try:
            reader = self._reader()
            try:
                stream = saipal_report_stream.iter_report_findings(reader)
                page: list = []
                try:
                    for row in stream:
                        error = _report_row_error(row)
                        if error:
                            raise ValueError(error)
                        page.append(row)
                        if len(page) >= page_size:
                            yield page
                            page = []
                    if page:
                        yield page
                finally:
                    stream.close()
            finally:
                with suppress(Exception):
                    reader.detach()
        finally:
            self.close()

    def read_all(self) -> dict:
        """Materialise the report the legacy way, for non-paged callers only."""
        if self._consumed:
            raise RuntimeError("a validated report is paged exactly once")
        self._consumed = True
        findings: list = []
        try:
            reader = self._reader()
            try:
                for row in saipal_report_stream.iter_report_findings(reader):
                    error = _report_row_error(row)
                    if error:
                        raise ValueError(error)
                    findings.append(row)
            finally:
                with suppress(Exception):
                    reader.detach()
            data = dict(self.envelope)
            data["findings"] = findings
            return data
        finally:
            self.close()

    def close(self) -> None:
        with suppress(Exception):
            self._spool.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def _envelope_error(data: object, command: str, *, streaming_report: bool = False) -> str | None:
    if not isinstance(data, dict) or type(data.get("ok")) is not bool:
        return "Backend envelope must be an object with a boolean ok field"
    if "schema_version" in data and (
        type(data["schema_version"]) is not int or data["schema_version"] != 1
    ):
        return "Unsupported backend envelope schema"
    # Native SAIPAL JSON is identified by its command, not a fabricated version.
    if data.get("command") != command:
        return "Backend response command does not match the requested operation"
    if command == "report":
        if streaming_report:
            # The findings array was validated element-by-element while it was
            # read, so it is absent from the envelope by design.
            if not isinstance(data.get("counts"), dict):
                return "Backend report requires object findings and an object counts field"
            if any(
                type(value) is not int or value < 0
                for value in data["counts"].values()
            ):
                return "Backend report has invalid finding identities or counters"
        elif (
            not isinstance(data.get("findings"), list)
            or not all(isinstance(row, dict) for row in data["findings"])
            or not isinstance(data.get("counts"), dict)
        ):
            return "Backend report requires object findings and an object counts field"
        elif any(
            _report_row_error(row) is not None for row in data["findings"]
        ) or any(type(value) is not int or value < 0 for value in data["counts"].values()):
            return "Backend report has invalid finding identities or counters"
    if command == "status":
        queue = data.get("queue")
        if (
            not isinstance(data.get("phase"), str)
            or not data["phase"].strip()
            or not isinstance(queue, dict)
        ):
            return "Backend status requires phase and queue"
        if any(type(queue[key]) is not int or queue[key] < 0 for key in queue):
            return "Backend queue counters must be nonnegative integers"
    if command == "next" and not isinstance(data.get("carrier"), str):
        return "Backend next response requires its read-only carrier"
    return None


def _read_append_log(path: Path) -> dict:
    """Read one byte-bounded snapshot; a damaged suffix never becomes empty history."""
    result = {
        "ok": True,
        "status": "LOG_VALID",
        "records": [],
        "path": str(path),
        "snapshot_size": 0,
        "suffix_status": "COMPLETE",
    }
    try:
        paths.prove_owned_regular(path, kind="SAIPAL history")
        with path.open("rb") as stream:
            remaining = result["snapshot_size"] = os.fstat(stream.fileno()).st_size
            offset, line_number = 0, 0
            while remaining:
                line_number += 1
                line = stream.readline(min(remaining, MAX_HISTORY_RECORD_BYTES + 1))
                remaining -= len(line)
                error = None
                status = "LOG_CORRUPT"
                if not line or not line.endswith(b"\n"):
                    status, error = "LOG_TRUNCATED", "Incomplete final append record"
                if len(line) > MAX_HISTORY_RECORD_BYTES:
                    status, error = "LOG_CORRUPT", "History record exceeds the declared size limit"
                if error is None and line.strip():
                    try:
                        row = _load_json(line.decode("utf-8"))
                        if not isinstance(row, dict):
                            raise ValueError("History record must be an object")
                        result["records"].append(row)
                    except (ValueError, UnicodeError, RecursionError) as exc:
                        error = str(exc)
                if error:
                    result.update(
                        {
                            "ok": False,
                            "status": status,
                            "error": error,
                            "error_offset": offset,
                            "error_line": line_number,
                            "valid_prefix_bytes": offset,
                            "suffix_status": "UNVERIFIED",
                            "damaged_record_hex": line.hex(),
                            "recovery": {
                                "action": "PRESERVE_AND_RECONCILE",
                                "path": str(path),
                                "unknown_suffix_offset": offset,
                                "automatic_repair_allowed": False,
                            },
                        }
                    )
                    return result
                offset += len(line)
    except FileNotFoundError:
        result.update(status="LOG_ABSENT")
    except (OSError, ValueError) as exc:
        result.update(ok=False, status="LOG_IO_ERROR", error=str(exc), suffix_status="UNVERIFIED")
    return result


def _quarantine_damaged_suffix(root: Path, path: Path, history: dict) -> dict:
    """Preserve the damaged bytes verbatim before any repair claims to be safe.

    W2-008 requires that "original damaged bytes remain recoverable". A repair
    that truncates first and then reports the offset has already destroyed the
    evidence it cites, so the suffix is copied out byte-for-byte under a
    content-addressed name and the copy is re-read to prove it matches.
    """
    offset = history.get("error_offset")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return {"ok": False, "status": "DAMAGED_SUFFIX_UNLOCATABLE"}
    try:
        with path.open("rb") as stream:
            stream.seek(offset)
            damaged = stream.read()
    except OSError as exc:
        return {"ok": False, "status": "DAMAGED_SUFFIX_UNREADABLE", "error": str(exc)}
    digest = hashlib.sha256(damaged).hexdigest()
    quarantine = (
        Path(root)
        / ".saipen"
        / "campaign"
        / "quarantine"
        / f"{path.name}.{offset}.{digest[:16]}.damaged"
    )
    try:
        paths.safe_atomic_write_bytes(
            quarantine,
            damaged,
            kind="SAIPAL damaged history suffix",
            ownership_root=Path(root),
        )
    except (OSError, ValueError) as exc:
        return {"ok": False, "status": "QUARANTINE_FAILED", "error": str(exc)}
    try:
        recovered = quarantine.read_bytes()
    except OSError as exc:
        return {"ok": False, "status": "QUARANTINE_UNVERIFIABLE", "error": str(exc)}
    if hashlib.sha256(recovered).hexdigest() != digest:
        return {"ok": False, "status": "QUARANTINE_DIGEST_MISMATCH"}
    return {
        "ok": True,
        "status": "DAMAGED_SUFFIX_PRESERVED",
        "path": quarantine.relative_to(Path(root)).as_posix(),
        "digest": digest,
        "bytes": len(damaged),
        "offset": offset,
    }


def _receipt_from_allocator(
    root: Path,
    row: dict,
    *,
    snapshot: dict | None = None,
    index: dict | None = None,
) -> dict | None:
    """Rebuild one publication receipt from the canonical enqueue allocator.

    Only `saipal` operations carry publication receipts, and only a COMMITTED
    allocator record plus a matching on-disk layer digest proves the layer was
    durably placed. Anything weaker (RESERVED, absent, corrupt allocator)
    returns None: R021 says recovery must not invent records, so an
    unprovable receipt stays missing.

    PERF-003: `snapshot` is one validated allocator document read once by the
    caller for the whole reconciliation pass. Before this, every reconstructed
    receipt re-read and re-parsed the complete allocator, so a damaged log with
    N recoverable operations cost N+1 full-file reads and N linear scans
    (measured: 21, 41 and 81 reads for 20, 40 and 80 operations). The digest
    check against the real artifact bytes stays per-receipt and is never
    short-circuited, because the snapshot proves which layer was allocated,
    not that the bytes are still the ones committed.
    """
    op_id = row.get("operation_id")
    finding_id = row.get("finding_id")
    layer = row.get("layer")
    if not isinstance(op_id, str) or not op_id:
        return None
    if not isinstance(finding_id, str) or not finding_id:
        return None
    if not isinstance(layer, int) or isinstance(layer, bool):
        return None
    if snapshot is not None:
        doc, allocator_state = snapshot, audit_enqueue.ALLOCATOR_OK
    else:
        doc, allocator_state = audit_enqueue.read_allocator_state(root)
    if allocator_state != audit_enqueue.ALLOCATOR_OK:
        return None
    if index is not None:
        record = index.get(("saipal", op_id, layer))
    else:
        record = _allocator_find_operation(doc, "saipal", op_id, layer)
    if record is None or record.get("state") != audit_enqueue.COMMITTED:
        return None
    canonical_digest = record.get("sha256")
    if not isinstance(canonical_digest, str) or not canonical_digest:
        return None
    try:
        actual = hashlib.sha256((Path(root) / "audit" / f"{layer}.md").read_bytes()).hexdigest()
    except OSError:
        return None
    if actual != canonical_digest:
        return None
    return {
        "finding_id": finding_id,
        "operation_id": op_id,
        "layer": layer,
        "digest": canonical_digest,
        "idempotent": True,
        "delivered_at": str(record.get("created_at") or _utc_now()),
        "reconciled": True,
    }


def _allocator_operation_index(doc: dict) -> dict:
    """Index one allocator snapshot by `(producer, operation_id, layer)`.

    PERF-003: rebuilding N receipts used to scan the operation collection N
    times. One linear pass here turns every lookup in the pass into a dict hit,
    so the reconciliation cost is linear in the allocator size plus linear in
    the recovered receipts, instead of quadratic in both.
    """
    index: dict = {}
    for record in (doc.get("operations") or {}).values():
        if not isinstance(record, dict):
            continue
        key = (
            str(record.get("producer") or ""),
            str(record.get("producer_operation_id") or ""),
            record.get("layer"),
        )
        index.setdefault(key, record)
    return index


def _allocator_find_operation(
    doc: dict, producer: str, operation_id: str, layer: object
) -> dict | None:
    """Linear fallback lookup when no index was built by the caller."""
    for candidate in (doc.get("operations") or {}).values():
        if not isinstance(candidate, dict):
            continue
        if (
            str(candidate.get("producer") or "") == producer
            and str(candidate.get("producer_operation_id") or "") == operation_id
            and candidate.get("layer") == layer
        ):
            return candidate
    return None


def _broker_verified(receipt: object) -> bool:
    """Is this really a proof the live broker wrote?

    CORE-001/CORE-004 (audit/27.md) reproduced `DELIVERED_PUBLICATION` and
    `DISPOSITION_RECORDED` from a caller dict shaped
    `{"authenticated": True, "signature": "obviously-forged"}`. Two boolean
    and string fields cannot be a proof: they are values the *caller* chose.
    The only thing that distinguishes a broker record is the keyed provenance
    that broker alone can reproduce, so this defers to the shared trusted
    boundary `host_authority_client.verify_record`, and no broker answering is
    False. A failure is never downgraded into an unauthenticated attempt:
    callers turn False into a refusal that names the missing broker.
    """
    from . import host_authority_client

    if not isinstance(receipt, dict):
        return False
    try:
        return bool(host_authority_client.verify_record(receipt))
    except Exception:
        return False


def _history_index_path(root: Path, filename: str) -> Path:
    return root / ".saipen" / "campaign" / f"{filename}.index.json"


def _history_index_identity(path: Path) -> dict | None:
    """A witness for the bytes an index was built from, or None when unknown.

    PERF-002: the index is a CACHE, never authority. It is accepted only while
    the log it describes still has exactly the size and modification time the
    index recorded. Anything else -- a different size, a different mtime, a
    missing index, an unreadable one -- falls back to reading the log itself,
    so a stale cache can cost time but can never hide a record.
    """
    try:
        stat = path.stat()
    except OSError:
        return None
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def load_history_index(root: Path, filename: str) -> dict | None:
    """The validated `{operation_id: row}` index for one history log, or None."""
    log_path = root / ".saipen" / "campaign" / filename
    identity = _history_index_identity(log_path)
    if identity is None:
        return None
    index_path = _history_index_path(root, filename)
    try:
        raw = index_path.read_bytes()
    except OSError:
        return None
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    if doc.get("schema_version") != 1 or doc.get("witness") != identity:
        return None
    rows = doc.get("operations")
    if not isinstance(rows, dict):
        return None
    return rows


def save_history_index(root: Path, filename: str, records: list[dict]) -> bool:
    """Persist the index for exactly these bytes. Best-effort, never required.

    A failed index write is not a failed publication: the append log is the
    authority and the index only saves a re-parse, so this returns False and
    the caller carries on.
    """
    log_path = root / ".saipen" / "campaign" / filename
    identity = _history_index_identity(log_path)
    if identity is None:
        return False
    operations: dict = {}
    for row in records:
        op_id = str(row.get("operation_id") or "")
        if op_id:
            operations[op_id] = row
    payload = {
        "schema_version": 1,
        "witness": identity,
        "operations": operations,
    }
    try:
        paths.safe_atomic_write_bytes(
            _history_index_path(root, filename),
            (json.dumps(payload, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"),
            kind="SAIPAL history index",
            ownership_root=root,
        )
    except (OSError, ValueError):
        return False
    return True


def _history_index_update(
    root: Path, filename: str, record: dict
) -> bool:
    """Add ONE record to the existing index without re-reading the log.

    PERF-002's remaining cost was the append path itself: the lock held a
    full-log parse so that the index could be rebuilt with the new row. The
    index is already a cache of every row in the log, so the new row can be
    merged into it directly -- one small read, one small write -- as long as the
    witness still matches the bytes it describes.

    Correctness is unchanged: the index is accepted only while its witness
    matches, and any mismatch (including this function's own failure) makes the
    next reader fall back to parsing the log.
    """
    log_path = root / ".saipen" / "campaign" / filename
    identity = _history_index_identity(log_path)
    if identity is None:
        return False
    index_path = _history_index_path(root, filename)
    try:
        doc = json.loads(index_path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        return False
    if not isinstance(doc.get("operations"), dict):
        return False
    op_id = str(record.get("operation_id") or "")
    if not op_id:
        return False
    operations = dict(doc["operations"])
    operations[op_id] = record
    payload = {"schema_version": 1, "witness": identity, "operations": operations}
    try:
        paths.safe_atomic_write_bytes(
            index_path,
            (json.dumps(payload, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"),
            kind="SAIPAL history index",
            ownership_root=root,
        )
    except (OSError, ValueError):
        return False
    return True


def _history_lookup_records(root: Path, filename: str) -> dict | None:
    """The validated index rows, or an EMPTY dict when there is no log at all.

    Distinguishing "no log" from "no index" is what lets the append path answer
    uniqueness without parsing: an absent log cannot hold a conflicting row.
    """
    log_path = root / ".saipen" / "campaign" / filename
    if not log_path.exists():
        return {}
    return load_history_index(root, filename)


def _find_history_record(root: Path, filename: str, operation_id: str) -> dict | None:
    """The recorded row for one operation identity, or None.

    A damaged log is not an empty one: if the history cannot be read, this
    raises so the caller refuses instead of appending a duplicate next to
    records it could not see.

    PERF-002: the index is consulted first so a normal lookup costs one small
    JSON read instead of a full parse of the receipt history. The index is
    witness-validated against the log's size and mtime, so a stale cache is
    simply ignored; correctness still comes from the log.
    """
    index = load_history_index(root, filename)
    if index is not None:
        row = index.get(operation_id)
        if isinstance(row, dict):
            return row
    history = _read_append_log(root / ".saipen" / "campaign" / filename)
    if history["status"] == "LOG_ABSENT":
        return None
    if not history["ok"]:
        raise ValueError(
            f"{filename} is {history['status']}: {history.get('error', 'unreadable')}"
        )
    for row in history["records"]:
        if str(row.get("operation_id") or "") == operation_id:
            return row
    return None


def _history_snapshot_for_append(root: Path, path: Path, filename: str) -> dict:
    """Everything the append path needs to know, at the cheapest honest price.

    PERF-002's real cost was here: the uniqueness check inside the lock parsed
    the ENTIRE receipt log on every append, so end-to-end publication was
    O(history) per receipt and O(N^2) over a campaign. Two shapes are possible:

      * ``INDEXED`` -- a witness-valid index describes exactly the bytes now on
        disk, which means a full parse already succeeded against them and
        nothing has changed since. Uniqueness is then one dict lookup.
      * ``PARSED``  -- no log (nothing can conflict) or no usable index. The log
        is parsed once; the index is (re)built from that parse, so only the
        first append after a lost index pays this.

    A damaged log is never silently appended to: `PARSED` carries the reader's
    failure and the caller refuses.
    """
    if not path.exists():
        return {
            "mode": "INDEXED",
            "rows": {},
            "history": None,
            "log_absent": True,
        }
    indexed = load_history_index(root, filename)
    if indexed is not None:
        return {"mode": "INDEXED", "rows": indexed, "history": None, "log_absent": False}
    history = _read_append_log(path)
    if not history["ok"]:
        return {"mode": "PARSED", "rows": None, "history": history, "log_absent": False}
    rows: dict = {}
    for row in history.get("records") or []:
        op_id = str(row.get("operation_id") or "")
        if op_id:
            rows[op_id] = row
    return {"mode": "PARSED", "rows": rows, "history": history, "log_absent": False}


def _history_after_append(root: Path, filename: str, record: dict, snapshot: dict) -> None:
    """Make the index describe the log that now exists. Never a publication.

    Ordering is the crash contract: the row is already fsynced into the log, so
    a failure here only costs the next reader a parse (the witness will not
    match). A crash between the two therefore cannot invent or lose a receipt.
    """
    if snapshot["mode"] == "INDEXED":
        _history_index_update(root, filename, record)
        return
    history = snapshot.get("history")
    base = list(history.get("records") or []) if isinstance(history, dict) else []
    save_history_index(root, filename, [*base, record])


def _append_history(root: Path, filename: str, record: dict) -> dict:
    path = root / ".saipen" / "campaign" / filename
    try:
        body = (json.dumps(record, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        if len(body) > MAX_HISTORY_RECORD_BYTES:
            return {"ok": False, "status": "HISTORY_RESOURCE_LIMIT", "path": str(path)}
        with _history_write_lock(root):
            paths.prove_owned_dir_chain(path.parent, ownership_root=root, kind="SAIPAL history")
            path.parent.mkdir(parents=True, exist_ok=True)
            with suppress(FileNotFoundError):
                paths.prove_owned_regular(path, kind="SAIPAL history")
            snapshot = _history_snapshot_for_append(root, path, filename)
            if snapshot["mode"] == "PARSED":
                history = snapshot["history"]
                if not history["ok"]:
                    return history
            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
            flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "ab") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            _history_after_append(root, filename, record, snapshot)
            return {"ok": True, "status": "HISTORY_RECORDED", "path": str(path)}
    except lock.FileLockBusy:
        return {"ok": False, "status": "HISTORY_BUSY", "path": str(path)}
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "status": "HISTORY_WRITE_FAILED",
            "path": str(path),
            "error": str(exc),
            "outcome_unknown": True,
        }


def _append_history_unique(root: Path, filename: str, record: dict) -> dict:
    """Append one record only if no row already holds its operation identity.

    W2-003: `deliver_finding_to_audit_inbox` used to look the receipt up
    OUTSIDE the writer lock and then append, so two identical concurrent
    deliveries both saw "absent" and both appended -- two rows for one
    `operation_id`, while the allocator had correctly published a single layer.
    The lookup, the digest comparison and the append now happen in one
    exclusive transaction, so uniqueness is a property of the write itself.

    PERF-002: the transaction's lookup is an index hit rather than a full-log
    parse whenever a witness-valid index describes the log, so the lock is held
    for one small read plus one append regardless of history length.

    Returns:
      * ``HISTORY_RECORDED`` -- a new row was appended;
      * ``HISTORY_PRESENT``  -- an identical row already existed (the stored
        row is returned unchanged, including its original timestamp);
      * ``HISTORY_CONFLICT`` -- the same operation id carries a different
        digest; refused, never overwritten.
    """
    path = root / ".saipen" / "campaign" / filename
    operation_id = str(record.get("operation_id") or "")
    try:
        body = (json.dumps(record, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        if len(body) > MAX_HISTORY_RECORD_BYTES:
            return {"ok": False, "status": "HISTORY_RESOURCE_LIMIT", "path": str(path)}
        with _history_write_lock(root):
            paths.prove_owned_dir_chain(path.parent, ownership_root=root, kind="SAIPAL history")
            path.parent.mkdir(parents=True, exist_ok=True)
            with suppress(FileNotFoundError):
                paths.prove_owned_regular(path, kind="SAIPAL history")
            snapshot = _history_snapshot_for_append(root, path, filename)
            if snapshot["mode"] == "PARSED":
                history = snapshot["history"]
                if not history["ok"] and history["status"] != "LOG_ABSENT":
                    return history
            existing = (snapshot["rows"] or {}).get(operation_id)
            if isinstance(existing, dict):
                if existing.get("digest") != record.get("digest"):
                    return {
                        "ok": False,
                        "status": "HISTORY_CONFLICT",
                        "path": str(path),
                        "existing": existing,
                    }
                return {
                    "ok": True,
                    "status": "HISTORY_PRESENT",
                    "path": str(path),
                    "existing": existing,
                }
            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
            flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "ab") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            _history_after_append(root, filename, record, snapshot)
            return {"ok": True, "status": "HISTORY_RECORDED", "path": str(path), "record": record}
    except lock.FileLockBusy:
        return {"ok": False, "status": "HISTORY_BUSY", "path": str(path)}
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "status": "HISTORY_WRITE_FAILED",
            "path": str(path),
            "error": str(exc),
            "outcome_unknown": True,
        }


DEFAULT_SAIPAL_PATHS = [
    Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPAL"),
]


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SaipalAdapter:
    """Logical and execution backend connecting SAIPEN campaign to SAIPAL."""

    def __init__(self, saipal_home: Path | str | None = None) -> None:
        self.saipal_home = Path(saipal_home).resolve() if saipal_home else self._resolve_home()

    def _resolve_home(self) -> Path | None:
        env_home = os.environ.get("SAIPAL_HOME")
        if env_home and Path(env_home).is_dir():
            return Path(env_home).resolve()
        for candidate in DEFAULT_SAIPAL_PATHS:
            if (candidate / "tools" / "saipal.py").is_file():
                return candidate
        return None

    def _resolve_cli(self) -> tuple[Path | None, Path | None]:
        if not self.saipal_home:
            return None, None
        cli_tool = self.saipal_home / "tools" / "saipal.py"
        dot_saipal = self.saipal_home / ".saipal"
        if cli_tool.is_file() and dot_saipal.is_dir():
            return cli_tool, dot_saipal
        return None, None

    def _classify_response(
        self,
        data: object,
        command: str,
        *,
        exit_code: int,
        transport: str,
        stderr: bytes,
        transport_bytes: int | None,
        streaming_report: bool = False,
    ) -> dict:
        """Apply the common envelope, refusal and command-schema rules.

        Shared by the materialising `_run_cmd` and the streaming report path so
        a report cannot be accepted by one and refused by the other.
        """
        if (
            not isinstance(data, dict)
            or type(data.get("ok")) is not bool
            or ("status" in data and not isinstance(data["status"], str))
            or ("code" in data and not isinstance(data["code"], str))
            or ("command" in data and data["command"] != command)
            or (
                "schema_version" in data
                and (type(data["schema_version"]) is not int or data["schema_version"] != 1)
            )
        ):
            return {
                "ok": False,
                "status": BACKEND_PROTOCOL_ERROR,
                "transport_status": transport,
                "protocol_status": "INVALID",
                "operation_status": "UNKNOWN",
                "returncode": exit_code,
                "error": "Backend envelope has invalid common fields",
            }
        status = data.get("status") or data.get("code")
        refused = {
            ANALYSIS_BLOCKED,
            AUTHORITY_REQUIRED,
            SOURCE_NOT_ENROLLED,
            RUNTIME_UNAVAILABLE,
            RETRYABLE_FAILURE,
            PERMANENT_FAILURE,
            "REFUSED",
            "REJECTED",
            "ERROR",
            "BLOCKED",
        }
        if data.get("ok") is False or status in refused:
            return {
                "ok": False,
                "status": status or PERMANENT_FAILURE,
                "transport_status": transport,
                "protocol_status": "VALID",
                "operation_status": "FAILED",
                "returncode": exit_code,
                "error": data.get("error")
                or data.get("detail")
                or data.get("message")
                or "SAIPAL backend refused the operation",
                "data": data,
            }
        error = _envelope_error(data, command, streaming_report=streaming_report)
        if error or exit_code != 0:
            return {
                "ok": False,
                "status": BACKEND_PROTOCOL_ERROR if exit_code == 0 else PERMANENT_FAILURE,
                "transport_status": transport,
                "protocol_status": "INVALID" if error else "VALID",
                "operation_status": "UNKNOWN",
                "returncode": exit_code,
                "error": error
                or stderr.decode("utf-8", errors="replace").strip()
                or f"Backend process exited {exit_code}",
            }
        return {
            "ok": True,
            "data": data,
            "transport_status": transport,
            "protocol_status": "VALID",
            "operation_status": "SUCCEEDED",
            "returncode": 0,
            "transport_bytes": transport_bytes,
        }

    def _run_cmd(self, subcommand: str, *args: str) -> dict:
        cli, home = self._resolve_cli()
        if not cli or not home:
            return {
                "ok": False,
                "status": RUNTIME_UNAVAILABLE,
                "error": "SAIPAL installation not found",
            }
        cmd = [sys.executable, str(cli), "--json", "--home", str(home), subcommand, *args]
        # PERF-004: a report is allowed to be larger than an ordinary response
        # and is decoded incrementally; every other command keeps the small bound.
        report_limit = (
            REPORT_SPOOL_LIMIT_BYTES
            if subcommand == "report"
            else MAX_BACKEND_STDOUT_BYTES
        )
        try:
            res = _backend_capture(cmd, stdout_limit=report_limit)
            if not res["ok"]:
                return res
            exit_code = res["returncode"]
            transport = "EXITED" if exit_code == 0 else "FAILED"
            stdout_spool = res["stdout_file"]
            try:
                if subcommand == "report":
                    # This is the MATERIALISING report API: `collect_findings`
                    # and `discover` return the corpus to their caller, so the
                    # list is the contract. Paged consumers use `_open_report`
                    # instead and never hold it.
                    reader = io.TextIOWrapper(stdout_spool, encoding="utf-8", newline="")
                    try:
                        envelope, findings = saipal_report_stream.read_report(reader)
                    finally:
                        with suppress(Exception):
                            reader.detach()
                        with suppress(Exception):
                            stdout_spool.close()
                    if findings is not None and (
                        envelope.get("ok") is not False or findings
                    ):
                        envelope["findings"] = findings
                    data = envelope
                else:
                    try:
                        payload_bytes = stdout_spool.read(res["stdout_bytes_len"])
                    finally:
                        with suppress(Exception):
                            stdout_spool.close()
                    data = _load_json(payload_bytes.decode("utf-8"))
            except (ValueError, UnicodeError, RecursionError) as exc:
                detail = res["stderr"].decode("utf-8", errors="replace").strip()
                return {
                    "ok": False,
                    "status": BACKEND_PROTOCOL_ERROR if exit_code == 0 else PERMANENT_FAILURE,
                    "transport_status": transport,
                    "protocol_status": "INVALID",
                    "operation_status": "UNKNOWN",
                    "returncode": exit_code,
                    "error": detail or str(exc),
                }
            return self._classify_response(
                data,
                subcommand,
                exit_code=exit_code,
                transport=transport,
                stderr=res["stderr"],
                transport_bytes=res["stdout_bytes_len"],
            )
        except OSError as exc:
            return {
                "ok": False,
                "status": RUNTIME_UNAVAILABLE,
                "error": str(exc),
                "transport_status": "UNAVAILABLE",
                "protocol_status": "UNOBSERVED",
                "operation_status": "UNKNOWN",
            }

    def _capture_report_spool(self) -> dict:
        """Run ``saipal report`` and return its bounded capture.

        The one report-transport seam. Production runs the real subprocess; a
        test substitutes a spool of bytes. Everything above it -- Phase A
        validation, identity, paging, descriptor closure -- is the same code on
        both paths, which is what makes the regression measure the real thing.
        """
        cli, home = self._resolve_cli()
        if not cli or not home:
            return {
                "ok": False,
                "status": RUNTIME_UNAVAILABLE,
                "error": "SAIPAL installation not found",
            }
        cmd = [sys.executable, str(cli), "--json", "--home", str(home), "report"]
        try:
            return _backend_capture(cmd, stdout_limit=REPORT_SPOOL_LIMIT_BYTES)
        except OSError as exc:
            return {
                "ok": False,
                "status": RUNTIME_UNAVAILABLE,
                "error": str(exc),
                "transport_status": "UNAVAILABLE",
                "protocol_status": "UNOBSERVED",
                "operation_status": "UNKNOWN",
            }

    def _open_report(self) -> dict:
        """Capture, validate and hand back a paged report (PERF-004 Phase A).

        The whole captured response is validated here, before any finding can
        be delivered: a malformed, truncated or oversized payload is a typed
        refusal, never a partial page. What is retained is the spool (already
        bounded by the transport) plus one ``[id, content_digest]`` pair per
        finding; the finding objects themselves are re-read per page.
        """
        res = self._capture_report_spool()
        if not res.get("ok"):
            return res
        exit_code = res["returncode"]
        transport = "EXITED" if exit_code == 0 else "FAILED"
        spool = res["stdout_file"]
        try:
            reader = io.TextIOWrapper(spool, encoding="utf-8", newline="")
            try:
                envelope, corpus, _count = _stream_report_validation(reader)
            finally:
                with suppress(Exception):
                    reader.detach()
        except (ValueError, UnicodeError, RecursionError) as exc:
            with suppress(Exception):
                spool.close()
            detail = res["stderr"].decode("utf-8", errors="replace").strip()
            return {
                "ok": False,
                "status": BACKEND_PROTOCOL_ERROR if exit_code == 0 else PERMANENT_FAILURE,
                "transport_status": transport,
                "protocol_status": "INVALID",
                "operation_status": "UNKNOWN",
                "returncode": exit_code,
                "error": detail or str(exc),
            }
        classified = self._classify_response(
            envelope,
            "report",
            exit_code=exit_code,
            transport=transport,
            stderr=res["stderr"],
            transport_bytes=res["stdout_bytes_len"],
            streaming_report=True,
        )
        if not classified["ok"]:
            with suppress(Exception):
                spool.close()
            return classified
        return {
            "ok": True,
            "report": _ValidatedReport(
                spool,
                envelope,
                corpus,
                _report_identity(envelope, corpus, res["stdout_bytes_len"]),
                res["stdout_bytes_len"],
            ),
        }

    def probe(self) -> dict:
        """Prove SAIPAL runtime binding, readiness and environment health."""
        cli, home = self._resolve_cli()
        if not cli or not home:
            return {
                "ok": False,
                "status": RUNTIME_UNAVAILABLE,
                "detail": f"SAIPAL installation not found at {self.saipal_home}",
            }
        outcome = self._run_cmd("status")
        if not outcome["ok"]:
            return outcome
        data = outcome["data"]
        return {
            "ok": True,
            "status": "BOUND",
            "home": str(home),
            "episodes": data.get("episodes", 0),
            "events_indexed": data.get("events_indexed", 0),
            "phase": data.get("phase", "UNKNOWN"),
            "next_action": data.get("next_action", ""),
            "data": data,
        }

    def start_or_resume(self) -> dict:
        """Advance or resume the next unit in forensic analysis."""
        return self._run_cmd("next")

    def collect_findings(self, *, qualified_only: bool = False) -> dict:
        """Collect findings from SAIPAL report."""
        outcome = self._run_cmd("report")
        if not outcome["ok"]:
            return outcome
        findings = outcome["data"].get("findings", [])
        if qualified_only:
            findings = [
                f for f in findings if str(f.get("state", "")).upper() in ("QUALIFIED", "CONFIRMED")
            ]
        return {**outcome, "findings": findings}

    def iter_finding_pages(self, *, page_size: int = REPORT_PAGE_DEFAULT):
        """Yield ``(page_index, total_pages, findings_slice, source_identity)``.

        R027/PERF-004: a report may be larger than the transport bound, and a
        consumer that wants only new qualified findings must not be forced to
        materialise the whole corpus. Phase A validates the complete captured
        response and keeps only identity metadata; Phase B re-reads the verified
        spool one page at a time, so the resident finding set is the page being
        delivered rather than the whole report.

        ``source_identity`` is stable across pages of one report (a digest of
        the envelope plus the sorted id->content digests), so a resumed run can
        prove it is continuing the SAME corpus rather than silently mixing two
        reports.
        """
        if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 1:
            return
        # PERF-004 item 8: the declared bounds apply at the PUBLIC pagination
        # boundary too, not only to internal callers that already clamp.
        page_size = self.report_page_size(page_size)
        opened = self._open_report()
        if not opened.get("ok"):
            yield (
                "ERROR",
                0,
                [],
                {
                    "status": opened.get("status"),
                    "error": opened.get("error"),
                    "outcome_unknown": opened.get("outcome_unknown"),
                },
            )
            return
        report = opened["report"]
        total = report.total_findings
        total_pages = max(1, (total + page_size - 1) // page_size)
        identity = report.identity
        try:
            index = 0
            try:
                for page in report.iter_pages(page_size):
                    yield index, total_pages, page, identity
                    index += 1
            except (ValueError, UnicodeError, RecursionError):
                # The spool passed Phase A, so this is a re-read failure (a
                # reaping process, a truncated temp file). It is reported as the
                # same protocol error Phase A would have produced, and no page
                # from the damaged pass is offered as a complete corpus.
                yield (
                    "ERROR",
                    0,
                    [],
                    {
                        "status": BACKEND_PROTOCOL_ERROR,
                        "error": "the validated report spool could not be re-read",
                    },
                )
                return
            if index == 0:
                # An empty corpus still has one (empty) page, which is what the
                # pre-PERF-004 contract promised callers.
                yield 0, 1, [], identity
        finally:
            report.close()

    def report_page_size(self, requested: int | None = None) -> int:
        """Clamp a requested page size into the declared transport bounds."""
        if not isinstance(requested, int) or isinstance(requested, bool) or requested < 1:
            return REPORT_PAGE_DEFAULT
        return min(requested, REPORT_PAGE_MAX)

    def _committed_publication_finding_ids(self, root: Path) -> set[str]:
        """Finding ids the canonical audit allocator already holds as COMMITTED.

        W2-002: this is the ONE durable answer to "was this finding delivered?".
        The cursor is a walk position and cannot be the delivery watermark, so
        eligibility is recomputed from the allocator each walk. An unreadable or
        unavailable allocator yields an empty set, which fails toward re-yielding
        a finding -- publication is idempotent by operation_id, so a duplicate
        attempt is recoverable while a skip is not.
        """
        try:
            doc, state = audit_enqueue.read_allocator_state(root)
        except Exception:
            return set()
        if state != audit_enqueue.ALLOCATOR_OK or not isinstance(doc, dict):
            return set()
        committed: set[str] = set()
        for record in (doc.get("operations") or {}).values():
            if not isinstance(record, dict):
                continue
            if str(record.get("producer") or "") != "saipal":
                continue
            if str(record.get("state") or "") != audit_enqueue.COMMITTED:
                continue
            # `producer_item_id` carries the finding id verbatim. Deriving it by
            # stripping the `saipal-` prefix off the operation id would lowercase
            # it, because the operation id is built from `fid.lower()`, and a
            # lowercased id never matches the report row it came from.
            item_id = record.get("producer_item_id")
            if isinstance(item_id, str) and item_id:
                committed.add(item_id)
                continue
            op_id = str(record.get("producer_operation_id") or "")
            if op_id.startswith("saipal-") and len(op_id) > len("saipal-"):
                committed.add(op_id[len("saipal-"):])
        return committed

    def load_page_checkpoint(self, project_root: Path | str) -> dict:
        """Read the resumable report cursor, or an empty one when absent."""
        root = Path(project_root).resolve()
        path = root / ".saipen" / "campaign" / "saipal_report_cursor.json"
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return {
                "ok": True,
                "status": "CURSOR_ABSENT",
                "cursor": {},
                "path": str(path),
            }
        except OSError as exc:
            return {"ok": False, "status": "CURSOR_IO_ERROR", "error": str(exc), "path": str(path)}
        try:
            cursor = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return {
                "ok": False,
                "status": "CURSOR_CORRUPT",
                "error": str(exc),
                "path": str(path),
            }
        if not isinstance(cursor, dict):
            return {"ok": False, "status": "CURSOR_CORRUPT", "path": str(path)}
        return {"ok": True, "status": "CURSOR_OK", "cursor": cursor, "path": str(path)}

    # ------------------------------------------------------------------
    # PERF-005: acknowledgment storage that does not grow the cursor.
    #
    # The cursor used to carry `delivered_finding_ids`, sorted and re-encoded
    # into the checkpoint after EVERY page, so a walk over N findings wrote
    # O(pages * N) bytes and retained every id it had ever seen. Measured at
    # 20/40/80 pages: 61450 / 234910 / 917830 cumulative serialized bytes --
    # quadratic. Acknowledgment is now an append-only batch journal, one
    # bounded line per acknowledged batch, while the checkpoint keeps only the
    # walk position. Canonical publication receipts stay the primary evidence;
    # this journal is the memo of an observation the allocator already holds,
    # and compaction drops rows the allocator can prove.
    # ------------------------------------------------------------------

    def _ack_journal_path(self, root: Path) -> Path:
        return root / ".saipen" / "campaign" / ACK_JOURNAL_NAME

    def _read_ack_rows(self, root: Path) -> dict:
        """All acknowledgment rows, or a typed refusal. Never a silent reset.

        A damaged journal is treated like a damaged cursor (W2-005): the walk
        stops and the original bytes stay where they are, because continuing
        over them could suppress a finding that was never published.
        """
        path = self._ack_journal_path(root)
        history = _read_append_log(path)
        if history.get("status") == "LOG_ABSENT":
            return {"ok": True, "rows": []}
        if not history.get("ok"):
            return {
                "ok": False,
                "status": history.get("status") or "ACK_JOURNAL_CORRUPT",
                "error": history.get("error"),
                "path": str(path),
            }
        rows = [row for row in history.get("records") or [] if isinstance(row, dict)]
        return {"ok": True, "rows": rows}

    def _acknowledged_ids(self, root: Path, source_digest: str | None) -> dict:
        """Finding ids acknowledged for THIS corpus, from the memo journal.

        Scope by source digest on purpose: an id acknowledged under a different
        corpus must not suppress a re-used id in this one (W2-006).
        """
        loaded = self._read_ack_rows(root)
        if not loaded["ok"]:
            return loaded
        ids: set[str] = set()
        for row in loaded["rows"]:
            if source_digest is not None and row.get("source_digest") not in (None, source_digest):
                continue
            ids |= {str(x) for x in (row.get("finding_ids") or [])}
        return {"ok": True, "ids": ids}

    def _append_ack_batch(self, root: Path, finding_ids, *, source_digest: str | None) -> dict:
        """Append one bounded acknowledgment batch. Idempotent by content.

        Repeating a batch is harmless (the reader unions into a set) and costs
        one small line, so a replayed acknowledgment is cheap and cannot lose
        or duplicate anything.
        """
        ids = sorted({str(x) for x in finding_ids if str(x)})
        if not ids:
            return {"ok": True, "status": "ACK_EMPTY", "acknowledged": []}
        path = self._ack_journal_path(root)
        record = {
            "schema_version": 1,
            "source_digest": source_digest,
            "finding_ids": ids,
            "acknowledged_at": _utc_now(),
        }
        body = (json.dumps(record, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        if len(body) > MAX_HISTORY_RECORD_BYTES:
            return {"ok": False, "status": "ACK_BATCH_TOO_LARGE", "path": str(path)}
        try:
            with _history_write_lock(root):
                paths.prove_owned_dir_chain(
                    path.parent, ownership_root=root, kind="SAIPAL acknowledgment"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                with suppress(FileNotFoundError):
                    paths.prove_owned_regular(path, kind="SAIPAL acknowledgment")
                flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
                flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(path, flags, 0o600)
                with os.fdopen(descriptor, "ab") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
        except lock.FileLockBusy:
            return {"ok": False, "status": "ACK_BUSY", "path": str(path)}
        except (OSError, ValueError) as exc:
            return {"ok": False, "status": "ACK_WRITE_FAILED", "path": str(path), "error": str(exc)}
        return {
            "ok": True,
            "status": "ACK_RECORDED",
            "path": str(path),
            "acknowledged": ids,
            "bytes": len(body),
        }

    def _compact_ack_journal(self, root: Path, *, force: bool = False) -> dict:
        """Drop acknowledgment rows the canonical allocator can already prove.

        The journal exists only for the window between "written batch" and
        "canonical receipt", so once every id in a row is COMMITTED the row is
        redundant. Compaction is atomic and only runs at a size threshold, which
        keeps the file bounded without turning ack into an O(history) write.
        A row whose ids are not all provable is preserved verbatim -- old
        acknowledgment evidence is never silently discarded.
        """
        path = self._ack_journal_path(root)
        try:
            size = path.stat().st_size
        except OSError:
            return {"ok": True, "status": "ACK_COMPACT_SKIPPED", "compacted": False}
        if not force and size < ACK_JOURNAL_COMPACT_BYTES:
            return {"ok": True, "status": "ACK_COMPACT_SKIPPED", "compacted": False, "size": size}
        loaded = self._read_ack_rows(root)
        if not loaded["ok"]:
            return loaded
        committed = self._committed_publication_finding_ids(root)
        kept: list[dict] = []
        for row in loaded["rows"]:
            ids = {str(x) for x in (row.get("finding_ids") or [])}
            if ids and ids <= committed:
                continue
            kept.append(row)
        payload = b"".join(
            (json.dumps(row, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
            for row in kept
        )
        try:
            paths.safe_atomic_write_bytes(
                path,
                payload,
                kind="SAIPAL acknowledgment",
                ownership_root=root,
            )
        except (OSError, ValueError) as exc:
            return {"ok": False, "status": "ACK_COMPACT_FAILED", "error": str(exc)}
        return {
            "ok": True,
            "status": "ACK_COMPACTED",
            "compacted": True,
            "rows_kept": len(kept),
            "rows_dropped": len(loaded["rows"]) - len(kept),
        }

    def acknowledge_delivery(
        self, project_root: Path | str, finding_ids: list[str], *, source_digest: str
    ) -> dict:
        """Record that these findings are durably published, after the fact.

        W2-002: acknowledgment is a separate lifecycle event from yielding, so
        it is a separate call. The caller invokes this only after observing a
        committed publication; the durable truth is still the allocator, and
        this record is a memo of that observation, never a substitute for it.

        PERF-005: the memo is one appended batch, not a regenerated list of
        everything ever acknowledged, so its cost follows the new work rather
        than the accumulated history.
        """
        root = Path(project_root).resolve()
        checkpoint = self.load_page_checkpoint(root)
        if not checkpoint.get("ok"):
            return {
                "ok": False,
                "status": "CURSOR_UNREADABLE",
                "error": checkpoint.get("error") or checkpoint.get("status"),
            }
        appended = self._append_ack_batch(root, finding_ids, source_digest=source_digest)
        if not appended.get("ok"):
            return appended
        compacted = self._compact_ack_journal(root)
        if not compacted.get("ok"):
            # The batch is already durable; a failed compaction is reported but
            # never turns a recorded acknowledgment into a lost one.
            return {
                "ok": True,
                "status": "DELIVERY_ACKNOWLEDGED",
                "acknowledged": appended.get("acknowledged") or [],
                "compaction": compacted,
            }
        return {
            "ok": True,
            "status": "DELIVERY_ACKNOWLEDGED",
            "acknowledged": appended.get("acknowledged") or [],
            "ack_bytes": appended.get("bytes"),
        }

    def save_page_checkpoint(self, project_root: Path | str, cursor: dict) -> dict:
        """Persist the resumable report cursor atomically."""
        root = Path(project_root).resolve()
        path = root / ".saipen" / "campaign" / "saipal_report_cursor.json"
        try:
            paths.safe_atomic_write_bytes(
                path,
                (json.dumps(cursor, indent=2, sort_keys=True) + "\n").encode("utf-8"),
                kind="SAIPAL report cursor",
                ownership_root=root,
            )
        except (OSError, ValueError) as exc:
            return {"ok": False, "status": "CURSOR_WRITE_FAILED", "error": str(exc)}
        return {"ok": True, "status": "CURSOR_RECORDED", "path": str(path)}

    def iter_new_qualified_findings(
        self,
        project_root: Path | str,
        *,
        page_size: int | None = None,
        expect_source_digest: str | None = None,
    ):
        """Walk the report in pages, skipping findings already ACKNOWLEDGED.

        R027 requires that an interrupted batch resumes without skipped
        findings and that a replayed batch does not duplicate publication.

        W2-002: returning a page is not delivering it. Before this, the durable
        cursor recorded a finding as delivered the moment it was yielded, so a
        crash, exception or refused publication afterwards made a qualified
        finding permanently invisible to every later walk -- reproduced with
        PAL-1 disappearing from an unchanged report while no audit layer
        existed. The cursor is now an acknowledgment watermark, and a finding is
        acknowledged only when the canonical audit allocator holds a COMMITTED
        operation for it. The allocator is the durable truth; this method never
        invents a second publication ledger.

        A resume against a DIFFERENT source digest starts over rather than
        mixing corpora, because a changed source could have inserted a finding
        anywhere in the order.
        """
        root = Path(project_root).resolve()
        size = self.report_page_size(page_size)
        checkpoint = self.load_page_checkpoint(root)
        # W2-005: a corrupt cursor is not an absent one. Treating it as empty
        # replaced the operator's bytes with a fresh cursor and reported success,
        # so a durable recovery state could be destroyed by merely continuing.
        if not checkpoint.get("ok"):
            yield {
                "ok": False,
                "status": checkpoint.get("status") or "CURSOR_UNREADABLE",
                "error": checkpoint.get("error")
                or "the report cursor cannot be read; refusing to walk over it",
                "path": checkpoint.get("path"),
                "page_index": None,
            }
            return
        # The cursor is WRITTEN by this walk as an observability watermark but
        # deliberately never READ as a resume gate: W2-002 requires that an
        # interrupted walk replay its unacknowledged findings, and the
        # allocator plus the ack journal already answer "was this delivered?".
        # Reading the old page_index here would re-introduce the skip.
        identity = None
        acknowledged: set[str] = set()
        committed: set[str] = set()
        # PERF-005: the walk no longer accumulates acknowledged ids into the
        # cursor. Both sources below are read once per walk, not rewritten per
        # page: the allocator (durable truth) and the append-only ack journal
        # (memo for a publication whose receipt has not landed yet).
        for index, total, page, page_identity in self.iter_finding_pages(page_size=size):
            if index == "ERROR":
                yield {
                    "ok": False,
                    "status": page_identity.get("status") or PERMANENT_FAILURE,
                    "error": page_identity.get("error"),
                    "page_index": None,
                }
                return
            if identity is None:
                identity = page_identity
                if expect_source_digest and page_identity["source_digest"] != expect_source_digest:
                    yield {
                        "ok": False,
                        "status": "REPORT_SOURCE_CHANGED",
                        "expected_source_digest": expect_source_digest,
                        "actual_source_digest": page_identity["source_digest"],
                    }
                    return
                committed = self._committed_publication_finding_ids(root)
                ack = self._acknowledged_ids(root, page_identity["source_digest"])
                if not ack["ok"]:
                    yield {
                        "ok": False,
                        "status": ack.get("status") or "ACK_JOURNAL_UNREADABLE",
                        "error": ack.get("error"),
                        "page_index": None,
                    }
                    return
                acknowledged = set(ack["ids"]) | committed
                # A changed corpus used to invalidate the old cursor entirely.
                # PERF-005 keeps that guarantee structurally: ack rows are read
                # scoped to THIS corpus digest, so ids acknowledged under a
                # different report cannot suppress anything here, and the old
                # walk position is simply overwritten below.
            fresh = [
                row
                for row in page
                if str(row.get("finding_id") or "") not in acknowledged
                and str(row.get("state") or "").upper() in ("QUALIFIED", "CONFIRMED")
            ]
            # The cursor tracks the WALK position, never the delivery of these
            # findings: re-yielding them is harmless because publication is
            # idempotent by operation_id, while skipping one is unrecoverable.
            # W2-005: a failed checkpoint write is surfaced, not swallowed --
            # a caller that believes its progress is durable when it is not
            # cannot recover the walk it thinks it can. PERF-005: the cursor now
            # holds only this bounded position, never the delivered id history.
            saved = self.save_page_checkpoint(
                root,
                {
                    "source_digest": identity["source_digest"],
                    "page_index": index,
                    "total_pages": total,
                    "updated_at": _utc_now(),
                },
            )
            if not saved.get("ok"):
                yield {
                    "ok": False,
                    "status": saved.get("status") or "CURSOR_WRITE_FAILED",
                    "error": saved.get("error"),
                    "page_index": index,
                    "page_size": size,
                    "findings": fresh,
                    "persisted": False,
                }
                return
            yield {
                "ok": True,
                "page_index": index,
                "total_pages": total,
                "page_size": size,
                "source_identity": identity,
                "findings": fresh,
                "skipped_already_delivered": len(page) - len(fresh),
            }

    def discover(self, project_root: Path | str | None = None) -> dict:
        """Execute forensic discovery check and classify results."""
        probe_res = self.probe()
        if not probe_res["ok"]:
            return probe_res

        root = Path(project_root).resolve() if project_root else None

        # Check queue: if there are pending sessions, drive actual analysis slice
        status_out = (
            {"ok": True, "data": probe_res["data"]}
            if "data" in probe_res
            else self._run_cmd("status")
        )
        if not status_out["ok"]:
            return status_out
        if status_out["ok"]:
            st_data = status_out["data"]
            queue = st_data.get("queue", {})
            if queue.get("hot", 0) > 0 or queue.get("cold", 0) > 0:
                slice_res = self.start_or_resume()
                if slice_res["ok"]:
                    return {
                        "ok": True,
                        "status": ANALYSIS_PROGRESS,
                        "detail": "SAIPAL analysis slice executed.",
                        "slice": slice_res.get("data"),
                    }
                else:
                    return slice_res

        # AUT-005 (SRC-344): discovery used to call `_run_cmd("report")`,
        # which materialises the ENTIRE corpus before a single row can be
        # classified -- so the bounded incremental transport had no production
        # caller at all. Discovery only acts on qualified findings, which is
        # exactly what `iter_new_qualified_findings` walks: one page resident,
        # deduplicated against the canonical allocator, with no second copy of
        # the corpus in memory.
        qualified: list = []
        source_identity = None
        total_findings = 0
        if root is not None:
            for page in self.iter_new_qualified_findings(root):
                if page.get("ok") is not True:
                    return {
                        "ok": False,
                        "status": page.get("status") or PERMANENT_FAILURE,
                        "error": page.get("error"),
                        "page_index": page.get("page_index"),
                    }
                if source_identity is None:
                    source_identity = page.get("source_identity")
                qualified.extend(page.get("findings") or [])
            total_findings = (source_identity or {}).get("total_findings", 0)
        else:
            # No project root means no cursor or allocator to consult, so this
            # is the read-only informational path. It still walks the validated
            # spool in pages rather than materialising the corpus.
            opened = self._open_report()
            if not opened.get("ok"):
                return opened
            report = opened["report"]
            try:
                source_identity = report.identity
                total_findings = report.total_findings
                for page in report.iter_pages(self.report_page_size(None)):
                    qualified.extend(
                        row
                        for row in page
                        if str(row.get("state", "")).upper() in ("QUALIFIED", "CONFIRMED")
                    )
            except (ValueError, UnicodeError, RecursionError) as exc:
                return {
                    "ok": False,
                    "status": BACKEND_PROTOCOL_ERROR,
                    "error": str(exc),
                }
            finally:
                report.close()

        # Deduplicate unchanged evidence via watermark. Readability is a
        # precondition here rather than a side effect of the walk: an EMPTY
        # corpus yields no page at all, and treating an unreadable durable
        # marker as "no marker" would silently reset dedup to clean.
        if root:
            watermark_file = root / ".saipen" / "campaign" / "saipal_watermark.json"
            last_hash = None
            if watermark_file.is_file():
                try:
                    last_hash = json.loads(watermark_file.read_text(encoding="utf-8")).get(
                        "report_hash"
                    )
                except (OSError, ValueError) as exc:
                    return {
                        "ok": False,
                        "status": ANALYSIS_BLOCKED,
                        "error": f"Discovery watermark is unreadable: {exc}",
                        "path": str(watermark_file),
                    }
            report_hash = (source_identity or {}).get("source_digest") or ""
            if report_hash and last_hash == report_hash and not qualified:
                return {
                    "ok": True,
                    "status": NO_NEW_EVIDENCE,
                    "detail": "No new evidence; unchanged SAIPAL report deduplicated.",
                }
            if report_hash:
                watermark_file.parent.mkdir(parents=True, exist_ok=True)
                paths.safe_atomic_write_bytes(
                    watermark_file,
                    (
                        json.dumps(
                            {"report_hash": report_hash, "updated_at": _utc_now()}, indent=2
                        )
                        + "\n"
                    ).encode("utf-8"),
                    kind="saipal watermark",
                    ownership_root=root,
                )

        if root and qualified:
            delivered_receipts = self.collect_publication_receipts(root)
            if not delivered_receipts["ok"]:
                return delivered_receipts
            delivered_ids = {
                r.get("finding_id") for r in delivered_receipts["records"] if r.get("finding_id")
            }
            new_qualified = [f for f in qualified if f.get("finding_id") not in delivered_ids]
            if not new_qualified:
                return {
                    "ok": True,
                    "status": NO_NEW_EVIDENCE,
                    "detail": "All qualified findings have already been delivered.",
                }
            qualified = new_qualified

        if qualified:
            return {
                "ok": True,
                "status": NEW_QUALIFIED_FINDINGS,
                "findings": qualified,
                "total_findings": total_findings,
            }

        return {
            "ok": True,
            "status": NO_NEW_EVIDENCE,
            "detail": "No qualified findings or new drift detected.",
        }

    def checkpoint(self, project_root: Path | str) -> dict:
        """Save or retrieve forensic scan checkpoint in project state."""
        root = Path(project_root).resolve()
        cp_file = root / ".saipen" / "campaign" / "saipal_checkpoint.json"
        if cp_file.is_file():
            try:
                return json.loads(cp_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def save_checkpoint(self, project_root: Path | str, payload: dict) -> None:
        root = Path(project_root).resolve()
        cp_file = root / ".saipen" / "campaign" / "saipal_checkpoint.json"
        cp_file.parent.mkdir(parents=True, exist_ok=True)
        paths.safe_atomic_write_bytes(
            cp_file,
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            kind="saipal checkpoint",
            ownership_root=root,
        )

    def collect_publication_receipts(self, project_root: Path | str) -> dict:
        """Read publication receipts recorded locally."""
        root = Path(project_root).resolve()
        receipts_file = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        return _read_append_log(receipts_file)

    def get_dispositions(self, project_root: Path | str) -> dict:
        """Read recorded maintainer dispositions."""
        root = Path(project_root).resolve()
        disp_file = root / ".saipen" / "campaign" / "dispositions.jsonl"
        return _read_append_log(disp_file)

    def reconcile_history(self, project_root: Path | str, *, kind: str) -> dict:
        """Repair one damaged append log from authority, or refuse honestly.

        W2-008 requires an explicit repair/reconciliation path, and requires
        that recovery invent nothing. The two logs differ in exactly that
        respect, so they get different answers:

        * ``publication_receipts`` -- authoritative. Every receipt is a
          projection of a canonical ``audit_enqueue`` operation, so a damaged
          suffix can be rebuilt from the allocator for records that are
          COMMITTED and whose layer bytes still hash to the recorded digest.
        * ``dispositions`` -- NOT authoritative. A maintainer decision exists
          only in this log; nothing else in the project records it. Damaged
          bytes are quarantined and the valid prefix is preserved, but no
          missing disposition is ever synthesized.

        W2-001: the whole read-inspect-rebuild-publish transaction runs under
        the history writer lock. Before this, ``LOG_ABSENT`` was decided from an
        unlocked snapshot, so a legitimate append landing between the read and
        the replacement was silently overwritten -- the caller was told
        ``LOG_RECONSTRUCTED`` while a committed receipt was gone.

        The damaged suffix is quarantined byte-for-byte before the live log is
        rewritten, and the live log is replaced atomically with the preserved
        prefix. Callers get the integrity status either way.
        """
        root = Path(project_root).resolve()
        if kind not in ("publication_receipts", "dispositions"):
            return {
                "ok": False,
                "status": "RECONCILE_UNKNOWN_LOG",
                "error": f"Unknown history kind: {kind!r}",
            }
        writer = lock.FileWriterLock(
            root / ".saipen" / "locks" / "saipal-history.lock", root, blocking=False
        )
        deadline = time.monotonic() + _history_lock_timeout()
        while True:
            try:
                writer.acquire()
                break
            except lock.FileLockBusy:
                if time.monotonic() >= deadline:
                    return {
                        "ok": False,
                        "status": "RECONCILE_BUSY",
                        "kind": kind,
                        "error": (
                            "another writer holds the history lock; reconciliation "
                            "refused rather than replacing a moving log"
                        ),
                    }
                time.sleep(_HISTORY_LOCK_RETRY_SLEEP)
        try:
            return self._reconcile_history_locked(root, kind=kind)
        finally:
            with suppress(Exception):
                writer.release()

    def _reconcile_history_locked(self, root: Path, *, kind: str) -> dict:
        """The reconciliation transaction; the caller holds the history lock."""
        if kind == "publication_receipts":
            filename = "saipal_receipts.jsonl"
        else:
            filename = "dispositions.jsonl"

        path = root / ".saipen" / "campaign" / filename
        for attempt in (1, 2):
            history = _read_append_log(path)
            if history["status"] == "LOG_ABSENT":
                # An absent log is a legitimate empty history, EXCEPT when the
                # canonical allocator proves a publication happened. That is
                # precisely the crash-after-enqueue shape: the layer is
                # committed and the receipt append never landed. Rebuilding it
                # is reconstruction from authority, not invention.
                if kind != "publication_receipts":
                    return {
                        "ok": True,
                        "status": "LOG_ABSENT",
                        "kind": kind,
                        "repaired": False,
                        "records": [],
                    }
                doc, allocator_state = audit_enqueue.read_allocator_state(root)
                if allocator_state != audit_enqueue.ALLOCATOR_OK:
                    return {
                        "ok": True,
                        "status": "LOG_ABSENT",
                        "kind": kind,
                        "repaired": False,
                        "records": [],
                    }
                rebuilt_absent: list[dict] = []
                absent_index = _allocator_operation_index(doc)
                for record in doc["operations"].values():
                    if not isinstance(record, dict):
                        continue
                    if str(record.get("producer") or "") != "saipal":
                        continue
                    recovered_one = _receipt_from_allocator(
                        root,
                        {
                            "operation_id": record.get("producer_operation_id"),
                            "finding_id": record.get("producer_item_id"),
                            "layer": record.get("layer"),
                        },
                        snapshot=doc,
                        index=absent_index,
                    )
                    if recovered_one is not None:
                        rebuilt_absent.append(recovered_one)
                if not rebuilt_absent:
                    return {
                        "ok": True,
                        "status": "LOG_ABSENT",
                        "kind": kind,
                        "repaired": False,
                        "records": [],
                    }
                payload = b"".join(
                    (json.dumps(row, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
                    for row in rebuilt_absent
                )
                # The caller already holds the history lock: acquiring it again
                # here would deadlock or, with a re-entrant shim, hide exactly
                # the interleaving this transaction exists to exclude.
                try:
                    paths.prove_owned_dir_chain(
                        path.parent, ownership_root=root, kind="SAIPAL history"
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    paths.safe_atomic_write_bytes(
                        path,
                        payload,
                        kind="SAIPAL reconstructed history",
                        ownership_root=root,
                    )
                except (OSError, ValueError) as exc:
                    return {
                        "ok": False,
                        "status": "RECONCILE_WRITE_FAILED",
                        "kind": kind,
                        "error": str(exc),
                    }
                verified = _read_append_log(path)
                return {
                    "ok": verified["ok"],
                    "status": "LOG_RECONSTRUCTED" if verified["ok"] else "RECONCILE_UNVERIFIED",
                    "kind": kind,
                    "repaired": True,
                    "integrity_before": "LOG_ABSENT",
                    "preserved_records": 0,
                    "recovered_records": len(rebuilt_absent),
                    "records": verified["records"],
                }
            if history["ok"]:
                return {
                    "ok": True,
                    "status": history["status"],
                    "kind": kind,
                    "repaired": False,
                    "records": history["records"],
                }
            if history["status"] not in ("LOG_CORRUPT", "LOG_TRUNCATED"):
                return {**history, "kind": kind, "repaired": False}

            quarantined = _quarantine_damaged_suffix(root, path, history)
            if not quarantined["ok"]:
                return {
                    "ok": False,
                    "status": "RECONCILE_REFUSED",
                    "kind": kind,
                    "integrity": history["status"],
                    "error": quarantined.get("error") or quarantined["status"],
                    "quarantine": quarantined,
                    "records": history["records"],
                }

            prefix_records = list(history["records"])
            recovered: list[dict] = []
            unrecoverable: list[str] = []
            if kind == "publication_receipts":
                seen = {
                    str(r.get("operation_id") or "")
                    for r in prefix_records
                    if r.get("operation_id")
                }
                doc, allocator_state = audit_enqueue.read_allocator_state(root)
                if allocator_state == audit_enqueue.ALLOCATOR_OK:
                    # PERF-003: one snapshot and one index for the whole pass.
                    damaged_index = _allocator_operation_index(doc)
                    for record in doc["operations"].values():
                        if not isinstance(record, dict):
                            continue
                        if str(record.get("producer") or "") != "saipal":
                            continue
                        op_id = str(record.get("producer_operation_id") or "")
                        if not op_id or op_id in seen:
                            continue
                        rebuilt = _receipt_from_allocator(
                            root,
                            {
                                "operation_id": op_id,
                                "finding_id": record.get("producer_item_id"),
                                "layer": record.get("layer"),
                            },
                            snapshot=doc,
                            index=damaged_index,
                        )
                        if rebuilt is None:
                            unrecoverable.append(op_id)
                            continue
                        recovered.append(rebuilt)
                        seen.add(op_id)
                else:
                    unrecoverable.append("*:allocator_unavailable")

            prefix_bytes = b"".join(
                (json.dumps(row, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
                for row in prefix_records + recovered
            )
            try:
                # Lock already held by `reconcile_history`; this write is part of
                # the same transaction as the read above it.
                paths.safe_atomic_write_bytes(
                    path,
                    prefix_bytes,
                    kind="SAIPAL reconciled history",
                    ownership_root=root,
                )
            except (OSError, ValueError) as exc:
                return {
                    "ok": False,
                    "status": "RECONCILE_WRITE_FAILED",
                    "kind": kind,
                    "error": str(exc),
                    "quarantine": quarantined,
                }

            # Re-read rather than assume: the repair is only done when the file
            # now parses completely.
            verified = _read_append_log(path)
            if attempt == 1 and not verified["ok"]:
                continue
            result = {
                "ok": verified["ok"],
                "status": "LOG_RECONCILED" if verified["ok"] else "RECONCILE_UNVERIFIED",
                "kind": kind,
                "repaired": True,
                "integrity_before": history["status"],
                "quarantine": quarantined,
                "preserved_records": len(prefix_records),
                "recovered_records": len(recovered),
                "unrecoverable_operations": sorted(unrecoverable),
                "records": verified["records"],
            }
            if kind == "dispositions":
                result["recovery_note"] = (
                    "Dispositions are not reconstructable from project state; only the "
                    "valid prefix was preserved and no record was invented."
                )
            return result
        return {
            "ok": False,
            "status": "RECONCILE_UNVERIFIED",
            "kind": kind,
            "error": "Repaired log still fails integrity verification",
        }

    def collect_receipts_with_integrity(self, project_root: Path | str) -> dict:
        """Read publication receipts, reporting an unreadable suffix explicitly."""
        return _read_append_log(
            Path(project_root).resolve() / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        )

    def collect_dispositions_with_integrity(self, project_root: Path | str) -> dict:
        """Read dispositions, reporting an unreadable suffix explicitly."""
        return _read_append_log(
            Path(project_root).resolve() / ".saipen" / "campaign" / "dispositions.jsonl"
        )

    def classify_retry(self, error: str) -> str:
        """Classify if an error code or message is retryable."""
        err_lower = str(error).lower()
        if any(term in err_lower for term in ("lock", "busy", "timeout", "rate limit", "429")):
            return RETRYABLE_FAILURE
        return PERMANENT_FAILURE

    def get_next_eligibility(
        self, project_root: Path | str, interval_seconds: float = 300.0
    ) -> dict:
        """Check if periodic discovery is due based on checkpoint."""
        cp = self.checkpoint(project_root)
        last_run = cp.get("last_run_at")
        if not last_run:
            return {"due": True, "seconds_remaining": 0.0}
        try:
            last_dt = _dt.datetime.fromisoformat(last_run.replace("Z", "+00:00"))
            now_dt = _dt.datetime.now(_dt.timezone.utc)
            elapsed = (now_dt - last_dt).total_seconds()
            if elapsed >= interval_seconds:
                return {"due": True, "seconds_remaining": 0.0}
            return {"due": False, "seconds_remaining": round(interval_seconds - elapsed, 1)}
        except Exception:
            return {"due": True, "seconds_remaining": 0.0}

    VALID_DISPOSITIONS = frozenset(
        {
            "NOT_REPRODUCED",
            "DUPLICATE",
            "FALSE_POSITIVE",
            "REJECTED",
            "DEFERRED",
            "BLOCKED",
            "VERIFIED",
            "REPAIRED",
            "RECURRED",
            "REGRESSION_FAILED",
        }
    )

    def deliver_finding_to_audit_inbox(
        self,
        project_root: Path | str,
        finding: dict,
        *,
        publication_authorized: bool = False,
    ) -> dict:
        """Deliver one qualified finding through SAIPEN's canonical audit enqueue API."""
        root = Path(project_root).resolve()
        fid = str(finding.get("finding_id") or "PAL-UNKNOWN")
        state_str = str(finding.get("state") or "").upper()
        if state_str not in ("QUALIFIED", "CONFIRMED"):
            return {
                "ok": False,
                "status": "NOT_QUALIFIED",
                "detail": (
                    f"Finding {fid} has unconfirmed state '{finding.get('state')}'; "
                    "publication refused."
                ),
                "finding_id": fid,
            }

        # Provenance: the qualification receipt must be a real SAIPAL artifact,
        # not a caller-named dictionary. CORE-006 reproduced `DELIVERED_PUBLICATION`
        # from `{"receipt_id": "invented-by-caller"}`: the presence of a key was
        # doing the work of authentication. A dict receipt must therefore name
        # an artifact that exists on disk and whose bytes hash to the digest in
        # the receipt; only a broker-verified field may stand in for that.
        qual_proof = (
            finding.get("qualification_receipt")
            or finding.get("qualification_proof")
            or finding.get("qualification_certificate")
        )
        if not qual_proof:
            return {
                "ok": False,
                "status": "NOT_QUALIFIED",
                "error": (
                    f"Finding {fid} lacks immutable qualification receipt or proof; "
                    "publication refused."
                ),
                "finding_id": fid,
            }

        if isinstance(qual_proof, dict):
            if (
                qual_proof.get("forged")
                or qual_proof.get("valid") is False
                or qual_proof.get("authenticated") is False
            ):
                return {
                    "ok": False,
                    "status": "NOT_QUALIFIED",
                    "error": f"Finding {fid} qualification proof is unauthenticated or forged.",
                    "finding_id": fid,
                }
            # CORE-001: `authenticated is True` plus a string was a fabricated
            # proof, not a verified one. Only a record whose keyed provenance
            # the live broker reproduces may stand in for the artifact route.
            verified_by_broker = (
                qual_proof.get("authenticated") is True
                and isinstance(qual_proof.get("signature") or qual_proof.get("provenance"), str)
                and _broker_verified(qual_proof)
            )
            if (
                qual_proof.get("authenticated") is True
                and not verified_by_broker
            ):
                return {
                    "ok": False,
                    "status": "NOT_QUALIFIED",
                    "error": (
                        f"Finding {fid} claims broker authentication that no live "
                        "authority broker can reproduce; a self-declared "
                        "`authenticated`/`signature` pair is not a proof."
                    ),
                    "finding_id": fid,
                }
            if not verified_by_broker:
                artifact = qual_proof.get("artifact_path") or qual_proof.get("audit_path")
                digest = qual_proof.get("artifact_digest") or qual_proof.get(
                    "qualification_digest"
                )
                if not isinstance(artifact, str) or not artifact.strip():
                    return {
                        "ok": False,
                        "status": "NOT_QUALIFIED",
                        "error": (
                            f"Finding {fid} qualification receipt names no verifiable "
                            "SAIPAL artifact; a caller-supplied receipt id is not proof."
                        ),
                        "finding_id": fid,
                    }
                if not isinstance(digest, str) or not digest.strip():
                    return {
                        "ok": False,
                        "status": "NOT_QUALIFIED",
                        "error": (
                            f"Finding {fid} qualification receipt carries no artifact digest."
                        ),
                        "finding_id": fid,
                    }
                resolved = (root / artifact).resolve()
                try:
                    resolved.relative_to(root)
                except ValueError:
                    return {
                        "ok": False,
                        "status": "NOT_QUALIFIED",
                        "error": f"Finding {fid} qualification artifact escapes the project root.",
                        "finding_id": fid,
                    }
                try:
                    actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
                except OSError as exc:
                    return {
                        "ok": False,
                        "status": "NOT_QUALIFIED",
                        "error": (
                            f"Finding {fid} qualification artifact is not readable: {exc}"
                        ),
                        "finding_id": fid,
                    }
                if actual != digest:
                    return {
                        "ok": False,
                        "status": "NOT_QUALIFIED",
                        "error": (
                            f"Finding {fid} qualification artifact digest does not match "
                            "its receipt."
                        ),
                        "finding_id": fid,
                    }
        elif isinstance(qual_proof, str):
            if any(
                bad in qual_proof.lower()
                for bad in ("forged", "fake", "mock", "unverified", "invalid")
            ):
                return {
                    "ok": False,
                    "status": "NOT_QUALIFIED",
                    "error": f"Finding {fid} qualification proof string is unverified or forged.",
                    "finding_id": fid,
                }
            # A bare receipt id proves nothing on its own: it must name a
            # published receipt in this project's own SAIPAL history.
            known = {
                str(row.get("receipt_id") or row.get("operation_id") or "")
                for row in self.collect_publication_receipts(root).get("records", [])
            }
            if qual_proof not in known:
                return {
                    "ok": False,
                    "status": "NOT_QUALIFIED",
                    "error": (
                        f"Finding {fid} names qualification receipt '{qual_proof}' that this "
                        "project's published history does not contain."
                    ),
                    "finding_id": fid,
                }

        if not publication_authorized:
            return {
                "ok": False,
                "status": STAGED_PUBLICATION,
                "detail": (
                    f"Finding {fid} publication not authorized (STAGE_ONLY). "
                    "Requires explicit grant."
                ),
                "finding_id": fid,
            }

        # Check authentic artifact: original immutable audit markdown body is mandatory
        audit_body = finding.get("audit_body") or finding.get("audit_artifact")
        if not audit_body:
            return {
                "ok": False,
                "status": "ARTIFACT_MISSING",
                "error": (
                    f"Finding {fid} has no original immutable audit artifact; "
                    "reconstruction from summary fields is prohibited."
                ),
                "finding_id": fid,
            }

        expected_digest = finding.get("artifact_digest")
        if not expected_digest:
            return {
                "ok": False,
                "status": "ARTIFACT_DIGEST_MISSING",
                "error": f"Finding {fid} missing required immutable artifact digest.",
                "finding_id": fid,
            }

        actual_digest = hashlib.sha256(audit_body.encode("utf-8")).hexdigest()
        if actual_digest != expected_digest:
            return {
                "ok": False,
                "status": "ARTIFACT_DIGEST_MISMATCH",
                "error": (
                    f"Audit artifact digest mismatch: expected {expected_digest}, "
                    f"got {actual_digest}"
                ),
                "finding_id": fid,
            }

        if not (root / ".saipen").is_dir():
            return {
                "ok": False,
                "status": "DESTINATION_NOT_READY",
                "error": f"Project root {root} has no valid .saipen infrastructure.",
                "finding_id": fid,
            }

        op_id = f"saipal-{fid.lower()}"
        res = audit_enqueue.enqueue(
            root,
            producer="saipal",
            body=audit_body,
            producer_operation_id=op_id,
            producer_item_id=fid,
        )
        if not res.get("ok"):
            return {
                "ok": False,
                "status": PERMANENT_FAILURE,
                "error": res.get("reason", "Enqueue refused"),
                "detail": res,
            }

        receipt = {
            "finding_id": fid,
            "operation_id": op_id,
            "layer": res.get("layer"),
            "digest": res.get("digest"),
            "idempotent": res.get("idempotent", False),
            "delivered_at": _utc_now(),
        }

        # R020/W2-007: receipt identity is the canonically enqueued operation,
        # not this call. A second delivery of the same finding appended a second
        # row with the same operation_id, so "same finding published twice
        # retains one logical receipt" was false and every downstream reader
        # counted two publications. The append now happens only when the
        # operation is genuinely new, and an idempotent enqueue reuses the
        # original row verbatim rather than minting a fresh timestamp.
        # W2-003: uniqueness is decided INSIDE the writer lock. The previous
        # shape looked the receipt up here and appended later, so two identical
        # concurrent deliveries both observed "absent" and both appended -- two
        # rows for one operation while the allocator correctly published one.
        recorded = _append_history_unique(root, "saipal_receipts.jsonl", receipt)
        if recorded["status"] == "HISTORY_CONFLICT":
            existing = recorded.get("existing") or {}
            return {
                "ok": False,
                "status": "PUBLICATION_RECEIPT_CONFLICT",
                "error": (
                    f"Operation {op_id} already has a receipt for a different "
                    "layer digest; refusing to overwrite publication identity."
                ),
                "finding_id": fid,
                "operation_id": op_id,
                "existing_receipt": existing,
            }
        if recorded["status"] == "HISTORY_PRESENT":
            existing = recorded.get("existing") or {}
            return {
                "ok": True,
                "status": DELIVERED_PUBLICATION,
                "finding_id": fid,
                # The stored row keeps its original publication identity and
                # timestamp; only the caller-facing view says that THIS call
                # was a replay of it.
                "receipt": {**existing, "idempotent": True},
                "idempotent_replay": True,
                "original_delivered_at": existing.get("delivered_at"),
            }
        if not recorded["ok"]:
            return {
                **recorded,
                "operation_id": op_id,
                "enqueue_committed": True,
                "receipt_reconciliation_required": True,
            }

        return {
            "ok": True,
            "status": DELIVERED_PUBLICATION,
            "finding_id": fid,
            "receipt": receipt,
        }

    def record_maintainer_disposition(
        self,
        project_root: Path | str,
        finding_id: str,
        *,
        disposition: str,
        task_id: str,
        closure_commit: str = "",
        verification_evidence: str | dict = "",
        source_receipt: str = "",
        notes: str = "",
    ) -> dict:
        """Record a closed-loop maintainer disposition for a finding."""
        root = Path(project_root).resolve()
        disp_upper = str(disposition).upper()
        if disp_upper not in self.VALID_DISPOSITIONS:
            return {
                "ok": False,
                "status": "DISPOSITION_INVALID",
                "error": (
                    f"Disposition '{disposition}' not in valid vocabulary: "
                    f"{sorted(self.VALID_DISPOSITIONS)}"
                ),
            }

        if disp_upper == "VERIFIED":
            if not task_id or not str(task_id).strip():
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": "VERIFIED disposition requires a valid terminal task_id",
                }
            # 1. Verify the EXACT task identity is DONE on board. CORE-004
            # reproduced `DISPOSITION_RECORDED` for a requested `T-20` against a
            # board holding only `- [x] T-200`, because substring membership
            # treats T-20 as a prefix of T-200. The canonical board parser
            # resolves tickets by identity, so use it instead of prose matching.
            board_file = root / ".saipen" / "BOARD.md"
            if not board_file.is_file():
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": f"Cannot verify disposition: {board_file} does not exist",
                }
            from .board import parse_board

            parsed = parse_board(board_file.read_text(encoding="utf-8"))
            ticket = parsed["tickets"].get(str(task_id).strip())
            if ticket is None:
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": (
                        f"Task {task_id} does not exist on board; a substring of a "
                        "different ticket id is not that ticket."
                    ),
                }
            if ticket.get("section") != "## DONE":
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": (
                        f"Task {task_id} sits under {ticket.get('section')}, "
                        "not terminal ## DONE"
                    ),
                }

            # 2. Verification evidence must substantiate repair through a real
            # receipt on disk. CORE-011 reproduced `DISPOSITION_RECORDED` from
            # the free text "ran 12 tests, all green": a phrase about evidence
            # was accepted as evidence. An evidence string must therefore name
            # an existing artifact whose bytes can be hashed, and a dict must
            # carry a path/digest pair or an authenticated broker receipt.
            if not verification_evidence:
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": "VERIFIED disposition requires verifiable verification_evidence",
                }
            if isinstance(verification_evidence, str):
                if (
                    verification_evidence.strip().upper() == "PASS"
                    or any(
                        bad in verification_evidence.lower()
                        for bad in ("assertion", "unverified", "self-asserted")
                    )
                ):
                    return {
                        "ok": False,
                        "status": "DISPOSITION_UNVERIFIED",
                        "error": (
                            "Generic assertion string is not valid verification execution evidence"
                        ),
                    }
                artifact_rel = verification_evidence.strip()
                if not artifact_rel.startswith((".saipen/", ".saipen\\")):
                    return {
                        "ok": False,
                        "status": "DISPOSITION_UNVERIFIED",
                        "error": (
                            "VERIFIED evidence must name a durable receipt under .saipen/; "
                            f"free text '{verification_evidence[:60]}' proves nothing"
                        ),
                    }
                artifact = (root / artifact_rel).resolve()
                try:
                    artifact.relative_to(root)
                except ValueError:
                    return {
                        "ok": False,
                        "status": "DISPOSITION_UNVERIFIED",
                        "error": "Verification artifact escapes the project root",
                    }
                if not artifact.is_file():
                    return {
                        "ok": False,
                        "status": "DISPOSITION_UNVERIFIED",
                        "error": f"Verification artifact '{artifact_rel}' does not exist",
                    }
                # CORE-004: existence of *a* file under .saipen/ is not evidence
                # of a repair. The machine-owned ledgers are claims the engine
                # itself writes -- citing BOARD.md as proof that a ticket's work
                # was verified is citing the assertion under test.
                ledger_names = {"board.md", "state.md", "log.md"}
                if artifact.name.lower() in ledger_names:
                    return {
                        "ok": False,
                        "status": "DISPOSITION_UNVERIFIED",
                        "error": (
                            f"'{artifact_rel}' is a machine-owned ledger, not an "
                            "execution receipt; VERIFIED needs evidence of the "
                            "intended verification"
                        ),
                    }
            elif isinstance(verification_evidence, dict):
                digest = verification_evidence.get("digest") or verification_evidence.get(
                    "sha256"
                )
                path = verification_evidence.get("path") or verification_evidence.get(
                    "record"
                )
                broker_ok = (
                    verification_evidence.get("authenticated") is True
                    and isinstance(verification_evidence.get("signature"), str)
                    and _broker_verified(verification_evidence)
                )
                if (
                    verification_evidence.get("authenticated") is True
                    and not broker_ok
                ):
                    return {
                        "ok": False,
                        "status": "DISPOSITION_UNVERIFIED",
                        "error": (
                            "Verification evidence claims broker authentication that "
                            "no live authority broker can reproduce; CORE-004 "
                            "reproduced DISPOSITION_RECORDED from exactly this shape."
                        ),
                    }
                if not broker_ok:
                    if not isinstance(path, str) or not path.strip():
                        return {
                            "ok": False,
                            "status": "DISPOSITION_UNVERIFIED",
                            "error": "Verification evidence object names no receipt path",
                        }
                    if not isinstance(digest, str) or not digest.strip():
                        return {
                            "ok": False,
                            "status": "DISPOSITION_UNVERIFIED",
                            "error": "Verification evidence object carries no digest",
                        }
                    artifact = (root / path).resolve()
                    try:
                        artifact.relative_to(root)
                    except ValueError:
                        return {
                            "ok": False,
                            "status": "DISPOSITION_UNVERIFIED",
                            "error": "Verification artifact escapes the project root",
                        }
                    try:
                        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
                    except OSError as exc:
                        return {
                            "ok": False,
                            "status": "DISPOSITION_UNVERIFIED",
                            "error": f"Verification artifact is not readable: {exc}",
                        }
                    if actual != digest:
                        return {
                            "ok": False,
                            "status": "DISPOSITION_UNVERIFIED",
                            "error": "Verification artifact digest does not match its receipt",
                        }

            # 3. If closure commit is declared and git repository is present, verify commit exists
            if closure_commit and (root / ".git").exists():
                try:
                    p = subprocess.run(
                        ["git", "-C", str(root), "cat-file", "-t", closure_commit],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                    )
                    if p.returncode != 0 or p.stdout.strip() != "commit":
                        return {
                            "ok": False,
                            "status": "DISPOSITION_UNVERIFIED",
                            "error": (
                                f"Closure commit '{closure_commit}' not found in git repository"
                            ),
                        }
                except OSError as exc:
                    return {
                        "ok": False,
                        "status": "DISPOSITION_UNVERIFIED",
                        "error": f"Could not verify closure commit via git: {exc}",
                    }
        elif disp_upper in ("FALSE_POSITIVE", "NOT_REPRODUCED", "REJECTED", "DUPLICATE"):
            if not notes or not notes.strip():
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": f"{disp_upper} disposition requires explanation in notes",
                }

        record = {
            "finding_id": str(finding_id),
            "task_id": str(task_id),
            "disposition": disp_upper,
            "closure_commit": str(closure_commit),
            "verification_evidence": verification_evidence
            if isinstance(verification_evidence, dict)
            else str(verification_evidence),
            "source_receipt": str(source_receipt),
            "notes": str(notes),
            "recorded_at": _utc_now(),
        }
        recorded = _append_history(root, "dispositions.jsonl", record)
        if not recorded["ok"]:
            return recorded
        return {"ok": True, "status": "DISPOSITION_RECORDED", "disposition": record}

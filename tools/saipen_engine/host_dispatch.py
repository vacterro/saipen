"""Host-scheduler dispatch contract for SAIPEN autonomous iterations (P0 / Block 2).

When an iteration finishes with action AUTO_KICK or an assess_continuation
classification in the executable set:
- Emit a structured host-scheduler dispatch request payload:
  campaign_id: active campaign identifier (from campaign context or fallback)
  goal_binding: current goal path + fingerprint
  project_lineage: project root + repository SHA / lineage identifier
  worker_generation: monotonically increasing generation counter
  iteration_id: current iteration counter
  authority_proof_reference: path or digest of valid continuous_maintenance proof
  idempotency_key: sha256(campaign_id + project_lineage + worker_generation + iteration_id)
  checkpoint_reference: path to verified crash-consistent state snapshot
- If the execution environment provides a registered host-scheduler dispatch hook,
  invoke it synchronously or queue it durably.
- If no native host scheduler is registered, write the dispatch payload to
  .saipen/campaign/dispatch_inbox.jsonl (atomic append) AND
  .saipen/campaign/next_turn.json (atomic write) AND print a structured
  ADVISORY log block so external watchers, human operators, or automation
  scripts can immediately pump the turn.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
import threading
import urllib.request
from collections.abc import Mapping
from pathlib import Path

from . import lock, paths

DEFAULT_CAMPAIGN_ID = "CAMPAIGN-00000000-0000-0000-0000-000000000000"
DISPATCH_SCHEMA_VERSION = 1
ACCEPTANCE_SCHEMA_VERSION = 1

# Closed dispatch lifecycle states
DISPATCH_PENDING = "PENDING"
DISPATCH_CLAIMED = "CLAIMED"
HOST_ACCEPTED = "HOST_ACCEPTED"
TURN_STARTED = "TURN_STARTED"
TURN_COMPLETED = "TURN_COMPLETED"
DISPATCH_ACKNOWLEDGED = "ACKNOWLEDGED"
UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
DISPATCH_REFUSED = "REFUSED"
HOST_DISPATCH_UNAVAILABLE = "HOST_DISPATCH_UNAVAILABLE"
DISPATCH_REQUEST_PERSISTED = "DISPATCH_REQUEST_PERSISTED"
ACCEPTANCE_UNVERIFIED = "ACCEPTANCE_UNVERIFIED"
#: W2-010: the host invocation exceeded its declared deadline. This is an
#: UNCERTAIN outcome, not a refusal: the host may still have accepted the
#: operation, so the operation identity is preserved and reconciliation is
#: required before any retry.
DISPATCH_TIMEOUT = "DISPATCH_TIMEOUT"

#: Declared finite deadline for one external scheduler invocation (W2-010).
#: A host that never returns must not hold dispatch ownership forever.
HOST_INVOCATION_DEADLINE_S = 30.0

# Lock and Ledger classifications
LOCK_BUSY = "LOCK_BUSY"
LOCK_UNAVAILABLE = "LOCK_UNAVAILABLE"
LOCK_CORRUPT = "LOCK_CORRUPT"
LOCK_OWNER_UNKNOWN = "LOCK_OWNER_UNKNOWN"
LEDGER_CORRUPT = "LEDGER_CORRUPT"


class LedgerCorruptError(ValueError):
    """Raised when dispatch ledger is structurally invalid or corrupt."""
    pass


def _acceptance_int(value: object, field: str) -> tuple[int | None, str]:
    """Coerce one numeric receipt field, or name why it is not one.

    AUT-001/H04-H05: `int("not-an-int")` used to escape as an uncaught
    ValueError, so a malformed receipt crashed the dispatcher instead of being
    refused. A receipt field that is not an integer is a typed refusal, and a
    bool is not an integer here even though Python says it is.
    """
    if isinstance(value, bool):
        return None, f"Receipt {field} is a boolean, not an integer: {value!r}"
    if isinstance(value, int):
        return value, ""
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip()), ""
    return None, f"Receipt {field} is not an integer: {value!r}"


def _broker_verified_receipt(receipt: object) -> bool:
    """Is this a record the live authority broker alone could have written?

    AUT-001 asks for independent origin verification rather than a caller
    inventory. The trusted boundary already exists and is already the one
    CORE-001 uses for SAIPAL qualification: `host_authority_client
    .verify_record`. No broker answering means False -- a missing broker is
    never read as "unverified but probably fine".
    """
    from . import host_authority_client

    if not isinstance(receipt, dict):
        return False
    try:
        return bool(host_authority_client.verify_record(receipt))
    except Exception:
        return False


def validate_host_acceptance_receipt(payload: dict, receipt: object) -> tuple[bool, str, str]:
    """Validate host acceptance receipt against typed schema.

    Returns (is_valid, status, error_detail).

    AUT-001: matching caller-supplied fields are NOT authentication. Every
    field this function reads can be written by whoever built `receipt`, so
    field equality alone proves only that one dictionary agrees with another.
    A receipt naming a host that no live authority broker can vouch for is
    therefore refused as ACCEPTANCE_UNVERIFIED, and
    ``DISPATCH_REQUEST_PERSISTED`` never satisfies acceptance: persisting a
    request is the step BEFORE a host accepts it.
    """
    if not isinstance(receipt, dict):
        return False, ACCEPTANCE_UNVERIFIED, f"Receipt is not a dictionary: {type(receipt).__name__}"

    schema_ver = receipt.get("schema_version") or receipt.get("schema")
    if schema_ver != ACCEPTANCE_SCHEMA_VERSION and schema_ver != 1:
        return False, ACCEPTANCE_UNVERIFIED, f"Unsupported receipt schema version: {schema_ver}"

    acc_status = receipt.get("status") or receipt.get("acceptance_status")
    # AUT-001/H03: a persisted request has not been accepted. The dispatch
    # lifecycle separates REQUEST_PERSISTED -> DISPATCH_CLAIMED ->
    # HOST_ACCEPTED -> TURN_STARTED -> TURN_COMPLETED, and a successful local
    # write is the weakest state in that chain, never evidence of its successor.
    if acc_status == DISPATCH_REQUEST_PERSISTED:
        return False, DISPATCH_REQUEST_PERSISTED, (
            "Receipt reports DISPATCH_REQUEST_PERSISTED: the request is durable "
            "but no host has accepted it yet, so it cannot satisfy acceptance"
        )
    if acc_status not in (HOST_ACCEPTED, TURN_STARTED, TURN_COMPLETED):
        return False, ACCEPTANCE_UNVERIFIED, f"Invalid or missing acceptance status: {acc_status}"

    rec_cid = receipt.get("campaign_id")
    if not rec_cid:
        return False, ACCEPTANCE_UNVERIFIED, "Receipt missing campaign_id"
    if str(rec_cid) != str(payload.get("campaign_id")):
        return False, ACCEPTANCE_UNVERIFIED, f"Receipt campaign_id '{rec_cid}' does not match request '{payload.get('campaign_id')}'"

    rec_iter = receipt.get("iteration_id")
    if rec_iter is None:
        return False, ACCEPTANCE_UNVERIFIED, "Receipt missing iteration_id"
    rec_iter_int, iter_err = _acceptance_int(rec_iter, "iteration_id")
    if iter_err:
        return False, ACCEPTANCE_UNVERIFIED, iter_err
    req_iter = payload.get("iteration_id", 0)
    req_iter_int, req_iter_err = _acceptance_int(req_iter, "request iteration_id")
    if req_iter_err:
        return False, ACCEPTANCE_UNVERIFIED, req_iter_err
    if rec_iter_int != req_iter_int:
        return False, ACCEPTANCE_UNVERIFIED, f"Receipt iteration_id '{rec_iter}' does not match request '{req_iter}'"

    rec_gen = receipt.get("worker_generation")
    if rec_gen is None:
        return False, ACCEPTANCE_UNVERIFIED, "Receipt missing worker_generation"
    rec_gen_int, gen_err = _acceptance_int(rec_gen, "worker_generation")
    if gen_err:
        return False, ACCEPTANCE_UNVERIFIED, gen_err
    req_gen = payload.get("worker_generation", 0)
    req_gen_int, req_gen_err = _acceptance_int(req_gen, "request worker_generation")
    if req_gen_err:
        return False, ACCEPTANCE_UNVERIFIED, req_gen_err
    if rec_gen_int != req_gen_int:
        return False, ACCEPTANCE_UNVERIFIED, f"Receipt worker_generation '{rec_gen}' does not match request '{req_gen}'"

    rec_idem = receipt.get("idempotency_key")
    if not rec_idem:
        return False, ACCEPTANCE_UNVERIFIED, "Receipt missing idempotency_key"
    if str(rec_idem) != str(payload.get("idempotency_key")):
        return False, ACCEPTANCE_UNVERIFIED, f"Receipt idempotency_key '{rec_idem}' does not match request '{payload.get('idempotency_key')}'"

    rec_host = receipt.get("accepting_host") or receipt.get("host_id") or receipt.get("host")
    if not rec_host:
        return False, ACCEPTANCE_UNVERIFIED, "Receipt names no accepting host identity"

    # Lineage and request digest are CONTRACT fields, not optional extras. A
    # receipt that omits them cannot prove it accepted THIS request in THIS
    # project; accepting it recorded an unrelated success dictionary as a
    # confirmed dispatch (CORE-004).
    rec_lineage = receipt.get("project_lineage") or receipt.get("lineage")
    expected_lineage = payload.get("project_lineage")
    if not rec_lineage:
        return False, ACCEPTANCE_UNVERIFIED, "Receipt missing project_lineage"
    if expected_lineage and str(rec_lineage) != str(expected_lineage):
        return False, ACCEPTANCE_UNVERIFIED, f"Receipt project_lineage '{rec_lineage}' does not match request '{expected_lineage}'"

    # `accepted_request_digest` is accepted because the contract itself names
    # the field "accepted request digest"; a receipt written to that wording
    # proved a real acceptance and was being refused on a naming difference.
    rec_req = (
        receipt.get("accepted_request_id")
        or receipt.get("request_id")
        or receipt.get("request_digest")
        or receipt.get("accepted_request_digest")
    )
    if not rec_req:
        return False, ACCEPTANCE_UNVERIFIED, "Receipt missing accepted request identity"
    accepted = {
        str(payload.get("idempotency_key") or ""),
        str(payload.get("request_id") or ""),
        str(payload.get("request_digest") or ""),
    }
    if str(rec_req) not in accepted:
        return False, ACCEPTANCE_UNVERIFIED, (
            f"Receipt request identity '{rec_req}' does not match request '{payload.get('idempotency_key')}'"
        )

    # AUT-001/H01-H02: the substring blacklist this replaced could not
    # establish identity -- `invented-host` passed because it contains none of
    # the banned words, while every banned word is trivially avoidable by the
    # same actor that chooses the name. Host identity is now a claim the live
    # authority broker must be able to reproduce, through the same trusted
    # boundary `saipal_adapter._broker_verified` and CORE-001 already use.
    #
    # Ordered LAST on purpose: a structurally deficient receipt is refused for
    # the deficiency, so a caller learns the real defect instead of being told
    # "unauthenticated" about a receipt no broker would ever have written.
    if not _broker_verified_receipt(receipt):
        return False, ACCEPTANCE_UNVERIFIED, (
            f"Accepting host '{rec_host}' is not authenticated: no live authority "
            "broker reproduces this receipt, and matching caller-supplied fields "
            "are not proof of host identity"
        )

    return True, str(acc_status), ""

_DISPATCH_THREAD_LOCK = threading.RLock()
_DISPATCH_THREAD_LOCKS: dict[str, threading.RLock] = {}
_DISPATCH_REGISTRY_LOCK = threading.Lock()


def _get_project_dispatch_lock(root: Path | str) -> threading.RLock:
    key = os.path.normcase(os.path.normpath(str(Path(root).resolve())))
    with _DISPATCH_REGISTRY_LOCK:
        if key not in _DISPATCH_THREAD_LOCKS:
            _DISPATCH_THREAD_LOCKS[key] = threading.RLock()
        return _DISPATCH_THREAD_LOCKS[key]


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_idempotency_key(
    campaign_id: str,
    project_lineage: str,
    worker_generation: int,
    iteration_id: int,
) -> str:
    seed = f"{campaign_id}:{project_lineage}:{worker_generation}:{iteration_id}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


def resolve_project_lineage(root: Path | str) -> str:
    root = Path(root).resolve()
    lineage = paths.project_lineage_identity(root)
    if lineage:
        return lineage
    # Fallback to git sha or deterministic path hash
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return f"git-{res.stdout.strip()[:16]}"
    except OSError:
        pass
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return f"lineage-local-{digest}"


def build_dispatch_payload(
    project_root: Path | str,
    *,
    campaign_id: str | None = None,
    goal_binding: object | None = None,
    worker_generation: int = 1,
    iteration_id: int = 1,
    authority_proof_reference: str | None = None,
    checkpoint_reference: str | None = None,
    action: str = "KICK_NEXT_ITERATION",
    decision: str = "AUTO_KICK",
    extra: Mapping[str, object] | None = None,
) -> dict:
    root = Path(project_root).resolve()
    cid = str(campaign_id or DEFAULT_CAMPAIGN_ID)
    lineage = resolve_project_lineage(root)
    w_gen = int(worker_generation)
    it_id = int(iteration_id)

    if goal_binding is None:
        state_path = root / ".saipen" / "STATE.md"
        goal_binding = {
            "path": str(state_path) if state_path.is_file() else ".saipen/STATE.md",
            "fingerprint": f"intent-goal-{lineage[:8]}",
        }
    elif isinstance(goal_binding, str):
        goal_binding = {"path": goal_binding, "fingerprint": f"goal-{lineage[:8]}"}

    if checkpoint_reference is None:
        cp_path = root / ".saipen" / "cache" / "autonomy-worker.json"
        checkpoint_reference = str(cp_path)

    if authority_proof_reference is None:
        authority_proof_reference = "authority/continuous_maintenance_proof"

    idem_key = compute_idempotency_key(cid, lineage, w_gen, it_id)

    payload = {
        "schema_version": DISPATCH_SCHEMA_VERSION,
        "campaign_id": cid,
        "project_lineage": lineage,
        "project_root": str(root),
        "worker_generation": w_gen,
        "iteration_id": it_id,
        "action": action,
        "decision": decision,
        "goal_binding": goal_binding,
        "authority_proof_reference": authority_proof_reference,
        "checkpoint_reference": checkpoint_reference,
        "idempotency_key": idem_key,
        "created_at": _utc_now(),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def format_advisory_log(payload: dict, inbox_path: Path | str) -> str:
    return (
        "\n[SAIPEN_HOST_DISPATCH_ADVISORY]\n"
        f"action: {payload.get('action', 'KICK_NEXT_ITERATION')}\n"
        f"campaign_id: {payload.get('campaign_id')}\n"
        f"iteration_id: {payload.get('iteration_id')}\n"
        f"worker_generation: {payload.get('worker_generation')}\n"
        f"idempotency_key: {payload.get('idempotency_key')}\n"
        f"inbox_path: {inbox_path}\n"
        "advisory: Native host iteration dispatch not registered; "
        "pump turn via host harness or external watcher.\n"
        "[/SAIPEN_HOST_DISPATCH_ADVISORY]\n"
    )


DISPATCH_LEDGER_JOURNAL = "dispatch_journal.jsonl"
DISPATCH_LEDGER_CHECKPOINT = "dispatch_ledger.json"
DISPATCH_LEDGER_LEGACY = "dispatch_idempotency.json"
#: Byte floor for compaction. There is deliberately no record-count trigger:
#: a fixed count fires at a constant interval no matter how large the ledger
#: has grown, and since each checkpoint rewrites every retained record that
#: makes total write volume quadratic in history (R026). Compaction is driven
#: by `_compaction_threshold`, which scales with the checkpoint it would write.
JOURNAL_COMPACT_BYTES = 256 * 1024
#: Hard ceiling on a single journal record, same idea as history records.
MAX_JOURNAL_RECORD_BYTES = 256 * 1024


def _journal_paths(campaign_dir: Path) -> tuple[Path, Path, Path]:
    return (
        campaign_dir / DISPATCH_LEDGER_JOURNAL,
        campaign_dir / DISPATCH_LEDGER_CHECKPOINT,
        campaign_dir / DISPATCH_LEDGER_LEGACY,
    )


def _read_journal(campaign_dir: Path) -> dict:
    """Read the append journal, reporting a torn tail instead of hiding it.

    R026 requires that "partial journal append is detected". A torn tail is
    the expected shape of a crash mid-append: that transition never
    committed, so its absence is correct -- but the caller must be able to
    see that it happened rather than infer a clean history.
    """
    path = campaign_dir / DISPATCH_LEDGER_JOURNAL
    out = {
        "records": [],
        "bytes": b"",
        "partial_tail": False,
        "partial_tail_bytes": 0,
        "status": "JOURNAL_ABSENT",
    }
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return out
    except OSError as exc:
        raise LedgerCorruptError(f"Dispatch journal storage inaccessible: {exc}")
    out["bytes"] = raw
    out["status"] = "JOURNAL_VALID"
    offset = 0
    for line in raw.splitlines(keepends=True):
        offset += len(line)
        if not line.endswith(b"\n"):
            # Incomplete final append: not a committed transition.
            out["partial_tail"] = True
            out["partial_tail_bytes"] = len(line)
            out["status"] = "JOURNAL_PARTIAL_APPEND"
            break
        if not line.strip():
            continue
        if len(line) > MAX_JOURNAL_RECORD_BYTES:
            raise LedgerCorruptError("Dispatch journal record exceeds the declared size limit")
        try:
            row = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise LedgerCorruptError(f"Dispatch journal contains invalid JSON: {exc}")
        if not isinstance(row, dict) or not isinstance(row.get("key"), str):
            raise LedgerCorruptError("Dispatch journal record is not a keyed transition")
        out["records"].append(row)
    return out


def _read_checkpoint(campaign_dir: Path) -> dict:
    path = campaign_dir / DISPATCH_LEDGER_CHECKPOINT
    empty = {"records": {}, "absorbed_bytes": 0, "absorbed_sha256": "", "generation": 0}
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return empty
    except OSError as exc:
        raise LedgerCorruptError(f"Dispatch ledger storage inaccessible: {exc}")
    if not raw.strip():
        raise LedgerCorruptError("Dispatch ledger file is empty")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise LedgerCorruptError(f"Dispatch ledger contains invalid JSON: {exc}")
    if not isinstance(doc, dict):
        raise LedgerCorruptError("Dispatch ledger is not a dictionary")
    if "records" not in doc:
        # A pre-journal ledger: the whole mapping IS the record set.
        return {**empty, "records": doc, "generation": 0, "legacy_shape": True}
    records = doc.get("records")
    if not isinstance(records, dict):
        raise LedgerCorruptError("Dispatch ledger checkpoint has no record mapping")
    absorbed = doc.get("absorbed_bytes")
    if not isinstance(absorbed, int) or isinstance(absorbed, bool) or absorbed < 0:
        raise LedgerCorruptError("Dispatch ledger checkpoint has an invalid absorbed length")
    digest = doc.get("absorbed_sha256")
    return {
        "records": records,
        "absorbed_bytes": absorbed,
        "absorbed_sha256": digest if isinstance(digest, str) else "",
        "generation": int(doc.get("generation") or 0),
    }


def _migrate_legacy_ledger(
    campaign_dir: Path, journal: dict, known_keys: set[str] | None = None
) -> list[dict]:
    """Explicit one-time migration of the legacy idempotency mirror.

    The old mirror was a bare `{keys: [...]}` file. It is adopted as accepted
    identities, in order, so a retry that predates the journal still resolves
    idempotently (R026: migration preserves old accepted identities). A key the
    checkpoint already holds is NOT re-adopted: the checkpoint knows more about
    it (acceptance timestamp, receipt) than the mirror's bare key ever did.
    """
    path = campaign_dir / DISPATCH_LEDGER_LEGACY
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise LedgerCorruptError(f"Legacy dispatch ledger storage inaccessible: {exc}")
    if not raw.strip():
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise LedgerCorruptError(f"Legacy dispatch idempotency ledger is corrupted: {exc}")
    keys = data if isinstance(data, list) else (data.get("keys") if isinstance(data, dict) else None)
    if not isinstance(keys, list):
        raise LedgerCorruptError("Legacy dispatch idempotency ledger is corrupted")
    known = {str(row.get("key")) for row in journal["records"]}
    known |= set(known_keys or ())
    migrated = []
    for key in keys:
        if not isinstance(key, str) or not key or key in known:
            continue
        migrated.append(
            {
                "key": key,
                "record": {"status": HOST_ACCEPTED, "migrated_from": DISPATCH_LEDGER_LEGACY},
            }
        )
    return migrated


def _apply_journal(records: dict[str, dict], journal: dict, *, start: int = 0) -> dict[str, dict]:
    for row in journal["records"][start:]:
        rec = row.get("record")
        if not isinstance(rec, dict):
            raise LedgerCorruptError("Dispatch journal transition carries no record")
        records[str(row["key"])] = rec
    return records


def _load_dispatch_ledger_with_status(campaign_dir: Path) -> tuple[dict[str, dict], dict]:
    checkpoint = _read_checkpoint(campaign_dir)
    journal = _read_journal(campaign_dir)
    records = dict(checkpoint["records"])
    absorbed = checkpoint["absorbed_bytes"]
    start = 0
    if absorbed and journal["bytes"]:
        prefix = journal["bytes"][:absorbed]
        if (
            checkpoint["absorbed_sha256"]
            and hashlib.sha256(prefix).hexdigest() == checkpoint["absorbed_sha256"]
        ):
            # Only the suffix is new; the checkpoint already holds the prefix.
            consumed = prefix.count(b"\n")
            start = consumed
    _apply_journal(records, journal, start=start)
    migrated = _migrate_legacy_ledger(campaign_dir, journal, set(records))
    for row in migrated:
        records[row["key"]] = row["record"]
    status = {
        "journal_status": journal["status"],
        "journal_records": len(journal["records"]),
        "replayed_from": start,
        "partial_tail": journal["partial_tail"],
        "partial_tail_bytes": journal["partial_tail_bytes"],
        "checkpoint_generation": checkpoint["generation"],
        "migrated_legacy_keys": len(migrated),
    }
    return records, status


def _load_dispatch_ledger(campaign_dir: Path) -> dict[str, dict]:
    records, _status = _load_dispatch_ledger_with_status(campaign_dir)
    return records


def _append_journal_records(
    campaign_dir: Path, transitions: list[dict[str, dict]]
) -> None:
    """Append transitions in one fsynced write; per-operation cost is bounded.

    R026/PERF-003: the old writer serialised the ENTIRE ledger on every
    transition, so a 200-operation history rewrote 12 KB to record one
    acceptance and the cost grew without bound. One durable append makes the
    cost proportional to the transition, not the history.
    """
    if not transitions:
        return
    path = campaign_dir / DISPATCH_LEDGER_JOURNAL
    payload = b"".join(
        (
            json.dumps({"key": key, "record": record}, sort_keys=True, allow_nan=False)
            + "\n"
        ).encode("utf-8")
        for key, record in transitions
    )
    if any(
        len(line) > MAX_JOURNAL_RECORD_BYTES for line in payload.splitlines(keepends=True)
    ):
        raise LedgerCorruptError("Dispatch journal transition exceeds the declared size limit")
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _checkpoint_journal(campaign_dir: Path, records: dict[str, dict], journal: dict) -> bool:
    """Fold the journal into a checkpoint once it grows past its bound.

    The checkpoint records how many leading journal bytes it absorbed and the
    digest of exactly that prefix, so a reader can prove the checkpoint and the
    journal describe the same history instead of double-applying it. The
    journal is truncated only AFTER the checkpoint is durable, so an
    interrupted compaction leaves the original transitions readable.

    Returns ``False`` without writing when the journal is still under the
    threshold, so callers may invoke it unconditionally.
    """
    if len(journal["bytes"]) < _compaction_threshold(
        _journal_stats(campaign_dir)[1]
    ):
        return False
    body = journal["bytes"]
    if journal["partial_tail"]:
        # Keep a torn tail out of the checkpoint: it is not a transition.
        body = body[: len(body) - journal["partial_tail_bytes"]]
    doc = {
        "schema_version": 1,
        "generation": int(journal.get("generation") or 0) + 1,
        "absorbed_bytes": len(body),
        "absorbed_sha256": hashlib.sha256(body).hexdigest(),
        "records": records,
    }
    checkpoint_path = campaign_dir / DISPATCH_LEDGER_CHECKPOINT
    paths.safe_atomic_write_bytes(
        checkpoint_path,
        (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        kind="dispatch ledger checkpoint",
        ownership_root=campaign_dir.parent.parent,
    )
    # Verify the checkpoint before discarding a single journal byte.
    verify = _read_checkpoint(campaign_dir)
    if verify["absorbed_bytes"] != len(body) or verify["records"] != records:
        raise LedgerCorruptError("Dispatch checkpoint failed verification; journal retained")
    journal_path = campaign_dir / DISPATCH_LEDGER_JOURNAL
    paths.safe_atomic_write_bytes(
        journal_path,
        b"",
        kind="dispatch journal",
        ownership_root=campaign_dir.parent.parent,
    )
    # The legacy mirror is derived state; refresh it here, where the cost is
    # already amortised over a whole journal, instead of on every transition.
    _write_legacy_mirror(campaign_dir, records)
    return True


def _save_dispatch_ledger(campaign_dir: Path, ledger: dict[str, dict]) -> None:
    """Persist the full ledger as a checkpoint, keeping the legacy mirror.

    Kept for callers that legitimately rewrite the whole mapping (fixtures,
    recovery, migration). Ordinary transitions go through
    ``_append_journal_records`` and never invoke this.
    """
    _checkpoint_ledger(campaign_dir, ledger)
    _write_legacy_mirror(campaign_dir, ledger)


def _checkpoint_ledger(campaign_dir: Path, ledger: dict[str, dict]) -> None:
    journal = _read_journal(campaign_dir)
    doc = {
        "schema_version": 1,
        "generation": int(_read_checkpoint(campaign_dir).get("generation") or 0) + 1,
        "absorbed_bytes": len(journal["bytes"]),
        "absorbed_sha256": hashlib.sha256(journal["bytes"]).hexdigest(),
        "records": ledger,
    }
    paths.safe_atomic_write_bytes(
        campaign_dir / DISPATCH_LEDGER_CHECKPOINT,
        (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        kind="dispatch ledger",
        ownership_root=campaign_dir.parent.parent,
    )


def _write_legacy_mirror(campaign_dir: Path, ledger: dict[str, dict]) -> None:
    accepted_keys = sorted(
        [
            k
            for k, v in ledger.items()
            if isinstance(v, dict)
            and v.get("status") in (HOST_ACCEPTED, TURN_STARTED, TURN_COMPLETED, DISPATCH_ACKNOWLEDGED)
        ]
    )
    old_body = (json.dumps({"keys": accepted_keys}, indent=2) + "\n").encode("utf-8")
    paths.safe_atomic_write_bytes(
        campaign_dir / DISPATCH_LEDGER_LEGACY,
        old_body,
        kind="dispatch idempotency ledger",
        ownership_root=campaign_dir.parent.parent,
    )


def _journal_stats(campaign_dir: Path) -> tuple[int, int]:
    """`(journal_bytes, checkpoint_bytes)` from stat, without parsing either.

    `_commit_transition` runs on every dispatch, so the compaction decision must
    not read the journal or the checkpoint body. Both sizes are enough: the
    threshold below is derived from them.
    """
    def size(name: str) -> int:
        try:
            return (campaign_dir / name).stat().st_size
        except OSError:
            return 0

    return size(DISPATCH_LEDGER_JOURNAL), size(DISPATCH_LEDGER_CHECKPOINT)


def _compaction_threshold(checkpoint_bytes: int) -> int:
    """When the journal is worth folding into a checkpoint.

    A checkpoint writes every retained record, so compacting on a FIXED journal
    length makes total write volume quadratic in history -- the exact defect
    R026 names, merely moved from every operation to every N operations. The
    threshold therefore scales with the checkpoint it would write, so each
    compaction interval holds proportionally more transitions and the total
    cost stays linear across the whole history.
    """
    return max(JOURNAL_COMPACT_BYTES, checkpoint_bytes)


def _commit_transition(
    campaign_dir: Path,
    ledger: dict[str, dict],
    key: str,
    record: dict,
) -> dict:
    """Durably commit ONE dispatch transition and apply it in place.

    This is the ordinary write path: one fsynced append, so a transition costs
    its own bytes rather than the whole history. The legacy idempotency mirror
    is NOT rewritten here -- it is derived state, so it is refreshed when the
    journal is folded into a checkpoint. Rewriting it per transition was the
    last remaining quadratic term: 1000 operations wrote 72 MB of mirror to
    record 1000 accepted keys.
    """
    ledger[key] = record
    _append_journal_records(campaign_dir, [(key, record)])
    journal_bytes, checkpoint_bytes = _journal_stats(campaign_dir)
    if journal_bytes >= _compaction_threshold(checkpoint_bytes):
        _checkpoint_journal(campaign_dir, ledger, _read_journal(campaign_dir))
    return record


def dispatch_next_turn(
    project_root: Path | str,
    payload: dict,
    *,
    host_hook: callable | None = None,
    print_advisory: bool = True,
) -> dict:
    root = Path(project_root).resolve()
    campaign_dir = root / ".saipen" / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)

    # Check if campaign is cancelled
    camp_state_file = campaign_dir / "state.json"
    if camp_state_file.is_file():
        try:
            cdata = json.loads(camp_state_file.read_text(encoding="utf-8"))
            if isinstance(cdata, dict) and cdata.get("campaign_state") == "CANCELLED":
                return {
                    "ok": False,
                    "dispatched": False,
                    "status": "CAMPAIGN_CANCELLED",
                    "detail": "Campaign is cancelled; dispatch refused",
                    "payload": payload,
                }
        except Exception:
            pass

    # W2-003 / R016: the idempotency key is DERIVED from canonical identity at
    # the dispatch boundary, never trusted from the caller. A caller-supplied
    # key that disagrees with the identity it claims to describe would let a
    # tampered payload reuse -- or collide with -- another operation's
    # exactly-once admission.
    expected_key = compute_idempotency_key(
        str(payload.get("campaign_id") or DEFAULT_CAMPAIGN_ID),
        str(payload.get("project_lineage") or resolve_project_lineage(root)),
        int(payload.get("worker_generation") or 1),
        int(payload.get("iteration_id") or 1),
    )
    supplied_key = payload.get("idempotency_key")
    if supplied_key and str(supplied_key) != expected_key:
        return {
            "ok": False,
            "dispatched": False,
            "status": "IDEMPOTENCY_KEY_MISMATCH",
            "detail": (
                "Caller-supplied idempotency key does not match the canonical "
                "identity of this operation; refusing to dispatch."
            ),
            "expected_idempotency_key": expected_key,
            "supplied_idempotency_key": str(supplied_key),
            "payload": payload,
        }
    idem_key = expected_key
    payload["idempotency_key"] = idem_key

    lock_file = root / ".saipen" / "locks" / "dispatch.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    with _get_project_dispatch_lock(root):
        try:
            dispatch_lock = lock.FileWriterLock(lock_file, root, blocking=False)
            dispatch_lock.acquire()
        except lock.FileLockBusy:
            return {
                "ok": False,
                "dispatched": False,
                "status": LOCK_BUSY,
                "detail": "Dispatch file lock is held by another process",
                "payload": payload,
            }
        except (ValueError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "dispatched": False,
                "status": LOCK_CORRUPT,
                "detail": f"Dispatch lock file is corrupted: {exc}",
                "payload": payload,
            }
        except (PermissionError, OSError) as exc:
            return {
                "ok": False,
                "dispatched": False,
                "status": LOCK_UNAVAILABLE,
                "detail": f"Dispatch file lock could not be accessed: {exc}",
                "payload": payload,
            }
        except Exception as exc:
            return {
                "ok": False,
                "dispatched": False,
                "status": LOCK_OWNER_UNKNOWN,
                "detail": f"Dispatch lock acquisition failed: {exc}",
                "payload": payload,
            }

        try:
            try:
                ledger = _load_dispatch_ledger(campaign_dir)
            except LedgerCorruptError as exc:
                return {
                    "ok": False,
                    "dispatched": False,
                    "status": "LEDGER_CORRUPT",
                    "error": str(exc),
                    "payload": payload,
                }

            record = ledger.get(idem_key)
            replay_persisted = False
            if record and isinstance(record, dict):
                rec_status = record.get("status")
                if rec_status in (HOST_ACCEPTED, TURN_STARTED, TURN_COMPLETED, DISPATCH_ACKNOWLEDGED):
                    return {
                        "ok": True,
                        "dispatched": False,
                        "status": "ALREADY_DISPATCHED",
                        "mode": "idempotent_skip",
                        "payload": payload,
                        "record": record,
                    }
                if rec_status == UNKNOWN_OUTCOME:
                    # W2-010: a timed-out invocation may still have been
                    # accepted by the host, so replaying it blindly could
                    # double-dispatch side effects. Only an explicit
                    # reconciliation clears this.
                    if not payload.get("allow_claim_recovery", False):
                        return {
                            "ok": False,
                            "dispatched": False,
                            "status": "RECOVERY_REQUIRED",
                            "outcome": UNKNOWN_OUTCOME,
                            "reason": record.get("reason") or "HOST_INVOCATION_DEADLINE_EXCEEDED",
                            "detail": (
                                "Prior dispatch outcome is UNCERTAIN after a deadline "
                                "timeout; reconcile the host's actual acceptance "
                                "before retrying. Operation identity is preserved."
                            ),
                            "reconcile_required": True,
                            "idempotency_key": idem_key,
                            "payload": payload,
                        }
                if rec_status == DISPATCH_REQUEST_PERSISTED:
                    # W2-004: a durable request is PENDING, not delivered. A
                    # host registering later must be able to accept it, so the
                    # replay keeps the SAME idempotency identity and moves
                    # REQUEST_PERSISTED -> DELIVERY_CLAIMED -> HOST_ACCEPTED.
                    # Returning a bare ALREADY_PERSISTED stranded the request
                    # forever while reporting success.
                    replay_persisted = True
                if rec_status == DISPATCH_CLAIMED:
                    claimed_at = record.get("claimed_at")
                    if not claimed_at:
                        return {
                            "ok": False,
                            "dispatched": False,
                            "status": "RECOVERY_REQUIRED",
                            "detail": "Claim metadata missing timestamp; recovery required",
                            "payload": payload,
                        }
                    try:
                        c_dt = _dt.datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
                        age = (_dt.datetime.now(_dt.timezone.utc) - c_dt).total_seconds()
                    except Exception:
                        return {
                            "ok": False,
                            "dispatched": False,
                            "status": "RECOVERY_REQUIRED",
                            "detail": "Claim metadata has invalid timestamp; recovery required",
                            "payload": payload,
                        }
                    if record.get("host_accepted") or record.get("acceptance_status") in (HOST_ACCEPTED, TURN_STARTED, TURN_COMPLETED):
                        return {
                            "ok": True,
                            "dispatched": False,
                            "status": "ALREADY_DISPATCHED",
                            "mode": "idempotent_skip",
                            "payload": payload,
                            "record": record,
                        }
                    if age <= 30.0:
                        return {
                            "ok": False,
                            "dispatched": False,
                            "status": "CLAIM_IN_PROGRESS",
                            "detail": f"Dispatch already claimed by concurrent caller (age: {age:.1f}s)",
                            "payload": payload,
                        }
                    if not payload.get("allow_claim_recovery", False):
                        return {
                            "ok": False,
                            "dispatched": False,
                            "status": "RECOVERY_REQUIRED",
                            "detail": f"Prior dispatch claim unconfirmed after {age:.1f}s; explicit recovery required",
                            "payload": payload,
                        }

            # Claim the idempotency key atomically before external side effects
            claim = {
                "status": DISPATCH_CLAIMED,
                "claimed_at": _utc_now(),
                "pid": os.getpid(),
                "campaign_id": payload.get("campaign_id"),
                "iteration_id": payload.get("iteration_id"),
                "worker_generation": payload.get("worker_generation"),
                "project_lineage": payload.get("project_lineage"),
                "request_digest": payload.get("request_digest") or payload.get("request_id"),
            }
            if replay_persisted:
                # The retry keeps the operation identity it was persisted
                # under; only the lifecycle state advances. Losing
                # `persisted_at` would change the publication timestamp of a
                # request that was already durable (W2-004 / R020).
                claim["replayed_from"] = DISPATCH_REQUEST_PERSISTED
                claim["persisted_at"] = record.get("persisted_at")
            _commit_transition(campaign_dir, ledger, idem_key, claim)

            # 1. Native Python callable hook
            if callable(host_hook):
                # W2-010: bound the invocation. A hook that never returns must
                # not hold the dispatch lock forever, and its timeout is an
                # UNCERTAIN outcome -- the host may already have accepted, so
                # the identity is preserved and reconciliation is required
                # rather than a retry that could double-dispatch.
                deadline = float(
                    payload.get("host_deadline_s", HOST_INVOCATION_DEADLINE_S)
                )
                outcome: dict = {}

                def _invoke() -> None:
                    try:
                        outcome["value"] = host_hook(payload)
                    except BaseException as exc:  # noqa: BLE001 - reported below
                        outcome["error"] = exc

                worker = threading.Thread(
                    target=_invoke, name="saipen-host-hook", daemon=True
                )
                worker.start()
                worker.join(deadline)
                if worker.is_alive():
                    # The thread is abandoned, not killed: Python cannot
                    # interrupt it. It must not be allowed to commit an
                    # acceptance after we have reported uncertainty, so the
                    # ledger records UNKNOWN_OUTCOME and a later acceptance
                    # reconciles through the same identity.
                    _commit_transition(campaign_dir, ledger, idem_key, {
                        "status": UNKNOWN_OUTCOME,
                        "reason": "HOST_INVOCATION_DEADLINE_EXCEEDED",
                        "deadline_s": deadline,
                        "claimed_at": claim.get("claimed_at"),
                        "updated_at": _utc_now(),
                    })
                    return {
                        "ok": False,
                        "dispatched": False,
                        "status": DISPATCH_TIMEOUT,
                        "outcome": UNKNOWN_OUTCOME,
                        "deadline_s": deadline,
                        "detail": (
                            f"Host invocation exceeded {deadline:g}s; delivery outcome is "
                            "UNCERTAIN. The operation identity is preserved and "
                            "reconciliation is required before retry."
                        ),
                        "reconcile_required": True,
                        "idempotency_key": idem_key,
                        "payload": payload,
                    }
                if "error" in outcome:
                    exc = outcome["error"]
                    _commit_transition(campaign_dir, ledger, idem_key, {
                        "status": DISPATCH_REFUSED,
                        "error": str(exc),
                        "updated_at": _utc_now(),
                    })
                    return {
                        "ok": False,
                        "dispatched": False,
                        "status": "HOOK_FAILED",
                        "error": str(exc),
                        "payload": payload,
                    }
                hook_result = outcome.get("value")

                # Structured refusal check
                if isinstance(hook_result, dict) and (
                    hook_result.get("ok") is False
                    or hook_result.get("status") in ("REFUSED", "REJECTED", "ERROR")
                    or hook_result.get("accepted") is False
                ):
                    _commit_transition(campaign_dir, ledger, idem_key, {
                        "status": DISPATCH_REFUSED,
                        "result": hook_result,
                        "updated_at": _utc_now(),
                    })
                    return {
                        "ok": False,
                        "dispatched": False,
                        "status": DISPATCH_REFUSED,
                        "error": hook_result.get("error") or "Host hook refused dispatch",
                        "result": hook_result,
                        "payload": payload,
                    }

                # Validate typed acceptance schema
                is_valid, acc_status, val_err = validate_host_acceptance_receipt(payload, hook_result)
                if not is_valid:
                    _commit_transition(campaign_dir, ledger, idem_key, {
                        "status": ACCEPTANCE_UNVERIFIED,
                        "error": val_err,
                        "result": hook_result if isinstance(hook_result, (dict, list, str, int, bool)) else str(hook_result),
                        "updated_at": _utc_now(),
                    })
                    return {
                        "ok": False,
                        "dispatched": False,
                        "status": ACCEPTANCE_UNVERIFIED,
                        "detail": val_err,
                        "result": hook_result,
                        "payload": payload,
                    }

                # Accepted by host hook
                _commit_transition(campaign_dir, ledger, idem_key, {
                    "status": acc_status,
                    "receipt": hook_result if isinstance(hook_result, dict) else {},
                    "accepted_at": _utc_now(),
                })
                return {
                    "ok": True,
                    "dispatched": True,
                    "status": acc_status,
                    "mode": "native_callable",
                    "receipt": hook_result,
                    "payload": payload,
                }

            # 2. Host scheduler dispatch command from env
            cmd = os.environ.get("HOST_SCHEDULER_DISPATCH_CMD")
            if cmd:
                try:
                    argv = shlex.split(cmd) + [json.dumps(payload)]
                    res = subprocess.run(
                        argv,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                    )
                    if res.returncode == 0:
                        out_json = None
                        try:
                            out_json = json.loads(res.stdout)
                        except Exception:
                            pass
                        if isinstance(out_json, dict):
                            is_valid, acc_status, val_err = validate_host_acceptance_receipt(payload, out_json)
                            if is_valid:
                                _commit_transition(campaign_dir, ledger, idem_key, {
                                    "status": acc_status,
                                    "receipt": out_json,
                                    "accepted_at": _utc_now(),
                                })
                                return {
                                    "ok": True,
                                    "dispatched": True,
                                    "status": acc_status,
                                    "mode": "host_command",
                                    "receipt": out_json,
                                    "payload": payload,
                                }
                        # Exit code 0 without valid acceptance schema is ACCEPTANCE_UNVERIFIED
                        _commit_transition(campaign_dir, ledger, idem_key, {
                            "status": ACCEPTANCE_UNVERIFIED,
                            "error": "Process exit 0 without valid acceptance receipt",
                            "updated_at": _utc_now(),
                        })
                        return {
                            "ok": False,
                            "dispatched": False,
                            "status": ACCEPTANCE_UNVERIFIED,
                            "detail": "Host command exited 0 without valid acceptance receipt",
                            "payload": payload,
                        }
                    else:
                        _commit_transition(campaign_dir, ledger, idem_key, {
                            "status": DISPATCH_REFUSED,
                            "returncode": res.returncode,
                            "error": res.stderr or res.stdout,
                            "updated_at": _utc_now(),
                        })
                        return {
                            "ok": False,
                            "dispatched": False,
                            "status": DISPATCH_REFUSED,
                            "error": res.stderr or res.stdout,
                            "payload": payload,
                        }
                except OSError:
                    pass

            # 3. Host dispatch endpoint from env
            endpoint = os.environ.get("HOST_DISPATCH_ENDPOINT")
            if endpoint:
                try:
                    req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        if 200 <= resp.status < 300:
                            body_json = None
                            try:
                                body_json = json.loads(resp.read().decode("utf-8"))
                            except Exception:
                                pass
                            if isinstance(body_json, dict):
                                is_valid, acc_status, val_err = validate_host_acceptance_receipt(payload, body_json)
                                if is_valid:
                                    _commit_transition(campaign_dir, ledger, idem_key, {
                                        "status": acc_status,
                                        "receipt": body_json,
                                        "accepted_at": _utc_now(),
                                    })
                                    return {
                                        "ok": True,
                                        "dispatched": True,
                                        "status": acc_status,
                                        "mode": "host_endpoint",
                                        "receipt": body_json,
                                        "payload": payload,
                                    }
                            _commit_transition(campaign_dir, ledger, idem_key, {
                                "status": ACCEPTANCE_UNVERIFIED,
                                "error": f"HTTP {resp.status} without valid acceptance receipt",
                                "updated_at": _utc_now(),
                            })
                            return {
                                "ok": False,
                                "dispatched": False,
                                "status": ACCEPTANCE_UNVERIFIED,
                                "detail": f"HTTP {resp.status} without valid acceptance receipt",
                                "payload": payload,
                            }
                        else:
                            _commit_transition(campaign_dir, ledger, idem_key, {
                                "status": DISPATCH_REFUSED,
                                "status_code": resp.status,
                                "updated_at": _utc_now(),
                            })
                            return {
                                "ok": False,
                                "dispatched": False,
                                "status": DISPATCH_REFUSED,
                                "status_code": resp.status,
                                "payload": payload,
                            }
                except (OSError, urllib.error.URLError):
                    pass

            # 4. Fallback: durable file write & append + structured ADVISORY log
            inbox_path = campaign_dir / "dispatch_inbox.jsonl"
            if not replay_persisted:
                # W2-004: a replay that still finds no host must not append a
                # second copy of a request that is already durable. The
                # persisted entry keeps its original timestamp and identity.
                with open(inbox_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, sort_keys=True) + "\n")

                next_turn_path = campaign_dir / "next_turn.json"
                body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
                paths.safe_atomic_write_bytes(
                    next_turn_path,
                    body,
                    kind="campaign next turn",
                    ownership_root=root,
                )
            else:
                next_turn_path = campaign_dir / "next_turn.json"

            _commit_transition(
                campaign_dir,
                ledger,
                idem_key,
                {
                    "status": DISPATCH_REQUEST_PERSISTED,
                    "persisted_at": (
                        record.get("persisted_at") if replay_persisted else None
                    )
                    or _utc_now(),
                },
            )

            if print_advisory:
                advisory_text = format_advisory_log(payload, inbox_path)
                sys.stderr.write(advisory_text)
                sys.stderr.flush()

            return {
                "ok": True,
                "dispatched": False,
                "status": HOST_DISPATCH_UNAVAILABLE,
                "mode": "file_advisory",
                "disposition": DISPATCH_REQUEST_PERSISTED,
                "replayed": replay_persisted,
                "inbox_path": str(inbox_path),
                "next_turn_path": str(next_turn_path),
                "payload": payload,
            }
        finally:
            if dispatch_lock is not None:
                try:
                    dispatch_lock.release()
                except Exception:
                    pass

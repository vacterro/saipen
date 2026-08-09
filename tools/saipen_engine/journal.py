"""Write-ahead transaction journal + conflict-safe recovery (NITRO).

The journal is the foundation of every mutating SAIOPS operation. It records,
for each ordered target, its identity, role, the hash of the file BEFORE the
operation and the hash of the exact planned AFTER bytes, and whether that
target has been applied. Recovery is ROLL-FORWARD and CONFLICT-SAFE: it never
overwrites bytes it cannot account for.

Design rules (NITRO integrity sweep):

- Stages are TRUTHFUL and GENERIC. There is no positional
  LOG/BOARD/STATE pseudo-semantics: a target is identified by path + role,
  never by its index in the target list. A MANIFEST is never reported as
  LOG_WRITTEN.
- Every write target carries before_hash and after_hash. Recovery never
  recomputes the intended output from the current state; the journal is the
  evidence of the already-authorized plan.
- Pending-operation preflight is MANDATORY: a new mutation may not begin over
  unresolved old mutation state.
- Post-write verification actually runs before VERIFIED is marked.

Crash injection: NITRO_CRASH_AFTER_PREPARE / _LOG / _BOARD / _STATE / _VERIFIED
exit the process at exactly that point, simulating process death mid-transaction.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import datetime
from pathlib import Path

STATUS = ("PREPARED", "APPLYING", "VERIFIED", "COMMITTED", "ABORTED", "CONFLICT")
TERMINAL = ("COMMITTED", "ABORTED", "CONFLICT")
ROLES = ("log", "board", "state", "manifest", "report", "sweep", "generic")
OPS_DIR = ".saipen/recovery/ops"

_CRASH_MAP = {
    "PREPARED": "NITRO_CRASH_AFTER_PREPARE",
    "log": "NITRO_CRASH_AFTER_LOG",
    "board": "NITRO_CRASH_AFTER_BOARD",
    "state": "NITRO_CRASH_AFTER_STATE",
    "VERIFIED": "NITRO_CRASH_AFTER_VERIFIED",
}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def _hash_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _slug(rel_path: str) -> str:
    return rel_path.replace("/", "__").replace("\\", "__")


def _atomic_json(path: Path, record: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    tmp.replace(path)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(content, str):
        content = content.encode("utf-8")
    tmp.write_bytes(content)
    tmp.replace(path)


def _crash_after(key: str) -> None:
    env = _CRASH_MAP.get(key)
    if env and env in os.environ:
        sys.exit(87)


def pending_ops(project_root: Path | str) -> list[dict]:
    """Every unresolved operation journal, oldest first.

    A pending op is one whose status is not terminal. COMMITTED / ABORTED /
    CONFLICT are settled; PREPARED / APPLYING / VERIFIED are open and must be
    resolved before any new mutation.
    """
    root = Path(project_root)
    ops_dir = root / OPS_DIR
    if not ops_dir.is_dir():
        return []
    found = []
    for entry in sorted(ops_dir.iterdir()):
        if not entry.is_dir():
            continue
        manifest = entry / "operation.json"
        if not manifest.is_file():
            continue
        try:
            record = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            found.append({"op_id": entry.name, "status": "PREPARED",
                          "corrupt": True})
            continue
        if record.get("status") not in TERMINAL:
            found.append({"op_id": record.get("op_id", entry.name),
                          "status": record.get("status", "PREPARED")})
    return found


def recovery_preflight(project_root: Path | str,
                       exclude_op_id: str | None = None) -> dict:
    """Mandatory scan before any new mutation.

    - none pending          -> proceed
    - exactly one pending   -> recover it first
    - recovery hits conflict -> refuse, evidence preserved
    - multiple pending      -> refuse RECOVERY_REQUIRED with the op_ids
    """
    pending = [op for op in pending_ops(project_root)
               if op["op_id"] != exclude_op_id]
    if not pending:
        return {"ok": True, "recovered": []}
    if len(pending) > 1:
        return {"ok": False, "code": "RECOVERY_REQUIRED",
                "op_ids": [op["op_id"] for op in pending],
                "recovery_required": True}
    result = recover(project_root, pending[0]["op_id"])
    if not result["ok"]:
        return result
    return {"ok": True, "recovered": [pending[0]["op_id"]]}


class Journal:
    """Per-operation journal under .saipen/recovery/ops/<op_id>/."""

    def __init__(self, project_root: Path | str, op_id: str) -> None:
        self.project_root = Path(project_root)
        self.dir = self.project_root / OPS_DIR / op_id
        self.op_id = op_id
        self.manifest = self.dir / "operation.json"

    def exists(self) -> bool:
        return self.manifest.is_file()

    def start(self, operation: str, agent: str, project_identity: str,
              semantic_payload_hash: str, targets: list[dict],
              preconditions: dict | None = None) -> None:
        """Write PREPARED: op metadata, per-target before/after hashes, and
        the exact staged final bytes of every target.

        `targets` is a list of dicts: {path, role, content(bytes),
        before_hash, after_hash}. Staged bytes are stored under the journal
        directory so recovery can replay exact intended bytes -- never
        recomputed from the current state.
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        record_targets = []
        for index, target in enumerate(targets):
            content = target["content"]
            if isinstance(content, str):
                content = content.encode("utf-8")
            (self.dir / f"{index}_{_slug(target['path'])}.staged").write_bytes(
                content)
            record_targets.append({
                "path": target["path"],
                "role": target["role"],
                "before_hash": target["before_hash"],
                "after_hash": target["after_hash"],
                "applied": False,
            })
        record = {
            "op_id": self.op_id,
            "operation": operation,
            "created_at": _now(),
            "agent": agent,
            "project_identity": project_identity,
            "semantic_payload_hash": semantic_payload_hash,
            "preconditions": preconditions or {},
            "status": "PREPARED",
            "progress_index": 0,
            "targets": record_targets,
        }
        _atomic_json(self.manifest, record)

    def mark(self, status: str, progress_index: int | None = None,
             target_index: int | None = None) -> None:
        record = self.read()
        record["status"] = status
        if progress_index is not None:
            record["progress_index"] = progress_index
        if target_index is not None and 0 <= target_index < len(
                record["targets"]):
            record["targets"][target_index]["applied"] = True
        _atomic_json(self.manifest, record)

    def read(self) -> dict:
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def staged_content(self, index: int) -> bytes:
        return (self.dir / f"{index}_{_slug(self.read()['targets'][index]['path'])}"
                ".staged").read_bytes()


def _verify_target_bytes(root: Path, targets: list[dict]) -> str | None:
    """Byte-level post-write verification: every written target must now hash
    to its planned after_hash. Returns the first mismatch or None."""
    for target in targets:
        live = _hash_file(root / target["path"])
        if live != target["after_hash"]:
            return (f"target {target['path']}: live {live!r} != planned "
                    f"after {target['after_hash']!r}")
    return None


def run_mutation(project_root: Path | str, op_id: str, operation: str,
                 agent: str, project_identity: str,
                 semantic_payload_hash: str,
                 targets: list[dict],
                 preconditions: dict | None = None,
                 verify: object | None = None,
                 skip_preflight: bool = False) -> dict:
    """Commit an ordered, journaled mutation with conflict-safe recovery.

    `targets` is an ordered list of {"path", "role", "content"} where path is
    relative to the project root. before_hash/after_hash are computed here from
    the live file and the staged content, and stored in the journal. The
    `preconditions` dict maps path -> expected live hash for every file the
    operation read (write targets and read-only dependencies alike).

    `verify` is an optional callable(project_root) -> list[str] of cross-file
    invariant errors. When provided it runs AFTER all targets are written and
    before VERIFIED is marked; a failure leaves the journal CONFLICT with
    evidence preserved.
    """
    root = Path(project_root)
    journal = Journal(root, op_id)
    if journal.exists():
        record = journal.read()
        if record["status"] == "COMMITTED":
            return {"ok": True, "code": "ALREADY_APPLIED", "op_id": op_id,
                    "recovery_required": False}
        return {"ok": False, "code": "RECOVERY_REQUIRED", "op_id": op_id,
                "recovery_required": True,
                "detail": f"op {op_id} is already {record['status']}; "
                          "recover it first"}

    if not skip_preflight:
        preflight = recovery_preflight(root, exclude_op_id=op_id)
        if not preflight["ok"]:
            return preflight

    # Compute per-target before/after hashes from live files + staged bytes.
    prepared = []
    for index, target in enumerate(targets):
        path = target["path"]
        role = target.get("role", "generic")
        if role not in ROLES:
            return {"ok": False, "code": "VALIDATION_FAILED", "op_id": op_id,
                    "detail": f"target {path}: role {role!r} outside "
                              f"{'/'.join(ROLES)}"}
        content = target["content"]
        if isinstance(content, str):
            content = content.encode("utf-8")
        before = _hash_file(root / path)
        prepared.append({"path": path, "role": role, "content": content,
                         "before_hash": before,
                         "after_hash": hash_bytes(content)})

    # Every file the operation depends on (write targets + read-only deps)
    # must match the preconditions captured at plan time.
    for path, expected in (preconditions or {}).items():
        actual = _hash_file(root / path)
        if actual != expected:
            return {"ok": False, "code": "STALE_STATE", "op_id": op_id,
                    "detail": f"precondition {path} changed (live {actual!r}, "
                              f"expected {expected!r})"}

    journal.start(operation, agent, project_identity, semantic_payload_hash,
                  prepared, preconditions)
    _crash_after("PREPARED")

    journal.mark("APPLYING")
    for index, target in enumerate(prepared):
        _atomic_write(root / target["path"], target["content"])
        journal.mark("APPLYING", progress_index=index + 1, target_index=index)
        _crash_after(target["role"])

    byte_error = _verify_target_bytes(root, prepared)
    if byte_error:
        journal.mark("CONFLICT")
        return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                "recovery_required": True,
                "detail": f"post-write byte verification failed: {byte_error}"}

    if verify is not None:
        errors = verify(root)
        if errors:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": "post-write cross-file validation failed: "
                              + "; ".join(errors[:5])}
    _crash_after("VERIFIED")

    journal.mark("VERIFIED")
    journal.mark("COMMITTED")
    return {"ok": True, "code": "COMMITTED", "op_id": op_id,
            "changed_files": [t["path"] for t in prepared],
            "recovery_required": False}


def recover(project_root: Path | str, op_id: str) -> dict:
    """Roll-forward, conflict-safe recovery.

    Per unfinished target:
      current == before_hash -> apply the staged planned bytes
      current == after_hash  -> already applied; advance
      anything else          -> CONFLICT: preserve journal + staged bytes,
                                write nothing further, refuse to guess.

    Per already-applied target the live bytes MUST equal after_hash, or the
    applied work was overwritten: CONFLICT. Repeated recovery is idempotent.
    """
    root = Path(project_root)
    journal = Journal(root, op_id)
    if not journal.exists():
        return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
    record = journal.read()
    status = record["status"]
    if status == "COMMITTED":
        return {"ok": True, "code": "ALREADY_APPLIED", "op_id": op_id}
    if status in ("ABORTED", "CONFLICT"):
        return {"ok": False, "code": status, "op_id": op_id,
                "recovery_required": True,
                "detail": f"op is {status}; resolve explicitly before "
                          "further mutation"}

    targets = record["targets"]
    # PREPARED with nothing applied: no canonical byte changed -> abort safely.
    if status == "PREPARED" and not any(t["applied"] for t in targets):
        journal.mark("ABORTED")
        return {"ok": True, "code": "ABORTED", "op_id": op_id}

    for index, target in enumerate(targets):
        live = _hash_file(root / target["path"])
        if target["applied"]:
            if live != target["after_hash"]:
                journal.mark("CONFLICT")
                return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                        "recovery_required": True,
                        "detail": f"applied target {target['path']} was "
                                  f"overwritten: live {live!r} != planned "
                                  f"after {target['after_hash']!r}"}
            continue
        if live == target["before_hash"]:
            staged = journal.staged_content(index)
            if hash_bytes(staged) != target["after_hash"]:
                journal.mark("CONFLICT")
                return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                        "recovery_required": True,
                        "detail": f"staged bytes for {target['path']} hash to "
                                  f"{hash_bytes(staged)!r}, not the planned "
                                  f"after {target['after_hash']!r}; the "
                                  "journal evidence is corrupt, refuse to "
                                  "guess"}
            _atomic_write(root / target["path"], staged)
            journal.mark("APPLYING", progress_index=index + 1,
                         target_index=index)
        elif live == target["after_hash"]:
            journal.mark("APPLYING", progress_index=index + 1,
                         target_index=index)
        else:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": f"unfinished target {target['path']} has "
                              f"unexpected bytes (live {live!r}; before "
                              f"{target['before_hash']!r}, after "
                              f"{target['after_hash']!r}); refuse to guess"}

    journal.mark("VERIFIED")
    journal.mark("COMMITTED")
    return {"ok": True, "code": "COMMITTED", "op_id": op_id,
            "changed_files": [t["path"] for t in targets],
            "recovery_required": True}


def auto_recover_pending(project_root: Path | str) -> dict:
    """Recover every pending op in order; stop at the first conflict.

    Used by `saipen recover` (no explicit op_id). A conflict stops the run
    with the conflicting op named and its evidence preserved.
    """
    pending = pending_ops(project_root)
    if not pending:
        return {"ok": True, "code": "CLEAN", "recovered": []}
    recovered = []
    for op in pending:
        result = recover(project_root, op["op_id"])
        if not result["ok"]:
            result["pending_op_ids"] = [p["op_id"]
                                        for p in pending_ops(project_root)]
            return result
        recovered.append(op["op_id"])
    return {"ok": True, "code": "RECOVERED", "recovered": recovered,
            "recovery_required": False}

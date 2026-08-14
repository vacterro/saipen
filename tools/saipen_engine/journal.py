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

import contextlib
import hashlib
import json
import os
import re
import sys
import datetime
from pathlib import Path

STATUS = ("PREPARED", "APPLYING", "VERIFIED", "COMMITTED", "ABORTED",
          "CONFLICT", "RESOLVED")
# SETTLED: no further mutation work needed; recovery may not act. RESOLVED is
# a conflict that was explicitly settled (accept-live or replan) with its
# partial-application evidence preserved -- distinct from ABORTED, which would
# falsely imply nothing happened when the op already appended LOG (NITRO
# dogfood III, T-594).
SETTLED = ("COMMITTED", "ABORTED", "RESOLVED")
# UNRESOLVED: the operation still owns mutation state. CONFLICT is stable
# evidence but NOT permission to continue -- a conflict must be resolved
# explicitly before any new canonical mutation (NITRO dogfood II, T-587).
UNRESOLVED = ("PREPARED", "APPLYING", "VERIFIED", "CONFLICT")
ROLES = ("log", "board", "state", "manifest", "report", "sweep", "generic")
OPS_DIR = ".saipen/recovery/ops"

# Closed verification-policy registry. Recovery must run the SAME semantic
# postcondition class as the original APPLY; a policy names the verifier
# WITHOUT serializing Python callables (NITRO dogfood II, T-587).
VERIFICATION_POLICIES = frozenset({
    "core_fast",
    "improve_atomic_file",
    "userperson",
    "sub_collect",
    "sub_lifecycle",
    "sub_clean",
    "sub_sync",
    "none",
})

SOURCE_IDENTITY_PREFIX = "source-identity-v1:"
MISSING_TREE_DEPENDENCY = "tree-missing-v1"
MISSING_FILE_DEPENDENCY = "file-missing-v1"

_CRASH_MAP = {
    "PREPARED": "NITRO_CRASH_AFTER_PREPARE",
    "log": "NITRO_CRASH_AFTER_LOG",
    "board": "NITRO_CRASH_AFTER_BOARD",
    "state": "NITRO_CRASH_AFTER_STATE",
    "VERIFIED": "NITRO_CRASH_AFTER_VERIFIED",
    "delete_file": "NITRO_CRASH_AFTER_DELETE_FILE",
    "delete_dir": "NITRO_CRASH_AFTER_DELETE_DIR",
}

TARGET_ACTIONS = ("write", "delete_file", "delete_dir")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def hash_file_dependency(path: Path | str) -> str:
    """Safe exact regular-file token for read-only CAS dependencies."""
    candidate = Path(path)
    try:
        info = candidate.lstat()
    except FileNotFoundError:
        return MISSING_FILE_DEPENDENCY
    except OSError:
        return "object-unreadable"
    attributes = getattr(info, "st_file_attributes", 0)
    if candidate.is_symlink() or attributes & 0x400 or not candidate.is_file():
        return f"object:{info.st_mode}"
    try:
        return hash_bytes(candidate.read_bytes())
    except OSError:
        return "object-unreadable"


def _hash_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _hash_tree(path: Path) -> str:
    """Hash a read-only directory dependency: relative names + exact bytes."""
    if not path.is_dir():
        return ""
    digest = hashlib.sha256()
    try:
        files = sorted(candidate for candidate in path.rglob("*")
                       if candidate.is_file())
        for candidate in files:
            rel = candidate.relative_to(path).as_posix().encode("utf-8")
            raw = candidate.read_bytes()
            digest.update(len(rel).to_bytes(8, "big"))
            digest.update(rel)
            digest.update(len(raw).to_bytes(8, "big"))
            digest.update(raw)
    except OSError:
        return ""
    return "tree-sha256:" + digest.hexdigest()


def hash_tree(path: Path | str) -> str:
    """Public plan-time digest for a directory read dependency."""
    return _hash_tree(Path(path))


def _hash_delete_tree(path: Path) -> str:
    """Exact deterministic hash for a directory deletion target."""
    try:
        root_info = path.lstat()
    except FileNotFoundError:
        return ""
    except OSError:
        return "object-unreadable"
    attributes = getattr(root_info, "st_file_attributes", 0)
    if path.is_symlink() or attributes & 0x400 or not path.is_dir():
        return f"object:{root_info.st_mode}"
    digest = hashlib.sha256(b"saipen-delete-tree-v1\0")
    try:
        for current, directories, names in os.walk(path, followlinks=False):
            directories.sort()
            names.sort()
            current_path = Path(current)
            rel_dir = current_path.relative_to(path).as_posix().encode("utf-8")
            digest.update(b"D" + len(rel_dir).to_bytes(8, "big") + rel_dir)
            for directory in directories:
                candidate = current_path / directory
                info = candidate.lstat()
                attrs = getattr(info, "st_file_attributes", 0)
                if candidate.is_symlink() or attrs & 0x400:
                    rel = candidate.relative_to(path).as_posix()
                    return f"object-reparse:{rel}"
            for name in names:
                candidate = current_path / name
                info = candidate.lstat()
                attrs = getattr(info, "st_file_attributes", 0)
                if candidate.is_symlink() or attrs & 0x400 \
                        or not candidate.is_file():
                    rel = candidate.relative_to(path).as_posix()
                    return f"object-unsupported:{rel}"
                rel = candidate.relative_to(path).as_posix().encode("utf-8")
                raw = candidate.read_bytes()
                digest.update(b"F" + len(rel).to_bytes(8, "big") + rel)
                digest.update(len(raw).to_bytes(8, "big") + raw)
    except OSError:
        return "object-unreadable"
    return "delete-tree-sha256:" + digest.hexdigest()


def hash_delete_tree(path: Path | str) -> str:
    """Public exact tree digest used by deletion plans and CAS checks."""
    return _hash_delete_tree(Path(path))


def hash_tree_dependency(path: Path | str) -> str:
    """Safe exact directory token for read-only CAS dependencies.

    Unlike ``hash_tree``, this never follows a symlink/reparse point and it
    distinguishes a missing directory from an unreadable/unsupported object.
    """
    candidate = Path(path)
    digest = _hash_delete_tree(candidate)
    if not digest and not os.path.lexists(candidate):
        return MISSING_TREE_DEPENDENCY
    return digest


def empty_delete_tree_hash() -> str:
    """Exact hash of an empty directory immediately before `rmdir`."""
    digest = hashlib.sha256(b"saipen-delete-tree-v1\0")
    digest.update(b"D" + (1).to_bytes(8, "big") + b".")
    return "delete-tree-sha256:" + digest.hexdigest()


def _target_action(target: dict) -> str:
    return target.get("action", "write")


def _target_live_hash(root: Path, target: dict) -> str:
    action = _target_action(target)
    path = root / target["path"]
    if action == "delete_dir":
        return _hash_delete_tree(path)
    if action == "delete_file":
        try:
            info = path.lstat()
        except FileNotFoundError:
            return ""
        except OSError:
            return "object-unreadable"
        attributes = getattr(info, "st_file_attributes", 0)
        if path.is_symlink() or attributes & 0x400 or not path.is_file():
            return f"object:{info.st_mode}"
    return _hash_file(path)


def hash_source_identity(project_root: Path | str) -> str:
    """Stable read-dependency token for canonical source identity."""
    from freshness import compute_source_identity
    return source_identity_dependency(compute_source_identity(
        Path(project_root)))


def source_identity_dependency(source) -> str:
    """Frame an already-sampled SourceIdentity as a journal CAS token."""
    framed = (source.source_head + "\0" +
              source.source_tree_fingerprint).encode("utf-8")
    return SOURCE_IDENTITY_PREFIX + hashlib.sha256(framed).hexdigest()


def _hash_dependency(path: Path, expected: str) -> str:
    if expected.startswith(SOURCE_IDENTITY_PREFIX):
        try:
            return hash_source_identity(path)
        except Exception:
            return ""
    if expected == MISSING_TREE_DEPENDENCY:
        return hash_tree_dependency(path)
    if expected == MISSING_FILE_DEPENDENCY:
        return hash_file_dependency(path)
    if expected.startswith("delete-tree-sha256:"):
        return _hash_delete_tree(path)
    if expected.startswith("tree-sha256:"):
        return _hash_tree(path)
    # Preserve legacy empty-file expectations; every nonempty current plan
    # uses the safe lstat-based token and cannot accept a symlink substitution
    # merely because its target happens to carry the same bytes.
    return _hash_file(path) if not expected else hash_file_dependency(path)


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
    """Every UNRESOLVED operation journal, oldest first.

    PREPARED / APPLYING / VERIFIED / CONFLICT are all unresolved: they own
    mutation state that must be resolved before any new mutation. CONFLICT is
    excluded from SETTLED deliberately -- a conflict is evidence a mutation
    must stop at, not a permission to continue (NITRO dogfood II, T-587).
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
        if record.get("status") not in SETTLED:
            found.append({"op_id": record.get("op_id", entry.name),
                          "status": record.get("status", "PREPARED")})
    return found


def pending_conflicts(project_root: Path | str) -> list[dict]:
    """Every CONFLICT journal -- stable evidence that still blocks mutation."""
    return [op for op in pending_ops(project_root)
            if op.get("status") == "CONFLICT"]


def recovery_preflight(project_root: Path | str,
                       exclude_op_id: str | None = None) -> dict:
    """Mandatory scan before any new mutation.

    - an unresolved CONFLICT exists -> REFUSE RECOVERY_CONFLICT, evidence
      preserved, exact op named (a conflict must be resolved explicitly).
    - none pending                 -> proceed
    - exactly one pending          -> recover it first
    - recovery hits conflict       -> refuse, evidence preserved
    - multiple pending             -> refuse RECOVERY_REQUIRED with op_ids
    """
    conflicts = [op for op in pending_conflicts(project_root)
                 if op["op_id"] != exclude_op_id]
    if conflicts:
        return {"ok": False, "code": "RECOVERY_CONFLICT",
                "op_ids": [op["op_id"] for op in conflicts],
                "recovery_required": True,
                "detail": f"unresolved conflict {conflicts[0]['op_id']} "
                          "blocks new mutation; resolve it explicitly (saipen "
                          "recover) before any further canonical write"}
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
              preconditions: dict | None = None,
              verification_policy: str = "none",
              read_preconditions: dict | None = None,
              receipt_metadata: dict | None = None) -> None:
        """Write PREPARED: op metadata, per-target before/after hashes, and
        the exact staged final bytes of every target.

        `targets` contains path, role, action, before_hash, and after_hash.
        Write actions also carry exact content bytes staged under the journal.
        Old receipts without action remain writes.

        `verification_policy` names the semantic verifier class recovery must
        rerun before VERIFIED (closed registry, never a serialized callable).
        `read_preconditions` are READ-ONLY dependencies: files the plan read
        but did not write. Recovery must recheck them against the plan's
        allowed state before roll-forward, so an intervening edit to a read
        dependency cannot be silently committed over (NITRO dogfood II).
        """
        if verification_policy not in VERIFICATION_POLICIES:
            raise ValueError(
                f"verification_policy {verification_policy!r} outside "
                f"{sorted(VERIFICATION_POLICIES)}")
        self.dir.mkdir(parents=True, exist_ok=True)
        record_targets = []
        for index, target in enumerate(targets):
            action = _target_action(target)
            if action == "write":
                content = target["content"]
                if isinstance(content, str):
                    content = content.encode("utf-8")
                (self.dir / f"{index}_{_slug(target['path'])}.staged").write_bytes(
                    content)
            record_targets.append({
                "path": target["path"],
                "role": target["role"],
                "action": action,
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
            "read_preconditions": read_preconditions or {},
            "verification_policy": verification_policy,
            "status": "PREPARED",
            "progress_index": 0,
            "targets": record_targets,
        }
        if receipt_metadata is not None:
            record["receipt_metadata"] = receipt_metadata
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

    def append_targets(self, targets: list[dict]) -> None:
        """Append write targets to an existing operation (T-994 release).

        A release operation learns its canonical closure bytes only after its
        content commit exists (the RUN event names the pushed commit), so the
        journal must be able to grow: the appended targets are staged exactly
        like the initial ones and recovery replays them by the same rules.
        The record's progress_index stays put; appended targets start
        unapplied.
        """
        record = self.read()
        record_targets = record.setdefault("targets", [])
        for target in targets:
            index = len(record_targets)
            action = _target_action(target)
            if action == "write":
                content = target["content"]
                if isinstance(content, str):
                    content = content.encode("utf-8")
                (self.dir / f"{index}_{_slug(target['path'])}.staged").write_bytes(
                    content)
            record_targets.append({
                "path": target["path"],
                "role": target["role"],
                "action": action,
                "before_hash": target["before_hash"],
                "after_hash": target["after_hash"],
                "applied": False,
            })
        _atomic_json(self.manifest, record)

    def update(self, **fields) -> None:
        """Merge extra fields into the operation record (T-994 release).

        Release operations record git facts (commits, remote tips, trees)
        that the generic byte-replay model does not own; they live alongside
        the standard status/targets keys in the SAME atomic journal write.
        """
        record = self.read()
        record.update(fields)
        _atomic_json(self.manifest, record)

    def read(self) -> dict:
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def staged_content(self, index: int) -> bytes:
        return (self.dir / f"{index}_{_slug(self.read()['targets'][index]['path'])}"
                ".staged").read_bytes()


def _verify_target_bytes(root: Path, targets: list[dict]) -> str | None:
    """Verify every target reached its planned bytes or absence."""
    for target in targets:
        live = _target_live_hash(root, target)
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
                  skip_preflight: bool = False,
                  verification_policy: str = "none",
                  read_preconditions: dict | None = None,
                  receipt_metadata: dict | None = None) -> dict:
    """Commit an ordered, journaled mutation with conflict-safe recovery.

    Targets are ordered `write`, `delete_file`, or `delete_dir` actions.
    Missing action remains `write` for compatibility. The
    `preconditions` dict maps path -> expected live hash for every WRITE target.

    `read_preconditions` maps path -> expected live hash for READ-ONLY
    dependencies (files the plan read but did not write). They are journaled
    so recovery can recheck them before roll-forward.

    `verification_policy` names the closed semantic-verifier class recovery
    must rerun before VERIFIED (never a serialized callable). `verify` is the
    live callable for THIS apply; the policy is what survives in the journal.
    """
    root = Path(project_root)
    journal = Journal(root, op_id)

    def dependency_path(path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else root / candidate
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

    # Compute truthful per-action before/after states.
    prepared = []
    for index, target in enumerate(targets):
        path = target["path"]
        role = target.get("role", "generic")
        if role not in ROLES:
            return {"ok": False, "code": "VALIDATION_FAILED", "op_id": op_id,
                    "detail": f"target {path}: role {role!r} outside "
                              f"{'/'.join(ROLES)}"}
        action = target.get("action", "write")
        if action not in TARGET_ACTIONS:
            return {"ok": False, "code": "VALIDATION_FAILED", "op_id": op_id,
                    "detail": f"target {path}: action {action!r} outside "
                              f"{'/'.join(TARGET_ACTIONS)}"}
        probe = {"path": path, "action": action}
        if action == "write":
            content = target["content"]
            if isinstance(content, str):
                content = content.encode("utf-8")
            prepared.append({"path": path, "role": role, "action": action,
                             "content": content,
                             "before_hash": _target_live_hash(root, probe),
                             "after_hash": hash_bytes(content)})
        else:
            before = (target.get("planned_before_hash")
                      if action == "delete_dir"
                      else _target_live_hash(root, probe))
            prepared.append({"path": path, "role": role, "action": action,
                             "before_hash": before, "after_hash": ""})

    # Every WRITE target and every read-only dependency must match the
    # hashes captured at plan time.
    prepared_by_path = {target["path"]: target for target in prepared}
    for path, expected in (preconditions or {}).items():
        target = prepared_by_path.get(path)
        # OperationPlan keeps write and read dependencies in one immutable
        # precondition map. Non-targets may be file, tree, or source-identity
        # tokens; treating every one as a write/file makes valid tree CAS
        # fail as an empty file hash before the read-only pass can check it.
        actual = (_target_live_hash(root, target) if target is not None else
                  _hash_dependency(dependency_path(path), expected))
        if actual != expected:
            return {"ok": False, "code": "STALE_STATE", "op_id": op_id,
                    "detail": f"precondition {path} changed (live {actual!r}, "
                              f"expected {expected!r})"}
    for path, expected in (read_preconditions or {}).items():
        actual = _hash_dependency(dependency_path(path), expected)
        if actual != expected:
            return {"ok": False, "code": "STALE_STATE", "op_id": op_id,
                    "detail": f"read dependency {path} changed (live "
                              f"{actual!r}, expected {expected!r})"}

    journal.start(operation, agent, project_identity, semantic_payload_hash,
                   prepared, preconditions,
                   verification_policy=verification_policy,
                   read_preconditions=read_preconditions,
                   receipt_metadata=receipt_metadata)
    _crash_after("PREPARED")

    journal.mark("APPLYING")
    for index, target in enumerate(prepared):
        live = _target_live_hash(root, target)
        action = _target_action(target)
        if live == target["after_hash"]:
            journal.mark("APPLYING", progress_index=index + 1,
                         target_index=index)
            # A semantic commit boundary still exists when this target was
            # already at its planned value. Crash probes model interruption
            # after roles (LOG/BOARD/STATE), not only after changed bytes.
            _crash_after(target["role"] if action == "write" else action)
            continue
        if live != target["before_hash"]:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": f"target {target['path']} has third state "
                              f"{live!r}; before {target['before_hash']!r}, "
                              f"after {target['after_hash']!r}"}
        try:
            if action == "write":
                _atomic_write(root / target["path"], target["content"])
            elif action == "delete_file":
                (root / target["path"]).unlink()
            else:
                (root / target["path"]).rmdir()
        except OSError as exc:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": f"target {target['path']} action failed: {exc}"}
        after = _target_live_hash(root, target)
        if after != target["after_hash"]:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": f"target {target['path']} action left {after!r}, "
                              f"expected {target['after_hash']!r}"}
        journal.mark("APPLYING", progress_index=index + 1, target_index=index)
        _crash_after(target["role"] if action == "write" else action)

    byte_error = _verify_target_bytes(root, prepared)
    if byte_error:
        journal.mark("CONFLICT")
        return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                "recovery_required": True,
                "detail": f"post-write byte verification failed: {byte_error}"}

    # Semantic verification runs BEFORE VERIFIED -- and it is the SAME
    # postcondition class the recovery path runs from the journaled policy
    # (NITRO dogfood IV, T-601): a named policy verifier is invoked here on
    # APPLY with the actual changed targets, so APPLY and Recovery can never
    # disagree about what a verified result means. The legacy caller-supplied
    # `verify` callable remains the fallback for a "none" policy.
    policy_verifier = _verifier_for(verification_policy)
    if policy_verifier is not None:
        errors = (policy_verifier(root, prepared, receipt_metadata)
                  if verification_policy == "sub_sync"
                  else policy_verifier(root, prepared))
        if errors:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": "post-write semantic verification (policy "
                              f"{verification_policy}) failed: "
                              + "; ".join(errors[:5])}
    elif verify is not None:
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
    """Roll-forward, conflict-safe recovery (NITRO dogfood II).

    Per unfinished target:
      current == before_hash -> apply the staged planned bytes
      current == after_hash  -> already applied; advance
      anything else          -> CONFLICT: preserve journal + staged bytes,
                                write nothing further, refuse to guess.

    Per already-applied target the live bytes MUST equal after_hash, or the
    applied work was overwritten: CONFLICT. Repeated recovery is idempotent.

    Before roll-forward, every READ-ONLY precondition captured by the original
    plan is rechecked against the plan's allowed state: a read dependency that
    changed is CONFLICT (an intervening edit to a file the operation decided
    against cannot be silently committed over). After roll-forward, the
    operation's registered semantic verifier (verification_policy) reruns;
    an invalid recovered state becomes CONFLICT, never COMMITTED.
    """
    root = Path(project_root)
    journal = Journal(root, op_id)
    if not journal.exists():
        return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
    record = journal.read()
    status = record["status"]
    if status == "COMMITTED":
        return {"ok": True, "code": "ALREADY_APPLIED", "op_id": op_id}
    if status in SETTLED:
        return {"ok": False, "code": status, "op_id": op_id,
                "recovery_required": True,
                "detail": f"op is {status}; resolve explicitly before "
                          "further mutation"}
    if status == "CONFLICT":
        return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                "recovery_required": True,
                "detail": "op is CONFLICT; resolve explicitly before "
                          "further mutation (saipen recover, evidence "
                          "preserved)"}

    # Release operations own git side effects (commits/pushes/tags) that the
    # byte-replay path below cannot redo. Dispatch to the release recovery,
    # which classifies every external fact against the journal's recorded
    # expectations and never blindly repeats a side effect (T-994).
    if record.get("operation") == "release":
        from .release import recover_release_op
        return recover_release_op(project_root, op_id)

    targets = record["targets"]
    # PREPARED with nothing applied: no canonical byte changed -> abort safely.
    if status == "PREPARED" and not any(t["applied"] for t in targets):
        journal.mark("ABORTED")
        return {"ok": True, "code": "ABORTED", "op_id": op_id}

    # Recheck READ-ONLY preconditions before any roll-forward. A read
    # dependency is a file the plan decided against but did not write; if its
    # live bytes differ from what the plan allowed, the plan is no longer the
    # authorized decision for the current repository -> CONFLICT.
    for path, expected in (record.get("read_preconditions") or {}).items():
        dependency = Path(path)
        if not dependency.is_absolute():
            dependency = root / dependency
        live = _hash_dependency(dependency, expected)
        if live != expected:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": f"read-only dependency {path} changed (live "
                              f"{live!r}, planned {expected!r}); the plan is "
                              "no longer the authorized decision, refuse to "
                              "roll forward"}

    for index, target in enumerate(targets):
        live = _target_live_hash(root, target)
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
            action = _target_action(target)
            try:
                if action == "write":
                    staged = journal.staged_content(index)
                    if hash_bytes(staged) != target["after_hash"]:
                        journal.mark("CONFLICT")
                        return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                                "recovery_required": True,
                                "detail": f"staged bytes for {target['path']} "
                                          f"hash to {hash_bytes(staged)!r}, not "
                                          f"planned {target['after_hash']!r}; "
                                          "journal evidence is corrupt"}
                    _atomic_write(root / target["path"], staged)
                elif action == "delete_file":
                    (root / target["path"]).unlink()
                else:
                    (root / target["path"]).rmdir()
            except OSError as exc:
                journal.mark("CONFLICT")
                return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                        "recovery_required": True,
                        "detail": f"target {target['path']} recovery action "
                                  f"failed: {exc}"}
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

    # Byte-level verification of every written target.
    byte_error = _verify_target_bytes(root, targets)
    if byte_error:
        journal.mark("CONFLICT")
        return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                "recovery_required": True,
                "detail": f"recovered byte verification failed: {byte_error}"}

    # Semantic verification per the operation's registered policy. This is the
    # same postcondition class the original APPLY ran -- the verifier receives
    # the operation's actual changed targets, so a domain verifier validates
    # the exact files it wrote (NITRO dogfood IV, T-601). Without it, VERIFIED
    # would be a false stage name on the recovery path.
    policy = record.get("verification_policy", "none")
    verifier = _verifier_for(policy)
    if verifier is not None:
        errors = (verifier(root, targets, record.get("receipt_metadata"))
                  if policy == "sub_sync" else verifier(root, targets))
        if errors:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": "recovered state fails the registered semantic "
                              "verifier: " + "; ".join(errors[:5])}

    journal.mark("VERIFIED")
    journal.mark("COMMITTED")
    return {"ok": True, "code": "COMMITTED", "op_id": op_id,
            "changed_files": [t["path"] for t in targets],
            "recovery_required": True}


def _verifier_for(policy: str):
    """The semantic verifier callable for a closed verification policy, or
    None when the policy carries no cross-file postcondition.

    Every NAMED policy must behave truthfully (NITRO dogfood III, T-594):
    a named semantic verifier actually verifies the semantic postcondition the
    mutation claims, never a silent None. Every callable takes
    (root, targets) -- the operation's actual changed targets -- so APPLY and
    Recovery share ONE postcondition class and a domain verifier validates
    the file it changed, never an unrelated scan (NITRO dogfood IV, T-601)."""
    if policy == "core_fast":
        from . import fast_check
        return lambda root, targets: fast_check.validate_project(root)
    if policy == "improve_atomic_file":
        return verify_improve
    if policy == "userperson":
        return lambda root, targets: _verify_userperson(root)
    if policy == "sub_collect":
        return verify_sub_collect
    if policy == "sub_lifecycle":
        return verify_sub_lifecycle
    if policy == "sub_clean":
        return verify_sub_clean
    if policy == "sub_sync":
        return verify_sub_sync
    return None


def verify_improve(root, targets) -> list[str]:
    """TARGET-AWARE Improve semantic postcondition (NITRO dogfood IV, T-601).

    The ONE semantic verifier both APPLY and Recovery run for the
    improve_atomic_file policy. It validates the ACTUAL changed targets --
    never a generic scan of unrelated files -- with the SAME grammar the
    consumers parse (improve.py's own manifest/sweep/report validators). A
    malformed SWEEP.md therefore FAILs its own semantic verifier even when an
    unrelated MANIFEST is valid.
    """
    errors = []
    try:
        import improve
        for target in targets or []:
            rel = target.get("path", "")
            role = target.get("role", "generic")
            path = root / rel
            if not path.is_file():
                errors.append(f"{rel}: written Improve target missing after "
                              "apply")
                continue
            text = path.read_text(encoding="utf-8-sig")
            if role in ("manifest", "cycle", "seat"):
                errors.extend(improve.validate_manifest(text))
            elif role == "sweep":
                errors.extend(improve.validate_sweep(text))
            elif role in ("report", "run"):
                errors.extend(improve.validate_report_target(text))
            elif role == "generic":
                pass  # no domain grammar for an unknown Improve file
    except Exception as exc:
        errors.append(f"improve verification failed: {exc}")
    return errors


def _verify_userperson(root) -> list[str]:
    """Verify the semantic postcondition of a USERPERSON write: an absent
    profile is the canonical OFF state; a present profile parses structurally."""
    errors = []
    profile = root / ".saipen" / "USERPERSON.md"
    if not profile.is_file():
        return errors  # absence is the canonical OFF state
    try:
        from userperson import validate_profile
        errors.extend(validate_profile(profile.read_text(encoding="utf-8-sig")))
    except Exception as exc:
        errors.append(f"userperson verification failed: {exc}")
    return errors


def verify_sub_collect(root, targets) -> list[str]:
    """Core-fast plus target-aware SubSaipen collection postconditions."""
    from . import fast_check
    errors = list(fast_check.validate_project(root))
    try:
        from .subs import (LAST_COLLECT_RE, MANIFEST_REL, SUBS_REL,
                           package_identity, parse_manifest_file,
                           parse_outbox)
        target_paths = {target.get("path", "") for target in targets or []}
        report_paths = sorted(path for path in target_paths
                              if path.startswith(SUBS_REL + "/")
                              and path.endswith("/kitchen/OUTBOX.md"))
        if MANIFEST_REL not in target_paths:
            errors.append("sub_collect did not own live MANIFEST")
        if not report_paths:
            errors.append("sub_collect did not own a target OUTBOX")
        entries, manifest_errors = parse_manifest_file(root)
        errors.extend(manifest_errors)
        entry_by_name = {entry.name: entry for entry in entries}
        board_text = (root / ".saipen" / "BOARD.md").read_text(
            encoding="utf-8-sig")
        log_text = (root / ".saipen" / "LOG.md").read_text(
            encoding="utf-8-sig")
        prefix = SUBS_REL + "/"
        for rel in report_paths:
            producer = rel[len(prefix):].split("/", 1)[0]
            entry = entry_by_name.get(producer)
            if entry is None:
                errors.append(f"{producer}: target OUTBOX has no MANIFEST entry")
                continue
            last_collect = entry.metadata.get("last_collect", "")
            if not LAST_COLLECT_RE.fullmatch(last_collect) \
                    or "@" not in last_collect:
                errors.append(f"{producer}: last_collect lacks package identity")
                continue
            expected_identity = last_collect.split("@", 1)[0]
            if expected_identity not in board_text:
                errors.append(f"{producer}: package identity absent from Core "
                              "BOARD provenance")
            if expected_identity not in log_text:
                errors.append(f"{producer}: package identity absent from Core "
                              "LOG provenance")
            path = root / rel
            if not path.is_file():
                errors.append(f"{rel}: target OUTBOX missing")
                continue
            model = parse_outbox(path.read_text(encoding="utf-8-sig"), producer)
            errors.extend(f"{rel}: {error}" for error in model.errors)
            matches = [package for package in model.packages
                       if package_identity(package) == expected_identity]
            if len(matches) != 1:
                errors.append(f"{producer}: last_collect identity matches "
                              f"{len(matches)} OUTBOX packages")
            elif matches[0].status != "reviewed":
                errors.append(f"{producer}/{matches[0].package_id}: collected "
                              f"package status is {matches[0].status!r}, not "
                              "'reviewed'")
    except Exception as exc:
        errors.append(f"sub collect verification failed: {exc}")
    return errors


def verify_sub_lifecycle(root, targets) -> list[str]:
    """Verify only SubSaipen entities owned by this journaled mutation."""
    errors = []
    try:
        from .state import parse_frontmatter
        from .subs import (MANIFEST_REL, SUBS_REL, _entry_dir,
                           parse_manifest_file, parse_outbox, parse_sub_board,
                           role_freshness)
        target_paths = {target.get("path", "") for target in targets or []}
        owns_outbox = {path for path in target_paths
                       if path.endswith("/kitchen/OUTBOX.md")}
        owns_lifecycle = (MANIFEST_REL in target_paths
                          or any(path.startswith(SUBS_REL + "/")
                                 and (path.endswith("/STATE.md")
                                      or path.endswith("/BOARD.md")
                                      or path.endswith("/LOG.md")
                                      or path.endswith("/kitchen/OUTBOX.md"))
                                 for path in target_paths))
        if not owns_lifecycle:
            return errors
        if not any(path == MANIFEST_REL or path.startswith(SUBS_REL + "/")
                   for path in target_paths):
            return errors
        names = set()
        prefix = SUBS_REL + "/"
        for path in target_paths:
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix):]
            if remainder.count("/") >= 2:
                candidate = remainder.split("/", 1)[0]
                if candidate not in {"TEMPLATE", "_shared"}:
                    names.add(candidate)
        entries, manifest_errors = parse_manifest_file(root)
        errors.extend(manifest_errors)
        entry_by_name = {entry.name: entry for entry in entries}
        for name in sorted(names):
            entry = entry_by_name.get(name)
            if entry is None:
                errors.append(f"{name}: missing strict MANIFEST registration")
                continue
            instance = _entry_dir(root, entry)
            expected = (root / SUBS_REL / name).resolve()
            if instance.resolve() != expected:
                errors.append(f"{name}: MANIFEST path does not bind target instance")
                continue
            state_file = instance / "STATE.md"
            board_file = instance / "BOARD.md"
            if not state_file.is_file():
                errors.append(f"{name}: STATE.md missing")
                continue
            state_text = state_file.read_text(encoding="utf-8-sig")
            st, state_error = parse_frontmatter(state_text)
            if state_error or not st:
                errors.append(f"{name}: STATE unparseable: {state_error}")
                continue
            for field in ("agent", "role_revision"):
                count = len(re.findall(rf"(?m)^{field}:\s*", state_text))
                if count != 1:
                    errors.append(
                        f"{name}: STATE field {field} appears {count} time(s)")
            if st.get("agent") != name:
                errors.append(f"{name}: STATE agent {st.get('agent')!r} mismatches role")
            role_revision = st.get("role_revision") or ""
            role_state = role_freshness(root, name, role_revision,
                                        st.get("saipen_home") or "")
            if role_state != "current":
                errors.append(f"{name}: role identity is {role_state}")
            board = parse_sub_board(
                board_file.read_text(encoding="utf-8-sig")
                if board_file.is_file() else "", expected_role=name)
            errors.extend(f"{name}: {error}" for error in board["errors"])
            if (st.get("phase") == "DONE"
                    and (board["counts"]["TODO"] or board["counts"]["DOING"]
                         or board["counts"]["BLOCKED"])):
                errors.append(f"{name}: DONE with pending board work")
            paused = (st.get("phase") == "BLOCKED"
                      and st.get("blocker") == "paused by main agent")
            if paused != bool(st.get("paused_from_phase")
                              and st.get("paused_from_na")):
                errors.append(f"{name}: pause metadata/phase mismatch")
        for rel in owns_outbox:
            owner = rel[len(prefix):].split("/", 1)[0]
            path = root / rel
            model = parse_outbox(path.read_text(encoding="utf-8-sig"), owner) \
                if path.is_file() else None
            if model is None:
                errors.append(f"{rel}: owned OUTBOX missing")
            else:
                errors.extend(f"{rel}: {error}" for error in model.errors)
    except Exception as exc:
        errors.append(f"sub lifecycle verification failed: {exc}")
    return errors


def verify_sub_clean(root, targets) -> list[str]:
    """Verify manifest removal, source absence, and exact archive binding."""
    errors = []
    try:
        from .subs import MANIFEST_REL, SUBS_REL, parse_manifest_file
        receipts = [target for target in targets or []
                    if target.get("action", "write") == "write"
                    and target.get("path", "").startswith(
                        ".saipen/recovery/subs/")
                    and target.get("path", "").endswith("/receipt.json")]
        if len(receipts) != 1:
            return [f"sub_clean owns {len(receipts)} receipt targets, expected 1"]
        receipt_path = root / receipts[0]["path"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        name = receipt.get("name", "")
        source_prefix = f"{SUBS_REL}/{name}/"
        archive_prefix = receipt.get("archive_instance", "").rstrip("/") + "/"
        entries, manifest_errors = parse_manifest_file(root)
        errors.extend(manifest_errors)
        if any(entry.name == name for entry in entries):
            errors.append(f"{name}: strict MANIFEST still contains cleaned role")
        source = root / source_prefix.rstrip("/")
        if os.path.lexists(source):
            errors.append(f"{name}: source instance still exists")
        deleted = {target["path"][len(source_prefix):]: target["before_hash"]
                   for target in targets or []
                   if target.get("action") == "delete_file"
                   and target.get("path", "").startswith(source_prefix)}
        archived = {target["path"][len(archive_prefix):]: target["after_hash"]
                    for target in targets or []
                    if target.get("action", "write") == "write"
                    and target.get("path", "").startswith(archive_prefix)}
        archive_root = root / archive_prefix.rstrip("/")
        actual_archived = {
            path.relative_to(archive_root).as_posix()
            for path in archive_root.rglob("*") if path.is_file()
        } if archive_root.is_dir() else set()
        if receipt.get("files") != deleted:
            errors.append("receipt file/hash map does not match deletion targets")
        if set(archived) != set(deleted) or actual_archived != set(deleted):
            errors.append("archive file set does not exactly match source file set")
        for rel, expected in deleted.items():
            live = _hash_file(root / archive_prefix / rel)
            if live != expected or archived.get(rel) != expected:
                errors.append(f"archive/{rel}: hash {live!r} != source {expected!r}")
        if MANIFEST_REL not in {target.get("path") for target in targets or []}:
            errors.append("sub_clean did not own strict MANIFEST")
        if not receipt.get("instance_tree_hash", "").startswith(
                "delete-tree-sha256:"):
            errors.append("receipt lacks exact source tree hash")
    except Exception as exc:
        errors.append(f"sub clean verification failed: {exc}")
    return errors


def verify_sub_sync(root, targets, receipt_metadata) -> list[str]:
    """Verify shared-contract postconditions from journaled provenance."""
    try:
        from .subs import verify_sub_sync_receipt
        return verify_sub_sync_receipt(root, receipt_metadata)
    except Exception as exc:
        return [f"sub sync verification failed: {exc}"]


def inspect_op(project_root: Path | str, op_id: str) -> dict:
    """READ-ONLY conflict inspection (NITRO dogfood III, T-594).

    Returns the full evidence a resolver needs: operation, status, targets
    with expected-before/planned-after/current hashes, read-only dependencies,
    which locations currently conflict, the verification policy, the staged
    identity, and the safe resolution classes. Zero mutation, JSON-first.
    """
    root = Path(project_root)
    journal = Journal(root, op_id)
    if not journal.exists():
        return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
    record = journal.read()
    targets = []
    conflicts = []
    for target in record.get("targets", []):
        live = _target_live_hash(root, target)
        entry = {
            "path": target["path"],
            "role": target["role"],
            "action": _target_action(target),
            "applied": target.get("applied", False),
            "expected_before": target.get("before_hash", ""),
            "planned_after": target.get("after_hash", ""),
            "current": live,
        }
        expected = target.get("after_hash") if target.get("applied") \
            else target.get("before_hash")
        if live != expected:
            entry["conflicts"] = True
            conflicts.append(target["path"])
        else:
            entry["conflicts"] = False
        targets.append(entry)
    return {
        "ok": True,
        "op_id": op_id,
        "operation": record.get("operation"),
        "status": record.get("status"),
        "created_at": record.get("created_at"),
        "agent": record.get("agent"),
        "verification_policy": record.get("verification_policy", "none"),
        "read_dependencies": record.get("read_preconditions", {}),
        "targets": targets,
        "conflicting_locations": conflicts,
        "staged_identity": record.get("semantic_payload_hash"),
        "safe_resolution_classes": (
            ["accept_live", "replan"]
            if record.get("status") == "CONFLICT" else []),
        "code": "CONFLICT_INSPECT" if record.get("status") == "CONFLICT"
        else "OP_INSPECT",
    }


def resolve_conflict(project_root: Path | str, op_id: str,
                     resolution: str = "accept_live",
                     agent: str = "saipen") -> dict:
    """Settle ONE unresolved CONFLICT through an explicit bounded lifecycle
    (NITRO dogfood III, T-594). No --force exists: a conflict means live
    evidence diverged from the authorized plan, and the resolver never writes
    planned bytes over live ones.

    ACCEPT_LIVE_ABORT_PLAN: keep the current conflicting live bytes as truth;
    abandon every remaining unapplied plan effect. Any target already applied
    stays (its after_hash IS the live truth); anything not applied stays live.

    REPLAN: retire this operation (conflict evidence preserved), requiring a
    fresh semantic OperationPlan built from the current canonical state.

    Both produce a RESOLVED journal with applied/skipped targets, the resolver
    event and validation evidence. Resolution bypasses ONLY this op from the
    preflight gate: it refuses when another unrelated unresolved operation or
    conflict exists, and it re-verifies the live repository afterwards.

    SERIALIZATION (NITRO dogfood IV, T-601): resolve is a MUTATION (it settles
    the journal status), so it runs under the canonical project writer lock.
    Two simultaneous resolvers of the same conflict therefore cannot race the
    journal status/evidence: the loser either blocks on the lock (WRITER_BUSY)
    or, if it acquires the lock after the winner settled, re-reads the journal
    under the lock and refuses because the op is no longer CONFLICT. Exactly
    one canonical settlement. `inspect` stays read-only and takes no lock.
    """
    root = Path(project_root)
    from .lock import project_writer_lock as _resolver_lock
    try:
        with _resolver_lock(root):
            return _resolve_conflict_locked(root, op_id, resolution, agent)
    except PermissionError:
        return {"ok": False, "code": "WRITER_BUSY", "op_id": op_id,
                "detail": "another live writer holds the project lock; "
                          "retry after it releases"}


def _resolve_conflict_locked(root: Path, op_id: str, resolution: str,
                             agent: str) -> dict:
    """The locked body of resolve_conflict (T-601). Called only under the
    project writer lock, so the journal read, the pending-op scan and the
    live-hash snapshot all observe one consistent world."""
    journal = Journal(root, op_id)
    if not journal.exists():
        return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
    record = journal.read()
    if record.get("status") != "CONFLICT":
        return {"ok": False, "code": "VALIDATION_FAILED",
                "detail": f"op {op_id} is {record.get('status')}, not "
                          "CONFLICT; only an unresolved conflict is "
                          "resolvable"}
    if resolution not in ("accept_live", "replan"):
        return {"ok": False, "code": "VALIDATION_FAILED",
                "detail": f"resolution {resolution!r} outside "
                          "accept_live|replan"}

    # Only the selected conflict may be settled: any OTHER unresolved op or
    # conflict blocks this resolution (no global bypass).
    for other in pending_ops(root):
        if other["op_id"] != op_id:
            return {"ok": False, "code": "RECOVERY_REQUIRED",
                    "op_ids": [other["op_id"]],
                    "detail": f"unrelated unresolved op {other['op_id']} "
                              "blocks resolving this conflict; resolve it "
                              "first"}

    # Re-read the live state before settling: if hashes changed again during
    # the decision, refuse (the evidence moved under us). ACCEPT_LIVE and
    # REPLAN both keep the current live bytes as the new baseline -- an
    # unfinished target's divergent bytes ARE the accepted truth, they do not
    # need to equal before/after. The only refusal is the evidence moving
    # mid-resolution.
    applied = []
    skipped = []
    live_snapshot = {}
    for target in record.get("targets", []):
        live = _target_live_hash(root, target)
        live_snapshot[target["path"]] = live
        if target.get("applied"):
            if live != target.get("after_hash"):
                return {"ok": False, "code": "CONFLICT",
                        "detail": f"applied target {target['path']} changed "
                                  f"again during resolution; evidence moved, "
                                  "re-inspect"}
            applied.append(target["path"])
        else:
            skipped.append(target["path"])
    # Stability guard: the live bytes must not move between the pre-resolution
    # read and the settle.
    for path, expected in live_snapshot.items():
        target = next(item for item in record.get("targets", [])
                      if item["path"] == path)
        if _target_live_hash(root, target) != expected:
            return {"ok": False, "code": "CONFLICT",
                    "detail": f"target {path} changed during resolution; "
                              "evidence moved, re-inspect"}

    # ACCEPT_LIVE: the current live bytes are the new truth. Verify the
    # resulting canonical repository before settling.
    policy = record.get("verification_policy", "none")
    verifier = _verifier_for(policy)
    errors = verifier(root, record.get("targets", [])) \
        if verifier is not None else []
    if errors:
        return {"ok": False, "code": "NEEDS_REPAIR",
                "detail": "resolving to current live leaves an invalid "
                          "repository: " + "; ".join(errors[:5]),
                "conflict_op_id": op_id, "repair_evidence": errors}

    # Settle: mark RESOLVED with the resolution record. Never touch the live
    # canonical files -- the resolution IS the decision to keep them.
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    record["status"] = "RESOLVED"
    record["resolution"] = resolution
    record["resolved_at"] = now
    record["resolver_agent"] = agent
    record["resolution_applied_targets"] = applied
    record["resolution_skipped_targets"] = skipped
    record["resolution_evidence"] = "live accepted" if resolution \
        == "accept_live" else "operation retired; fresh plan required"
    _atomic_json(journal.manifest, record)
    return {"ok": True, "code": "RESOLVED", "op_id": op_id,
            "resolution": resolution, "applied_targets": applied,
            "skipped_targets": skipped,
            "detail": "conflict settled; live bytes accepted as truth, "
                      "unapplied plan effects abandoned"}


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


def compact_committed(project_root: Path | str) -> dict:
    """Bounded explicit maintenance compaction of SETTLED operation journals
    (NITRO dogfood II + IV, T-596).

    A COMMITTED or RESOLVED op no longer needs its staged bytes for recovery:
    idempotent retry only needs the compact tombstone. Compaction deletes the
    large `.staged` payloads and KEEPS the full tombstone -- op_id, operation,
    status, result identity (semantic_payload_hash), the per-target final
    hashes (before_hash/after_hash), timestamp (created_at) -- so a repeated
    checkpoint does not accumulate unbounded write amplification and every
    settled op stays attributable.

    NEVER compacts PREPARED / APPLYING / VERIFIED / CONFLICT / ABORTED --
    those still require evidence. A retried compacted op still returns
    ALREADY_APPLIED. This is the journal-compaction operation the CLEAN phase
    runs (saipen/phases/clean.md step 4); it is a maintenance mutation, never
    an automatic side effect of ordinary checkpointing.
    """
    root = Path(project_root)
    ops_dir = root / OPS_DIR
    if not ops_dir.is_dir():
        return {"ok": True, "compacted": [], "skipped": []}
    compacted = []
    skipped = []
    for entry in sorted(ops_dir.iterdir()):
        if not entry.is_dir():
            continue
        manifest = entry / "operation.json"
        if not manifest.is_file():
            continue
        try:
            record = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped.append(entry.name)
            continue
        if record.get("status") not in ("COMMITTED", "RESOLVED"):
            skipped.append(entry.name)
            continue
        for staged in entry.glob("*.staged"):
            with contextlib.suppress(OSError):
                staged.unlink()
        compacted.append(entry.name)
    return {"ok": True, "compacted": compacted, "skipped": skipped}

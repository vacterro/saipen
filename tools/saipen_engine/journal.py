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
    "sub_lifecycle",
    "none",
})

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
              read_preconditions: dict | None = None) -> None:
        """Write PREPARED: op metadata, per-target before/after hashes, and
        the exact staged final bytes of every target.

        `targets` is a list of dicts: {path, role, content(bytes),
        before_hash, after_hash}. Staged bytes are stored under the journal
        directory so recovery can replay exact intended bytes -- never
        recomputed from the current state.

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
            "read_preconditions": read_preconditions or {},
            "verification_policy": verification_policy,
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
                 skip_preflight: bool = False,
                 verification_policy: str = "none",
                 read_preconditions: dict | None = None) -> dict:
    """Commit an ordered, journaled mutation with conflict-safe recovery.

    `targets` is an ordered list of {"path", "role", "content"} where path is
    relative to the project root. before_hash/after_hash are computed here from
    the live file and the staged content, and stored in the journal. The
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

    # Every WRITE target and every read-only dependency must match the
    # hashes captured at plan time.
    for path, expected in (preconditions or {}).items():
        actual = _hash_file(root / path)
        if actual != expected:
            return {"ok": False, "code": "STALE_STATE", "op_id": op_id,
                    "detail": f"precondition {path} changed (live {actual!r}, "
                              f"expected {expected!r})"}
    for path, expected in (read_preconditions or {}).items():
        actual = _hash_file(root / path)
        if actual != expected:
            return {"ok": False, "code": "STALE_STATE", "op_id": op_id,
                    "detail": f"read dependency {path} changed (live "
                              f"{actual!r}, expected {expected!r})"}

    journal.start(operation, agent, project_identity, semantic_payload_hash,
                  prepared, preconditions,
                  verification_policy=verification_policy,
                  read_preconditions=read_preconditions)
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

    # Semantic verification runs BEFORE VERIFIED -- and it is the SAME
    # postcondition class the recovery path runs from the journaled policy
    # (NITRO dogfood IV, T-601): a named policy verifier is invoked here on
    # APPLY with the actual changed targets, so APPLY and Recovery can never
    # disagree about what a verified result means. The legacy caller-supplied
    # `verify` callable remains the fallback for a "none" policy.
    policy_verifier = _verifier_for(verification_policy)
    if policy_verifier is not None:
        errors = policy_verifier(root, prepared)
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
        live = _hash_file(root / path)
        if live != expected:
            journal.mark("CONFLICT")
            return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                    "recovery_required": True,
                    "detail": f"read-only dependency {path} changed (live "
                              f"{live!r}, planned {expected!r}); the plan is "
                              "no longer the authorized decision, refuse to "
                              "roll forward"}

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
        errors = verifier(root, targets)
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
    if policy == "sub_lifecycle":
        return lambda root, targets: _verify_sub_lifecycle(root)
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


def _verify_sub_lifecycle(root) -> list[str]:
    """Verify the semantic postcondition of a SubSaipen lifecycle write: the
    sub STATE parses and pause metadata pairs correctly with the phase."""
    errors = []
    subs_dir = root / ".saipen" / "extensions" / "subs"
    if not subs_dir.is_dir():
        return errors
    try:
        from .state import parse_state
        for instance in sorted(subs_dir.iterdir()):
            state_file = instance / "STATE.md"
            if not state_file.is_file():
                continue
            st = parse_state(state_file.read_text(encoding="utf-8-sig"))
            if not st:
                errors.append(f"{instance.name}: STATE unparseable")
            phase = st.get("phase")
            if phase == "BLOCKED" and st.get("blocker") == "paused by main agent":
                if not st.get("paused_from_phase"):
                    errors.append(f"{instance.name}: paused without "
                                  "paused_from_phase")
                if not st.get("paused_from_na"):
                    errors.append(f"{instance.name}: paused without "
                                  "paused_from_na")
    except Exception as exc:
        errors.append(f"sub lifecycle verification failed: {exc}")
    return errors


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
        live = _hash_file(root / target["path"])
        entry = {
            "path": target["path"],
            "role": target["role"],
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
        live = _hash_file(root / target["path"])
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
        if _hash_file(root / path) != expected:
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
            try:
                staged.unlink()
            except OSError:
                pass
        compacted.append(entry.name)
    return {"ok": True, "compacted": compacted, "skipped": skipped}

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
import stat
import sys
import datetime
from dataclasses import dataclass
from pathlib import Path

from .board import strict_iso_utc, iso_utc_sort_key

STATUS = ("PREPARED", "APPLYING", "VERIFIED", "COMMITTED", "ABORTED", "CONFLICT", "RESOLVED")
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
LINEAGE_MIGRATION_OP = "op-migrate-lineage"
# Engine-written settled receipt marker (perf wave T-1020): a tiny summary
# published next to operation.json when an op reaches a terminal status, so
# hot pending scans enumerate settled receipts without deep-decoding every
# historical manifest. The marker is a fast path ONLY (T-1008): it certifies
# the EXACT operation.json bytes it was written over (manifest_hash), and
# scan_pending trusts it only while those bytes are unchanged -- a missing,
# corrupt or stale marker falls back to the strict manifest decode (correct,
# legacy), never launders unresolved/corrupt evidence.
SETTLED_DIR = ".saipen/recovery/settled"
# PERF-005: bounded cleanup-debt namespace. When a post-settlement staged-byte
# deletion fails, the op_id is durably enqueued here so `compact_committed`
# processes ONLY outstanding debt instead of re-scanning the whole lifetime
# settled history on every CLEAN.
CLEANUP_QUEUE_DIR = SETTLED_DIR + "/.cleanup-needed"

# Closed verification-policy registry. Recovery must run the SAME semantic
# postcondition class as the original APPLY; a policy names the verifier
# WITHOUT serializing Python callables (NITRO dogfood II, T-587).
VERIFICATION_POLICIES = frozenset(
    {
        "core_fast",
        "improve_atomic_file",
        "userperson",
        "sub_collect",
        "sub_disposition",
        "sub_lifecycle",
        "sub_clean",
        "sub_sync",
        "none",
    }
)

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


def _canonical_receipt_metadata(value: object) -> tuple[dict | None, str | None]:
    """Normalize the one optional semantic-receipt ticket representation.

    Older settled receipts used ``ticket_id: null`` and some callers used an
    empty string when no Core ticket existed.  Both mean absence.  New records
    omit the key, while non-null/non-string values remain corrupt evidence.
    """
    if value is None:
        return None, None
    if not isinstance(value, dict):
        return None, "must be a JSON object or null"
    normalized = dict(value)
    if "ticket_id" in normalized:
        ticket_id = normalized["ticket_id"]
        if ticket_id is None or ticket_id == "":
            normalized.pop("ticket_id")
        elif not isinstance(ticket_id, str):
            return None, "ticket_id must be a string or null"
    return normalized, None


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
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


def _hash_delete_tree(path: Path, read_file=None) -> str:
    """Exact deterministic hash for a directory deletion target.

    PERFORMANCE (PERF-003): ``read_file`` is an optional callable ``Path -> bytes``
    used to supply already-read content. When omitted, bytes are read from disk
    as before. The unified mutation-PLAN capture passes a resolver backed by a
    SINGLE read of every sealed LOG segment so the delete-tree digest is computed
    from the same bytes the history snapshot already consumed -- identical framing,
    identical sentinels, just no second content read."""
    read_file = read_file if read_file is not None else (lambda p: Path(p).read_bytes())
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
                if candidate.is_symlink() or attrs & 0x400 or not candidate.is_file():
                    rel = candidate.relative_to(path).as_posix()
                    return f"object-unsupported:{rel}"
                rel = candidate.relative_to(path).as_posix().encode("utf-8")
                raw = read_file(candidate)
                digest.update(b"F" + len(rel).to_bytes(8, "big") + rel)
                digest.update(len(raw).to_bytes(8, "big") + raw)
    except OSError:
        return "object-unreadable"
    return "delete-tree-sha256:" + digest.hexdigest()


def hash_delete_tree(path: Path | str) -> str:
    """Public exact tree digest used by deletion plans and CAS checks."""
    return _hash_delete_tree(Path(path))


def hash_tree_dependency(path: Path | str, read_file=None) -> str:
    """Safe exact directory token for read-only CAS dependencies.

    Unlike ``hash_tree``, this never follows a symlink/reparse point and it
    distinguishes a missing directory from an unreadable/unsupported object.

    PERFORMANCE (PERF-003): ``read_file`` is forwarded to ``_hash_delete_tree`` so
    the mutation-PLAN capture can compute the sealed-LOG dependency digest from a
    single read of the history segments.
    """
    candidate = Path(path)
    digest = _hash_delete_tree(candidate, read_file=read_file)
    if not digest and not os.path.lexists(candidate):
        return MISSING_TREE_DEPENDENCY
    return digest


DIRECTORY_LISTING_PREFIX = "directory-listing-sha256:"


def hash_directory_listing_dependency(path: Path | str) -> str:
    """Hash one directory's immediate owned membership without child bytes.

    Crew uses this beside exact file/small-tree dependencies to detect a new
    charter, instance or READY/SETTLED namespace while avoiding recursive
    reads of irrelevant producer scratch.  Child type is framed so replacing
    a regular file with a directory/symlink cannot preserve the token.
    """
    candidate = Path(path)
    try:
        info = candidate.lstat()
    except FileNotFoundError:
        return DIRECTORY_LISTING_PREFIX + "missing"
    except OSError:
        return "object-unreadable"
    attrs = getattr(info, "st_file_attributes", 0)
    if candidate.is_symlink() or attrs & 0x400 or not candidate.is_dir():
        return f"object:{info.st_mode}"
    digest = hashlib.sha256(b"saipen-directory-listing-v1\0")
    try:
        for child in sorted(candidate.iterdir(), key=lambda item: item.name):
            child_info = child.lstat()
            child_attrs = getattr(child_info, "st_file_attributes", 0)
            name = child.name.encode("utf-8")
            if child.is_symlink() or child_attrs & 0x400:
                kind = b"L"
            elif child.is_file():
                kind = b"F"
            elif child.is_dir():
                kind = b"D"
            else:
                kind = b"O"
            digest.update(kind + len(name).to_bytes(8, "big") + name)
    except OSError:
        return "object-unreadable"
    return DIRECTORY_LISTING_PREFIX + digest.hexdigest()


def empty_delete_tree_hash() -> str:
    """Exact hash of an empty directory immediately before `rmdir`."""
    digest = hashlib.sha256(b"saipen-delete-tree-v1\0")
    digest.update(b"D" + (1).to_bytes(8, "big") + b".")
    return "delete-tree-sha256:" + digest.hexdigest()


def owned_target_path(
    root: Path, rel: str, *, kind: str = "target", owner_canonical: Path | None = None
) -> Path:
    """ONE canonical owned-target resolver (T-1003 operational integrity).

    Every mutation/recovery target path -- and every op_id-derived path --
    must be a RELATIVE, non-drive-qualified string that resolves INSIDE the
    project after symlink/junction collapse. This is the single resolver for
    hash/stage/apply/recover: no code path may build a target path another
    way and still be safe. Raises InvalidIdError on any escape.

    Callers convert the raise into their own refusal shape; direct Journal
    users get the raise (fail closed).

    PERF-004: `owner_canonical` is the once-canonicalized project root for a
    single decoder invocation, avoiding repeated realpath on the identical
    owner per candidate target.
    """
    from .safeid import InvalidIdError, prove_inside

    if not isinstance(rel, str) or not rel:
        raise InvalidIdError(f"{kind} path {rel!r} is empty or not a string")
    if os.path.isabs(rel) or re.match(r"^[A-Za-z]:[\\/]", rel):
        raise InvalidIdError(
            f"{kind} {rel!r} is absolute or drive-qualified; only relative "
            "project-owned paths are allowed"
        )
    return prove_inside(root / rel, root, kind=kind, owner_canonical=owner_canonical)


def read_dependency_path(root: Path, rel: str, *, kind: str = "read-dependency") -> Path:
    """Resolve a READ-ONLY dependency path.

    Absolute paths are allowed here because read-only dependencies may
    legitimately reference the SAIPEN home (the source of the shared
    contract) -- they are hashed, never written. Relative paths must still
    resolve INSIDE the project (one owned-target resolver; a hostile journal
    cannot use a relative read-dependency to escape).
    """
    candidate = Path(rel)
    if candidate.is_absolute():
        return candidate
    return owned_target_path(root, rel, kind=kind)


def validate_op_id(op_id: str) -> str:
    """Validate an operation id before it becomes a path component.

    Operation IDs obey the same portable grammar and byte budget as every
    other engine-owned identifier.  A former partial check returned before
    the shared validator (left as unreachable text below ``safe_op_dir``), so
    spaces, control characters, device names and oversized components could
    reach the filesystem even though the decoder claimed the shared grammar.
    """
    from .safeid import InvalidIdError, validate_safe_id

    if not isinstance(op_id, str) or not op_id:
        raise InvalidIdError("op_id is empty or not a string")
    if op_id.startswith("..") or "/" in op_id or "\\" in op_id:
        raise InvalidIdError(f"op_id {op_id!r} is not a single safe path component")
    return validate_safe_id(op_id, kind="op_id")


def safe_op_dir(root: Path, op_id: str, base_dir: str = OPS_DIR) -> Path:
    """Safely resolve and contain the op directory, refusing symlinks/junctions."""
    from .safeid import prove_inside, InvalidIdError

    op_id = validate_op_id(op_id)

    b_dir = root / base_dir
    if b_dir.exists():
        info = os.lstat(b_dir)
        if b_dir.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise InvalidIdError(f"base_dir {base_dir!r} is a symlink or reparse point")

    op_dir = b_dir / op_id
    prove_inside(op_dir, root, kind="op_dir")

    if op_dir.exists():
        info = os.lstat(op_dir)
        if op_dir.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise InvalidIdError(f"op_dir {op_id!r} is a symlink or reparse point")

    return op_dir


def _target_action(target: dict) -> str:
    """The action of one journal target. Legacy targets without an `action`
    key remain writes (the pre-action receipt format); a PRESENT action must
    already have passed the strict operation-record decoder -- recovery never
    dispatches on an unvalidated action (an unknown action is an explicit
    refusal, never an `else` destructive fallback)."""
    return target.get("action", "write")


def _target_live_hash(root: Path, target: dict) -> str:
    action = _target_action(target)
    # Resolve through the owned-target resolver: hashing must never touch a
    # path outside the project even after entry validation (T-1003
    # operational integrity).
    path = owned_target_path(root, target["path"])
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

    return source_identity_dependency(compute_source_identity(Path(project_root)))


def source_identity_dependency(source) -> str:
    """Frame an already-sampled SourceIdentity as a journal CAS token."""
    framed = (source.source_head + "\0" + source.source_tree_fingerprint).encode("utf-8")
    return SOURCE_IDENTITY_PREFIX + hashlib.sha256(framed).hexdigest()


def _hash_dependency(path: Path, expected: str) -> str:
    """Hash a read-only dependency. `path` must be inside the project (the
    caller resolves it through owned_target_path / dependency_path first);
    this is a pure byte/tree tokenizer for the already-owned path."""
    if expected.startswith(SOURCE_IDENTITY_PREFIX):
        try:
            return hash_source_identity(path)
        except Exception:
            return ""
    if expected.startswith(DIRECTORY_LISTING_PREFIX):
        return hash_directory_listing_dependency(path)
    if expected.startswith("ops-receipt-sha256:"):
        # The dependency key is <root>/.saipen/recovery.
        return semantic_receipt_digest(path.parent.parent)
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


def staged_name(index: int, canonical_path: str) -> str:
    """Bounded, path-independent staged evidence filename."""
    path_hash = hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()[:16]
    return f"{index}_{path_hash}.staged"


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


def _settle_journal(journal: "Journal") -> None:
    """Move a settled receipt out of the unresolved ops namespace (T-1008).

    Called ONLY after the terminal manifest write is already durable, so a
    move failure can never rewrite semantic status. The move is deliberately
    NON-FATAL: the manifest in ops/ is still the authoritative receipt. If the
    rename fails (e.g. permission error, disk full), the caller returns
    truthful COMMITTED semantics, and the next pending scan simply falls back
    to the strict manifest decode for this op (it reads status=COMMITTED and
    ignores it natively).
    """
    settled_base = journal.project_root / SETTLED_DIR
    try:
        settled_base.mkdir(parents=True, exist_ok=True)
        settled_dir = safe_op_dir(journal.project_root, journal.op_id, SETTLED_DIR)
        os.rename(journal.dir, settled_dir)
        journal.dir = settled_dir
        journal.manifest = settled_dir / "operation.json"
    except OSError:
        pass


def _crash_after(key: str) -> None:
    env = _CRASH_MAP.get(key)
    if env and env in os.environ:
        sys.exit(87)


def decode_operation_record(
    root: Path | str,
    op_dir: Path,
    raw: bytes | None = None,
    *,
    progress_raw: bytes | None = None,
    progress_captured: bool = False,
) -> dict:
    """STRICT single operation-record decoder (T-1003 hostile findings).

    Every consumer that trusts a journal loaded from disk -- pending_ops,
    preflight, inspect, resolve, recover and the release dispatch -- decodes
    through THIS one gate before any status/byte/dispatch decision. A hostile
    record can therefore never reach a destructive fallback: unknown actions,
    statuses, roles and policies are refused structurally, with ZERO target
    changes.

    Rules (all fail closed, never silently repaired):
    - the directory name must equal the record's op_id and pass the safe-id
      grammar;
    - status / verification_policy / target role are closed-enum members;
      a PRESENT target action must be in TARGET_ACTIONS (legacy targets
      without `action` default to `write`, the pre-action receipt format);
    - every target carries typed strings (path/role/before_hash/after_hash),
      a boolean `applied` flag, and unique paths within the operation;
    - precondition maps are dict[str, str];
    - UNRESOLVED write targets carry their staged-write evidence (the exact
      staged bytes recovery replays must exist, or the journal evidence is
      corrupt).

    ``raw`` and ``progress_raw`` may carry bytes already read and framed into
    the semantic snapshot digest; parsing and authentication then use that
    exact capture without a second open.  With ``progress_captured=True``, a
    ``None`` progress payload means the sidecar was authoritatively absent.

    Returns {"ok": True, "record": record} or a stable refusal dict
    {"ok": False, "code": ..., "detail": ...} with ZERO side effects:
    unparseable bytes are RECOVERY_CONFLICT (evidence that cannot be trusted
    must still be preserved), a structurally invalid record is
    VALIDATION_FAILED.
    """
    # Canonical absolute root ONCE: every owned identity below is
    # "resolved path relative to resolved root", so a relative root and a
    # resolved target can never be relative_to()'d into a crash
    # (hostile-regression canonical-identity rule).
    root = Path(root).resolve()
    from .safeid import InvalidIdError

    manifest = op_dir / "operation.json"
    if raw is None:
        try:
            raw = manifest.read_bytes()
        except OSError as exc:
            return {
                "ok": False,
                "code": "RECOVERY_CONFLICT",
                "detail": f"operation.json is unreadable: {exc}",
            }
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "code": "RECOVERY_CONFLICT",
            "detail": f"operation.json is not valid JSON: {exc}",
        }
    if not isinstance(record, dict):
        return {
            "ok": False,
            "code": "RECOVERY_CONFLICT",
            "detail": "operation record is not a JSON object",
        }

    def _bad(field: str, expected: str) -> dict:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"operation record field {field!r} {expected}",
        }

    def _strict_iso_utc(value: object) -> str:
        # Delegated to the ONE shared strict-UTC parser (P1#5): requires
        # utcoffset() == 0, canonicalizes to Z, and refuses non-zero offsets.
        return strict_iso_utc(value)

    op_id = record.get("op_id")
    if not isinstance(op_id, str) or not op_id:
        return _bad("op_id", "must be a non-empty string")
    try:
        validate_op_id(op_id)
    except InvalidIdError as exc:
        return _bad("op_id", f"fails the safe-id grammar: {exc}")
    if op_dir.name != op_id:
        return _bad("op_id", f"mismatches its directory name {op_dir.name!r}")
    status = record.get("status")
    if status not in STATUS:
        return _bad("status", f"{status!r} is outside the closed status set")
    if not isinstance(record.get("operation"), str) or not record.get("operation"):
        return _bad("operation", "must be a non-empty string")
    for key in ("semantic_payload_hash", "created_at"):
        value = record.get(key)
        if not isinstance(value, str):
            return _bad(key, "must be a string")
    # created_at is the ordering identity of an UNRESOLVED operation: a
    # timestamp that cannot parse cannot order recovery, and inventing
    # chronology from a garbage string is how dependent ops replay out of
    # creation order. A strict ISO-8601 UTC stamp (Z / +00:00, aware) is
    # REQUIRED for unresolved records, and the DECODED record carries the
    # validated value so every consumer (pending_ops ordering, recovery
    # dispatch) sorts by real chronology, never the directory name (T-1003
    # recovery ordering). SETTLED records (COMMITTED/ABORTED/RESOLVED) are
    # history, never ordered: a settled receipt whose timestamp degraded must
    # not poison the whole project into CORRUPT -- its durable evidence (the
    # inventory receipt) is still readable and a fresh valid successor can
    # supersede it (T-1001 sync lineage self-heal).
    created_at = record.get("created_at") or ""
    parsed_stamp = _strict_iso_utc(created_at)
    if status in UNRESOLVED and not parsed_stamp:
        return _bad(
            "created_at",
            f"must be a strict ISO-8601 UTC timestamp (Z or +00:00, aware); got {created_at!r}",
        )
    record["created_at"] = parsed_stamp or created_at
    if not isinstance(record.get("agent"), str):
        return _bad("agent", "must be a string")
    if not isinstance(record.get("project_identity"), str):
        return _bad("project_identity", "must be a string")
    if record.get("project_lineage") is not None and not isinstance(
        record.get("project_lineage"), str
    ):
        return _bad("project_lineage", "must be a string or absent")
    policy = record.get("verification_policy", "none")
    if not isinstance(policy, str) or policy not in VERIFICATION_POLICIES:
        return _bad("verification_policy", f"{policy!r} is outside the closed policy set")
    for key in ("preconditions", "read_preconditions"):
        value = record.get(key, {})
        if not isinstance(value, dict):
            return _bad(key, "must be a JSON object")
        for path, expected in value.items():
            if not isinstance(path, str) or not path or not isinstance(expected, str):
                return _bad(key, "must map string paths to string hashes")
    raw_receipt_metadata = record.get("receipt_metadata")
    receipt_metadata, metadata_error = _canonical_receipt_metadata(raw_receipt_metadata)
    if metadata_error is not None:
        field = (
            "receipt_metadata.ticket_id"
            if isinstance(raw_receipt_metadata, dict)
            else "receipt_metadata"
        )
        return _bad(field, metadata_error)
    if receipt_metadata is not None:
        record["receipt_metadata"] = receipt_metadata
        # Persisted receipts must obey the same JSON-object contract as live
        # writes.  A few fields are consumed mechanically across crew,
        # convergence, release and SubSaipen readers; validate their shapes at
        # the single decode boundary so hostile disk bytes cannot escape as an
        # AttributeError/TypeError later.
        for key in (
            "operation",
            "status",
            "event_id",
            "crew_epoch",
            "role",
            "stage",
            "verdict",
            "package_identity",
            "source_head",
            "source_tree_fingerprint",
            "resulting_source_head",
            "resulting_source_tree_fingerprint",
            "producer",
            "input_source",
            "input_source_fingerprint",
            "resulting_source",
            "resulting_source_fingerprint",
        ):
            if key in receipt_metadata and not isinstance(receipt_metadata[key], str):
                return _bad(f"receipt_metadata.{key}", "must be a string")
        if "paths" in receipt_metadata:
            paths = receipt_metadata["paths"]
            if not isinstance(paths, dict):
                return _bad("receipt_metadata.paths", "must be a JSON object")
            for path, expected in paths.items():
                if (
                    not isinstance(path, str)
                    or not path
                    or not (expected is None or isinstance(expected, str))
                ):
                    return _bad(
                        "receipt_metadata.paths",
                        "must map non-empty string paths to string hashes or null",
                    )
    if not isinstance(record.get("progress_index"), int):
        return _bad("progress_index", "must be an integer")
    targets = record.get("targets")
    if not isinstance(targets, list):
        return _bad("targets", "must be a JSON array")
    seen_paths: set[str] = set()
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            return _bad(f"targets[{index}]", "must be a JSON object")
        for key in ("path", "role", "before_hash", "after_hash"):
            value = target.get(key)
            if not isinstance(value, str):
                return _bad(f"targets[{index}].{key}", "must be a string")
        if not target["path"]:
            return _bad(f"targets[{index}].path", "must be non-empty")
        # ONE canonical owned identity per target (hostile-regression). The
        # duplicate/alias gate runs on the RESOLVED identity, never the raw
        # stored string: two stored spellings of one file ("a" and "./a",
        # "a/../a", alternate symlink routes) are the SAME owned object, and a
        # receipt that plans it twice is corrupt -- replay would apply two
        # mutations to one object. A stored path that escapes the project
        # (absolute, drive-qualified, traversal) is VALIDATION_FAILED, never a
        # crash: safe-path exceptions translate to structured refusals.
        try:
            canonical = (
                owned_target_path(root, target["path"], owner_canonical=root)
                .relative_to(root)
                .as_posix()
            )
        except InvalidIdError as exc:
            return _bad(f"targets[{index}].path", f"is not an owned project path: {exc}")
        if canonical in seen_paths:
            return _bad(
                f"targets[{index}].path",
                f"resolves to owned object {canonical!r} which is "
                "already a target -- one owned object may appear at "
                "most once per operation",
            )
        seen_paths.add(canonical)
        role = target.get("role")
        if role not in ROLES:
            return _bad(f"targets[{index}].role", f"{role!r} is outside the closed role set")
        action = target.get("action", "write")
        if not isinstance(action, str) or action not in TARGET_ACTIONS:
            return _bad(
                f"targets[{index}].action", f"{action!r} is outside {sorted(TARGET_ACTIONS)}"
            )
        if not isinstance(target.get("applied"), bool):
            return _bad(f"targets[{index}].applied", "must be a boolean")
        if "content" in target and not isinstance(target["content"], str):
            return _bad(f"targets[{index}].content", "must be a string")
        if status in UNRESOLVED and action == "write":
            name = staged_name(index, canonical)
            staged = op_dir / name
            if not staged.is_file():
                staged = op_dir / f"{index}_{_slug(target['path'])}.staged"
            if not staged.is_file():
                return _bad(
                    f"targets[{index}].path",
                    f"{target['path']!r} is a write target of an unresolved "
                    "op but its staged-write evidence "
                    f"{name!r} is missing; journal evidence is corrupt",
                )
    # CORE-001: ONE strict authoritative decoder owns BOTH the immutable
    # operation.json manifest AND the bounded-progress sidecar progress.json.
    # Live execution writes mutable progress (status / progress_index /
    # applied_frontier) to the sidecar so it never rewrites the whole manifest
    # after every target; recovery/inspect/resolve/retry/scan must read the
    # SAME effective record, or a crash after canonical bytes changed is
    # misread as "nothing applied" and wrongly aborted (broken crash-recovery
    # invariant). The sidecar is optional for legacy receipts; a PRESENT but
    # unreadable/malformed/contradictory sidecar is REFUSED, never ignored.
    merged = _merge_progress_sidecar(
        op_dir,
        record,
        progress_raw=progress_raw,
        progress_captured=progress_captured,
    )
    if not merged["ok"]:
        return merged
    return {"ok": True, "record": record}


def _decode_progress_sidecar(
    progress_file: Path,
    n: int,
    base_status: object,
    *,
    raw: bytes | None = None,
) -> dict:
    """Strict decode of the bounded-progress sidecar progress.json (CORE-001).

    Returns {"ok": True, "status", "progress_index", "applied_frontier"} where
    each field is None when absent, or a stable refusal dict
    {"ok": False, "code": ..., "detail": ...} with ZERO writes. A PRESENT
    sidecar that is unreadable, malformed, out-of-range or contradictory with
    the immutable manifest is refused -- never silently ignored.
    """
    if raw is None:
        try:
            raw = progress_file.read_bytes()
        except OSError as exc:
            return {
                "ok": False,
                "code": "RECOVERY_CONFLICT",
                "detail": f"progress.json is unreadable: {exc}",
            }
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "code": "RECOVERY_CONFLICT",
            "detail": f"progress.json is not valid JSON: {exc}",
        }
    if not isinstance(data, dict):
        return {
            "ok": False,
            "code": "RECOVERY_CONFLICT",
            "detail": "progress.json is not a JSON object",
        }
    status = data.get("status")
    if status is not None and status not in STATUS:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"progress.json status {status!r} outside closed status set",
        }
    progress_index = data.get("progress_index")
    if progress_index is not None:
        if not isinstance(progress_index, int) or isinstance(progress_index, bool):
            return {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "progress.json progress_index must be an integer",
            }
        if progress_index < 0 or progress_index > n:
            return {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"progress.json progress_index {progress_index} out of range [0, {n}]",
            }
    applied_frontier = data.get("applied_frontier")
    if applied_frontier is not None:
        if not isinstance(applied_frontier, int) or isinstance(applied_frontier, bool):
            return {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": "progress.json applied_frontier must be an integer",
            }
        hi = max(n - 1, -1)
        if applied_frontier < -1 or applied_frontier > hi:
            return {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": (
                    f"progress.json applied_frontier {applied_frontier} out of range [-1, {hi}]"
                ),
            }
    # Contradiction: a sidecar claiming a terminal status while the immutable
    # manifest is still UNRESOLVED means fold_progress did not delete the
    # sidecar on settlement -- untrustworthy evidence, refuse rather than guess.
    if status in SETTLED and base_status not in SETTLED:
        return {
            "ok": False,
            "code": "RECOVERY_CONFLICT",
            "detail": f"progress.json claims terminal {status!r} but manifest "
            f"is {base_status!r}; settlement did not fold",
        }
    return {
        "ok": True,
        "status": status,
        "progress_index": progress_index,
        "applied_frontier": applied_frontier,
    }


def _merge_progress_sidecar(
    op_dir: Path,
    record: dict,
    *,
    progress_raw: bytes | None = None,
    progress_captured: bool = False,
) -> dict:
    """Merge progress.json into a decoded operation record (CORE-001).

    The sidecar is optional (legacy receipts have none). When present, its
    status / progress_index override the immutable manifest's and the applied
    prefix is derived deterministically from applied_frontier. Returns the
    refusal dict unchanged on sidecar failure; otherwise mutates `record` and
    returns {"ok": True}.
    """
    progress_file = op_dir / "progress.json"
    if progress_captured:
        if progress_raw is None:
            return {"ok": True}
    else:
        # ``Path.is_file`` follows symlinks and treats PRESENT non-files as
        # absence.  A journal sidecar is authority, so inspect the directory
        # entry itself and reject every unsafe PRESENT shape.
        try:
            progress_info = os.lstat(progress_file)
        except FileNotFoundError:
            return {"ok": True}
        except OSError as exc:
            return {
                "ok": False,
                "code": "RECOVERY_CONFLICT",
                "detail": f"progress.json stat failed: {exc}",
            }
        if stat.S_ISLNK(progress_info.st_mode) or getattr(
            progress_info, "st_file_attributes", 0
        ) & 0x400:
            return {
                "ok": False,
                "code": "RECOVERY_CONFLICT",
                "detail": "progress.json is a symlink or reparse point",
            }
        if not stat.S_ISREG(progress_info.st_mode):
            return {
                "ok": False,
                "code": "RECOVERY_CONFLICT",
                "detail": "progress.json is not a regular file",
            }
    prog = _decode_progress_sidecar(
        progress_file,
        len(record.get("targets") or []),
        record.get("status"),
        raw=progress_raw,
    )
    if not prog["ok"]:
        return prog
    if prog["status"] is not None:
        record["status"] = prog["status"]
    if prog["progress_index"] is not None:
        record["progress_index"] = prog["progress_index"]
    frontier = prog["applied_frontier"]
    if frontier is not None:
        targets = record.get("targets") or []
        for i in range(min(frontier + 1, len(targets))):
            targets[i]["applied"] = True
    return {"ok": True}


def scan_pending(project_root: Path | str) -> tuple[list[dict], list[dict]]:
    """ONE ephemeral recovery-manifest traversal returning ordered pending
    and conflict subsets from a single scan (T-1004 pending).

    Every public command / preflight calls this once and passes both lists
    downstream; pending_ops / pending_conflicts remain compatibility
    projections over the same result. NO persistent cache/index: recovery
    truth stays disk-authoritative and corrupt receipts stay visible, so a
    receipt added between two commands is observed immediately.

    Returns (pending, conflicts) where pending is OLDEST FIRST -- chronology
    is the validated created_at (never the directory name, which is op-id
    lexical and can disagree with creation order -- a z-op minted before an
    a-op must still recover first). The decoder already refused records whose
    created_at cannot parse, so every entry here has real chronology; equal
    timestamps break ties by op_id for a deterministic total order.
    """
    root = Path(project_root).resolve()
    ops_dir = root / OPS_DIR
    recovery_dir = ops_dir.parent  # .saipen/recovery
    found: list[dict] = []

    # ONE probe decides absence vs corruption, and it is `os.lstat` -- NOT
    # `.exists()` and NOT `os.path.lexists()` (hostile-regression, P1#6):
    #
    #   * `.exists()` FOLLOWS a broken symlink and reports it as absent, which
    #     launders a corrupt-evidence pointer into CLEAN;
    #   * `os.path.lexists()` swallows EVERY OSError into False, so an ops path
    #     whose PARENT is a file (NotADirectoryError) also reads as absent;
    #   * `os.lstat` does not follow the final symlink and raises a TYPED error,
    #     so exactly `FileNotFoundError` means "genuinely absent" and every
    #     other failure is malformed evidence that must surface.
    #
    # The RECOVERY container is probed FIRST because on some platforms (Windows)
    # `lstat` of an ops path whose PARENT is a file raises `FileNotFoundError`
    # too, which would otherwise be mistaken for "genuinely absent" -- a file
    # standing in for the recovery directory is corrupt evidence, never CLEAN.
    try:
        rec_info = os.lstat(recovery_dir)
    except FileNotFoundError:
        # No recovery container at all -> no ops dir either. Genuinely absent
        # -> CLEAN, no evidence to surface.
        return found, []
    except OSError as exc:
        found.append(
            {
                "op_id": "OPS_DIR",
                "status": "CORRUPT_JOURNAL",
                "corrupt": True,
                "detail": f"RECOVERY is unreadable ({type(exc).__name__}): {exc}",
            }
        )
        return found, []
    if os.path.islink(recovery_dir) or getattr(rec_info, "st_file_attributes", 0) & 0x400:
        found.append(
            {
                "op_id": "OPS_DIR",
                "status": "CORRUPT_JOURNAL",
                "corrupt": True,
                "detail": "RECOVERY is a symlink or reparse point",
            }
        )
        return found, []
    if not recovery_dir.is_dir():
        # The recovery container exists but is a FILE (or other non-dir): the
        # ops directory cannot live underneath it, so any pending op is
        # unrecoverable evidence.
        found.append(
            {
                "op_id": "OPS_DIR",
                "status": "CORRUPT_JOURNAL",
                "corrupt": True,
                "detail": "RECOVERY exists but is not a directory",
            }
        )
        return found, []
    # The recovery container is a real directory; now probe the ops dir exactly
    # as before -- only FileNotFoundError here means a genuinely absent ops dir.
    try:
        ops_info = os.lstat(ops_dir)
    except FileNotFoundError:
        return found, []  # genuinely absent -> CLEAN, no evidence to surface
    except OSError as exc:
        # Includes NotADirectoryError (a parent component is a file) and
        # PermissionError: corrupt evidence, never "nothing pending".
        found.append(
            {
                "op_id": "OPS_DIR",
                "status": "CORRUPT_JOURNAL",
                "corrupt": True,
                "detail": f"OPS_DIR is unreadable ({type(exc).__name__}): {exc}",
            }
        )
        return found, []
    if os.path.islink(ops_dir) or getattr(ops_info, "st_file_attributes", 0) & 0x400:
        found.append(
            {
                "op_id": "OPS_DIR",
                "status": "CORRUPT_JOURNAL",
                "corrupt": True,
                "detail": "OPS_DIR is a symlink or reparse point",
            }
        )
        return found, []
    if not ops_dir.is_dir():
        found.append(
            {
                "op_id": "OPS_DIR",
                "status": "CORRUPT_JOURNAL",
                "corrupt": True,
                "detail": "OPS_DIR exists but is not a directory",
            }
        )
        return found, []

    try:
        # Materialize the listing INSIDE the guarded operation: iterdir() is lazy,
        # so a deferred iteration-time PermissionError would otherwise escape as a
        # traceback instead of surfacing as CORRUPT evidence (hostile-regression,
        # P1#5 corrupt-evidence partition).
        entries = list(ops_dir.iterdir())
    except OSError as exc:
        found.append(
            {
                "op_id": "OPS_DIR",
                "status": "CORRUPT_JOURNAL",
                "corrupt": True,
                "detail": f"OPS_DIR entry listing failed: {exc}",
            }
        )
        return found, []

    for entry in entries:
        try:
            info = os.lstat(entry)
        except FileNotFoundError:
            # A raced deletion between listing and stat is genuine absence.
            continue
        except OSError as exc:
            # Everything else -- including NotADirectoryError, i.e. a malformed
            # parent component -- is CORRUPT_JOURNAL evidence (P1#6).
            found.append(
                {
                    "op_id": entry.name,
                    "status": "CORRUPT_JOURNAL",
                    "corrupt": True,
                    "detail": f"op_dir stat failed ({type(exc).__name__}): {exc}",
                }
            )
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            found.append(
                {
                    "op_id": entry.name,
                    "status": "CORRUPT_JOURNAL",
                    "corrupt": True,
                    "detail": "op_dir is a symlink or reparse point",
                }
            )
            continue
        if not stat.S_ISDIR(info.st_mode):
            # An unexpected NON-directory entry under recovery/ops (e.g. a
            # stray regular file) is corrupt evidence, never a launder into
            # CLEAN (second-wave P1): every entry under ops must be a valid
            # manifest-bearing op directory.
            found.append(
                {
                    "op_id": entry.name,
                    "status": "CORRUPT_JOURNAL",
                    "corrupt": True,
                    "detail": "unexpected non-directory entry under recovery/ops",
                }
            )
            continue
        if not (entry / "operation.json").is_file():
            # A directory with NO manifest is an interrupted pre-manifest
            # staging: staged target bytes were written but operation.json was
            # never published (second-wave P1). It must NOT be laundered into
            # CLEAN by `continue` -- that would let a later mutation proceed
            # over orphaned recovery evidence. Do not delete or guess the
            # staged bytes automatically; surface CORRUPT_JOURNAL and force an
            # explicit resolve.
            found.append(
                {
                    "op_id": entry.name,
                    "status": "CORRUPT_JOURNAL",
                    "corrupt": True,
                    "detail": "op directory has no operation.json "
                    "manifest (interrupted pre-manifest "
                    "staging?); orphan staged evidence must "
                    "be resolved explicitly",
                }
            )
            continue
        # Perf wave T-1020 + T-1008: a valid engine-written SETTLED marker
        try:
            decoded = decode_operation_record(root, entry)
        except Exception as exc:
            # Defense-in-depth: the decoder is the strict gate, but a receipt it
            # cannot even name must surface as CORRUPT evidence, never a
            # traceback that takes the whole project down.
            found.append(
                {
                    "op_id": entry.name,
                    "status": "CORRUPT_JOURNAL",
                    "corrupt": True,
                    "detail": f"operation record refused ({type(exc).__name__}): {exc}",
                }
            )
            continue
        if not decoded["ok"]:
            found.append(
                {
                    "op_id": entry.name,
                    "status": "CORRUPT_JOURNAL",
                    "corrupt": True,
                    "detail": decoded["detail"],
                }
            )
            continue
        record = decoded["record"]
        if record.get("status") not in SETTLED:
            found.append(
                {
                    "op_id": record["op_id"],
                    "status": record.get("status"),
                    "created_at": record.get("created_at", ""),
                }
            )
    # Order by the REAL UTC instant (never the original spelling); op_id is only
    # the equal-instant tiebreak. A spelling-only lexical sort reverses chronology
    # inside one second (e.g. `00Z` > `00.900000Z`), so the sort key is the
    # parsed datetime (P1#3).
    _earliest = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    found.sort(
        key=lambda op: (iso_utc_sort_key(op.get("created_at", "")) or _earliest, op["op_id"])
    )
    conflicts = [op for op in found if op.get("status") == "CONFLICT"]
    return found, conflicts


def pending_ops(project_root: Path | str) -> list[dict]:
    """Every UNRESOLVED operation journal, oldest first.

    PREPARED / APPLYING / VERIFIED / CONFLICT are all unresolved: they own
    mutation state that must be resolved before any new mutation. CONFLICT is
    excluded from SETTLED deliberately -- a conflict is evidence a mutation
    must stop at, not a permission to continue (NITRO dogfood II, T-587).

    A journal that fails the strict operation-record decoder is reported as
    CORRUPT (still unresolved: it blocks new mutation until resolved), never
    laundered into a healthy-looking PREPARED. Projection over the ONE
    scan_pending traversal (T-1004 pending).
    """
    return scan_pending(project_root)[0]


def pending_conflicts(project_root: Path | str) -> list[dict]:
    """Every CONFLICT journal -- stable evidence that still blocks mutation.
    Projection over the ONE scan_pending traversal (T-1004 pending)."""
    return scan_pending(project_root)[1]


def recovery_preflight(project_root: Path | str, exclude_op_id: str | None = None) -> dict:
    """Mandatory scan before any new mutation.

    - an unresolved CONFLICT exists -> REFUSE RECOVERY_CONFLICT, evidence
      preserved, exact op named (a conflict must be resolved explicitly).
    - CORRUPT journal evidence exists -> REFUSE CORRUPT_JOURNAL with zero
      Journal construction/replay: a receipt the strict decoder refused (or
      an op directory that failed its containment probe) is evidence that
      cannot be trusted, and a new mutation must never be planned on top of
      it -- recovery of corrupt evidence is an explicit human action, never
      an automatic attempt (hostile-regression corrupt-evidence partition).
    - none pending                 -> proceed
    - exactly one pending          -> recover it first
    - recovery hits conflict       -> refuse, evidence preserved
    - multiple pending             -> refuse RECOVERY_REQUIRED with op_ids

    Performs exactly ONE recovery-manifest traversal via scan_pending and
    derives both subsets from it (T-1004 pending)."""
    root = Path(project_root).resolve()
    pending, conflicts = scan_pending(root)
    corrupt = [op for op in pending if op.get("corrupt") and op["op_id"] != exclude_op_id]
    if corrupt:
        return {
            "ok": False,
            "code": "CORRUPT_JOURNAL",
            "op_ids": [op["op_id"] for op in corrupt],
            "recovery_required": True,
            "detail": (
                f"corrupt journal evidence {corrupt[0]['op_id']} "
                "blocks new mutation: "
                f"{corrupt[0].get('detail', '')} -- resolve the "
                "corrupt receipt explicitly before any further "
                "canonical write"
            ),
        }
    conflicts = [op for op in conflicts if op["op_id"] != exclude_op_id]
    if conflicts:
        return {
            "ok": False,
            "code": "RECOVERY_CONFLICT",
            "op_ids": [op["op_id"] for op in conflicts],
            "recovery_required": True,
            "detail": f"unresolved conflict {conflicts[0]['op_id']} "
            "blocks new mutation; resolve it explicitly (saipen "
            "recover) before any further canonical write",
        }
    pending = [op for op in pending if op["op_id"] != exclude_op_id]
    if not pending:
        return {"ok": True, "recovered": []}
    if len(pending) > 1:
        return {
            "ok": False,
            "code": "RECOVERY_REQUIRED",
            "op_ids": [op["op_id"] for op in pending],
            "recovery_required": True,
        }
    result = _recover_locked(root, pending[0]["op_id"])
    if not result["ok"]:
        return result
    return {"ok": True, "recovered": [pending[0]["op_id"]]}


class Journal:
    """Per-operation journal under .saipen/recovery/ops/<op_id>/."""

    def __init__(self, project_root: Path | str, op_id: str) -> None:
        # Canonical absolute root ONCE: every relative_to(self.project_root)
        # in this class must be relative-to-relative or absolute-to-absolute;
        # a relative root with resolved targets is the crash pair
        # (hostile-regression canonical-identity rule).
        self.project_root = Path(project_root).resolve()
        # op_id becomes a filesystem path under .saipen/recovery/ops: hostile
        # ids (../../x, absolute, drive-qualified) must never escape (T-1003
        # operational integrity).
        self.op_id = validate_op_id(op_id)

        # Prevent symlink/junction escape
        ops_op_dir = safe_op_dir(self.project_root, self.op_id, OPS_DIR)
        settled_op_dir = safe_op_dir(self.project_root, self.op_id, SETTLED_DIR)

        if settled_op_dir.is_dir() and not ops_op_dir.is_dir():
            self.dir = settled_op_dir
        else:
            self.dir = ops_op_dir

        self.manifest = self.dir / "operation.json"

    def exists(self) -> bool:
        return self.manifest.is_file()

    def start(
        self,
        operation: str,
        agent: str,
        project_identity: str,
        semantic_payload_hash: str,
        targets: list[dict],
        preconditions: dict | None = None,
        verification_policy: str = "none",
        read_preconditions: dict | None = None,
        receipt_metadata: dict | None = None,
        project_lineage: str | None = None,
    ) -> None:
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

        `project_lineage` is the durable PORTABLE lineage of the creating
        project (T-1003 carrier-loss wave). Recovery validates it against the
        live project before touching any target, so a receipt transplanted
        into another project can never mutate it. `project_identity` remains
        the machine-local runtime binding (lock spelling identity), never
        portable evidence.
        """
        if verification_policy not in VERIFICATION_POLICIES:
            raise ValueError(
                f"verification_policy {verification_policy!r} outside "
                f"{sorted(VERIFICATION_POLICIES)}"
            )
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            # Re-check after mkdir (T-1004 journal integrity)
            safe_op_dir(self.project_root, self.op_id)
            record_targets = []
            for index, target in enumerate(targets):
                # One owned-target resolver for staging too: a target path must be
                # relative + inside the project before its name becomes a staged
                # file (T-1003 operational integrity).
                canonical = owned_target_path(self.project_root, target["path"])
                action = _target_action(target)
                if action == "write":
                    content = target["content"]
                    if isinstance(content, str):
                        content = content.encode("utf-8")
                    name = staged_name(index, canonical.relative_to(self.project_root).as_posix())
                    (self.dir / name).write_bytes(content)
                record_targets.append(
                    {
                        "path": target["path"],
                        "role": target["role"],
                        "action": action,
                        "before_hash": target["before_hash"],
                        "after_hash": target["after_hash"],
                        "applied": False,
                    }
                )
            record = {
                "op_id": self.op_id,
                "operation": operation,
                "created_at": _now(),
                "agent": agent,
                "project_identity": project_identity,
                "project_lineage": project_lineage,
                "semantic_payload_hash": semantic_payload_hash,
                "preconditions": preconditions or {},
                "read_preconditions": read_preconditions or {},
                "verification_policy": verification_policy,
                "status": "PREPARED",
                "progress_index": 0,
                "targets": record_targets,
            }
            normalized_metadata, metadata_error = _canonical_receipt_metadata(receipt_metadata)
            if metadata_error is not None:
                raise ValueError(f"receipt_metadata {metadata_error}")
            if normalized_metadata is not None:
                record["receipt_metadata"] = normalized_metadata
            # Manifest publication INSIDE the cleanup guard: a record write
            # that fails after staging (unserializable metadata, disk error)
            # must not leave an orphan op dir full of staged bytes with no
            # manifest to name them (hostile-regression zero-orphan rule).
            _atomic_json(self.manifest, record)
        except Exception:
            import shutil

            shutil.rmtree(self.dir, ignore_errors=True)
            raise

    def mark(
        self, status: str, progress_index: int | None = None, target_index: int | None = None
    ) -> None:
        progress_file = self.dir / "progress.json"
        prog = {}
        if progress_file.is_file():
            with contextlib.suppress(Exception):
                prog = json.loads(progress_file.read_text(encoding="utf-8"))
        prog["status"] = status
        if progress_index is not None:
            prog["progress_index"] = progress_index
        if target_index is not None:
            prog["applied_frontier"] = max(prog.get("applied_frontier", -1), target_index)
        _atomic_json(progress_file, prog)

        if status in SETTLED:
            self.fold_progress()
            _settle_journal(self)

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
        if record.get("status") in SETTLED:
            raise ValueError(
                f"cannot append targets to terminal operation {self.op_id!r} "
                f"with status {record.get('status')!r}"
            )
        record_targets = record.setdefault("targets", [])
        for target in targets:
            index = len(record_targets)
            action = _target_action(target)
            # ONE canonical owned identity + ONE bounded staged-name scheme
            # (hostile-regression): the same resolver and name builder the
            # initial staging uses, so recovery finds appended evidence by the
            # same rule and a deep path can never overflow a filesystem name
            # (OSError Errno 36). The slug-based name is read-compatible only.
            canonical = owned_target_path(self.project_root, target["path"])
            rel = canonical.relative_to(self.project_root).as_posix()
            if action == "write":
                content = target["content"]
                if isinstance(content, str):
                    content = content.encode("utf-8")
                (self.dir / staged_name(index, rel)).write_bytes(content)
            new_target = dict(target)
            new_target["path"] = rel
            record_targets.append(
                {
                    "path": new_target["path"],
                    "role": new_target.get("role", "generic"),
                    "action": action,
                    "before_hash": new_target.get("before_hash", ""),
                    "after_hash": new_target.get("after_hash", ""),
                    "applied": False,
                }
            )
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
        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        progress_file = self.dir / "progress.json"
        if progress_file.is_file():
            try:
                prog = json.loads(progress_file.read_text(encoding="utf-8"))
                if "status" in prog:
                    record["status"] = prog["status"]
                if "progress_index" in prog:
                    record["progress_index"] = prog["progress_index"]
                frontier = prog.get("applied_frontier", -1)
                targets = record.get("targets", [])
                for i in range(min(frontier + 1, len(targets))):
                    targets[i]["applied"] = True
            except Exception:
                pass
        return record

    def fold_progress(self) -> None:
        progress_file = self.dir / "progress.json"
        if progress_file.is_file():
            try:
                record = self.read()
                _atomic_json(self.manifest, record)
                progress_file.unlink()
            except OSError:
                pass

    def staged_content(self, index: int, record: dict | None = None) -> bytes:
        # PERF-001: when the caller already holds the strict-decoded operation
        # record (e.g. the recovery attempt that decoded it once), pass it here
        # so we skip the O(N) receipt re-parse per target. Without `record`,
        # behaviour is unchanged: the receipt is decoded on demand.
        if record is None:
            record = self.read()
        target_path = record["targets"][index]["path"]
        canonical = (
            owned_target_path(self.project_root, target_path)
            .relative_to(self.project_root)
            .as_posix()
        )
        name = staged_name(index, canonical)
        f = self.dir / name
        if not f.exists():
            f = self.dir / f"{index}_{_slug(target_path)}.staged"
        return f.read_bytes()


def _drop_settled_staged(journal: "Journal") -> None:
    """Best-effort delete an op's `.staged` payloads after terminal COMMITTED.

    COMMITTED ops never participate in recovery -- idempotent retry only
    needs the compact tombstone -- so their staged bytes are dead weight
    that would otherwise accumulate unbounded across a long session (perf
    pass). The terminal manifest write has ALREADY succeeded and is durable;
    cleanup failure must never rewrite semantic status or fail a successful
    operation, so every failure is suppressed. `compact_committed` remains
    as the explicit repair/legacy sweep for leftovers and interrupted
    cleanup. NEVER called for PREPARED/APPLYING/VERIFIED/CONFLICT/ABORTED.

    PERF-005: if a staged unlink fails, the op_id is durably enqueued in the
    bounded cleanup queue so the next `compact_committed` removes the leftover
    payload without re-scanning the entire settled ledger.
    """
    queue = journal.project_root / CLEANUP_QUEUE_DIR
    debt = False
    for staged in journal.dir.glob("*.staged"):
        try:
            staged.unlink()
        except OSError:
            debt = True
    if debt:
        from .safeid import InvalidIdError

        with contextlib.suppress(OSError, InvalidIdError):
            queue.mkdir(parents=True, exist_ok=True)
            # Re-prove containment after mkdir: an engine-owned cleanup queue
            # may never be replaced by a symlink/junction that redirects the
            # durable debt marker outside the project.
            marker = safe_op_dir(
                journal.project_root,
                journal.op_id,
                CLEANUP_QUEUE_DIR,
            )
            marker.write_text("")


def _verify_target_bytes(root: Path, targets: list[dict]) -> str | None:
    """Verify every target reached its planned bytes or absence."""
    for target in targets:
        live = _target_live_hash(root, target)
        if live != target["after_hash"]:
            return (
                f"target {target['path']}: live {live!r} != planned after {target['after_hash']!r}"
            )
    return None


def _recovery_identity_binding(root: Path, record: dict) -> dict:
    """Bind a recovery receipt to the project that created it (T-1003
    carrier-loss wave).

    Portable lineage is authoritative for NEW strict receipts: the receipt's
    lineage must equal the live project's lineage, or recovery REFUSES with
    ZERO writes -- a receipt transplanted from project A can never mutate
    project B, and the same project moved to a new path keeps its tracked
    lineage so its pending recovery remains valid.

    LEGACY receipts (created before lineage existed) carry no lineage field.
    They are recoverable ONLY at the exact runtime path that created them
    (explicit compatibility boundary). A moved ambiguous legacy receipt
    refuses: without lineage there is no way to prove it belongs here.
    """
    from .paths import project_lineage_identity, runtime_lock_identity

    record_lineage = record.get("project_lineage")
    if record_lineage:
        live_lineage = project_lineage_identity(root)
        if not live_lineage or live_lineage != record_lineage:
            return {
                "ok": False,
                "code": "PROJECT_MISMATCH",
                "recovery_required": True,
                "detail": (
                    f"receipt lineage {record_lineage!r} does not "
                    f"match this project's lineage "
                    f"{live_lineage!r}; refuse cross-project "
                    "recovery with zero writes"
                ),
            }
        return {"ok": True}
    # Legacy receipt without a durable lineage.
    record_runtime = record.get("project_identity")
    live_runtime = runtime_lock_identity(root)
    if not record_runtime:
        return {
            "ok": False,
            "code": "PROJECT_MISMATCH",
            "recovery_required": True,
            "detail": "receipt has no project lineage and no runtime "
            "identity; refuse to guess which project owns it",
        }
    if record_runtime != live_runtime:
        return {
            "ok": False,
            "code": "PROJECT_MISMATCH",
            "recovery_required": True,
            "detail": (
                "legacy receipt (no lineage) was created at "
                f"{record_runtime!r}, not the current project "
                f"{live_runtime!r}; a moved ambiguous legacy "
                "receipt must refuse"
            ),
        }
    return {"ok": True}


class LineageRefusal(RuntimeError):
    """Fail-closed refusal from the lineage bootstrap (T-1003 carrier-loss
    wave): the carrier is missing/malformed after settled migration evidence,
    so minting a fresh lineage would orphan every receipt bound to the old
    one. Carries the stable refusal code the caller converts into its own
    structured refusal shape."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _read_lineage_strict(root: Path) -> tuple[str | None, str | None]:
    """(lineage, error) from the canonical carrier. Absent file -> (None, None)
    (never-migrated); present-but-unparseable -> (None, error) (malformed,
    fail-closed material -- distinct from absent so the bootstrap never
    overwrites a present carrier)."""
    from .paths import parse_identity_content

    path = root / ".saipen" / "IDENTITY.md"
    if not path.is_file():
        return None, None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, f"unreadable: {exc}"
    return parse_identity_content(text)


def ensure_project_lineage(root: Path | str) -> str:
    """Return this project's durable portable lineage, creating it journaled
    if absent (T-1003 carrier-loss wave).

    The lineage lives in the tracked `.saipen/IDENTITY.md` so it survives Git
    clone, directory moves and machine replacement. Creation is itself a
    journaled mutation (the dedicated `op-migrate-lineage` op), so a crash
    mid-migration is recovered like any other operation. The migration op is
    a legacy-style receipt (it cannot carry a lineage it is creating) and is
    therefore recoverable only at the same runtime path.

    Fail-closed bootstrap (T-1003 hostile findings):
    - the COMPLETE request is validated before any lineage write, so an
      invalid mutation never mints a lineage (run_mutation validates first);
    - a PRESENT but malformed carrier is never overwritten -- the file may
      hold the project's only durable identity;
    - after a settled migration (COMMITTED), a missing/malformed carrier
      REFUSES instead of minting a second lineage -- the next mutation cannot
      COMMIT a receipt carrying a phantom lineage no recovery can ever match;
    - after a fresh migration, only the EXACT persisted value is returned.

    Caller must hold the project writer lock (this never acquires it).
    Raises LineageRefusal on any fail-closed condition.
    """
    from .paths import identity_file_content, new_project_lineage, runtime_lock_identity
    import shutil

    root = Path(root)
    lineage, error = _read_lineage_strict(root)
    if lineage:
        return lineage
    if error:
        raise LineageRefusal(
            "RECOVERY_REQUIRED",
            f".saipen/IDENTITY.md is present but malformed ({error}); refuse "
            "to mint or overwrite a lineage -- restore the canonical carrier "
            "or resolve explicitly",
        )
    journal = Journal(root, LINEAGE_MIGRATION_OP)
    if journal.exists():
        # Crash-left migration: finish it first, then re-read. Callers of
        # ensure_project_lineage may already hold the writer lock (mutation
        # entry points), so the locked body is used and never re-acquired.
        result = _recover_locked(root, LINEAGE_MIGRATION_OP)
        if result.get("code") == "ABORTED":
            # Zero applied targets -- whether THIS call aborted a fresh
            # PREPARED op, or a prior recovery already marked it ABORTED (an
            # already-aborted journal recovers as ok:false/ABORTED): the
            # migration genuinely never happened. Retire the zero-effect
            # aborted journal and migrate fresh (the fixed op_id cannot be
            # replayed otherwise).
            shutil.rmtree(journal.dir, ignore_errors=True)
        elif not result["ok"]:
            raise LineageRefusal(
                result.get("code", "RECOVERY_REQUIRED"),
                f"lineage migration recovery failed: {result.get('detail', '')}",
            )
        else:
            lineage, error = _read_lineage_strict(root)
            if lineage:
                return lineage
            raise LineageRefusal(
                "RECOVERY_REQUIRED",
                f"lineage migration evidence is settled "
                f"({result.get('code')}) but .saipen/IDENTITY.md is "
                f"{'missing' if not error else f'malformed ({error})'}; "
                "refuse to mint a new lineage -- restore the carrier or "
                "resolve explicitly",
            )
    lineage = new_project_lineage()
    result = run_mutation(
        root,
        LINEAGE_MIGRATION_OP,
        "migrate_lineage",
        "saipen",
        runtime_lock_identity(root),
        "lineage-migration",
        [
            {
                "path": ".saipen/IDENTITY.md",
                "role": "manifest",
                "action": "write",
                "content": identity_file_content(lineage),
            }
        ],
        verification_policy="none",
        _ensure_lineage=False,
    )
    if not result["ok"]:
        raise LineageRefusal(
            result.get("code", "RECOVERY_REQUIRED"),
            f"lineage migration failed: {result.get('detail', '')}",
        )
    # Migration COMMITTED: return ONLY the exact persisted value -- never the
    # minted one, so a write that silently did not land cannot hand out a
    # phantom lineage.
    persisted, error = _read_lineage_strict(root)
    if persisted:
        return persisted
    raise LineageRefusal(
        "RECOVERY_REQUIRED",
        f"lineage migration COMMITTED but .saipen/IDENTITY.md is "
        f"{'missing' if not error else f'malformed ({error})'}; refuse to "
        "return an unpinned lineage",
    )


def validate_mutation_request(
    project_root: Path | str,
    op_id: str,
    operation: str,
    agent: str,
    project_identity: str,
    semantic_payload_hash: str,
    targets: list[dict],
    preconditions: dict | None = None,
    verification_policy: str = "none",
    read_preconditions: dict | None = None,
    receipt_metadata: dict | None = None,
) -> dict:
    """ONE pure validation gate for mutation requests (hostile-regression).

    Runs BEFORE any Journal construction or disk write, so a malformed probe
    fails with VALIDATION_FAILED and zero changes -- no op directory, no
    staged bytes, no journal manifest. Every run_mutation (and every future
    entry point) routes its request through here; no caller may re-implement
    a fragment of this contract.

    Returns {"ok": True, "targets": [...], "preconditions": {...},
             "read_preconditions": {...}} with canonicalized owned paths, or
    {"ok": False, "code": "VALIDATION_FAILED", "op_id": op_id,
     "recovery_required": False, "detail": <reason>}.
    """
    from .safeid import InvalidIdError

    def refuse(detail: str) -> dict:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "op_id": op_id,
            "recovery_required": False,
            "detail": detail,
        }

    # Canonical absolute root ONCE: owned identities are "resolved path
    # relative to resolved root", so relative and resolved forms can never
    # mix in a relative_to() crash.
    root = Path(project_root).resolve()
    try:
        validate_op_id(op_id)
    except InvalidIdError as exc:
        return refuse(f"op_id is not a safe path component: {exc}")
    for name, value in (
        ("operation", operation),
        ("agent", agent),
        ("project_identity", project_identity),
        ("semantic_payload_hash", semantic_payload_hash),
    ):
        if not isinstance(value, str) or not value:
            return refuse(f"{name} must be a non-empty string")
    if verification_policy not in VERIFICATION_POLICIES:
        return refuse(
            f"verification_policy {verification_policy!r} outside {sorted(VERIFICATION_POLICIES)}"
        )
    if not isinstance(preconditions, (dict, type(None))):
        return refuse("preconditions must be a path->hash map")
    if not isinstance(read_preconditions, (dict, type(None))):
        return refuse("read_preconditions must be a path->hash map")
    normalized_metadata, metadata_error = _canonical_receipt_metadata(receipt_metadata)
    if metadata_error is not None:
        return refuse(f"receipt_metadata {metadata_error}")
    if normalized_metadata is not None:
        try:
            json.dumps(normalized_metadata, sort_keys=True)
        except (TypeError, ValueError) as exc:
            return refuse(f"receipt_metadata is not JSON-serializable: {exc}")
    if not isinstance(targets, list):
        return refuse("targets must be a list of target mappings")

    try:
        seen_target_paths: set[str] = set()
        canonical_targets = []
        for index, target in enumerate(targets):
            if not isinstance(target, dict):
                return refuse("every target must be a mapping")
            path = target.get("path")
            if not isinstance(path, str) or not path:
                return refuse("target path must be a non-empty string")
            canonical = owned_target_path(root, path).relative_to(root).as_posix()
            if canonical in seen_target_paths:
                return refuse(
                    f"duplicate target path {canonical!r}: one path may "
                    "be planned at most once per operation"
                )
            seen_target_paths.add(canonical)
            role = target.get("role", "generic")
            if role not in ROLES:
                return refuse(f"target {path}: role {role!r} outside {'/'.join(ROLES)}")
            action = target.get("action", "write")
            if action not in TARGET_ACTIONS:
                return refuse(
                    f"target {path}: action {action!r} outside {'/'.join(TARGET_ACTIONS)}"
                )
            if action == "write":
                content = target.get("content")
                if content is None:
                    return refuse(f"target {path}: write action requires content")
                if not isinstance(content, (str, bytes)):
                    return refuse(f"target {path}: write content must be str or bytes")
            # Keep mutated target with canonical path
            new_target = dict(target)
            new_target["path"] = canonical
            canonical_targets.append(new_target)

        canonical_preconditions = {}
        for path, hash_val in (preconditions or {}).items():
            if not isinstance(path, str) or not path:
                return refuse("precondition keys must be non-empty strings")
            if not isinstance(hash_val, str):
                # None (or anything non-str) would crash the verifier's
                # token dispatch -- refuse it. "" is NOT refused: it is the
                # deliberate "expect absent" token first-write plans use,
                # and _target_live_hash hashes an absent file as "" so the
                # STALE_STATE pass compares like forms (hostile sweep fix:
                # an over-strict non-empty rule rejected every legitimate
                # first-write plan, e.g. sub_sync seeding a fresh project).
                return refuse(
                    f"precondition {path}: value must be a "
                    'string hash token (or "" for an expected-'
                    "absent file)"
                )
            can = owned_target_path(root, path, kind="precondition").relative_to(root).as_posix()
            canonical_preconditions[can] = hash_val

        canonical_read_preconditions = {}
        for path, hash_val in (read_preconditions or {}).items():
            if not isinstance(path, str) or not path:
                return refuse("read_preconditions keys must be non-empty strings")
            if not isinstance(hash_val, str):
                return refuse(
                    f"read_preconditions {path}: value must be a "
                    'string hash token (or "" for an expected-'
                    "absent file)"
                )
            # ONE read identity (hostile-regression): only an EXPLICITLY
            # absolute read stays absolute (external dependencies like the
            # SAIPEN home); a relative read resolves through the same owned
            # resolver and is persisted as canonical-relative POSIX, so the
            # owned-vs-read overlap gate compares like forms -- otherwise a
            # target `x.txt` plus a read dependency `x.txt` commits because
            # the read identity became absolute while the target stayed
            # relative.
            if Path(path).is_absolute():
                can_str = read_dependency_path(root, path).as_posix()
            else:
                can_str = read_dependency_path(root, path).relative_to(root).as_posix()
            canonical_read_preconditions[can_str] = hash_val
    except InvalidIdError as exc:
        return refuse(f"target/precondition path escapes the project: {exc}")

    owned_vs_read = seen_target_paths & set(canonical_read_preconditions)
    if owned_vs_read:
        return refuse(
            "target path(s) also declared as read-only "
            "dependencies: "
            + ", ".join(sorted(owned_vs_read))
            + " -- one path cannot be both owned and a "
            "read-only dependency in one operation"
        )

    return {
        "ok": True,
        "targets": canonical_targets,
        "preconditions": canonical_preconditions,
        "read_preconditions": canonical_read_preconditions,
        "receipt_metadata": normalized_metadata,
    }


def run_mutation(
    project_root: Path | str,
    op_id: str,
    operation: str,
    agent: str,
    project_identity: str,
    semantic_payload_hash: str,
    targets: list[dict],
    preconditions: dict | None = None,
    verify: object | None = None,
    skip_preflight: bool = False,
    verification_policy: str = "none",
    read_preconditions: dict | None = None,
    receipt_metadata: dict | None = None,
    receipt_metadata_finalize: object | None = None,
    _ensure_lineage: bool = True,
) -> dict:
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
    root = Path(project_root).resolve()
    # 1. COMPLETE PURE REQUEST VALIDATION FIRST -- one shared gate, before
    # any Journal construction or disk write, so a malformed probe fails
    # with VALIDATION_FAILED and zero changes (hostile-regression).
    validated = validate_mutation_request(
        root,
        op_id,
        operation,
        agent,
        project_identity,
        semantic_payload_hash,
        targets,
        preconditions,
        verification_policy,
        read_preconditions,
        receipt_metadata,
    )
    if not validated["ok"]:
        return validated
    targets = validated["targets"]
    preconditions = validated["preconditions"]
    read_preconditions = validated["read_preconditions"]
    receipt_metadata = validated["receipt_metadata"]

    journal = Journal(root, op_id)

    def dependency_path(path: str) -> Path:
        return read_dependency_path(root, path, kind="dependency")

    if journal.exists():
        # The existing journal is disk evidence: decode it strictly -- a
        # hostile/malformed record refuses cleanly instead of crashing.
        decoded = decode_operation_record(root, journal.dir)
        if not decoded["ok"]:
            return {
                "ok": False,
                "code": decoded["code"],
                "op_id": op_id,
                "recovery_required": True,
                "detail": decoded["detail"],
            }
        record = decoded["record"]

        # Verify semantic idempotence: the request must exactly match the record
        # (T-1003 idempotence collision wave).
        expected_lineage = record.get("project_lineage")
        # STRICT live-project binding BEFORE any idempotence/dispatch decision
        # (hostile-regression): a receipt whose carrier was deleted, malformed
        # or transplanted must refuse with PROJECT_MISMATCH / RECOVERY_REQUIRED
        # and zero changes -- ALREADY_APPLIED is never blessed against an
        # unbound receipt, and a missing carrier is never recreated, ignored
        # or silently re-minted here. This is the SAME binding recovery uses,
        # so the retry path and the recovery path cannot diverge.
        binding = _recovery_identity_binding(root, record)
        if not binding["ok"]:
            return {
                "ok": False,
                "code": binding["code"],
                "op_id": op_id,
                "recovery_required": True,
                "detail": binding["detail"],
            }
        if _ensure_lineage and expected_lineage:
            try:
                live_lineage = ensure_project_lineage(root)
                if live_lineage != expected_lineage:
                    return {
                        "ok": False,
                        "code": "PROJECT_MISMATCH",
                        "op_id": op_id,
                        "recovery_required": False,
                        "detail": "lineage changed since receipt was created",
                    }
            except LineageRefusal as exc:
                return {
                    "ok": False,
                    "code": exc.code,
                    "op_id": op_id,
                    "recovery_required": True,
                    "detail": exc.detail,
                }

        request_targets = []
        for index, target in enumerate(targets):
            action = target.get("action", "write")
            if action == "write":
                content = target["content"]
                after_hash = hash_bytes(
                    content.encode("utf-8") if isinstance(content, str) else content
                )
            else:
                after_hash = ""
            request_targets.append(
                {
                    "path": target["path"],
                    "role": target.get("role", "generic"),
                    "action": action,
                    "after_hash": after_hash,
                }
            )

        # W2-004: include normalized meaning-bearing receipt_metadata in the
        # retry semantic identity so a changed ticket/crew authority under
        # the same op_id is a semantic collision, not ALREADY_APPLIED.
        # Finalizer-owned derived keys (resulting_*) are excluded because
        # they are generated only after apply.
        _REQUEST_METADATA_KEYS = (
            "crew_epoch", "ticket_id", "producer", "package_identity",
            "input_source", "input_source_fingerprint", "role", "stage",
            "verdict", "source_head", "source_tree_fingerprint",
        )
        _request_meta = {}
        if receipt_metadata:
            for _k in _REQUEST_METADATA_KEYS:
                if _k in receipt_metadata:
                    _request_meta[_k] = receipt_metadata[_k]
        fingerprint = {
            "operation": operation,
            "semantic_payload_hash": semantic_payload_hash,
            "verification_policy": verification_policy,
            "targets": request_targets,
            "receipt_metadata": _request_meta,
        }
        computed_semantic = hashlib.sha256(
            json.dumps(fingerprint, sort_keys=True).encode("utf-8")
        ).hexdigest()

        _record_meta = {}
        _record_raw_meta = record.get("receipt_metadata")
        if isinstance(_record_raw_meta, dict):
            for _k in _REQUEST_METADATA_KEYS:
                if _k in _record_raw_meta:
                    _record_meta[_k] = _record_raw_meta[_k]
        record_fingerprint = {
            "operation": record.get("operation"),
            "semantic_payload_hash": record.get("semantic_payload_hash"),
            "verification_policy": record.get("verification_policy"),
            "targets": [
                {
                    "path": t["path"],
                    "role": t.get("role", "generic"),
                    "action": t.get("action", "write"),
                    "after_hash": t.get("after_hash", ""),
                }
                for t in record.get("targets", [])
            ],
            "receipt_metadata": _record_meta,
        }
        record_semantic = hashlib.sha256(
            json.dumps(record_fingerprint, sort_keys=True).encode("utf-8")
        ).hexdigest()

        if computed_semantic != record_semantic:
            return {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "op_id": op_id,
                "recovery_required": False,
                "detail": "op_id collision: semantic payload does not match existing receipt",
            }

        if record["status"] == "COMMITTED":
            return {
                "ok": True,
                "code": "ALREADY_APPLIED",
                "op_id": op_id,
                "recovery_required": False,
            }
        return {
            "ok": False,
            "code": "RECOVERY_REQUIRED",
            "op_id": op_id,
            "recovery_required": True,
            "detail": f"op {op_id} is already {record['status']}; recover it first",
        }

    # Preflight BEFORE lineage migration: an unresolved CONFLICT or pending
    # op must refuse cleanly (RECOVERY_CONFLICT / RECOVERY_REQUIRED), not
    # raise inside the lineage-migration op (T-1003 carrier-loss wave).
    if not skip_preflight:
        preflight = recovery_preflight(root, exclude_op_id=op_id)
        if not preflight["ok"]:
            return preflight

    if _ensure_lineage:
        try:
            lineage = ensure_project_lineage(root)
        except LineageRefusal as exc:
            return {
                "ok": False,
                "code": exc.code,
                "op_id": op_id,
                "recovery_required": True,
                "detail": exc.detail,
            }
    else:
        lineage = None

    # Compute truthful per-action before/after states.
    prepared = []
    for target in targets:
        path = target["path"]
        role = target.get("role", "generic")
        action = target.get("action", "write")
        probe = {"path": path, "action": action}
        if action == "write":
            content = target["content"]
            if isinstance(content, str):
                content = content.encode("utf-8")
            prepared.append(
                {
                    "path": path,
                    "role": role,
                    "action": action,
                    "content": content,
                    "before_hash": _target_live_hash(root, probe),
                    "after_hash": hash_bytes(content),
                }
            )
        else:
            before = (
                target.get("planned_before_hash")
                if action == "delete_dir"
                else _target_live_hash(root, probe)
            )
            prepared.append(
                {
                    "path": path,
                    "role": role,
                    "action": action,
                    "before_hash": before,
                    "after_hash": "",
                }
            )

    # Every WRITE target and every read-only dependency must match the
    # hashes captured at plan time.
    prepared_by_path = {target["path"]: target for target in prepared}
    for path, expected in (preconditions or {}).items():
        target = prepared_by_path.get(path)
        # OperationPlan keeps write and read dependencies in one immutable
        # precondition map. Non-targets may be file, tree, or source-identity
        # tokens; treating every one as a write/file makes valid tree CAS
        # fail as an empty file hash before the read-only pass can check it.
        actual = (
            _target_live_hash(root, target)
            if target is not None
            else _hash_dependency(dependency_path(path), expected)
        )
        if actual != expected:
            return {
                "ok": False,
                "code": "STALE_STATE",
                "op_id": op_id,
                "detail": f"precondition {path} changed (live {actual!r}, expected {expected!r})",
            }
    for path, expected in (read_preconditions or {}).items():
        actual = _hash_dependency(dependency_path(path), expected)
        if actual != expected:
            return {
                "ok": False,
                "code": "STALE_STATE",
                "op_id": op_id,
                "detail": f"read dependency {path} changed (live "
                f"{actual!r}, expected {expected!r})",
            }

    journal.start(
        operation,
        agent,
        project_identity,
        semantic_payload_hash,
        prepared,
        preconditions,
        verification_policy=verification_policy,
        read_preconditions=read_preconditions,
        receipt_metadata=receipt_metadata,
        project_lineage=lineage,
    )
    _crash_after("PREPARED")

    journal.mark("APPLYING")
    for index, target in enumerate(prepared):
        live = _target_live_hash(root, target)
        action = _target_action(target)
        if live == target["after_hash"]:
            journal.mark("APPLYING", progress_index=index + 1, target_index=index)
            # A semantic commit boundary still exists when this target was
            # already at its planned value. Crash probes model interruption
            # after roles (LOG/BOARD/STATE), not only after changed bytes.
            _crash_after(target["role"] if action == "write" else action)
            continue
        if live != target["before_hash"]:
            journal.mark("CONFLICT")
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": f"target {target['path']} has third state "
                f"{live!r}; before {target['before_hash']!r}, "
                f"after {target['after_hash']!r}",
            }
        try:
            if action == "write":
                _atomic_write(root / target["path"], target["content"])
            elif action == "delete_file":
                (root / target["path"]).unlink()
            elif action == "delete_dir":
                (root / target["path"]).rmdir()
            else:  # unreachable after request validation; refuse, never fall
                return {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "op_id": op_id,
                    "recovery_required": False,
                    "detail": f"target {target['path']} carries an "
                    f"unknown action {action!r}; refusing to "
                    "dispatch a destructive fallback",
                }
        except OSError as exc:
            journal.mark("CONFLICT")
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": f"target {target['path']} action failed: {exc}",
            }
        after = _target_live_hash(root, target)
        if after != target["after_hash"]:
            journal.mark("CONFLICT")
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": f"target {target['path']} action left {after!r}, "
                f"expected {target['after_hash']!r}",
            }
        journal.mark("APPLYING", progress_index=index + 1, target_index=index)
        _crash_after(target["role"] if action == "write" else action)

    byte_error = _verify_target_bytes(root, prepared)
    if byte_error:
        journal.mark("CONFLICT")
        return {
            "ok": False,
            "code": "CONFLICT",
            "op_id": op_id,
            "recovery_required": True,
            "detail": f"post-write byte verification failed: {byte_error}",
        }

    # Some operation metadata is knowable only after the journal has applied
    # and byte-verified its targets (producer S0 -> S1 is the canonical case).
    # Persist it inside the still-live operation before VERIFIED/COMMITTED, so
    # the terminal receipt and its settled twin remain exactly equivalent.
    if receipt_metadata_finalize is not None:
        try:
            finalized = receipt_metadata_finalize(root, dict(receipt_metadata or {}))
            if not isinstance(finalized, dict):
                raise TypeError("metadata finalizer must return a dict")
            normalized_finalized, metadata_error = _canonical_receipt_metadata(finalized)
            if metadata_error is not None:
                raise TypeError(f"metadata finalizer result {metadata_error}")
            if normalized_finalized is None:
                normalized_finalized = {}
            json.dumps(normalized_finalized, sort_keys=True)
            receipt_metadata = normalized_finalized
            journal.update(receipt_metadata=normalized_finalized)
        except Exception as exc:
            journal.mark("CONFLICT")
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": f"post-write receipt metadata failed: {exc}",
            }

    # Semantic verification runs BEFORE VERIFIED -- and it is the SAME
    # postcondition class the recovery path runs from the journaled policy
    # (NITRO dogfood IV, T-601): a named policy verifier is invoked here on
    # APPLY with the actual changed targets, so APPLY and Recovery can never
    # disagree about what a verified result means. The legacy caller-supplied
    # `verify` callable remains the fallback for a "none" policy.
    if verification_policy != "none":
        errors = _run_verifier(root, prepared, verification_policy, receipt_metadata)
        if errors:
            journal.mark("CONFLICT")
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": "post-write semantic verification (policy "
                f"{verification_policy}) failed: " + "; ".join(errors[:5]),
            }
    elif verify is not None:
        errors = verify(root)
        if errors:
            journal.mark("CONFLICT")
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": "post-write cross-file validation failed: " + "; ".join(errors[:5]),
            }
    _crash_after("VERIFIED")

    journal.mark("VERIFIED")
    journal.mark("COMMITTED")
    _drop_settled_staged(journal)
    return {
        "ok": True,
        "code": "COMMITTED",
        "op_id": op_id,
        "changed_files": [t["path"] for t in prepared],
        "recovery_required": False,
    }


def recover(project_root: Path | str, op_id: str) -> dict:
    """Recovery is a MUTATING writer (it applies targets, rewrites files and
    journals terminal status), so the public entry acquires the canonical
    project writer lock before the first journal read and holds it through
    target/byte/Git verification and the terminal status write. Two concurrent
    `saipen recover` invocations (or a recover racing a normal mutation) must
    serialize: exactly one writer, the loser refuses WRITER_BUSY -- never two
    writers classifying/writing the same targets or diverging on receipt
    status (T-1003 recovery serialization). The locked body is
    `_recover_locked`; internal callers that already run under a caller-held
    lock call `_recover_locked` directly and never re-acquire."""
    root = Path(project_root)
    from .lock import project_writer_lock as _recover_lock

    try:
        with _recover_lock(root):
            return _recover_locked(root, op_id)
    except PermissionError:
        return {
            "ok": False,
            "code": "WRITER_BUSY",
            "op_id": op_id,
            "detail": "another live writer holds the project lock; retry after it releases",
        }


def _recover_locked(root: Path, op_id: str) -> dict:
    """Roll-forward, conflict-safe recovery (NITRO dogfood II).

    Called ONLY under the project writer lock (public `recover`) or by a
    caller that already holds it (auto_recover_pending, recovery_preflight,
    lineage bootstrap) -- recovery is a mutating writer and must never run
    against a concurrently mutating world.

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
    root = Path(root).resolve()
    from .safeid import InvalidIdError

    try:
        journal = Journal(root, op_id)
    except InvalidIdError as exc:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "op_id": op_id,
            "recovery_required": True,
            "detail": f"op_id is not a safe path component: {exc}",
        }
    if not journal.exists():
        return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
    # ONE strict decoder gate before ANY status/byte/dispatch decision: a
    # hostile or malformed journal (unknown action/status/role/policy, op_id
    # mismatch, missing fields, broken JSON) refuses with a stable code and
    # ZERO target changes -- never an `else` destructive fallback.
    decoded = decode_operation_record(root, journal.dir)
    if not decoded["ok"]:
        return {
            "ok": False,
            "code": decoded["code"],
            "op_id": op_id,
            "recovery_required": True,
            "detail": decoded["detail"],
        }
    record = decoded["record"]

    # Owned-target guard BEFORE any dispatch: a crafted journal whose target
    # paths escape the project must refuse with ZERO writes/deletes -- the
    # journal bytes come from disk and are not trusted (T-1003 operational
    # integrity). op_id itself was validated by Journal.__init__. READ-ONLY
    # dependencies may be absolute (home), so they use the lenient resolver.
    from .safeid import InvalidIdError

    try:
        for target in record.get("targets", []):
            owned_target_path(root, target["path"])
        for path in record.get("read_preconditions") or {}:
            read_dependency_path(root, path)
    except InvalidIdError as exc:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "op_id": op_id,
            "recovery_required": True,
            "detail": f"journal target/precondition path escapes the project: {exc}",
        }

    # Identity binding BEFORE any dispatch, status or byte decision: a receipt
    # that does not belong to this project may never be recovered here, even
    # if it claims to be COMMITTED already (a foreign receipt is evidence of
    # confusion, not of completion) -- T-1003 carrier-loss wave.
    binding = _recovery_identity_binding(root, record)
    if not binding["ok"]:
        return {
            "ok": False,
            "code": binding["code"],
            "op_id": op_id,
            "recovery_required": True,
            "detail": binding["detail"],
        }

    status = record["status"]
    if status == "COMMITTED":
        return {"ok": True, "code": "ALREADY_APPLIED", "op_id": op_id}
    if status in SETTLED:
        return {
            "ok": False,
            "code": status,
            "op_id": op_id,
            "recovery_required": True,
            "detail": f"op is {status}; resolve explicitly before further mutation",
        }
    if status == "CONFLICT":
        return {
            "ok": False,
            "code": "CONFLICT",
            "op_id": op_id,
            "recovery_required": True,
            "detail": "op is CONFLICT; resolve explicitly before "
            "further mutation (saipen recover, evidence "
            "preserved)",
        }

    # Release operations own git side effects (commits/pushes/tags) that the
    # byte-replay path below cannot redo. Dispatch to the release recovery,
    # which classifies every external fact against the journal's recorded
    # expectations and never blindly repeats a side effect (T-994).
    if record.get("operation") == "release":
        from .release import _recover_release_op_locked

        return _recover_release_op_locked(root, op_id)

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
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": f"read-only dependency {path} changed (live "
                f"{live!r}, planned {expected!r}); the plan is "
                "no longer the authorized decision, refuse to "
                "roll forward",
            }

    for index, target in enumerate(targets):
        live = _target_live_hash(root, target)
        if target["applied"]:
            if live != target["after_hash"]:
                journal.mark("CONFLICT")
                return {
                    "ok": False,
                    "code": "CONFLICT",
                    "op_id": op_id,
                    "recovery_required": True,
                    "detail": f"applied target {target['path']} was "
                    f"overwritten: live {live!r} != planned "
                    f"after {target['after_hash']!r}",
                }
            continue
        if live == target["before_hash"]:
            action = _target_action(target)
            try:
                if action == "write":
                    staged = journal.staged_content(index, record)
                    if hash_bytes(staged) != target["after_hash"]:
                        journal.mark("CONFLICT")
                        return {
                            "ok": False,
                            "code": "CONFLICT",
                            "op_id": op_id,
                            "recovery_required": True,
                            "detail": f"staged bytes for {target['path']} "
                            f"hash to {hash_bytes(staged)!r}, not "
                            f"planned {target['after_hash']!r}; "
                            "journal evidence is corrupt",
                        }
                    _atomic_write(root / target["path"], staged)
                elif action == "delete_file":
                    (root / target["path"]).unlink()
                elif action == "delete_dir":
                    (root / target["path"]).rmdir()
                else:  # unreachable after the strict decoder; refuse anyway
                    journal.mark("CONFLICT")
                    return {
                        "ok": False,
                        "code": "CONFLICT",
                        "op_id": op_id,
                        "recovery_required": True,
                        "detail": f"target {target['path']} carries an "
                        f"unknown action {action!r}; recovery "
                        "refuses to dispatch a destructive "
                        "fallback",
                    }
            except OSError as exc:
                journal.mark("CONFLICT")
                return {
                    "ok": False,
                    "code": "CONFLICT",
                    "op_id": op_id,
                    "recovery_required": True,
                    "detail": f"target {target['path']} recovery action failed: {exc}",
                }
            journal.mark("APPLYING", progress_index=index + 1, target_index=index)
        elif live == target["after_hash"]:
            journal.mark("APPLYING", progress_index=index + 1, target_index=index)
        else:
            journal.mark("CONFLICT")
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": f"unfinished target {target['path']} has "
                f"unexpected bytes (live {live!r}; before "
                f"{target['before_hash']!r}, after "
                f"{target['after_hash']!r}); refuse to guess",
            }

    # Byte-level verification of every written target.
    byte_error = _verify_target_bytes(root, targets)
    if byte_error:
        journal.mark("CONFLICT")
        return {
            "ok": False,
            "code": "CONFLICT",
            "op_id": op_id,
            "recovery_required": True,
            "detail": f"recovered byte verification failed: {byte_error}",
        }

    # Semantic verification per the operation's registered policy. This is the
    # same postcondition class the original APPLY ran -- the verifier receives
    # the operation's actual changed targets, so a domain verifier validates
    # the exact files it wrote (NITRO dogfood IV, T-601). Without it, VERIFIED
    # would be a false stage name on the recovery path.
    policy = record.get("verification_policy", "none")
    if policy != "none":
        errors = _run_verifier(root, targets, policy, record.get("receipt_metadata"))
        if errors:
            journal.mark("CONFLICT")
            return {
                "ok": False,
                "code": "CONFLICT",
                "op_id": op_id,
                "recovery_required": True,
                "detail": "recovered state fails the registered semantic "
                "verifier: " + "; ".join(errors[:5]),
            }

    journal.mark("VERIFIED")
    journal.mark("COMMITTED")
    _drop_settled_staged(journal)
    return {
        "ok": True,
        "code": "COMMITTED",
        "op_id": op_id,
        "changed_files": [t["path"] for t in targets],
        "recovery_required": True,
    }


def _verifier_for(policy: str):
    """The semantic verifier callable for a closed verification policy, or
    None when the policy carries no cross-file postcondition.

    Every NAMED policy must behave truthfully (NITRO dogfood III, T-594):
    a named semantic verifier actually verifies the semantic postcondition the
    mutation claims, never a silent None. Every callable takes ONE signature
    ``(root, targets, receipt_metadata=None)`` -- the operation's actual changed
    targets plus the journaled receipt metadata -- so APPLY, Recovery and conflict
    resolution all run the same postcondition through :func:`_run_verifier` and a
    domain verifier validates the file it changed, never an unrelated scan
    (NITRO dogfood IV, T-601; P1#3 verifier normalization)."""
    if policy == "core_fast":
        from . import fast_check

        return lambda root, targets, receipt_metadata=None: fast_check.validate_project(root)
    if policy == "improve_atomic_file":
        return verify_improve
    if policy == "userperson":
        return lambda root, targets, receipt_metadata=None: _verify_userperson(
            root, receipt_metadata
        )
    if policy == "sub_collect":
        return verify_sub_collect
    if policy == "sub_disposition":
        return verify_sub_disposition
    if policy == "sub_lifecycle":
        return verify_sub_lifecycle
    if policy == "sub_clean":
        return verify_sub_clean
    if policy == "sub_sync":
        return verify_sub_sync
    return None


def _run_verifier(root, targets, policy: str, receipt_metadata=None) -> list[str]:
    """Run the registered semantic verifier for ``policy`` with the ONE shared
    signature.

    Unifies APPLY, ordinary Recovery and conflict resolution: every policy
    normalizes to ``(root, targets, receipt_metadata=None)`` (P1#3), so no
    caller special-cases arity. Returns the verifier's error list ``[]`` when the
    policy has no verifier.
    """
    verifier = _verifier_for(policy)
    if verifier is None:
        return []
    return verifier(root, targets, receipt_metadata) or []


def verify_improve(root, targets, receipt_metadata=None) -> list[str]:
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
                errors.append(f"{rel}: written Improve target missing after apply")
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


def _verify_userperson(root, receipt_metadata=None) -> list[str]:
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


def verify_sub_collect(root, targets, receipt_metadata=None) -> list[str]:
    """Core-fast plus target-aware SubSaipen INTAKE postconditions.

    Intake (INTAKE != REVIEW, Wave 2 item 4) creates the Core review ticket
    and the durable collect receipt, and leaves the worker package READY.
    The OUTBOX is a READ-ONLY dependency: the postcondition must prove the
    package was NOT flipped to reviewed by intake.
    """
    from . import fast_check

    errors = list(fast_check.validate_project(root))
    try:
        from .subs import (
            LAST_COLLECT_RE,
            MANIFEST_REL,
            SUBS_REL,
            package_identity,
            parse_manifest_file,
            parse_outbox,
        )

        target_paths = {target.get("path", "") for target in targets or []}
        if MANIFEST_REL not in target_paths:
            errors.append("sub_collect did not own live MANIFEST")
        if ".saipen/LOG.md" not in target_paths or ".saipen/BOARD.md" not in target_paths:
            errors.append("sub_collect did not own Core LOG/BOARD provenance")
        entries, manifest_errors = parse_manifest_file(root)
        errors.extend(manifest_errors)
        board_text = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig")
        log_text = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8-sig")
        SUBS_REL + "/"
        # A package may legitimately read 'reviewed' only when a COMMITTED
        # sub_disposition receipt binds its identity -- intake itself must
        # never have flipped it (INTAKE != REVIEW, Wave 2 item 4).
        disposed = set()
        # W2-002: scan BOTH recovery/ops and recovery/settled through the ONE
        # canonical semantic snapshot, not ops alone -- a committed sub_disposition
        # receipt moved to settled by _settle_journal must still be recognized.
        records, _errors = semantic_receipt_snapshot(root)
        if _errors:
            # CORE-002 (audit fdc73e06): a collect committed while the receipt
            # snapshot was corrupt is itself corrupt -- the op cannot be
            # verified clean against broken authority. Fail the verifier so
            # the mutation stays CONFLICT until the corruption is resolved.
            errors.append(
                "semantic receipt corruption during collect verification: "
                + "; ".join(_errors[:3])
            )
        for record in records:
            meta = record.get("receipt_metadata") or {}
            if record.get("operation") != "sub_disposition":
                continue
            if record.get("status") != "COMMITTED":
                continue
            if meta.get("package_identity"):
                disposed.add(meta["package_identity"])
        # TARGETED SCOPE (audit, live repro): a targeted `sub collect <name>`
        # must verify only the producers THIS op actually collected. The
        # manifest's OTHER entries may legitimately carry stale
        # `last_collect` markers (their own collect receipts vanished with a
        # failed/rolled-back op, or their packages predate the current source)
        # -- failing a targeted collect over an unrelated producer's stale
        # evidence is exactly the deadlock that made a saihunt/HUNT-008 intake
        # uncollectable at HEAD e045ad07 while the whole crew circuit waited on
        # SC-2. Legacy receipts without producer metadata fall back to the
        # full-manifest scope.
        targeted = set()
        if isinstance(receipt_metadata, dict):
            producers = receipt_metadata.get("producers")
            if isinstance(producers, list) and producers:
                targeted = {str(p) for p in producers if isinstance(p, str)}
        for entry in entries:
            if targeted and entry.name not in targeted:
                continue
            last_collect = entry.metadata.get("last_collect", "")
            if not last_collect:
                continue
            if not LAST_COLLECT_RE.fullmatch(last_collect):
                errors.append(f"{entry.name}: last_collect malformed")
                continue
            if "@" not in last_collect:
                # Legacy timestamp-only marker: valid per the canonical
                # MANIFEST parser (LAST_COLLECT_RE accepts it) and it carries
                # no package-identity claim to verify, so it must not block
                # intake of other packages.
                continue
            expected_identity = last_collect.split("@", 1)[0]
            if expected_identity not in board_text:
                errors.append(f"{entry.name}: package identity absent from Core BOARD provenance")
            if expected_identity not in log_text:
                errors.append(f"{entry.name}: package identity absent from Core LOG provenance")
            outbox_path = root / SUBS_REL / entry.name / "kitchen" / "OUTBOX.md"
            if not outbox_path.is_file():
                errors.append(f"{entry.name}: collected OUTBOX missing")
                continue
            model = parse_outbox(outbox_path.read_text(encoding="utf-8-sig"), entry.name)
            errors.extend(f"{entry.name}: {error}" for error in model.errors)
            matches = [
                package
                for package in model.packages
                if package_identity(package) == expected_identity
            ]
            if len(matches) != 1:
                errors.append(
                    f"{entry.name}: last_collect identity matches {len(matches)} OUTBOX packages"
                )
            elif matches[0].status == "reviewed" and expected_identity not in disposed:
                errors.append(
                    f"{entry.name}/{matches[0].package_id}: intake must NOT "
                    "mark the package reviewed (INTAKE != REVIEW); a "
                    "reviewed claim is a Core disposition, applied only by "
                    "sub_disposition after the linked ticket is terminal"
                )
    except Exception as exc:
        errors.append(f"sub collect verification failed: {exc}")
    return errors


def verify_sub_disposition(root, targets, receipt_metadata=None) -> list[str]:
    """Core-fast plus target-aware disposition postconditions (Wave 2 items
    4/13): the target OUTBOX package must actually be 'reviewed' now, and the
    Core LOG/STATE provenance must exist."""
    from . import fast_check

    errors = list(fast_check.validate_project(root))
    try:
        from .subs import SUBS_REL, parse_outbox

        target_paths = {target.get("path", "") for target in targets or []}
        if ".saipen/LOG.md" not in target_paths or ".saipen/STATE.md" not in target_paths:
            errors.append("sub_disposition did not own Core LOG/STATE provenance")
        prefix = SUBS_REL + "/"
        for rel in sorted(
            path
            for path in target_paths
            if path.startswith(prefix) and path.endswith("/kitchen/OUTBOX.md")
        ):
            producer = rel[len(prefix) :].split("/", 1)[0]
            path = root / rel
            if not path.is_file():
                errors.append(f"{rel}: disposition OUTBOX missing")
                continue
            model = parse_outbox(path.read_text(encoding="utf-8-sig"), producer)
            errors.extend(f"{rel}: {error}" for error in model.errors)
            if not any(package.status == "reviewed" for package in model.packages):
                errors.append(f"{producer}: disposition did not mark any package reviewed")
    except Exception as exc:
        errors.append(f"sub disposition verification failed: {exc}")
    return errors


def verify_sub_lifecycle(root, targets, receipt_metadata=None) -> list[str]:
    """Verify only SubSaipen entities owned by this journaled mutation."""
    errors = []
    try:
        from .state import parse_frontmatter
        from .subs import (
            MANIFEST_REL,
            SUBS_REL,
            _entry_dir,
            parse_manifest_file,
            parse_outbox,
            parse_sub_board,
            role_freshness,
            validate_sub_lifecycle,
        )

        target_paths = {target.get("path", "") for target in targets or []}
        owns_outbox = {path for path in target_paths if path.endswith("/kitchen/OUTBOX.md")}
        owns_lifecycle = MANIFEST_REL in target_paths or any(
            path.startswith(SUBS_REL + "/")
            and (
                path.endswith("/STATE.md")
                or path.endswith("/BOARD.md")
                or path.endswith("/LOG.md")
                or path.endswith("/kitchen/OUTBOX.md")
            )
            for path in target_paths
        )
        if not owns_lifecycle:
            return errors
        if not any(
            path == MANIFEST_REL or path.startswith(SUBS_REL + "/") for path in target_paths
        ):
            return errors
        names = set()
        prefix = SUBS_REL + "/"
        for path in target_paths:
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix) :]
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
                    errors.append(f"{name}: STATE field {field} appears {count} time(s)")
            if st.get("agent") != name:
                errors.append(f"{name}: STATE agent {st.get('agent')!r} mismatches role")
            role_revision = st.get("role_revision") or ""
            role_state = role_freshness(root, name, role_revision, st.get("saipen_home") or "")
            if role_state != "current":
                errors.append(f"{name}: role identity is {role_state}")
            board = parse_sub_board(
                board_file.read_text(encoding="utf-8-sig") if board_file.is_file() else "",
                expected_role=name,
            )
            errors.extend(f"{name}: {error}" for error in board["errors"])
            errors.extend(f"{name}: {error}" for error in validate_sub_lifecycle(st, board, name))
            paused = st.get("phase") == "BLOCKED" and st.get("blocker") == "paused by main agent"
            if paused != bool(st.get("paused_from_phase") and st.get("paused_from_na")):
                errors.append(f"{name}: pause metadata/phase mismatch")
        for rel in owns_outbox:
            owner = rel[len(prefix) :].split("/", 1)[0]
            path = root / rel
            model = (
                parse_outbox(path.read_text(encoding="utf-8-sig"), owner)
                if path.is_file()
                else None
            )
            if model is None:
                errors.append(f"{rel}: owned OUTBOX missing")
            else:
                errors.extend(f"{rel}: {error}" for error in model.errors)
    except Exception as exc:
        errors.append(f"sub lifecycle verification failed: {exc}")
    return errors


def verify_sub_clean(root, targets, receipt_metadata=None) -> list[str]:
    """Verify manifest removal, source absence, and exact archive binding."""
    errors = []
    try:
        from .subs import MANIFEST_REL, SUBS_REL, parse_manifest_file

        receipts = [
            target
            for target in targets or []
            if target.get("action", "write") == "write"
            and target.get("path", "").startswith(".saipen/recovery/subs/")
            and target.get("path", "").endswith("/receipt.json")
        ]
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
        deleted = {
            target["path"][len(source_prefix) :]: target["before_hash"]
            for target in targets or []
            if target.get("action") == "delete_file"
            and target.get("path", "").startswith(source_prefix)
        }
        archived = {
            target["path"][len(archive_prefix) :]: target["after_hash"]
            for target in targets or []
            if target.get("action", "write") == "write"
            and target.get("path", "").startswith(archive_prefix)
        }
        archive_root = root / archive_prefix.rstrip("/")
        actual_archived = (
            {
                path.relative_to(archive_root).as_posix()
                for path in archive_root.rglob("*")
                if path.is_file()
            }
            if archive_root.is_dir()
            else set()
        )
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
        if not receipt.get("instance_tree_hash", "").startswith("delete-tree-sha256:"):
            errors.append("receipt lacks exact source tree hash")
    except Exception as exc:
        errors.append(f"sub clean verification failed: {exc}")
    return errors


def verify_sub_sync(root, targets, receipt_metadata=None) -> list[str]:
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
    from .safeid import InvalidIdError

    try:
        journal = Journal(root, op_id)
        if not journal.exists():
            return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
        # Strict decoder before ANY projection: a hostile/malformed journal
        # inspects as a structured refusal, never a partial healthy surface.
        decoded = decode_operation_record(root, journal.dir)
        if not decoded["ok"]:
            return {
                "ok": False,
                "code": decoded["code"],
                "op_id": op_id,
                "recovery_required": True,
                "detail": decoded["detail"],
            }
        record = decoded["record"]
        for target in record.get("targets", []):
            owned_target_path(root, target["path"])
        targets = []
        conflicts = []
    except InvalidIdError as exc:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "op_id": op_id,
            "detail": f"journal target path or op_id escapes the project: {exc}",
        }
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
        expected = target.get("after_hash") if target.get("applied") else target.get("before_hash")
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
            ["accept_live", "replan"] if record.get("status") == "CONFLICT" else []
        ),
        "code": "CONFLICT_INSPECT" if record.get("status") == "CONFLICT" else "OP_INSPECT",
    }


def resolve_conflict(
    project_root: Path | str, op_id: str, resolution: str = "accept_live", agent: str = "saipen"
) -> dict:
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
        return {
            "ok": False,
            "code": "WRITER_BUSY",
            "op_id": op_id,
            "detail": "another live writer holds the project lock; retry after it releases",
        }


def _resolve_conflict_locked(root: Path, op_id: str, resolution: str, agent: str) -> dict:
    """The locked body of resolve_conflict (T-601). Called only under the
    project writer lock, so the journal read, the pending-op scan and the
    live-hash snapshot all observe one consistent world."""
    from .safeid import InvalidIdError

    try:
        journal = Journal(root, op_id)
        if not journal.exists():
            return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
        decoded = decode_operation_record(root, journal.dir)
        if not decoded["ok"]:
            return {
                "ok": False,
                "code": decoded["code"],
                "op_id": op_id,
                "recovery_required": True,
                "detail": decoded["detail"],
            }
        record = decoded["record"]
        for target in record.get("targets", []):
            owned_target_path(root, target["path"])
    except InvalidIdError as exc:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "op_id": op_id,
            "detail": f"journal target path or op_id escapes the project: {exc}",
        }
    if record.get("status") != "CONFLICT":
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"op {op_id} is {record.get('status')}, not "
            "CONFLICT; only an unresolved conflict is "
            "resolvable",
        }
    if resolution not in ("accept_live", "replan"):
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": f"resolution {resolution!r} outside accept_live|replan",
        }

    # Only the selected conflict may be settled: any OTHER unresolved op or
    # conflict blocks this resolution (no global bypass).
    for other in scan_pending(root)[0]:
        if other["op_id"] != op_id:
            return {
                "ok": False,
                "code": "RECOVERY_REQUIRED",
                "op_ids": [other["op_id"]],
                "detail": f"unrelated unresolved op {other['op_id']} "
                "blocks resolving this conflict; resolve it "
                "first",
            }

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
                return {
                    "ok": False,
                    "code": "CONFLICT",
                    "detail": f"applied target {target['path']} changed "
                    f"again during resolution; evidence moved, "
                    "re-inspect",
                }
            applied.append(target["path"])
        else:
            skipped.append(target["path"])
    # Stability guard: the live bytes must not move between the pre-resolution
    # read and the settle.
    for path, expected in live_snapshot.items():
        target = next(item for item in record.get("targets", []) if item["path"] == path)
        if _target_live_hash(root, target) != expected:
            return {
                "ok": False,
                "code": "CONFLICT",
                "detail": f"target {path} changed during resolution; evidence moved, re-inspect",
            }

    # ACCEPT_LIVE: the current live bytes are the new truth. Verify the
    # resulting canonical repository before settling.
    policy = record.get("verification_policy", "none")
    errors = _run_verifier(root, record.get("targets", []), policy, record.get("receipt_metadata"))
    if errors:
        return {
            "ok": False,
            "code": "NEEDS_REPAIR",
            "detail": "resolving to current live leaves an invalid "
            "repository: " + "; ".join(errors[:5]),
            "conflict_op_id": op_id,
            "repair_evidence": errors,
        }

    # Settle: mark RESOLVED with the resolution record. Never touch the live
    # canonical files -- the resolution IS the decision to keep them.
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["status"] = "RESOLVED"
    record["resolution"] = resolution
    record["resolved_at"] = now
    record["resolver_agent"] = agent
    record["resolution_applied_targets"] = applied
    record["resolution_skipped_targets"] = skipped
    record["resolution_evidence"] = (
        "live accepted" if resolution == "accept_live" else "operation retired; fresh plan required"
    )
    # W2-003 (CORE-005): ownership handover is an explicit part of the
    # resolution lifecycle, validated and performed BEFORE the irreversible
    # terminal write -- never a post-settlement best effort that can silently
    # lie about success. If the required owner transition cannot complete, we
    # refuse HERE (resolution NOT committed) so the conflict stays resolvable
    # and the command fails truthfully instead of reporting RESOLVED with a
    # stale owner. The previous code unpacked `parse_state()` as if it returned
    # a (state, error) tuple (it returns ONE dict), raised inside a broad
    # `except Exception: pass`, swallowed the failure, and returned RESOLVED
    # while STATE.agent stayed unchanged.
    from .state import parse_state

    state_path = root / ".saipen" / "STATE.md"
    if state_path.is_file():
        state_rec = parse_state(state_path.read_text(encoding="utf-8"))
        if state_rec.get("agent") != agent:
            from .operations import handover_agent

            try:
                ho = handover_agent(root, agent, allow_dead_home=True)
            except Exception as exc:  # injected / unexpected handover failure
                return {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "op_id": op_id,
                    "resolution_committed": False,
                    "detail": f"conflict resolution blocked: required ownership "
                    f"handover to {agent!r} raised before settlement: {exc}",
                }
            if not ho.ok:
                return {
                    "ok": False,
                    "code": "VALIDATION_FAILED",
                    "op_id": op_id,
                    "resolution_committed": False,
                    "detail": f"conflict resolution blocked: required ownership "
                    f"handover to {agent!r} failed before settlement: {ho.message}",
                }

    _atomic_json(journal.manifest, record)
    # Terminalize through Journal.mark so the bounded progress sidecar is
    # folded into operation.json and removed before settlement. Moving the
    # directory directly leaves a stale CONFLICT sidecar that the canonical
    # decoder correctly treats as the effective status, making the accepted
    # resolution invisible to every receipt consumer.
    journal.mark("RESOLVED", progress_index=record.get("progress_index"))
    # RESOLVED is terminal just like COMMITTED: staged planned bytes are no
    # longer executable authority and must be removed. The shared cleanup
    # helper records bounded retry debt if an unlink fails, so settling never
    # leaves an unbounded payload archive in the lifetime receipt namespace.
    _drop_settled_staged(journal)

    return {
        "ok": True,
        "code": "RESOLVED",
        "op_id": op_id,
        "resolution": resolution,
        "applied_targets": applied,
        "skipped_targets": skipped,
        "detail": "conflict settled; live bytes accepted as truth, "
        "unapplied plan effects abandoned",
    }


def auto_recover_pending(project_root: Path | str) -> dict:
    """Recover every pending op in order; stop at the first conflict.

    Used by `saipen recover` (no explicit op_id). A conflict stops the run
    with the conflicting op named and its evidence preserved. The ENTIRE
    selected recovery sequence runs under ONE writer-lock acquisition: each
    op's `_recover_locked` body is serialized against any concurrent writer,
    so a parallel recover/mutation cannot interleave between ops."""
    root = Path(project_root)
    from .lock import project_writer_lock as _recover_lock

    try:
        with _recover_lock(root):
            pending, _conflicts = scan_pending(root)
            if not pending:
                return {"ok": True, "code": "CLEAN", "recovered": []}
            recovered = []
            for op in pending:
                # Refuse corrupt evidence BEFORE any replay (hostile-regression
                # corrupt-evidence partition, P1#6): a receipt the strict
                # decoder already refused -- or an op directory that failed its
                # containment probe -- is evidence that cannot be trusted, and
                # auto-recovery must never attempt to roll it forward. The
                # structured corrupt record (op_id + detail) is preserved and
                # surfaced; resolving it is an explicit human action.
                if op.get("corrupt"):
                    return {
                        "ok": False,
                        "code": "CORRUPT_JOURNAL",
                        "op_ids": [op["op_id"]],
                        "recovery_required": True,
                        "detail": (
                            f"corrupt journal evidence "
                            f"{op['op_id']} blocks auto-recovery: "
                            f"{op.get('detail', '')} -- resolve the "
                            f"corrupt receipt explicitly before "
                            f"replay"
                        ),
                    }
                result = _recover_locked(root, op["op_id"])
                if not result["ok"]:
                    # ONE fresh scan for the stale receipt list: the failed
                    # op may have been settled mid-loop.
                    result["pending_op_ids"] = [p["op_id"] for p in scan_pending(root)[0]]
                    return result
                recovered.append(op["op_id"])
            return {
                "ok": True,
                "code": "RECOVERED",
                "recovered": recovered,
                "recovery_required": False,
            }
    except PermissionError:
        return {
            "ok": False,
            "code": "WRITER_BUSY",
            "detail": "another live writer holds the project lock; retry after it releases",
        }


def _compact_drop_staged(entry: Path, compacted: list, skipped: list) -> None:
    """Drop any leftover `.staged` payloads for a single settled op dir.

    PERF-005: invoked only for ops that carry cleanup debt (whose post-
    settlement staged unlink failed earlier and was durably enqueued).

    W2-005: explicitly tracks success vs outstanding debt. Every staged file
    is removed; if ANY removal fails the entry is reported as skipped so the
    durable cleanup-queue marker survives for a later CLEAN retry -- we never
    claim success we did not achieve, and never delete the marker while debt
    remains. Only when NO staged payload remains is the entry marked compacted.
    """
    remaining: list[str] = []
    for staged in entry.glob("*.staged"):
        try:
            staged.unlink()
        except OSError:
            remaining.append(staged.name)
    if remaining:
        # Outstanding debt: keep the entry in the skip list so the caller
        # retains its cleanup-queue marker for the next CLEAN.
        skipped.append(entry.name)
        return
    if entry.name not in compacted:
        compacted.append(entry.name)


def _compact_migrate_ops(
    root: Path, ops_dir: Path, settled_dir: Path, compacted: list, skipped: list
) -> None:
    """Collision-safe migration of terminal ops from ``ops_dir`` -> ``settled_dir``.

    Bounded by ``ops_dir`` size (only pending/active/terminal ops live there),
    NOT by the whole lifetime settled history. PERF-005: this is the only full
    directory scan ``compact_committed`` performs, and ``ops_dir`` stays small
    under normal CLEAN cadence -- it never re-walks the settled ledger.
    """
    if not ops_dir.is_dir():
        return
    try:
        info = os.lstat(ops_dir)
        if ops_dir.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            return
    except OSError:
        return
    for entry in sorted(ops_dir.iterdir()):
        from .safeid import InvalidIdError

        try:
            safe_op_dir(root, entry.name, OPS_DIR)
            info = os.lstat(entry)
            if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                continue
        except (OSError, InvalidIdError):
            continue
        if not entry.is_dir():
            continue
        manifest = entry / "operation.json"
        if not manifest.is_file():
            continue
        decoded = decode_operation_record(root, entry)
        if not decoded["ok"]:
            skipped.append(entry.name)
            continue
        record = decoded["record"]
        if record.get("status") not in ("COMMITTED", "RESOLVED"):
            skipped.append(entry.name)
            continue
        # Drop staged payloads at migration time.
        for staged in entry.glob("*.staged"):
            with contextlib.suppress(OSError):
                staged.unlink()
        # Migrate to settled namespace. Collision-safe (CORE-008): the
        # destination existing is NOT proof the receipt was already migrated.
        # Decode BOTH sides; only collapse when both are terminal receipts for
        # the SAME op whose immutable/terminal evidence is demonstrably
        # equivalent. Any non-equivalent collision -- stale, corrupt, or a
        # foreign same-name directory with no operation.json -- leaves the
        # valid source untouched and is reported as skipped.
        try:
            dest = safe_op_dir(root, entry.name, SETTLED_DIR)
        except InvalidIdError:
            skipped.append(entry.name)
            continue
        if dest.exists():
            dest_dec = decode_operation_record(root, dest)
            if (
                dest_dec["ok"]
                and dest_dec["record"].get("status") in SETTLED
                and _terminal_receipt_equivalent(record, dest_dec["record"])
            ):
                import shutil

                shutil.rmtree(entry, ignore_errors=True)
                if entry.name not in compacted:
                    compacted.append(entry.name)
            else:
                skipped.append(entry.name)
        else:
            try:
                settled_dir.mkdir(parents=True, exist_ok=True)
                # The directory can be swapped between the first proof and
                # mkdir. Re-prove the exact destination immediately before
                # the no-replace rename.
                dest = safe_op_dir(root, entry.name, SETTLED_DIR)
                # No-replace atomic rename: only move when the destination is
                # absent; a concurrent creation between the check and the rename
                # leaves the source intact.
                os.rename(entry, dest)
                if entry.name not in compacted:
                    compacted.append(entry.name)
            except (OSError, InvalidIdError):
                skipped.append(entry.name)


# ---------------------------------------------------------------------------
# W2-001: Canonical semantic-receipt snapshot.
#
# All semantic readers (convergence, crew, subs, operations) must consume
# this ONE snapshot rather than reopening raw JSON from a single namespace.
# The snapshot scans both `ops` (unresolved/current evidence) and `settled`
# (terminal receipts moved by _settle_journal), enforces op_id uniqueness
# across both, and returns all records through the strict decoder.
# ---------------------------------------------------------------------------


_RECEIPT_STRUCTURE_SENTINEL = b"\0saipen-receipt-structure-v1\0"
_PROGRESS_ABSENT_SENTINEL = b"\0saipen-progress-absent-v1\0"
_PROGRESS_UNAVAILABLE_SENTINEL = b"\0saipen-progress-unavailable-v1\0"


@dataclass(frozen=True)
class _ReceiptEntry:
    name: str
    op_dir: Path | None
    manifest_raw: bytes
    progress_raw: bytes | None
    structural_error: str | None


def _receipt_namespace_entries(
    ns_dir: Path,
) -> list[_ReceiptEntry]:
    """Capture one receipt namespace as exact bytes plus structural verdicts.

    The semantic pass and its lightweight closing CAS MUST tokenize the same
    world.  Skipping a dangling symlink, non-directory entry, missing
    manifest, or unreadable namespace made an added corrupt artifact hash like
    absence and allowed the stability proof to miss the race.  Invalid shapes
    now receive deterministic sentinel bytes; valid manifests are still read
    exactly once and decoded from those same bytes.
    """

    def invalid(name: str, detail: str) -> _ReceiptEntry:
        token = _RECEIPT_STRUCTURE_SENTINEL + detail.encode("utf-8", errors="replace")
        return _ReceiptEntry(name, None, token, _PROGRESS_UNAVAILABLE_SENTINEL, detail)

    try:
        ns_info = os.lstat(ns_dir)
    except FileNotFoundError:
        return []
    except OSError as exc:
        detail = f"namespace stat failed ({type(exc).__name__}): {exc}"
        return [invalid("NAMESPACE", detail)]
    if stat.S_ISLNK(ns_info.st_mode) or getattr(ns_info, "st_file_attributes", 0) & 0x400:
        return [invalid("NAMESPACE", "namespace is a symlink or reparse point")]
    if not stat.S_ISDIR(ns_info.st_mode):
        return [invalid("NAMESPACE", "namespace exists but is not a directory")]
    try:
        entries = sorted(ns_dir.iterdir())
    except OSError as exc:
        detail = f"namespace listing failed ({type(exc).__name__}): {exc}"
        return [invalid("NAMESPACE", detail)]

    captured: list[_ReceiptEntry] = []
    for op_dir in entries:
        # Engine-owned cleanup debt is not a semantic operation receipt and
        # intentionally does not stale a crew decision.
        if ns_dir.name == Path(SETTLED_DIR).name and op_dir.name == ".cleanup-needed":
            continue
        try:
            op_info = os.lstat(op_dir)
        except FileNotFoundError:
            # A deletion raced this pass. The membership changed, so frame a
            # sentinel rather than pretending the listing never contained it.
            captured.append(invalid(op_dir.name, "op entry vanished during capture"))
            continue
        except OSError as exc:
            captured.append(
                invalid(op_dir.name, f"op entry stat failed ({type(exc).__name__}): {exc}")
            )
            continue
        if stat.S_ISLNK(op_info.st_mode) or getattr(op_info, "st_file_attributes", 0) & 0x400:
            captured.append(invalid(op_dir.name, "op directory is a symlink or reparse point"))
            continue
        if not stat.S_ISDIR(op_info.st_mode):
            captured.append(invalid(op_dir.name, "op entry is not a directory"))
            continue

        manifest = op_dir / "operation.json"
        try:
            manifest_info = os.lstat(manifest)
        except FileNotFoundError:
            captured.append(invalid(op_dir.name, "op directory has no operation.json"))
            continue
        except OSError as exc:
            captured.append(
                invalid(
                    op_dir.name,
                    f"operation.json stat failed ({type(exc).__name__}): {exc}",
                )
            )
            continue
        if stat.S_ISLNK(manifest_info.st_mode) or getattr(
            manifest_info, "st_file_attributes", 0
        ) & 0x400:
            captured.append(invalid(op_dir.name, "operation.json is a symlink or reparse point"))
            continue
        if not stat.S_ISREG(manifest_info.st_mode):
            captured.append(invalid(op_dir.name, "operation.json is not a regular file"))
            continue
        try:
            raw = manifest.read_bytes()
        except OSError as exc:
            captured.append(
                invalid(op_dir.name, f"operation.json unreadable ({type(exc).__name__}): {exc}")
            )
            continue
        progress = op_dir / "progress.json"
        try:
            progress_info = os.lstat(progress)
        except FileNotFoundError:
            progress_raw = None
        except OSError as exc:
            detail = f"progress.json stat failed ({type(exc).__name__}): {exc}"
            token = _RECEIPT_STRUCTURE_SENTINEL + detail.encode(
                "utf-8", errors="replace"
            )
            captured.append(_ReceiptEntry(op_dir.name, None, raw, token, detail))
            continue
        else:
            if stat.S_ISLNK(progress_info.st_mode) or getattr(
                progress_info, "st_file_attributes", 0
            ) & 0x400:
                detail = "progress.json is a symlink or reparse point"
                token = _RECEIPT_STRUCTURE_SENTINEL + detail.encode("utf-8")
                captured.append(_ReceiptEntry(op_dir.name, None, raw, token, detail))
                continue
            if not stat.S_ISREG(progress_info.st_mode):
                detail = "progress.json is not a regular file"
                token = _RECEIPT_STRUCTURE_SENTINEL + detail.encode("utf-8")
                captured.append(_ReceiptEntry(op_dir.name, None, raw, token, detail))
                continue
            try:
                progress_raw = progress.read_bytes()
            except OSError as exc:
                detail = f"progress.json unreadable ({type(exc).__name__}): {exc}"
                token = _RECEIPT_STRUCTURE_SENTINEL + detail.encode(
                    "utf-8", errors="replace"
                )
                captured.append(_ReceiptEntry(op_dir.name, None, raw, token, detail))
                continue
        captured.append(_ReceiptEntry(op_dir.name, op_dir, raw, progress_raw, None))
    return captured


def _frame_receipt(digest, namespace: str, entry: _ReceiptEntry) -> None:
    progress_token = (
        _PROGRESS_ABSENT_SENTINEL if entry.progress_raw is None else entry.progress_raw
    )
    for part in (
        namespace.encode("utf-8"),
        entry.name.encode("utf-8"),
        b"operation.json",
        entry.manifest_raw,
        b"progress.json",
        progress_token,
    ):
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)


def _scan_receipt_namespace(
    root: Path,
    ns_dir: Path,
    results: dict[str, dict],
    errors: list[str],
    corrupt_op_ids: set[str],
    digest,
) -> None:
    """Scan one receipt namespace (ops or settled) and merge into results.

    W2-001: every candidate is decoded through the ONE strict decoder
    (decode_operation_record). A decode/read/namespace failure is PRESERVED in
    ``errors`` and never silently skipped -- corrupt evidence must surface so
    fail-closed consumers can refuse it. op_id uniqueness is enforced: a
    duplicate collision is corrupt evidence UNLESS both sides are demonstrably
    equivalent terminal receipts (the same op settled under both namespaces
    after a crash re-scan), in which case the settled (current) record wins.
    """
    for entry in _receipt_namespace_entries(ns_dir):
        _frame_receipt(digest, ns_dir.name, entry)
        if entry.structural_error is not None or entry.op_dir is None:
            errors.append(
                f"{entry.name}: CORRUPT_JOURNAL: "
                f"{entry.structural_error or 'invalid receipt structure'}"
            )
            corrupt_op_ids.add(entry.name)
            results.pop(entry.name, None)
            continue
        # Decode the exact manifest + progress bytes already framed into the
        # semantic digest. Reopening either authority would double lifetime
        # receipt I/O and could parse bytes different from those authenticated.
        decoded = decode_operation_record(
            root,
            entry.op_dir,
            raw=entry.manifest_raw,
            progress_raw=entry.progress_raw,
            progress_captured=True,
        )
        if not decoded["ok"]:
            # Preserve the corruption evidence instead of discarding it.
            errors.append(
                f"{entry.name}: {decoded.get('code', 'RECOVERY_CONFLICT')}: "
                f"{decoded.get('detail', 'unparseable operation receipt')}"
            )
            corrupt_op_ids.add(entry.name)
            results.pop(entry.name, None)
            continue
        record = decoded["record"]
        op_id = record.get("op_id") or entry.name
        if op_id in corrupt_op_ids:
            # A malformed sibling with this identity already exists.  The
            # parseable twin is not positive authority; neither side wins.
            continue
        if op_id in results:
            # W2-001: duplicate op_id across namespaces is corrupt evidence
            # UNLESS both records are equivalent terminal receipts.
            existing = results[op_id]
            if (
                existing.get("status") in SETTLED
                and record.get("status") in SETTLED
                and _terminal_receipt_equivalent(existing, record)
            ):
                # Both terminal + equivalent: the settled (current) one wins.
                results[op_id] = record
            else:
                errors.append(
                    f"duplicate op_id {op_id!r} across ops/settled "
                    "with non-equivalent records -- corrupt evidence"
                )
                corrupt_op_ids.add(op_id)
                # A non-equivalent duplicate is corrupt evidence: NEITHER side
                # may be trusted as positive evidence, so drop the previously
                # selected record rather than leaving it silently in play.
                results.pop(op_id, None)
        else:
            results[op_id] = record


@dataclass(frozen=True)
class SemanticReceiptSnapshot:
    """Command-scoped canonical receipt authority plus corruption verdict.

    Iteration preserves the historical ``records, errors = snapshot`` API,
    while named fields prevent new consumers from accidentally forgetting the
    corruption half of the contract.
    """

    records: tuple[dict, ...]
    errors: tuple[str, ...]
    corrupt_op_ids: frozenset[str]
    digest: str

    def __iter__(self):
        yield list(self.records)
        yield list(self.errors)


def semantic_receipt_snapshot(
    project_root: Path | str,
) -> SemanticReceiptSnapshot:
    """W2-001: ONE canonical semantic-receipt snapshot.

    Scans both `recovery/ops` (unresolved/current evidence) and
    `recovery/settled` (terminal receipts), decodes every manifest
    through the strict decoder, and enforces op_id uniqueness across
    both namespaces.

    W2-001: enforces LIVE project-lineage binding on every current
    (lineage-bearing) receipt before records are exposed to consumers.
    A receipt carrying project_lineage that does not match the live
    canonical lineage is surfaced as foreign/corrupt evidence and
    excluded from positive semantic results. This keeps convergence,
    crew, intent, and targeted-release consumers on one canonical
    filtered snapshot instead of each independently checking lineage.

    Returns (records, errors) where records is a list of all decoded
    operation records and errors is a list of corruption evidence strings.
    Records are sorted by created_at for deterministic ordering.
    """
    root = Path(project_root)
    results: dict[str, dict] = {}
    errors: list[str] = []
    corrupt_op_ids: set[str] = set()
    digest = hashlib.sha256(b"saipen-op-receipts-v3\0")

    # Scan ops first (unresolved/current evidence)
    _scan_receipt_namespace(root, root / OPS_DIR, results, errors, corrupt_op_ids, digest)
    # Scan settled second (terminal receipts)
    _scan_receipt_namespace(root, root / SETTLED_DIR, results, errors, corrupt_op_ids, digest)

    # W2-001 / CORE-003: enforce live project binding on every receipt before
    # consumers see it. A lineage-bearing receipt must match the live lineage;
    # a legacy no-lineage UNRESOLVED receipt is usable only at the exact runtime
    # identity that created it (the SAME rule recovery uses). Settled legacy
    # receipts (COMMITTED/ABORTED/RESOLVED) are immutable history: they are
    # compatible without runtime binding and must not poison unrelated valid
    # receipts after a legitimate directory move / archive extraction.
    # Explicit foreign lineage (record carries a lineage that mismatches live)
    # remains rejected.
    foreign: list[str] = []
    for op_id, rec in list(results.items()):
        # CORE-003: settled legacy receipts are history, not recovery authority
        if rec.get("project_lineage") is None and rec.get("status") in SETTLED:
            continue
        binding = _recovery_identity_binding(root, rec)
        if not binding["ok"]:
            foreign.append(op_id)
            del results[op_id]
    if foreign:
        errors.append(
            f"foreign-lineage/identity receipt(s) excluded: "
            f"{', '.join(sorted(foreign)[:5])}"
            f"{'...' if len(foreign) > 5 else ''}"
        )
    # Sort by created_at for deterministic ordering (W2-005: canonical UTC).
    # Year 0000 does not exist in datetime (MINYEAR is 1), so the fallback
    # must be a REAL instant -- parsing "0000-01-01" returned None and made
    # the sort key itself None, which crashed every consumer comparing it
    # against a real timestamp (saicrew harness, TypeError NoneType < datetime).
    _earliest = iso_utc_sort_key("0001-01-01T00:00:00Z") or datetime.datetime.min.replace(
        tzinfo=datetime.timezone.utc
    )
    records = sorted(
        results.values(),
        key=lambda r: (iso_utc_sort_key(r.get("created_at", "")) or _earliest, r.get("op_id", "")),
    )
    return SemanticReceiptSnapshot(
        tuple(records),
        tuple(errors),
        frozenset(corrupt_op_ids),
        "ops-receipt-sha256:" + digest.hexdigest(),
    )


def semantic_receipt_digest(project_root: Path | str) -> str:
    """Lightweight exact-byte digest of both operation receipt namespaces.

    This is the closing snapshot proof and the mutation-time CAS tokenizer.
    It binds exact operation.json and progress.json authority, deliberately
    performs no JSON decode, and never reads staged payloads.
    """
    root = Path(project_root)
    digest = hashlib.sha256(b"saipen-op-receipts-v3\0")
    for ns_dir in (root / OPS_DIR, root / SETTLED_DIR):
        for entry in _receipt_namespace_entries(ns_dir):
            _frame_receipt(digest, ns_dir.name, entry)
    return "ops-receipt-sha256:" + digest.hexdigest()


class SemanticReceiptCorruptionError(ValueError):
    """Typed corruption refusal for semantic receipt authority (CORE-004).

    Raised by semantic_receipts_for_operation when the canonical snapshot
    contains errors. Callers must distinguish CORRUPT authority (fail-closed)
    from CLEAN_EMPTY (no matching operation).
    """

    def __init__(self, errors: tuple[str, ...], snapshot) -> None:
        super().__init__(
            "; ".join(errors[:3]) if errors else "semantic receipt snapshot is corrupt"
        )
        self.errors = errors
        self.snapshot = snapshot


def semantic_receipts_for_operation(project_root: Path | str, operation: str) -> list[dict]:
    """W2-001 / CORE-004: filtered semantic receipts for a specific operation.

    Returns all records matching the operation from the canonical snapshot.
    If the snapshot contains errors, raises SemanticReceiptCorruptionError
    instead of collapsing CORRUPT authority into CLEAN_EMPTY negative evidence.
    Callers that need to distinguish must catch this exception and return a
    CORRUPT_JOURNAL refusal; plain list filtering is safe only after the
    snapshot has been proven clean.
    """
    snapshot = semantic_receipt_snapshot(project_root)
    if snapshot.errors:
        raise SemanticReceiptCorruptionError(snapshot.errors, snapshot)
    return [r for r in snapshot.records if r.get("operation") == operation]


def semantic_receipts_for_operation_safe(
    project_root: Path | str, operation: str
) -> tuple[list[dict], tuple[str, ...]]:
    """Safe variant that returns (records, errors) without raising.

    Useful for read-only projections that want to surface corrupción as data
    rather than exception. Mutation paths should use the raising variant and
    fail closed on corruption.
    """
    snapshot = semantic_receipt_snapshot(project_root)
    if snapshot.errors:
        return [], snapshot.errors
    return [r for r in snapshot.records if r.get("operation") == operation], ()


def _compaction_queue_preflight(root: Path, cleanup_queue: Path) -> tuple[list[Path], str | None]:
    """Validate cleanup-debt authority before compaction performs any write."""
    from .safeid import InvalidIdError, prove_inside

    for label, path in (
        ("OPS_DIR", root / OPS_DIR),
        ("SETTLED_DIR", root / SETTLED_DIR),
        ("CLEANUP_QUEUE", cleanup_queue),
    ):
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            return [], f"{label} stat failed: {exc}"
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return [], f"{label} is a symlink or reparse point"
        if not stat.S_ISDIR(info.st_mode):
            return [], f"{label} exists but is not a directory"
        try:
            prove_inside(path, root, kind=label)
        except InvalidIdError as exc:
            return [], str(exc)

    try:
        queue_info = os.lstat(cleanup_queue)
    except FileNotFoundError:
        return [], None
    except OSError as exc:
        return [], f"CLEANUP_QUEUE stat failed: {exc}"
    if not stat.S_ISDIR(queue_info.st_mode):
        # Kept explicit even though the namespace loop above caught the
        # ordinary case; it also documents the type promised below.
        return [], "CLEANUP_QUEUE exists but is not a directory"
    try:
        candidates = sorted(cleanup_queue.iterdir())
    except OSError as exc:
        return [], f"CLEANUP_QUEUE listing failed: {exc}"

    markers: list[Path] = []
    for marker in candidates:
        try:
            marker_info = os.lstat(marker)
            validate_op_id(marker.name)
            prove_inside(marker, cleanup_queue, kind="cleanup marker")
        except (OSError, InvalidIdError) as exc:
            return [], f"cleanup marker {marker.name!r} is unsafe: {exc}"
        if stat.S_ISLNK(marker_info.st_mode) or getattr(
            marker_info, "st_file_attributes", 0
        ) & 0x400:
            return [], f"cleanup marker {marker.name!r} is a symlink or reparse point"
        if not stat.S_ISREG(marker_info.st_mode):
            return [], f"cleanup marker {marker.name!r} is not a regular file"
        markers.append(marker)
    return markers, None


def compact_committed(project_root: Path | str) -> dict:
    """Bounded explicit maintenance compaction of SETTLED operation journals.

    PERF-005: cost is proportional to OUTSTANDING cleanup debt, not to the
    lifetime settled history. Two bounded steps:
      1. Migrate terminal ops from ``ops_dir`` -> ``settled_dir`` (collision-
         safe, CORE-008). ``ops_dir`` only holds pending/active/terminal ops,
         so this scan stays small under normal CLEAN cadence -- it never
         re-walks the whole settled ledger.
      2. Process only the durable cleanup queue: op_ids whose post-settlement
         staged-byte deletion failed earlier. Each is found directly by name;
         its leftover staged payloads are removed and its marker cleared. An
         empty queue makes repeated CLEAN a no-op regardless of settled count.
    """
    root = Path(project_root)
    ops_dir = root / OPS_DIR
    settled_dir = root / SETTLED_DIR
    compacted = []
    skipped = []

    cleanup_queue = root / CLEANUP_QUEUE_DIR
    markers, preflight_error = _compaction_queue_preflight(root, cleanup_queue)
    if preflight_error is not None:
        return {
            "ok": False,
            "code": "CORRUPT_JOURNAL",
            "detail": preflight_error,
            "compacted": compacted,
            "skipped": skipped,
        }

    _compact_migrate_ops(root, ops_dir, settled_dir, compacted, skipped)

    if markers:
        from .safeid import InvalidIdError

        for marker in markers:
            op_id = marker.name
            try:
                entry = safe_op_dir(root, op_id, SETTLED_DIR)
                decoded = decode_operation_record(root, entry)
            except (OSError, InvalidIdError):
                decoded = {"ok": False}
            if decoded.get("ok") and decoded["record"].get("status") == "COMMITTED":
                _compact_drop_staged(entry, compacted, skipped)
            elif op_id not in skipped:
                skipped.append(op_id)
            # W2-005: only clear the marker once the staged payload is proven
            # gone (the entry landed in compacted). If the drop is still in
            # debt (entry in skipped, not compacted) the marker is retained so
            # the next CLEAN retries the outstanding cleanup.
            if op_id in compacted:
                try:
                    marker_info = os.lstat(marker)
                    if stat.S_ISREG(marker_info.st_mode) and not getattr(
                        marker_info, "st_file_attributes", 0
                    ) & 0x400:
                        marker.unlink()
                    elif op_id not in skipped:
                        skipped.append(op_id)
                except OSError:
                    if op_id not in skipped:
                        skipped.append(op_id)

    return {"ok": True, "compacted": compacted, "skipped": skipped}


def _terminal_receipt_equivalent(a: dict, b: dict) -> bool:
    """True when two terminal operation records are demonstrably the SAME
    immutable evidence (byte-for-byte equivalent plan + verdict), so one may be
    collapsed onto the other during compaction without losing information
    (CORE-008). Compares only the durable, meaning-bearing fields -- never the
    volatile progress sidecar, which terminal receipts no longer carry."""
    # Terminal receipts are immutable.  Compare the complete normalized JSON
    # meaning, not a hand-picked subset that lets operation/lineage/metadata or
    # target action semantics disagree under one op_id.  Decoder normalization
    # has already supplied legacy defaults and folded any valid progress
    # sidecar, so canonical JSON equality is deterministic.
    try:
        return json.dumps(a, sort_keys=True, separators=(",", ":")) == json.dumps(
            b, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError):
        return False

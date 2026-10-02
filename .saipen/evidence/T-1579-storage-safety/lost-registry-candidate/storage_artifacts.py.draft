"""Declared project stores and atomic publication of durable artifacts.

The object copy is written and verified first. The registry replacement is the
commit point; a crash before that point leaves the previous canonical pointer
intact. Source files are never removed by promotion or migration.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from contextlib import nullcontext, suppress
from pathlib import Path
from typing import Any

from .lock import file_writer_lock
from .paths import (
    prove_owned_dir_chain,
    prove_owned_regular,
    read_bound_regular_bytes,
    safe_atomic_write_bytes,
)
from .storage import (
    StoragePolicyError,
    _resolved_path,
    _within,
    classify_path,
    load_policy,
    policy_path,
)

STORES_FILE = "STORES.json"
REGISTRY_FILE = "STORAGE_REGISTRY.json"
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,79}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_LIFETIMES = {"RUN", "SESSION", "REBOOT", "PROJECT", "PERMANENT"}
_RECOVERY = {"RECONSTRUCTABLE", "PARTIAL", "UNRECOVERABLE"}
_MAX_JSON_BYTES = 4 * 1024 * 1024


def _root(project_root: str | Path) -> Path:
    return _resolved_path(project_root)


def _read_json(path: Path, empty: dict[str, Any]) -> dict[str, Any]:
    try:
        info = prove_owned_regular(path, kind="storage authority")
    except FileNotFoundError:
        return empty
    except ValueError as exc:
        raise StoragePolicyError("STORAGE_REGISTRY_INVALID", str(exc)) from exc
    if info.st_size > _MAX_JSON_BYTES:
        raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"{path} exceeds size limit")
    try:
        raw = read_bound_regular_bytes(path, info, max_bytes=_MAX_JSON_BYTES)
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"{path} must be an object")
    return value


def _write_json(path: Path, value: dict[str, Any], project_root: Path) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    safe_atomic_write_bytes(path, data, kind="storage authority", ownership_root=project_root)


def _machine_policy_lock(explicit_policy: dict | None):
    """Serialize a canonical pointer write against machine root changes."""
    if explicit_policy is not None:
        return nullcontext()
    home = policy_path().parent
    return file_writer_lock(home / "locks" / "storage.lock", home)


def _require_current_policy(selected: dict, explicit_policy: dict | None) -> None:
    if explicit_policy is None and load_policy() != selected:
        raise StoragePolicyError(
            "STORAGE_POLICY_CHANGED", "machine storage policy changed; retry the operation"
        )


def load_stores(project_root: str | Path) -> dict[str, Any]:
    root = _root(project_root)
    path = root / ".saipen" / STORES_FILE
    value = _read_json(path, {"schema_version": 1, "stores": {}})
    if (
        set(value) != {"schema_version", "stores"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"invalid store schema: {path}")
    stores = value["stores"]
    if not isinstance(stores, dict):
        raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"stores must be an object: {path}")
    for name, entry in stores.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"invalid store name: {name}")
        if not isinstance(entry, dict) or set(entry) != {
            "class",
            "lifetime",
            "path",
            "owner",
            "recovery",
        }:
            raise StoragePolicyError(
                "STORAGE_REGISTRY_INVALID", f"invalid store declaration: {name}"
            )
        if not isinstance(entry["class"], str) or entry["class"] not in {
            "DURABLE",
            "EPHEMERAL",
            "CACHE",
            "EXTERNAL",
        }:
            raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"invalid class: {name}")
        if (
            not isinstance(entry["lifetime"], str)
            or entry["lifetime"] not in _LIFETIMES
            or not isinstance(entry["recovery"], str)
            or entry["recovery"] not in _RECOVERY
        ):
            raise StoragePolicyError(
                "STORAGE_REGISTRY_INVALID", f"invalid lifetime/recovery: {name}"
            )
        if any(
            not isinstance(entry[field], str) or not entry[field] for field in ("path", "owner")
        ):
            raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"invalid path/owner: {name}")
        if entry["lifetime"] in {"PROJECT", "PERMANENT", "REBOOT"} and entry["class"] != "DURABLE":
            raise StoragePolicyError(
                "STORAGE_POLICY_VIOLATION", f"{name}: {entry['lifetime']} requires DURABLE"
            )
    return value


def store_verdicts(project_root: str | Path, *, policy: dict | None = None) -> list[dict[str, Any]]:
    root = _root(project_root)
    selected = load_policy() if policy is None else policy
    stores = load_stores(root)["stores"]
    results = []
    for name, entry in stores.items():
        verdict = classify_path(entry["path"], entry["class"], policy=selected, base=root)
        results.append({"store": name, "lifetime": entry["lifetime"], **verdict})
    return results


def declare_store(
    project_root: str | Path,
    name: str,
    storage_class: str,
    path: str | Path,
    *,
    lifetime: str,
    owner: str,
    recovery: str,
    policy: dict | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    if not _NAME.fullmatch(name):
        raise StoragePolicyError("STORAGE_PATH_INVALID", f"invalid store name: {name}")
    if not all(isinstance(item, str) for item in (storage_class, lifetime, owner, recovery)):
        raise StoragePolicyError("STORAGE_POLICY_INVALID", "store fields must be strings")
    selected = load_policy() if policy is None else policy
    entry = {
        "class": storage_class.upper(),
        "lifetime": lifetime.upper(),
        "path": str(_resolved_path(path, base=root)),
        "owner": owner.strip(),
        "recovery": recovery.upper(),
    }
    if (
        entry["lifetime"] not in _LIFETIMES
        or entry["recovery"] not in _RECOVERY
        or not entry["owner"]
    ):
        raise StoragePolicyError(
            "STORAGE_POLICY_INVALID", "invalid store lifetime, recovery or owner"
        )
    if entry["lifetime"] in {"PROJECT", "PERMANENT", "REBOOT"} and entry["class"] != "DURABLE":
        raise StoragePolicyError(
            "STORAGE_POLICY_VIOLATION", f"{name}: {entry['lifetime']} requires DURABLE"
        )
    verdict = classify_path(entry["path"], entry["class"], policy=selected)
    if not verdict["ok"]:
        raise StoragePolicyError(verdict["code"], f"{name}: {verdict['detail']}")
    # The declaration itself is canonical state. A project under an ephemeral
    # root cannot become the sole copy of a persistent store contract.
    declaration = classify_path(root / ".saipen" / STORES_FILE, "DURABLE", policy=selected)
    if entry["class"] == "DURABLE" and not declaration["ok"]:
        raise StoragePolicyError(declaration["code"], declaration["detail"])
    registry_verdict = classify_path(root / ".saipen" / REGISTRY_FILE, "DURABLE", policy=selected)
    if entry["class"] == "DURABLE" and not registry_verdict["ok"]:
        raise StoragePolicyError(registry_verdict["code"], registry_verdict["detail"])
    lock_path = root / ".saipen" / "locks" / "storage.lock"
    with file_writer_lock(lock_path, root):
        current = load_stores(root)
        if (
            any(store["class"] == "DURABLE" for store in current["stores"].values())
            and not (root / ".saipen" / REGISTRY_FILE).is_file()
        ):
            raise StoragePolicyError(
                "STORAGE_REGISTRY_MISSING",
                "declared DURABLE stores have lost their canonical registry; "
                "inventory surviving objects and provenance before recovery",
            )
        old = current["stores"].get(name)
        if old is not None and old != entry:
            raise StoragePolicyError(
                "STORAGE_POLICY_VIOLATION",
                f"{name} already points to {old['path']}; migrate registered "
                "artifacts before changing it",
            )
        if old is None:
            with _machine_policy_lock(policy):
                _require_current_policy(selected, policy)
                for candidate in (
                    entry["path"],
                    root / ".saipen" / STORES_FILE,
                    root / ".saipen" / REGISTRY_FILE,
                ):
                    if entry["class"] != "DURABLE" and candidate != entry["path"]:
                        continue
                    fresh = classify_path(
                        candidate,
                        entry["class"] if candidate == entry["path"] else "DURABLE",
                        policy=selected,
                    )
                    if not fresh["ok"]:
                        raise StoragePolicyError(fresh["code"], fresh["detail"])
                if entry["class"] == "DURABLE" and not (root / ".saipen" / REGISTRY_FILE).exists():
                    _write_json(
                        root / ".saipen" / REGISTRY_FILE,
                        {"schema_version": 1, "artifacts": {}},
                        root,
                    )
                current["stores"][name] = entry
                _write_json(root / ".saipen" / STORES_FILE, current, root)
    return {"ok": True, "code": "STORE_DECLARED", "store": name, "entry": entry, "verdict": verdict}


def load_registry(project_root: str | Path) -> dict[str, Any]:
    root = _root(project_root)
    path = root / ".saipen" / REGISTRY_FILE
    value = _read_json(path, {"schema_version": 1, "artifacts": {}})
    if (
        set(value) != {"schema_version", "artifacts"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"invalid registry schema: {path}")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, dict):
        raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"artifacts must be an object: {path}")
    for name, entry in artifacts.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"invalid artifact ID: {name}")
        if not isinstance(entry, dict) or not {
            "store",
            "path",
            "sha256",
            "size",
            "recovery",
            "provenance",
        } <= set(entry):
            raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"invalid artifact record: {name}")
        if (
            not isinstance(entry["path"], str)
            or not isinstance(entry["store"], str)
            or not isinstance(entry["sha256"], str)
            or not _SHA256.fullmatch(entry["sha256"])
            or type(entry["size"]) is not int
            or entry["size"] < 0
            or not isinstance(entry["recovery"], str)
            or entry["recovery"] not in _RECOVERY
            or not isinstance(entry["provenance"], dict)
            or not isinstance(entry.get("kind", "file"), str)
            or entry.get("kind", "file") not in {"file", "directory"}
        ):
            raise StoragePolicyError("STORAGE_REGISTRY_INVALID", f"invalid artifact fields: {name}")
    return value


def _hash_file(path: Path) -> tuple[str, int]:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise StoragePolicyError("STORAGE_PATH_INVALID", f"artifact is not a regular file: {path}")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            total += len(chunk)
    after = path.stat()
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or total != info.st_size:
        raise StoragePolicyError(
            "STORAGE_SOURCE_CHANGED", f"artifact changed while reading: {path}"
        )
    return digest.hexdigest(), total


def _hash_directory(path: Path) -> tuple[str, int]:
    """Hash names, empty directories and file contents as one immutable tree."""
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or path.is_symlink()
        or bool(getattr(info, "st_file_attributes", 0) & reparse)
    ):
        raise StoragePolicyError(
            "STORAGE_PATH_INVALID", f"artifact is not an owned directory: {path}"
        )

    def fail(error: OSError) -> None:
        raise error

    directories: list[str] = []
    files: list[list[str | int]] = []
    total = 0
    for current, names, leaves in os.walk(path, topdown=True, followlinks=False, onerror=fail):
        names.sort(key=str.casefold)
        leaves.sort(key=str.casefold)
        folder = Path(current)
        relative_dir = folder.relative_to(path)
        if relative_dir != Path("."):
            directories.append(relative_dir.as_posix())
        for name in names:
            child = folder / name
            child_info = child.lstat()
            if (
                not stat.S_ISDIR(child_info.st_mode)
                or child.is_symlink()
                or bool(getattr(child_info, "st_file_attributes", 0) & reparse)
            ):
                raise StoragePolicyError(
                    "STORAGE_PATH_INVALID", f"linked/reparse directory: {child}"
                )
        for name in leaves:
            child = folder / name
            try:
                prove_owned_regular(child, kind="artifact tree file")
            except ValueError as exc:
                raise StoragePolicyError("STORAGE_PATH_INVALID", str(exc)) from exc
            digest, size = _hash_file(child)
            files.append([child.relative_to(path).as_posix(), digest, size])
            total += size
    encoded = json.dumps(
        {"directories": directories, "files": files},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), total


def _copy_object(source: Path, dest: Path, owner: Path, expected_hash: str, size: int) -> None:
    prove_owned_dir_chain(dest.parent, kind="durable artifact", ownership_root=owner)
    dest.parent.mkdir(parents=True, exist_ok=True)
    prove_owned_dir_chain(dest.parent, kind="durable artifact", ownership_root=owner)
    try:
        prove_owned_regular(dest, kind="durable artifact")
    except FileNotFoundError:
        existing = False
    else:
        existing = True
    if existing:
        actual, actual_size = _hash_file(dest)
        if (actual, actual_size) != (expected_hash, size):
            raise StoragePolicyError("STORAGE_HASH_MISMATCH", f"existing object differs: {dest}")
        return
    temporary = dest.parent / f".{dest.name}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as target:
            descriptor = -1
            with source.open("rb") as original:
                while chunk := original.read(1024 * 1024):
                    target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        actual, actual_size = _hash_file(temporary)
        if (actual, actual_size) != (expected_hash, size):
            raise StoragePolicyError(
                "STORAGE_SOURCE_CHANGED", f"source changed during copy: {source}"
            )
        # Only the digest-named object is published here. The registry pointer
        # remains unchanged until the caller's later atomic replacement.
        try:
            os.link(temporary, dest)
        except FileExistsError:
            prove_owned_regular(dest, kind="durable artifact")
            existing, existing_size = _hash_file(dest)
            if (existing, existing_size) != (expected_hash, size):
                raise StoragePolicyError("STORAGE_HASH_MISMATCH", f"object race: {dest}")
        if os.name != "nt":
            directory = os.open(dest.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        with suppress(FileNotFoundError):
            temporary.unlink()


def _copy_directory(source: Path, dest: Path, owner: Path, expected_hash: str, size: int) -> None:
    """Stage a complete adapter tree, verify, then publish its digest name."""
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    prove_owned_dir_chain(dest.parent, kind="durable artifact", ownership_root=owner)
    dest.parent.mkdir(parents=True, exist_ok=True)
    prove_owned_dir_chain(dest.parent, kind="durable artifact", ownership_root=owner)

    def existing_matches() -> bool:
        try:
            info = dest.lstat()
        except FileNotFoundError:
            return False
        if (
            not stat.S_ISDIR(info.st_mode)
            or dest.is_symlink()
            or bool(getattr(info, "st_file_attributes", 0) & reparse)
        ):
            raise StoragePolicyError(
                "STORAGE_HASH_MISMATCH", f"object path is not a directory: {dest}"
            )
        actual, actual_size = _hash_directory(dest)
        if (actual, actual_size) != (expected_hash, size):
            raise StoragePolicyError("STORAGE_HASH_MISMATCH", f"existing tree differs: {dest}")
        return True

    if existing_matches():
        return
    temporary = dest.parent / f".{dest.name}.{uuid.uuid4().hex}.tmp"
    try:
        shutil.copytree(source, temporary, symlinks=True)
        actual, actual_size = _hash_directory(temporary)
        if (actual, actual_size) != (expected_hash, size):
            raise StoragePolicyError(
                "STORAGE_SOURCE_CHANGED", f"source tree changed during copy: {source}"
            )
        prove_owned_dir_chain(dest.parent, kind="durable artifact", ownership_root=owner)
        if not existing_matches():
            try:
                os.rename(temporary, dest)
            except OSError:
                if not existing_matches():
                    raise
        if os.name != "nt":
            descriptor = os.open(dest.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary.exists():
            resolved_parent = dest.parent.resolve(strict=True)
            resolved_temporary = temporary.resolve(strict=True)
            if not _within(resolved_temporary, resolved_parent) or temporary.is_symlink():
                raise StoragePolicyError(
                    "STORAGE_OPERATION_FAILED",
                    f"temporary copy escaped its owned directory: {temporary}",
                )
            shutil.rmtree(temporary)


def promote_artifact(
    project_root: str | Path,
    artifact_id: str,
    source: str | Path,
    store_name: str,
    *,
    expected_sha256: str | None = None,
    provenance: dict[str, Any] | None = None,
    migration: bool = False,
    policy: dict | None = None,
) -> dict[str, Any]:
    """Copy and hash-verify before one atomic registry pointer replacement."""
    root = _root(project_root)
    if not _NAME.fullmatch(artifact_id):
        raise StoragePolicyError("STORAGE_PATH_INVALID", f"invalid artifact ID: {artifact_id}")
    selected = load_policy() if policy is None else policy
    source_path = _resolved_path(source, base=root)
    store = load_stores(root)["stores"].get(store_name)
    if store is None or store["class"] != "DURABLE":
        raise StoragePolicyError(
            "STORAGE_POLICY_VIOLATION", f"{store_name} is not a declared DURABLE store"
        )
    target_root = _resolved_path(store["path"], base=root)
    verdict = classify_path(target_root, "DURABLE", policy=selected)
    if not verdict["ok"]:
        raise StoragePolicyError(verdict["code"], verdict["detail"])
    registry_verdict = classify_path(root / ".saipen" / REGISTRY_FILE, "DURABLE", policy=selected)
    if not registry_verdict["ok"]:
        raise StoragePolicyError(registry_verdict["code"], registry_verdict["detail"])
    lock_path = root / ".saipen" / "locks" / "storage.lock"
    with file_writer_lock(lock_path, root):
        registry = load_registry(root)
        previous = registry["artifacts"].get(artifact_id)
        if previous is not None and not migration:
            raise StoragePolicyError(
                "STORAGE_POLICY_VIOLATION", f"{artifact_id} already exists; use migration"
            )
        if migration and (previous is None or _resolved_path(previous["path"]) != source_path):
            raise StoragePolicyError(
                "STORAGE_REGISTRY_INVALID", f"{artifact_id} has no matching legacy source"
            )
        if not migration:
            findings = validate_storage(root, policy=selected)
            if findings:
                first = findings[0]
                raise StoragePolicyError(
                    "STORAGE_REGISTRY_INVALID",
                    f"existing canonical state is invalid ({first['code']}): {first['detail']}",
                )
        artifact_provenance = dict((previous or {}).get("provenance", {})) if migration else {}
        artifact_provenance.update(provenance or {})
        if store["recovery"] == "RECONSTRUCTABLE" and not (
            isinstance(artifact_provenance.get("rebuild_command"), str)
            and artifact_provenance["rebuild_command"].strip()
        ):
            raise StoragePolicyError(
                "STORAGE_RECOVERY_UNPROVEN",
                f"{artifact_id}: RECONSTRUCTABLE requires a deterministic rebuild_command",
            )
        kind = "directory" if source_path.is_dir() else "file"
        digest, size = (
            _hash_directory(source_path) if kind == "directory" else _hash_file(source_path)
        )
        if expected_sha256 is not None and expected_sha256 != digest:
            raise StoragePolicyError(
                "STORAGE_HASH_MISMATCH", f"{artifact_id}: expected {expected_sha256}, got {digest}"
            )
        if previous is not None and previous["sha256"] != digest:
            raise StoragePolicyError(
                "STORAGE_HASH_MISMATCH", f"{artifact_id}: source differs from recorded hash"
            )
        if previous is not None and previous.get("kind", "file") != kind:
            raise StoragePolicyError(
                "STORAGE_HASH_MISMATCH", f"{artifact_id}: artifact kind changed"
            )
        dest = target_root / ("trees" if kind == "directory" else "objects") / digest[:2] / digest
        final_verdict = classify_path(dest, "DURABLE", policy=selected)
        if not final_verdict["ok"]:
            raise StoragePolicyError(final_verdict["code"], final_verdict["detail"])
        if kind == "directory":
            _copy_directory(source_path, dest, target_root, digest, size)
            verified, verified_size = _hash_directory(dest)
        else:
            _copy_object(source_path, dest, target_root, digest, size)
            verified, verified_size = _hash_file(dest)
        if (verified, verified_size) != (digest, size):
            raise StoragePolicyError(
                "STORAGE_HASH_MISMATCH", f"durable copy failed verification: {dest}"
            )
        record = {
            "store": store_name,
            "path": str(dest),
            "sha256": digest,
            "size": size,
            "kind": kind,
            "recovery": store["recovery"],
            "provenance": {**artifact_provenance, "source": str(source_path)},
        }
        origin = classify_path(source_path, "EPHEMERAL", policy=selected)
        if "matched_ephemeral_root" in origin:
            record["provenance"]["transient_source"] = True
            record["provenance"]["source_ephemeral_root"] = origin["matched_ephemeral_root"]
        if previous is not None:
            record["provenance"]["migrated_from"] = previous["path"]
        with _machine_policy_lock(policy):
            _require_current_policy(selected, policy)
            for candidate in (dest, root / ".saipen" / REGISTRY_FILE):
                fresh = classify_path(candidate, "DURABLE", policy=selected)
                if not fresh["ok"]:
                    raise StoragePolicyError(fresh["code"], fresh["detail"])
            if not _within(_resolved_path(dest), _resolved_path(store["path"], base=root)):
                raise StoragePolicyError(
                    "STORAGE_POLICY_VIOLATION", "promoted object escaped its declared store"
                )
            registry["artifacts"][artifact_id] = record
            _write_json(root / ".saipen" / REGISTRY_FILE, registry, root)
    return {"ok": True, "code": "ARTIFACT_PROMOTED", "artifact": artifact_id, "record": record}


def validate_storage(
    project_root: str | Path, *, policy: dict | None = None
) -> list[dict[str, Any]]:
    """Inspect every declared store and canonical artifact, including missing state."""
    root = _root(project_root)
    selected = load_policy() if policy is None else policy
    findings: list[dict[str, Any]] = []
    try:
        stores = load_stores(root)["stores"]
        registry = load_registry(root)["artifacts"]
    except StoragePolicyError as exc:
        return [{"code": exc.code, "detail": exc.detail}]
    if (
        any(entry["class"] == "DURABLE" for entry in stores.values())
        and not (root / ".saipen" / REGISTRY_FILE).is_file()
    ):
        findings.append(
            {
                "code": "STORAGE_REGISTRY_MISSING",
                "path": str(root / ".saipen" / REGISTRY_FILE),
                "recovery": "PARTIAL",
                "detail": "declared DURABLE stores have lost their canonical registry; "
                "inventory surviving objects and provenance before recovery",
            }
        )
    if any(entry["class"] == "DURABLE" for entry in stores.values()):
        declaration_verdict = classify_path(
            root / ".saipen" / STORES_FILE, "DURABLE", policy=selected
        )
        if not declaration_verdict["ok"]:
            findings.append(
                {"code": declaration_verdict["code"], "detail": declaration_verdict["detail"]}
            )
    if registry:
        registry_verdict = classify_path(
            root / ".saipen" / REGISTRY_FILE, "DURABLE", policy=selected
        )
        if not registry_verdict["ok"]:
            findings.append(
                {"code": registry_verdict["code"], "detail": registry_verdict["detail"]}
            )
    for verdict in store_verdicts(root, policy=selected):
        if not verdict["ok"]:
            findings.append(
                {"code": verdict["code"], "store": verdict["store"], "detail": verdict["detail"]}
            )
    for artifact_id, entry in registry.items():
        store = stores.get(entry["store"])
        if store is None or store["class"] != "DURABLE":
            findings.append(
                {
                    "code": "STORAGE_POLICY_VIOLATION",
                    "artifact": artifact_id,
                    "detail": "canonical artifact has no DURABLE store",
                }
            )
            continue
        verdict = classify_path(entry["path"], "DURABLE", policy=selected)
        if not verdict["ok"]:
            findings.append(
                {"code": verdict["code"], "artifact": artifact_id, "detail": verdict["detail"]}
            )
        path = _resolved_path(entry["path"])
        kind = entry.get("kind", "file")
        if not (path.is_dir() if kind == "directory" else path.is_file()):
            finding = {
                "code": "STORAGE_ARTIFACT_MISSING",
                "artifact": artifact_id,
                "path": str(path),
                "recovery": entry["recovery"],
                "detail": f"{artifact_id} is missing; recovery={entry['recovery']}; "
                "do not initialize a fresh registry",
            }
            rebuild = entry["provenance"].get("rebuild_command")
            if entry["recovery"] == "RECONSTRUCTABLE" and isinstance(rebuild, str):
                finding["rebuild_command"] = rebuild
            findings.append(finding)
            continue
        if not verdict["ok"]:
            continue
        target_root = _resolved_path(store["path"], base=root)
        if not _within(path, target_root):
            findings.append(
                {
                    "code": "STORAGE_POLICY_VIOLATION",
                    "artifact": artifact_id,
                    "detail": f"canonical artifact {path} is outside its store {target_root}",
                }
            )
            continue
        try:
            if kind == "directory":
                actual, size = _hash_directory(path)
            else:
                prove_owned_regular(path, kind="canonical artifact")
                actual, size = _hash_file(path)
        except (OSError, ValueError) as exc:
            findings.append(
                {
                    "code": (
                        exc.code
                        if isinstance(exc, StoragePolicyError)
                        else "STORAGE_PATH_INVALID"
                        if isinstance(exc, ValueError)
                        else "STORAGE_ARTIFACT_MISSING"
                    ),
                    "artifact": artifact_id,
                    "path": str(path),
                    "recovery": entry["recovery"],
                    "detail": str(exc),
                }
            )
            continue
        if (actual, size) != (entry["sha256"], entry["size"]):
            findings.append(
                {
                    "code": "STORAGE_HASH_MISMATCH",
                    "artifact": artifact_id,
                    "path": str(path),
                    "detail": f"{artifact_id} differs from recorded digest/size",
                }
            )
    return findings

"""Machine storage policy and path classification.

Durable roots are explicit operator decisions. OS temporary roots and the
operator's additional cleanup roots take precedence over them. Scratch is safe
to delete at any instant; the caller must never publish it as canonical state.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import read_bound_regular_bytes, safe_atomic_write_bytes

POLICY_FILE = "STORAGE_POLICY.json"
POLICY_SCHEMA = 1
_POLICY_KEYS = {"schema_version", "durable_roots", "ephemeral_roots", "scratch_root"}
_CLASSES = {"DURABLE", "EPHEMERAL", "CACHE", "EXTERNAL"}
_MAX_POLICY_BYTES = 1024 * 1024
_UNEXPANDED = re.compile(r"%[A-Za-z_][A-Za-z0-9_]*%|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")


class StoragePolicyError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def policy_path(user_config_home: Path | str | None = None) -> Path:
    """Use SAIPEN's existing machine-profile directory, not project memory."""
    from userperson import user_config_home_resolved

    return user_config_home_resolved(user_config_home) / POLICY_FILE


def _resolved_path(value: str | Path, *, base: Path | str | None = None) -> Path:
    raw = str(value).strip()
    if not raw:
        raise StoragePolicyError("STORAGE_PATH_INVALID", "storage path is empty")
    expanded = os.path.expandvars(raw)
    if _UNEXPANDED.search(expanded):
        raise StoragePolicyError(
            "STORAGE_PATH_INVALID", f"storage path has an unresolved environment variable: {raw}"
        )
    try:
        candidate = Path(expanded).expanduser()
        if not candidate.is_absolute():
            candidate = Path(base if base is not None else Path.cwd()) / candidate
        return candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise StoragePolicyError("STORAGE_PATH_INVALID", f"cannot resolve {raw}: {exc}") from exc


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _within(path: Path, root: Path) -> bool:
    candidate = _path_key(path)
    boundary = _path_key(root)
    try:
        return os.path.commonpath((candidate, boundary)) == boundary
    except ValueError:
        return False


def _roots(values: list[str], *, base: Path | str | None = None) -> list[Path]:
    resolved = [_resolved_path(value, base=base) for value in values]
    return sorted(
        {str(path): path for path in resolved}.values(), key=lambda p: len(str(p)), reverse=True
    )


def os_temporary_roots(environ: dict[str, str] | None = None) -> list[str]:
    """The live host's temporary roots are always disposable."""
    env = os.environ if environ is None else environ
    values = [env.get(name, "") for name in ("TEMP", "TMP", "TMPDIR")]
    values.append(tempfile.gettempdir())
    roots: list[str] = []
    for raw in values:
        if not raw:
            continue
        try:
            path = str(_resolved_path(raw))
        except StoragePolicyError:
            continue
        if path not in roots:
            roots.append(path)
    return roots


def empty_policy() -> dict[str, Any]:
    return {
        "schema_version": POLICY_SCHEMA,
        "durable_roots": [],
        "ephemeral_roots": [],
        "scratch_root": None,
    }


def _validate_policy(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _POLICY_KEYS:
        raise StoragePolicyError(
            "STORAGE_POLICY_INVALID", "storage policy has missing or unknown fields"
        )
    if value.get("schema_version") != POLICY_SCHEMA:
        raise StoragePolicyError("STORAGE_POLICY_INVALID", "unsupported storage policy schema")
    for field in ("durable_roots", "ephemeral_roots"):
        roots = value[field]
        if not isinstance(roots, list) or any(
            not isinstance(item, str) or not item for item in roots
        ):
            raise StoragePolicyError("STORAGE_POLICY_INVALID", f"{field} must be a list of paths")
        if len(roots) != len(set(roots)):
            raise StoragePolicyError("STORAGE_POLICY_INVALID", f"{field} contains duplicates")
    if value["scratch_root"] is not None and not isinstance(value["scratch_root"], str):
        raise StoragePolicyError("STORAGE_POLICY_INVALID", "scratch_root must be a path or null")
    for field in ("durable_roots", "ephemeral_roots"):
        for root in value[field]:
            path = _resolved_path(root)
            if str(path) != root:
                raise StoragePolicyError(
                    "STORAGE_POLICY_INVALID", f"{field} is not canonical: {root}"
                )
    if value["scratch_root"] is not None:
        path = _resolved_path(value["scratch_root"])
        if str(path) != value["scratch_root"]:
            raise StoragePolicyError("STORAGE_POLICY_INVALID", "scratch_root is not canonical")
    return value


def load_policy(user_config_home: Path | str | None = None) -> dict[str, Any]:
    path = policy_path(user_config_home)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return empty_policy()
    except OSError as exc:
        raise StoragePolicyError("STORAGE_POLICY_INVALID", f"cannot inspect {path}: {exc}") from exc
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISREG(info.st_mode)
        or path.is_symlink()
        or bool(getattr(info, "st_file_attributes", 0) & reparse)
    ):
        raise StoragePolicyError(
            "STORAGE_POLICY_INVALID", f"policy path is not an owned file: {path}"
        )
    if info.st_size > _MAX_POLICY_BYTES:
        raise StoragePolicyError("STORAGE_POLICY_INVALID", "storage policy exceeds size limit")
    try:
        raw = read_bound_regular_bytes(path, info, max_bytes=_MAX_POLICY_BYTES)
        selected = _validate_policy(json.loads(raw.decode("utf-8")))
        root = next(
            (item for item in effective_ephemeral_roots(selected) if _within(path.resolve(), item)),
            None,
        )
        if root is not None:
            raise StoragePolicyError(
                "STORAGE_POLICY_VIOLATION",
                f"policy file {path} is under ephemeral root {root}; move machine configuration "
                "to a persistent user configuration home",
            )
        return selected
    except StoragePolicyError:
        raise
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise StoragePolicyError("STORAGE_POLICY_INVALID", f"cannot read {path}: {exc}") from exc


def effective_ephemeral_roots(policy: dict[str, Any]) -> list[Path]:
    values = os_temporary_roots() + policy["ephemeral_roots"]
    if policy["scratch_root"]:
        values.append(policy["scratch_root"])
    return _roots(values)


def classify_path(
    requested: str | Path,
    required_class: str,
    *,
    policy: dict[str, Any] | None = None,
    base: Path | str | None = None,
) -> dict[str, Any]:
    """Classify an intended use; unknown never grants a durable write."""
    if required_class not in _CLASSES:
        raise StoragePolicyError(
            "STORAGE_POLICY_INVALID", f"unknown storage class {required_class}"
        )
    selected = _validate_policy(policy if policy is not None else load_policy())
    try:
        path = _resolved_path(requested, base=base)
        ephemeral = next(
            (root for root in effective_ephemeral_roots(selected) if _within(path, root)), None
        )
        durable = next(
            (root for root in _roots(selected["durable_roots"]) if _within(path, root)), None
        )
    except StoragePolicyError as exc:
        return {
            "ok": False,
            "code": "UNKNOWN_REQUIRES_EXPLICIT_DECISION",
            "requested": str(requested),
            "required_class": required_class,
            "detail": exc.detail,
        }
    result: dict[str, Any] = {
        "requested": str(requested),
        "resolved": str(path),
        "required_class": required_class,
    }
    if required_class == "EXTERNAL":
        return result | {
            "ok": True,
            "code": "EXTERNAL_USER_OWNED",
            "detail": "user-owned path; SAIPEN may inspect but cannot relocate or delete it",
        }
    if ephemeral is not None:
        if required_class == "DURABLE":
            return result | {
                "ok": False,
                "code": "STORAGE_POLICY_VIOLATION",
                "matched_ephemeral_root": str(ephemeral),
                "detail": (
                    f"{path} is under auto-cleaned/temporary root {ephemeral}; DURABLE state "
                    "could be lost at any moment. Configure a trusted durable root and "
                    "move/copy the artifact there before using it as canonical state."
                ),
            }
        return result | {
            "ok": True,
            "code": "EPHEMERAL_ALLOWED" if required_class == "EPHEMERAL" else "CACHE_ALLOWED",
            "matched_ephemeral_root": str(ephemeral),
        }
    if required_class in {"EPHEMERAL", "CACHE"}:
        return result | {
            "ok": True,
            "code": "EPHEMERAL_ALLOWED" if required_class == "EPHEMERAL" else "CACHE_ALLOWED",
            "detail": "disposable use is allowed; never persist this path as canonical evidence",
        }
    if durable is not None:
        return result | {
            "ok": True,
            "code": "DURABLE_ALLOWED",
            "matched_durable_root": str(durable),
        }
    return result | {
        "ok": False,
        "code": "UNKNOWN_REQUIRES_EXPLICIT_DECISION",
        "detail": (
            f"{path} is outside every explicitly trusted durable root. "
            "Use 'saipen storage durable add <root>' after confirming its retention policy."
        ),
    }


def save_policy(
    policy: dict[str, Any],
    *,
    user_config_home: Path | str | None = None,
    expected_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist explicit policy without ever moving files it describes."""
    selected = _validate_policy(policy)
    path = policy_path(user_config_home)
    ephemeral = effective_ephemeral_roots(selected)
    root = next((item for item in ephemeral if _within(path.resolve(strict=False), item)), None)
    if root is not None:
        raise StoragePolicyError(
            "STORAGE_POLICY_VIOLATION",
            f"policy file {path} is under ephemeral root {root}; set SAIPEN_USER_CONFIG_HOME "
            "to a persistent directory before saving storage policy",
        )
    for durable in selected["durable_roots"]:
        if _resolved_path(durable).is_file():
            raise StoragePolicyError("STORAGE_PATH_INVALID", f"durable root is a file: {durable}")
        verdict = classify_path(durable, "DURABLE", policy=selected)
        if verdict["code"] == "STORAGE_POLICY_VIOLATION":
            raise StoragePolicyError(verdict["code"], verdict["detail"])
    from .lock import file_writer_lock

    home = path.parent
    with file_writer_lock(home / "locks" / "storage.lock", home):
        current = load_policy(user_config_home)
        if expected_policy is not None and current != expected_policy:
            raise StoragePolicyError(
                "STORAGE_POLICY_CHANGED",
                "machine storage policy changed concurrently; reload and retry",
            )
        if current != selected:
            data = (json.dumps(selected, indent=2, sort_keys=True) + "\n").encode("utf-8")
            safe_atomic_write_bytes(path, data, kind="storage policy", ownership_root=home)
    return {"ok": True, "code": "STORAGE_POLICY_SAVED", "path": str(path), "policy": selected}


def configure_root(
    action: str,
    value: str | Path | None,
    *,
    user_config_home: Path | str | None = None,
) -> dict[str, Any]:
    """Set/add/remove machine roots; reject overlap that would bless temp."""
    policy = load_policy(user_config_home)
    original = deepcopy(policy)
    resolved = str(_resolved_path(value)) if value is not None else None
    if resolved is None and action != "scratch-unset":
        raise StoragePolicyError("STORAGE_PATH_INVALID", f"{action} requires a path")
    if action == "durable-set":
        policy["durable_roots"] = [resolved]
    elif action == "durable-add":
        policy["durable_roots"] = sorted(set(policy["durable_roots"]) | {resolved})
    elif action == "durable-remove":
        policy["durable_roots"] = [root for root in policy["durable_roots"] if root != resolved]
    elif action == "ephemeral-add":
        policy["ephemeral_roots"] = sorted(set(policy["ephemeral_roots"]) | {resolved})
    elif action == "ephemeral-remove":
        policy["ephemeral_roots"] = [root for root in policy["ephemeral_roots"] if root != resolved]
    elif action == "scratch-set":
        policy["scratch_root"] = resolved
    elif action == "scratch-unset":
        policy["scratch_root"] = None
    else:
        raise StoragePolicyError(
            "STORAGE_POLICY_INVALID", f"unknown storage root operation {action}"
        )
    return save_policy(policy, user_config_home=user_config_home, expected_policy=original)

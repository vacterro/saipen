"""Wave-1 adaptive-runtime identity and capability model.

This module deliberately knows nothing about SAIPEN ownership, Work, routing,
or provider strategy.  ``--agent`` is supplied by the caller as the acting
seat; optional runtime metadata describes the harness/model operating that
seat.  Missing capability evidence is represented by ``None`` (UNKNOWN),
never promoted to ``False`` or guessed from an executable/model name.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from ..paths import read_bound_regular_bytes

RUNTIME_INFO_SCHEMA_VERSION = 1
ENV_RUNTIME_INFO = "SAIPEN_RUNTIME_INFO"
MAX_RUNTIME_INFO_BYTES = 64 * 1024
MAX_IDENTITY_CHARS = 128

# Bounded operational facts, not personality traits.  A missing member is
# emitted as JSON null so UNKNOWN cannot silently become FALSE.
CAPABILITY_NAMES = (
    "shell",
    "filesystem",
    "patch",
    "browser",
    "web",
    "subagents",
    "parallel_subagents",
    "skills",
    "mcp",
    "structured_output",
    "persistent_session",
    "context_compaction",
    "reasoning_effort",
    "tool_search",
    "programmatic_tool_calling",
)

_IDENTITY_FIELDS = ("harness", "provider", "model", "variant")
_TOP_LEVEL_FIELDS = frozenset({"schema_version", *_IDENTITY_FIELDS, "capabilities"})
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class RuntimeInfoError(ValueError):
    """Controlled refusal for untrusted runtime metadata."""


def _safe_identity(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeInfoError(f"runtime-info field {field!r} must be a string or null")
    clean = value.strip()
    if not clean:
        raise RuntimeInfoError(f"runtime-info field {field!r} must not be empty")
    if len(clean) > MAX_IDENTITY_CHARS:
        raise RuntimeInfoError(
            f"runtime-info field {field!r} exceeds {MAX_IDENTITY_CHARS} characters"
        )
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in clean):
        raise RuntimeInfoError(f"runtime-info field {field!r} contains control characters")
    return clean


def _read_runtime_info(path: Path) -> dict[str, Any]:
    try:
        info = path.lstat()
    except OSError as exc:
        raise RuntimeInfoError(f"runtime-info is not readable: {path}: {exc}") from None
    attributes = getattr(info, "st_file_attributes", 0)
    if path.is_symlink() or attributes & _REPARSE_POINT or not stat.S_ISREG(info.st_mode):
        raise RuntimeInfoError(
            f"runtime-info must be a regular non-symlink/non-reparse file: {path}"
        )
    try:
        raw = read_bound_regular_bytes(path, info, max_bytes=MAX_RUNTIME_INFO_BYTES)
    except (OSError, ValueError) as exc:
        raise RuntimeInfoError(f"runtime-info cannot be read safely: {path}: {exc}") from None
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise RuntimeInfoError(f"runtime-info is not valid UTF-8: {exc}") from None
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeInfoError(f"runtime-info repeats JSON field {key!r}")
            result[key] = value
        return result

    def reject_constant(token: str) -> None:
        raise RuntimeInfoError(f"runtime-info contains non-JSON numeric constant {token!r}")

    try:
        document = json.loads(
            text, object_pairs_hook=unique_object, parse_constant=reject_constant
        )
    except json.JSONDecodeError as exc:
        raise RuntimeInfoError(
            f"runtime-info is malformed JSON at line {exc.lineno}, column {exc.colno}"
        ) from None
    if not isinstance(document, dict):
        raise RuntimeInfoError("runtime-info root must be a JSON object")
    return document


def _validate_document(document: Mapping[str, Any]) -> dict[str, Any]:
    unknown_fields = sorted(set(document) - _TOP_LEVEL_FIELDS)
    if unknown_fields:
        if "agent" in unknown_fields:
            raise RuntimeInfoError(
                "runtime-info must not define 'agent'; --agent/STATE owns the acting seat"
            )
        raise RuntimeInfoError(
            "runtime-info has unsupported field(s): " + ", ".join(unknown_fields)
        )

    schema = document.get("schema_version", RUNTIME_INFO_SCHEMA_VERSION)
    if type(schema) is not int or schema != RUNTIME_INFO_SCHEMA_VERSION:
        raise RuntimeInfoError(
            f"runtime-info schema_version must be {RUNTIME_INFO_SCHEMA_VERSION}, got {schema!r}"
        )

    capabilities_raw = document.get("capabilities", {})
    if not isinstance(capabilities_raw, dict):
        raise RuntimeInfoError("runtime-info 'capabilities' must be a JSON object")
    unknown_capabilities = sorted(set(capabilities_raw) - set(CAPABILITY_NAMES))
    if unknown_capabilities:
        raise RuntimeInfoError(
            "runtime-info has unsupported capability field(s): "
            + ", ".join(unknown_capabilities)
        )
    capabilities: dict[str, bool | None] = {}
    for name in CAPABILITY_NAMES:
        value = capabilities_raw.get(name)
        if value is not None and not isinstance(value, bool):
            raise RuntimeInfoError(f"runtime capability {name!r} must be true, false, or null")
        capabilities[name] = value

    result: dict[str, Any] = {
        "schema_version": RUNTIME_INFO_SCHEMA_VERSION,
        **{field: _safe_identity(document.get(field), field) for field in _IDENTITY_FIELDS},
        "capabilities": capabilities,
    }
    return result


def load_runtime_info(
    explicit_path: str | Path | None = None, *, env: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Load one runtime snapshot by explicit-first precedence.

    Precedence is ``explicit_path`` > ``SAIPEN_RUNTIME_INFO`` > UNKNOWN.  The
    environment value is a JSON file path, not inline JSON, which keeps shell
    quoting and size behavior deterministic.  No directory or file is created.
    """

    source_env = os.environ if env is None else env
    selected: str | Path | None = explicit_path
    source = "explicit_cli" if explicit_path is not None else "unknown"
    if selected is None:
        declared = str(source_env.get(ENV_RUNTIME_INFO, "") or "").strip()
        if declared:
            selected = declared
            source = "environment"
    if selected is None:
        empty = _validate_document({})
        return {**empty, "source": source, "present": False}
    raw_path = str(selected).strip()
    if not raw_path:
        raise RuntimeInfoError("runtime-info path must not be empty")
    parsed = _validate_document(_read_runtime_info(Path(raw_path)))
    return {**parsed, "source": source, "present": True}


def runtime_projection(
    agent: str,
    explicit_path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the portable read-only Wave-1 runtime projection.

    ``agent`` is copied from the ownership layer and is never derived from the
    runtime-info document.  Runtime metadata is telemetry only and is not
    persisted by this function.
    """

    seat = _safe_identity(agent, "agent")
    if seat is None:  # defensive: callers always have a seat
        raise RuntimeInfoError("acting agent seat is required")
    info = load_runtime_info(explicit_path, env=env)
    return {
        "agent": seat,
        "runtime_info_source": info["source"],
        "runtime_info_present": info["present"],
        "schema_version": info["schema_version"],
        "harness": info["harness"],
        "provider": info["provider"],
        "model": info["model"],
        "variant": info["variant"],
        "capabilities": info["capabilities"],
    }

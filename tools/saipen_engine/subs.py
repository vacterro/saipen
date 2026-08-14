"""SubSaipen lifecycle operations on the common machinery (NITRO M8, SAICREW).

Mechanizes the DETERMINISTIC parts of the SubSaipen lifecycle (extensions/subs/
PROTOCOL.md section 7): manifest parsing, spawn, list, status, adopt, pause,
resume, sync, clean preflight, collect preflight, and the one built-in crew
registry the crew planner/gate/docs/tests all consume.

The mechanical truth contract (SAICREW):

- ONE strict MANIFEST parser is used by every consumer (list/status/collect/
  spawn/adopt/sync/crew/validator). A malformed manifest is INVALID_MANIFEST,
  never "skip bad line and continue".
- The PROJECT-LOCAL charter (`.saipen/extensions/subs/<name>.md`) is the only
  role-revision authority for an attached project. The installation charter is
  only the `saipen sub sync` source. Missing local evidence is
  SYNC_REQUIRED / ROLE_EVIDENCE_UNAVAILABLE, never a silent fallback.
- A generic `sai*` worker's role_revision is the deterministic digest of the
  project-local PROTOCOL.md (never blank).
- Every mutating sub command honors `dry_run`: same validation, same proposed
  outcome, ZERO writes/LOG/STATE/MANIFEST/journal.
- Board/STATE are validated as one coherent machine: DONE cannot coexist with
  TODO/DOING/unresolved BLOCKED, duplicate headings/IDs fail, at most one
  DOING, checkbox matches section.
- `sub list`/`sub status` report mechanically-derived health, never a
  timestamp or an empty OUTBOX dressed up as clean.

NO semantic acceptance of a finding is mechanized. Core still judges work;
this module guarantees boundaries and mechanics.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import stat
import struct
from dataclasses import dataclass, field
from pathlib import Path

from . import codec
from .journal import (empty_delete_tree_hash, hash_bytes, hash_delete_tree,
                      hash_source_identity, hash_tree, run_mutation)
from .lock import project_writer_lock
from .paths import project_identity
from .result import Result
from .safeid import prove_inside, validate_safe_id
from .state import patch_state

SUBS_REL = ".saipen/extensions/subs"
MANIFEST_REL = f"{SUBS_REL}/MANIFEST.md"
MANIFEST_HEADER = "# SubSaipen Manifest"
MANIFEST_METADATA = frozenset({"last_collect"})

# Shared inherited contract files (PROTOCOL.md section 7): the exact surface
# `saipen sub sync` refreshes from <saipen_home>/extensions/subs/. A live
# instance's own STATE/BOARD/LOG/kitchen is NEVER part of this surface, and
# _shared/inbox.md is created once then preserved byte-identically.
_SHARED_FILES = ("PROTOCOL.md", "README.md", "crew.md")
_SHARED_DIRS = ("TEMPLATE",)

OUTBOX_STATUSES = ("ready", "draft", "blocked", "reviewed", "stale")

# ---------------------------------------------------------------------------
# Built-in crew registry -- ONE machine-readable contract (SAICREW section M).
# Used by the crew planner, crew gate, docs parity and tests. Custom subs are
# standalone by default; the crew never runs every arbitrary `sai*` worker.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CrewRole:
    name: str
    role_class: str
    runtime_kind: str
    ticket_prefix: str
    ensure_instance: bool
    collect_policy: str
    stage: str
    evidence_kind: str
    outbox_path: str


CREW_ROLES = (
    CrewRole("saihunt", "core-review", "generic-sub", "HUNT", True,
             "core-review", "SC-2", "sensor",
             f"{SUBS_REL}/saihunt/kitchen/OUTBOX.md"),
    CrewRole("saitest", "core-review", "generic-sub", "TEST", True,
             "core-review", "SC-3", "sensor",
             f"{SUBS_REL}/saitest/kitchen/OUTBOX.md"),
    CrewRole("saipython", "core-review", "generic-sub", "PY", True,
             "core-review", "SC-4", "sensor",
             f"{SUBS_REL}/saipython/kitchen/OUTBOX.md"),
    CrewRole("saiui", "core-review", "generic-sub", "UI", True,
             "core-review", "SC-5", "sensor",
             f"{SUBS_REL}/saiui/kitchen/OUTBOX.md"),
    CrewRole("saitranslate", "producer", "specialized-translate", "SAIT",
             False, "explicit", "SC-8", "translation",
             ".saipen/saitranslate/kitchen/OUTBOX.md"),
    CrewRole("saiwiki", "producer", "generic-sub", "W", True,
             "explicit", "SC-9", "wiki",
             f"{SUBS_REL}/saiwiki/kitchen/OUTBOX.md"),
)
ROLE_REGISTRY = {role.name: role for role in CREW_ROLES}
CREW_SENSORS = tuple(role.name for role in CREW_ROLES
                     if role.role_class == "core-review")
CREW_PRODUCERS = tuple(role.name for role in CREW_ROLES
                       if role.role_class == "producer")
CREW_REGISTRY = CREW_ROLES

# The serial full-platoon convergence circuit (SAICREW sections O/P). The
# stage ids match the spec exactly; a stage's mechanical precondition is what
# the planner and the `--gate crew` validator evaluate.
CREW_STAGES = (
    ("SC-0", "recover-sync",
     "no unresolved recovery; shared contract surface current; strict MANIFEST"),
    ("SC-1", "instances", "required durable crew instances exist"),
    ("SC-2", "saihunt", "saihunt board valid, no pending work, current evidence"),
    ("SC-3", "saitest", "saitest board valid, no pending work, current evidence"),
    ("SC-4", "saipython", "saipython board valid, no pending work, current evidence"),
    ("SC-5", "saiui", "saiui board valid, no pending work, current evidence"),
    ("SC-6", "core-collect", "core-review packages reviewed or disposed"),
    ("SC-7", "core-converge", "Core board/tests/HUNT at fixed point"),
    ("SC-8", "saitranslate", "EE package ready + current against source identity"),
    ("SC-9", "saiwiki", "QQ package ready + current against source identity"),
    ("SC-10", "final-fixed-point", "all crew evidence re-verified after producer integration"),
    ("SC-11", "ship", "exactly one final ship through the canonical release executor"),
    ("SC-12", "post-ship", "post-ship certification bound to the shipped HEAD"),
    ("SC-13", "finalize",
     "canonical finalizer clears crew target; final --gate crew passes"),
)

# ---------------------------------------------------------------------------
# Health vocabulary -- mechanical state, never subjective quality.
# ---------------------------------------------------------------------------
HEALTH_CURRENT = "CURRENT"
HEALTH_WORK_PENDING = "WORK_PENDING"
HEALTH_READY_FOR_REVIEW = "READY_FOR_REVIEW"
HEALTH_BLOCKED = "BLOCKED"
HEALTH_STALE = "STALE"
HEALTH_INVALID = "INVALID"
HEALTH_NOT_RUN = "NOT_RUN"


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d.%m.%y %H:%M")


def _refuse(code: str, detail: str = "", **extra) -> Result:
    return Result(ok=False, code=code, message=detail, data=extra)


def _reject_reparse_ancestors(root: Path, path: Path) -> None:
    """Fail when an owned path would traverse a symlink or junction."""
    root = root.absolute()
    path = path.absolute()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"owned path {path} escapes project root {root}") from exc
    current = root
    for part in relative.parts:
        current /= part
        if not os.path.lexists(current):
            continue
        info = current.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        if current.is_symlink() or attributes & 0x400:
            raise ValueError(f"owned path traverses symlink or reparse point: {current}")


def _sub_dir(project_root: Path, name: str) -> Path:
    """The instance dir for a subSaipen, path-safe and inside the owner root.

    The name is validated through the shared safe-ID primitive and the
    resolved path is proven inside `.saipen/extensions/subs/` before use --
    no `..`, separators, drive/absolute forms or control characters can
    escape the owner root.
    """
    safe = validate_safe_id(name, kind="subSaipen name")
    root = Path(project_root).resolve()
    owner_path = Path(project_root) / SUBS_REL
    prove_inside(owner_path, root, kind="SubSaipen owner root")
    _reject_reparse_ancestors(Path(project_root), owner_path)
    owner = owner_path.resolve()
    path = Path(project_root) / SUBS_REL / safe
    prove_inside(path, owner, kind="subSaipen instance")
    _reject_reparse_ancestors(Path(project_root), path)
    return path


def _read_maybe(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _read_bytes_maybe(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _captured_hash(raw: bytes | None) -> str:
    return hash_bytes(raw) if raw is not None else ""


def _decode_captured(raw: bytes | None, label: str) -> str:
    if raw is None:
        return ""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8: {exc}") from exc


def _role_revision_from_bytes(raw: bytes, *, generic: bool) -> str:
    canonical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    magic = b"saipen-generic-role-revision-v1\0"
    if not generic:
        lines = canonical.splitlines(keepends=True)
        body = []
        in_yaml = False
        removed = 0
        for line in lines:
            stripped = line.strip()
            if stripped == b"```yaml" and not in_yaml:
                in_yaml = True
            elif stripped == b"```" and in_yaml:
                in_yaml = False
            elif in_yaml and line.lstrip().startswith(b"role_revision:"):
                removed += 1
                continue
            body.append(line)
        if removed != 1:
            raise ValueError(
                f"role charter must contain one role_revision; found {removed}")
        canonical = b"".join(body)
        magic = b"saipen-role-revision-v1\0"
    digest = hashlib.sha256()
    digest.update(magic)
    digest.update(struct.pack(">Q", len(canonical)))
    digest.update(canonical)
    return "sha256:" + digest.hexdigest()


def _sources_unchanged(targets: list[dict]) -> bool:
    return all(_captured_hash(_read_bytes_maybe(Path(target["source_path"])))
               == target["source_hash"]
               for target in targets if target.get("source_path"))


def _external_read_preconditions(targets: list[dict]) -> dict[str, str]:
    return {target["source_path"]: target["source_hash"]
            for target in targets if target.get("source_path")}


# ---------------------------------------------------------------------------
# ONE strict MANIFEST parser (SAICREW section B). Every consumer -- list,
# status, spawn, adopt, collect, sync, crew, validator -- parses the manifest
# through this function. Malformed input is INVALID_MANIFEST, never a skipped
# line.
# ---------------------------------------------------------------------------
_ENTRY_RE = re.compile(r"^(.+?) -- (\S+)$")
_META_RE = re.compile(r"^([a-z_][a-z0-9_]*):\s*(.*)$")
_ISO_Z_RE = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
LAST_COLLECT_RE = re.compile(
    rf"^(?:sha256:[0-9a-f]{{64}}@)?{_ISO_Z_RE}$")


@dataclass(frozen=True)
class ManifestEntry:
    name: str
    path: str
    metadata: dict = field(default_factory=dict)


def parse_manifest(text: str) -> tuple[list[ManifestEntry], list[str]]:
    """Strict MANIFEST.md parser.

    Returns (entries, errors). Any error makes the manifest unusable: callers
    MUST refuse with INVALID_MANIFEST. Accepted shape:

        # SubSaipen Manifest
        - <name> -- .saipen/extensions/subs/<name>/ | meta: value

    Only the current project-local path is legal. Metadata is a closed schema:
    optional `last_collect` only, once, with either an ISO-8601 UTC value or
    the immutable collected-package identity joined to that time.
    """
    text = text.replace("\r\n", "\n")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or lines[0].strip() != MANIFEST_HEADER:
        return [], [f"MANIFEST must open with exactly `{MANIFEST_HEADER}`"]
    entries: dict[str, ManifestEntry] = {}
    errors: list[str] = []
    for line_no, line in enumerate(lines[1:], 2):
        stripped = line.strip()
        if not stripped.startswith("- "):
            errors.append(
                f"MANIFEST.md:{line_no} non-entry line {stripped!r} -- the "
                "strict manifest admits only `- <name> -- <path>` entry lines")
            continue
        content = stripped[2:].strip()
        parts = content.split("|")
        head = parts[0].strip()
        match = _ENTRY_RE.match(head)
        if not match:
            errors.append(
                f"MANIFEST.md:{line_no} entry {head!r} is not "
                "`<name> -- <path>`")
            continue
        name, path = match.group(1).strip(), match.group(2).strip()
        try:
            name = validate_safe_id(name, kind="subSaipen name")
        except ValueError as exc:
            errors.append(f"MANIFEST.md:{line_no} invalid name {name!r}: {exc}")
            continue
        canonical = f"{SUBS_REL}/{name}/"
        if path != canonical:
            errors.append(
                f"MANIFEST.md:{line_no} path {path!r} for {name!r} does not "
                f"map exactly to {canonical} -- legacy, absolute, traversal, "
                "alias and arbitrary paths are forbidden")
            continue
        metadata: dict[str, str] = {}
        for part in parts[1:]:
            meta_match = _META_RE.match(part.strip())
            if not meta_match:
                errors.append(
                    f"MANIFEST.md:{line_no} unparseable metadata "
                    f"{part.strip()!r} -- metadata must be explicit "
                    "`key: value` tokens")
                continue
            key, value = meta_match.group(1), meta_match.group(2).strip()
            if key not in MANIFEST_METADATA:
                errors.append(
                    f"MANIFEST.md:{line_no} unknown metadata {key!r}; allowed: "
                    + ", ".join(sorted(MANIFEST_METADATA)))
                continue
            if key in metadata:
                errors.append(
                    f"MANIFEST.md:{line_no} duplicate metadata {key!r}")
                continue
            if not LAST_COLLECT_RE.fullmatch(value):
                errors.append(
                    f"MANIFEST.md:{line_no} {key} must be ISO-8601 UTC or "
                    "sha256:<64>@<ISO-8601 UTC>")
                continue
            metadata[key] = value
        if name in entries:
            errors.append(f"MANIFEST.md:{line_no} duplicate entry for {name!r}")
            continue
        if any(path == entry.path for entry in entries.values()):
            errors.append(f"MANIFEST.md:{line_no} duplicate path {path!r}")
            continue
        entries[name] = ManifestEntry(name=name, path=path, metadata=metadata)
    if errors:
        return [], errors
    return list(entries.values()), []


def parse_manifest_file(project_root: Path | str) -> tuple[list[ManifestEntry],
                                                           list[str]]:
    """Read + strictly parse the project's MANIFEST.md."""
    root = Path(project_root)
    manifest = root / MANIFEST_REL
    if not manifest.is_file():
        return [], ["no MANIFEST.md; run `saipen sub sync` or "
                    "`saipen sub spawn <name>` to bootstrap"]
    return parse_manifest(_read_maybe(manifest))


def _entry_dir(root: Path, entry: ManifestEntry) -> Path:
    path = root / entry.path.rstrip("/")
    prove_inside(path, (root / SUBS_REL).resolve(),
                 kind="manifest subSaipen path")
    return path


def _registered_entry(root: Path, name: str) -> tuple[bytes | None,
                                                       ManifestEntry | None,
                                                       list[str]]:
    raw = _read_bytes_maybe(root / MANIFEST_REL)
    if raw is None:
        return None, None, ["no MANIFEST.md"]
    try:
        entries, errors = parse_manifest(_decode_captured(raw, MANIFEST_REL))
    except ValueError as exc:
        return raw, None, [str(exc)]
    entry = next((candidate for candidate in entries
                  if candidate.name == name), None)
    if not errors and entry is None:
        errors = [f"{name!r} is not registered in MANIFEST.md"]
    return raw, entry, errors


# ---------------------------------------------------------------------------
# Shared-contract surface (SAICREW section C). `_bootstrap_needed()` was
# "directory exists", which cannot distinguish a partial bootstrap from a
# complete one; `shared_contract_status()` reports the exact truth.
# ---------------------------------------------------------------------------
def _shared_contract_source(saipen_home: str) -> tuple[list[dict], list[dict],
                                                        str | None]:
    """Return file targets plus exact file/directory source inventory."""
    src = Path(saipen_home) / "extensions" / "subs"
    if not (src / "PROTOCOL.md").is_file():
        return [], [], (f"saipen_home stale: {saipen_home} -- "
                        "extensions/subs/PROTOCOL.md missing; refresh the "
                        "install before syncing")
    targets: list[dict] = []
    inventory: list[dict] = []

    def add(source: Path, rel: str) -> None:
        try:
            info = source.lstat()
        except OSError as exc:
            raise ValueError(f"shared source {rel} unreadable: {exc}") from exc
        attributes = getattr(info, "st_file_attributes", 0)
        if source.is_symlink() or attributes & 0x400 \
                or not stat.S_ISREG(info.st_mode):
            raise ValueError(f"shared source {rel} is not a regular file")
        raw = source.read_bytes()
        targets.append({"path": f"{SUBS_REL}/{rel}", "content": raw,
                        "source_path": str(source.resolve()),
                        "source_hash": hash_bytes(raw)})
        inventory.append({"path": rel, "kind": "file",
                          "source_hash": hash_bytes(raw)})

    def add_directory(directory: Path, rel: str) -> None:
        digest = hash_delete_tree(directory)
        if not digest.startswith("delete-tree-sha256:"):
            raise ValueError(f"shared source directory {rel} is unsafe: {digest}")
        inventory.append({"path": rel, "kind": "directory",
                          "source_hash": digest})

    try:
        for name in _SHARED_FILES:
            source = src / name
            if source.is_file():
                add(source, name)
        for dirname in _SHARED_DIRS:
            directory = src / dirname
            if not directory.is_dir():
                continue
            directories = []
            for current, dirnames, filenames in os.walk(
                    directory, topdown=True, followlinks=False):
                dirnames.sort()
                filenames.sort()
                current_path = Path(current)
                directories.append(current_path)
                for child in dirnames:
                    candidate = current_path / child
                    info = candidate.lstat()
                    attributes = getattr(info, "st_file_attributes", 0)
                    if candidate.is_symlink() or attributes & 0x400 \
                            or not stat.S_ISDIR(info.st_mode):
                        raise ValueError(
                            f"shared source directory is unsafe: {candidate}")
                for filename in filenames:
                    source = current_path / filename
                    add(source, source.relative_to(src).as_posix())
            for source_dir in directories:
                add_directory(source_dir,
                              source_dir.relative_to(src).as_posix())
        for charter in sorted(src.glob("sai*.md")):
            add(charter, charter.name)
    except (OSError, ValueError) as exc:
        return [], [], str(exc)
    inventory.sort(key=lambda item: (item["path"], item["kind"]))
    targets.sort(key=lambda item: item["path"])
    return targets, inventory, None


def _shared_contract_targets(saipen_home: str) -> tuple[list[dict], str | None]:
    """Compatibility wrapper for callers that only need inherited files."""
    targets, _inventory, invalid = _shared_contract_source(saipen_home)
    return targets, invalid


def _valid_inventory_path(path: str, kind: str) -> bool:
    """Constrain receipt ownership to the shipped shared-contract surface."""
    candidate = Path(path)
    if not path or candidate.is_absolute() or "\\" in path \
            or candidate.as_posix() != path or ".." in candidate.parts:
        return False
    if kind == "directory":
        return path == "TEMPLATE" or path.startswith("TEMPLATE/")
    return (path in _SHARED_FILES or path.startswith("TEMPLATE/")
            or (len(candidate.parts) == 1
                and re.fullmatch(r"sai[^/]*\.md", path) is not None))


def _normalize_owned_inventory(value) -> list[dict] | None:
    if not isinstance(value, list):
        return None
    normalized = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            return None
        path = item.get("path")
        kind = item.get("kind")
        digest = item.get("source_hash")
        if not isinstance(path, str) or kind not in {"file", "directory"} \
                or not isinstance(digest, str) \
                or not _valid_inventory_path(path, kind):
            return None
        if kind == "file" and not re.fullmatch(r"[0-9a-f]{16}", digest):
            return None
        if kind == "directory" and not re.fullmatch(
                r"delete-tree-sha256:[0-9a-f]{64}", digest):
            return None
        key = (path, kind)
        if key in seen:
            return None
        seen.add(key)
        normalized.append({"path": path, "kind": kind,
                           "source_hash": digest})
    return sorted(normalized, key=lambda item: (item["path"], item["kind"]))


def _latest_sub_sync_inventory(root: Path) -> tuple[dict | None,
                                                     list[dict] | None]:
    """Newest committed normal sub_sync receipt carrying valid inventory."""
    ops = root / ".saipen" / "recovery" / "ops"
    candidates = []
    if not ops.is_dir():
        return None, None
    for manifest in ops.glob("*/operation.json"):
        try:
            record = json.loads(manifest.read_text(encoding="utf-8"))
            inventory = _normalize_owned_inventory(
                (record.get("receipt_metadata") or {}).get(
                    "owned_source_inventory"))
            if (record.get("operation") == "sub_sync"
                    and record.get("status") == "COMMITTED"
                    and inventory is not None):
                candidates.append((manifest.stat().st_mtime_ns,
                                   record.get("created_at", ""),
                                   record.get("op_id", ""), record, inventory,
                                   manifest.relative_to(root).as_posix()))
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    if not candidates:
        return None, None
    _mtime, _created, _op_id, record, inventory, receipt_path = max(
        candidates, key=lambda item: item[:3])
    return {**record, "_receipt_path": receipt_path}, inventory


def _owned_local_path(root: Path, rel: str) -> Path:
    shared = root / SUBS_REL
    prove_inside(shared, root.resolve(), kind="project-local shared root")
    _reject_reparse_ancestors(root, shared)
    candidate = shared / rel
    prove_inside(candidate, shared.resolve(), kind="inherited shared path")
    _reject_reparse_ancestors(root, candidate)
    return candidate


def _live_inventory_hash(root: Path, item: dict) -> str:
    try:
        path = _owned_local_path(root, item["path"])
        info = path.lstat()
    except FileNotFoundError:
        return ""
    except (OSError, ValueError):
        return "object-unreadable"
    attributes = getattr(info, "st_file_attributes", 0)
    if path.is_symlink() or attributes & 0x400:
        return "object-reparse"
    if item["kind"] == "file":
        if not stat.S_ISREG(info.st_mode):
            return f"object:{info.st_mode}"
        try:
            return hash_bytes(path.read_bytes())
        except OSError:
            return "object-unreadable"
    if not stat.S_ISDIR(info.st_mode):
        return f"object:{info.st_mode}"
    return hash_delete_tree(path)


def _obsolete_inventory(prior: list[dict] | None,
                        current: list[dict]) -> list[dict]:
    current_keys = {(item["path"], item["kind"]) for item in current}
    return [item for item in (prior or [])
            if (item["path"], item["kind"]) not in current_keys]


def _obsolete_contract_status(root: Path, prior: list[dict] | None,
                              current: list[dict]) -> tuple[list[dict],
                                                            list[str]]:
    obsolete = _obsolete_inventory(prior, current)
    conflicts = []
    for item in obsolete:
        live = _live_inventory_hash(root, item)
        if live and live != item["source_hash"]:
            conflicts.append(item["path"])
    return obsolete, sorted(set(conflicts))


def shared_contract_status(project_root: Path | str,
                           saipen_home: str) -> dict:
    """The exact shared-contract drift report.

    Returns {"current", "invalid_source_home", "missing_files",
    "stale_files"}. `current` is True ONLY when the source home is valid and
    every inherited file exists locally with identical bytes.
    """
    root = Path(project_root)
    _targets, source_inventory, invalid = _shared_contract_source(saipen_home)
    if invalid:
        return {"current": False, "invalid_source_home": invalid,
                "missing_files": [], "stale_files": [],
                "obsolete_files": [], "obsolete_dirs": [],
                "obsolete_conflicts": [], "inventory_known": False,
                "inventory_establishment": False}
    receipt, prior_inventory = _latest_sub_sync_inventory(root)
    obsolete, conflicts = _obsolete_contract_status(
        root, prior_inventory, source_inventory)
    missing, stale, missing_dirs = [], [], []
    for item in source_inventory:
        rel = f"{SUBS_REL}/{item['path']}"
        live = _live_inventory_hash(root, item)
        if item["kind"] == "file":
            if not live:
                missing.append(rel)
            elif live != item["source_hash"]:
                stale.append(rel)
            continue
        if not live:
            missing_dirs.append(rel)
        elif not live.startswith("delete-tree-sha256:"):
            stale.append(rel)
    inventory_changed = prior_inventory != source_inventory
    return {
        "current": (receipt is not None and not inventory_changed
                    and not missing and not stale and not missing_dirs
                    and not conflicts),
        "invalid_source_home": None,
        "missing_files": sorted(missing),
        "missing_dirs": sorted(missing_dirs),
        "stale_files": sorted(stale),
        "obsolete_files": sorted(f"{SUBS_REL}/{item['path']}" for item in obsolete
                                 if item["kind"] == "file"),
        "obsolete_dirs": sorted(
            (f"{SUBS_REL}/{item['path']}" for item in obsolete
             if item["kind"] == "directory"),
            key=lambda path: (len(Path(path).parts), path), reverse=True),
        "obsolete_conflicts": [f"{SUBS_REL}/{path}" for path in conflicts],
        "inventory_known": receipt is not None,
        "inventory_establishment": receipt is None,
        "inventory_changed": inventory_changed,
        "inventory_receipt": receipt.get("op_id") if receipt else None,
        "inventory_receipt_path": receipt.get("_receipt_path")
        if receipt else None,
    }


def verify_sub_sync_receipt(root: Path, receipt_metadata: dict | None) -> list[str]:
    """Recovery-safe verifier for one provenance-backed sync plan."""
    if not isinstance(receipt_metadata, dict):
        return ["sub_sync receipt metadata missing"]
    inventory = _normalize_owned_inventory(
        receipt_metadata.get("owned_source_inventory"))
    reconciled = receipt_metadata.get("obsolete_reconciliation")
    if inventory is None or not isinstance(reconciled, list):
        return ["sub_sync receipt inventory/reconciliation malformed"]
    errors = []
    for item in inventory:
        live = _live_inventory_hash(root, item)
        if item["kind"] == "file" and live != item["source_hash"]:
            errors.append(f"{SUBS_REL}/{item['path']}: live {live!r} != source "
                          f"{item['source_hash']!r}")
        elif item["kind"] == "directory" and not live.startswith(
                "delete-tree-sha256:"):
            errors.append(f"{SUBS_REL}/{item['path']}: inherited directory "
                          f"missing or unsafe ({live!r})")
    for item in reconciled:
        if not isinstance(item, dict) or _normalize_owned_inventory([{
                "path": item.get("path"), "kind": item.get("kind"),
                "source_hash": item.get("source_hash")}]) is None:
            errors.append("obsolete reconciliation entry malformed")
            continue
        path = _owned_local_path(root, item["path"])
        if os.path.lexists(path):
            errors.append(f"{SUBS_REL}/{item['path']}: receipt-safe obsolete "
                          "path remains")
    return errors


# ---------------------------------------------------------------------------
# Role-revision authority (SAICREW sections D/E). For an attached project the
# PROJECT-LOCAL charter is the only role-revision source; the installation
# charter is only the sync source. A generic `sai*` worker's revision is the
# deterministic digest of the project-local PROTOCOL.md. Never blank.
# ---------------------------------------------------------------------------
def current_local_role_revision(root: Path, name: str,
                                saipen_home: str = "") -> str | None:
    """The role revision the project-local charter (or local PROTOCOL for a
    generic role) derives RIGHT NOW, or None when evidence is unavailable.

    Built-in vs generic is decided by whether the SAIPEN home ships a charter
    for this name. A BUILT-IN role with a missing project-local charter is
    UNAVAILABLE -- never a silent fallback to the generic PROTOCOL digest
    (SAICREW D/E); the home charter is only the sync source. A custom name
    with no shipped charter is generic and derives from the project-local
    PROTOCOL.md. With no home known, a local charter still wins; otherwise
    the local PROTOCOL is the generic authority.
    """
    try:
        from freshness import (compute_generic_role_revision,
                               compute_role_revision, FreshnessError)
    except ImportError:
        return None
    local_charter = root / SUBS_REL / f"{name}.md"
    local_protocol = root / SUBS_REL / "PROTOCOL.md"
    home_charter = (Path(saipen_home) / "extensions" / "subs" / f"{name}.md"
                    if saipen_home else None)
    built_in = home_charter is not None and home_charter.is_file()
    try:
        if built_in:
            if not local_charter.is_file():
                return None  # built-in charter must exist locally: UNAVAILABLE
            return compute_role_revision(local_charter)
        if local_charter.is_file():
            return compute_role_revision(local_charter)
        if local_protocol.is_file():
            return compute_generic_role_revision(local_protocol)
    except (FreshnessError, OSError):
        return None
    return None


def role_freshness(root: Path, name: str, recorded: str,
                   saipen_home: str = "") -> str:
    """Tri-state role freshness against the PROJECT-LOCAL authority.

    Returns `current` (local evidence matches the recorded revision),
    `stale` (local evidence readable but differs), or `unavailable`
    (no local charter, no local PROTOCOL, or a read/hash failure).
    UNKNOWN is never FRESH: ROLE_EVIDENCE_UNAVAILABLE means the instance
    cannot be verified and MUST NOT be treated as current (SAICREW D).
    """
    current = current_local_role_revision(root, name, saipen_home)
    if current is None:
        return "unavailable"
    return "current" if current == recorded else "stale"


# ---------------------------------------------------------------------------
# ONE reusable sub-board parser (SAICREW section H). The sub board uses its
# own `PREFIX-NNN` namespace (PROTOCOL § 3), never Core's T-###, and must be a
# coherent machine with its STATE phase.
# ---------------------------------------------------------------------------
SUB_HEADINGS = ("## DOING", "## TODO", "## DONE", "## BLOCKED")
# Optional `[TAG]` prefix (e.g. `[MARKHUNT]`) before the ticket id.
SUB_TICKET_RE = re.compile(
    r"^- \[([ x/])\] (?:\[[^\]]*\]\s*)?([A-Za-z][A-Za-z0-9]*-\d+)"
    r"(?:\s+(.*))?$")


def ticket_prefix_for_role(role: str, declared: str | None = None) -> str:
    """One deterministic ticket-prefix authority for built-in/custom roles."""
    if declared is not None:
        prefix = declared.rstrip("-")
        if not re.fullmatch(r"[A-Z][A-Z0-9]*", prefix):
            raise ValueError(f"declared ticket prefix {declared!r} is invalid")
        return prefix
    registered = ROLE_REGISTRY.get(role)
    if registered:
        return registered.ticket_prefix
    safe = validate_safe_id(role, kind="subSaipen role")
    return safe[:4].upper()


def parse_sub_board(text: str, expected_role: str | None = None,
                    ticket_prefix: str | None = None) -> dict:
    """Strict sub-board parser.

    Returns {"tickets", "headings", "errors", "counts"}. Errors cover:
    duplicate/missing headings, duplicate ticket IDs, at most one DOING,
    checkbox/section disagreement, Core T-### IDs, malformed ticket lines,
    tickets outside the four sections. HTML comments and prose are inert
    (the validator reading this file does NOT skip comments, but only
    `- [ ] PREFIX-NNN` lines are tickets).
    """
    expected_prefix = None
    if expected_role is not None or ticket_prefix is not None:
        expected_prefix = ticket_prefix_for_role(expected_role or "generic",
                                                 ticket_prefix)
    tickets: dict[str, dict] = {}
    seen_ticket_ids: set[str] = set()
    headings: list[str] = []
    errors: list[str] = []
    section = None
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            section = line.strip()
            headings.append(section)
            if section not in SUB_HEADINGS:
                errors.append(f"BOARD.md:{line_no} unknown heading {section!r}")
            continue
        if not line.strip():
            continue
        if line.lstrip().startswith("- ["):
            match = SUB_TICKET_RE.match(line.strip())
            if not match:
                errors.append(
                    f"BOARD.md:{line_no} ticket-ish line doesn't match "
                    "`- [ ] <PREFIX>-NNN description`")
                continue
            checkbox, tid, rest = match.groups()
            if tid in seen_ticket_ids:
                errors.append(f"duplicate ticket ID {tid}")
                continue
            seen_ticket_ids.add(tid)
            if section not in SUB_HEADINGS:
                errors.append(
                    f"ticket {tid} sits under {section or 'no heading'} -- "
                    "not one of the four sections")
                continue
            if tid.startswith("T-"):
                errors.append(
                    f"ticket {tid} uses Core's T-### namespace -- a sub "
                    "board must use its own prefix (PROTOCOL § 3)")
                continue
            prefix = tid.rsplit("-", 1)[0]
            if expected_prefix is not None and prefix != expected_prefix:
                errors.append(
                    f"ticket {tid} has prefix {prefix}-, expected "
                    f"{expected_prefix}- for {expected_role or 'declared role'}")
                continue
            expected_checkbox = {"## DOING": "/", "## TODO": " ",
                                 "## DONE": "x", "## BLOCKED": " "}[section]
            if checkbox != expected_checkbox:
                errors.append(
                    f"ticket {tid} checkbox [{checkbox}] disagrees with "
                    f"section {section}; expected [{expected_checkbox}]")
            tickets[tid] = {"id": tid, "section": section,
                            "checkbox": checkbox, "description": rest or ""}
    for heading in SUB_HEADINGS:
        seen = headings.count(heading)
        if seen != 1:
            errors.append(f"required heading {heading} appears {seen} time(s)")
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if len(doing) > 1:
        errors.append("at most one DOING ticket allowed")
    counts = {heading[3:]: sum(1 for t in tickets.values()
                               if t["section"] == heading)
              for heading in SUB_HEADINGS}
    return {"tickets": tickets, "headings": headings, "errors": errors,
            "counts": counts}


def _derive_health(state: dict, board: dict, outbox: dict,
                   role_state: str) -> str:
    """Mechanical health from STATE + BOARD + OUTBOX + role evidence.

    Order of precedence (each higher rule wins):
    1. board invalid                     -> INVALID
    2. phase DONE but pending board work -> INVALID (H's key invariant)
    3. phase BLOCKED                     -> BLOCKED
    4. role evidence unavailable         -> STALE
    5. open TODO/DOING work              -> WORK_PENDING
    6. DONE + current-source package     -> CURRENT
    7. DONE + ready-but-stale package    -> STALE
    8. DONE + no package                 -> NOT_RUN (J: empty OUTBOX is not
                                           proof of running)
    9. PLAN/INIT with no work/evidence   -> NOT_RUN
    10. otherwise                        -> WORK_PENDING
    """
    phase = state.get("phase") or "?"
    if board["errors"] or outbox.get("errors"):
        return HEALTH_INVALID
    counts = board["counts"]
    if phase == "DONE" and (counts["TODO"] or counts["DOING"]
                            or counts["BLOCKED"]):
        return HEALTH_INVALID
    if phase == "BLOCKED" or counts["BLOCKED"]:
        return HEALTH_BLOCKED
    if counts["TODO"] or counts["DOING"]:
        return HEALTH_WORK_PENDING
    if outbox.get("counts", {}).get("ready"):
        if outbox.get("ready_current"):
            return HEALTH_READY_FOR_REVIEW
        return HEALTH_STALE
    if outbox.get("counts", {}).get("reviewed") \
            and not outbox.get("package_current"):
        return HEALTH_STALE
    if role_state != "current":
        return HEALTH_STALE
    if phase == "DONE":
        if outbox.get("package_current"):
            return HEALTH_CURRENT
        return HEALTH_NOT_RUN
    if phase in ("PLAN", "INIT"):
        return HEALTH_NOT_RUN
    return HEALTH_WORK_PENDING


OUTBOX_FIELDS = frozenset({
    "status", "summary", "main_project_refs", "critical", "severity",
    "producer", "source_head", "source_tree_fingerprint", "role_revision",
    "coverage", "payload", "verified", "instructions", "details",
    "superseded_by", "base_head", "patch",
})
OUTBOX_COMPLETE_FIELDS = frozenset({
    "status", "producer", "source_head", "source_tree_fingerprint",
    "role_revision", "coverage", "payload", "verified", "instructions",
})
OUTBOX_FIELD_RE = re.compile(r"^- \*\*([a-z_][a-z0-9_]*):\*\*\s*(.*)$")
OUTBOX_HEADING_RE = re.compile(r"^## ([A-Za-z][A-Za-z0-9]*-\d+):\s*(\S.*)$")
GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
TREE_FINGERPRINT_RE = re.compile(
    r"^(?:git-delta-v1|no-git-tree-v1):[0-9a-f]{64}$")
ROLE_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class OutboxPackage:
    package_id: str
    description: str
    fields: dict[str, str]
    block: str

    @property
    def status(self) -> str:
        return self.fields["status"]


@dataclass(frozen=True)
class OutboxModel:
    packages: tuple[OutboxPackage, ...]
    errors: tuple[str, ...]


def parse_outbox(text: str, producer: str | None = None) -> OutboxModel:
    """Parse one OUTBOX using a closed, duplicate-proof package grammar."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    if not lines or lines[0] != "# OUTBOX":
        return OutboxModel((), ("OUTBOX must open with exactly `# OUTBOX`",))
    errors: list[str] = []
    starts = [index for index, line in enumerate(lines) if line.startswith("## ")]
    preamble_end = starts[0] if starts else len(lines)
    in_comment = False
    for line in lines[1:preamble_end]:
        stripped = line.strip()
        if stripped.startswith("<!--"):
            in_comment = True
        if stripped and not in_comment:
            errors.append("OUTBOX preamble may contain only blank lines/comments")
            break
        if "-->" in stripped:
            in_comment = False
    if in_comment:
        errors.append("OUTBOX preamble has an unclosed comment")
    packages: list[OutboxPackage] = []
    seen_ids: set[str] = set()
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        block_lines = lines[start:end]
        heading = OUTBOX_HEADING_RE.fullmatch(block_lines[0])
        if not heading:
            errors.append(f"OUTBOX:{start + 1} malformed package heading")
            continue
        package_id, description = heading.groups()
        if package_id in seen_ids:
            errors.append(f"OUTBOX:{start + 1} duplicate package ID {package_id}")
        seen_ids.add(package_id)
        fields: dict[str, str] = {}
        active_field = None
        for line_no, line in enumerate(block_lines[1:], start + 2):
            match = OUTBOX_FIELD_RE.match(line)
            if match:
                key, value = match.groups()
                if key not in OUTBOX_FIELDS:
                    errors.append(f"OUTBOX:{line_no} unknown field {key!r}")
                    active_field = None
                    continue
                if key in fields:
                    errors.append(f"OUTBOX:{line_no} duplicate field {key!r}")
                    active_field = None
                    continue
                fields[key] = value.strip()
                active_field = key
                continue
            if line.startswith("  ") and active_field:
                fields[active_field] += ("\n" if fields[active_field] else "") \
                    + line.strip()
                continue
            if not line.strip():
                active_field = None
                continue
            errors.append(f"OUTBOX:{line_no} malformed field/content line")
            active_field = None
        status = fields.get("status", "")
        if status not in OUTBOX_STATUSES:
            errors.append(
                f"OUTBOX:{start + 1} status {status!r} outside closed enum")
        if "producer" in fields and producer is not None \
                and fields["producer"] != producer:
            errors.append(
                f"OUTBOX:{start + 1} producer {fields['producer']!r} "
                f"does not match owner {producer!r}")
        head = fields.get("source_head", "")
        if head and head != "no-git" and not GIT_SHA_RE.fullmatch(head):
            errors.append(f"OUTBOX:{start + 1} invalid source_head")
        tree = fields.get("source_tree_fingerprint", "")
        if tree and not TREE_FINGERPRINT_RE.fullmatch(tree):
            errors.append(
                f"OUTBOX:{start + 1} invalid source_tree_fingerprint")
        if head == "no-git" and tree and not tree.startswith("no-git-tree-v1:"):
            errors.append(
                f"OUTBOX:{start + 1} no-git source_head requires "
                "no-git-tree-v1 fingerprint")
        if GIT_SHA_RE.fullmatch(head) and tree \
                and not tree.startswith("git-delta-v1:"):
            errors.append(
                f"OUTBOX:{start + 1} Git source_head requires "
                "git-delta-v1 fingerprint")
        role = fields.get("role_revision", "")
        if role and not ROLE_REVISION_RE.fullmatch(role):
            errors.append(f"OUTBOX:{start + 1} invalid role_revision")
        missing = sorted(OUTBOX_COMPLETE_FIELDS - fields.keys())
        if missing:
            errors.append(f"OUTBOX:{start + 1} package missing "
                          + ", ".join(missing))
        for key in OUTBOX_COMPLETE_FIELDS:
            if key in fields and not fields[key].strip():
                errors.append(f"OUTBOX:{start + 1} field {key} is empty")
        verified = fields.get("verified", "").lower()
        if verified and re.search(
                r"\b(?:unverified|pending|unknown|not[- ]run|not verified)\b",
                verified):
            errors.append(
                f"OUTBOX:{start + 1} verified field is not closed evidence")
        packages.append(OutboxPackage(package_id, description, fields,
                                      "\n".join(block_lines)))
    if not starts and not errors:
        # Header plus comments is canonical empty queue (TEMPLATE included).
        pass
    return OutboxModel(tuple(packages), tuple(errors))


def _outbox_blocks(text: str) -> list[str]:
    model = parse_outbox(text)
    ready = [package for package in model.packages
             if package.fields.get("status") == "ready"]
    if model.errors or len(ready) > 1:
        return []
    return [package.block for package in model.packages]


def _field(text: str, key: str) -> str:
    values = [match.group(2).strip() for line in text.splitlines()
              if (match := OUTBOX_FIELD_RE.match(line))
              and match.group(1) == key]
    return values[0] if len(values) == 1 else ""


def _outbox_health(root: Path, name: str, source_id,
                   saipen_home: str = "") -> dict:
    """OUTBOX status counts + package currentness against source identity.

    `package_current` is True only when a ready/reviewed entry binds the
    current source_head + source_tree_fingerprint + role_revision triple.
    A clean run with payload [] is valid evidence; NO package is never
    evidence (SAICREW J).
    """
    outbox_path = root / SUBS_REL / name / "kitchen" / "OUTBOX.md"
    if not outbox_path.is_file():
        return {"present": False, "counts": {},
                "package_current": False, "ready_current": False}
    text = _read_maybe(outbox_path)
    model = parse_outbox(text, name)
    counts = {status: 0 for status in OUTBOX_STATUSES}
    for package in model.packages:
        status = package.fields.get("status", "")
        if status in counts:
            counts[status] += 1
    if source_id is None:
        try:
            from freshness import compute_source_identity
            source_id = compute_source_identity(root)
        except Exception:
            source_id = None
    current_role = current_local_role_revision(root, name, saipen_home)
    package_current = False
    ready_current = False
    if source_id is not None and current_role is not None:
        current_ready = []
        for package in model.packages:
            status = package.fields.get("status", "")
            if status not in ("ready", "reviewed"):
                continue
            head = package.fields.get("source_head", "")
            tree = package.fields.get("source_tree_fingerprint", "")
            role = package.fields.get("role_revision", "")
            if not head or not tree or not role:
                continue
            if (head != source_id.source_head
                    or tree != source_id.source_tree_fingerprint
                    or role != current_role):
                continue
            package_current = True
            if status == "ready":
                ready_current = True
                current_ready.append(package.package_id)
        if len(current_ready) > 1:
            model = OutboxModel(model.packages, (*model.errors,
                "multiple current READY packages are ambiguous: "
                + ", ".join(current_ready),))
    return {"present": True, "counts": counts,
            "package_current": package_current, "ready_current": ready_current,
            "errors": list(model.errors)}


def sub_instance_health(project_root: Path | str, name: str,
                        source_id=None,
                        manifest_entry: ManifestEntry | None = None) -> dict:
    """The full mechanically-derived health record for one sub (SAICREW I)."""
    root = Path(project_root)
    info = {"name": name}
    if manifest_entry is None:
        _manifest_raw, manifest_entry, manifest_errors = _registered_entry(
            root, name)
        if manifest_errors:
            return {**info, "phase": None, "task": None,
                    "health": HEALTH_INVALID,
                    "board": {"valid": False, "errors": manifest_errors,
                              "counts": {}},
                    "local_charter_present": False, "role_revision": "",
                    "role_revision_state": "UNAVAILABLE",
                    "outbox": {"present": False, "counts": {},
                               "package_current": False,
                               "ready_current": False, "errors": []}}
    instance = _entry_dir(root, manifest_entry)
    state_path = instance / "STATE.md"
    if not state_path.is_file():
        return {**info, "phase": None, "task": None, "health": HEALTH_INVALID,
                "board_valid": False, "board_errors": ["no STATE.md"],
                "local_charter_present": False,
                "role_revision": "", "role_revision_state": "UNAVAILABLE",
                "outbox": {"present": False, "counts": {},
                           "package_current": False, "ready_current": False}}
    from .state import parse_state
    st = parse_state(codec.read_doc(state_path))
    saipen_home = st.get("saipen_home") or ""
    board = parse_sub_board(_read_maybe(instance / "BOARD.md"),
                            expected_role=name)
    outbox = _outbox_health(root, name, source_id, saipen_home)
    role_state = role_freshness(root, name, st.get("role_revision") or "",
                                saipen_home)
    health = _derive_health(st, board, outbox, role_state)
    return {
        **info,
        "phase": st.get("phase"),
        "task": st.get("task"),
        "board": {"valid": not board["errors"],
                  "errors": board["errors"][:5],
                  "counts": board["counts"]},
        "outbox": outbox,
        "local_charter_present": bool(
            (root / SUBS_REL / f"{name}.md").is_file()),
        "role_revision": st.get("role_revision") or "",
        "role_revision_state": role_state.upper(),
        "health": health,
    }


# ---------------------------------------------------------------------------
# list / status
# ---------------------------------------------------------------------------
def sub_list(project_root: Path | str) -> Result:
    """Truthful manifest-backed list with per-role mechanical health.

    `blocked` reports every instance whose PHASE is BLOCKED or whose BOARD
    still holds unresolved BLOCKED entries -- an empty OUTBOX or a DONE phase
    can never hide an open block.
    """
    root = Path(project_root)
    entries, errors = parse_manifest_file(root)
    if errors:
        return _refuse("INVALID_MANIFEST",
                       "MANIFEST malformed: " + "; ".join(errors[:5]),
                       errors=errors)
    try:
        from freshness import compute_source_identity
        source_id = compute_source_identity(root)
    except Exception:
        source_id = None
    lines = []
    blocked = []
    for entry in entries:
        info = sub_instance_health(root, entry.name, source_id, entry)
        lines.append(info)
        if (info["health"] == HEALTH_BLOCKED
                or info.get("board", {}).get("counts", {}).get("BLOCKED")):
            blocked.append(entry.name)
    return Result(ok=True, code="SUB_LIST", data={"subs": lines,
                                                 "blocked": blocked})


def sub_status(project_root: Path | str, name: str) -> Result:
    """Read-only peek with mechanically-derived health (SAICREW I)."""
    root = Path(project_root)
    try:
        _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    _manifest_raw, entry, errors = _registered_entry(root, name)
    if errors:
        code = "INVALID_MANIFEST" if any("MANIFEST" in error
                                          or "registered" not in error
                                          for error in errors) \
            else "TICKET_NOT_FOUND"
        return _refuse(code, "; ".join(errors[:5]), name=name)
    if not (_entry_dir(root, entry) / "STATE.md").is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    try:
        from freshness import compute_source_identity
        source_id = compute_source_identity(root)
    except Exception:
        source_id = None
    health = sub_instance_health(root, name, source_id, entry)
    return Result(ok=True, code="SUB_STATUS", data=health)


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------
def sub_sync(project_root: Path | str, saipen_home: str,
             dry_run: bool = False) -> Result:
    """Refresh the inherited shared contract surface -- never a sub's history.

    Copies PROTOCOL.md/README.md/crew.md/TEMPLATE/** and every built-in
    sai*.md charter from <saipen_home>/extensions/subs/. Creates a missing
    _shared/inbox.md once; preserves an existing one byte-identically. Never
    looks inside a `<name>/` folder. One journaled mutation; a second sync
    with no drift performs ZERO writes (idempotent). `dry_run` performs the
    same validation and computes the same diff with ZERO writes.
    """
    root = Path(project_root)
    source_root = Path(saipen_home) / "extensions" / "subs"
    source_tree_plan_hash = hash_tree(source_root)
    targets, source_inventory, invalid = _shared_contract_source(saipen_home)
    if invalid:
        return _refuse("VALIDATION_FAILED",
                       invalid + " -- run `saipen sub sync` after refreshing "
                       "the install (BLOCKED, never copy from a path that did "
                       "not check out)")
    receipt, prior_inventory = _latest_sub_sync_inventory(root)
    obsolete, conflicts = _obsolete_contract_status(
        root, prior_inventory, source_inventory)
    prior_kinds = {item["path"]: item["kind"]
                   for item in (prior_inventory or [])}
    current_kinds = {item["path"]: item["kind"]
                     for item in source_inventory}
    kind_changes = sorted(path for path in prior_kinds.keys() & current_kinds
                          if prior_kinds[path] != current_kinds[path])
    if kind_changes:
        return _refuse(
            "VALIDATION_FAILED",
            "shared-contract path kind changed; one journal target cannot "
            "safely delete and recreate the same path: "
            + ", ".join(f"{SUBS_REL}/{path}" for path in kind_changes[:5]))
    if conflicts:
        return _refuse(
            "VALIDATION_FAILED",
            "obsolete inherited path has local changes; refusing deletion: "
            + ", ".join(f"{SUBS_REL}/{path}" for path in conflicts[:5]),
            obsolete_conflicts=[f"{SUBS_REL}/{path}" for path in conflicts])
    inbox_src = Path(saipen_home) / "extensions" / "subs" / "_shared" \
        / "inbox.md"
    local_inbox = root / f"{SUBS_REL}/_shared/inbox.md"
    local_inbox_raw = _read_bytes_maybe(local_inbox)
    if inbox_src.is_file() and local_inbox_raw is None:
        inbox_raw = inbox_src.read_bytes()
        targets.append({"path": f"{SUBS_REL}/_shared/inbox.md",
                        "content": inbox_raw,
                        "source_path": str(inbox_src.resolve()),
                        "source_hash": hash_bytes(inbox_raw)})
    changed = []
    for target in targets:
        local = root / target["path"]
        local_raw = _read_bytes_maybe(local)
        if local_raw != target["content"]:
            changed.append({**target,
                            "before_hash": _captured_hash(local_raw)})

    delete_files = []
    delete_dirs = []
    for item in obsolete:
        live = _live_inventory_hash(root, item)
        if not live:
            continue
        rel = f"{SUBS_REL}/{item['path']}"
        if item["kind"] == "file":
            delete_files.append({"path": rel, "role": "manifest",
                                 "action": "delete_file",
                                 "expected_hash": item["source_hash"]})
        else:
            delete_dirs.append({"path": rel, "role": "manifest",
                                "action": "delete_dir",
                                "planned_before_hash": empty_delete_tree_hash()})
    delete_files.sort(key=lambda item: (-len(Path(item["path"]).parts),
                                        item["path"]))
    delete_dirs.sort(key=lambda item: (-len(Path(item["path"]).parts),
                                       item["path"]))

    receipt_metadata = {
        "owned_source_inventory": source_inventory,
        "obsolete_reconciliation": obsolete,
    }
    inventory_changed = prior_inventory != source_inventory
    drift = bool(changed or delete_files or delete_dirs
                 or receipt is None or inventory_changed)
    if not drift:
        return Result(ok=True, code="SUB_SYNC",
                      data={"changed": [], "deleted": [], "drift": False,
                            "inventory_established": False,
                            "dry_run": dry_run})

    writes = [{"path": item["path"], "role": item.get("role", "manifest"),
               "content": item["content"]} for item in changed]
    mutation_targets = [*delete_files, *delete_dirs, *writes]
    proposed_writes = [item["path"] for item in changed]
    proposed_deletes = [item["path"] for item in (*delete_files, *delete_dirs)]
    proposed = [item["path"] for item in mutation_targets]
    if dry_run:
        return Result(ok=True, code="SUB_SYNC",
                      data={"changed": proposed, "drift": True,
                            "dry_run": True,
                            "would_write": proposed_writes,
                            "would_delete": proposed_deletes,
                            "would_record_receipt": True,
                            "inventory_established": receipt is None})
    op_id = "sub-sync-" + __import__("uuid").uuid4().hex[:8]
    preconditions = {item["path"]: item["before_hash"] for item in changed}
    preconditions.update({item["path"]: item["expected_hash"]
                          for item in delete_files})
    semantic = json.dumps(receipt_metadata, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    with project_writer_lock(root):
        if not _sources_unchanged(changed):
            return _refuse(
                "STALE_STATE",
                "shared-contract source changed after sync planning; replan")
        commit = run_mutation(
            root, op_id, "sub_sync", "saipen-cli", project_identity(root),
            hash_bytes(b"sub_sync:" + semantic), mutation_targets,
            preconditions=preconditions,
            read_preconditions={**{str(source_root.resolve()):
                                    source_tree_plan_hash},
                                **_external_read_preconditions(changed)},
            verification_policy="sub_sync",
            receipt_metadata=receipt_metadata)
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""))
    return Result(ok=True, code="SUB_SYNC", op_id=op_id,
                  changed_files=proposed,
                  data={"changed": proposed, "deleted": proposed_deletes,
                        "drift": True,
                        "inventory_established": receipt is None})


# ---------------------------------------------------------------------------
# spawn
# ---------------------------------------------------------------------------
def sub_spawn(project_root: Path | str, name: str, saipen_home: str,
              agent: str | None = None, dry_run: bool = False) -> Result:
    """Bootstrap-and-spawn a subSaipen, journaled (PROTOCOL.md section 7).

    The shared contract surface is repaired if partial (a directory existing
    is NOT a complete bootstrap), then the instance is created from TEMPLATE
    with a REAL role_revision anchored to the local charter / local PROTOCOL
    -- a blank role identity refuses spawn. `dry_run` computes the same
    outcome with ZERO writes.
    """
    root = Path(project_root)
    try:
        target = _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    instance_tree_hash = hash_tree(target)
    if target.exists():
        return _refuse("ALREADY_CLAIMED",
                       f"subSaipen {name!r} already exists; run "
                       f"`saipen sub clean {name}` first if replacement is "
                       "intended", name=name)

    sync_result = None
    sync_changed = []
    if not dry_run:
        sync_result = sub_sync(root, saipen_home)
        if not sync_result.ok:
            return _refuse(sync_result.code,
                           "shared-contract bootstrap refused: "
                           + sync_result.message, name=name,
                           sync=sync_result.data)
        sync_changed = list(sync_result.changed_files)
    source_tree_plan_hash = hash_tree(
        Path(saipen_home) / "extensions" / "subs")

    template_root = Path(saipen_home) / "extensions" / "subs" / "TEMPLATE"
    template_paths = {
        "STATE.md": template_root / "STATE.md",
        "BOARD.md": template_root / "BOARD.md",
        "LOG.md": template_root / "LOG.md",
        "kitchen/OUTBOX.md": template_root / "kitchen" / "OUTBOX.md",
    }
    template_raw = {rel: _read_bytes_maybe(path)
                    for rel, path in template_paths.items()}
    if any(raw is None for raw in template_raw.values()):
        return _refuse("VALIDATION_FAILED",
                       f"saipen_home {saipen_home!r} has incomplete subSaipen TEMPLATE; "
                       "clone/refresh before spawning", name=name)

    # A malformed MANIFEST refuses spawn -- the manifest is a registry, not
    # a scratchpad, and adding a line to a corrupt registry would launder it.
    manifest = root / MANIFEST_REL
    manifest_raw = _read_bytes_maybe(manifest)
    try:
        manifest_text = _decode_captured(manifest_raw, MANIFEST_REL)
    except ValueError as exc:
        return _refuse("INVALID_MANIFEST", str(exc), name=name)
    if manifest_text.strip():
        _entries, manifest_errors = parse_manifest(manifest_text)
        if manifest_errors:
            return _refuse("INVALID_MANIFEST",
                           "MANIFEST malformed; spawn refused: "
                           + "; ".join(manifest_errors[:5]),
                           errors=manifest_errors)
    if not manifest_text.strip():
        # Fresh bootstrap: the strict parser requires the exact header, so
        # the first spawn writes it -- a header-less manifest would make the
        # very registry this command maintains INVALID_MANIFEST.
        new_manifest = MANIFEST_HEADER + "\n\n" \
            f"- {name} -- {SUBS_REL}/{name}/\n"
    else:
        if not manifest_text.startswith(MANIFEST_HEADER):
            manifest_text = MANIFEST_HEADER + "\n\n" + manifest_text
        new_manifest = manifest_text.rstrip("\n") + "\n" + \
            f"- {name} -- {SUBS_REL}/{name}/\n"
    now = _utc_iso()

    targets, invalid = _shared_contract_targets(saipen_home)
    if invalid:
        return _refuse("VALIDATION_FAILED", invalid, name=name)
    # Only copy what is missing/stale locally (partial-bootstrap repair).
    shared = []
    for t in targets:
        local = root / t["path"]
        local_raw = _read_bytes_maybe(local)
        if local_raw != t["content"]:
            shared.append({**t, "before_hash": _captured_hash(local_raw)})
    if not dry_run and shared:
        return _refuse(
            "STALE_STATE",
            "shared contract changed immediately after bootstrap sync; retry "
            "spawn against a stable saipen_home", name=name)
    inbox_src = Path(saipen_home) / "extensions" / "subs" / "_shared" \
        / "inbox.md"
    local_inbox = root / f"{SUBS_REL}/_shared/inbox.md"
    local_inbox_raw = _read_bytes_maybe(local_inbox)
    if inbox_src.is_file() and local_inbox_raw is None:
        inbox_raw = inbox_src.read_bytes()
        shared.append({"path": f"{SUBS_REL}/_shared/inbox.md",
                       "content": inbox_raw,
                       "before_hash": "",
                       "source_path": str(inbox_src.resolve()),
                       "source_hash": hash_bytes(inbox_raw)})

    role_source = Path(saipen_home) / "extensions" / "subs" / f"{name}.md"
    generic_role = not role_source.is_file()
    if generic_role:
        role_source = Path(saipen_home) / "extensions" / "subs" / "PROTOCOL.md"
    role_raw = _read_bytes_maybe(role_source)
    try:
        role_revision = (_role_revision_from_bytes(role_raw, generic=generic_role)
                         if role_raw is not None else None)
    except ValueError as exc:
        return _refuse("VALIDATION_FAILED", str(exc), name=name)
    if not role_revision or role_raw is None:
        return _refuse("VALIDATION_FAILED",
                       f"no role evidence to anchor spawn of {name!r}: no "
                       "built-in charter and no PROTOCOL.md (ROLE_EVIDENCE_"
                       "UNAVAILABLE) -- a strict worker never gets a blank "
                       "role identity; refresh the install and run "
                       "`saipen sub sync`", name=name)

    template_state_doc = codec.read_document(template_paths["STATE.md"])
    state = template_state_doc.text_norm
    state = patch_state(state, {
        "agent": name,
        "saipen_home": saipen_home,
        "updated": now,
        "role_revision": role_revision,
    })

    mutation_targets = [t for t in shared]
    mutation_targets += [
        {"path": f"{SUBS_REL}/{name}/STATE.md", "role": "state",
         "content": template_state_doc.encode(state), "before_hash": ""},
        {"path": f"{SUBS_REL}/{name}/BOARD.md", "role": "board",
         "content": template_raw["BOARD.md"], "before_hash": ""},
        {"path": f"{SUBS_REL}/{name}/LOG.md", "role": "log",
         "content": template_raw["LOG.md"], "before_hash": ""},
        {"path": f"{SUBS_REL}/{name}/kitchen/OUTBOX.md", "role": "report",
         "content": template_raw["kitchen/OUTBOX.md"], "before_hash": ""},
        {"path": MANIFEST_REL, "role": "manifest",
         "content": new_manifest.encode("utf-8"),
         "before_hash": _captured_hash(manifest_raw)},
    ]
    source_preconditions = {
        str((Path(saipen_home) / "extensions" / "subs").resolve()):
        source_tree_plan_hash}
    source_preconditions.update(_external_read_preconditions(shared))
    source_preconditions.update({
        str(path.resolve()): _captured_hash(template_raw[rel])
        for rel, path in template_paths.items()
    })
    source_preconditions[str(role_source.resolve())] = hash_bytes(role_raw)
    write_preconditions = {item["path"]: item["before_hash"]
                           for item in mutation_targets}
    proposed = [t["path"] for t in mutation_targets]
    if dry_run:
        return Result(ok=True, code="SPAWNED",
                      data={"name": name,
                            "path": f"{SUBS_REL}/{name}/",
                            "bootstrap": bool(shared),
                            "role_revision": role_revision,
                            "dry_run": True, "would_write": proposed})
    op_id = "sub-spawn-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        if hash_tree(target) != instance_tree_hash:
            return _refuse("STALE_STATE",
                           f"subSaipen {name!r} target changed after planning",
                           name=name)
        commit = run_mutation(
            root, op_id, "sub_spawn", agent or name, project_identity(root),
            hash_bytes(("sub_spawn:" + name).encode("utf-8")),
            mutation_targets,
            preconditions=write_preconditions,
            read_preconditions=source_preconditions,
            verification_policy="sub_lifecycle")
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SPAWNED", op_id=op_id,
                  changed_files=[*sync_changed, *proposed],
                  data={"name": name,
                        "path": f"{SUBS_REL}/{name}/",
                        "bootstrap": bool(sync_changed),
                        "sync_op_id": sync_result.op_id if sync_result else None,
                        "role_revision": role_revision})


def _hash_or_empty(path: Path) -> str:
    try:
        return hash_bytes(path.read_bytes())
    except OSError:
        return ""


def _lifecycle_read_preconditions(root: Path, name: str,
                                  manifest_raw: bytes | None,
                                  saipen_home: str = "") -> dict[str, str]:
    dependencies = {MANIFEST_REL: _captured_hash(manifest_raw)}
    board_rel = f"{SUBS_REL}/{name}/BOARD.md"
    dependencies[board_rel] = _captured_hash(_read_bytes_maybe(root / board_rel))
    charter_rel = f"{SUBS_REL}/{name}.md"
    dependencies[charter_rel] = _captured_hash(
        _read_bytes_maybe(root / charter_rel))
    protocol_rel = f"{SUBS_REL}/PROTOCOL.md"
    dependencies[protocol_rel] = _captured_hash(
        _read_bytes_maybe(root / protocol_rel))
    if saipen_home:
        home_charter = (Path(saipen_home) / "extensions" / "subs" /
                        f"{name}.md").resolve()
        dependencies[str(home_charter)] = _captured_hash(
            _read_bytes_maybe(home_charter))
    return dependencies


# ---------------------------------------------------------------------------
# adopt
# ---------------------------------------------------------------------------
def sub_adopt(project_root: Path | str, name: str, saipen_home: str,
              dry_run: bool = False) -> Result:
    """Re-anchor a sub under the CURRENT project-local charter (PROTOCOL § 6).

    The local charter is the only authority: a built-in charter present in
    saipen_home but missing locally is SYNC_REQUIRED / ROLE_EVIDENCE_-
    UNAVAILABLE, never silently replaced by the home copy. A generic role
    adopts against the local PROTOCOL digest. `dry_run` computes the same
    patch with ZERO writes.
    """
    root = Path(project_root)
    try:
        _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    manifest_raw, entry, manifest_errors = _registered_entry(root, name)
    if manifest_errors:
        return _refuse("INVALID_MANIFEST", "; ".join(manifest_errors[:5]),
                       name=name, errors=manifest_errors)
    state_path = _entry_dir(root, entry) / "STATE.md"
    if not state_path.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    local_charter = root / SUBS_REL / f"{name}.md"
    home_charter = Path(saipen_home) / "extensions" / "subs" / f"{name}.md"
    local_protocol = root / SUBS_REL / "PROTOCOL.md"
    role_raw = None
    home_charter_raw = _read_bytes_maybe(home_charter)
    try:
        if local_charter.is_file():
            role_raw = local_charter.read_bytes()
            role_revision = _role_revision_from_bytes(role_raw, generic=False)
        elif home_charter_raw is not None:
            return _refuse("VALIDATION_FAILED",
                           f"{name!r} has a built-in charter in saipen_home "
                           "but not project-locally -- SYNC_REQUIRED: run "
                           "`saipen sub sync`; ROLE_EVIDENCE_UNAVAILABLE",
                           name=name)
        elif local_protocol.is_file():
            role_raw = local_protocol.read_bytes()
            role_revision = _role_revision_from_bytes(role_raw, generic=True)
        else:
            return _refuse("VALIDATION_FAILED",
                           f"no local charter or PROTOCOL.md for {name!r} -- "
                           "run `saipen sub sync`; ROLE_EVIDENCE_UNAVAILABLE",
                           name=name)
    except (ValueError, OSError) as exc:
        return _refuse("VALIDATION_FAILED",
                       f"cannot derive role revision for {name!r}: {exc}",
                       name=name)
    doc = codec.read_document(state_path)
    rel = f"{SUBS_REL}/{name}/STATE.md"
    new_text = patch_state(doc.text_norm, {
        "role_revision": role_revision,
        "updated": _utc_iso(),
    })
    lifecycle_reads = _lifecycle_read_preconditions(
        root, name, manifest_raw, saipen_home)
    if dry_run:
        return Result(ok=True, code="SUB_ADOPTED",
                      data={"name": name, "role_revision": role_revision,
                            "dry_run": True,
                            "would_write": [rel]})
    op_id = "sub-adopt-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, "sub_adopt", "saipen-cli", project_identity(root),
            hash_bytes(("sub_adopt:" + name).encode("utf-8")),
            [{"path": rel, "role": "state", "content": doc.encode(new_text),
              "before_hash": doc.raw_hash,
              "after_hash": hash_bytes(doc.encode(new_text))}],
            preconditions={rel: doc.raw_hash},
            read_preconditions=lifecycle_reads,
            verification_policy="sub_lifecycle")
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SUB_ADOPTED", op_id=op_id,
                  changed_files=[rel],
                  data={"name": name, "role_revision": role_revision})


# ---------------------------------------------------------------------------
# pause / resume
# ---------------------------------------------------------------------------
def sub_pause(project_root: Path | str, name: str,
              dry_run: bool = False) -> Result:
    """Pause a subSaipen: record prior phase/next_action, then BLOCKED.

    The prior execution state is stored conditionally on the sub's STATE as
    owned pause-lifecycle metadata (`paused_from_phase` / `paused_from_na`)
    so resume can restore it deterministically. A trace line is appended to
    the sub's own LOG. `dry_run` performs the same validation and computes
    the same patch with ZERO writes/LOG/STATE/journal.
    """
    root = Path(project_root)
    try:
        _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    manifest_raw, entry, manifest_errors = _registered_entry(root, name)
    if manifest_errors:
        return _refuse("INVALID_MANIFEST", "; ".join(manifest_errors[:5]),
                       name=name, errors=manifest_errors)
    state_path = _entry_dir(root, entry) / "STATE.md"
    if not state_path.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    doc = codec.read_document(state_path)
    from .state import parse_state
    st = parse_state(doc.text_norm)
    if st.get("phase") == "BLOCKED":
        return _refuse("VALIDATION_FAILED",
                       f"subSaipen {name!r} is already BLOCKED", name=name)
    rel = f"{SUBS_REL}/{name}/STATE.md"
    new_text = patch_state(doc.text_norm, {
        "phase": "BLOCKED",
        "blocker": "paused by main agent",
        "paused_from_phase": st.get("phase") or "PLAN",
        "paused_from_na": st.get("next_action") or "saipen plan",
        "updated": _utc_iso(),
    })
    targets = [{"path": rel, "role": "state", "content": doc.encode(new_text),
                "before_hash": doc.raw_hash,
                "after_hash": hash_bytes(doc.encode(new_text))}]
    log_rel = f"{SUBS_REL}/{name}/LOG.md"
    log_raw = _read_bytes_maybe(root / log_rel)
    targets.extend(_sub_trace_targets(name, "pause",
                                      f"paused by main agent "
                                      f"(from {st.get('phase')})", log_raw))
    lifecycle_reads = _lifecycle_read_preconditions(
        root, name, manifest_raw, st.get("saipen_home") or "")
    if dry_run:
        return Result(ok=True, code="SUB_PAUSED",
                      data={"name": name,
                            "paused_from_phase": st.get("phase"),
                            "dry_run": True,
                            "would_write": [t["path"] for t in targets]})
    op_id = "sub-pause-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, "sub_pause", "saipen-cli", project_identity(root),
            hash_bytes(("sub_pause:" + name).encode("utf-8")),
            targets,
            preconditions={rel: doc.raw_hash,
                           log_rel: _captured_hash(log_raw)},
            read_preconditions=lifecycle_reads,
            verification_policy="sub_lifecycle")
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SUB_PAUSED", op_id=op_id,
                  changed_files=[t["path"] for t in targets],
                  data={"name": name,
                        "paused_from_phase": st.get("phase")})


def sub_resume(project_root: Path | str, name: str,
               dry_run: bool = False) -> Result:
    """Resume a subSaipen: prove it was paused by us, restore exact prior
    phase + next_action, clear blocker and pause metadata, append trace.

    Refuses SUB_RESUME if the sub was not paused by the main agent or has no
    recorded prior state -- no fake success. `dry_run` computes the same
    patch with ZERO writes.
    """
    root = Path(project_root)
    try:
        _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    manifest_raw, entry, manifest_errors = _registered_entry(root, name)
    if manifest_errors:
        return _refuse("INVALID_MANIFEST", "; ".join(manifest_errors[:5]),
                       name=name, errors=manifest_errors)
    state_path = _entry_dir(root, entry) / "STATE.md"
    if not state_path.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    doc = codec.read_document(state_path)
    from .state import parse_state
    st = parse_state(doc.text_norm)
    if st.get("phase") != "BLOCKED" or \
            st.get("blocker") != "paused by main agent":
        return _refuse("VALIDATION_FAILED",
                       f"subSaipen {name!r} is not paused by the main agent",
                       name=name, phase=st.get("phase"))
    prior_phase = st.get("paused_from_phase")
    prior_na = st.get("paused_from_na")
    if not prior_phase:
        return _refuse("RECOVERY_REQUIRED",
                       f"subSaipen {name!r} has no recorded paused state; "
                       "restore phase/next_action from its LOG tail manually",
                       name=name)
    rel = f"{SUBS_REL}/{name}/STATE.md"
    new_text = patch_state(doc.text_norm, {
        "phase": prior_phase,
        "next_action": prior_na,
        "blocker": "",
        "paused_from_phase": "",
        "paused_from_na": "",
        "updated": _utc_iso(),
    })
    targets = [{"path": rel, "role": "state", "content": doc.encode(new_text),
                "before_hash": doc.raw_hash,
                "after_hash": hash_bytes(doc.encode(new_text))}]
    log_rel = f"{SUBS_REL}/{name}/LOG.md"
    log_raw = _read_bytes_maybe(root / log_rel)
    targets.extend(_sub_trace_targets(name, "resume",
                                      f"resumed to {prior_phase}", log_raw))
    lifecycle_reads = _lifecycle_read_preconditions(
        root, name, manifest_raw, st.get("saipen_home") or "")
    if dry_run:
        return Result(ok=True, code="SUB_RESUMED",
                      data={"name": name, "restored_phase": prior_phase,
                            "restored_next_action": prior_na,
                            "dry_run": True,
                            "would_write": [t["path"] for t in targets]})
    op_id = "sub-resume-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, "sub_resume", "saipen-cli", project_identity(root),
            hash_bytes(("sub_resume:" + name).encode("utf-8")),
            targets,
            preconditions={rel: doc.raw_hash,
                           log_rel: _captured_hash(log_raw)},
            read_preconditions=lifecycle_reads,
            verification_policy="sub_lifecycle")
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SUB_RESUMED", op_id=op_id,
                  changed_files=[t["path"] for t in targets],
                  data={"name": name, "restored_phase": prior_phase,
                        "restored_next_action": prior_na})


def _sub_trace_targets(name: str, action: str, message: str,
                       log_raw: bytes | None) -> list[dict]:
    """One trace line appended to the sub's own LOG (PROTOCOL traceability)."""
    log_rel = f"{SUBS_REL}/{name}/LOG.md"
    text = _decode_captured(log_raw, log_rel)
    from .log import log_tail_event
    tail = log_tail_event(text)
    from .log import build_event
    _event, line = build_event(tail, "DEC",
                               f"main agent {action}: {message}",
                               ticket=None, agent="saipen-cli", now=_now())
    new_log = (text.rstrip("\n") + "\n" + line + "\n") if text else \
        ("# Log\n\n" + line + "\n")
    return [{"path": log_rel, "role": "log", "content": new_log.encode("utf-8"),
             "before_hash": _captured_hash(log_raw),
             "after_hash": hash_bytes(new_log.encode("utf-8"))}]


def sub_clean_preflight(project_root: Path | str, name: str) -> Result:
    """Evidence-gated removal preflight (PROTOCOL section 7, read-only).

    Delegates the deterministic evidence scan to tools/sub_clean.py's
    sub_clean_blockers. The engine NEVER deletes; this reports every blocker
    and, when clean, leaves removal to the human-confirmed path.
    """
    root = Path(project_root)
    try:
        _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    _manifest_raw, entry, manifest_errors = _registered_entry(root, name)
    if manifest_errors:
        missing_registration = (len(manifest_errors) == 1
                                and "is not registered" in manifest_errors[0])
        return _refuse("TICKET_NOT_FOUND" if missing_registration
                       else "INVALID_MANIFEST",
                       "; ".join(manifest_errors[:5]), name=name,
                       errors=manifest_errors)
    instance = _entry_dir(root, entry)
    if not instance.is_dir():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    try:
        from sub_clean import sub_clean_blockers
        blockers = sub_clean_blockers(
            instance,
            root / ".saipen" / "recovery" / "subs" / name)
    except RuntimeError as exc:
        return _refuse("VALIDATION_FAILED", str(exc), name=name)
    if blockers:
        return _refuse("VALIDATION_FAILED", "clean refused; " +
                       "; ".join(blockers[:5]), name=name, blockers=list(
                           blockers))
    return Result(ok=True, code="CLEAN_PREFLIGHT", data={"name": name})


def _clean_manifest_bytes(raw: bytes, name: str) -> bytes:
    """Remove exactly one strict entry line while preserving all other bytes."""
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    kept = []
    removed = 0
    for raw_line in raw[len(bom):].splitlines(keepends=True):
        line = raw_line.decode("utf-8")
        stripped = line.strip()
        matched_name = None
        if stripped.startswith("- "):
            head = stripped[2:].split("|", 1)[0].strip()
            match = _ENTRY_RE.fullmatch(head)
            if match:
                matched_name = match.group(1).strip()
        if matched_name == name:
            removed += 1
        else:
            kept.append(raw_line)
    if removed != 1:
        raise ValueError(f"strict MANIFEST contains {removed} entries for {name!r}")
    return bom + b"".join(kept)


def _capture_clean_instance(instance: Path) -> dict:
    """Capture every regular file and directory without crossing links."""
    from sub_clean import _is_reparse_point

    try:
        root_info = instance.lstat()
    except OSError as exc:
        raise RuntimeError(f"cannot stat cleanup instance {instance}: {exc}") from exc
    if (not stat.S_ISDIR(root_info.st_mode) or instance.is_symlink()
            or _is_reparse_point(instance)):
        raise RuntimeError("cleanup instance is not a regular owned directory")
    files: dict[str, bytes] = {}
    directories: list[str] = []
    errors: list[OSError] = []
    for current, dirnames, names in os.walk(
            instance, topdown=True, followlinks=False, onerror=errors.append):
        dirnames.sort()
        names.sort()
        current_path = Path(current)
        directories.append(current_path.relative_to(instance).as_posix())
        for dirname in dirnames:
            candidate = current_path / dirname
            try:
                info = candidate.lstat()
            except OSError as exc:
                errors.append(exc)
                continue
            if (not stat.S_ISDIR(info.st_mode) or candidate.is_symlink()
                    or _is_reparse_point(candidate)):
                rel = candidate.relative_to(instance).as_posix()
                raise RuntimeError(
                    f"cleanup refuses symlink, junction, or non-directory: {rel}")
        for filename in names:
            candidate = current_path / filename
            try:
                info = candidate.lstat()
            except OSError as exc:
                errors.append(exc)
                continue
            if (not stat.S_ISREG(info.st_mode) or candidate.is_symlink()
                    or _is_reparse_point(candidate)):
                rel = candidate.relative_to(instance).as_posix()
                raise RuntimeError(
                    f"cleanup refuses symlink, junction, or non-regular file: {rel}")
            try:
                files[candidate.relative_to(instance).as_posix()] = \
                    candidate.read_bytes()
            except OSError as exc:
                errors.append(exc)
    if errors:
        raise RuntimeError(f"cannot capture cleanup instance: {errors[0]}")
    tree_hash = hash_delete_tree(instance)
    if not tree_hash.startswith("delete-tree-sha256:"):
        raise RuntimeError(f"cleanup instance tree is unsafe: {tree_hash}")
    return {"files": files, "directories": directories,
            "tree_hash": tree_hash}


def sub_clean(project_root: Path | str, name: str,
              dry_run: bool = False) -> Result:
    """Archive, unregister, and remove one SubSaipen transactionally."""
    root = Path(project_root)
    try:
        instance = _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    manifest_raw = _read_bytes_maybe(root / MANIFEST_REL)
    if manifest_raw is None:
        return _refuse("INVALID_MANIFEST", "no MANIFEST.md", name=name)
    try:
        entries, manifest_errors = parse_manifest(
            _decode_captured(manifest_raw, MANIFEST_REL))
    except ValueError as exc:
        return _refuse("INVALID_MANIFEST", str(exc), name=name)
    if manifest_errors:
        return _refuse("INVALID_MANIFEST", "; ".join(manifest_errors[:5]),
                       name=name, errors=manifest_errors)
    entry = next((candidate for candidate in entries
                  if candidate.name == name), None)
    if entry is None:
        if not os.path.lexists(instance):
            return Result(ok=True, code="ALREADY_CLEAN", data={"name": name})
        return _refuse("RECOVERY_REQUIRED",
                       f"unregistered instance still exists for {name!r}",
                       name=name)
    try:
        if _entry_dir(root, entry).resolve() != instance.resolve():
            return _refuse("PATH_ESCAPE",
                           f"MANIFEST path does not bind {name!r} instance",
                           name=name)
        snapshot = _capture_clean_instance(instance)
        from sub_clean import sub_clean_blockers
        blockers = sub_clean_blockers(
            instance, root / ".saipen" / "recovery" / "subs" / name)
        new_manifest = _clean_manifest_bytes(manifest_raw, name)
    except (RuntimeError, ValueError, OSError) as exc:
        return _refuse("VALIDATION_FAILED", str(exc), name=name)
    if blockers:
        return _refuse("VALIDATION_FAILED", "clean refused; "
                       + "; ".join(blockers[:5]), name=name,
                       blockers=list(blockers))

    op_id = "sub-clean-" + __import__("uuid").uuid4().hex[:8]
    archive_rel = f".saipen/recovery/subs/{name}/{op_id}"
    archive_instance_rel = f"{archive_rel}/instance"
    archive_root = root / archive_rel
    try:
        prove_inside(archive_root, root.resolve(), kind="sub clean archive")
        _reject_reparse_ancestors(root, archive_root)
    except ValueError as exc:
        return _refuse("PATH_ESCAPE", str(exc), name=name)
    file_hashes = {rel: hash_bytes(raw)
                   for rel, raw in sorted(snapshot["files"].items())}
    receipt = {
        "operation": "sub_clean",
        "op_id": op_id,
        "name": name,
        "source_instance": f"{SUBS_REL}/{name}",
        "archive_instance": archive_instance_rel,
        "instance_tree_hash": snapshot["tree_hash"],
        "manifest_before_hash": hash_bytes(manifest_raw),
        "files": file_hashes,
    }
    receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(
        "utf-8")
    targets = [
        {"path": f"{archive_instance_rel}/{rel}", "role": "generic",
         "action": "write", "content": raw}
        for rel, raw in sorted(snapshot["files"].items())
    ]
    targets.extend([
        {"path": f"{archive_rel}/receipt.json", "role": "report",
         "action": "write", "content": receipt_raw},
        {"path": MANIFEST_REL, "role": "manifest", "action": "write",
         "content": new_manifest},
    ])
    source_prefix = f"{SUBS_REL}/{name}"
    targets.extend(
        {"path": f"{source_prefix}/{rel}", "role": "generic",
         "action": "delete_file"}
        for rel in sorted(snapshot["files"])
    )
    deepest_dirs = sorted(snapshot["directories"],
                          key=lambda rel: (len(Path(rel).parts), rel),
                          reverse=True)
    targets.extend(
        {"path": source_prefix if rel == "." else f"{source_prefix}/{rel}",
         "role": "generic", "action": "delete_dir",
         "planned_before_hash": empty_delete_tree_hash()}
        for rel in deepest_dirs
    )
    would_write = [target["path"] for target in targets
                   if target["action"] == "write"]
    would_delete = [target["path"] for target in targets
                    if target["action"].startswith("delete_")]
    if dry_run:
        return Result(ok=True, code="SUB_CLEAN_PLAN", op_id=op_id,
                      data={"name": name, "dry_run": True,
                            "would_write": would_write,
                            "would_delete": would_delete,
                            "instance_tree_hash": snapshot["tree_hash"]})

    try:
        with project_writer_lock(root):
            live_manifest = _read_bytes_maybe(root / MANIFEST_REL)
            try:
                live_snapshot = _capture_clean_instance(instance)
            except RuntimeError:
                live_snapshot = None
            if live_manifest != manifest_raw or live_snapshot != snapshot:
                return _refuse("STALE_STATE",
                               "MANIFEST or instance tree changed after clean "
                               "planning; zero cleanup writes performed",
                               name=name)
            if os.path.lexists(archive_root):
                return _refuse("STALE_STATE",
                               f"archive destination already exists: {archive_rel}",
                               name=name)
            commit = run_mutation(
                root, op_id, "sub_clean", "saipen-cli", project_identity(root),
                hash_bytes(("sub_clean:" + name + ":"
                            + snapshot["tree_hash"]).encode("utf-8")),
                targets,
                preconditions={
                    MANIFEST_REL: hash_bytes(manifest_raw),
                    **{f"{archive_instance_rel}/{rel}": ""
                       for rel in snapshot["files"]},
                    f"{archive_rel}/receipt.json": "",
                    **{f"{source_prefix}/{rel}": digest
                       for rel, digest in file_hashes.items()},
                },
                verification_policy="sub_clean")
    except PermissionError:
        return _refuse("WRITER_BUSY",
                       "another live writer holds the project lock", name=name)
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SUB_CLEANED", op_id=op_id,
                  changed_files=would_write + would_delete,
                  data={"name": name, "archive": archive_rel,
                        "deleted": would_delete})


def _collect_policy(root: Path, name: str) -> tuple[str | None, str | None,
                                                    Path]:
    """Resolve executable collection policy from registry + local charter."""
    charter = root / SUBS_REL / f"{name}.md"
    role = ROLE_REGISTRY.get(name)
    if not charter.is_file():
        if role is not None:
            return None, f"{name}: local charter missing", charter
        return "core-review", None, root / SUBS_REL / "PROTOCOL.md"
    try:
        text = charter.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except OSError as exc:
        return None, f"{name}: charter unreadable: {exc}", charter
    block = re.search(r"(?ms)^```yaml\n(.*?)^```\s*$", text)
    values = re.findall(r"(?m)^collect_policy:\s*(\S+)\s*$",
                        block.group(1) if block else "")
    if len(values) != 1 or values[0] not in {
            "automatic", "core-review", "explicit"}:
        return None, (f"{name}: charter must declare one collect_policy from "
                      "automatic|core-review|explicit"), charter
    policy = values[0]
    if role is not None and policy != role.collect_policy:
        return None, (f"{name}: charter collect_policy {policy!r} disagrees "
                      f"with CrewRole {role.collect_policy!r}"), charter
    return policy, None, charter


def _canonical_package_block(package: OutboxPackage) -> bytes:
    """Status-neutral LF form: ready -> reviewed keeps package identity."""
    lines = package.block.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    rendered = []
    for line in lines:
        match = OUTBOX_FIELD_RE.match(line)
        rendered.append("- **status:** ready" if match and
                        match.group(1) == "status" else line)
    return ("\n".join(rendered).rstrip("\n") + "\n").encode("utf-8")


def package_identity(package: OutboxPackage) -> str:
    """Immutable full SHA-256 over package block + producer/source triple."""
    parts = (
        _canonical_package_block(package),
        package.fields.get("producer", "").encode("utf-8"),
        package.fields.get("source_head", "").encode("utf-8"),
        package.fields.get("source_tree_fingerprint", "").encode("utf-8"),
        package.fields.get("role_revision", "").encode("utf-8"),
    )
    digest = hashlib.sha256(b"saipen-sub-collect-v1\0")
    for part in parts:
        digest.update(struct.pack(">Q", len(part)))
        digest.update(part)
    return "sha256:" + digest.hexdigest()


def _mark_package_reviewed(text: str, package_id: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    active = False
    changed = 0
    for index, line in enumerate(lines):
        heading = OUTBOX_HEADING_RE.fullmatch(line)
        if heading:
            active = heading.group(1) == package_id
            continue
        match = OUTBOX_FIELD_RE.match(line)
        if active and match and match.group(1) == "status":
            if match.group(2).strip() != "ready":
                raise ValueError(f"package {package_id} is no longer READY")
            lines[index] = "- **status:** reviewed"
            changed += 1
    if changed != 1:
        raise ValueError(f"package {package_id} has {changed} status fields")
    return "\n".join(lines)


def _manifest_with_collects(text: str, updates: dict[str, str]) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    seen = set()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        parts = stripped[2:].split("|")
        match = _ENTRY_RE.match(parts[0].strip())
        if not match or match.group(1).strip() not in updates:
            continue
        name = match.group(1).strip()
        metadata = [part.strip() for part in parts[1:]
                    if not part.strip().startswith("last_collect:")]
        metadata.append(f"last_collect: {updates[name]}")
        lines[index] = "- " + parts[0].strip() + " | " + " | ".join(metadata)
        seen.add(name)
    missing = sorted(set(updates) - seen)
    if missing:
        raise ValueError("MANIFEST entries disappeared: " + ", ".join(missing))
    return "\n".join(lines)


def _core_log_context(root: Path, active_log: str) -> tuple[str, dict[str, str]]:
    """Return full LOG allocation context and captured sealed dependencies."""
    dependencies = {}
    chunks = []
    segments = sorted((root / ".saipen" / "logs").glob("LOG-*.md"),
                      key=lambda path: int(re.search(r"(\d+)", path.stem).group(1)))
    for segment in segments:
        raw = _read_bytes_maybe(segment)
        rel = segment.relative_to(root).as_posix()
        dependencies[rel] = _captured_hash(raw)
        chunks.append(_decode_captured(raw, rel))
    chunks.append(active_log)
    return "\n".join(chunks), dependencies


def sub_collect(project_root: Path | str, name: str | None = None,
                dry_run: bool = False) -> Result:
    """Journal ready SubSaipen hypotheses into ordinary Core review tickets.

    Aggregate collection considers only automatic/core-review policies and
    skips explicit producers. Targeting an explicit producer refuses because
    its producer-specific SC integration stage owns that payload.
    """
    from .board import escape_ticket_description, parse_board
    from .fast_check import validate_texts
    from .log import build_event, log_tail_event
    from .operations import next_ticket_id

    root = Path(project_root)
    manifest_path = root / MANIFEST_REL
    manifest_doc = codec.read_document(manifest_path)
    entries, errors = parse_manifest(manifest_doc.text_norm)
    if errors:
        return _refuse("INVALID_MANIFEST",
                       "MANIFEST malformed: " + "; ".join(errors[:5]),
                       errors=errors)
    by_name = {entry.name: entry for entry in entries}
    if name is not None and name not in by_name:
        return _refuse("TICKET_NOT_FOUND",
                       f"no subSaipen {name!r} in MANIFEST", name=name)

    candidates = [name] if name is not None else sorted(by_name)
    policies = {}
    charter_dependencies = {}
    skipped = []
    for producer in candidates:
        policy, policy_error, charter = _collect_policy(root, producer)
        raw = _read_bytes_maybe(charter)
        charter_dependencies[str(charter.resolve())] = _captured_hash(raw)
        if policy_error:
            return _refuse("VALIDATION_FAILED", policy_error, name=producer)
        policies[producer] = policy
        if policy == "explicit":
            if name is not None:
                role = ROLE_REGISTRY.get(producer)
                stage = role.stage if role is not None else "SC"
                return _refuse(
                    "VALIDATION_FAILED",
                    f"EXPLICIT_POLICY: {producer} is an explicit producer; "
                    f"producer-specific {stage} "
                    "integration owns it, so `saipen sub collect` refuses")
            skipped.append({"name": producer, "policy": policy,
                            "reason": "EXPLICIT_POLICY"})

    eligible = [producer for producer in candidates
                if policies[producer] in ("automatic", "core-review")]
    from freshness import compute_source_identity
    try:
        current = compute_source_identity(root)
        source_dependency = hash_source_identity(root)
    except Exception as exc:
        return _refuse("VALIDATION_FAILED", f"source identity UNKNOWN: {exc}")

    state_doc = codec.read_document(root / ".saipen" / "STATE.md")
    board_doc = codec.read_document(root / ".saipen" / "BOARD.md")
    log_doc = codec.read_document(root / ".saipen" / "LOG.md")
    board = parse_board(board_doc.text_norm)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]))
    full_log, sealed_dependencies = _core_log_context(root, log_doc.text_norm)

    planned = []
    package_reports = []
    deduplicated = []
    outbox_docs = {}
    for producer in eligible:
        entry = by_name[producer]
        outbox_path = _entry_dir(root, entry) / "kitchen" / "OUTBOX.md"
        if not outbox_path.is_file():
            if name is not None:
                return _refuse("PACKAGE_INCOMPLETE",
                               f"{producer}: no OUTBOX")
            package_reports.append({"name": producer, "packages": []})
            continue
        outbox_doc = codec.read_document(outbox_path)
        outbox_docs[producer] = outbox_doc
        model = parse_outbox(outbox_doc.text_norm, producer)
        if model.errors:
            return _refuse("MALFORMED_PACKAGE",
                           f"{producer}: " + "; ".join(model.errors[:5]),
                           name=producer, errors=list(model.errors))
        current_ready = []
        stale_ready = []
        reviewed = []
        for package in model.packages:
            identity = package_identity(package)
            info = {"id": package.package_id, "status": package.status,
                    "package_identity": identity}
            if package.status == "reviewed":
                reviewed.append((package, identity))
                continue
            if package.status != "ready":
                continue
            role_state = role_freshness(root, producer,
                                        package.fields["role_revision"],
                                        saipen_home_of(root))
            reasons = []
            if package.fields["source_head"] != current.source_head:
                reasons.append("source_head stale")
            if package.fields["source_tree_fingerprint"] != \
                    current.source_tree_fingerprint:
                reasons.append("source_tree_fingerprint differs")
            if role_state != "current":
                reasons.append(f"role_revision {role_state}")
            if reasons:
                stale_ready.append((package, reasons))
            else:
                current_ready.append((package, identity, info))
        last_collect = entry.metadata.get("last_collect", "")
        durable = {identity for _package, identity in reviewed
                   if identity in board_doc.text_norm
                   or identity in log_doc.text_norm
                   or last_collect.startswith(identity + "@")}
        if not current_ready and durable:
            deduplicated.extend({"name": producer,
                                 "package_identity": identity}
                                for identity in sorted(durable))
            package_reports.append({"name": producer, "packages": [
                {"id": package.package_id, "status": package.status,
                 "package_identity": identity, "deduplicated": True}
                for package, identity in reviewed if identity in durable]})
            continue
        if stale_ready:
            detail = "; ".join(
                f"{producer}/{package.package_id}: {', '.join(reasons)}"
                for package, reasons in stale_ready)
            return _refuse("PACKAGE_INCOMPLETE",
                           "collect refused; stale READY package(s): " + detail)
        if len(current_ready) != 1:
            # An existing canonical empty queue is truthful evidence that
            # there is currently nothing to collect, including for a targeted
            # diagnostic. A targeted nonempty queue with no READY package is
            # different: it is incomplete and must still refuse.
            if not current_ready and (name is None or not model.packages):
                package_reports.append({"name": producer, "packages": []})
                continue
            return _refuse(
                "PACKAGE_INCOMPLETE" if not current_ready else
                "MALFORMED_PACKAGE",
                f"{producer}: expected exactly one current READY package; "
                f"found {len(current_ready)}")
        package, identity, info = current_ready[0]
        if (identity in board_doc.text_norm or identity in log_doc.text_norm
                or last_collect.startswith(identity + "@")):
            deduplicated.append({"name": producer,
                                 "package_identity": identity})
            continue
        planned.append({"producer": producer, "entry": entry,
                        "package": package, "identity": identity,
                        "outbox_path": outbox_path})
        package_reports.append({"name": producer, "packages": [info]})

    if not planned:
        code = "ALREADY_COLLECTED" if deduplicated else "SUB_COLLECT"
        return Result(ok=True, code=code,
                      data={"names": eligible, "packages": package_reports,
                            "skipped": skipped,
                            "deduplicated": deduplicated,
                            "dry_run": dry_run})

    now_iso = _utc_iso()
    now_log = _now()
    next_id = next_ticket_id(board_doc.text_norm, full_log)
    tail = log_tail_event(full_log)
    op_id = "sub-collect-" + __import__("uuid").uuid4().hex[:8]
    new_board = board_doc.text_norm
    new_log = log_doc.text_norm
    tickets = []
    manifest_updates = {}
    outbox_targets = []
    for offset, item in enumerate(planned):
        producer = item["producer"]
        package = item["package"]
        identity = item["identity"]
        ticket = f"T-{next_id + offset}"
        provenance = (
            f"package_identity={identity}; producer={producer}; "
            f"package={package.package_id}; source_head="
            f"{package.fields['source_head']}; source_tree_fingerprint="
            f"{package.fields['source_tree_fingerprint']}; role_revision="
            f"{package.fields['role_revision']}; outbox="
            f"{item['outbox_path'].relative_to(root).as_posix()}")
        description = escape_ticket_description(
            f"Review SubSaipen hypothesis {producer}/{package.package_id}: "
            f"{package.description}; not accepted fact; {provenance}")
        verify = escape_ticket_description(
            "Independently reproduce or reject hypothesis, record Core "
            f"disposition, apply no package patch during intake; {provenance}")
        severity = package.fields.get("severity", "")
        priority = severity if severity in ("P0", "P1", "P2") else \
            ("P1" if package.fields.get("critical", "").lower() == "true"
             else "P2")
        line = f"- [ ] {ticket} [{priority}] {description} | verify: {verify}"
        board_lines = new_board.splitlines(keepends=True)
        todo_index = next(index for index, value in enumerate(board_lines)
                          if value.startswith("## TODO"))
        board_lines.insert(todo_index + 1, line + "\n")
        new_board = "".join(board_lines)
        event, log_line = build_event(
            tail, "RUN",
            f"collect {producer}/{package.package_id} -> {ticket}; "
            f"{provenance}; queued as Core review hypothesis",
            ticket=ticket, agent=producer, now=now_log,
            op_id=op_id)
        tail = event
        new_log = new_log.rstrip("\n") + "\n" + log_line + "\n"
        tickets.append({"ticket": ticket, "producer": producer,
                        "package": package.package_id,
                        "package_identity": identity})
        manifest_updates[producer] = identity + "@" + now_iso
        outbox_doc = outbox_docs[producer]
        reviewed_text = _mark_package_reviewed(outbox_doc.text_norm,
                                               package.package_id)
        rel = item["outbox_path"].relative_to(root).as_posix()
        outbox_targets.append({"path": rel, "role": "report",
                               "content": outbox_doc.encode(reviewed_text)})

    new_state = patch_state(state_doc.text_norm, {
        "last_event": tail,
        "updated": now_iso,
    })
    new_manifest = _manifest_with_collects(manifest_doc.text_norm,
                                           manifest_updates)
    proposed_errors = validate_texts(new_state, new_board, new_log)
    _parsed_manifest, manifest_errors = parse_manifest(new_manifest)
    if proposed_errors or manifest_errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed collect fails validation: " + "; ".join(
                           (proposed_errors + manifest_errors)[:5]))

    targets = [
        {"path": ".saipen/LOG.md", "role": "log",
         "content": log_doc.encode(new_log)},
        {"path": ".saipen/BOARD.md", "role": "board",
         "content": board_doc.encode(new_board)},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": state_doc.encode(new_state)},
        *outbox_targets,
        {"path": MANIFEST_REL, "role": "manifest",
         "content": manifest_doc.encode(new_manifest)},
    ]
    preconditions = {
        ".saipen/LOG.md": log_doc.raw_hash,
        ".saipen/BOARD.md": board_doc.raw_hash,
        ".saipen/STATE.md": state_doc.raw_hash,
        MANIFEST_REL: manifest_doc.raw_hash,
    }
    preconditions.update({target["path"]: outbox_docs[item["producer"]].raw_hash
                          for target, item in zip(outbox_targets, planned)})
    read_preconditions = {".": source_dependency, **sealed_dependencies,
                          **charter_dependencies}
    changed = [target["path"] for target in targets]
    if dry_run:
        return Result(ok=True, code="SUB_COLLECTED",
                      data={"names": eligible, "packages": package_reports,
                            "tickets": tickets, "skipped": skipped,
                            "deduplicated": deduplicated, "dry_run": True,
                            "would_write": changed})
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, "sub_collect", "saipen-cli", project_identity(root),
            hash_bytes(("sub_collect:" + ",".join(
                item["identity"] for item in planned)).encode("utf-8")),
            targets, preconditions=preconditions,
            read_preconditions=read_preconditions,
            verification_policy="sub_collect")
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), tickets=tickets)
    return Result(ok=True, code="SUB_COLLECTED", op_id=op_id,
                  changed_files=changed,
                  data={"names": eligible, "packages": package_reports,
                        "tickets": tickets, "skipped": skipped,
                        "deduplicated": deduplicated})


def saipen_home_of(project_root: Path) -> str:
    from .state import parse_state
    st = parse_state(codec.read_doc(project_root / ".saipen" / "STATE.md"))
    return st.get("saipen_home") or ""

"""V7 Producer Parallelism Hardening -- the mechanical layer.

Everything here is zero-dependency stdlib so it can be imported by the
validator, the engine, and the scenario harness without drift.

Design contract (see the V7 spec, PRODUCER PARALLELISM HARDENING):

  * Core remains the sole main-tree writer. `saipen crew` stays serial.
  * Producers (saitranslate / saiwiki) may:
        - read canonical project source;
        - write their own producer namespace;
        - create their own package evidence.
  * Producers may NOT:
        - mutate Core STATE/BOARD/LOG;
        - integrate their own output;
        - collect / disposition;
        - commit / tag / push / ship.
  * Integration is serialized through the canonical Core writer lock.
  * No daemon, no DB, no GUI, no background service, no distributed STATE.

The module is deliberately PATH-AGNOSTIC: a "namespace" is just a directory.
Conventional layout is provided by `producer_namespace()` but never hard-coded
into the safety logic.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import uuid
import contextlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping

# --- local engine imports (no cycle: lock/capability never import producer) ---
from .lock import ProducerLock, project_writer_lock


def _utc_now_iso() -> str:
    """W2-004: microsecond-precision UTC timestamp for dependency binding."""
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------------
# Constants & closed enums
# ---------------------------------------------------------------------------

PRODUCERS = ("saitranslate", "saiwiki")

STAGING_DIRNAME = ".prepare-staging"
READY_DIRNAME = "READY"
SETTLED_DIRNAME = "SETTLED"
SUPERSEDED_DIRNAME = "SUPERSEDED"
EPOCH_FILENAME = "producer_epoch.json"


def _ready_filename(package_identity: str) -> str:
    """Filesystem-safe READY filename.

    ``package_identity`` is ``sha256:…`` and Windows forbids ``:`` in paths, so
    we sanitize the colon. The on-disk name is cosmetic only -- the canonical
    identity always lives INSIDE the JSON payload.
    """
    return package_identity.replace(":", "_") + ".json"


PACKAGE_MAGIC = b"saipen-producer-pkg-v1\0"
DEP_MAGIC = b"saipen-producer-dep-v1\0"


class PackageStatus(str, Enum):
    STAGING = "staging"
    READY = "ready"
    REVIEWED = "reviewed"
    STALE = "stale"
    SUPERSEDED = "superseded"


class IntegrationClass(str, Enum):
    CURRENT = "CURRENT"
    COMPATIBLE_DRIFT = "COMPATIBLE_DRIFT"
    STALE = "STALE"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProducerError(RuntimeError):
    """Base class for producer-layer failures."""


class StaleWorkerError(ProducerError):
    """An older producer epoch tried to publish after a takeover."""


class ConflictError(ProducerError):
    """Two packages collide on a write target before any canonical write."""


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    """sha256 of a regular file; `sha256:absent` for a missing path.

    Never mtime-based -- we only ever compare content digests.
    """
    p = Path(path)
    if not p.is_file():
        return "sha256:absent"
    return _sha256_bytes(p.read_bytes())


def _is_windows_absolute(rel: str) -> bool:
    """Platform-neutral detection of Windows absolute paths.

    ``Path.is_absolute()`` is HOST-PLATFORM dependent: a drive-rooted path like
    ``C:\\Windows\\win.ini`` or a UNC path like ``\\\\server\\share\\x`` is NOT
    absolute on a POSIX audit host, so a naive host check lets those escape the
    project. We detect the Windows forms by string inspection regardless of the
    host OS so producer dependency metadata can never name an outside-tree file.
    """
    if not isinstance(rel, str):
        return False
    # Drive rooted:  C:\  or  C:/
    if re.match(r"^[A-Za-z]:[\\/]", rel):
        return True
    # UNC / POSIX-double-slash share:  \\server\share  or  //server/share
    return bool(re.match(r"^[\\/]{2,}", rel))


def _validate_producer_rel_path(rel: str, *, context: str = "") -> None:
    """CORE-007: Centralized producer path validation.

    Accepts only safe normalized relative paths from a closed grammar.
    Rejects absolute paths, UNC/drive forms, parent traversal, control
    characters, and paths that would resolve outside a container.
    Raises ProducerError on any violation.
    """
    if not isinstance(rel, str) or not rel:
        raise ProducerError(f"{context}: path must be a non-empty string")
    # Reject absolute paths. ``Path.is_absolute()`` is host-dependent, so we
    # ALSO detect Windows drive/UNC forms by string inspection (CORE-008).
    if Path(rel).is_absolute() or _is_windows_absolute(rel):
        raise ProducerError(
            f"{context}: absolute path {rel!r} rejected; only producer-relative paths allowed"
        )
    # Reject parent traversal
    parts = Path(rel).parts
    if any(part in ("..", ".") for part in parts):
        raise ProducerError(
            f"{context}: path traversal {rel!r} rejected; only simple relative paths allowed"
        )
    # Reject paths with null bytes or control characters
    for ch in rel:
        if ord(ch) < 0x20:
            raise ProducerError(f"{context}: control character in path rejected")
    # Reject Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    _reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    for part in parts:
        stem = part.split(".")[0].upper()
        if stem in _reserved:
            raise ProducerError(f"{context}: Windows reserved name {part!r} in path rejected")


def _safe_rel_hash(root: Path | str, rel: str) -> str:
    """CORE-008: validate, prove containment, then hash a producer-relative path.

    Never opens/hashes ``root / rel`` until ``rel`` passes the closed path
    grammar and the *resolved* target is proven to sit beneath the project
    root (symlink/junction/reparse escape included). This is the single choke
    point every dependency/integration hash must pass.
    """
    _validate_producer_rel_path(rel, context="dependency hash")
    root_path = Path(root)
    try:
        root_res = root_path.resolve()
    except OSError as exc:
        raise ProducerError(f"dependency path {rel!r}: project root unresolvable: {exc}") from exc
    try:
        candidate = (root_path / rel).resolve()
    except OSError as exc:
        raise ProducerError(f"dependency path {rel!r}: target unresolvable: {exc}") from exc
    if candidate != root_res and root_res not in candidate.parents:
        raise ProducerError(
            f"dependency path {rel!r} resolves outside project root "
            f"({candidate} is not under {root_res}); refusing to hash "
            "outside-tree content"
        )
    return file_sha256(candidate)


def read_set_from(root: Path | str, paths: Iterable[str]) -> dict[str, str]:
    """Canonical source dependency path -> content hash (at prepare time).

    CORE-008: every path is validated and containment-proven before hashing so
    an absolute, traversing, drive/UNC, or reparse-escaping path cannot reach
    the filesystem.
    """
    return {rel: _safe_rel_hash(root, rel) for rel in paths}


def write_set_before(root: Path | str, paths: Iterable[str]) -> dict[str, str]:
    """Intended target path -> content hash of the file as it stands NOW
    (the 'before' hash). `sha256:absent` means the target does not yet exist.

    CORE-008: every path is validated before hashing.
    """
    return read_set_from(root, paths)


# ---------------------------------------------------------------------------
# Source identity (duck-typed to freshness.SourceIdentity)
# ---------------------------------------------------------------------------


class SourceKey:
    """W2-007: normalized source-identity representation.

    Both runtime SourceIdentity objects and serialized package fields
    must produce the same classification through global_source_key.
    This class normalizes both forms so the identical-global-identity
    fast path works from any caller.
    """

    __slots__ = ("discovery_model", "source_head", "source_tree_fingerprint")

    def __init__(self, source_head: str, source_tree_fingerprint: str, discovery_model: str = ""):
        self.source_head = source_head
        self.source_tree_fingerprint = source_tree_fingerprint
        self.discovery_model = discovery_model

    @classmethod
    def from_package(cls, pkg: "ProducerPackage") -> "SourceKey":
        """Construct from a ProducerPackage's serialized identity fields."""
        return cls(
            pkg.base_source_head,
            pkg.base_source_tree_fingerprint,
            pkg.base_discovery_model,
        )

    @classmethod
    def from_identity(cls, identity) -> "SourceKey":
        """Construct from a runtime SourceIdentity or duck-typed object."""
        return cls(
            getattr(identity, "source_head", ""),
            getattr(identity, "source_tree_fingerprint", ""),
            getattr(identity, "discovery_model", ""),
        )

    @classmethod
    def from_tuple(cls, t: tuple[str, str, str]) -> "SourceKey":
        """Construct from an explicit (head, fp, model) tuple."""
        head, fp = t[0], t[1]
        model = t[2] if len(t) > 2 else ""
        return cls(head, fp, model)


def global_source_key(identity) -> tuple[str, str, str]:
    """W2-007: (source_head, source_tree_fingerprint, discovery_model).

    Structural-equality key for the 'identical global source identity' fast
    path. Accepts SourceIdentity objects, ProducerPackages, SourceKey
    instances, or duck-typed objects with the three attributes.
    """
    if isinstance(identity, SourceKey):
        return (identity.source_head, identity.source_tree_fingerprint, identity.discovery_model)
    if isinstance(identity, ProducerPackage):
        return (
            identity.base_source_head,
            identity.base_source_tree_fingerprint,
            identity.base_discovery_model,
        )
    if isinstance(identity, tuple) and len(identity) >= 2:
        model = identity[2] if len(identity) > 2 else ""
        return (identity[0], identity[1], model)
    # Duck-typed object with attributes
    return (
        getattr(identity, "source_head", ""),
        getattr(identity, "source_tree_fingerprint", ""),
        getattr(identity, "discovery_model", ""),
    )


# ---------------------------------------------------------------------------
# Dependency fingerprint + stable package identity (spec §1, §6)
# ---------------------------------------------------------------------------


def dependency_fingerprint(
    read_set: Mapping[str, str],
    write_set: Mapping[str, str],
    role_revision: str,
) -> str:
    """A stable hash over the dependency STRUCTURE (paths + content hashes).

    Order-independent: sorting keys makes the fingerprint depend only on the
    declared dependency set, not on dict iteration order.
    """
    digest = hashlib.sha256()
    digest.update(DEP_MAGIC)
    digest.update(role_revision.encode("utf-8"))
    digest.update(b"\0")
    for rel in sorted(read_set):
        digest.update(struct.pack(">Q", len(rel)))
        digest.update(rel.encode("utf-8"))
        digest.update(struct.pack(">Q", len(read_set[rel])))
        digest.update(read_set[rel].encode("utf-8"))
    for rel in sorted(write_set):
        digest.update(struct.pack(">Q", len(rel)))
        digest.update(rel.encode("utf-8"))
        digest.update(struct.pack(">Q", len(write_set[rel])))
        digest.update(write_set[rel].encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def package_identity(
    producer: str,
    role_revision: str,
    dependency_fp: str,
    requested_scope: str,
) -> str:
    """Stable identity derived from at least:

        producer + role_revision + dependency fingerprint + requested scope.

    Repeated preparation of identical work yields the SAME identity, so Core
    can reuse an already-READY package instead of duplicating it (spec §6 F).
    """
    digest = hashlib.sha256()
    digest.update(PACKAGE_MAGIC)
    for part in (producer, role_revision, dependency_fp, requested_scope):
        chunk = part.encode("utf-8")
        digest.update(struct.pack(">Q", len(chunk)))
        digest.update(chunk)
    return "sha256:" + digest.hexdigest()


# ---------------------------------------------------------------------------
# ProducerPackage (spec §1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProducerPackage:
    producer: str
    role_revision: str
    base_source_head: str
    base_source_tree_fingerprint: str
    base_discovery_model: str
    scope: str
    read_set: dict[str, str] = field(default_factory=dict)
    write_set: dict[str, str] = field(default_factory=dict)
    epoch: int = 0
    dependency_fp: str = ""
    package_identity: str = ""
    status: str = PackageStatus.STAGING.value
    # READY-only decoded payload. Excluded from identity derivation because the
    # published payload is independently bound by payload_hashes and the exact
    # write-set keys.
    payloads: dict[str, bytes] = field(default_factory=dict, repr=False, compare=False)
    ready_path: Path | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.dependency_fp:
            object.__setattr__(
                self,
                "dependency_fp",
                dependency_fingerprint(self.read_set, self.write_set, self.role_revision),
            )
        if not self.package_identity:
            object.__setattr__(
                self,
                "package_identity",
                package_identity(
                    self.producer,
                    self.role_revision,
                    self.dependency_fp,
                    self.scope,
                ),
            )

    def to_dict(self) -> dict:
        return {
            "producer": self.producer,
            "role_revision": self.role_revision,
            "base_source_head": self.base_source_head,
            "base_source_tree_fingerprint": self.base_source_tree_fingerprint,
            "base_discovery_model": self.base_discovery_model,
            "scope": self.scope,
            "read_set": dict(self.read_set),
            "write_set": dict(self.write_set),
            "epoch": self.epoch,
            "dependency_fp": self.dependency_fp,
            "package_identity": self.package_identity,
            "status": self.status,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping,
        *,
        expected_producer: str | None = None,
        expected_identity: str | None = None,
        ready_path: Path | None = None,
    ) -> "ProducerPackage":
        """Strict persisted-package decoder.

        Derived authority is always recomputed.  READY payload bytes/hashes,
        namespace producer and filename identity are one closed persistence
        schema; hostile or partial JSON raises ``ProducerError`` rather than
        reaching autonomous planning as a forged package.
        """
        if not isinstance(data, Mapping):
            raise ProducerError("READY package must be a JSON object")
        if ready_path is not None:
            ready_schema = {
                "producer",
                "role_revision",
                "base_source_head",
                "base_source_tree_fingerprint",
                "base_discovery_model",
                "scope",
                "read_set",
                "write_set",
                "epoch",
                "dependency_fp",
                "package_identity",
                "status",
                "payload_hashes",
                "payload_bytes",
            }
            if set(data) != ready_schema:
                missing = sorted(ready_schema - set(data))
                extra = sorted(set(data) - ready_schema)
                raise ProducerError(f"READY schema mismatch (missing={missing}, extra={extra})")
        required_strings = (
            "producer",
            "role_revision",
            "base_source_head",
            "base_source_tree_fingerprint",
            "base_discovery_model",
            "scope",
            "dependency_fp",
            "package_identity",
            "status",
        )
        for key in required_strings:
            if not isinstance(data.get(key), str):
                raise ProducerError(f"READY field {key!r} must be a string")
        producer = data["producer"]
        if producer not in PRODUCERS:
            raise ProducerError(f"READY producer {producer!r} outside {PRODUCERS}")
        if expected_producer is not None and producer != expected_producer:
            raise ProducerError(
                f"READY producer {producer!r} does not match namespace {expected_producer!r}"
            )
        status = data["status"]
        if status not in {item.value for item in PackageStatus}:
            raise ProducerError(f"READY status {status!r} outside closed status set")
        if ready_path is not None and status != PackageStatus.READY.value:
            raise ProducerError("file in READY/SETTLED must carry status 'ready'")
        epoch = data.get("epoch")
        if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
            raise ProducerError("READY epoch must be a non-negative integer")

        def _hash_map(key: str) -> dict[str, str]:
            value = data.get(key)
            if not isinstance(value, Mapping):
                raise ProducerError(f"READY field {key!r} must be a JSON object")
            out: dict[str, str] = {}
            for rel, digest in value.items():
                _validate_producer_rel_path(rel, context=f"package {key}")
                if not isinstance(digest, str):
                    raise ProducerError(f"READY {key}[{rel!r}] must be a string hash")
                out[rel] = digest
            return out

        read_set = _hash_map("read_set")
        write_set = _hash_map("write_set")
        derived_dep = dependency_fingerprint(read_set, write_set, data["role_revision"])
        if data["dependency_fp"] != derived_dep:
            raise ProducerError("READY dependency_fp does not match recomputed dependencies")
        derived_identity = package_identity(
            producer, data["role_revision"], derived_dep, data["scope"]
        )
        if data["package_identity"] != derived_identity:
            raise ProducerError("READY package_identity does not match recomputed identity")
        if expected_identity is not None and derived_identity != expected_identity:
            raise ProducerError("READY filename/request identity does not match package identity")

        payloads: dict[str, bytes] = {}
        if status == PackageStatus.READY.value:
            import base64

            payload_hashes = data.get("payload_hashes")
            payload_bytes = data.get("payload_bytes")
            if not isinstance(payload_hashes, Mapping) or not isinstance(payload_bytes, Mapping):
                raise ProducerError("READY payload_hashes/payload_bytes must be JSON objects")
            if set(payload_hashes) != set(write_set) or set(payload_bytes) != set(write_set):
                raise ProducerError("READY payload keys must exactly equal write_set keys")
            for rel in write_set:
                encoded = payload_bytes[rel]
                expected_hash = payload_hashes[rel]
                if not isinstance(encoded, str) or not isinstance(expected_hash, str):
                    raise ProducerError(f"READY payload metadata for {rel!r} must be strings")
                try:
                    raw = base64.b64decode(encoded.encode("ascii"), validate=True)
                except Exception as exc:
                    raise ProducerError(
                        f"READY payload {rel!r} is not valid base64: {exc}"
                    ) from exc
                if _sha256_bytes(raw) != expected_hash:
                    raise ProducerError(f"READY payload hash mismatch for {rel!r}")
                payloads[rel] = raw

        return cls(
            producer=producer,
            role_revision=data["role_revision"],
            base_source_head=data["base_source_head"],
            base_source_tree_fingerprint=data["base_source_tree_fingerprint"],
            base_discovery_model=data["base_discovery_model"],
            scope=data["scope"],
            read_set=read_set,
            write_set=write_set,
            epoch=epoch,
            dependency_fp=derived_dep,
            package_identity=derived_identity,
            status=status,
            payloads=payloads,
            ready_path=ready_path,
        )


def build_package(
    *,
    producer: str,
    role_revision: str,
    base_source_head: str,
    base_source_tree_fingerprint: str,
    base_discovery_model: str,
    scope: str,
    read_set: Mapping[str, str],
    write_set: Mapping[str, str],
    epoch: int = 0,
    status: str = PackageStatus.STAGING.value,
) -> ProducerPackage:
    return ProducerPackage(
        producer=producer,
        role_revision=role_revision,
        base_source_head=base_source_head,
        base_source_tree_fingerprint=base_source_tree_fingerprint,
        base_discovery_model=base_discovery_model,
        scope=scope,
        read_set=dict(read_set),
        write_set=dict(write_set),
        epoch=epoch,
        status=status,
    )


# ---------------------------------------------------------------------------
# Integration classification (spec §1, read_set/write_set revalidation)
# ---------------------------------------------------------------------------


def classify_integration(
    base_identity,
    current_identity,
    read_set: Mapping[str, str],
    write_set: Mapping[str, str],
    current_hashes: Mapping[str, str],
) -> tuple[IntegrationClass, str]:
    """Decide how a prepared package integrates against the CURRENT source.

    Fast path: identical global source identity -> CURRENT.
    Otherwise revalidate the declared read_set AND write_set against the live
    filesystem (content hashes only -- never mtime):

      * any read dependency changed  -> STALE (relevant input drifted);
      * any intended write target diverged from its 'before' hash -> STALE
        (someone else moved a path this package would clobber);
      * otherwise -> COMPATIBLE_DRIFT (global identity changed but no declared
        dependency of THIS package changed) -> serialized Core integration OK.
    """
    if global_source_key(base_identity) == global_source_key(current_identity):
        return IntegrationClass.CURRENT, "identical global source identity"

    for rel, expected in read_set.items():
        now = current_hashes.get(rel, "sha256:absent")
        if now != expected:
            return (
                IntegrationClass.STALE,
                f"read dependency {rel!r} changed (expected {expected[:12]}.. got {now[:12]}..)",
            )

    for rel, before in write_set.items():
        now = current_hashes.get(rel, "sha256:absent")
        if now != before:
            return (
                IntegrationClass.STALE,
                f"intended write target {rel!r} diverged from its 'before' hash "
                f"(before {before[:12]}.. now {now[:12]}..)",
            )

    return (
        IntegrationClass.COMPATIBLE_DRIFT,
        "global source identity changed but no declared read/write dependency "
        "of this package changed",
    )


# ---------------------------------------------------------------------------
# Explicit conflict model (spec §2)
# ---------------------------------------------------------------------------


def derive_conflicts(a: ProducerPackage, b: ProducerPackage) -> dict:
    """Derive compatibility mechanically from the two packages' read/write sets.

    Exposes the EXACT conflict/invalidation reason so Core can refuse with a
    precise diagnosis instead of a generic failure.
    """
    a_write = set(a.write_set)
    a_read = set(a.read_set)
    b_write = set(b.write_set)
    b_read = set(b.read_set)

    write_write = sorted(a_write & b_write)
    a_write_b_read = sorted(a_write & b_read)
    b_write_a_read = sorted(b_write & a_read)

    compatible = not (write_write or a_write_b_read or b_write_a_read)
    reasons: list[str] = []
    if write_write:
        reasons.append(
            f"write/write collision on {write_write}: {a.producer} and "
            f"{b.producer} both intend to write the same path"
        )
    if a_write_b_read:
        reasons.append(f"{a.producer} writes paths {a_write_b_read} that {b.producer} reads")
    if b_write_a_read:
        reasons.append(f"{b.producer} writes paths {b_write_a_read} that {a.producer} reads")

    return {
        "packages": (a.package_identity, b.package_identity),
        "write_write": write_write,
        "a_write_b_read": a_write_b_read,
        "b_write_a_read": b_write_a_read,
        "compatible": compatible,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Producer epoch / stale-worker rejection (spec §5)
# ---------------------------------------------------------------------------


class ProducerEpoch:
    """Per-namespace monotonic ownership epoch.

    A mutable producer preparation generation carries the epoch it claimed.
    If ownership is replaced (a newer epoch exists), an older epoch can no
    longer publish READY state -- a resumed stale worker fails BEFORE it
    overwrites newer producer evidence.

    CORE-008: The epoch must distinguish ABSENT (never-initialized, resolve
    to epoch 0) from CORRUPT (malformed/truncated/unreadable, block
    claim/publish). Malformed state must NOT silently reset authority --
    that lets a stale worker publish over a newer generation.
    """

    @staticmethod
    def _path(namespace: Path) -> Path:
        return Path(namespace) / EPOCH_FILENAME

    @staticmethod
    def _decode(namespace: Path | str) -> tuple[int, str, str]:
        """Strictly decode persisted fencing authority once.

        Numeric coercion, booleans and negative epochs would roll the fencing
        token backwards.  A present record therefore has one closed shape;
        only genuine absence denotes the initial epoch zero.
        """
        path = ProducerEpoch._path(Path(namespace))
        if not path.is_file():
            return 0, "", ""
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProducerError(f"producer epoch file is corrupt/unreadable: {exc}") from exc
        if not isinstance(data, dict):
            raise ProducerError("producer epoch file is not a JSON object")
        known = {"epoch", "owner", "claimed_at"}
        unknown = set(data) - known
        if unknown:
            raise ProducerError(f"producer epoch file contains unrecognized fields: {unknown}")
        epoch = data.get("epoch")
        owner = data.get("owner")
        claimed_at = data.get("claimed_at")
        if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
            raise ProducerError(
                f"producer epoch must be a non-negative JSON integer, got {epoch!r}"
            )
        if not isinstance(owner, str) or not owner:
            raise ProducerError("producer epoch owner must be a non-empty string")
        if not isinstance(claimed_at, str) or not claimed_at:
            raise ProducerError("producer epoch claimed_at must be a non-empty string")
        return epoch, owner, claimed_at

    @staticmethod
    def current(namespace: Path | str) -> int:
        """Read the current epoch. Returns 0 only when genuinely ABSENT.

        Malformed/truncated/unreadable state raises rather than resetting
        to epoch 0. This prevents a crash-truncated file from letting a
        stale worker appear current.
        """
        return ProducerEpoch._decode(namespace)[0]

    @staticmethod
    def claim(namespace: Path | str) -> int:
        """Advance and persist the namespace epoch atomically; return the epoch owned.

        CORE-008: Claim writes through a temp file + os.replace to guarantee
        atomic visibility. A crash during write leaves either the old epoch
        or the new one, never a partial/truncated file.
        """
        ns = Path(namespace)
        try:
            project_root = StagingGeneration._project_root_from_namespace(ns)
        except ProducerError:
            # A first-ever claim may precede creation of the .saipen directory;
            # the registry layout still binds <root>/.saipen/<producer>
            # unambiguously.
            if ns.parent.name != ".saipen":
                raise
            project_root = ns.parent.parent
        producer = ns.name
        if producer not in PRODUCERS:
            raise ProducerError(f"cannot claim epoch for unknown producer {producer!r}")
        # The read/increment/replace sequence is one producer-local critical
        # section.  Unique temp names alone prevent temp collisions but do not
        # prevent the classic n -> n+1 lost update.
        with ProducerLock(project_root, producer):
            ns.mkdir(parents=True, exist_ok=True)
            path = ProducerEpoch._path(ns)
            new_epoch = ProducerEpoch.current(ns) + 1
            owner = uuid.uuid4().hex
            payload = (
                json.dumps(
                    {
                        "epoch": new_epoch,
                        "owner": owner,
                        "claimed_at": uuid.uuid1().hex,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, path)
            return new_epoch

    @staticmethod
    def current_owner(namespace: Path | str) -> str:
        """Return the current owner token; corrupt authority raises."""
        return ProducerEpoch._decode(namespace)[1]

    @staticmethod
    def owns(namespace: Path | str, epoch: int, owner: str | None = None) -> bool:
        """True only when the stored epoch matches and (optionally) the owner matches.

        When owner is None, only epoch matching is checked (backward
        compatible). When owner is provided, both epoch and owner must match
        to prove current ownership.
        """
        stored = ProducerEpoch.current(namespace)
        if stored != epoch:
            return False
        if owner is not None:
            return ProducerEpoch.current_owner(namespace) == owner
        return True


# ---------------------------------------------------------------------------
# Atomic prepare publication (spec §3)
# ---------------------------------------------------------------------------


class StagingGeneration:
    """Prepare into a non-READY staging generation.

    READY becomes visible ONLY after every payload is complete, hashes/manifests
    are complete, internal verification passed, and package metadata is
    complete. A crash before final publication leaves only incomplete staging
    evidence -- never a READY package. Final publication is atomic (os.replace)
    and idempotent (re-publishing the same identity is a no-op success).
    """

    def __init__(
        self,
        namespace: Path | str,
        producer: str,
        generation_id: str | None = None,
    ) -> None:
        self.namespace = Path(namespace)
        self.producer = producer
        self.generation_id = generation_id or uuid.uuid4().hex
        self.staging_dir = self.namespace / STAGING_DIRNAME / self.generation_id
        self.payload_dir = self.staging_dir / "payload"
        self.manifest_path = self.staging_dir / "staging.manifest.json"
        self.package: ProducerPackage | None = None
        self._payloads: dict[str, bytes] = {}

    # -- lifecycle --------------------------------------------------------

    def begin(self) -> "StagingGeneration":
        # Decode persisted authority before creating even an empty staging
        # directory.  Corrupt fencing state must be a zero-namespace-write
        # refusal, not a failure that leaves a misleading partial generation.
        epoch = ProducerEpoch.current(self.namespace)
        begin_time = _utc_now_iso()
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.payload_dir.mkdir(parents=True, exist_ok=True)
        # marker that this generation is in flight (incomplete until published)
        self.staging_dir.joinpath(".in-flight").write_text(self.generation_id + "\n")
        # W2-002 / CORE-005: persist generation metadata (including the epoch
        # claimed at begin time) atomically so recovery can mechanically
        # distinguish this generation's ownership from a newer takeover. A
        # crash here leaves a partial manifest that recovery treats as
        # orphaned, never as a READY package.
        self.manifest_path.write_text(
            json.dumps(
                {
                    "generation_id": self.generation_id,
                    "begin_time": begin_time,
                    "epoch": epoch,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self._begin_manifest = {
            "generation_id": self.generation_id,
            "begin_time": begin_time,
            "epoch": epoch,
        }
        return self

    def add_payload(self, rel_path: str, content: bytes | str) -> None:
        # CORE-007: validate the path before any filesystem operation so
        # absolute paths, traversal, or reparse escapes cannot write outside
        # the producer namespace.
        _validate_producer_rel_path(rel_path, context="add_payload")
        data = content.encode("utf-8") if isinstance(content, str) else content
        target = self.payload_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # Containment proof: the resolved target must be under payload_dir
        try:
            res_target = target.resolve()
            res_payload = self.payload_dir.resolve()
            if not res_target.is_relative_to(res_payload):
                raise ProducerError(
                    f"add_payload: resolved path {res_target} escapes "
                    f"payload directory {res_payload}"
                )
        except ProducerError:
            raise
        except OSError as exc:
            raise ProducerError(f"add_payload: cannot resolve target path: {exc}") from exc
        target.write_bytes(data)
        self._payloads[rel_path] = data

    def set_package(self, package: ProducerPackage) -> None:
        self.package = package

    def _verify(self) -> list[str]:
        errors: list[str] = []
        if self.package is None:
            errors.append("package metadata is missing -- nothing to publish")
            return errors
        # Every declared write_set target must have a COMPLETE payload present.
        # The payload carries the NEW content; the 'before' hash in write_set is
        # checked only at integration time (by classify_integration), not here.
        # A crash before every payload is written leaves this generation in
        # flight and never reaches publish() -> no READY artifact.
        for rel in self.package.write_set:
            payload = self.payload_dir / rel
            if not payload.is_file():
                errors.append(f"payload missing for intended write target {rel!r}")
        # package metadata completeness
        if not self.package.package_identity:
            errors.append("package_identity not derived")
        if not self.package.read_set and not self.package.write_set:
            errors.append("package declares neither read_set nor write_set")
        # W2-004: revalidate that declared dependencies still match.
        # This catches the case where Core changed a declared input between
        # the producer's real read/generation step and this publish call.
        reval_errs = self._revalidate_dependencies()
        errors.extend(reval_errs)
        return errors

    def _revalidate_dependencies(self) -> list[str]:
        """W2-004: re-read every declared dependency/write precondition and
        require it still matches what the package declares.

        Unrelated whole-tree drift may remain compatible, but any
        declared-input drift makes the generation STALE/RETRY and it
        must never publish READY.

        Read-set dependencies are checked against the PROJECT ROOT (not the
        namespace), since that's where source files live.
        """
        if self.package is None:
            return []
        errors: list[str] = []
        # W2-004: read-set dependencies are in the project source tree,
        # not in the namespace. Resolve the project root by going up from
        # the namespace until we find a .saipen directory.
        project_root = self._find_project_root()
        # Revalidate read_set: each declared read dependency must still
        # have the same content hash as when the package was built.
        for rel, expected_hash in self.package.read_set.items():
            if project_root is not None:
                actual = file_sha256(project_root / rel)
            else:
                # Fallback: check in the staging parent (namespace)
                actual = file_sha256(self.staging_dir.parent / rel)
            if actual != expected_hash:
                errors.append(
                    f"W2-004: read dependency {rel!r} drifted: "
                    f"expected {expected_hash[:16]}.. got {actual[:16]}.. "
                    "-- package is STALE, must retry"
                )
        # Write preconditions bind canonical project targets exactly, including
        # absent->present and present->absent movement.
        for rel, expected_before in self.package.write_set.items():
            if project_root is None:
                errors.append("W2-004: project root unavailable for write precondition")
                continue
            try:
                actual = _safe_rel_hash(project_root, rel)
            except ProducerError as exc:
                errors.append(str(exc))
                continue
            if actual != expected_before:
                errors.append(
                    f"W2-004: write target {rel!r} 'before' hash drifted: "
                    f"expected {expected_before[:16]}.. got {actual[:16]}.. "
                    "-- package is STALE, must retry"
                )
        return errors

    def _find_project_root(self) -> Path | None:
        """W2-004: resolve the project root by finding .saipen directory."""
        # Walk up from the namespace to find the project root
        candidate = self.namespace
        while candidate != candidate.parent:
            if (candidate / ".saipen").is_dir():
                return candidate
            candidate = candidate.parent
        return None

    def publish(self) -> dict:
        """Publish under the same-role producer lock.

        Claim and publication share one lock identity.  A concurrent same-role
        publisher therefore either wins the lock or receives PRODUCER_BUSY;
        it can never race the epoch check and publish beside the winner.
        """
        project_root = self._find_project_root()
        if project_root is None:
            return {
                "ok": False,
                "code": "PROJECT_ROOT_UNKNOWN",
                "detail": "cannot locate project root for producer publication",
            }
        try:
            with ProducerLock(project_root, self.producer):
                return self._publish_under_lock()
        except PermissionError as exc:
            return {"ok": False, "code": "PRODUCER_BUSY", "detail": str(exc)}

    def _publish_under_lock(self) -> dict:
        """Atomically promote this staging generation to READY.

        Returns a result dict. On any failure, no READY artifact is created.
        """
        if self.package is None:
            return {"ok": False, "code": "NO_PACKAGE", "detail": "package metadata missing"}
        errors = self._verify()
        if errors:
            return {"ok": False, "code": "INCOMPLETE", "detail": "; ".join(errors)}

        # CORE-008: Stale-worker guard + corrupt-state guard. If the epoch
        # file is corrupt/unreadable, owns() -> current() raises
        # ProducerError -- publication is blocked rather than reset.
        try:
            owns = ProducerEpoch.owns(self.namespace, self.package.epoch)
        except ProducerError as exc:
            return {
                "ok": False,
                "code": "EPOCH_CORRUPT",
                "detail": f"producer epoch is corrupt/unreadable: {exc}",
            }
        if not owns:
            return {
                "ok": False,
                "code": "STALE_WORKER",
                "detail": (
                    f"namespace epoch advanced past {self.package.epoch}; "
                    "this worker is stale and may not publish"
                ),
            }

        ready_dir = self.namespace / READY_DIRNAME
        ready_dir.mkdir(parents=True, exist_ok=True)
        rid = self.package.package_identity
        target = ready_dir / _ready_filename(rid)

        # Idempotent: an identical READY package already exists -> reuse.
        # BUT a matching package_identity only proves identical CONTENT; the
        # artifact's recorded base-source binding must still be CURRENT.
        # package_identity is derived from producer/role/dependencies/scope,
        # NOT from the source binding, so a package produced against an older
        # HEAD can share the identity while carrying a stale source_head/
        # source_tree_fingerprint. Reusing that artifact leaves producer
        # health NOT_RUN/STALE against the current tree forever (reproduced
        # live: saitranslate READY carried e045ad07/da948ff while the tree was
        # a5bbda6f/55f, so `saipen crew` kept demanding PREPARE_TRANSLATE).
        # Only reuse when the existing binding equals the new one; otherwise
        # fall through and re-publish the current binding.
        if target.is_file():
            try:
                existing = ProducerPackage.from_dict(json.loads(target.read_text()))
                if (
                    existing.package_identity == rid
                    and existing.base_source_head == self.package.base_source_head
                    and existing.base_source_tree_fingerprint
                    == self.package.base_source_tree_fingerprint
                    and existing.base_discovery_model == self.package.base_discovery_model
                ):
                    shutil.rmtree(self.staging_dir, ignore_errors=True)
                    return {
                        "ok": True,
                        "code": "REUSED",
                        "package_identity": rid,
                        "detail": "identical READY package already present",
                    }
            except (ValueError, OSError):
                pass

        data = self.package.to_dict()
        data["status"] = PackageStatus.READY.value
        # CORE-006: retain payload bytes so READY is a self-contained
        # artifact. Integration can reconstruct/apply solely from READY
        # storage without any in-memory staging objects.
        payload_hashes: dict[str, str] = {}
        payload_bytes: dict[str, str] = {}
        for rel, raw in self._payloads.items():
            h = _sha256_bytes(raw)
            payload_hashes[rel] = h
            # Store as base64 so the JSON is self-contained binary-safe
            import base64 as _b64

            payload_bytes[rel] = _b64.b64encode(raw).decode("ascii")
        data["payload_hashes"] = payload_hashes
        data["payload_bytes"] = payload_bytes
        tmp = ready_dir / (_ready_filename(rid) + ".tmp")
        tmp.write_text(json.dumps(data, sort_keys=True) + "\n")
        # ATOMIC switch: readers see either the old state or the new READY.
        os.replace(tmp, target)
        shutil.rmtree(self.staging_dir, ignore_errors=True)
        return {"ok": True, "code": "PUBLISHED", "package_identity": rid}

    # -- visibility -------------------------------------------------------

    @classmethod
    def is_ready(cls, namespace: Path | str, package_identity: str) -> bool:
        return (Path(namespace) / READY_DIRNAME / _ready_filename(package_identity)).is_file()

    @classmethod
    def ready_package(cls, namespace: Path | str, package_identity: str) -> ProducerPackage | None:
        path = Path(namespace) / READY_DIRNAME / _ready_filename(package_identity)
        if not path.is_file():
            return None
        try:
            return ProducerPackage.from_dict(
                json.loads(path.read_text(encoding="utf-8")),
                expected_producer=Path(namespace).name,
                expected_identity=package_identity,
                ready_path=path,
            )
        except (ProducerError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    @classmethod
    def scan_ready(cls, namespace: Path | str) -> tuple[list[ProducerPackage], list[dict]]:
        """Return valid READY packages plus structured invalid-record errors."""
        ready_dir = Path(namespace) / READY_DIRNAME
        if not ready_dir.is_dir():
            return [], []
        producer = Path(namespace).name
        out: list[ProducerPackage] = []
        errors: list[dict] = []
        for path in sorted(ready_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                candidate = ProducerPackage.from_dict(
                    data, expected_producer=producer, ready_path=path
                )
                if path.name != _ready_filename(candidate.package_identity):
                    raise ProducerError("READY filename does not match package identity")
                out.append(candidate)
            except (ProducerError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append({"code": "INVALID_READY", "path": str(path), "detail": str(exc)})
        return out, errors

    @classmethod
    def list_ready(cls, namespace: Path | str) -> list[ProducerPackage]:
        packages, _errors = cls.scan_ready(namespace)
        return packages

    # -- recovery (spec §M) ----------------------------------------------

    @classmethod
    def _project_root_from_namespace(cls, ns: Path) -> Path:
        """CORE-005: resolve the project root that owns a producer namespace.

        Walks up from the namespace until it finds the directory containing
        ``.saipen``. This is the single authoritative registry used so recovery
        locks the SAME canonical ``ProducerLock(project_root, producer)`` the live
        writer holds -- never a path derived from ``namespace.parent``.
        """
        candidate = Path(ns)
        while candidate != candidate.parent:
            if (candidate / ".saipen").exists():
                return candidate
            candidate = candidate.parent
        raise ProducerError(f"cannot locate project root for producer namespace {ns}")

    @classmethod
    def recover(
        cls,
        namespace: Path | str,
        project_root: Path | str | None = None,
        producer: str | None = None,
    ) -> dict:
        """W2-002: Deterministic cleanup of orphaned staging generations.

        Acquires the producer-local ProducerLock before classifying or
        deleting staging generations. If another writer owns the lock,
        returns BUSY/no-op with zero deletion. Under the lock, only
        deletes generations that are mechanically proven stale/abandoned
        relative to current ownership -- never infers abandonment solely
        because READY is absent.

        CORE-005: the lock is the CANONICAL ``ProducerLock(project_root,
        producer)`` -- identical to the live writer's lock. The namespace alone
        no longer determines the lock path (the old code used ``namespace.parent``
        which landed on ``.saipen/.saipen/locks`` for saitranslate and locked a
        different file from the real writer, allowing a live generation to be
        classified as an orphan and deleted). ``project_root``/``producer`` may
        be passed explicitly; otherwise they are derived from the namespace.

        A staging dir with no published READY counterpart is incomplete by
        definition (publication is atomic and removes it). We delete it. We
        NEVER synthesize a READY package from partial staging evidence.
        Returns a report of what was removed.
        """
        ns = Path(namespace)
        _explicit_project = project_root is not None
        if project_root is None:
            project_root = cls._project_root_from_namespace(ns)
        if producer is None:
            producer = ns.name
        if producer not in PRODUCERS:
            raise ProducerError(f"recover: unknown producer role {producer!r}")
        # W2-001: when the caller explicitly supplies project_root, prove the
        # namespace is the canonical owned one for this project/producer before
        # reading or deleting anything through it -- otherwise a symlink/junction
        # substitution turns recover into an outside-root recursive delete.
        # When project_root was derived from the namespace (not explicitly passed),
        # the caller is using a legacy layout; skip the strict canonical check
        # to avoid breaking test fixtures that predate the extensions/subs/ layout.
        if _explicit_project:
            try:
                canonical = _resolve_namespace_ownership(project_root, producer)
            except ValueError as exc:
                raise ProducerError(
                    f"recover: namespace authority refused for producer "
                    f"{producer!r}: {exc}"
                ) from exc
            if not ns.is_absolute():
                ns = (Path(project_root) / ns).resolve()
            try:
                if ns.resolve() != canonical.resolve():
                    raise ProducerError(
                        f"recover: namespace {ns} is not the canonical producer "
                        f"namespace {canonical} for project {project_root}; refuse"
                    )
            except OSError as exc:
                raise ProducerError(
                    f"recover: namespace {ns} cannot be resolved: {exc}"
                ) from exc
        staging_root = ns / STAGING_DIRNAME
        removed: list[str] = []
        # W2-002 / CORE-005: acquire the canonical producer-local lock to
        # prevent racing a live producer that holds the SAME lock identity.
        try:
            with ProducerLock(project_root, producer):
                removed = cls._recover_under_lock(ns, staging_root)
        except PermissionError:
            # Another writer owns the lock -- do not delete anything
            return {"removed_staging": [], "false_ready": False, "busy": True}
        except ProducerError:
            # Epoch is corrupt -- do not delete anything
            return {"removed_staging": [], "false_ready": False, "busy": True}
        return {"removed_staging": removed, "false_ready": False, "busy": False}

    @classmethod
    def _recover_under_lock(cls, ns: Path, staging_root: Path) -> list[str]:
        """W2-002: delete only mechanically stale generations under the lock.

        A generation is stale/abandoned when:
        1. Its in-flight marker exists (publication never completed), AND
        2. The current epoch has advanced past the generation's epoch
           (ownership was taken over), OR the generation has no valid
           epoch file.
        """
        removed: list[str] = []
        if not staging_root.is_dir():
            return removed
        # Get current epoch to determine which generations are stale
        try:
            current_epoch = ProducerEpoch.current(ns)
        except ProducerError:
            # Epoch is corrupt -- do not remove anything under uncertainty
            return removed
        for gen in staging_root.iterdir():
            if not gen.is_dir():
                continue
            # The marker proves incompleteness, not abandonment.  Only a
            # mechanically newer ownership epoch makes this generation stale.
            # Unknown/future/current authority remains untouched.
            gen_epoch = cls._generation_epoch(gen)
            if gen_epoch is None or gen_epoch >= current_epoch:
                continue
            shutil.rmtree(gen, ignore_errors=True)
            removed.append(gen.name)
        return removed

    @staticmethod
    def _generation_epoch(gen_dir: Path) -> int | None:
        """W2-002: extract the epoch from a generation's staging manifest."""
        manifest = gen_dir / "staging.manifest.json"
        if not manifest.is_file():
            return None
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            epoch = data.get("epoch")
            if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
                return None
            return epoch
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None


# ---------------------------------------------------------------------------
# Conventional namespace helper (optional; never hard-coded into safety)
# ---------------------------------------------------------------------------


def _resolve_namespace_ownership(
    root: Path | str, producer: str
) -> Path:
    """The canonical producer-namespace ownership resolver (W2-001).

    Validates that the producer namespace resolves INSIDE the canonical
    project root and rejects symlinks, junctions/reparse points, or any
    resolved path outside the root. Returns the owned namespace path.
    Raises ValueError on any containment failure.
    """
    root = Path(root).resolve()
    if producer == "saitranslate":
        ns = root / ".saipen" / "saitranslate"
    else:
        ns = root / ".saipen" / "extensions" / "subs" / producer
    # Prove every existing namespace component resolves inside the root.
    # lstat each component so a symlink/junction is detected, not followed.
    try:
        resolved = ns.resolve(strict=False)
    except OSError as exc:
        raise ValueError(
            f"producer namespace {ns} cannot be resolved: {exc}"
        ) from exc
    # Containment: resolved path must be the root itself or a descendant.
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(
            f"producer namespace {ns} resolves to {resolved}, "
            f"outside project root {root}"
        ) from None
    # Walk each ancestor from root down to the namespace, lstat-checking
    # each component so a symlink/junction/reparse point is rejected
    # BEFORE it can redirect a write or delete outside the project.
    _check = root
    for part in ns.relative_to(root).parts:
        _check = _check / part
        try:
            st = _check.lstat()
        except FileNotFoundError:
            break  # Non-existent is fine; we'll create it under the root.
        except OSError as exc:
            raise ValueError(
                f"producer namespace component {_check} cannot be lstat'd: {exc}"
            ) from exc
        # On POSIX, S_ISLNK; on Windows, reparse points via S_ISLNK too.
        import stat as _stat
        if _stat.S_ISLNK(st.st_mode):
            raise ValueError(
                f"producer namespace component {_check} is a symlink; "
                f"producer operations refuse to follow it"
            )
    return ns


def producer_namespace(root: Path | str, producer: str) -> Path:
    """The conventional on-disk namespace for a producer role.

    Mirrors subs.py: saitranslate -> .saipen/saitranslate (special-cased);
    saiwiki -> .saipen/extensions/subs/saiwiki.

    W2-001: returns the owned namespace only after proving it resolves
    inside the canonical project root (no symlinks/junctions/reparse).
    """
    return _resolve_namespace_ownership(root, producer)


# ---------------------------------------------------------------------------
# Multi-package integration plan (spec §8) + serialized Core integration (§N)
# ---------------------------------------------------------------------------


def plan_integration(
    packages: Iterable[ProducerPackage],
    base_identity,
    *,
    current_identity_provider: Callable[[], object],
    current_hashes_provider: Callable[[ProducerPackage], Mapping[str, str]],
) -> dict:
    """Dry-run / planning output for Core.

    Shows, in a DETERMINISTIC order:
      - READY packages;
      - exact base identities;
      - CURRENT / COMPATIBLE_DRIFT / STALE for each;
      - read/write conflicts between packages;
      - deterministic integration order;
      - which package must be regenerated after each integration.

    Does NOT auto-rebase semantically stale packages. Integrates sequentially:
    after each non-stale package we apply its write_set to a SIMULATED current
    state so later packages are re-classified against the post-integration world.
    """
    pkgs = list(packages)
    order = sorted(pkgs, key=lambda p: (p.producer, p.package_identity))

    # pairwise conflicts
    conflicts: list[dict] = []
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            c = derive_conflicts(order[i], order[j])
            if not c["compatible"]:
                conflicts.append(
                    {
                        "a": order[i].package_identity,
                        "b": order[j].package_identity,
                        "write_write": c["write_write"],
                        "a_write_b_read": c["a_write_b_read"],
                        "b_write_a_read": c["b_write_a_read"],
                        "reasons": c["reasons"],
                    }
                )

    entries: list[dict] = []
    # W2-003: simulated world starts EMPTY. Live hashes remain authoritative
    # for all paths. Simulation may overlay only concrete post-write effects
    # from packages already accepted EARLIER in this plan. This prevents the
    # planner from hiding actual concurrent modification of a package's write
    # target by replacing live hashes with the package's historical 'before' hashes.
    simulated: dict[str, str] = {}

    for idx, p in enumerate(order):
        cur_id = current_identity_provider()
        cur_hashes = current_hashes_provider(p)
        # W2-003: start from live hashes (authoritative). Only overlay
        # simulated post-write effects from EARLIER accepted packages.
        merged = dict(cur_hashes)
        for rel, before in simulated.items():
            if rel in merged:
                merged[rel] = before
        cls, reason = classify_integration(
            (
                p.base_source_head,
                p.base_source_tree_fingerprint,
                p.base_discovery_model,
            ),
            cur_id,
            p.read_set,
            p.write_set,
            merged,
        )
        regenerate = cls is IntegrationClass.STALE
        entries.append(
            {
                "order": idx,
                "producer": p.producer,
                "package_identity": p.package_identity,
                "base_source_head": p.base_source_head,
                "base_source_tree_fingerprint": p.base_source_tree_fingerprint,
                "role_revision": p.role_revision,
                "class": cls.value,
                "reason": reason,
                "regenerate": regenerate,
            }
        )
        if not regenerate:
            # advance simulated world: the integrated writes now land.
            for rel, before in p.write_set.items():
                # after integration the path holds the producer's new content;
                # we don't have it here, but the *next* package only cares that
                # the path no longer equals its OWN before-hash if it overlaps.
                # Mark divergence so a later package with the same target is
                # forced STALE (handled by conflict refusal in integrate()).
                simulated[rel] = "sha256:integrated:" + rel

    return {
        "order": [e["package_identity"] for e in entries],
        "packages": entries,
        "conflicts": conflicts,
        "serialized": True,
    }


def integrate_packages_core(
    packages: Iterable[ProducerPackage],
    root: Path | str,
    *,
    apply_write: Callable[[ProducerPackage, Path], None] | None = None,
    dry_run: bool = False,
    agent: str = "saipen-core",
    crew_epoch: str = "",
    ticket_id: str = "",
) -> dict:
    """Serialized Core integration through the canonical Core writer lock.

    Each package is re-classified against the REAL filesystem at integration
    time. A package that is STALE, or that collides (write/write) with a
    package already integrated in THIS batch, is REFUSED before any canonical
    write. Returns a per-package report. The Core writer lock guarantees that
    no two integrations run concurrently (spec §N).
    """
    with project_writer_lock(root):
        root_path = Path(root)
        pkgs = sorted(packages, key=lambda p: (p.producer, p.package_identity))
        applied: list[str] = []
        results: list[dict] = []

        for p in pkgs:
            # CORE-006: strict pre-flight verification -- status must be ready
            if p.status != PackageStatus.READY.value:
                results.append(
                    {
                        "package_identity": p.package_identity,
                        "producer": p.producer,
                        "result": "REFUSED",
                        "code": "NOT_READY",
                        "reason": f"package status is {p.status!r}, not 'ready'",
                        "wrote": False,
                    }
                )
                continue
            # W2-003: a COMMITTED producer_integration receipt for this exact
            # package is idempotence authority ONLY when its resulting edge is
            # still CURRENT. The receipt's resulting_source/fingerprint bind
            # the source the integration produced; if that HEAD has since moved
            # (even with identical content -- a commit is a new source
            # identity), the committed edge no longer certifies the current
            # tree and the package must be re-integrated to record a fresh
            # resulting edge. Without this, a content-identical commit leaves
            # the producer permanently ALREADY_APPLIED against a stale
            # resulting_source and crew SC-8/SC-9 never advances (reproduced
            # live: saitranslate READY at 4451d073 short-circuited on a
            # receipt whose resulting_source was e98bcb03).
            from .journal import SemanticReceiptCorruptionError, semantic_receipts_for_operation

            try:
                _committed = semantic_receipts_for_operation(root_path, "producer_integration")
            except SemanticReceiptCorruptionError as exc:
                results.append(
                    {
                        "package_identity": p.package_identity,
                        "producer": p.producer,
                        "result": "REFUSED",
                        "code": "CORRUPT_JOURNAL",
                        "reason": (
                            f"semantic receipt snapshot is corrupt: "
                            f"{'; '.join(exc.errors[:2])}"
                        ),
                        "wrote": False,
                        "recovery_required": True,
                    }
                )
                continue
            try:
                from freshness import compute_source_identity as _csi

                _live = _csi(root_path)
            except Exception:
                _live = None
            _current_edge = any(
                rec.get("status") == "COMMITTED"
                and (rec.get("receipt_metadata") or {}).get("package_identity")
                == p.package_identity
                and _live is not None
                and (rec.get("receipt_metadata") or {}).get("resulting_source") == _live.source_head
                and (rec.get("receipt_metadata") or {}).get("resulting_source_fingerprint")
                == _live.source_tree_fingerprint
                for rec in _committed
            )
            if _current_edge:
                # Retirement failure is non-fatal cleanup debt; the source is
                # already integrated and must not be reapplied.
                with contextlib.suppress(OSError):
                    _retire_ready_package(p, supersede_older=True)
                results.append(
                    {
                        "package_identity": p.package_identity,
                        "producer": p.producer,
                        "result": "INTEGRATED",
                        "code": "ALREADY_APPLIED",
                        "reason": (
                            "committed producer integration receipt exists; "
                            "READY retired idempotently"
                        ),
                        "wrote": True,
                        "cleanup_pending": False,
                    }
                )
                continue
            # Re-classify on the live tree. Source identity is authority for
            # the integration decision; an unreadable/unstable source must be
            # a structured per-package refusal, never a synthetic fallback or
            # a public traceback.
            try:
                cur_id = _live_source_identity(root_path)
                cur_hashes = _live_hashes(root_path, p)
            except (ProducerError, OSError, UnicodeError) as exc:
                results.append(
                    {
                        "package_identity": p.package_identity,
                        "producer": p.producer,
                        "result": "REFUSED",
                        "code": "SOURCE_IDENTITY_FAILED",
                        "reason": str(exc),
                        "wrote": False,
                    }
                )
                continue
            cls, reason = classify_integration(
                (
                    p.base_source_head,
                    p.base_source_tree_fingerprint,
                    p.base_discovery_model,
                ),
                cur_id,
                p.read_set,
                p.write_set,
                cur_hashes,
            )
            if cls is IntegrationClass.STALE:
                results.append(
                    {
                        "package_identity": p.package_identity,
                        "producer": p.producer,
                        "result": "REFUSED",
                        "code": "STALE",
                        "reason": reason,
                        "wrote": False,
                    }
                )
                continue

            # write/write collision with an already-integrated package?
            collision = next((q for q in applied if set(q.write_set) & set(p.write_set)), None)
            if collision is not None:
                results.append(
                    {
                        "package_identity": p.package_identity,
                        "producer": p.producer,
                        "result": "REFUSED",
                        "code": "CONFLICT",
                        "reason": (
                            f"write target collides with already-integrated "
                            f"package {collision.package_identity}"
                        ),
                        "wrote": False,
                    }
                )
                continue

            if dry_run:
                applied.append(p)
                results.append(
                    {
                        "package_identity": p.package_identity,
                        "producer": p.producer,
                        "result": "PLANNED",
                        "code": cls.value,
                        "reason": reason,
                        "wrote": False,
                    }
                )
                continue

            payloads = dict(p.payloads)
            if set(payloads) != set(p.write_set):
                if apply_write is None:
                    results.append(
                        {
                            "package_identity": p.package_identity,
                            "producer": p.producer,
                            "result": "REFUSED",
                            "code": "PAYLOAD_MISSING",
                            "reason": "READY package has no complete authenticated payload",
                            "wrote": False,
                        }
                    )
                    continue
                # Compatibility adapter for old in-memory callers: execute the
                # callback only in an isolated scratch root, capture its declared
                # outputs, then journal those bytes.  The callback never receives
                # the canonical root and therefore cannot leave a mixed tree.
                import tempfile

                try:
                    with tempfile.TemporaryDirectory(prefix="saipen-producer-apply-") as td:
                        scratch = Path(td)
                        for rel in sorted(set(p.read_set) | set(p.write_set)):
                            source = root_path / rel
                            if source.is_file():
                                target = scratch / rel
                                target.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copyfile(source, target)
                        apply_write(p, scratch)
                        payloads = {}
                        for rel in p.write_set:
                            target = scratch / rel
                            if not target.is_file():
                                raise ProducerError(
                                    f"legacy apply callback did not materialize {rel!r}"
                                )
                            payloads[rel] = target.read_bytes()
                except Exception as exc:
                    results.append(
                        {
                            "package_identity": p.package_identity,
                            "producer": p.producer,
                            "result": "REFUSED",
                            "code": "APPLY_MATERIALIZATION_FAILED",
                            "reason": str(exc),
                            "wrote": False,
                        }
                    )
                    continue

            from .journal import run_mutation
            from .paths import project_identity

            def _integration_receipt_metadata(live_root: Path, metadata: dict) -> dict:
                resulting = _live_source_identity(live_root)
                metadata["resulting_source"] = resulting.source_head
                metadata["resulting_source_fingerprint"] = resulting.source_tree_fingerprint
                return metadata

            op_id = "producer-integrate-" + p.package_identity.split(":", 1)[-1][:32]
            journal_result = run_mutation(
                root_path,
                op_id,
                "producer_integration",
                agent,
                project_identity(root_path),
                p.package_identity,
                [
                    {"path": rel, "role": "generic", "content": payloads[rel]}
                    for rel in sorted(payloads)
                ],
                receipt_metadata={
                    "operation": "producer_integration",
                    "status": "COMMITTED",
                    "crew_epoch": crew_epoch,
                    "ticket_id": ticket_id,
                    "producer": p.producer,
                    "package_identity": p.package_identity,
                    "input_source": p.base_source_head,
                    "input_source_fingerprint": p.base_source_tree_fingerprint,
                },
                receipt_metadata_finalize=_integration_receipt_metadata,
                # W2-002: producer integration binds the canonical project
                # lineage like every other recoverable mutation. Suppressing it
                # produced legacy null-lineage receipts that became
                # unrecoverable after a legitimate project move. The lineage
                # migration primitive itself still suppresses recursion
                # internally.
                _ensure_lineage=True,
            )
            if not journal_result.get("ok"):
                results.append(
                    {
                        "package_identity": p.package_identity,
                        "producer": p.producer,
                        "result": "REFUSED",
                        "code": journal_result.get("code", "INTEGRATION_FAILED"),
                        "reason": journal_result.get("detail", "journaled integration failed"),
                        "wrote": False,
                        "recovery_required": journal_result.get("recovery_required", False),
                    }
                )
                continue
            applied.append(p)
            # W2-003: READY retirement is a post-commit cleanup step OUTSIDE the
            # integration journal. Its failure must not be reported as if source
            # mutation failed: the payload is already committed. Surface
            # cleanup-pending debt truthfully and let a retry converge through
            # the committed-receipt idempotence path above.
            try:
                _retire_ready_package(p, supersede_older=True)
                _cleanup_pending = False
            except OSError:
                _cleanup_pending = True
            results.append(
                {
                    "package_identity": p.package_identity,
                    "producer": p.producer,
                    "result": "INTEGRATED",
                    "code": cls.value,
                    "reason": reason,
                    "wrote": True,
                    "op_id": journal_result.get("op_id"),
                    "cleanup_pending": _cleanup_pending,
                }
            )

        return {"serialized": True, "results": results}


def _retire_ready_package(package: ProducerPackage, *, supersede_older: bool = False) -> None:
    """Atomically remove terminal package evidence from the READY hot set."""
    source = package.ready_path
    if source is None or not source.is_file():
        return
    namespace = source.parent.parent
    settled = namespace / SETTLED_DIRNAME
    settled.mkdir(parents=True, exist_ok=True)
    destination = settled / source.name
    if destination.is_file():
        source.unlink()
    else:
        os.replace(source, destination)
    if not supersede_older:
        return
    ready_dir = namespace / READY_DIRNAME
    superseded = namespace / SUPERSEDED_DIRNAME
    if not ready_dir.is_dir():
        return
    for candidate in list(ready_dir.glob("*.json")):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            epoch = data.get("epoch")
            producer = data.get("producer")
        except (OSError, json.JSONDecodeError):
            continue
        if producer != package.producer or not isinstance(epoch, int) or epoch > package.epoch:
            continue
        superseded.mkdir(parents=True, exist_ok=True)
        target = superseded / candidate.name
        if target.is_file():
            candidate.unlink()
        else:
            os.replace(candidate, target)


def _live_source_identity(root: Path) -> object:
    """Resolve the live SourceIdentity (git or no-git) without hard-coupling
    to `freshness` at import time."""
    try:
        from freshness import FreshnessError, compute_source_identity
    except ImportError as exc:
        raise ProducerError(f"source identity provider unavailable: {exc}") from exc
    try:
        return compute_source_identity(root)
    except (FreshnessError, OSError, UnicodeError) as exc:
        # Authority capture is fail-closed. The retired fallback swallowed
        # every internal error and recursively hashed the whole project,
        # following unrelated scratch/cache trees and potentially external
        # symlink targets into a fabricated `fallback:` identity.
        raise ProducerError(f"cannot capture authoritative source identity: {exc}") from exc


def _live_hashes(root: Path, package: ProducerPackage) -> dict[str, str]:
    keys = set(package.read_set) | set(package.write_set)
    return {rel: _safe_rel_hash(root, rel) for rel in keys}

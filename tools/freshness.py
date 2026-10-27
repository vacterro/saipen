#!/usr/bin/env python
"""Deterministic SAIPEN package freshness primitives.

The source identity deliberately has two models:

* ``git-delta-v1`` fingerprints only the working-tree delta from ``HEAD``:
  tracked modifications/deletions/type or mode changes plus untracked,
  non-ignored files. ``HEAD`` itself binds the committed tree.
* ``no-git-tree-v1`` fingerprints the complete filesystem tree except its
  explicitly named runtime directories/files because no committed baseline
  or Git ignore engine exists. It is not presented as equivalent to Git
  discovery.

Both models exclude ``.saipen/``. Records are framed, symlinks are hashed as
link target text, and an input that cannot be classified or read is fatal.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


class FreshnessError(RuntimeError):
    """Freshness evidence could not be computed without omitting input."""


#: The width ``phases/translate.md`` mandates for a locale
#: ``source-digest`` marker. The digest it carries is a full sha256.
SHORT_DIGEST_MARKER_HEX = 16

#: T-1902: how many per-file reads inside one sampling pass may overlap. The
#: measured ceiling is shallow -- the live tree's 482 content-bearing paths
#: cost 0.188 s sequentially, 0.144 s at 4 workers, 0.131 s at 8 and 0.130 s
#: at 16 -- so eight captures almost the whole win without opening 482 file
#: handles against a V: network volume. Kept a constant so a fixture can pin
#: the sequential path and prove both paths agree byte-for-byte.
_READ_WORKERS = 8

#: A version token: three numeric components plus the bare pre-release
#: suffix this project actually ships (``1.2.3``, ``0.0.2a3``, ``0.0.2b1``).
#: The suffix belongs to the token: leaving it out made a pre-release bump
#: (``0.0.2a3`` -> ``0.0.2b1``) move the source digest, which is exactly the
#: badge bump the gate's own comment says can never move it. It stops at the
#: first non-alphanumeric character on purpose -- a greedy ``-``/``.`` tail
#: would swallow the rest of a wheel filename (``0.0.2a3-py3-none-any.whl``)
#: and hide a real content change behind a version-shaped prefix.
VERSION_TOKEN_RE = r"\d+\.\d+\.\d+[0-9A-Za-z]*"


def normalize_version_strings(text: str) -> str:
    """Replace every version token in ``text`` with the literal ``VERSION``."""
    return re.sub(VERSION_TOKEN_RE, "VERSION", text)


def source_content_digest(text: str) -> str:
    """sha256 of ``text`` with version tokens normalised out.

    This is the digest a locale ``source-digest`` marker claims, so the
    recipe lives here beside the other source-identity helpers instead of
    inline in a validator branch where a producer cannot reproduce it.
    """
    return hashlib.sha256(normalize_version_strings(text).encode("utf-8")).hexdigest()


def digest_marker_matches(marker_hex: object, want_hex: object) -> bool:
    """Does a locale ``source-digest`` marker equal the canonical digest?

    ``phases/translate.md`` mandates a ``<16 hex>`` marker while the digest
    the validator computes is a full 64-hex sha256, so an exact-width
    comparison could never be satisfied by a conformant marker: the
    ``translation-stale`` WARN was unreachable by design, and a producer that
    followed the documented contract could never clear it. Accept exactly the
    two widths the contract and the digest itself name; any other width, and
    any wrong digest, is still stale.
    """
    if not isinstance(marker_hex, str) or not isinstance(want_hex, str):
        return False
    if marker_hex == want_hex:
        return True
    return len(marker_hex) == SHORT_DIGEST_MARKER_HEX and want_hex.startswith(marker_hex)


@dataclass(frozen=True)
class SourceIdentity:
    source_head: str
    source_tree_fingerprint: str
    discovery_model: str
    # Command-scoped bounded evidence used by crew's end-of-snapshot CAS
    # check.  It is deliberately excluded from equality/representation so the
    # public identity and every persisted comparison remain byte-compatible.
    _revalidation: object | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class _RevalidationToken:
    root: str
    model: str
    head: str
    listing: tuple[bytes, bytes] | None
    evidence: tuple[object, ...]


@dataclass(frozen=True)
class _Record:
    kind: bytes
    path: bytes
    mode: int
    content: bytes


_ROLE_FIELD = b"role_revision:"
_SOURCE_MAGIC = b"saipen-source-fingerprint-v1\0"
_ROLE_MAGIC = b"saipen-role-revision-v1\0"
_GENERIC_ROLE_MAGIC = b"saipen-generic-role-revision-v1\0"
_NO_GIT_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".freebuff",
        ".claude",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
        # Runtime output mirrors a git project's .gitignore: logs/ and state/
        # change on every run (acceptance artifacts, locks, pids), so counting
        # them as source makes the fingerprint move under a concurrent test
        # suite and blocks every freshness check with the two-walk race.
        "logs",
        "state",
    }
)
_NO_GIT_EXCLUDED_ROOT_FILES = frozenset({"nul"})


def _run_git(root: Path, *args: str, timeout: float | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FreshnessError(f"Git discovery failed: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise FreshnessError(
            f"git {' '.join(args)} failed with exit {result.returncode}"
            + (f": {detail}" if detail else "")
        )
    return result.stdout


def _is_saipen_path(path: bytes) -> bool:
    return path == b".saipen" or path.startswith(b".saipen/")


def _is_reparse_point(path: Path) -> bool:
    """True for a symlink or a Windows junction/reparse point.

    A junction is NOT a symlink: ``stat.S_ISLNK`` is False for it, so the
    no-Git walk would otherwise recurse through it and hash content outside
    the declared root. The reparse-point attribute exists only on Windows;
    elsewhere this degrades to the symlink check (T-572).
    """
    if path.is_symlink():
        return True
    try:
        info = path.lstat()
    except OSError:
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def _frame(record: _Record) -> bytes:
    if len(record.kind) != 1:
        raise FreshnessError("fingerprint record type must be exactly one byte")
    return b"".join(
        (
            record.kind,
            struct.pack(">Q", len(record.path)),
            record.path,
            struct.pack(">I", record.mode),
            struct.pack(">Q", len(record.content)),
            record.content,
        )
    )


def _digest(model: str, records: Iterable[_Record]) -> str:
    model_bytes = model.encode("ascii")
    h = hashlib.sha256()
    h.update(_SOURCE_MAGIC)
    h.update(struct.pack(">Q", len(model_bytes)))
    h.update(model_bytes)
    for record in sorted(records, key=lambda item: item.path):
        h.update(_frame(record))
    return f"{model}:{h.hexdigest()}"


# PERF-001: preserve reference to original _digest for drift probe detection
_original_digest = _digest


def _path_from_git(root: Path, raw_path: bytes) -> Path:
    if not raw_path or raw_path.startswith(b"/") or b"\0" in raw_path:
        raise FreshnessError(f"Git returned an invalid path: {raw_path!r}")
    if any(part in (b"", b".", b"..") for part in raw_path.split(b"/")):
        raise FreshnessError(f"Git returned a non-canonical path: {raw_path!r}")
    rel = os.fsdecode(raw_path)
    candidate = root.joinpath(*rel.split("/"))
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise FreshnessError(f"Git path escapes project root: {rel!r}") from exc
    return candidate


def _read_regular_info(path: Path) -> tuple[bytes, tuple]:
    """Race-safe read returning (content, post-read stat fingerprint).

    The descriptor is opened with O_NOFOLLOW and stat'd before, during and
    after the read; any identity/size/mtime/mode drift raises FreshnessError
    (the file was replaced or mutated while its bytes were being consumed).
    The fingerprint -- (dev, ino, size, mtime_ns, mode) from the fstat of the
    EXACT descriptor whose bytes were consumed -- is returned so callers can
    re-stat or re-read the path and prove stability.
    """
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        before = path.lstat()
        fd = os.open(path, flags)
    except OSError as exc:
        raise FreshnessError(f"cannot stat/read fingerprint input {path}: {exc}") from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise FreshnessError(f"fingerprint input changed type while opening: {path}")
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise FreshnessError(f"fingerprint input raced while opening: {path}")
        chunks = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
        if (opened.st_size, opened.st_mtime_ns, opened.st_mode) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_mode,
        ):
            raise FreshnessError(f"fingerprint input changed while reading: {path}")
        fingerprint = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode)
        return b"".join(chunks), fingerprint
    except OSError as exc:
        raise FreshnessError(f"cannot read fingerprint input {path}: {exc}") from exc
    finally:
        os.close(fd)


def _read_symlink(path: Path) -> bytes:
    try:
        before = path.lstat()
        target = os.readlink(path)
        repeated = os.readlink(path)
        after = path.lstat()
    except OSError as exc:
        raise FreshnessError(f"cannot read fingerprint symlink {path}: {exc}") from exc
    if target != repeated or (before.st_dev, before.st_ino, before.st_mode, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_mtime_ns,
    ):
        raise FreshnessError(f"fingerprint symlink changed while reading: {path}")
    return os.fsencode(target)


def _record_current(
    root: Path, raw_path: bytes, declared_mode: int | None, path_map: dict | None = None
) -> _Record:
    """Record one changed/untracked path with one race-safe content read.

    The capture re-parses the delta after the second listing and requires
    the records to be byte-identical, so every content-bearing path is read
    a second time and compared -- never trusted on stat metadata alone
    (same-size, mtime-restored replacement must fail closed, T-1007).
    """
    if path_map is not None and raw_path in path_map:
        path = path_map[raw_path]
    else:
        path = _path_from_git(root, raw_path)
        if path_map is not None:
            path_map[raw_path] = path
    try:
        info = path.lstat()
    except OSError as exc:
        raise FreshnessError(f"cannot stat fingerprint input {path}: {exc}") from exc

    if stat.S_ISLNK(info.st_mode):
        mode = 0o120000
        kind = b"L"
        content = _read_symlink(path)
    elif stat.S_ISREG(info.st_mode):
        mode = 0o100755 if info.st_mode & 0o111 else 0o100644
        if declared_mode in (0o100644, 0o100755):
            mode = declared_mode
        kind = b"F"
        content, _ = _read_regular_info(path)
    else:
        raise FreshnessError(
            f"unsupported fingerprint input type at {path}; only regular files "
            "and symlinks are supported"
        )

    if declared_mode is not None and declared_mode not in (mode, 0):
        raise FreshnessError(f"Git mode {declared_mode:o} disagrees with filesystem type at {path}")
    return _Record(kind, raw_path, mode, content)


@dataclass(frozen=True)
class _Evidence:
    """Bounded freshness capture record (PERF-002): full file content is
    replaced by its SHA-256 digest so the stability passes hold O(file-count)
    metadata instead of the whole source tree. ``content`` carries the raw
    framed bytes for L (symlink target) and D (empty) records; for F records
    it carries the 32-byte content digest used only for pass-to-pass equality.
    """

    kind: bytes
    path: bytes
    mode: int
    content: bytes
    length: int


def _content_digest(content: bytes) -> bytes:
    return hashlib.sha256(content).digest()


#: A slot filled in after the reads finish. Only ever returned to the caller
#: when a read raised, in which case the pass aborts before reading slots, so
#: it can never leak into evidence.
_PLACEHOLDER = _Evidence(b"F", b"", 0, b"", 0)


def _record_evidence(
    root: Path,
    raw_path: bytes,
    declared_mode: int | None,
    path_map: dict | None = None,
    record_observer: Callable[[_Record], None] | None = None,
) -> _Evidence:
    """One race-safe capture producing bounded evidence (PERF-002).

    Mirrors ``_record_current`` but retains only a content digest, so the
    three parse passes never hold more than one file's bytes at a time. The
    digest pass re-reads the canonical bytes to frame them exactly as
    ``_frame`` does.
    """
    if path_map is not None and raw_path in path_map:
        path = path_map[raw_path]
    else:
        path = _path_from_git(root, raw_path)
        if path_map is not None:
            path_map[raw_path] = path
    try:
        info = path.lstat()
    except OSError as exc:
        raise FreshnessError(f"cannot stat fingerprint input {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        mode = 0o120000
        kind = b"L"
        content = _read_symlink(path)
    elif stat.S_ISREG(info.st_mode):
        mode = 0o100755 if info.st_mode & 0o111 else 0o100644
        if declared_mode in (0o100644, 0o100755):
            mode = declared_mode
        kind = b"F"
        content, _ = _read_regular_info(path)
    else:
        raise FreshnessError(
            f"unsupported fingerprint input type at {path}; only regular files "
            "and symlinks are supported"
        )
    if declared_mode is not None and declared_mode not in (mode, 0):
        raise FreshnessError(f"Git mode {declared_mode:o} disagrees with filesystem type at {path}")
    if record_observer is not None:
        record_observer(_Record(kind, raw_path, mode, content))
    framed = content if kind != b"F" else _content_digest(content)
    return _Evidence(kind, raw_path, mode, framed, len(content))


def _parse_git_delta_evidence(
    root: Path,
    raw: bytes,
    untracked: bytes,
    path_map: dict | None = None,
    record_observer: Callable[[_Record], None] | None = None,
    parallel: bool = True,
) -> list[_Evidence]:
    """Evidence variant of ``_parse_git_delta`` (PERF-002)."""
    records: dict[bytes, tuple[bytes, int, int]] = {}
    fields = raw.split(b"\0")
    index = 0
    while index < len(fields) and fields[index]:
        header = fields[index]
        index += 1
        if index >= len(fields) or not fields[index]:
            raise FreshnessError("Git returned a truncated --raw delta record")
        raw_path = fields[index]
        index += 1
        if _is_saipen_path(raw_path):
            continue
        parts = header.split()
        if len(parts) != 5 or not parts[0].startswith(b":"):
            raise FreshnessError(f"Git returned an unparseable --raw record: {header!r}")
        try:
            old_mode = int(parts[0][1:], 8)
            new_mode = int(parts[1], 8)
        except ValueError as exc:
            raise FreshnessError(f"Git returned an invalid mode: {header!r}") from exc
        status_code = parts[4][:1]
        if status_code == b"U":
            raise FreshnessError(
                "unmerged fingerprint input cannot become ready: " + os.fsdecode(raw_path)
            )
        if status_code not in (b"A", b"D", b"M", b"T"):
            raise FreshnessError(
                f"unsupported Git delta status {parts[4]!r}: {os.fsdecode(raw_path)}"
            )
        if status_code == b"D" or new_mode == 0:
            records[raw_path] = (b"D", old_mode, new_mode)
            continue
        if new_mode == 0o160000:
            raise FreshnessError(f"changed Git submodule is unsupported: {os.fsdecode(raw_path)}")
        records[raw_path] = (b"F", old_mode, new_mode)
    for raw_path in untracked.split(b"\0"):
        if not raw_path or _is_saipen_path(raw_path):
            continue
        records[raw_path] = (b"F", 0, 0)
    # The output order is `sorted(records)`' order and is load-bearing: the
    # confirming pass frames these records into the canonical digest in exactly
    # this sequence, so the parallel path below must reproduce it byte-for-byte
    # rather than re-sorting by kind or by completion time.
    ordered_paths = sorted(records)

    if record_observer is not None or not parallel or len(ordered_paths) < 2:
        # The confirmed pass streams these frames into the canonical digest, so
        # its call order IS part of the fingerprint. It therefore runs the
        # original single loop, unchanged: one record at a time, in
        # `sorted(records)` order, observer called at the record's own position.
        # Reusing the slot machinery below would group the deletion frames ahead
        # of the file frames and silently move `git-delta-v1`.
        evidence: list[_Evidence] = []
        for raw_path in ordered_paths:
            kind, old_mode, new_mode = records[raw_path]
            if kind == b"D":
                if record_observer is not None:
                    # Deletions have no live file to read, but they are still
                    # source identity evidence.  Omitting this frame made a
                    # tracked deletion change Git's delta listing without
                    # changing the resulting fingerprint.
                    record_observer(_Record(b"D", raw_path, old_mode, b""))
                evidence.append(_Evidence(b"D", raw_path, old_mode, b"", 0))
            else:
                evidence.append(
                    _record_evidence(
                        root, raw_path, new_mode or None, path_map, record_observer
                    )
                )
        return evidence

    # Observer-less sampling passes only. Each per-file read is independent, so
    # they overlap; the returned list is still assembled in `sorted(records)`
    # order, which is the order the confirming pass will frame it in.
    slots: list[_Evidence] = []
    read_slots: list[int] = []
    pending: list[tuple[bytes, int | None]] = []
    for raw_path in ordered_paths:
        kind, old_mode, new_mode = records[raw_path]
        if kind == b"D":
            slots.append(_Evidence(b"D", raw_path, old_mode, b"", 0))
        else:
            read_slots.append(len(slots))
            slots.append(_PLACEHOLDER)
            pending.append((raw_path, new_mode or None))

    if len(pending) > 1:
        # T-1902: the per-file reads inside one sampling pass are independent,
        # so they overlap. Bounded memory is unchanged: each read still returns
        # a content digest, never the source bytes.
        #
        # `path_map` is filled on the main thread in sorted order, exactly as
        # the sequential path fills it, so no two workers race for one raw
        # path and the cache contents are identical. Results are read back in
        # submission order, so a failing input raises the same FreshnessError
        # for the same path a sequential pass would have raised first.
        for raw_path, _declared in pending:
            if path_map is not None and raw_path not in path_map:
                path_map[raw_path] = _path_from_git(root, raw_path)
        workers = min(_READ_WORKERS, len(pending))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(_record_evidence, root, raw_path, declared, path_map, None)
                for raw_path, declared in pending
            ]
            read_results = [future.result() for future in futures]
    else:
        read_results = [
            _record_evidence(root, raw_path, declared, path_map, None)
            for raw_path, declared in pending
        ]
    for position, result in zip(read_slots, read_results):
        slots[position] = result
    return slots


def _digest_capture(model: str) -> tuple[hashlib._Hash, Callable[[_Record], None]]:
    """Create a streaming canonical digest sink for the final read pass."""
    model_bytes = model.encode("ascii")
    digest = hashlib.sha256()
    digest.update(_SOURCE_MAGIC)
    digest.update(struct.pack(">Q", len(model_bytes)))
    digest.update(model_bytes)

    def observe(record: _Record) -> None:
        digest.update(_frame(record))

    return digest, observe


def _stream_digest(root: Path, model: str, evidence: list[_Evidence]) -> str:
    """Frame the canonical source digest by re-reading each regular file's
    content in sorted path order (PERF-002).

    Produces byte-identical output to ``_digest(model, full_records)`` but
    holds at most one file's bytes at a time. Every F record is re-read and
    streamed into the SHA-256 exactly as ``_frame`` would frame its full
    content; L/D records frame their already-bounded content directly. The
    final confirmation pass is the only place full content is materialised.
    """
    root_path = Path(root)
    model_bytes = model.encode("ascii")
    h = hashlib.sha256()
    h.update(_SOURCE_MAGIC)
    h.update(struct.pack(">Q", len(model_bytes)))
    h.update(model_bytes)
    for ev in sorted(evidence, key=lambda item: item.path):
        h.update(ev.kind)
        h.update(struct.pack(">Q", len(ev.path)))
        h.update(ev.path)
        h.update(struct.pack(">I", ev.mode))
        if ev.kind == b"F":
            content = _read_regular_info(
                root_path.joinpath(*os.fsdecode(ev.path).split("/")),
            )[0]
            # PERF-001: the final confirmation re-read is the LAST content read
            # and MUST stay inside the stability comparison. Without this check a
            # same-size, mtime-restored swap that lands between the ``confirmed``
            # parse and this read would be silently folded into the fingerprint
            # (the audit's "no unvalidated reread" guardrail). The bounded
            # evidence already carries the confirmed content digest, so any
            # divergence here fails closed instead of poisoning the identity.
            if ev.content != hashlib.sha256(content).digest():
                raise FreshnessError(
                    f"fingerprint input changed between confirmation and digest: {ev.path!r}"
                )
            h.update(struct.pack(">Q", len(content)))
            h.update(content)
        else:
            h.update(struct.pack(">Q", len(ev.content)))
            h.update(ev.content)
    return f"{model}:{h.hexdigest()}"


def _evidence_to_records(root: Path, evidence: list[_Evidence]) -> list[_Record]:
    """Re-materialise bounded evidence into full framing records for the final
    hash (PERF-002 -> PERF-003 bridge).

    The three stability passes capture bounded evidence (a content digest,
    never the full bytes), so F full content is NOT held in memory across the
    whole capture -- it is re-read here, one file at a time, only for the small
    Git delta, framed exactly as ``_frame`` would, and immediately discarded.
    ``_digest`` then produces the identical fingerprint the pre-wave capture
    did, and because ``_digest`` is a module global it stays the symbol the
    perf-wave drift probe monkeypatches -- no observable-behavior regression.
    """
    root_path = Path(root)
    out: list[_Record] = []
    for ev in evidence:
        if ev.kind == b"F":
            content = _read_regular_info(root_path.joinpath(*os.fsdecode(ev.path).split("/")))[0]
            out.append(_Record(b"F", ev.path, ev.mode, content))
        else:
            out.append(_Record(ev.kind, ev.path, ev.mode, ev.content))
    return out


def _iter_no_git(
    root: Path,
    *,
    full: bool,
    record_observer: Callable[[_Record], None] | None = None,
):
    """Iterative deterministic no-Git walk (PERF-006: no Python recursion).

    When ``full`` is true each record carries the full file bytes (``_Record``);
    otherwise it carries bounded evidence (``_Evidence``, PERF-002). Depth-first
    byte-sorted traversal is preserved exactly by pushing child directories in
    reverse-sorted order so the popped order matches the original recursive
    ``visit``.
    """
    out = []
    stack: list[tuple[Path, tuple[str, ...]]] = [(Path(root), ())]
    while stack:
        directory, rel_parts = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: os.fsencode(entry.name))
        except OSError as exc:
            raise FreshnessError(
                f"cannot enumerate fingerprint directory {directory}: {exc}"
            ) from exc
        for entry in entries:
            next_parts = (*rel_parts, entry.name)
            raw_path = b"/".join(os.fsencode(part) for part in next_parts)
            path = Path(entry.path)
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise FreshnessError(f"cannot stat fingerprint input {path}: {exc}") from exc
            if stat.S_ISDIR(info.st_mode) and (
                (not rel_parts and entry.name == ".saipen") or entry.name in _NO_GIT_EXCLUDED_DIRS
            ):
                continue
            if not rel_parts and entry.name in _NO_GIT_EXCLUDED_ROOT_FILES:
                continue
            if stat.S_ISLNK(info.st_mode) or _is_reparse_point(path):
                target = _read_symlink(path)
                record = _Record(b"L", raw_path, 0o120000, target)
                if record_observer is not None:
                    record_observer(record)
                out.append(record)
            elif stat.S_ISDIR(info.st_mode):
                stack.append((path, next_parts))
            elif stat.S_ISREG(info.st_mode):
                mode = 0o100755 if info.st_mode & 0o111 else 0o100644
                content, _ = _read_regular_info(path)
                record = _Record(b"F", raw_path, mode, content)
                if full:
                    out.append(record)
                else:
                    if record_observer is not None:
                        record_observer(record)
                    out.append(
                        _Evidence(b"F", raw_path, mode, _content_digest(content), len(content))
                    )
            else:
                raise FreshnessError(
                    f"unsupported fingerprint input type at {path}; only regular "
                    "files, directories, and symlinks are supported"
                )
    return out


def _walk_no_git_evidence(
    root: Path, record_observer: Callable[[_Record], None] | None = None
) -> list[_Evidence]:
    """Bounded evidence walk used by ``compute_source_identity`` (PERF-002/006)."""
    return _iter_no_git(root, full=False, record_observer=record_observer)


#: The one boundary the source identity draws, expressed for Git as well as for
#: `_is_saipen_path`. Exclusion-only, with no positive pathspec beside it: Git
#: keeps its default selection (the whole repository as seen from the caller's
#: directory) and then drops exactly this prefix. A positive pathspec such as
#: "." would narrow that selection to the caller's subtree, which is NOT the
#: same set for a project that lives in a subdirectory of a larger repository.
_SAIPEN_PATHSPEC = (":(exclude).saipen",)


def _git_delta_listing(root: Path, *, timeout: float | None = None) -> tuple[bytes, bytes]:
    """The changed-path listing the source identity fingerprints.

    T-1900 (SRC-318). Both Git calls ask for the `.saipen` boundary to be
    excluded, because every reader of this listing either discards those paths
    or should: `_parse_git_delta` and `_parse_git_delta_evidence` skip them,
    `_filtered_git_listing` projects them out before every comparison, and
    `_nested_binding` hashes the listing of a DECLARED nested repository -- a
    project in its own right, whose `.saipen` is that project's runtime, not
    the outer one's source. Leaving the exclusion to Python meant Git
    generated and this process decoded the entire `.saipen` population on every
    pass -- measured on the live tree, 42 572 untracked paths (4.18 MB) to keep
    57, and three listings per `compute_source_identity`. The pathspec returns
    the identical surviving set (byte-for-byte, same order) for 0.032 s instead
    of 0.795 s per pass.

    The boundary is exactly `_is_saipen_path`: `.saipenicious.py`,
    `.saipen-src/` and `.saipenx/` stay ordinary source, proved against a
    fixture. The same holds inside a declared nested repository, which this
    function also serves through `_nested_binding`: the binding is
    SHA256(raw_delta + b"\0" + untracked), so excluding the nested `.saipen`
    here CHANGES the binding bytes relative to the pre-T-1900 function. That is
    the intended meaning -- a nested repository's runtime churn is not the
    outer project's source -- but it is a semantic change, so AC-05 pins it.
    A Git that could not parse this pathspec exits non-zero and the capture
    fails closed; `_parse_git_delta` and `_filtered_git_listing` keep their own
    predicate, so a Git that somehow emitted the excluded paths anyway would
    still produce the same fingerprint for a project that declares no nested
    repositories (verified: pathspeced and unfiltered listings hash identically
    on this tree). The residual exposure is a declared nested repository under
    such a Git, where the binding would be the more sensitive pre-T-1900 one.
    """
    raw = _run_git(
        root,
        "diff",
        "--raw",
        "-z",
        "--no-renames",
        "--no-ext-diff",
        "--ignore-submodules=none",
        "HEAD",
        "--",
        *_SAIPEN_PATHSPEC,
        timeout=timeout,
    )
    untracked = _run_git(
        root,
        "ls-files",
        "-z",
        "--others",
        "--exclude-standard",
        "--",
        *_SAIPEN_PATHSPEC,
        timeout=timeout,
    )
    return raw, untracked


def _filtered_git_listing(
    listing: tuple[bytes, bytes],
) -> tuple[tuple[bytes, ...], tuple[bytes, ...]]:
    """Project a Git delta listing onto the paths source identity fingerprints.

    T-1827 (SRC-282:R003). A protocol operation releases the writer lock around
    a long external process and then re-proves the source it captured. Its own
    journal, lock sidecar and recovery files live under ``.saipen`` and appear
    in ``git diff --raw``/``ls-files`` as untracked, while the source identity
    deliberately excludes every ``.saipen`` path. Comparing the RAW listing
    bytes therefore reported the caller's own bookkeeping as source drift.
    Both sides of a bounded comparison are filtered here -- the same path
    space ``_parse_git_delta`` uses -- so only fingerprinted paths can trip it.
    """
    raw, untracked = listing
    fields = raw.split(b"\0")
    kept: list[bytes] = []
    index = 0
    while index < len(fields) and fields[index]:
        header = fields[index]
        index += 1
        if index >= len(fields) or not fields[index]:
            raise FreshnessError("Git returned a truncated --raw delta record")
        raw_path = fields[index]
        index += 1
        if not _is_saipen_path(raw_path):
            kept.extend((header, raw_path))
    paths = tuple(
        path for path in untracked.split(b"\0") if path and not _is_saipen_path(path)
    )
    return tuple(kept), paths


def _parse_git_delta(root: Path, raw: bytes, untracked: bytes) -> list[_Record]:
    records: dict[bytes, _Record] = {}
    fields = raw.split(b"\0")
    index = 0
    while index < len(fields) and fields[index]:
        header = fields[index]
        index += 1
        if index >= len(fields) or not fields[index]:
            raise FreshnessError("Git returned a truncated --raw delta record")
        raw_path = fields[index]
        index += 1
        if _is_saipen_path(raw_path):
            continue
        parts = header.split()
        if len(parts) != 5 or not parts[0].startswith(b":"):
            raise FreshnessError(f"Git returned an unparseable --raw record: {header!r}")
        try:
            old_mode = int(parts[0][1:], 8)
            new_mode = int(parts[1], 8)
        except ValueError as exc:
            raise FreshnessError(f"Git returned an invalid mode: {header!r}") from exc
        status_code = parts[4][:1]
        if status_code == b"U":
            raise FreshnessError(
                "unmerged fingerprint input cannot become ready: " + os.fsdecode(raw_path)
            )
        if status_code not in (b"A", b"D", b"M", b"T"):
            raise FreshnessError(
                f"unsupported Git delta status {parts[4]!r}: {os.fsdecode(raw_path)}"
            )
        if status_code == b"D" or new_mode == 0:
            records[raw_path] = _Record(b"D", raw_path, old_mode, b"")
            continue
        if new_mode == 0o160000:
            raise FreshnessError(f"changed Git submodule is unsupported: {os.fsdecode(raw_path)}")
        records[raw_path] = _record_current(root, raw_path, new_mode)

    for raw_path in untracked.split(b"\0"):
        if not raw_path or _is_saipen_path(raw_path):
            continue
        records[raw_path] = _record_current(root, raw_path, None)
    return list(records.values())


def _git_identity(root: Path) -> SourceIdentity:
    """Bounded race-safe capture: HEAD, listing, content parse, listing,
    content parse, listing, HEAD, ONE content confirmation parse (perf wave
    T-1019: was 12 Git subprocesses / four listings / three reads per path;
    now 10 subprocesses / three listings / three reads per path).

    Stability proof -- no check ever trusts stat metadata ALONE (a
    same-size, mtime-restored replacement must fail closed, T-1007):
    - HEAD before and after must be identical;
    - the three delta listings must be byte-identical. A tracked in-place
      content change between them changes the new blob SHA inside
      `git diff --raw`, so listing inequality detects it -- including a
      tracked file that becomes dirty AFTER the second content parse;
    - every content-bearing path is read a second and third time and the
      three record frames (kind/path/mode/content) must be byte-identical.
      Untracked paths carry no SHA in the listing, so only these bounded
      content re-reads can prove they did not move; a replacement that
      preserves size and mtime still changes the bytes.

    The capture retains only bounded evidence (PERF-002): each parse holds
    O(file-count) metadata (a content digest, never the full source bytes),
    and the final confirmation pass streams the canonical content straight
    into the digest. A stable fixture yields the exact same `git-delta-v1`
    identity as the pre-wave capture because the framing is identical.
    """
    head_before = _run_git(root, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    listing_before = _git_delta_listing(root)
    # PERF-001: one call-scoped raw-git-path -> validated Path map. The three
    # listing passes re-walk the same deterministic raw paths; mapping each
    # distinct raw path through _path_from_git once (instead of once per pass)
    # removes repeated containment work while the race-safe content/stat/Git
    # evidence passes are untouched.
    _path_map: dict[bytes, Path] = {}
    first = _parse_git_delta_evidence(root, *listing_before, path_map=_path_map)
    listing_middle = _git_delta_listing(root)
    second = _parse_git_delta_evidence(root, *listing_middle, path_map=_path_map)
    listing_after = _git_delta_listing(root)
    head_after = _run_git(root, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if head_before != head_after or not (listing_before == listing_middle == listing_after):
        raise FreshnessError("source tree or HEAD changed while fingerprint inputs were being read")
    model = "git-delta-v1"
    binding_before = _nested_binding(root)
    digest, observe = _digest_capture(model)
    # T-1902: the confirming pass stays strictly sequential. Its frames feed
    # the canonical digest in sorted order, so overlapping its reads would
    # change the fingerprint; the two observer-less passes above and below are
    # the only ones that may overlap.
    confirmed = _parse_git_delta_evidence(
        root,
        *listing_after,
        path_map=_path_map,
        record_observer=observe,
        parallel=False,
    )
    if first != second or second != confirmed:
        raise FreshnessError("source content changed while fingerprint inputs were being read")
    # PERF-002: the final confirmation read also frames the canonical digest;
    # do not throw those validated bytes away and read every file a fourth
    # time merely for hashing.
    if _digest is not _original_digest:
        # Drift probe is active -- route through _digest for compatibility
        records = _evidence_to_records(root, confirmed)
        fingerprint = _digest(model, records)
    else:
        fingerprint = f"{model}:{digest.hexdigest()}"
    if binding_before != _nested_binding(root):
        raise FreshnessError(
            "declared nested source changed while fingerprint inputs were being read"
        )
    fingerprint = _bind_nested(fingerprint, binding_before)
    token = _RevalidationToken(
        os.fspath(root.resolve()), model, head_before, listing_after, tuple(confirmed)
    )
    return SourceIdentity(head_before, fingerprint, model, token)


#: A project that keeps a repository INSIDE another one declares it here. The
#: outer `git diff` cannot see it: the path is either gitignored (ZAICODE's
#: ``/zcode/``) or tracked as a submodule, and in both cases an edit inside
#: the nested tree left the outer fingerprint byte-identical -- measured, not
#: assumed, on 27.09.26 against _zaicode. Every freshness and staleness
#: decision in the outer project was therefore blind to the code that ships.
#:
#: Declaration, not discovery: a tree walk for ``.git`` on every identity call
#: would cost more than the capture it protects, and would silently bind
#: repositories the project never meant to. A project says which ones count.
NESTED_REPOS_CONFIG_REL = Path(".saipen") / "source-nested-repos.json"


def _nested_binding(root: Path) -> bytes:
    """Canonical bytes binding every DECLARED nested repository's identity.

    Empty when the project declares none, which keeps every existing project's
    identity byte-identical to what it was before this rule existed. A declared
    repository that is missing, unreadable or not a Git work tree FAILS the
    capture rather than dropping out of it: a freshness guarantee that quietly
    stops covering its source is worse than no guarantee, because it is believed.
    """
    config = root / NESTED_REPOS_CONFIG_REL
    try:
        raw = config.read_bytes()
    except OSError:
        return b""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise FreshnessError(f"nested-repo binding is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise FreshnessError("nested-repo binding must be a JSON object")
    declared = data.get("nested_repos")
    if declared is None:
        return b""
    if not isinstance(declared, list) or not all(isinstance(x, str) for x in declared):
        raise FreshnessError("nested-repo binding 'nested_repos' must be a list of paths")
    if not declared:
        return b""
    # Canonical, not raw: the binding names WHICH repositories count, so
    # reordering the list or repeating an entry is not a change in what is
    # bound and must not move the identity. Only adding or removing one does.
    canon = json.dumps(
        {"schema_version": data.get("schema_version", 1), "nested_repos": sorted(set(declared))},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    parts: list[bytes] = [b"git-delta-v1-nested\x00", canon]
    for rel in sorted(set(declared)):
        nested = (root / rel).resolve()
        try:
            nested.relative_to(root.resolve())
        except ValueError as exc:
            raise FreshnessError(
                f"declared nested repository escapes the project root: {rel!r}"
            ) from exc
        if not nested.is_dir():
            raise FreshnessError(f"declared nested repository is missing: {rel!r}")
        if _is_reparse_point(root / rel):
            raise FreshnessError(
                f"declared nested repository is a reparse point: {rel!r}"
            )
        # `--is-inside-work-tree` is the wrong test here: a plain directory
        # inside the outer repository answers true and would then be bound to
        # the OUTER head and delta, silently covering the wrong bytes. The
        # nested path must be the TOP LEVEL of its own work tree -- the same
        # rule compute_source_identity applies to a checkpoint root nested
        # inside somebody else's repository.
        probe = subprocess.run(
            ["git", "-C", os.fspath(nested), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if probe.returncode != 0:
            raise FreshnessError(
                f"declared nested repository is not a Git work tree: {rel!r}"
            )
        try:
            toplevel = Path(os.fsdecode(probe.stdout.strip())).resolve()
        except (OSError, ValueError) as exc:
            raise FreshnessError(
                f"declared nested repository has an unreadable work tree: {rel!r}"
            ) from exc
        if toplevel != nested:
            raise FreshnessError(
                f"declared nested repository is not its own work tree root: {rel!r} "
                f"(git reports {os.fspath(toplevel)!r}); a directory inside the "
                f"outer repository would be bound to the outer head and delta"
            )
        head = _run_git(nested, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
        raw_delta, untracked = _git_delta_listing(nested)
        parts.append(
            b"\x00"
            + rel.encode("utf-8")
            + b"\x00"
            + head.encode("ascii")
            + b"\x00"
            + hashlib.sha256(raw_delta + b"\x00" + untracked).digest()
        )
    return b"".join(parts)


def _bind_nested(fingerprint: str, binding: bytes) -> str:
    """Mix the nested binding into ``model:hex`` without changing its shape."""
    if not binding:
        return fingerprint
    model, _, _hexdigest = fingerprint.partition(":")
    mixed = hashlib.sha256()
    mixed.update(fingerprint.encode("ascii"))
    mixed.update(b"\x00")
    mixed.update(struct.pack(">Q", len(binding)))
    mixed.update(binding)
    return f"{model}:{mixed.hexdigest()}"


def _walk_no_git(root: Path) -> list[_Record]:
    """Iterative deterministic no-Git walk returning full-content ``_Record``
    (PERF-006: no Python recursion). The bounded-memory identity capture uses
    ``_walk_no_git_evidence``; this wrapper exists for any caller that needs
    the full bytes and preserves the exact traversal/exclusion semantics.
    """
    return _iter_no_git(root, full=True)


def compute_source_identity(project_root: Path | str) -> SourceIdentity:
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise FreshnessError(f"project root is not a directory: {root}")
    git_marker = root / ".git"
    try:
        probe = subprocess.run(
            ["git", "-C", os.fspath(root), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        if git_marker.exists():
            raise FreshnessError(f"Git repository discovery failed: {exc}") from exc
        probe = None
    if probe is not None and probe.returncode == 0 and probe.stdout.strip() == b"true":
        try:
            top = _run_git(root, "rev-parse", "--show-toplevel")
            git_root = Path(os.fsdecode(top.strip())).resolve()
        except (FreshnessError, OSError) as exc:
            raise FreshnessError(f"Git repository root discovery failed: {exc}") from exc
        # A checkpoint root nested inside somebody else's repository is not a
        # Git project of its own. Applying the parent's root-relative paths to
        # the child silently hashes the wrong source surface (and can escape
        # the child entirely), so it uses the explicit no-Git model instead.
        if git_root == root:
            return _git_identity(root)
    elif git_marker.exists():
        detail = ""
        if probe is not None:
            detail = probe.stderr.decode("utf-8", "replace").strip()
        raise FreshnessError(
            "Git metadata exists but work-tree discovery failed" + (f": {detail}" if detail else "")
        )
    model = "no-git-tree-v1"
    first = _walk_no_git_evidence(root)
    digest, observe = _digest_capture(model)
    second = _walk_no_git_evidence(root, record_observer=observe)
    if first != second:
        raise FreshnessError("no-Git source tree changed while fingerprint inputs were being read")
    fingerprint = f"{model}:{digest.hexdigest()}"
    token = _RevalidationToken(os.fspath(root.resolve()), model, "no-git", None, tuple(second))
    return SourceIdentity("no-git", fingerprint, model, token)


def listing_token_unchanged(
    project_root: Path | str, identity: SourceIdentity, *, timeout: float | None = None
) -> tuple[bool, str | None]:
    """The cheap half of revalidation: HEAD and the changed-path LISTING only.

    T-1827 (SRC-282:R003/R006). The writer lock may hold this check, so it
    re-derives only what Git reports (two HEAD reads, two delta listings) and
    never re-hashes changed file contents: a 70k-entry working tree made the
    full content confirmation take minutes, which is exactly the hold the
    audit measured. Tracked edits are still caught because `git diff --raw`
    carries the blob hashes; untracked content edits are not, and no
    lock-respecting writer can cause those anyway.
    """
    root = Path(project_root).resolve()
    token = identity._revalidation
    if not isinstance(token, _RevalidationToken):
        return False, "source identity has no bounded revalidation token"
    if token.root != os.fspath(root) or token.model != identity.discovery_model:
        return False, "source revalidation token is bound to another root/model"
    if token.model != "git-delta-v1" or token.listing is None:
        return False, "source identity has no bounded Git listing token"
    try:
        head_before = _run_git(
            root, "rev-parse", "--verify", "HEAD", timeout=timeout
        ).decode("ascii").strip()
        listing_before = _git_delta_listing(root, timeout=timeout)
        listing_after = _git_delta_listing(root, timeout=timeout)
        head_after = _run_git(
            root, "rev-parse", "--verify", "HEAD", timeout=timeout
        ).decode("ascii").strip()
        listing_stable = (
            _filtered_git_listing(listing_before)
            == _filtered_git_listing(listing_after)
            == _filtered_git_listing(token.listing)
        )
    except (FreshnessError, OSError, UnicodeError) as exc:
        return False, str(exc)
    if not (head_before == head_after == token.head == identity.source_head and listing_stable):
        return False, "source HEAD or changed-path listing moved after capture"
    return True, None


def revalidate_source_identity(
    project_root: Path | str, identity: SourceIdentity, *, timeout: float | None = None
) -> tuple[bool, str | None]:
    """Confirm a captured identity without repeating the full capture.

    Git confirmation uses two HEAD reads and two delta listings (six Git
    subprocesses total) plus bounded content evidence, instead of another ten
    subprocess full identity.  No-Git confirmation performs one evidence walk
    and one checked streaming digest.  Any missing/foreign token fails closed.

    ``timeout`` bounds each Git subprocess. T-1827 (SRC-282:R003): a caller
    that runs this confirmation while holding the project writer lock passes
    its declared bound, so no external process under that lock can outlast it.
    """
    root = Path(project_root).resolve()
    token = identity._revalidation
    if not isinstance(token, _RevalidationToken):
        return False, "source identity has no bounded revalidation token"
    if token.root != os.fspath(root) or token.model != identity.discovery_model:
        return False, "source revalidation token is bound to another root/model"
    try:
        if token.model == "git-delta-v1":
            if token.listing is None:
                return False, "Git source revalidation token has no listing"
            head_before = _run_git(
                root, "rev-parse", "--verify", "HEAD", timeout=timeout
            ).decode("ascii").strip()
            listing_before = _git_delta_listing(root, timeout=timeout)
            digest, observe = _digest_capture(token.model)
            evidence = _parse_git_delta_evidence(
                root, *listing_before, record_observer=observe
            )
            listing_after = _git_delta_listing(root, timeout=timeout)
            head_after = _run_git(
                root, "rev-parse", "--verify", "HEAD", timeout=timeout
            ).decode("ascii").strip()
            if not (
                head_before == head_after == token.head == identity.source_head
                and _filtered_git_listing(listing_before)
                == _filtered_git_listing(listing_after)
                == _filtered_git_listing(token.listing)
                and tuple(evidence) == token.evidence
            ):
                return False, "source tree or HEAD changed after snapshot capture"
            digest = f"{token.model}:{digest.hexdigest()}"
        elif token.model == "no-git-tree-v1":
            digest, observe = _digest_capture(token.model)
            evidence = _walk_no_git_evidence(root, record_observer=observe)
            if tuple(evidence) != token.evidence:
                return False, "no-Git source tree changed after snapshot capture"
            digest = f"{token.model}:{digest.hexdigest()}"
        else:
            return False, f"unsupported source revalidation model: {token.model}"
    except (FreshnessError, OSError, UnicodeError) as exc:
        return False, str(exc)
    if digest != identity.source_tree_fingerprint:
        return False, "source fingerprint changed after snapshot capture"
    return True, None


def compute_role_revision(charter_path: Path | str) -> str:
    path = Path(charter_path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FreshnessError(f"cannot read role charter {path}: {exc}") from exc
    raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = raw.splitlines(keepends=True)
    in_yaml = False
    removed = 0
    body: list[bytes] = []
    for line in lines:
        stripped = line.strip()
        if stripped == b"```yaml" and not in_yaml:
            in_yaml = True
            body.append(line)
            continue
        if stripped == b"```" and in_yaml:
            in_yaml = False
            body.append(line)
            continue
        if in_yaml and line.lstrip().startswith(_ROLE_FIELD):
            removed += 1
            continue
        body.append(line)
    if removed != 1:
        raise FreshnessError(
            f"role charter {path} must contain exactly one role_revision field; found {removed}"
        )
    canonical = b"".join(body)
    h = hashlib.sha256()
    h.update(_ROLE_MAGIC)
    h.update(struct.pack(">Q", len(canonical)))
    h.update(canonical)
    return "sha256:" + h.hexdigest()


def compute_generic_role_revision(protocol_path: Path | str) -> str:
    path = Path(protocol_path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FreshnessError(f"cannot read generic role protocol {path}: {exc}") from exc
    canonical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    h = hashlib.sha256()
    h.update(_GENERIC_ROLE_MAGIC)
    h.update(struct.pack(">Q", len(canonical)))
    h.update(canonical)
    return "sha256:" + h.hexdigest()

"""Cross-platform single-writer lock (NITRO M2).

Real OS file locking: msvcrt on Windows, fcntl on POSIX. The lock file carries
no canonical truth; process death releases the OS lock. Project path aliases
resolve to the same lock identity (canonical_identity), so two aliases to one
project cannot create two writers.
"""

from __future__ import annotations

import contextlib
import os
import threading
from pathlib import Path

_MSVCRT = None
_FCNTL = None
if os.name == "nt":
    import msvcrt as _MSVCRT  # type: ignore
else:
    import fcntl as _FCNTL  # type: ignore

from .snapshot import canonical_identity  # noqa: E402

LOCK_DIR = ".saipen/locks"

# In-process ownership registry for producer-local locks. OS file locks are
# reentrant across distinct handles within one process on some platforms
# (notably Windows msvcrt.locking), so we ALSO track the live holder here to
# make same-process conflict detection deterministic (CORE-005 / V7). The key
# is the resolved lock-file path; the value is the holding ProducerLock instance.
# In-process ownership registries for same-process single-writer defense.
# OS file locks are reentrant across distinct handles within one process
# on some platforms (notably Windows msvcrt.locking), so we ALSO track live
# holders here to make same-process conflict detection deterministic.
# W2-002: the registry is a RESERVATION layer -- the key is reserved BEFORE
# the OS lock attempt and cleared on failure, closing the check-then-publish
# TOCTOU race.
_WRITER_HOLDERS: dict[str, "WriterLock"] = {}
_PRODUCER_HOLDERS: dict[str, "ProducerLock"] = {}
_HOLDERS_GUARD = threading.Lock()


class WriterLock:
    """An exclusive OS lock on the project's canonical lock file."""

    def __init__(self, project_root: Path | str) -> None:
        root = Path(project_root)
        lock_dir = root / LOCK_DIR
        try:
            res_root = root.resolve()
        except OSError as exc:
            raise PermissionError(f"project root is unresolvable: {exc}")
        # Self-enforcing containment (CORE-007). Prove the lock directory
        # resolves INSIDE the canonical project root BEFORE any filesystem
        # mutation. `resolve()` follows symlinks/junctions/reparse points, so a
        # symlinked `.saipen` that points outside the project yields an
        # out-of-root path. The previous code only raised for an *already
        # existing* escaped directory and then swallowed that PermissionError
        # inside a broad `except OSError: pass`, so it still mkdir'd the
        # escaped directory first -- a direct writer-lock call could therefore
        # perform an outside-root write before failing closed.
        try:
            res_lock = lock_dir.resolve()
        except OSError as exc:
            raise PermissionError(f"lock directory is unresolvable: {exc}")
        if not res_lock.is_relative_to(res_root):
            # Containment escape (symlink/junction/reparse outside root): refuse
            # with ZERO writes. A canonical whole-project alias that resolves to
            # the same legitimate root is NOT an escape and falls through below.
            raise PermissionError("lock directory escapes project root")
        # Existing-component reparse/symlink sanity check using NON-following
        # lstat: a reparse point that resolve() did not fully collapse must
        # still sit under the project root, or we refuse with zero writes.
        for comp in (root / ".saipen", lock_dir):
            try:
                info = os.lstat(comp)
            except OSError:
                continue
            if os.path.islink(comp) or getattr(info, "st_file_attributes", 0) & 0x400:
                try:
                    comp_res = Path(comp).resolve()
                except OSError:
                    raise PermissionError("lock component is unresolvable")
                if not comp_res.is_relative_to(res_root):
                    raise PermissionError("lock directory escapes project root")
        # Create only AFTER containment is proved: a missing local lock dir is
        # created INSIDE the project, an existing in-root dir is left untouched.
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.path = lock_dir / "core.lock"
        self._handle = None
        self._acquired = False

    def acquire(self) -> bool:
        """Blocking exclusive lock. Returns True (or raises WRITER_BUSY).

        W2-002: uses an atomic process-local reservation BEFORE the OS lock
        so two same-process threads cannot both enter the critical section
        on Windows-like reentrant OS locking.
        """
        if self._acquired:
            return True
        key = str(self.path.resolve())
        # RESERVE under the guard: reject an existing holder, then publish
        # ourselves BEFORE attempting the OS lock. This closes the
        # check-then-publish TOCTOU race.
        with _HOLDERS_GUARD:
            holder = _WRITER_HOLDERS.get(key)
            if holder is not None and holder is not self:
                raise PermissionError("WRITER_BUSY")
            _WRITER_HOLDERS[key] = self
        # Attempt the OS lock; on failure, atomically clear our reservation.
        self._handle = open(self.path, "a+b")  # noqa: SIM115
        try:
            if _MSVCRT is not None:
                _MSVCRT.locking(self._handle.fileno(), _MSVCRT.LK_NBLCK, 1)
            else:
                _FCNTL.flock(self._handle.fileno(), _FCNTL.LOCK_EX | _FCNTL.LOCK_NB)
        except OSError:
            self._handle.close()
            self._handle = None
            with _HOLDERS_GUARD:
                if _WRITER_HOLDERS.get(key) is self:
                    del _WRITER_HOLDERS[key]
            raise PermissionError("WRITER_BUSY")
        self._acquired = True
        return True

    def release(self) -> None:
        if not self._acquired or self._handle is None:
            return
        key = str(self.path.resolve())
        try:
            if _MSVCRT is not None:
                self._handle.seek(0)
                _MSVCRT.locking(self._handle.fileno(), _MSVCRT.LK_UNLCK, 1)
            else:
                _FCNTL.flock(self._handle.fileno(), _FCNTL.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None
            self._acquired = False
            with _HOLDERS_GUARD:
                if _WRITER_HOLDERS.get(key) is self:
                    del _WRITER_HOLDERS[key]

    def __enter__(self) -> "WriterLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


@contextlib.contextmanager
def project_writer_lock(project_root: Path | str):
    """Acquire the canonical project writer lock or raise PermissionError
    (WRITER_BUSY) if another live writer holds it."""
    lock = WriterLock(project_root)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()


def lock_identity(project_root: Path | str) -> str:
    """The canonical lock identity: aliases of one project share it."""
    return canonical_identity(project_root)


# ---------------------------------------------------------------------------
# V7 Producer Parallelism Hardening -- producer-LOCAL lock.
#
# This serializes TWO WRITERS racing the SAME producer namespace
# (saitranslate + saitranslate, or saiwiki + saiwiki). It deliberately grants
# NO authority over the canonical main tree: it only locks a
# `.saipen/locks/producer-<name>.lock` file. Cross-producer concurrency
# (saitranslate + saiwiki) is allowed because the lock files differ. Core
# canonical writes remain gated exclusively by `WriterLock` / `project_writer_lock`.
# ---------------------------------------------------------------------------


class ProducerLock:
    """Exclusive OS lock scoped to ONE producer namespace."""

    def __init__(self, project_root: Path | str, producer: str) -> None:
        if producer not in ("saitranslate", "saiwiki"):
            raise ValueError(f"unknown producer role: {producer!r}")
        root = Path(project_root)
        lock_dir = root / LOCK_DIR
        # Reuse WriterLock's containment discipline: prove the lock dir resolves
        # INSIDE the project before any write. A producer lock is only ever a
        # sibling of core.lock -- it can never reach outside the project.
        try:
            res_root = root.resolve()
            res_lock = lock_dir.resolve()
        except OSError as exc:
            raise PermissionError(f"producer lock path unresolvable: {exc}")
        if not res_lock.is_relative_to(res_root):
            raise PermissionError("producer lock directory escapes project root")
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.producer = producer
        self.path = lock_dir / f"producer-{producer}.lock"
        self._handle = None
        self._acquired = False

    def acquire(self) -> bool:
        """Blocking-exclusive, non-blocking acquire. Raises WRITER_BUSY on conflict.

        W2-002: uses an atomic process-local reservation BEFORE the OS lock
        so two same-process threads cannot both enter the critical section
        on Windows-like reentrant OS locking.
        """
        if self._acquired:
            return True
        key = str(self.path.resolve())
        # RESERVE under the guard: reject an existing holder, then publish
        # ourselves BEFORE attempting the OS lock. This closes the
        # check-then-publish TOCTOU race.
        with _HOLDERS_GUARD:
            holder = _PRODUCER_HOLDERS.get(key)
            if holder is not None and holder is not self:
                raise PermissionError(f"PRODUCER_BUSY: {self.producer} is already writing")
            _PRODUCER_HOLDERS[key] = self
        # Attempt the OS lock; on failure, atomically clear our reservation.
        self._handle = open(self.path, "a+b")  # noqa: SIM115 -- held across the lock lifecycle
        try:
            if _MSVCRT is not None:
                _MSVCRT.locking(self._handle.fileno(), _MSVCRT.LK_NBLCK, 1)
            else:
                _FCNTL.flock(self._handle.fileno(), _FCNTL.LOCK_EX | _FCNTL.LOCK_NB)
        except OSError:
            self._handle.close()
            self._handle = None
            with _HOLDERS_GUARD:
                if _PRODUCER_HOLDERS.get(key) is self:
                    del _PRODUCER_HOLDERS[key]
            raise PermissionError(f"PRODUCER_BUSY: {self.producer} is already writing")
        self._acquired = True
        return True

    def release(self) -> None:
        if not self._acquired or self._handle is None:
            return
        key = str(self.path.resolve())
        try:
            if _MSVCRT is not None:
                self._handle.seek(0)
                _MSVCRT.locking(self._handle.fileno(), _MSVCRT.LK_UNLCK, 1)
            else:
                _FCNTL.flock(self._handle.fileno(), _FCNTL.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None
            self._acquired = False
        with _HOLDERS_GUARD:
            if _PRODUCER_HOLDERS.get(key) is self:
                del _PRODUCER_HOLDERS[key]

    def __enter__(self) -> "ProducerLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


@contextlib.contextmanager
def producer_writer_lock(project_root: Path | str, producer: str):
    """Acquire the producer-local writer lock for one role.

    Distinct producers (saitranslate vs saiwiki) may hold their locks at the
    same time. Two writers of the SAME producer serialize or the second raises
    PermissionError(PRODUCER_BUSY). This lock never gates canonical main-tree
    writes -- that is `project_writer_lock`'s job.
    """
    lock = ProducerLock(project_root, producer)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()

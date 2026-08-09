"""Cross-platform single-writer lock (NITRO M2).

Real OS file locking: msvcrt on Windows, fcntl on POSIX. The lock file carries
no canonical truth; process death releases the OS lock. Project path aliases
resolve to the same lock identity (canonical_identity), so two aliases to one
project cannot create two writers.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

_MSVCRT = None
_FCNTL = None
if os.name == "nt":
    import msvcrt as _MSVCRT  # type: ignore
else:
    import fcntl as _FCNTL  # type: ignore

from .snapshot import canonical_identity  # noqa: E402

LOCK_DIR = ".saipen/locks"


class WriterLock:
    """An exclusive OS lock on the project's canonical lock file."""

    def __init__(self, project_root: Path | str) -> None:
        root = Path(project_root)
        lock_dir = root / LOCK_DIR
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.path = lock_dir / "core.lock"
        self._handle = None
        self._acquired = False

    def acquire(self) -> bool:
        """Blocking exclusive lock. Returns True (or raises WRITER_BUSY)."""
        if self._acquired:
            return True
        self._handle = open(self.path, "a+b")  # noqa: SIM115 -- held across the lock lifecycle, not a scoped with
        try:
            if _MSVCRT is not None:
                _MSVCRT.locking(self._handle.fileno(), _MSVCRT.LK_NBLCK, 1)
            else:
                _FCNTL.flock(self._handle.fileno(),
                             _FCNTL.LOCK_EX | _FCNTL.LOCK_NB)
        except OSError:
            self._handle.close()
            self._handle = None
            raise PermissionError("WRITER_BUSY")
        self._acquired = True
        return True

    def release(self) -> None:
        if not self._acquired or self._handle is None:
            return
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

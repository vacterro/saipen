"""Cross-platform single-writer lock (NITRO M2).

Real OS file locking: msvcrt on Windows, fcntl on POSIX. The lock file carries
no canonical truth; process death releases the OS lock. Project path aliases
resolve to the same lock identity (canonical_identity), so two aliases to one
project cannot create two writers.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import stat
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_MSVCRT = None
_FCNTL = None
if os.name == "nt":
    import msvcrt as _MSVCRT  # type: ignore
else:
    import fcntl as _FCNTL  # type: ignore

from .snapshot import canonical_identity  # noqa: E402
from .paths import prove_owned_dir_chain, prove_owned_regular  # noqa: E402

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
_FILE_HOLDERS: dict[str, "FileWriterLock"] = {}
_HOLDERS_GUARD = threading.Lock()


#: T-1647. The lock is the first byte any mutation writes, so it is where an
#: account granted a project for reading only meets that grant. That is a fact
#: about access, answered as one: the raw error was a traceback.
NOT_WRITABLE = "PROJECT_NOT_WRITABLE"

#: T-1827 (SRC-282). The project writer lock used to be acquired with a single
#: non-blocking OS call while its docstring promised a blocking one, so a
#: second writer refused in ~0.4 s with no holder identity. The wait is now
#: bounded and declared: one deadline covers the whole acquisition, an
#: environment override lets a test prove the refusal without sitting through
#: the production wait, and an exhausted deadline still speaks exactly
#: WRITER_BUSY. The default matches the watchdog's own 5 s retry budget.
WRITER_LOCK_TIMEOUT_ENV = "SAIPEN_WRITER_LOCK_TIMEOUT"
DEFAULT_WRITER_LOCK_TIMEOUT = 5.0
_LOCK_RETRY_SLEEP = 0.02
#: A holder record is diagnostic bytes written while the lock is held. It is
#: never read to decide acquisition -- process death releasing the OS lock is
#: the ONE release truth (SRC-282:R005) -- only to name the holder in a
#: refusal or through `saipen lock status`.
_HOLDER_RECORD_LIMIT = 4096
_HOLDER_COMMAND_LIMIT = 400


class WriterBusy(PermissionError):
    """Another live writer owns the project lock.

    ``str()`` stays exactly ``WRITER_BUSY``: several call sites (and the CLI
    boundary) compare that token. The human explanation -- including the
    holder record when one is readable -- lives in :attr:`detail`/`holder`.
    """

    def __init__(self, detail: str = "", *, holder: dict | None = None) -> None:
        super().__init__("WRITER_BUSY")
        self.detail = detail or "another live writer holds the project lock"
        self.holder = holder

    def __str__(self) -> str:
        return "WRITER_BUSY"


def writer_lock_timeout() -> float:
    """Seconds to wait for the project writer lock before refusing.

    Overridable through the environment so a test can prove the bounded
    refusal without sitting through the production wait. A non-numeric or
    non-positive value is the default, never an unbounded wait.
    """
    raw = os.environ.get(WRITER_LOCK_TIMEOUT_ENV)
    if raw is None:
        return DEFAULT_WRITER_LOCK_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_WRITER_LOCK_TIMEOUT
    return value if value > 0 else DEFAULT_WRITER_LOCK_TIMEOUT


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _holder_command() -> str:
    argv = list(sys.argv or [])
    if argv:
        argv[0] = Path(argv[0]).name
    return " ".join(argv)[:_HOLDER_COMMAND_LIMIT]


def _holder_record_path(lock_path: Path) -> Path:
    return lock_path.with_name(lock_path.name + ".holder")


def _is_lock_contention(exc: OSError) -> bool:
    """Is this OS error another live writer's byte lock, and nothing else?

    Both lock syscalls report a held range the same narrow way: msvcrt raises
    OSError(EACCES) and fcntl raises EACCES or EAGAIN/EWOULDBLOCK. Everything
    else -- EBADF, EIO, ENOLCK, or an OSError carrying no errno at all -- is a
    filesystem or programming failure that must never be dressed up as
    WRITER_BUSY with a retry story. T-1827 (SRC-282:R002) made this decisive:
    a generic OSError previously read as contention on Windows and an injected
    failure spun until the budget expired instead of surfacing.
    """
    return exc.errno in (
        getattr(errno, "EWOULDBLOCK", -1),
        getattr(errno, "EAGAIN", -1),
        getattr(errno, "EACCES", None),
        getattr(errno, "EDEADLK", None),
    )


def _write_holder_record(path: Path) -> dict | None:
    """Best-effort: record who holds the lock, for the next refusal to name.

    A sidecar, not the lock file: the lock file stays the permanent zero-byte
    mutex OPS.md documents, and Windows byte-range locks make its bytes
    unreadable to a diagnostic reader anyway. A failure here never fails the
    acquisition: identity is diagnostic, not part of the mutex.

    Returns the record written (so :meth:`WriterLock.release` can withdraw
    exactly its own bytes) or None.
    """
    record = {
        "schema": 1,
        "pid": os.getpid(),
        "acquired_at": _utc_now(),
        "command": _holder_command(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError:
        return None
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(record, sort_keys=True).encode("utf-8"))
    except OSError:
        return None
    return record


def _clear_holder_record(path: Path, written: dict | None) -> None:
    """Withdraw OUR record on release; never touch a successor's.

    SRC-282:R005 -- a holder record may not outlive its holder. The release is
    only diagnostic bytes, so the read-then-unlink is best effort: if another
    writer took the mutex in the window and rewrote the sidecar, the pid check
    leaves its record alone.
    """
    if not written:
        return
    current = _read_holder_record(path)
    if current is None:
        return
    if current.get("pid") != written.get("pid"):
        return
    if current.get("acquired_at") != written.get("acquired_at"):
        return
    with contextlib.suppress(OSError):
        os.unlink(path)


def _read_holder_record(path: Path) -> dict | None:
    """The last readable holder record, or None. Never creates or locks."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read(_HOLDER_RECORD_LIMIT)
    except OSError:
        return None
    if not raw:
        return None
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    pid = record.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    return record


def _holder_detail(record: dict | None) -> str:
    if record:
        command = str(record.get("command") or "").strip()
        acquired_at = str(record.get("acquired_at") or "").strip() or "an unrecorded time"
        if command:
            return (
                f"another live writer holds the project lock: pid {record['pid']} "
                f"since {acquired_at} running `{command}`"
            )
        return (
            "another live writer holds the project lock: "
            f"pid {record['pid']} since {acquired_at}"
        )
    return (
        "another live writer holds the project lock; the lock file carries no "
        "readable holder record, so the holder is unknown"
    )


def busy_detail(exc: BaseException) -> str:
    """The human detail behind a WRITER_BUSY exception, never a bare token."""
    detail = getattr(exc, "detail", "")
    if isinstance(detail, str) and detail.strip():
        return detail
    return "another live writer holds the project lock"


def writer_busy_payload(exc: BaseException) -> dict:
    """The structured WRITER_BUSY refusal every surface can emit."""
    payload: dict = {
        "ok": False,
        "code": "WRITER_BUSY",
        "detail": busy_detail(exc),
    }
    holder = getattr(exc, "holder", None)
    if isinstance(holder, dict) and holder:
        payload["holder"] = holder
    payload["remediation"] = (
        "Run `saipen lock status` to see who holds it. The OS lock is released "
        "when its holder process exits: wait for it, or stop only that recorded "
        "PID if it is an orphan. Never delete .saipen/locks/core.lock -- its "
        "existence is normal and deleting it releases nothing."
    )
    return payload


def _probe_locked(path: Path) -> bool | None:
    """True when a live writer holds the OS lock, False when free, None unknown.

    Read-only with respect to project bytes: never creates the lock file and
    never writes it. A free probe acquires the byte lock for an instant and
    releases it, so the answer is the real mutex, not a file's existence.
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return None
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        handle = os.fdopen(descriptor, "r+b", buffering=0)
    except OSError:
        os.close(descriptor)
        return None
    try:
        try:
            _os_lock(handle)
        except OSError:
            return True
        _os_unlock(handle)
        return False
    finally:
        handle.close()


def lock_status(project_root: Path | str) -> dict:
    """Read-only answer: who holds the project writer lock, or that it is free.

    Never acquires the canonical writer lock and never creates the lock file,
    so `saipen status`/`saipen lock status` stay usable during a hold.
    """
    root = Path(project_root)
    path = root / LOCK_DIR / "core.lock"
    payload = {
        "ok": True,
        "code": "LOCK_STATUS",
        "path": f"{LOCK_DIR}/core.lock",
        "held": False,
        "state": "free",
        "holder": None,
    }
    try:
        target = os.path.normcase(str(path))
    except OSError:
        target = ""
    with _HOLDERS_GUARD:
        in_process = next(
            (
                holder
                for holder in _WRITER_HOLDERS.values()
                if os.path.normcase(str(getattr(holder, "path", ""))) == target
            ),
            None,
        )
    record = _read_holder_record(_holder_record_path(path))
    if in_process is not None:
        payload.update(
            {
                "held": True,
                "state": "held",
                "holder": record,
                "detail": (
                    f"the project writer lock is held by this process (pid {os.getpid()})"
                ),
            }
        )
        return payload
    locked = _probe_locked(path)
    if locked is None:
        payload.update(
            {
                "state": "unknown",
                "detail": (
                    "cannot probe the project writer lock without following or "
                    "mutating its path; report this path for inspection"
                ),
            }
        )
        return payload
    if locked:
        payload.update(
            {
                "held": True,
                "state": "held",
                "holder": record,
                "detail": (
                    f"lock held by pid {record['pid']} since "
                    f"{record.get('acquired_at') or 'an unrecorded time'} running "
                    f"`{record.get('command')}`"
                    if record
                    else "lock is held; the holder record is missing or unreadable, "
                    "so the holder is unknown"
                ),
            }
        )
        return payload
    payload["last_holder"] = record
    payload["detail"] = (
        "the project writer lock is free"
        + (
            f"; last recorded holder was pid {record['pid']} "
            f"since {record.get('acquired_at') or 'an unrecorded time'}"
            if record
            else ""
        )
    )
    return payload


def _refused_write(folder: Path) -> bool:
    """True when this account can create no file in `folder`.

    Asked only after a lock open was refused: a refusal the folder shares is
    an access list, one it does not share is another process holding the file.
    """
    probe = folder / f".write-probe-{os.getpid()}-{threading.get_ident()}"
    try:
        descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except PermissionError:
        return True
    except OSError:
        return False
    os.close(descriptor)
    with contextlib.suppress(OSError):
        os.unlink(probe)
    return False


def not_writable(folder: Path) -> PermissionError:
    return PermissionError(
        f"{NOT_WRITABLE}: this account may not write {folder} (access denied); "
        "the project is granted to it for reading only"
    )


def _same_node(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino, left.st_mode) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
    )


def _owned_lock_path(lock_path: Path | str, ownership_root: Path | str) -> tuple[Path, Path]:
    """Map one lexical owner-relative path onto the canonical owner.

    A whole-owner alias is legitimate; symlink/reparse descendants are not.
    Mapping before descendant resolution preserves that distinction.
    """
    root_input = Path(os.path.abspath(ownership_root))
    path_input = Path(os.path.abspath(lock_path))
    try:
        relative = path_input.relative_to(root_input)
    except ValueError as exc:
        raise PermissionError(f"lock path escapes or has invalid owner: {exc}") from exc
    try:
        root = Path(ownership_root).resolve(strict=True)
    except (OSError, ValueError):
        # ownership root not yet on disk (e.g. global USERPERSON config dir
        # created on first write); use abspath projection, skip chain
        # validation until after mkdir proves the chain exists.
        root = root_input
    path = root / relative
    try:
        prove_owned_dir_chain(path.parent, kind="lock", ownership_root=root)
        path.parent.mkdir(parents=True, exist_ok=True)
        prove_owned_dir_chain(path.parent, kind="lock", ownership_root=root)
    except (OSError, ValueError) as exc:
        raise PermissionError(f"unsafe lock directory: {exc}") from exc
    return path, root


def _open_owned_lock(path: Path, root: Path):
    """Open/create the final mutex without following or trusting its name."""
    before = None
    try:
        before = prove_owned_regular(path, kind="lock file")
    except FileNotFoundError:
        pass
    except ValueError as exc:
        raise PermissionError(f"unsafe lock file: {exc}") from exc

    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        try:
            descriptor = os.open(path, flags, 0o600)
        except PermissionError as exc:
            if _refused_write(path.parent):
                raise not_writable(path.parent) from exc
            raise
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise PermissionError(f"unsafe lock file: {path} is not regular")
        prove_owned_dir_chain(path.parent, kind="lock", ownership_root=root)
        current = prove_owned_regular(path, kind="lock file")
        if not _same_node(opened, current):
            raise PermissionError(f"unsafe lock file: {path} changed during open")
        if before is not None and not _same_node(before, opened):
            raise PermissionError(f"unsafe lock file: {path} was replaced during open")
        handle = os.fdopen(descriptor, "r+b", buffering=0)
        descriptor = -1
        inode_key = f"inode:{opened.st_dev}:{opened.st_ino}"
        return handle, inode_key
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _reserve(
    registry: dict,
    key: str,
    owner: object,
    message: str,
    error_type: type[PermissionError] = PermissionError,
) -> None:
    with _HOLDERS_GUARD:
        holder = registry.get(key)
        if holder is not None and holder is not owner:
            raise error_type(message)
        registry[key] = owner


def _drop_reservation(registry: dict, key: str | None, owner: object) -> None:
    if key is None:
        return
    with _HOLDERS_GUARD:
        if registry.get(key) is owner:
            del registry[key]


def _promote_reservation(
    registry: dict,
    reservation_key: str,
    inode_key: str,
    owner: object,
    message: str,
    error_type: type[PermissionError] = PermissionError,
) -> None:
    with _HOLDERS_GUARD:
        if registry.get(reservation_key) is owner:
            del registry[reservation_key]
        holder = registry.get(inode_key)
        if holder is not None and holder is not owner:
            raise error_type(message)
        registry[inode_key] = owner


def _os_lock(handle, *, blocking: bool = False) -> None:
    handle.seek(0)
    if _MSVCRT is not None:
        mode = _MSVCRT.LK_LOCK if blocking else _MSVCRT.LK_NBLCK
        _MSVCRT.locking(handle.fileno(), mode, 1)
    else:
        mode = _FCNTL.LOCK_EX
        if not blocking:
            mode |= _FCNTL.LOCK_NB
        _FCNTL.flock(handle.fileno(), mode)


def _os_unlock(handle) -> None:
    handle.seek(0)
    if _MSVCRT is not None:
        _MSVCRT.locking(handle.fileno(), _MSVCRT.LK_UNLCK, 1)
    else:
        _FCNTL.flock(handle.fileno(), _FCNTL.LOCK_UN)


class FileLockBusy(PermissionError):
    """The non-project lock exists but another writer currently owns it."""


class FileWriterLock:
    """Exclusive lock for one non-project-owned file namespace.

    This is deliberately separate from :class:`WriterLock`: callers provide
    an exact lock path and an ownership root, so user configuration can use
    the same OS-lock discipline without fabricating a project or touching its
    ``.saipen`` journal/lock tree. Construction is mutating because it creates
    the lock directory; read-only callers must never instantiate it.
    """

    def __init__(
        self,
        lock_path: Path | str,
        ownership_root: Path | str,
        *,
        blocking: bool = False,
    ) -> None:
        self.path, self._root = _owned_lock_path(lock_path, ownership_root)
        self._handle = None
        self._acquired = False
        self._holder_key: str | None = None
        self._blocking = blocking

    def acquire(self) -> bool:
        if self._acquired:
            return True
        reservation = "path:" + os.path.normcase(str(self.path))
        _reserve(
            _FILE_HOLDERS,
            reservation,
            self,
            "WRITER_BUSY",
            error_type=FileLockBusy,
        )
        try:
            self._handle, inode_key = _open_owned_lock(self.path, self._root)
            _promote_reservation(
                _FILE_HOLDERS,
                reservation,
                inode_key,
                self,
                "WRITER_BUSY",
                error_type=FileLockBusy,
            )
            self._holder_key = inode_key
            try:
                _os_lock(self._handle, blocking=self._blocking)
            except OSError as exc:
                # On Windows msvcrt uses PermissionError for a held byte
                # range.  Once the file itself was proven owned, every such
                # error is lock contention, not an arbitrary filesystem
                # failure; normalize it for non-blocking callers.
                raise FileLockBusy("WRITER_BUSY") from exc
        except BaseException as exc:
            if self._handle is not None:
                self._handle.close()
            self._handle = None
            _drop_reservation(_FILE_HOLDERS, reservation, self)
            _drop_reservation(_FILE_HOLDERS, self._holder_key, self)
            self._holder_key = None
            if isinstance(exc, OSError) and not isinstance(exc, PermissionError):
                raise FileLockBusy("WRITER_BUSY") from exc
            raise
        self._acquired = True
        return True

    def release(self) -> None:
        if not self._acquired or self._handle is None:
            return
        try:
            _os_unlock(self._handle)
        finally:
            self._handle.close()
            self._handle = None
            self._acquired = False
            _drop_reservation(_FILE_HOLDERS, self._holder_key, self)
            self._holder_key = None

    def __enter__(self) -> "FileWriterLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


@contextlib.contextmanager
def file_writer_lock(
    lock_path: Path | str,
    ownership_root: Path | str,
    *,
    blocking: bool = False,
):
    """Acquire a non-project writer lock with containment enforcement."""
    lock = FileWriterLock(lock_path, ownership_root, blocking=blocking)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()


class WriterLock:
    """An exclusive OS lock on the project's canonical lock file."""

    def __init__(self, project_root: Path | str, *, timeout: float | None = None) -> None:
        root = Path(project_root)
        lock_dir = root / LOCK_DIR
        self.path, self._root = _owned_lock_path(lock_dir / "core.lock", root)
        self._handle = None
        self._acquired = False
        self._holder_key: str | None = None
        # The record this acquisition wrote, withdrawn on release (R005).
        self._holder_record: dict | None = None
        # None defers to SAIPEN_WRITER_LOCK_TIMEOUT at acquisition time.
        # 0 keeps the probe semantics for callers that own their retry loop.
        self._timeout = timeout

    def wait_budget(self) -> float:
        """The whole-acquisition deadline in seconds, never unbounded."""
        if self._timeout is None:
            return writer_lock_timeout()
        try:
            return max(0.0, float(self._timeout))
        except (TypeError, ValueError):
            return writer_lock_timeout()

    def _os_lock_bounded(self) -> None:
        """Take the byte lock within one deadline, or raise WriterBusy.

        The OS call itself stays non-blocking: a blocking msvcrt lock cannot
        be interrupted, and its holder record must be readable on refusal.
        A non-contention OS failure is re-raised as itself, never retried as
        if waiting could clear it.
        """
        budget = self.wait_budget()
        deadline = time.monotonic() + budget
        while True:
            try:
                _os_lock(self._handle)
                return
            except OSError as exc:
                if not _is_lock_contention(exc):
                    raise
                last = exc
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                record = _read_holder_record(_holder_record_path(self.path))
                detail = _holder_detail(record)
                if budget > 0:
                    detail += f" (waited {budget:.1f}s)"
                raise WriterBusy(detail, holder=record) from last
            time.sleep(min(_LOCK_RETRY_SLEEP, remaining))

    def acquire(self, timeout: float | None = None) -> bool:
        """Exclusive project writer lock, bounded wait; True or WriterBusy.

        A short legitimate hold resolves by waiting within the declared budget
        (``SAIPEN_WRITER_LOCK_TIMEOUT``, default 5 s); a long one still refuses
        in bounded time with the holder's PID and command when its record is
        readable. The raised :class:`WriterBusy` is a ``PermissionError`` whose
        ``str()`` remains exactly ``WRITER_BUSY``.

        ``timeout`` overrides this lock's budget for one acquisition (used by
        a yielded re-acquisition that must not wait longer than its own
        declared critical section); ``None`` keeps the constructed budget.

        W2-002: uses an atomic process-local reservation BEFORE the OS lock
        so two same-process threads cannot both enter the critical section
        on Windows-like reentrant OS locking. That reservation refuses at
        once, without waiting: waiting cannot free a same-process holder.
        """
        if self._acquired:
            return True
        if timeout is not None:
            self._timeout = timeout
        reservation = "path:" + os.path.normcase(str(self.path))
        try:
            _reserve(_WRITER_HOLDERS, reservation, self, "WRITER_BUSY")
        except PermissionError as exc:
            raise WriterBusy(
                "this process already holds the project writer lock; waiting "
                "cannot free a same-process holder"
            ) from exc
        try:
            self._handle, inode_key = _open_owned_lock(self.path, self._root)
            _promote_reservation(_WRITER_HOLDERS, reservation, inode_key, self, "WRITER_BUSY")
            self._holder_key = inode_key
            try:
                self._os_lock_bounded()
            except OSError as exc:
                # Once the owned lock file opened successfully, an OS-lock
                # collision is contention. Windows msvcrt reports it as the
                # same raw PermissionError used for unsafe filesystem paths;
                # normalize only this post-open boundary to WRITER_BUSY.
                # WriterBusy already carries the holder record; any other
                # failure keeps its own identity.
                if isinstance(exc, WriterBusy):
                    raise
                if isinstance(exc, PermissionError):
                    raise
                if not _is_lock_contention(exc):
                    raise
                raise WriterBusy(_holder_detail(None)) from exc
            self._holder_record = _write_holder_record(_holder_record_path(self.path))
        except BaseException as exc:
            if self._handle is not None:
                self._handle.close()
            self._handle = None
            _drop_reservation(_WRITER_HOLDERS, reservation, self)
            _drop_reservation(_WRITER_HOLDERS, self._holder_key, self)
            self._holder_key = None
            if (
                isinstance(exc, OSError)
                and not isinstance(exc, PermissionError)
                and _is_lock_contention(exc)
            ):
                raise WriterBusy(_holder_detail(None)) from exc
            raise
        self._acquired = True
        return True

    def release(self) -> None:
        if not self._acquired or self._handle is None:
            return
        try:
            _os_unlock(self._handle)
        finally:
            self._handle.close()
            self._handle = None
            self._acquired = False
            _drop_reservation(_WRITER_HOLDERS, self._holder_key, self)
            self._holder_key = None
            _clear_holder_record(_holder_record_path(self.path), self._holder_record)
            self._holder_record = None

    def __enter__(self) -> "WriterLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


@contextlib.contextmanager
def project_writer_lock(project_root: Path | str, *, timeout: float | None = None):
    """Take the canonical project writer lock for the block.

    Waits up to the declared budget (``SAIPEN_WRITER_LOCK_TIMEOUT``, default
    5 s) and raises ``WriterBusy`` -- a ``PermissionError`` whose ``str()`` is
    exactly ``WRITER_BUSY`` -- when another live writer still holds it.
    """
    lock = WriterLock(project_root, timeout=timeout)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()


@contextlib.contextmanager
def writer_lock_yielded(lock: WriterLock, *, timeout: float | None = None):
    """Release a HELD writer lock around an external process, then take it back.

    T-1827 (SRC-282:R003): a validator or verification subprocess can run for
    minutes, and holding the only writer mutex across it makes every other
    mutation refuse WRITER_BUSY for that whole span. The candidate gate runs in
    this window instead, so the lock is held for the local read/verify work
    only.

    The caller MUST re-prove its own preconditions after the window closes:
    another writer may have run while the lock was free. A re-acquisition that
    loses the race raises ``WriterBusy`` -- the caller then no longer holds the
    mutex and must treat its operation as unresolved rather than write.

    ``timeout`` bounds only the re-acquisition; ``None`` keeps the budget the
    lock was constructed with.
    """
    lock.release()
    try:
        yield
    finally:
        lock.acquire(timeout=timeout)


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
        self.producer = producer
        self.path, self._root = _owned_lock_path(lock_dir / f"producer-{producer}.lock", root)
        self._handle = None
        self._acquired = False
        self._holder_key: str | None = None

    def acquire(self) -> bool:
        """Blocking-exclusive, non-blocking acquire. Raises WRITER_BUSY on conflict.

        W2-002: uses an atomic process-local reservation BEFORE the OS lock
        so two same-process threads cannot both enter the critical section
        on Windows-like reentrant OS locking.
        """
        if self._acquired:
            return True
        message = f"PRODUCER_BUSY: {self.producer} is already writing"
        reservation = "path:" + os.path.normcase(str(self.path))
        _reserve(_PRODUCER_HOLDERS, reservation, self, message)
        try:
            self._handle, inode_key = _open_owned_lock(self.path, self._root)
            _promote_reservation(_PRODUCER_HOLDERS, reservation, inode_key, self, message)
            self._holder_key = inode_key
            try:
                _os_lock(self._handle)
            except OSError as exc:
                # msvcrt reports another process holding the byte range as
                # raw PermissionError.  The open/provenance checks already
                # passed, so expose the producer-specific stable code.
                raise PermissionError(message) from exc
        except BaseException as exc:
            if self._handle is not None:
                self._handle.close()
            self._handle = None
            _drop_reservation(_PRODUCER_HOLDERS, reservation, self)
            _drop_reservation(_PRODUCER_HOLDERS, self._holder_key, self)
            self._holder_key = None
            if isinstance(exc, OSError) and not isinstance(exc, PermissionError):
                raise PermissionError(message) from exc
            raise
        self._acquired = True
        return True

    def release(self) -> None:
        if not self._acquired or self._handle is None:
            return
        try:
            _os_unlock(self._handle)
        finally:
            self._handle.close()
            self._handle = None
            self._acquired = False
            _drop_reservation(_PRODUCER_HOLDERS, self._holder_key, self)
            self._holder_key = None

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

"""Project resolution and the canonical paths under `.saipen/`.

Behaviour is `tools/validate.py._resolve_project_root`, moved rather than
rewritten: explicit selection wins, then the ACTIVE Git worktree, then the main
worktree via `--git-common-dir`, then the nearest ancestor carrying `.saipen/`.
The worktree-before-common order is not a detail — asking git-common first once
made the validator read a different tree than the agent was editing and report
green for the wrong repository.

TWO identities, never one (T-1003 carrier-loss wave):

1. `project_identity` / `runtime_lock_identity` — machine-local
   (`os.path.realpath` + `normcase`). It exists for the lock and journal
   runtime binding: two paths that reach the same project (a symlink, a
   substituted drive, a case-different Windows path) must produce ONE identity,
   or the single-writer guarantee is a single writer per spelling. It is NEVER
   durable portable evidence: moving the project changes it.

2. `project_lineage_identity` — a durable PORTABLE lineage stored canonically
   in the tracked `.saipen/IDENTITY.md`. It survives directory moves, machine
   replacement, Git clone and `saipen export`, and differs between unrelated
   initialized projects (a random lineage id, so two no-git projects sharing a
   folder name or two forks sharing a remote are still distinct). Journals,
   evidence and recovery bind to THIS identity. Moving the carrier must not
   change the meaning of the project.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

SAIPEN_DIR = ".saipen"
STATE_NAME = "STATE.md"
BOARD_NAME = "BOARD.md"
LOG_NAME = "LOG.md"
LOGS_DIR = "logs"
LOCKS_DIR = "locks"
RECOVERY_OPS_DIR = "recovery/ops"
IDENTITY_NAME = "IDENTITY.md"
LINEAGE_FIELD = "project_lineage"
LINEAGE_RE = re.compile(r"^lineage-[0-9a-f]{32}$")


def read_bound_regular_bytes(path: Path, expected: os.stat_result, *, max_bytes: int) -> bytes:
    """Read the exact regular node witnessed by an earlier ``lstat``.

    The descriptor, not the pathname, owns the read. Comparing ``fstat``
    before and after the bounded read with the caller's no-follow ``lstat``
    closes the lstat/open race even on hosts without ``O_NOFOLLOW``: a path
    pivot may open another node, but that descriptor cannot impersonate the
    node the caller inspected.

    Raises ``OSError`` for an unreadable path and ``ValueError`` when the path
    pivoted, the descriptor is not stable/regular, or the authority exceeds
    its explicit size bound.
    """

    def identity(info: os.stat_result) -> tuple[int, int, int, int]:
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_before.st_mode)
            or identity(opened_before) != identity(expected)
            or opened_before.st_size > max_bytes
        ):
            raise ValueError(f"authority node changed before open: {path}")
        remaining = max_bytes + 1
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        opened_after = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_after.st_mode)
            or identity(opened_before) != identity(opened_after)
            or len(raw) != opened_before.st_size
            or len(raw) > max_bytes
        ):
            raise ValueError(f"authority node changed while reading: {path}")
        return raw
    finally:
        os.close(descriptor)


_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def prove_owned_regular(path: Path, *, kind: str = "path") -> os.stat_result:
    """Prove `path` is an owned regular non-link/non-reparse final node.

    Uses no-follow ``lstat`` semantics: a final symlink/junction/reparse or
    non-regular node is refused regardless of where it points. Raises
    ``FileNotFoundError`` when absent and ``ValueError`` on any unsafe/other
    topology. Returns the witnessed ``lstat`` result for a bounded read.
    """
    try:
        st = path.lstat()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ValueError(f"{kind} {path} is unreadable: {exc}") from None
    if os.path.islink(path) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE):
        raise ValueError(f"{kind} {path} is a link/reparse node")
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"{kind} {path} is not a regular file")
    return st


def prove_owned_dir_chain(
    dir_path: Path,
    *,
    kind: str = "dir",
    ownership_root: Path | None = None,
) -> None:
    """Prove every existing ancestor component (and the final directory) of
    ``dir_path`` is an owned non-link/non-reparse directory.

    Raises ``ValueError`` on any symlink/junction/reparse/non-directory
    ancestor. Absent leaf components are permitted (they are created later by
    the caller under proven ancestors).
    """
    absolute = Path(os.path.abspath(dir_path))
    if ownership_root is not None:
        owner = Path(os.path.abspath(ownership_root))
        if absolute != owner and not absolute.is_relative_to(owner):
            raise ValueError(f"{kind} {absolute} escapes ownership root {owner}")
    chain = list(reversed((absolute, *absolute.parents)))
    for node in chain:
        try:
            st = node.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"{kind} ancestor {node} unreadable: {exc}") from None
        if os.path.islink(node) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE):
            raise ValueError(f"{kind} ancestor {node} is a link/reparse node")
        if not stat.S_ISDIR(st.st_mode):
            raise ValueError(f"{kind} ancestor {node} is not a directory")


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino, left.st_mode) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
    )


def _open_exclusive_regular(path: Path, *, kind: str) -> tuple[int, os.stat_result]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise ValueError(f"{kind} {path} already exists") from None
    try:
        witnessed = os.fstat(descriptor)
        if not stat.S_ISREG(witnessed.st_mode):
            raise ValueError(f"{kind} {path} is not a regular file")
        current = path.lstat()
        if not _same_stat(witnessed, current):
            raise ValueError(f"{kind} {path} changed during exclusive creation")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, witnessed


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("short write to owned file descriptor")
        view = view[written:]
    os.fsync(descriptor)


def safe_create_bytes_exclusive(
    path: Path,
    data: bytes,
    *,
    kind: str = "path",
    ownership_root: Path | None = None,
) -> None:
    """Create one owned regular file exactly once and write through its fd."""
    path = Path(path)
    prove_owned_dir_chain(
        path.parent,
        kind=kind,
        ownership_root=ownership_root,
    )
    descriptor, witnessed = _open_exclusive_regular(path, kind=kind)
    try:
        _write_all(descriptor, data)
        current = path.lstat()
        if not _same_stat(witnessed, current):
            raise ValueError(f"{kind} {path} changed while being written")
    except BaseException:
        with suppress(OSError):
            current = path.lstat()
            if _same_stat(witnessed, current):
                os.unlink(path)
        raise
    finally:
        os.close(descriptor)


def safe_atomic_write_bytes(
    path: Path,
    data: bytes,
    *,
    kind: str = "path",
    ownership_root: Path | None = None,
) -> None:
    """Owned same-directory atomic replacement for a project file.

    Proves the ancestor chain is owned directories, refuses a linked/reparse or
    non-regular existing final node, writes to a uniquely-named temporary in the
    SAME directory (so ``replace`` cannot cross a mount), and atomically
    replaces the target. Raises ``ValueError`` on any unsafe topology.
    """
    path = Path(path)
    parent = path.parent
    prove_owned_dir_chain(parent, kind=kind, ownership_root=ownership_root)
    parent.mkdir(parents=True, exist_ok=True)
    prove_owned_dir_chain(parent, kind=kind, ownership_root=ownership_root)
    before = None
    with suppress(FileNotFoundError):
        before = prove_owned_regular(path, kind=kind)
    tmp_path = parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor, tmp_stat = _open_exclusive_regular(tmp_path, kind=f"{kind} temporary")
    try:
        _write_all(descriptor, data)
        os.close(descriptor)
        descriptor = -1
        prove_owned_dir_chain(parent, kind=kind, ownership_root=ownership_root)
        try:
            current = prove_owned_regular(path, kind=kind)
        except FileNotFoundError:
            current = None
        if (before is None) != (current is None) or (
            before is not None and current is not None and not _same_stat(before, current)
        ):
            raise ValueError(f"{kind} {path} changed before atomic replacement")
        tmp_current = prove_owned_regular(tmp_path, kind=f"{kind} temporary")
        if not _same_stat(tmp_stat, tmp_current):
            raise ValueError(f"{kind} temporary {tmp_path} changed before replacement")
        os.replace(tmp_path, path)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        with suppress(OSError, ValueError):
            current = prove_owned_regular(tmp_path, kind=f"{kind} temporary")
            if _same_stat(tmp_stat, current):
                os.unlink(tmp_path)
        raise


def safe_unlink_owned(
    path: Path,
    *,
    kind: str = "path",
    ownership_root: Path | None = None,
) -> bool:
    """Unlink an owned regular file, no-follow. Returns False (no-op) when the
    file does not exist; raises ValueError on a linked/reparse/non-regular
    final node or unsafe ancestor chain so an unsafe carrier is never silently
    deleted."""
    path = Path(path)
    prove_owned_dir_chain(
        path.parent,
        kind=kind,
        ownership_root=ownership_root,
    )
    try:
        prove_owned_regular(path, kind=kind)
    except FileNotFoundError:
        return False
    os.unlink(path)
    return True


def _git_from(cwd: str | Path, *args: str) -> tuple[int, str]:
    """Run git in `cwd`. Never raises: this runs from pre-commit hooks and in
    directories that are not repositories at all."""
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return result.returncode, result.stdout.strip()


def is_git_project_root(root: Path) -> bool:
    """True if this project root is its own independent Git repository.
    A child project nested inside an unrelated parent repository is NOT a Git
    project of its own."""
    root = root.resolve()
    rc, top_text = _git_from(root, "rev-parse", "--show-toplevel")
    if rc == 0 and top_text:
        try:
            return Path(top_text).resolve() == root
        except OSError:
            return False
    return False


def _valid_saipen_dir(root: Path) -> bool:
    saipen = root / SAIPEN_DIR
    if not saipen.is_dir():
        return False
    try:
        if saipen.is_symlink():
            return False
        # Reparse point check (Windows junctions)
        st = saipen.lstat()
        if getattr(st, "st_file_attributes", 0) & 0x400:
            return False
    except OSError:
        return False
    return True


def _nearest_checkpoint_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if _valid_saipen_dir(candidate):
            return candidate
    return None


def resolve_project_root(
    start: Path | None = None, explicit: str | Path | None = None
) -> tuple[Path | None, str]:
    """Resolve the one root whose checkpoint files this run may touch.

    Returns `(root, source)` on success and `(None, reason)` on refusal. It
    refuses rather than creating a `.saipen/`: inventing a second checkpoint
    directory is how a session's history silently forks.
    """
    start = (start or Path.cwd()).resolve()

    if explicit is not None:
        root = Path(explicit).expanduser()
        if not root.is_absolute():
            root = start / root
        root = root.resolve()
        if not root.is_dir():
            return None, f"explicit --project-root is not a directory: {root}"
        if not _valid_saipen_dir(root):
            return None, f"explicit --project-root has no .saipen/ directory: {root}"
        return root, "explicit"

    rc, top_text = _git_from(start, "rev-parse", "--show-toplevel")
    if rc == 0 and top_text:
        worktree_root = Path(top_text).resolve()
        common_rc, common_text = _git_from(start, "rev-parse", "--git-common-dir")
        candidates: list[tuple[Path, str]] = [(worktree_root, "git-worktree")]
        if common_rc == 0 and common_text:
            common_dir = Path(common_text)
            if not common_dir.is_absolute():
                common_dir = start / common_dir
            common_dir = common_dir.resolve()
            if common_dir.name.lower() == ".git":
                candidates.append((common_dir.parent, "git-common"))
        seen: set[str] = set()
        for root, source in candidates:
            key = os.path.normcase(str(root))
            if key in seen:
                continue
            seen.add(key)
            if _valid_saipen_dir(root):
                return root, source
        return None, (
            f"cwd belongs to Git worktree {worktree_root} but its "
            f"owning repository has no .saipen/; refusing to guess "
            f"or create a second .saipen/. Run from the intended "
            f"project or pass --project-root PATH"
        )

    root = _nearest_checkpoint_root(start)
    if root is not None:
        return root, "ancestor"
    return None, (
        "cwd has no owning .saipen/; refusing to guess or create "
        "one. Run from the intended project or pass "
        "--project-root PATH"
    )


def project_identity(root: Path) -> str:
    """One stable RUNTIME identity per project, whatever path spelled it.

    `os.path.realpath` collapses symlinks and junctions; `normcase` collapses
    the case and separator differences Windows treats as the same file. Without
    both, `V:\\proj` and `v:/proj/` are two writers holding two locks over one
    set of files.

    This is the machine-local lock/journal-runtime identity. It must never be
    treated as durable portable evidence: moving the project changes it. Durable
    portable binding uses `project_lineage_identity` instead.
    """
    return os.path.normcase(os.path.realpath(str(root)))


def runtime_lock_identity(root: Path | str) -> str:
    """Machine-local lock identity: aliases of one project share it.

    Never persisted as durable evidence. Two path spellings of one project
    (symlink, junction, case difference) must collapse to one value so two
    spellings cannot take two writer locks.
    """
    return project_identity(Path(root))


def new_project_lineage() -> str:
    """A fresh portable project lineage id (random: unrelated projects differ
    even when they share a remote, a folder name, or both)."""
    return "lineage-" + uuid.uuid4().hex


def identity_file_content(lineage: str) -> str:
    """Canonical tracked content of `.saipen/IDENTITY.md`."""
    return f"---\n{LINEAGE_FIELD}: {lineage}\n---\n"


def parse_identity_content(text: str) -> tuple[str | None, str | None]:
    """STRICT canonical parse of `.saipen/IDENTITY.md` content (T-1003
    carrier-loss wave).

    The canonical form is exactly one frontmatter fence holding exactly one
    `project_lineage:` field naming a lineage-id:

        ---
        project_lineage: lineage-<hex32>
        ---

    Duplicate fields, a missing/broken fence, a second lineage field, or any
    other body content ("body garbage") are all INVALID -- a carrier is the
    project's only durable portable identity, so leniency here is how one
    project silently becomes another. Returns (lineage, None) on success and
    (None, error) on any malformation.
    """
    if not text or not text.strip():
        return None, "identity file is empty"
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return None, "missing opening --- frontmatter fence"
    if len(lines) < 3 or lines[-1].strip() != "---":
        return None, "missing closing --- frontmatter fence"
    body = lines[1:-1]
    body_lines = [line for line in body if line.strip()]
    if len(body_lines) != 1:
        return None, (
            "canonical IDENTITY.md holds exactly one lineage field "
            "inside the fence; found "
            f"{len(body_lines)} non-empty line(s)"
        )
    line = body_lines[0]
    match = re.fullmatch(rf"{re.escape(LINEAGE_FIELD)}:\s*(\S+)\s*", line)
    if not match:
        return None, f"unexpected identity body line {line!r}"
    value = match.group(1)
    if not LINEAGE_RE.match(value):
        return None, f"lineage value {value!r} fails the lineage-id grammar"
    return value, None


def project_lineage_identity(root: Path | str) -> str | None:
    """The durable portable lineage of this project, or None.

    Reads the tracked `.saipen/IDENTITY.md` and validates the canonical
    carrier grammar (one fenced lineage field, no body garbage). None means:
    project not yet migrated, or the identity file is missing/malformed. A
    missing/malformed lineage is fail-closed material for NEW strict receipts
    -- it must never silently become "same project".
    """
    root = Path(root)
    saipen = root / SAIPEN_DIR
    path = saipen / IDENTITY_NAME
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    def identity(info) -> tuple[int, int, int, int]:
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

    try:
        saipen_before = saipen.lstat()
        path_before = path.lstat()
    except (FileNotFoundError, OSError):
        return None
    if (
        os.path.islink(saipen)
        or bool(getattr(saipen_before, "st_file_attributes", 0) & reparse_flag)
        or not stat.S_ISDIR(saipen_before.st_mode)
        or os.path.islink(path)
        or bool(getattr(path_before, "st_file_attributes", 0) & reparse_flag)
        or not stat.S_ISREG(path_before.st_mode)
        or path_before.st_size > 4096
    ):
        return None
    try:
        raw = read_bound_regular_bytes(path, path_before, max_bytes=4096)
        path_after = path.lstat()
        saipen_after = saipen.lstat()
    except (OSError, ValueError):
        return None
    if (
        os.path.islink(saipen)
        or bool(getattr(saipen_after, "st_file_attributes", 0) & reparse_flag)
        or not stat.S_ISDIR(saipen_after.st_mode)
        or os.path.islink(path)
        or bool(getattr(path_after, "st_file_attributes", 0) & reparse_flag)
        or not stat.S_ISREG(path_after.st_mode)
        or identity(saipen_before) != identity(saipen_after)
        or identity(path_before) != identity(path_after)
        or raw.startswith(b"\xef\xbb\xbf")
    ):
        return None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    lineage, _error = parse_identity_content(text)
    return lineage


@dataclass(frozen=True)
class ProjectPaths:
    """Every canonical path an operation may touch, derived once."""

    root: Path

    @property
    def saipen(self) -> Path:
        return self.root / SAIPEN_DIR

    @property
    def state(self) -> Path:
        return self.saipen / STATE_NAME

    @property
    def board(self) -> Path:
        return self.saipen / BOARD_NAME

    @property
    def log(self) -> Path:
        return self.saipen / LOG_NAME

    @property
    def sealed_logs(self) -> list[Path]:
        from .log import history_paths

        return [p for p in history_paths(self.root) if p.name != "LOG.md"]

    @property
    def lock(self) -> Path:
        return self.saipen / LOCKS_DIR / "core.lock"

    @property
    def recovery_ops(self) -> Path:
        return self.saipen / RECOVERY_OPS_DIR

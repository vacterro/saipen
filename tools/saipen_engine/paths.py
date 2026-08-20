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
import subprocess
import uuid
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
    path = Path(root) / SAIPEN_DIR / IDENTITY_NAME
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
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

"""Project resolution and the canonical paths under `.saipen/`.

Behaviour is `tools/validate.py._resolve_project_root`, moved rather than
rewritten: explicit selection wins, then the ACTIVE Git worktree, then the main
worktree via `--git-common-dir`, then the nearest ancestor carrying `.saipen/`.
The worktree-before-common order is not a detail — asking git-common first once
made the validator read a different tree than the agent was editing and report
green for the wrong repository.

`project_identity` exists for the lock and the journal: two paths that reach the
same project (a symlink, a substituted drive, a case-different Windows path)
must produce ONE identity, or the single-writer guarantee is a single writer per
spelling.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

SAIPEN_DIR = ".saipen"
STATE_NAME = "STATE.md"
BOARD_NAME = "BOARD.md"
LOG_NAME = "LOG.md"
LOGS_DIR = "logs"
LOCKS_DIR = "locks"
RECOVERY_OPS_DIR = "recovery/ops"


def _git_from(cwd: str | Path, *args: str) -> tuple[int, str]:
    """Run git in `cwd`. Never raises: this runs from pre-commit hooks and in
    directories that are not repositories at all."""
    try:
        result = subprocess.run(["git", *args], cwd=str(cwd),
                                capture_output=True, text=True, check=False)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return result.returncode, result.stdout.strip()


def _nearest_checkpoint_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / SAIPEN_DIR).is_dir():
            return candidate
    return None


def resolve_project_root(start: Path | None = None,
                         explicit: str | Path | None = None
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
            return None, f"explicit project root is not a directory: {root}"
        if not (root / SAIPEN_DIR).is_dir():
            return None, f"explicit project root has no .saipen/: {root}"
        return root, "explicit"

    rc, top_text = _git_from(start, "rev-parse", "--show-toplevel")
    if rc == 0 and top_text:
        worktree_root = Path(top_text).resolve()
        common_rc, common_text = _git_from(start, "rev-parse",
                                           "--git-common-dir")
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
            if (root / SAIPEN_DIR).is_dir():
                return root, source
        return None, (f"cwd belongs to Git worktree {worktree_root} but its "
                      f"owning repository has no .saipen/; refusing to guess "
                      f"or create a second one")

    root = _nearest_checkpoint_root(start)
    if root is not None:
        return root, "ancestor"
    return None, ("cwd has no owning .saipen/; refusing to guess or create "
                  "one")


def project_identity(root: Path) -> str:
    """One stable identity per project, whatever path spelled it.

    `os.path.realpath` collapses symlinks and junctions; `normcase` collapses
    the case and separator differences Windows treats as the same file. Without
    both, `V:\\proj` and `v:/proj/` are two writers holding two locks over one
    set of files.
    """
    return os.path.normcase(os.path.realpath(str(root)))


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
        directory = self.saipen / LOGS_DIR
        if not directory.is_dir():
            return []
        return sorted(directory.glob("LOG-*.md"))

    @property
    def lock(self) -> Path:
        return self.saipen / LOCKS_DIR / "core.lock"

    @property
    def recovery_ops(self) -> Path:
        return self.saipen / RECOVERY_OPS_DIR

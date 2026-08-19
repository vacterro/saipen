"""Project snapshot -- the stale-operation guard (NITRO M1).

Before any mutating operation the snapshot records the canonical files and
their hashes; immediately before committing, the operation re-reads the
affected files and REFUSES if a precondition hash changed. This is optimistic
concurrency and the sequential precursor of v8 stale-plan refusal.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def canonical_identity(project_root: Path) -> str:
    """Canonical project identity, not raw path spelling.

    Two aliases to the same project must yield the same identity (used by the
    lock and the cycle id). ONE implementation owns this: paths.project_identity
    (normcase + realpath). Keep it here as the single public name the lock and
    snapshot consume.
    """
    from .paths import project_identity

    return project_identity(project_root)


def git_head(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


@dataclass(frozen=True)
class ProjectSnapshot:
    project_root: Path
    project_identity: str
    state_hash: str = ""
    board_hash: str = ""
    log_hash: str = ""
    log_tail: int | None = None
    head: str = ""
    # T-1014: the parsed events from the SAME one-pass snapshot that fed
    # log_hash/log_tail -- a command that captures the snapshot once can
    # derive the ledger verdict, the hash, the tail AND the events from that
    # single read instead of reopening the complete LOG history per consumer.
    history_events: tuple = ()

    @staticmethod
    def capture(project_root: Path | str) -> "ProjectSnapshot":
        root = Path(project_root)
        state = root / ".saipen" / "STATE.md"
        board = root / ".saipen" / "BOARD.md"
        from .log import read_history_snapshot

        history = read_history_snapshot(root)
        return ProjectSnapshot(
            project_root=root,
            project_identity=canonical_identity(root),
            state_hash=_sha256(state),
            board_hash=_sha256(board),
            log_hash=history.hash,
            log_tail=history.tail,
            head=git_head(root),
            history_events=history.events,
        )

    def stale(self, project_root: Path | str) -> bool:
        """True if any canonical precondition hash differs from the snapshot."""
        fresh = ProjectSnapshot.capture(project_root)
        return (
            fresh.state_hash != self.state_hash
            or fresh.board_hash != self.board_hash
            or fresh.log_hash != self.log_hash
        )

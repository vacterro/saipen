"""ProjectSnapshot — what the plan was decided against.

Read the canonical files once, hash them, and hold the parsed result together
with those hashes. Every mutating operation is planned against a snapshot and,
immediately before committing, re-reads the affected files: if any precondition
hash moved, the operation is REFUSED rather than applied, because a decision
made against state that no longer exists is not a decision about this
repository.

That is optimistic concurrency in its sequential form. v8 adds workers, claims
and epochs on top of it; the point of building it now is that v8 should not be
inventing transaction semantics while also inventing concurrency.

Nothing here writes. M1 is read-only by design.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .board import BoardDocument, parse_board
from .codec import Document, load_document
from .errors import StaleSnapshotError
from .log import LogDocument, parse_log
from .paths import ProjectPaths, project_identity
from .state import StateRecord, parse_state

# CORE section 1.2's closed ticket-field list. Held here so both the engine and
# the validator can be handed the same set instead of each carrying a copy.
KNOWN_TICKET_FIELDS = frozenset({
    "needs", "owner", "claim_time", "blocker", "verify",
    "review_passes", "verify_attempts",
})


def _head(root: Path) -> str | None:
    """Current commit, or None where this is not a Git repository.

    Not being a repository is a normal, supported state — `requires: git` is a
    project's own declaration, not this module's assumption — so it returns
    None instead of raising.
    """
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                                capture_output=True, text=True, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    out = result.stdout.strip()
    return out if result.returncode == 0 and out else None


@dataclass
class ProjectSnapshot:
    """One coherent read of a project's canonical state."""

    root: Path
    identity: str
    paths: ProjectPaths
    state_doc: Document
    board_doc: Document
    log_doc: Document
    state: StateRecord
    board: BoardDocument
    log: LogDocument
    head: str | None = None
    sealed_log_ids: list[int] = field(default_factory=list)

    # ---------------------------------------------------------------- hashes

    @property
    def state_hash(self) -> str:
        return self.state_doc.raw_sha256

    @property
    def board_hash(self) -> str:
        return self.board_doc.raw_sha256

    @property
    def log_hash(self) -> str:
        return self.log_doc.raw_sha256

    @property
    def log_tail(self) -> int:
        return self.log.tail_id

    def preconditions(self) -> dict[str, object]:
        """The exact facts a plan is allowed to depend on.

        A plan declares these; apply rechecks them under the writer lock. Both
        sides read the same dictionary shape so a precondition cannot be
        checked in one place and forgotten in the other.
        """
        return {
            "project_identity": self.identity,
            "state_hash": self.state_hash,
            "board_hash": self.board_hash,
            "log_hash": self.log_hash,
            "log_tail": self.log_tail,
            "head": self.head,
        }

    def assert_fresh(self, preconditions: dict[str, object]) -> None:
        """Refuse when this snapshot disagrees with the one a plan was built on.

        `head` is deliberately excluded: a commit can land between planning and
        applying without changing one byte of the three canonical files, and
        refusing on that would make every operation during an ordinary commit
        fail for no reason. The file hashes are the preconditions that matter.
        """
        current = self.preconditions()
        moved = [key for key in ("project_identity", "state_hash",
                                 "board_hash", "log_hash", "log_tail")
                 if key in preconditions and preconditions[key] != current[key]]
        if moved:
            detail = ", ".join(
                f"{key}: planned {preconditions[key]!r}, found {current[key]!r}"
                for key in moved)
            raise StaleSnapshotError(
                f"the snapshot this operation was planned against has moved "
                f"({detail})",
                next_action="saipen status")

    # ------------------------------------------------------------ projections

    @property
    def active_ticket_id(self) -> str | None:
        return self.state.active_ticket

    def binding_error(self) -> str | None:
        """STATE.task and BOARD `## DOING` must name the same ticket.

        This pair disagreeing is the single most common structural corruption
        in this repository's own history: a checkpoint interrupted between the
        BOARD write and the STATE write leaves exactly this shape. Reporting it
        as one sentence is what lets a mutation refuse before it makes the
        damage deeper.
        """
        claimed = self.board.active_ticket
        claimed_id = claimed.ticket_id if claimed else None
        if self.active_ticket_id == claimed_id:
            return None
        return (f"STATE.task={self.active_ticket_id or 'none'} "
                f"BOARD.DOING={claimed_id or 'none'}")

    def last_event_error(self) -> str | None:
        """`STATE.last_event` must equal the active LOG tail.

        LOG ahead of STATE is the NORMAL crash shape (checkpoints write LOG
        first) and is reported as a fact, not softened away: it is what tells
        Recovery there is something to roll forward.
        """
        recorded = self.state.last_event
        if recorded is None:
            return "STATE carries no last_event"
        if recorded == self.log_tail:
            return None
        direction = "behind" if recorded < self.log_tail else "ahead of"
        return (f"STATE.last_event={recorded} is {direction} the LOG tail "
                f"E-{self.log_tail}")


def snapshot(root: Path | None = None, *,
             paths: ProjectPaths | None = None) -> ProjectSnapshot:
    """Read one coherent snapshot of a project's canonical state.

    The three files are read in LOG, BOARD, STATE order — the same order a
    checkpoint writes them — so that a snapshot taken during someone else's
    interrupted write sees at worst the recoverable shape (LOG ahead) rather
    than the unrecoverable one.
    """
    if paths is None:
        if root is None:
            raise ValueError("snapshot() needs a root or a ProjectPaths")
        paths = ProjectPaths(Path(root))
    root = paths.root

    log_doc = load_document(paths.log)
    board_doc = load_document(paths.board)
    state_doc = load_document(paths.state)

    sealed_ids: list[int] = []
    for sealed in paths.sealed_logs:
        sealed_ids.extend(
            e.event_id for e in
            parse_log(load_document(sealed).text, sealed.as_posix()).events)

    return ProjectSnapshot(
        root=root,
        identity=project_identity(root),
        paths=paths,
        state_doc=state_doc,
        board_doc=board_doc,
        log_doc=log_doc,
        state=parse_state(state_doc.text),
        board=parse_board(board_doc.text, KNOWN_TICKET_FIELDS),
        log=parse_log(log_doc.text, paths.log.as_posix()),
        head=_head(root),
        sealed_log_ids=sealed_ids,
    )

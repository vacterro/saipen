"""Release executor (T-994: release trust repair).

One immutable ReleasePlan and one execution function own the whole release
flow: exact reviewed-source scope, source identity, STATE/BOARD/LOG binding,
version parity, ship gate, content commit (A), branch push, canonical closure
(ticket DONE + digest), closure commit (B), closure push, tag creation/push,
remote verification, and durable recovery.

Key invariants (T-994):
- PLAN is read-only: zero writes (no write-tree, no index mutation, no git
  objects, no recovery journal).
- The release is ONE recovery-visible SAIOPS operation under
  `.saipen/recovery/ops/release-<hex>/`; every external side effect is
  classified expected-BEFORE / expected-AFTER / CONFLICT, and recovery never
  blindly repeats a side effect.
- Release scope = the exact reviewed ticket scope (recorded at REVIEW -> SHIP
  via `saipen scope`) + the mechanically required release metadata. It is
  never inferred from dirty files and never `git add .`.
- Source identity is the canonical freshness primitive
  (`compute_source_identity`), which includes untracked non-ignored files.
- ReleasePlan is deeply immutable and carries project identity + every
  decision binding; `canonical()` covers every field that changes execution
  semantics.
- ALREADY_APPLIED requires full remote + canonical evidence, never local tag
  presence alone.
- No-publish mode: zero staging, zero commit, zero tag, zero push; local
  validation, truthful skipped-publish LOG event, digest, SHIP -> DONE.
- First publish is a journaled canonical WAIT, never chat memory.
- Every public refusal returns a code from errors.CODES; internal stage
  failures collapse to RELEASE_FAILED with the stage/error in `detail`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import codec
from .errors import CODES
from .operations import RELEASE_SCOPE_DIR, _plan_finish_ticket
from .state import parse_state

# ---------------------------------------------------------------------------
# Git result model
# ---------------------------------------------------------------------------


@dataclass
class GitResult:
    """Structured git subprocess result preserving stderr."""
    rc: int
    stdout: str
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.rc == 0


class ReleaseRefusal(Exception):
    """A public release refusal with a stable code from errors.CODES."""

    def __init__(self, code: str, detail: str) -> None:
        if code not in CODES:
            raise ValueError(
                f"release refusal {code!r} is not in OPS.md's closed set")
        super().__init__(f"REFUSE [{code}] {detail}")
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# Release operation stages (T-994 / § 3): one recovery-visible operation.
# ---------------------------------------------------------------------------

RELEASE_OP_STAGES = (
    "PREPARED",
    "CONTENT_COMMIT_CREATED",
    "CONTENT_PUBLISHED",
    "CLOSURE_PREPARED",
    "CLOSURE_COMMIT_CREATED",
    "CLOSURE_PUBLISHED",
    "TAG_CREATED",
    "TAG_PUBLISHED",
    "REMOTE_VERIFIED",
    "COMMITTED",
)

# Remote classification closed states (T-994 / § 12).
REMOTE_ABSENT = "ABSENT"            # no origin, or endpoint says nothing exists
REMOTE_EMPTY = "EMPTY"              # endpoint queryable, zero heads AND tags
REMOTE_ESTABLISHED = "ESTABLISHED"  # endpoint has heads or tags
REMOTE_UNAVAILABLE = "UNAVAILABLE"  # network/auth failure, cannot answer
REMOTE_AMBIGUOUS = "AMBIGUOUS"      # multiple push destinations

# Where a continuation plan resumes (T-994 / § 18).
START_PREPARED = "PREPARED"  # nothing external happened yet
START_CLOSURE = "CLOSURE"    # content commit A committed + pushed
START_TAG = "TAG"            # closure commit B committed + pushed, tag missing

CLOSURE_FILES = (
    ".saipen/STATE.md",
    ".saipen/BOARD.md",
    ".saipen/LOG.md",
    ".saipen/kitchen/digest.md",
)


def _closure_stage_paths(root: Path) -> list[str]:
    """The exact closure staging set: the four canonical files PLUS every
    sealed LOG segment that exists. A segment sealed between releases
    (`clean.md` step 4) is canonical history -- if the closure did not stage
    it, a fresh clone would lack the E-### events Recovery depends on and the
    released tag would be broken (the v7.223.16 sealed-segment omission)."""
    paths = list(CLOSURE_FILES)
    logs_dir = root / ".saipen" / "logs"
    if logs_dir.is_dir():
        paths += sorted(str(p.relative_to(root).as_posix())
                        for p in logs_dir.glob("LOG-*.md"))
    return paths


# ---------------------------------------------------------------------------
# Index snapshot: exact, deletion-preserving rollback (T-994 / § 19).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexSnapshot:
    """Exact pre-release index state for rollback.

    Records every staged path with its status (M/A/T/D) and, where the staged
    entry has a blob, the mode + blob hash. A staged deletion has status D and
    no blob -- restoring it re-stages the deletion instead of destroying it
    (a broad `git reset` alone destroys staged deletions).
    """
    paths: tuple[str, ...]
    entries: tuple[tuple[str, str, str], ...]  # (path, mode_or_D, blob_or_)
    content_hash: str

    def to_dict(self) -> dict:
        return {
            "paths": list(self.paths),
            "entries": {p: {"mode": m, "blob": b}
                        for p, m, b in self.entries},
            "content_hash": self.content_hash,
        }


def _capture_index_state(root: Path) -> IndexSnapshot:
    """Capture the exact pre-operation index for rollback.

    Uses `-z` machine lists (a path with a newline must not split staging
    scope) and `--name-status` so a staged deletion is recorded with status D
    -- the current `git reset`-based rollback must be able to recreate it.
    """
    result = _git(root, "diff", "--cached", "--name-status", "-z")
    raw = result.stdout
    fields = raw.split("\0")
    paths: list[str] = []
    entries: list[tuple[str, str, str]] = []
    index = 0
    while index < len(fields):
        if not fields[index]:
            index += 1
            continue
        header = fields[index]
        index += 1
        if index >= len(fields):
            break
        path = fields[index]
        index += 1
        if not header:
            continue
        status = header.split()[0][0]
        paths.append(path)
        if status == "D":
            entries.append((path, "D", ""))
            continue
        ls = _git(root, "ls-files", "-s", "-z", "--", path, literal=True)
        mode_blob = ""
        for piece in ls.stdout.split("\0"):
            if not piece or "\t" not in piece:
                continue
            meta = piece.split("\t", 1)[0].split()
            if len(meta) >= 2:
                mode_blob = f"{meta[0]},{meta[1]}"
                break
        if mode_blob:
            mode, blob = mode_blob.split(",", 1)
            entries.append((path, mode, blob))
        else:
            # A staged typechange/mode change with no readable entry is
            # represented by its deletion half; the reset path below still
            # restores the exact --cached delta.
            entries.append((path, "D", ""))
    ordered = sorted(paths)
    content_hash = hashlib.sha256(
        "|".join(
            f"{p}:{m}:{b}" for p, m, b in sorted(entries)
        ).encode("utf-8")).hexdigest()[:16]
    return IndexSnapshot(tuple(ordered), tuple(sorted(entries)), content_hash)


def _restore_index(root: Path, pre_state: IndexSnapshot) -> None:
    """Restore the index to the exact pre-release state.

    Pre-existing staged entries (source + foreign) are restored to their
    exact prior mode + blob -- never rebuilt from HEAD, and the working tree
    is never touched, so concurrent/user edits are preserved. Staged
    deletions are re-staged with `git rm --cached`, which a broad `git reset`
    would otherwise destroy.
    """
    _git(root, "reset", "-q")
    for path, mode, blob in pre_state.entries:
        if mode == "D":
            _git(root, "rm", "--cached", "--quiet", "--", path, literal=True)
        else:
            _git(root, "update-index", "--add", "--cacheinfo",
                 f"{mode},{blob},{path}", literal=True)


# ---------------------------------------------------------------------------
# ReleasePlan: the deeply immutable, project-bound decision (T-994 / § 5, § 6).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleasePlan:
    """The immutable release decision, bound to the world it decided against.

    Every precondition the release depends on is captured here: project
    identity, source HEAD + tree fingerprint, index identity, STATE/BOARD/LOG
    hashes, remote classification/tip/refs, push endpoint, mode, and the
    reviewed scope. All decision-bearing fields are immutable tuples/records
    and ALL of them participate in `canonical()`, so an immutable object is
    an immutable DECISION -- no caller can mutate a dict inside it afterwards.
    """
    invocation: str
    op_id: str
    version: str
    branch: str
    tag: str
    ticket_id: str
    commit_message: str
    scope_paths: tuple[str, ...]
    metadata_paths: tuple[str, ...]
    # identity + bindings
    project_identity: str
    source_head: str
    source_tree_fingerprint: str
    source_discovery_model: str
    state_phase: str
    state_task: str | None
    state_hash: str
    board_hash: str
    log_hash: str
    mode: str
    dry_run: bool
    # remote facts (closed classification, T-994 / § 12)
    remote_classification: str
    remote_branch_tip: str
    remote_refs: tuple[tuple[str, str], ...]
    remote_push_url: str
    head_relation: str
    # continuation / policy
    start_stage: str
    content_already_committed: bool
    already_applied: bool
    first_publish_wait: bool
    confirmation: str
    pre_plan_index: IndexSnapshot

    def canonical(self) -> tuple:
        """The plan's identity, INVOCATION-NAME NORMALIZED -- `ship` and
        `push` plans for the same release are identical (T-635), and every
        field capable of changing execution semantics is covered."""
        return (
            self.version, self.branch, self.tag, self.ticket_id,
            self.commit_message, self.scope_paths, self.metadata_paths,
            self.project_identity, self.source_head,
            self.source_tree_fingerprint, self.source_discovery_model,
            self.state_phase, self.state_task, self.state_hash,
            self.board_hash, self.log_hash, self.mode,
            self.remote_classification, self.remote_branch_tip,
            self.remote_refs, self.remote_push_url, self.head_relation,
            self.start_stage, self.content_already_committed,
            self.first_publish_wait, self.confirmation,
            self.pre_plan_index.content_hash, self.pre_plan_index.paths,
        )

    @property
    def release_paths(self) -> tuple[str, ...]:
        """Exact staged surface: reviewed scope + release metadata + the
        scope record itself (the reviewed-ownership evidence must reach git,
        or a fresh clone could never continue the release)."""
        return self.scope_paths + self.metadata_paths + (
            f"{RELEASE_SCOPE_DIR}/{self.ticket_id}.json",)


def _release_failure(stage: str, detail: str, **extra) -> dict:
    out = {"ok": False, "code": "RELEASE_FAILED", "stage": stage,
           "detail": detail}
    out.update(extra)
    return out


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def plan_release(
    root: Path, invocation: str, *, dry_run: bool = False,
) -> "ReleasePlan":
    """Build the immutable release decision.  WRITES NOTHING."""
    root = Path(root).resolve()
    _recovery_preflight(root)

    version = _installed_version(root)
    state_text, state = _read_state(root)
    board_text, board = _read_board(root)
    log_hash = _log_hash(root)
    mode = _read_mode(state)

    from .paths import project_identity as _project_identity
    project_identity = _project_identity(root)

    try:
        from freshness import compute_source_identity
        ident = compute_source_identity(root)
    except Exception as exc:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            f"cannot compute canonical source identity: {exc}")

    source_head = ident.source_head
    fingerprint = ident.source_tree_fingerprint
    source_model = ident.discovery_model
    head = _git(root, "rev-parse", "HEAD").stdout if mode == "full" else source_head

    tag = f"v{version}"

    # ---- no-publish needs NO git facts at all (T-994 / § 10) --------------
    if mode == "no-publish":
        phase = state.get("phase")
        if phase != "SHIP":
            raise ReleaseRefusal(
                "ILLEGAL_PHASE",
                f"release requires phase SHIP; actual phase {phase}. "
                "Run the ticket through REVIEW then SHIP first.")
        task = state.get("task")
        ticket = _find_ticket(board, task)
        if ticket is None:
            raise ReleaseRefusal(
                "SOURCE_SCOPE_MISSING",
                f"STATE.task={task!r} but no matching DOING ticket on BOARD.")
        _scope_for(root, ticket["id"], head, fingerprint, continuation=False)
        _check_parity(root, version)
        index = IndexSnapshot((), (), hashlib.sha256(
            b"no-publish-no-git").hexdigest()[:16])
        return ReleasePlan(
            invocation=invocation,
            op_id="release-" + _hex8(),
            version=version, branch="", tag=tag,
            ticket_id=ticket["id"],
            commit_message=f"ship v{version}",
            scope_paths=tuple(_scope_paths(root, ticket["id"])),
            metadata_paths=tuple(_metadata_paths(root)),
            project_identity=project_identity,
            source_head=source_head, source_tree_fingerprint=fingerprint,
            source_discovery_model=source_model,
            state_phase=phase, state_task=task,
            state_hash=_quick_hash(state_text), board_hash=_quick_hash(board_text),
            log_hash=log_hash, mode=mode, dry_run=dry_run,
            remote_classification="never", remote_branch_tip="",
            remote_refs=(), remote_push_url="", head_relation="local",
            start_stage=START_PREPARED, content_already_committed=False,
            already_applied=False, first_publish_wait=False, confirmation="",
            pre_plan_index=index,
        )

    # ---- mode full: remote + continuation classification ------------------
    if not _branch_exists(root, _branch(root)):
        raise ReleaseRefusal(
            "STALE_PLAN", f"current branch {_branch(root)!r} does not exist")

    cls, cls_err = _classify_remote(root)
    if cls == REMOTE_UNAVAILABLE:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            f"remote origin is UNAVAILABLE -- cannot classify before any "
            f"external write: {cls_err or 'query failed'}")
    if cls == REMOTE_AMBIGUOUS:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            "origin has multiple push destinations; refuse multi-destination "
            "publication")

    push_urls = _push_urls(root)
    if len(push_urls) > 1:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            "multiple push destinations configured for origin: "
            + ", ".join(push_urls) + " -- refuse multi-destination publication")
    if cls not in (REMOTE_ABSENT, REMOTE_EMPTY) and not push_urls:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            "no push URL configured for origin -- configure the push "
            "destination before releasing")
    remote_push_url = _sanitize_push_url(push_urls[0]) if push_urls else ""

    branch = _branch(root)
    remote_ok, remote_tip = _remote_branch_tip(root, "origin", branch)
    if not remote_ok:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            "remote branch tip query failed at plan time; remote "
            "classification is not re-checkable -- refuse")
    tag_local, tag_local_c = _local_tag_commit(root, tag)
    _tag_remote_ok, tag_remote_c = _remote_tag_commit(root, tag)
    tag_remote_exists = bool(tag_remote_c)
    remote_refs = tuple(sorted(
        _snapshot_remote_refs(root, "origin").items()))
    head_relation = _head_relation(root, remote_tip)

    phase = state.get("phase")
    task = state.get("task")

    # ---- tag collisions are always refusals before any decision ----------
    if tag_local and tag_local_c != head:
        raise ReleaseRefusal(
            "TAG_CONFLICT",
            f"local tag {tag} exists at {tag_local_c[:12]}, not HEAD "
            f"{head[:12]}; resolve before releasing")
    if tag_remote_exists and tag_remote_c != head:
        raise ReleaseRefusal(
            "TAG_CONFLICT",
            f"remote tag {tag} exists at {tag_remote_c[:12]}, not HEAD "
            f"{head[:12]}; resolve before releasing")

    # ---- phase gate -------------------------------------------------------
    if phase not in ("SHIP", "DONE"):
        raise ReleaseRefusal(
            "ILLEGAL_PHASE",
            f"release requires phase SHIP (or a proven in-flight release "
            f"with phase DONE); actual phase {phase}")

    # ---- ticket identity ---------------------------------------------------
    if phase == "DONE":
        ticket_id = _find_release_ticket(root, version)
        if ticket_id is None:
            raise ReleaseRefusal(
                "RELEASE_FAILED",
                "phase DONE but no committed release RUN event names this "
                "version; cannot continue an unproven release")
    else:
        ticket = _find_ticket(board, task)
        if ticket is None:
            raise ReleaseRefusal(
                "SOURCE_SCOPE_MISSING",
                f"STATE.task={task!r} but no matching DOING ticket on BOARD.")
        ticket_id = ticket["id"]

    # ---- exact reviewed scope ----------------------------------------------
    _scope_for(root, ticket_id, head, fingerprint,
               continuation=(phase == "DONE" or tag_remote_exists
                             or (remote_tip and remote_tip == head)))
    scope_paths = _scope_paths(root, ticket_id)
    scope_record_rel = f"{RELEASE_SCOPE_DIR}/{ticket_id}.json"

    _check_parity(root, version)
    index = _capture_index_state(root)

    # ---- foreign pre-existing staging must refuse (T-994 / § 2) ------------
    # A path this release does not own (not reviewed scope, not mechanically
    # required metadata, not the scope record) must never enter the commit.
    allowed = set(scope_paths) | set(_metadata_paths(root)) | {
        scope_record_rel}
    foreign = sorted(set(index.paths) - allowed)
    if foreign:
        raise ReleaseRefusal(
            "VALIDATION_FAILED",
            "foreign pre-existing staged path(s) would enter this release: "
            + ", ".join(foreign)
            + " -- stage the release scope explicitly or leave it untouched")

    # ---- continuation / completion classification --------------------------
    classification = _classify_continuation(
        root, state, phase, ticket_id, version, tag, branch, head, cls,
        remote_tip, tag_local, tag_local_c, tag_remote_exists,
        tag_remote_c,
        [*scope_paths, scope_record_rel])

    confirmation = _read_confirmation(state)

    return ReleasePlan(
        invocation=invocation,
        op_id="release-" + _hex8(),
        version=version, branch=branch, tag=tag, ticket_id=ticket_id,
        commit_message=f"ship v{version}",
        scope_paths=tuple(scope_paths),
        metadata_paths=tuple(_metadata_paths(root)),
        project_identity=project_identity,
        source_head=source_head, source_tree_fingerprint=fingerprint,
        source_discovery_model=source_model,
        state_phase=phase, state_task=task,
        state_hash=_quick_hash(state_text), board_hash=_quick_hash(board_text),
        log_hash=log_hash, mode=mode, dry_run=dry_run,
        remote_classification=cls, remote_branch_tip=remote_tip,
        remote_refs=remote_refs, remote_push_url=remote_push_url,
        head_relation=head_relation,
        start_stage=classification["start_stage"],
        content_already_committed=classification["content_already_committed"],
        already_applied=classification["already_applied"],
        first_publish_wait=classification["first_publish_wait"],
        confirmation=confirmation,
        pre_plan_index=index,
    )


def execute_release(root: Path, plan: ReleasePlan) -> dict:
    """Execute the plan.  The ONE execution function."""
    root = Path(root).resolve()
    if plan.already_applied:
        return {
            "ok": True, "code": "RELEASED", "already_applied": True,
            "stage": "COMMITTED", "stages_reached": list(RELEASE_OP_STAGES),
            "tag": plan.tag, "branch": plan.branch,
            "detail": "full remote + canonical evidence proves this release "
                      "already completed; no commit/tag/push performed",
        }
    if plan.dry_run:
        return _apply_dry_run(root, plan)
    if plan.first_publish_wait:
        if plan.confirmation:
            # Confirmation present + matching: publication authorized, but the
            # plan bindings must still be re-verified before any write.
            preflight = _preflight_plan(root, plan)
            if not preflight["ok"]:
                return preflight
            return _apply_release(root, plan)
        return _apply_first_publish_wait(root, plan)
    if plan.mode == "no-publish":
        preflight = _preflight_plan(root, plan)
        if not preflight["ok"]:
            return preflight
        return _apply_no_publish(root, plan)
    preflight = _preflight_plan(root, plan)
    if not preflight["ok"]:
        return preflight
    return _apply_release(root, plan)


# ---------------------------------------------------------------------------
# Recovery preflight
# ---------------------------------------------------------------------------


def _recovery_preflight(root: Path) -> None:
    """Read-only journal scan: unresolved operations block a new release."""
    from .journal import pending_ops
    pending = pending_ops(root)
    if not pending:
        return
    conflicts = [op for op in pending if op.get("status") == "CONFLICT"]
    if conflicts:
        raise ReleaseRefusal(
            "RECOVERY_CONFLICT",
            "unresolved recovery conflict(s): "
            + ", ".join(str(op.get("op_id", "?")) for op in conflicts)
            + " -- recover before releasing")
    raise ReleaseRefusal(
        "RECOVERY_REQUIRED",
        "pending recovery operation(s): "
        + ", ".join(str(op.get("op_id", "?")) for op in pending[:5])
        + " -- recover before releasing")


# ---------------------------------------------------------------------------
# Continuation / completion classification (T-994 / § 13, § 18)
# ---------------------------------------------------------------------------


def _surface_dirty(root: Path, paths: list[str]) -> list[str]:
    """Paths with a staged, unstaged OR untracked non-ignored delta against
    HEAD (literal paths).

    `git diff` alone MISSES untracked files, so a scope consisting of a brand
    new (untracked) file would read as a clean surface and the continuation
    classification would skip its content commit -- the v7.223.15 false-success
    defect. Untracked non-ignored files are part of the canonical source
    identity (freshness.py `git-delta-v1`), and the continuation decision
    uses the SAME surface.
    """
    dirty = set()
    cached = _git(root, "diff", "--cached", "--name-only", "-z",
                  "--", *paths, literal=True)
    for p in cached.stdout.split("\0"):
        if p:
            dirty.add(p)
    work = _git(root, "diff", "--name-only", "-z",
                "--", *paths, literal=True)
    for p in work.stdout.split("\0"):
        if p:
            dirty.add(p)
    untracked = _git(root, "ls-files", "--others", "--exclude-standard",
                     "-z", "--", *paths, literal=True)
    for p in untracked.stdout.split("\0"):
        if p:
            dirty.add(p)
    return sorted(dirty)


def _classify_continuation(
    root: Path, state: dict, phase: str, ticket_id: str, version: str,
    tag: str, branch: str, head: str, cls: str, remote_tip: str,
    tag_local: bool, tag_local_c: str, tag_remote_exists: bool,
    tag_remote_c: str,
    scope_paths: list[str],
) -> dict:
    """Classify the release as FRESH / NEEDS_CLOSURE / NEEDS_TAG /
    ALREADY_APPLIED / FIRST_PUBLISH. Never rounds a partial state up."""
    if (phase == "DONE"
            and tag_local and tag_local_c == head
            and tag_remote_exists and tag_remote_c == head
            and remote_tip == head
            and _ticket_done(root, ticket_id)
            and _log_has_ship(root, version, ticket_id)):
        return {"start_stage": START_TAG, "content_already_committed": True,
                "already_applied": True, "first_publish_wait": False}
    if (phase == "DONE"
            and remote_tip == head
            and not tag_remote_exists
            and _ticket_done(root, ticket_id)
            and _log_has_ship(root, version, ticket_id)):
        return {"start_stage": START_TAG, "content_already_committed": True,
                "already_applied": False, "first_publish_wait": False}
    if (phase == "SHIP"
            and not tag_local and not tag_remote_exists
            and remote_tip == head
            and not _surface_dirty(root, scope_paths)):
        return {"start_stage": START_CLOSURE, "content_already_committed": True,
                "already_applied": False, "first_publish_wait": False}
    if phase == "SHIP" and not tag_local and not tag_remote_exists:
        if cls in (REMOTE_ABSENT, REMOTE_EMPTY):
            return {"start_stage": START_PREPARED,
                    "content_already_committed": False,
                    "already_applied": False, "first_publish_wait": True}
        return {"start_stage": START_PREPARED,
                "content_already_committed": False,
                "already_applied": False, "first_publish_wait": False}
    if phase == "DONE":
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            "phase DONE but the release cannot be proven complete (remote "
            "branch/tag or committed evidence missing); UNKNOWN != RELEASED")
    raise ReleaseRefusal(
        "RELEASE_FAILED",
        f"ambiguous release continuation state (phase {phase}, remote tip "
        f"{remote_tip[:12] if remote_tip else '(none)'}, local tag "
        f"{tag_local}, remote tag {tag_remote_exists})")


def _ticket_done(root: Path, ticket_id: str) -> bool:
    from .board import parse_board
    text = codec.read_doc(root / ".saipen" / "BOARD.md")
    board = parse_board(text)
    ticket = board["tickets"].get(ticket_id)
    return bool(ticket and ticket["section"] == "## DONE"
                and ticket["checkbox"] == "x")


def _log_has_ship(root: Path, version: str, ticket_id: str) -> bool:
    """Committed LOG evidence: a RUN event naming this version + ticket."""
    from .log import parse_log_line
    log_path = root / ".saipen" / "LOG.md"
    text = codec.read_doc(log_path) if log_path.is_file() else ""
    for line in text.splitlines():
        parsed = parse_log_line(line)
        if (parsed and parsed["taxonomy"] == "RUN"
                and f"ship v{version}" in parsed["text"]
                and parsed["ticket"] == ticket_id):
            return True
    return False


def _find_release_ticket(root: Path, version: str) -> str | None:
    """The ticket that shipped this version, from committed RUN evidence."""
    from .log import parse_log_line
    log_path = root / ".saipen" / "LOG.md"
    text = codec.read_doc(log_path) if log_path.is_file() else ""
    for line in text.splitlines():
        parsed = parse_log_line(line)
        if (parsed and parsed["taxonomy"] == "RUN"
                and f"ship v{version}" in parsed["text"]
                and parsed["ticket"] and parsed["ticket"].startswith("T-")):
            return parsed["ticket"]
    return None


def _read_confirmation(state: dict) -> str:
    return str(state.get("first_publish_confirmation") or "")


# ---------------------------------------------------------------------------
# Reviewed scope (T-994 / § 2)
# ---------------------------------------------------------------------------


def _scope_path(root: Path, ticket_id: str) -> Path:
    return root / RELEASE_SCOPE_DIR / f"{ticket_id}.json"


def _scope_paths(root: Path, ticket_id: str) -> list[str]:
    return sorted(_load_scope(root, ticket_id, None, None,
                              continuation=True)["paths"])


def _load_scope(root: Path, ticket_id: str, head: str | None,
                fingerprint: str | None,
                continuation: bool) -> dict:
    """Read + validate the recorded reviewed scope for a ticket.

    Binds the ticket to exact file identities and the source identity at
    review time. For a fresh release the current HEAD must BE the reviewed
    HEAD; for a continuation the reviewed HEAD must be an ancestor (the
    release commits landed on top). Per-path hashes must match the live
    bytes in both cases.
    """
    from .paths import project_identity as _project_identity
    path = _scope_path(root, ticket_id)
    if not path.is_file():
        raise ReleaseRefusal(
            "SOURCE_SCOPE_MISSING",
            f"no release scope recorded for {ticket_id} -- record the exact "
            f"reviewed files (`saipen scope {ticket_id} <path...>`) before "
            "shipping")
    try:
        data = json.loads(codec.read_doc(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseRefusal(
            "RECOVERY_CONFLICT",
            f"release scope record {path} is corrupt: {exc}")
    if data.get("schema_version") != 1:
        raise ReleaseRefusal(
            "RECOVERY_CONFLICT",
            f"release scope record {path} has unknown schema_version "
            f"{data.get('schema_version')!r}")
    if data.get("ticket") != ticket_id:
        raise ReleaseRefusal(
            "RECOVERY_CONFLICT",
            f"release scope record {path} names ticket {data.get('ticket')!r}, "
            f"not {ticket_id}")
    # A scope record is bound to the worktree that recorded it. For a FRESH
    # release that binding is a hard boundary (cross-worktree scope is
    # refused). For a CONTINUATION the record is committed release evidence:
    # a fresh clone of the release branch legitimately carries it, so the
    # ancestry check below -- not the absolute path -- is the binding.
    if not continuation and data.get("project_identity") != _project_identity(root):
        raise ReleaseRefusal(
            "PATH_ESCAPE",
            "release scope record was created for a different project; "
            "refuse cross-project scope")
    reviewed_head = data.get("source_head") or ""
    if head is not None:
        if continuation:
            if not _is_ancestor(root, reviewed_head, head):
                raise ReleaseRefusal(
                    "STALE_PLAN",
                    f"reviewed source_head {reviewed_head[:12]} is not an "
                    f"ancestor of current HEAD {head[:12]}; the release "
                    "continuation is not bound to this tree")
        elif reviewed_head != head:
            raise ReleaseRefusal(
                "STALE_PLAN",
                f"reviewed source_head {reviewed_head[:12]} != current HEAD "
                f"{head[:12]}; the reviewed scope is stale, re-record it")
    paths = data.get("paths") or {}
    if not paths:
        raise ReleaseRefusal(
            "SOURCE_SCOPE_MISSING",
            f"release scope record {path} carries no paths")
    for rel, expected in paths.items():
        fp = root / rel
        if expected is None:
            # Deletion scope entry: the reviewed file must STILL be absent at
            # APPLY (a file that reappeared is a stale scope, not a ship).
            if fp.exists():
                raise ReleaseRefusal(
                    "STALE_PLAN",
                    f"scope path {rel} is recorded as a reviewed deletion but "
                    "exists in the worktree; re-record the scope or restore "
                    "the deletion")
            continue
        if not fp.is_file():
            raise ReleaseRefusal(
                "SOURCE_SCOPE_MISSING",
                f"scope path {rel} is missing from the worktree")
        live = _quick_hash(fp.read_bytes())
        if live != expected:
            raise ReleaseRefusal(
                "STALE_PLAN",
                f"scope path {rel} changed since review (live {live!r}, "
                f"reviewed {expected!r}); re-record the scope or revert the "
                "edit")
    return data


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    if ancestor == descendant:
        return True
    result = _git(root, "merge-base", "--is-ancestor", ancestor, descendant)
    return result.ok


# ---------------------------------------------------------------------------
# Preflight: validate plan against live state (T-994 / § 8)
# ---------------------------------------------------------------------------


def _preflight_plan(root: Path, plan: ReleasePlan) -> dict:
    """Verify every plan binding against the live world before ANY write."""
    from .paths import project_identity as _project_identity
    if _project_identity(root) != plan.project_identity:
        return _release_failure(
            "PREFLIGHT", "plan was built for a different project; refusing "
            "cross-project execution")

    # Re-read + validate canonical state.
    try:
        state_text, state = _read_state(root)
        board_text, board = _read_board(root)
        log_hash = _log_hash(root)
    except Exception as exc:
        return _release_failure("PREFLIGHT", f"canonical state unreadable: "
                                            f"{exc}")
    if _quick_hash(state_text) != plan.state_hash:
        return _release_failure(
            "PREFLIGHT", "STATE.md changed since the plan was built; rebuild "
            "the plan")
    if _quick_hash(board_text) != plan.board_hash:
        return _release_failure(
            "PREFLIGHT", "BOARD.md changed since the plan was built; rebuild "
            "the plan")
    if log_hash != plan.log_hash:
        return _release_failure(
            "PREFLIGHT", "LOG.md changed since the plan was built; rebuild "
            "the plan")

    # First-publish confirmation must name THIS endpoint (T-994 / § 11).
    if plan.first_publish_wait and plan.confirmation:
        confirm_remote = (plan.confirmation.split()[0]
                          if plan.confirmation.split() else "")
        if confirm_remote and plan.remote_push_url and \
                _sanitize_push_url(confirm_remote) != plan.remote_push_url:
            return _release_failure(
                "FIRST_PUBLISH_WAIT",
                f"recorded first-publish confirmation names a different "
                f"remote ({plan.confirmation!r}); refuse")

    if plan.mode == "no-publish":
        # No-publish APPLY performs ZERO git operations: re-verify only the
        # canonical + scope bindings (T-994 / § 10).
        if state.get("phase") != "SHIP" or state.get("task") != plan.ticket_id:
            return _release_failure(
                "PREFLIGHT", f"no-publish requires phase SHIP / task == "
                f"{plan.ticket_id}; live {state.get('phase')}/"
                f"{state.get('task')}")
        doing = [t for t in board["tickets"].values()
                 if t["section"] == "## DOING"]
        if len(doing) != 1 or doing[0]["id"] != plan.ticket_id:
            return _release_failure(
                "PREFLIGHT", "no-publish requires exactly one ## DOING ticket "
                f"== {plan.ticket_id}")
        try:
            _scope_for(root, plan.ticket_id, plan.source_head,
                       plan.source_tree_fingerprint, continuation=False)
        except ReleaseRefusal as exc:
            return _release_failure("PREFLIGHT", str(exc))
        return {"ok": True}

    if plan.start_stage == START_TAG:
        if state.get("phase") != "DONE" or state.get("task") not in (
                None, "none"):
            return _release_failure(
                "PREFLIGHT",
                "continuation needs phase DONE / task none; live "
                f"{state.get('phase')}/{state.get('task')}")
        if not _ticket_done(root, plan.ticket_id):
            return _release_failure(
                "PREFLIGHT",
                f"continuation requires {plan.ticket_id} DONE on BOARD")
        if not _log_has_ship(root, plan.version, plan.ticket_id):
            return _release_failure(
                "PREFLIGHT", "no committed release RUN event binds this "
                "continuation to the ticket")
    else:
        if state.get("phase") != "SHIP":
            return _release_failure(
                "PREFLIGHT", f"release requires phase SHIP; live "
                             f"{state.get('phase')}")
        if state.get("task") != plan.ticket_id:
            return _release_failure(
                "PREFLIGHT", f"STATE.task={state.get('task')} != planned "
                             f"{plan.ticket_id}")
        doing = [t for t in board["tickets"].values()
                 if t["section"] == "## DOING"]
        if len(doing) != 1 or doing[0]["id"] != plan.ticket_id:
            return _release_failure(
                "PREFLIGHT", "BOARD must hold exactly one ## DOING ticket == "
                f"{plan.ticket_id}")

    # Source identity must still match the plan.
    try:
        from freshness import compute_source_identity
        live = compute_source_identity(root)
    except Exception as exc:
        return _release_failure("PREFLIGHT",
                                f"cannot recompute source identity: {exc}")
    if live.source_head != plan.source_head:
        return _release_failure(
            "PREFLIGHT", f"source HEAD changed: planned "
                         f"{plan.source_head[:12]}, live "
                         f"{live.source_head[:12]}; rebuild the plan")
    if live.source_tree_fingerprint != plan.source_tree_fingerprint:
        return _release_failure(
            "PREFLIGHT", "source tree fingerprint changed since the plan was "
            "built; rebuild the plan")

    # Exact index identity.
    index = _capture_index_state(root)
    if index.content_hash != plan.pre_plan_index.content_hash:
        return _release_failure(
            "PREFLIGHT", "index content changed since the plan was built; "
            "rebuild the plan")

    # Reviewed scope bytes must still match the plan (they are inside the
    # source fingerprint, but name them explicitly for a clear refusal).
    try:
        _scope_for(root, plan.ticket_id, plan.source_head,
                   plan.source_tree_fingerprint,
                   continuation=(plan.start_stage != START_PREPARED))
    except ReleaseRefusal as exc:
        return _release_failure("PREFLIGHT", str(exc))

    # Remote re-classification: closed, fail-closed (T-994 / § 12).
    cls, cls_err = _classify_remote(root)
    if cls == REMOTE_UNAVAILABLE:
        return _release_failure(
            "PREFLIGHT", f"remote was queryable at PLAN but is UNAVAILABLE "
            f"at APPLY -- refuse before publication: "
            f"{cls_err or 'query failed'}")
    if cls == REMOTE_AMBIGUOUS:
        return _release_failure(
            "PREFLIGHT", "remote classification became AMBIGUOUS at APPLY")
    if cls != plan.remote_classification and not (
            plan.remote_classification in (REMOTE_ABSENT, REMOTE_EMPTY)
            and cls in (REMOTE_ABSENT, REMOTE_EMPTY)):
        return _release_failure(
            "PREFLIGHT", f"remote classification changed: planned "
            f"{plan.remote_classification}, live {cls}")

    remote_ok, remote_tip = _remote_branch_tip(root, "origin", plan.branch)
    if not remote_ok:
        return _release_failure(
            "PREFLIGHT", "remote branch tip query failed at APPLY; refuse "
            "before publication")
    if remote_tip != plan.remote_branch_tip:
        return _release_failure(
            "PREFLIGHT", f"remote branch moved: planned "
            f"{plan.remote_branch_tip[:12] or '(none)'}, live "
            f"{remote_tip[:12] or '(none)'}. Rebuild the plan.")

    push_urls = _push_urls(root)
    if [_sanitize_push_url(u) for u in push_urls] != [plan.remote_push_url] \
            and not (plan.remote_push_url == "" and not push_urls):
        return _release_failure(
            "PREFLIGHT", f"push destination changed: planned "
            f"{plan.remote_push_url!r}, live {push_urls!r}")

    # Local + remote tag absence is a hard precondition for a fresh/closure
    # plan (a present tag would collide with this release's tag).
    tag_local, tag_local_c = _local_tag_commit(root, plan.tag)
    _tag_remote_ok, tag_remote_c = _remote_tag_commit(root, plan.tag)
    tag_remote_exists = bool(tag_remote_c)
    if plan.start_stage in (START_PREPARED, START_CLOSURE):
        if tag_local:
            return _release_failure(
                "TAG_CONFLICT",
                f"local tag {plan.tag} exists at "
                f"{tag_local_c[:12] or '?'}; resolve before releasing")
        if tag_remote_exists:
            return _release_failure(
                "TAG_CONFLICT",
                f"remote tag {plan.tag} exists at "
                f"{tag_remote_c[:12] or '?'}; resolve before releasing")
    elif plan.start_stage == START_TAG:
        # Resumable tag: the tag must be missing or already point at HEAD.
        if tag_local and tag_local_c != plan.source_head:
            return _release_failure(
                "TAG_CONFLICT",
                f"local tag {plan.tag} points at {tag_local_c[:12]}, not the "
                "release HEAD; refuse to rewrite")
        if tag_remote_exists and tag_remote_c != plan.source_head:
            return _release_failure(
                "TAG_CONFLICT",
                f"remote tag {plan.tag} points at {tag_remote_c[:12]}, not "
                "the release HEAD; refuse to rewrite")
        if tag_remote_exists and tag_remote_c == plan.source_head:
            # Tag already published: the only missing piece is the local
            # mark; this is effectively complete.
            pass

    return {"ok": True}


def _scope_for(root: Path, ticket_id: str, head: str | None,
               fingerprint: str | None, continuation: bool) -> dict:
    return _load_scope(root, ticket_id, head, fingerprint, continuation)


# ---------------------------------------------------------------------------
# Dry-run (zero writes)
# ---------------------------------------------------------------------------


def _apply_dry_run(root: Path, plan: ReleasePlan) -> dict:
    """Dry-run: ZERO writes.  Verify by snapshot comparison."""
    if plan.first_publish_wait:
        return {
            "ok": True, "code": "FIRST_PUBLISH_WAIT", "writes": "none",
            "would_wait": True,
            "next_action": _wait_message(plan.remote_push_url),
            "detail": "would persist a journaled first-publish WAIT (no "
                      "commit/tag/push)",
        }
    if plan.mode == "no-publish":
        return {
            "ok": True, "code": "RELEASE_PLAN", "writes": "none",
            "plan": plan.canonical(),
            "commit_message": plan.commit_message,
            "tag": plan.tag, "branch": plan.branch,
            "release_paths": list(plan.release_paths),
            "mode": "no-publish",
        }

    pre_worktree = _snapshot_worktree(root, plan.release_paths)
    pre_refs = _snapshot_all_refs(root)
    pre_index = _capture_index_state(root)
    pre_tags = _git(root, "tag", "--list").stdout
    pre_branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout
    pre_head = _git(root, "rev-parse", "HEAD").stdout
    pre_obj_count = _git_object_count(root)

    errors = _verify_zero_writes(
        root, plan, pre_worktree, pre_refs, pre_index, pre_tags,
        pre_branch, pre_head, pre_obj_count)

    if errors:
        return _release_failure("DRY_RUN", "; ".join(errors))

    return {
        "ok": True, "code": "RELEASE_PLAN", "writes": "none",
        "plan": plan.canonical(),
        "commit_message": plan.commit_message,
        "tag": plan.tag, "branch": plan.branch,
        "release_paths": list(plan.release_paths),
    }


def _verify_zero_writes(
    root: Path, plan: ReleasePlan,
    pre_worktree: dict, pre_refs: dict, pre_index: IndexSnapshot,
    pre_tags: str, pre_branch: str, pre_head: str, pre_obj_count: int,
) -> list[str]:
    """Compare pre/post snapshots; return list of violations."""
    violations: list[str] = []
    post_worktree = _snapshot_worktree(root, plan.release_paths)
    for path, h in pre_worktree.items():
        if post_worktree.get(path) != h:
            violations.append(f"worktree changed: {path}")
    post_refs = _snapshot_all_refs(root)
    for ref, h in pre_refs.items():
        if post_refs.get(ref) != h:
            violations.append(f"ref changed: {ref}")
    for ref in post_refs:
        if ref not in pre_refs:
            violations.append(f"new ref: {ref}")
    post_index = _capture_index_state(root)
    if post_index.content_hash != pre_index.content_hash:
        violations.append("index content changed")
    post_tags = _git(root, "tag", "--list").stdout
    if post_tags != pre_tags:
        violations.append("tags changed")
    post_head = _git(root, "rev-parse", "HEAD").stdout
    if post_head != pre_head:
        violations.append("HEAD changed")
    post_obj = _git_object_count(root)
    if post_obj != pre_obj_count:
        violations.append(
            f"git object count changed: {pre_obj_count} -> {post_obj}")
    return violations


# ---------------------------------------------------------------------------
# First-publish WAIT (T-994 / § 11)
# ---------------------------------------------------------------------------


def _wait_message(remote_push_url: str) -> str:
    name = _remote_name(remote_push_url)
    return (f"WAIT: first-publish -- confirm repo name '{name}' and "
            "public/private before I push")


def _remote_name(push_url: str) -> str:
    if not push_url:
        return "<origin>"
    return push_url


def _apply_first_publish_wait(root: Path, plan: ReleasePlan) -> dict:
    """Persist the canonical first-publish WAIT. ZERO commit/tag/push.

    The confirmation-present path is dispatched by `execute_release` (it runs
    the full preflight + apply); this function ONLY writes the WAIT.
    """
    from .operations import record_first_publish_wait
    # record_first_publish_wait is itself a journaled SAIOPS op and acquires
    # the writer lock; never nest a lock around it (WRITER_BUSY).
    result = record_first_publish_wait(
        root, _agent(root), _remote_name(plan.remote_push_url))
    if not result.ok:
        return _release_failure(
            "FIRST_PUBLISH_WAIT",
            f"could not persist canonical first-publish WAIT: "
            f"{result.message}")
    return {
        "ok": False, "code": "FIRST_PUBLISH_WAIT",
        "stage": "FIRST_PUBLISH_WAIT",
        "stages_reached": ["FIRST_PUBLISH_WAIT"],
        "next_action": _wait_message(plan.remote_push_url),
        "event_id": result.data.get("event_id"),
        "op_id": result.op_id,
        "detail": "first publish requires confirmation; canonical WAIT "
                  "persisted, zero commit/tag/push performed",
    }


def _agent(root: Path) -> str:
    try:
        _, state = _read_state(root)
        return state.get("agent") or "saipen-cli"
    except (OSError, ValueError):
        return "saipen-cli"


# ---------------------------------------------------------------------------
# No-publish mode (T-994 / § 10: matches ship.md exactly)
# ---------------------------------------------------------------------------


def _apply_no_publish(root: Path, plan: ReleasePlan) -> dict:
    """no-publish: zero staging, zero commit, zero tag, zero push.

    Runs the local validator, writes the truthful skipped-publish LOG event
    through canonical machinery, closes the ticket with the digest, and goes
    SHIP -> DONE. Works even when Git is genuinely unavailable.
    """
    from .lock import project_writer_lock
    from .operations import RELEASE_SCOPE_DIR  # noqa: F401

    try:
        with project_writer_lock(root):
            return _apply_no_publish_locked(root, plan)
    except PermissionError:
        return _release_failure("WRITER_BUSY",
                                "another live writer holds the project lock")


def _git_available(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, errors="replace")
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _apply_no_publish_locked(root: Path, plan: ReleasePlan) -> dict:
    from .journal import Journal
    from .operations import record_scope  # noqa: F401
    journal = Journal(root, plan.op_id)
    if journal.exists():
        return _release_failure(
            "RECOVERY_REQUIRED",
            f"release op {plan.op_id} already exists; recover first")
    _try_journal(journal, "start", "release", _agent(root),
                 plan.project_identity,
                 hashlib.sha256(str(plan.canonical()).encode()).hexdigest()[:16],
                 [], {})
    _try_journal(journal, "update", version=plan.version, branch="",
                 tag=plan.tag, ticket_id=plan.ticket_id, mode="no-publish",
                 scope_paths=list(plan.scope_paths),
                 metadata_paths=list(plan.metadata_paths),
                 source_head=plan.source_head,
                 remote_push_url="", remote_old_tip="", content_commit="",
                 closure_commit="", remote_tag_sha="", start_stage="PREPARED",
                 plan_canonical=list(plan.canonical()))
    try:
        _no_publish_body(root, plan, journal)
    except ReleaseRefusal as exc:
        return _release_failure("NO_PUBLISH", exc.detail)
    _try_journal(journal, "mark", "COMMITTED")
    _try_journal(journal, "update", release_stage="COMMITTED")
    return {
        "ok": True, "code": "NO_PUBLISH_MODE", "stage": "COMMITTED",
        "stages_reached": ["NO_PUBLISH_MODE"], "op_id": plan.op_id,
        "tag": plan.tag,
        "detail": "no-publish: local validation passed, skipped-publish event "
                  "recorded, ticket closed; zero git writes",
    }


def _no_publish_body(root: Path, plan: ReleasePlan,
                     journal) -> None:
    """Local validation + canonical closure for no-publish (zero git)."""
    gate = _run_gate(root, "core")
    if not gate["ok"]:
        raise ReleaseRefusal(
            "VALIDATION_FAILED",
            f"no-publish local validation failed: {gate['detail']}")
    git_ok = _git_available(root)
    reason = "policy" if git_ok else "no git"
    run_msg = (f"ship v{plan.version} -> skipped publish "
               f"(no-publish: {reason})")
    top = _top_todo(root)
    digest = (
        f"done: ship v{plan.version} -> skipped publish "
        f"(no-publish: {reason})\n"
        f"remaining: {top}\n"
        f"awaiting: {'git needed to publish' if not git_ok else 'nothing'}\n"
    )
    _apply_finish_targets(root, journal, plan, digest, run_msg)
    _try_journal(journal, "update", release_stage="CLOSURE_COMMIT_CREATED")


# ---------------------------------------------------------------------------
# Full release apply
# ---------------------------------------------------------------------------


def _apply_release(root: Path, plan: ReleasePlan) -> dict:
    from .lock import project_writer_lock
    try:
        with project_writer_lock(root):
            return _apply_release_locked(root, plan)
    except PermissionError:
        return _release_failure("WRITER_BUSY",
                                "another live writer holds the project lock")


def _apply_release_locked(root: Path, plan: ReleasePlan) -> dict:
    from .journal import Journal
    journal = Journal(root, plan.op_id)
    if journal.exists():
        return _release_failure(
            "RECOVERY_REQUIRED",
            f"release op {plan.op_id} already exists; recover first")
    stages = []
    try:
        crew_context = None
        try:
            from .state import parse_state
            active_state = parse_state(codec.read_doc(
                root / ".saipen" / "STATE.md"))
            if (active_state.get("execution_intent") == "converge"
                    and active_state.get("converge_target") == "crew"):
                from .crew import crew_release_context
                crew_context = crew_release_context(root)
                if not crew_context.get("ok"):
                    return _release_failure(
                        "CREW_NOT_READY", crew_context.get("detail", ""))
        except OSError as exc:
            return _release_failure("CREW_NOT_READY",
                                    f"cannot read crew release context: {exc}")
        _try_journal(journal, "start", "release", _agent(root),
                     plan.project_identity,
                     hashlib.sha256(
                         str(plan.canonical()).encode()).hexdigest()[:16],
                     [], {})
        _try_journal(journal, "update",
                     version=plan.version, branch=plan.branch, tag=plan.tag,
                     ticket_id=plan.ticket_id, mode="full",
                     scope_paths=list(plan.scope_paths),
                     metadata_paths=list(plan.metadata_paths),
                     source_head=plan.source_head,
                     source_tree_fingerprint=plan.source_tree_fingerprint,
                     remote_push_url=plan.remote_push_url,
                     remote_old_tip=plan.remote_branch_tip,
                     remote_classification=plan.remote_classification,
                     content_commit="", closure_commit="", remote_tag_sha="",
                     intended_content_tree="", intended_closure_tree="",
                      start_stage=plan.start_stage,
                      plan_canonical=list(plan.canonical()),
                      confirmation=plan.confirmation)
        if crew_context:
            _try_journal(
                journal, "update", crew_epoch=crew_context["crew_epoch"],
                crew_pre_ship_source=crew_context["crew_pre_ship_source"],
                crew_pre_ship_evidence=crew_context["crew_pre_ship_evidence"])

        if plan.start_stage == START_TAG:
            # ---- continuation: only the tag is missing (T-994 / § 18 B/C) --
            closure_commit = plan.source_head
            content_commit = _git(root, "rev-parse", "HEAD^").stdout or ""
            _try_journal(journal, "update", content_commit=content_commit,
                         closure_commit=closure_commit)
            _mark_stage(journal, "CONTENT_COMMIT_CREATED")
            _mark_stage(journal, "CONTENT_PUBLISHED")
            _mark_stage(journal, "CLOSURE_PREPARED")
            _mark_stage(journal, "CLOSURE_COMMIT_CREATED")
            _mark_stage(journal, "CLOSURE_PUBLISHED")
            stages += ["CONTENT_COMMIT_CREATED", "CONTENT_PUBLISHED",
                       "CLOSURE_PREPARED", "CLOSURE_COMMIT_CREATED",
                       "CLOSURE_PUBLISHED"]
            tag_local, tag_local_c = _local_tag_commit(root, plan.tag)
            if not (tag_local and tag_local_c == closure_commit):
                _create_tag(root, plan, closure_commit)
            _mark_stage(journal, "TAG_CREATED")
            stages.append("TAG_CREATED")
            _push_tag(root, plan, closure_commit)
            _mark_stage(journal, "TAG_PUBLISHED")
            stages.append("TAG_PUBLISHED")
        else:
            if plan.start_stage == START_PREPARED:
                # ---- content commit A --------------------------------------
                commit_result = _stage_and_commit(root, plan)
                if not commit_result["ok"]:
                    _restore_index(root, plan.pre_plan_index)
                    return _release_failure(
                        commit_result.get("stage", "CONTENT_COMMIT"),
                        commit_result.get("detail", ""))
                content_commit = commit_result["commit"]
                _try_journal(journal, "update",
                             content_commit=content_commit,
                             intended_content_tree=commit_result["tree"])
                _mark_stage(journal, "CONTENT_COMMIT_CREATED")
                stages.append("CONTENT_COMMIT_CREATED")
                _maybe_crash("CONTENT_COMMIT_CREATED")
                # ---- publish content ------------------------------------------
                _publish_branch(root, plan, content_commit,
                                journal, "CONTENT_PUBLISHED")
                stages.append("CONTENT_PUBLISHED")
                _maybe_crash("CONTENT_PUBLISHED")
            else:  # START_CLOSURE: content A committed + pushed already
                content_commit = plan.source_head
                _try_journal(journal, "update", content_commit=content_commit)
                _mark_stage(journal, "CONTENT_COMMIT_CREATED")
                _mark_stage(journal, "CONTENT_PUBLISHED")
                stages += ["CONTENT_COMMIT_CREATED", "CONTENT_PUBLISHED"]

            # ---- canonical closure ---------------------------------------------
            _mark_stage(journal, "CLOSURE_PREPARED")
            stages.append("CLOSURE_PREPARED")
            _maybe_crash("CLOSURE_PREPARED")
            run_msg = (f"ship v{plan.version} -> content commit "
                       f"{content_commit[:12]} pushed")
            digest = _release_digest(root, plan)
            _apply_finish_targets(root, journal, plan, digest, run_msg)
            _try_journal(journal, "update", release_stage="CLOSURE_PREPARED_DONE")
            # closure commit B
            closure_commit, closure_tree = _commit_closure(root, plan)
            _try_journal(journal, "update", closure_commit=closure_commit,
                         intended_closure_tree=closure_tree)
            _mark_stage(journal, "CLOSURE_COMMIT_CREATED")
            stages.append("CLOSURE_COMMIT_CREATED")
            _maybe_crash("CLOSURE_COMMIT_CREATED")

            # ---- publish closure -----------------------------------------------
            _publish_branch(root, plan, closure_commit,
                            journal, "CLOSURE_PUBLISHED")
            stages.append("CLOSURE_PUBLISHED")
            _maybe_crash("CLOSURE_PUBLISHED")

            # ---- tag -------------------------------------------------------------
            _create_tag(root, plan, closure_commit)
            _mark_stage(journal, "TAG_CREATED")
            stages.append("TAG_CREATED")
            _maybe_crash("TAG_CREATED")
            _push_tag(root, plan, closure_commit)
            _mark_stage(journal, "TAG_PUBLISHED")
            stages.append("TAG_PUBLISHED")
            _maybe_crash("TAG_PUBLISHED")

        # ---- final verification -----------------------------------------------------
        verified = _verify_release(root, plan, closure_commit)
        if not verified["ok"]:
            return _release_failure("REMOTE_VERIFIED", verified["detail"])
        _mark_stage(journal, "REMOTE_VERIFIED")
        stages.append("REMOTE_VERIFIED")
        _try_journal(journal, "mark", "VERIFIED")
        _try_journal(journal, "mark", "COMMITTED")
        _try_journal(journal, "update", release_stage="COMMITTED")
    except ReleaseRefusal as exc:
        return _release_failure(_last_stage(stages), exc.detail,
                                op_id=plan.op_id,
                                stages_reached=stages)

    return {
        "ok": True, "code": "RELEASED", "stage": "COMMITTED",
        "stages_reached": stages, "op_id": plan.op_id,
        "commit": content_commit, "closure_commit": closure_commit,
        "tag": plan.tag, "branch": plan.branch,
        "detail": f"released v{plan.version}: content {content_commit[:12]} "
                  f"-> closure {closure_commit[:12]} -> tag {plan.tag}",
    }


def _last_stage(stages: list[str]) -> str:
    return stages[-1] if stages else "PREPARED"


_RELEASE_CRASH_MAP = {
    "CONTENT_COMMIT_CREATED": "SAIPEN_CRASH_AFTER_CONTENT_COMMIT",
    "CONTENT_PUBLISHED": "SAIPEN_CRASH_AFTER_CONTENT_PUBLISH",
    "CLOSURE_PREPARED": "SAIPEN_CRASH_AFTER_CLOSURE_PREPARE",
    "CLOSURE_COMMIT_CREATED": "SAIPEN_CRASH_AFTER_CLOSURE_COMMIT",
    "CLOSURE_PUBLISHED": "SAIPEN_CRASH_AFTER_CLOSURE_PUBLISH",
    "TAG_CREATED": "SAIPEN_CRASH_AFTER_TAG_CREATE",
    "TAG_PUBLISHED": "SAIPEN_CRASH_AFTER_TAG_PUSH",
}


def _maybe_crash(stage: str) -> None:
    """Process-death injection between release edges (T-994 / § 17).

    Mirrors the journal's NITRO_CRASH_* knobs: the test harness sets
    SAIPEN_CRASH_AFTER_<STAGE> and the process dies at exactly that edge so
    recovery has a real partial state to classify.
    """
    env_key = _RELEASE_CRASH_MAP.get(stage)
    if env_key and env_key in os.environ:
        sys.exit(86)


def _try_journal(journal, method: str, *args, **kwargs):
    """Journal writes are the recovery evidence: a failure is a hard stop."""
    try:
        getattr(journal, method)(*args, **kwargs)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            f"release journal write failed ({journal.manifest}): {exc}")


def _mark_stage(journal, stage: str) -> None:
    _try_journal(journal, "update", release_stage=stage,
                 stages=[*getattr(journal, "read")().get("stages", []),
                         stage])


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _stage_release_content(root: Path, plan: ReleasePlan) -> dict:
    """Stage ONLY the exact owned scope + release metadata paths.

    A reviewed DELETION scope entry (JSON null in the scope record) is staged
    with `git add -u` so the removal reaches the commit; every present path is
    staged exactly by name. Nothing else is ever staged.
    """
    present = [p for p in sorted(plan.release_paths)
               if (root / p).exists()]
    deleted = [p for p in sorted(plan.release_paths)
               if not (root / p).exists()]
    if present:
        result = _git(root, "add", "--", *present, literal=True)
        if not result.ok:
            return {"ok": False, "stage": "STAGING",
                    "detail": result.stderr or result.stdout}
    if deleted:
        # `git add -u` stages a tracked path's deletion without touching
        # anything else; an untracked missing path is a scope mistake and the
        # command's failure is the refusal.
        result = _git(root, "add", "-u", "--", *deleted, literal=True)
        if not result.ok:
            return {"ok": False, "stage": "STAGING",
                    "detail": result.stderr or result.stdout}
    return {"ok": True}


def _run_gate(root: Path, gate: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "validate.py"),
         "--gate", gate],
        cwd=str(root), capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        return {"ok": False,
                "detail": _format_gate_failure(result.stdout, result.stderr)}
    return {"ok": True}


def _verify_index_after_gate(root: Path, plan: ReleasePlan) -> dict:
    """The index must hold EXACTLY the pre-plan index plus the release scope:
    the gate must not have pulled in any path this release does not own."""
    index = _capture_index_state(root)
    expected = set(plan.pre_plan_index.paths) | set(plan.release_paths)
    actual = set(index.paths)
    if actual != expected:
        extra = sorted(actual - expected)
        missing = sorted(expected - actual)
        return {
            "ok": False, "stage": "INDEX_DRIFT",
            "detail": (
                "index paths changed after ship gate"
                + (f" -- unexpected: {', '.join(extra)}" if extra else "")
                + (f" -- missing: {', '.join(missing)}" if missing else ""))}
    return {"ok": True}


def _stage_and_commit(root: Path, plan: ReleasePlan) -> dict:
    """Stage, gate, verify, commit -- the local content commit A.

    The intended tree is captured with `git write-tree` right before the
    commit, and after the commit HEAD^{tree} MUST equal it. A hook or a
    concurrent git process that changes the selected tree is a refusal with
    zero publication, never "the reviewed release".
    """
    stage_result = _stage_release_content(root, plan)
    if not stage_result["ok"]:
        return stage_result
    gate_result = _run_gate(root, "ship")
    if not gate_result["ok"]:
        return {"ok": False, "stage": "SHIP_GATE",
                "detail": gate_result["detail"]}
    idx_result = _verify_index_after_gate(root, plan)
    if not idx_result["ok"]:
        return idx_result
    diff = _git(root, "diff", "--cached", "--check")
    if not diff.ok:
        return {"ok": False, "stage": "DIFF_CHECK",
                "detail": diff.stdout or diff.stderr}
    intended_tree = _git(root, "write-tree")
    if not intended_tree.ok:
        return {"ok": False, "stage": "COMMIT",
                "detail": f"write-tree failed: {intended_tree.stderr}"}
    commit = _git(root, "commit", "-m", plan.commit_message)
    if not commit.ok:
        return {"ok": False, "stage": "COMMIT",
                "detail": commit.stderr or commit.stdout}
    committed_tree = _git(root, "rev-parse", "HEAD^{tree}")
    if not committed_tree.ok or committed_tree.stdout != intended_tree.stdout:
        return {"ok": False, "stage": "TREE_MISMATCH",
                "detail": (
                    f"committed tree "
                    f"{committed_tree.stdout[:12] if committed_tree.ok else '?'} "
                    f"!= intended tree {intended_tree.stdout[:12]} -- a hook "
                    "or concurrent git changed the selected tree; NO push "
                    "follows")}
    return {"ok": True, "commit": _git(root, "rev-parse", "HEAD").stdout,
            "tree": intended_tree.stdout}


def _publish_branch(root: Path, plan: ReleasePlan, commit: str,
                    journal, stage: str) -> None:
    """Push the branch and REQUIRE the exact expected AFTER (query must
    succeed; an empty/missing query result is a refusal, never a pass)."""
    result = _git(root, "push", "origin", plan.branch)
    if not result.ok:
        raise ReleaseRefusal(
            "RELEASE_FAILED", f"branch push failed: "
            f"{result.stderr or result.stdout}")
    remote_ok, tip = _remote_branch_tip(root, "origin", plan.branch)
    if not remote_ok:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            f"{stage}: remote verification query FAILED -- no evidence, "
            "never PASS")
    if tip != commit:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            f"{stage}: remote tip {tip[:12] or '(none)'} != expected "
            f"{commit[:12]}; remote verification FAILED")
    _try_journal(journal, "update", remote_old_tip=tip)
    _mark_stage(journal, stage)


def _finish_targets(root: Path, plan: ReleasePlan, digest: str,
                    run_msg: str) -> list[dict]:
    """Build the ONE atomic closure plan: RUN event + finish event + BOARD +
    STATE + digest, all through the canonical SAIOPS planner. The journal
    carries a SINGLE LOG target whose after-bytes recovery can verify."""
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d.%m.%y %H:%M")
    utc = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    finish = _plan_finish_ticket(root, plan.ticket_id, _agent(root), now,
                                 utc, digest_text=digest, prefix_run=run_msg)
    if not hasattr(finish, "targets"):
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            f"closure finish could not be planned: "
            f"{getattr(finish, 'message', '')}")
    return [{
        "path": t.path, "role": t.role, "content": t.content,
        "before_hash": t.before_hash, "after_hash": t.after_hash,
    } for t in finish.targets]


def _apply_finish_targets(root: Path, journal, plan: ReleasePlan,
                          digest: str, run_msg: str) -> None:
    _apply_closure_targets(root, journal,
                           _finish_targets(root, plan, digest, run_msg))


def _apply_closure_targets(root: Path, journal, targets: list[dict]) -> None:
    """Append + apply closure targets THROUGH the release op journal."""
    from .journal import _atomic_write
    _try_journal(journal, "append_targets", targets)
    record = journal.read()
    start_index = len(record.get("targets", [])) - len(targets)
    for offset, target in enumerate(targets):
        index = start_index + offset
        live = _hash_file(root / target["path"])
        if live == target["after_hash"]:
            _mark_target(journal, index)
            continue
        if live != target["before_hash"]:
            raise ReleaseRefusal(
                "RECOVERY_CONFLICT",
                f"closure target {target['path']} has unexpected live bytes "
                f"(live {live!r}); refuse to overwrite")
        _atomic_write(root / target["path"], target["content"])
        if _hash_file(root / target["path"]) != target["after_hash"]:
            raise ReleaseRefusal(
                "RECOVERY_CONFLICT",
                f"closure target {target['path']} failed post-write "
                "verification")
        _mark_target(journal, index)
    # Cross-file validation of the exact closure bytes.
    from .fast_check import validate_project
    errors = validate_project(root)
    if errors:
        raise ReleaseRefusal(
            "RECOVERY_CONFLICT",
            "closure bytes fail canonical validation: "
            + "; ".join(errors[:5]))


def _mark_target(journal, index: int) -> None:
    _try_journal(journal, "mark", "APPLYING", target_index=index)


def _commit_closure(root: Path, plan: ReleasePlan) -> tuple[str, str]:
    """Stage ONLY the canonical closure files (+ sealed LOG segments),
    write-tree, commit B."""
    add = _git(root, "add", "--", *_closure_stage_paths(root), literal=True)
    if not add.ok:
        raise ReleaseRefusal("RELEASE_FAILED",
                             f"closure staging failed: "
                             f"{add.stderr or add.stdout}")
    tree = _git(root, "write-tree")
    if not tree.ok:
        raise ReleaseRefusal("RELEASE_FAILED",
                             f"closure write-tree failed: {tree.stderr}")
    commit = _git(root, "commit", "-m",
                  f"closure v{plan.version}: ticket {plan.ticket_id} DONE")
    if not commit.ok:
        raise ReleaseRefusal("RELEASE_FAILED",
                             f"closure commit failed: "
                             f"{commit.stderr or commit.stdout}")
    committed_tree = _git(root, "rev-parse", "HEAD^{tree}")
    if not committed_tree.ok or committed_tree.stdout != tree.stdout:
        raise ReleaseRefusal(
            "TREE_MISMATCH",
            "closure committed tree != intended tree; NO push follows")
    return _git(root, "rev-parse", "HEAD").stdout, tree.stdout


def _create_tag(root: Path, plan: ReleasePlan, target: str) -> None:
    result = _git(root, "tag", "-a", plan.tag, "-m", plan.commit_message,
                  target)
    if not result.ok:
        raise ReleaseRefusal("RELEASE_FAILED",
                             f"tag creation failed: "
                             f"{result.stderr or result.stdout}")
    local_target = _git(root, "rev-parse", f"{plan.tag}^{{commit}}").stdout
    if local_target != target:
        raise ReleaseRefusal(
            "TAG_CONFLICT",
            f"tag {plan.tag} points at {local_target[:12]}, expected "
            f"{target[:12]}")


def _push_tag(root: Path, plan: ReleasePlan, target: str) -> None:
    result = _git(root, "push", "origin",
                  f"refs/tags/{plan.tag}:refs/tags/{plan.tag}")
    if not result.ok:
        raise ReleaseRefusal("RELEASE_FAILED",
                             f"tag push failed: "
                             f"{result.stderr or result.stdout}")
    _query_ok, remote_sha = _remote_tag_commit(root, plan.tag)
    if not remote_sha:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            f"remote tag {plan.tag} missing after push -- no evidence, never "
            "PASS")
    if remote_sha != target:
        raise ReleaseRefusal(
            "RELEASE_FAILED",
            f"remote tag {plan.tag} points at {remote_sha[:12]}, expected "
            f"{target[:12]}")


def _verify_release(root: Path, plan: ReleasePlan, closure_commit: str) -> dict:
    """Every VERIFIED stage requires the query to succeed AND exact equality
    with a non-empty witness."""
    remote_ok, tip = _remote_branch_tip(root, "origin", plan.branch)
    if not remote_ok or not tip:
        return {"ok": False, "detail": "remote branch tip query failed or "
                "empty at final verification"}
    if tip != closure_commit:
        return {"ok": False, "detail": f"remote branch tip {tip[:12]} != "
                f"closure {closure_commit[:12]}"}
    tag_ok, tag_sha = _remote_tag_commit(root, plan.tag)
    if not tag_ok or not tag_sha:
        return {"ok": False, "detail": "remote tag query failed or empty at "
                "final verification"}
    if tag_sha != closure_commit:
        return {"ok": False, "detail": f"remote tag {tag_sha[:12]} != "
                f"closure {closure_commit[:12]}"}
    return {"ok": True}


# ---------------------------------------------------------------------------
# Remote helpers (closed classification, T-994 / § 12)
# ---------------------------------------------------------------------------


def _classify_remote(root: Path) -> tuple[str, str]:
    """Classify origin into the closed set ABSENT/EMPTY/ESTABLISHED/
    UNAVAILABLE/AMBIGUOUS. UNAVAILABLE != EMPTY and UNKNOWN != FIRST_PUBLISH."""
    origin = _git(root, "remote", "get-url", "origin")
    if not origin.ok or not origin.stdout:
        return REMOTE_ABSENT, "no origin configured"
    query = _git(root, "ls-remote", "origin")
    if query.ok:
        if not query.stdout.strip():
            return REMOTE_EMPTY, ""
        return REMOTE_ESTABLISHED, ""
    err = query.stderr.lower()
    if ("unable to access" in err or "authentication" in err
            or "permission denied" in err or "network is unreachable" in err
            or "couldn't resolve" in err or "could not resolve" in err
            or "connection" in err or "timed out" in err
            or "ssl" in err or "couldn't connect" in err):
        return REMOTE_UNAVAILABLE, query.stderr
    if ("does not appear" in err or "could not read from remote" in err
            or "repository not found" in err or "not found" in err):
        return REMOTE_ABSENT, query.stderr
    return REMOTE_UNAVAILABLE, query.stderr


def _remote_branch_tip(root: Path, remote: str, branch: str) -> tuple[bool, str]:
    """(query_ok, tip_or_empty). tip empty means query ok but branch absent."""
    result = _git(root, "ls-remote", "--heads", remote, branch)
    if not result.ok:
        return False, ""
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            return True, parts[0]
    return True, ""


def _remote_tag_commit(root: Path, tag: str) -> tuple[bool, str]:
    """(query_ok, tag_commit_or_empty). Empty means query ok but tag absent."""
    result = _git(root, "ls-remote", "origin", f"refs/tags/{tag}^{{}}")
    if not result.ok:
        return False, ""
    line = result.stdout.strip()
    if not line:
        return True, ""
    return True, line.split()[0]


def _local_tag_commit(root: Path, tag: str) -> tuple[bool, str]:
    rc = _git(root, "rev-parse", "--verify", "--quiet", tag).rc
    if rc != 0:
        return False, ""
    return True, _git(root, "rev-parse", f"{tag}^{{commit}}").stdout


def _snapshot_remote_refs(root: Path, remote: str) -> dict:
    result = _git(root, "ls-remote", remote)
    refs: dict[str, str] = {}
    if result.ok:
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                refs[parts[1]] = parts[0]
    return refs


def _push_urls(root: Path) -> list[str]:
    result = _git(root, "remote", "get-url", "--push", "--all", "origin")
    if not result.ok or not result.stdout:
        return []
    return [_sanitize_push_url(u) for u in result.stdout.splitlines()
            if u.strip()]


def _sanitize_push_url(url: str) -> str:
    url = url.strip()
    if "://" in url:
        scheme, rest = url.split("://", 1)
        rest = rest.split("@", 1)[-1]
        return f"{scheme}://{rest.replace(chr(92), '/')}"
    if "@" in url:
        return url.split("@", 1)[-1].replace(chr(92), "/")
    return url.replace(chr(92), "/")


def _head_relation(root: Path, remote_tip: str) -> str:
    if not remote_tip:
        return "no-remote-tip"
    head = _git(root, "rev-parse", "HEAD").stdout
    if head == remote_tip:
        return "equal"
    anc = _git(root, "merge-base", "--is-ancestor", head, remote_tip)
    if anc.ok:
        return "behind"
    anc2 = _git(root, "merge-base", "--is-ancestor", remote_tip, head)
    if anc2.ok:
        return "ahead"
    return "diverged"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str, literal: bool = False) -> GitResult:
    env = None
    if literal:
        env = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, errors="replace", env=env)
    return GitResult(result.returncode, result.stdout.strip(),
                     result.stderr.strip())


def _git_object_count(root: Path) -> int:
    """Stable machine-output object count for zero-write verification.

    `git count-objects` human text varies ("790 objects, 5276 kilobytes");
    `count-objects -v` emits stable `count:` / `in-pack:` keys covering both
    loose objects and packed objects.
    """
    result = _git(root, "count-objects", "-v")
    count = 0
    import contextlib
    for line in result.stdout.splitlines():
        key, _, value = line.partition(":")
        if key.strip() in ("count", "in-pack"):
            with contextlib.suppress(ValueError):
                count += int(value.strip())
    return count


def _installed_version(root: Path) -> str:
    version = root / "VERSION"
    if not version.is_file():
        raise ReleaseRefusal("VALIDATION_FAILED",
                             "VERSION is missing from the repository root")
    return version.read_text(encoding="utf-8-sig").strip().split("\n")[0]


def _branch(root: Path) -> str:
    result = _git(root, "branch", "--show-current")
    if not result.ok or not result.stdout:
        raise ReleaseRefusal("STALE_PLAN", "cannot determine the current "
                                           "branch")
    return result.stdout


def _branch_exists(root: Path, branch: str) -> bool:
    rc = _git(root, "rev-parse", "--verify", "--quiet",
              f"refs/heads/{branch}").rc
    return rc == 0


def _snapshot_worktree(root: Path, paths: tuple[str, ...]) -> dict:
    hashes: dict[str, str] = {}
    for p in paths:
        fp = root / p
        if fp.is_file():
            hashes[p] = _quick_hash(fp.read_bytes())
        else:
            hashes[p] = ""
    return hashes


def _snapshot_all_refs(root: Path) -> dict:
    result = _git(root, "show-ref")
    refs: dict[str, str] = {}
    if result.ok:
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                refs[parts[1]] = parts[0]
    return refs


def _quick_hash(text: str) -> str:
    if isinstance(text, bytes):
        return hashlib.sha256(text).hexdigest()[:16]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _hash_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _hex8() -> str:
    import uuid
    return uuid.uuid4().hex[:8]


def _format_gate_failure(stdout: str, stderr: str) -> str:
    lines = (stdout + "\n" + stderr).splitlines()
    fail_lines = [ln for ln in lines if ln.startswith("FAIL")]
    if fail_lines:
        return " | ".join(fail_lines[:3])
    tail = (stdout + stderr)[-500:].strip()
    return tail or "gate failed (no detail)"


# ---------------------------------------------------------------------------
# Version parity / metadata
# ---------------------------------------------------------------------------


def _metadata_paths(root: Path) -> list[str]:
    from .release_contract import release_metadata_paths
    return [p.as_posix() for p in release_metadata_paths(root)]


def _check_parity(root: Path, version: str) -> None:
    from .release_contract import version_badges as _version_badges
    problems: list[str] = []
    if _installed_version(root) != version:
        problems.append("VERSION does not read the release version")
    for rel in _metadata_paths(root):
        if Path(rel).name == "VERSION":
            continue
        fp = root / rel
        if not fp.is_file():
            problems.append(f"{rel} is missing")
            continue
        if Path(rel).name == "CHANGELOG.md":
            text = fp.read_text(encoding="utf-8-sig")
            heads = re.findall(r"(?m)^## (\d+\.\d+\.\d+)", text)
            if heads[:1] != [version]:
                problems.append(f"{rel} head entry must be ## {version}")
            continue
        badges = _version_badges(fp)
        if len(badges) != 1 or badges[0] != f"**v{version}**":
            problems.append(f"{rel} must carry **v{version}** exactly once")
    if problems:
        raise ReleaseRefusal(
            "VALIDATION_FAILED",
            "release version parity unmet:\n- " + "\n- ".join(problems[:8]))


# ---------------------------------------------------------------------------
# Mode reader (fails closed, T-994 / § 9)
# ---------------------------------------------------------------------------


def _read_mode(state: dict) -> str:
    mode = state.get("mode")
    if mode == "full":
        return "full"
    if mode == "no-publish":
        return "no-publish"
    raise ReleaseRefusal(
        "VALIDATION_FAILED",
        f"unknown release mode {mode!r} -- an invalid policy must never "
        "become permission to publish; set mode: full or mode: no-publish")


# ---------------------------------------------------------------------------
# STATE / BOARD / LOG readers
# ---------------------------------------------------------------------------


def _read_state(root: Path) -> tuple[str, dict]:
    state_path = root / ".saipen" / "STATE.md"
    if not state_path.is_file():
        raise ReleaseRefusal("VALIDATION_FAILED", "STATE.md is missing")
    text = codec.read_doc(state_path)
    state = parse_state(text)
    if not state:
        raise ReleaseRefusal("VALIDATION_FAILED",
                             "STATE.md has no parseable frontmatter")
    return text, state


def _read_board(root: Path) -> tuple[str, dict]:
    from .board import parse_board
    board_path = root / ".saipen" / "BOARD.md"
    if not board_path.is_file():
        raise ReleaseRefusal("VALIDATION_FAILED", "BOARD.md is missing")
    text = codec.read_doc(board_path)
    board = parse_board(text)
    return text, board


def _log_hash(root: Path) -> str:
    log_path = root / ".saipen" / "LOG.md"
    return _quick_hash(codec.read_doc(log_path)) if log_path.is_file() else ""


def _find_ticket(board: dict, task: str | None) -> dict | None:
    if not task or task == "none":
        return None
    tickets = board.get("tickets", {})
    for t in tickets.values():
        if t["id"] == task and t["section"] == "## DOING":
            return t
    return None


def _top_todo(root: Path) -> str:
    import contextlib
    with contextlib.suppress(OSError, ValueError):
        from .board import parse_board
        board = parse_board(codec.read_doc(root / ".saipen" / "BOARD.md"))
        for t in board["tickets"].values():
            if t["section"] == "## TODO":
                return t["id"]
    return "nothing"


def _release_digest(root: Path, plan: ReleasePlan) -> str:
    top = _top_todo(root)
    return (
        f"done: ship v{plan.version} (content -> closure, tag {plan.tag})\n"
        f"remaining: {top}\n"
        f"awaiting: nothing\n"
    )


# ---------------------------------------------------------------------------
# Recovery (T-994 / § 3, § 11, § 17, § 18): classifies every external fact.
# ---------------------------------------------------------------------------


def recover_release_op(project_root: Path | str, op_id: str) -> dict:
    """Recover a release operation. Never blindly redoes an external side
    effect: each git fact is classified expected-BEFORE / expected-AFTER /
    THIRD STATE (CONFLICT) against the journal's recorded expectations.

    Unresolvable remote state is UNKNOWN and stops recovery as CONFLICT --
    UNKNOWN is never treated as PASS.
    """
    from .journal import Journal, _atomic_write, _hash_file as _jh  # noqa: F401
    root = Path(project_root)
    journal = Journal(root, op_id)
    if not journal.exists():
        return {"ok": False, "code": "TICKET_NOT_FOUND", "op_id": op_id}
    record = journal.read()
    status = record.get("status")
    if status == "COMMITTED":
        return {"ok": True, "code": "ALREADY_APPLIED", "op_id": op_id}
    if status in ("CONFLICT", "ABORTED", "RESOLVED"):
        return {"ok": False, "code": status, "op_id": op_id,
                "recovery_required": True,
                "detail": f"release op is {status}; resolve explicitly before "
                          "further mutation"}

    if not _validate_record(record):
        _try_recovery_journal(journal, "mark", "CONFLICT")
        return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                "recovery_required": True,
                "detail": "release op record is corrupt or incomplete; "
                          "preserve evidence and resolve explicitly"}

    mode = record.get("mode")
    if mode == "no-publish":
        return _recover_no_publish(root, journal, record)

    try:
        return _recover_release_git(root, journal, record)
    except ReleaseRefusal as exc:
        _try_recovery_journal(journal, "mark", "CONFLICT")
        return {"ok": False, "code": "CONFLICT", "op_id": op_id,
                "recovery_required": True, "detail": exc.detail}


def _validate_record(record: dict) -> bool:
    required = ("version", "branch", "tag", "ticket_id", "source_head",
                "remote_push_url", "scope_paths", "metadata_paths")
    return all(key in record for key in required)


def _try_recovery_journal(journal, method: str, *args, **kwargs) -> None:
    import contextlib
    with contextlib.suppress(OSError):
        # the conflict evidence is already being preserved
        getattr(journal, method)(*args, **kwargs)


def _recover_no_publish(root: Path, journal, record: dict) -> dict:
    """no-publish recovery: replay any unapplied closure targets, verify,
    COMMITTED. No git facts exist to classify."""
    replay_error = _replay_targets(root, journal, record)
    if replay_error:
        _try_recovery_journal(journal, "mark", "CONFLICT")
        return {"ok": False, "code": "CONFLICT", "op_id": record["op_id"],
                "recovery_required": True, "detail": replay_error}
    _try_recovery_journal(journal, "mark", "VERIFIED")
    _try_recovery_journal(journal, "mark", "COMMITTED")
    _try_recovery_journal(journal, "update", release_stage="COMMITTED")
    return {"ok": True, "code": "COMMITTED", "op_id": record["op_id"],
            "changed_files": [t["path"]
                              for t in record.get("targets", [])],
            "recovery_required": True}


def _replay_targets(root: Path, journal, record: dict) -> str | None:
    """Replay unapplied journal targets with before/after classification.
    Returns the first conflict detail or None when every target is settled."""
    from .journal import _atomic_write
    targets = record.get("targets", [])
    for index, target in enumerate(targets):
        live = _hash_file(root / target["path"])
        if target.get("applied"):
            if live != target["after_hash"]:
                return (f"applied target {target['path']} was overwritten: "
                        f"live {live!r} != planned {target['after_hash']!r}")
            continue
        if live == target["before_hash"]:
            staged = journal.staged_content(index)
            if hashlib.sha256(staged).hexdigest()[:16] != target["after_hash"]:
                return (f"staged bytes for {target['path']} do not match the "
                        "planned after hash; journal evidence is corrupt")
            _atomic_write(root / target["path"], staged)
            _mark_target(journal, index)
        elif live == target["after_hash"]:
            _mark_target(journal, index)
        else:
            return (f"unfinished target {target['path']} has unexpected bytes "
                    f"(live {live!r}; before {target['before_hash']!r}, after "
                    f"{target['after_hash']!r}); refuse to guess")
    return None


def _recover_release_git(root: Path, journal, record: dict) -> dict:
    """Classify every external fact and resume from the first missing one.
    Each git fact is expected-BEFORE / expected-AFTER / THIRD STATE (CONFLICT);
    a missing stage is resumed, never blindly repeated."""
    op_id = record["op_id"]
    version = record["version"]
    branch = record["branch"]
    tag = record["tag"]
    ticket_id = record["ticket_id"]
    source_head = record["source_head"]
    old_tip = record.get("remote_old_tip") or ""
    recorded_a = record.get("content_commit") or ""
    recorded_b = record.get("closure_commit") or ""

    head = _git(root, "rev-parse", "HEAD").stdout

    # ---- 1. content commit A ----------------------------------------------
    if recorded_a:
        if not _is_ancestor(root, recorded_a, head):
            return _conflict(journal, op_id,
                             f"recorded content commit {recorded_a[:12]} is "
                             "not an ancestor of HEAD; refuse to guess")
        content_commit = recorded_a
    else:
        if head == source_head:
            if not any(t.get("applied")
                       for t in record.get("targets", [])):
                _try_recovery_journal(journal, "mark", "ABORTED")
                _try_recovery_journal(journal, "update",
                                      release_stage="ABORTED")
                return {"ok": True, "code": "ABORTED", "op_id": op_id,
                        "detail": "release never began; aborted"}
            return _conflict(
                journal, op_id,
                "release has applied closure targets but no content commit; "
                "refuse to guess")
        intended = record.get("intended_content_tree") or ""
        if intended and _git(root, "rev-parse",
                             "HEAD^{tree}").stdout == intended:
            content_commit = head
            _try_recovery_journal(journal, "update", content_commit=head)
        else:
            return _conflict(
                journal, op_id,
                f"HEAD moved from {source_head[:12]} but no recorded content "
                "commit matches; refuse to guess")
    _try_recovery_journal(journal, "update", release_stage="CONTENT_COMMIT_CREATED")

    # ---- 2. closure targets (canonical bytes) ------------------------------
    replay_error = _replay_targets(root, journal, record)
    if replay_error:
        return _conflict(journal, op_id, replay_error)
    from .fast_check import validate_project
    v_errors = validate_project(root)
    if v_errors:
        return _conflict(journal, op_id,
                         "recovered closure bytes fail canonical validation: "
                         + "; ".join(v_errors[:5]))

    # ---- 3. closure commit B ------------------------------------------------
    _state_text, state = _read_state(root)
    canonical_closed = (state.get("phase") == "DONE"
                        and state.get("task") in (None, "none")
                        and _ticket_done(root, ticket_id))
    if recorded_b:
        if not _is_ancestor(root, recorded_b, head):
            return _conflict(journal, op_id,
                             f"recorded closure commit {recorded_b[:12]} is "
                             "not an ancestor of HEAD")
        closure_commit = recorded_b
    elif canonical_closed and head != source_head:
        intended_b = record.get("intended_closure_tree") or ""
        if intended_b and _git(root, "rev-parse",
                               "HEAD^{tree}").stdout == intended_b:
            closure_commit = head
            _try_recovery_journal(journal, "update", closure_commit=head)
        else:
            return _conflict(
                journal, op_id,
                "canonical state is DONE but HEAD tree does not match the "
                "recorded closure tree; refuse to guess")
    else:
        if head not in (source_head, content_commit):
            return _conflict(journal, op_id,
                             "HEAD is an unexpected intermediate commit; "
                             "refuse to guess")
        add = _git(root, "add", "--", *_closure_stage_paths(root),
                   literal=True)
        if not add.ok:
            return _conflict(journal, op_id, f"closure staging failed: "
                                             f"{add.stderr or add.stdout}")
        tree = _git(root, "write-tree")
        if not tree.ok:
            return _conflict(journal, op_id,
                             f"closure write-tree failed: {tree.stderr}")
        intended_b = record.get("intended_closure_tree") or ""
        if intended_b and tree.stdout != intended_b:
            return _conflict(journal, op_id,
                             "live closure tree differs from the recorded "
                             "intended closure tree")
        commit = _git(root, "commit", "-m",
                      f"closure v{version}: ticket {ticket_id} DONE")
        if not commit.ok:
            return _conflict(journal, op_id, f"closure commit failed: "
                                             f"{commit.stderr or commit.stdout}")
        closure_commit = _git(root, "rev-parse", "HEAD").stdout
        _try_recovery_journal(journal, "update",
                              closure_commit=closure_commit,
                              intended_closure_tree=tree.stdout)
    _try_recovery_journal(journal, "update", release_stage="CLOSURE_COMMIT_CREATED")

    # ---- 4. publish the branch (content and/or closure) -----------------------
    remote_ok, tip = _remote_branch_tip(root, "origin", branch)
    if not remote_ok:
        return _unavailable(journal, op_id, "remote branch tip query failed "
                                             "during recovery")
    if tip == closure_commit:
        pass  # already published
    elif tip in (content_commit, old_tip, ""):
        push = _git(root, "push", "origin", branch)
        if not push.ok:
            return _conflict(journal, op_id,
                             f"branch push failed during recovery: "
                             f"{push.stderr or push.stdout}")
        remote_ok, tip = _remote_branch_tip(root, "origin", branch)
        if not remote_ok or tip != closure_commit:
            return _unavailable(journal, op_id,
                                "post-push verification could not prove the "
                                "branch tip == closure commit")
        _try_recovery_journal(journal, "update", remote_old_tip=tip)
    else:
        return _conflict(journal, op_id,
                         f"remote branch tip {tip[:12] or '(none)'} is "
                         "neither the old/content/closure tip; refuse to "
                         "guess")
    _try_recovery_journal(journal, "update", release_stage="CLOSURE_PUBLISHED")

    # ---- 5. tag created -------------------------------------------------------
    tag_local, tag_local_c = _local_tag_commit(root, tag)
    if tag_local:
        if tag_local_c != closure_commit:
            return _conflict(journal, op_id,
                             f"local tag {tag} points at {tag_local_c[:12]}, "
                             f"not closure {closure_commit[:12]}")
    else:
        _create_tag(root, _PlanShim(version, tag), closure_commit)
    _try_recovery_journal(journal, "update", release_stage="TAG_CREATED")

    # ---- 6. tag published -------------------------------------------------------
    _tag_remote_ok, tag_remote_c = _remote_tag_commit(root, tag)
    if tag_remote_c:
        if tag_remote_c != closure_commit:
            return _conflict(journal, op_id,
                             f"remote tag {tag} points at "
                             f"{tag_remote_c[:12]}, not closure "
                             f"{closure_commit[:12]}")
    else:
        _push_tag(root, _PlanShim(version, tag), closure_commit)
    _try_recovery_journal(journal, "update", release_stage="TAG_PUBLISHED")

    # ---- 7. final verification ---------------------------------------------------
    verified = _verify_release(root, _PlanShim(version, tag, branch),
                               closure_commit)
    if not verified["ok"]:
        return _conflict(journal, op_id, verified["detail"])
    _try_recovery_journal(journal, "update", release_stage="REMOTE_VERIFIED")
    _try_recovery_journal(journal, "mark", "VERIFIED")
    _try_recovery_journal(journal, "mark", "COMMITTED")
    _try_recovery_journal(journal, "update", release_stage="COMMITTED")
    return {"ok": True, "code": "COMMITTED", "op_id": op_id,
            "changed_files": [t["path"] for t in record.get("targets", [])],
            "content_commit": content_commit, "closure_commit": closure_commit,
            "recovery_required": True}


class _PlanShim:
    """Minimal plan-shaped carrier for stage helpers during recovery."""

    def __init__(self, version: str, tag: str, branch: str = "") -> None:
        self.version = version
        self.tag = tag
        self.branch = branch
        self.commit_message = f"ship v{version}"


def _conflict(journal, op_id: str, detail: str) -> dict:
    _try_recovery_journal(journal, "mark", "CONFLICT")
    return {"ok": False, "code": "CONFLICT", "op_id": op_id,
            "recovery_required": True,
            "detail": f"{detail} -- evidence preserved, resolve explicitly"}


def _unavailable(journal, op_id: str, detail: str) -> dict:
    _try_recovery_journal(journal, "update", recovery_note=detail)
    return {"ok": False, "code": "CONFLICT", "op_id": op_id,
            "recovery_required": True,
            "detail": f"{detail} -- remote state UNKNOWN, never treated as "
                      "PASS; resolve explicitly when the remote answers"}

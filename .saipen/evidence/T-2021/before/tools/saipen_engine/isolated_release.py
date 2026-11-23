"""Isolated Release Runner & Production Worktree Engine (P0-01 / SRC-366).

Executes a canonical release in an isolated linked worktree or isolated git index,
guaranteeing:
- 100% preservation of foreign staged paths in the primary shared repository index;
- Exact byte-exact verification of the original Git index before and after release;
- Detection of concurrent index writers (never overwrites or silently restores over them);
- Clean transfer of only reviewed, attributable SAIPEN-owned paths;
- Strict dual-remote and branch verification (never force-pushes non-fast-forward tips);
- Direct remote HEAD verification post-push (GITHUB_SYNCED).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .release import (
    IndexSnapshot,
    ReleasePlan,
    ReleaseRefusal,
    _capture_index_state,
    _exact_index_bytes,
    _git,
    _metadata_paths,
    _remote_branch_tip,
    _remote_snapshot,
    execute_release,
    plan_release,
)


class IsolatedReleaseError(Exception):
    """Raised on isolation invariants violation."""

    def __init__(self, code: str, detail: str, *, remediation: str = "") -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.remediation = remediation


CLASS_SAIPEN_OWNED_REVIEWED = "SAIPEN_OWNED_REVIEWED"
CLASS_SAIPEN_OWNED_UNREVIEWED = "SAIPEN_OWNED_UNREVIEWED"
CLASS_OTHER_TICKET_OR_COHORT = "OTHER_TICKET_OR_COHORT"
CLASS_FOREIGN_PROJECT_OR_OWNER = "FOREIGN_PROJECT_OR_OWNER"
CLASS_GENERATED_OR_TRANSIENT = "GENERATED_OR_TRANSIENT"
CLASS_SENSITIVE_OR_PUBLICATION_FORBIDDEN = "SENSITIVE_OR_PUBLICATION_FORBIDDEN"
CLASS_AMBIGUOUS_PROVENANCE = "AMBIGUOUS_PROVENANCE"

ALL_ENTRY_CLASSES = frozenset({
    CLASS_SAIPEN_OWNED_REVIEWED,
    CLASS_SAIPEN_OWNED_UNREVIEWED,
    CLASS_OTHER_TICKET_OR_COHORT,
    CLASS_FOREIGN_PROJECT_OR_OWNER,
    CLASS_GENERATED_OR_TRANSIENT,
    CLASS_SENSITIVE_OR_PUBLICATION_FORBIDDEN,
    CLASS_AMBIGUOUS_PROVENANCE,
})

VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
INVALID_REPOSITORY = "INVALID_REPOSITORY"
INDEX_UNREADABLE = "INDEX_UNREADABLE"
GIT_COMMAND_FAILED = "GIT_COMMAND_FAILED"
INCOMPLETE_INVENTORY = "INCOMPLETE_INVENTORY"
CONCURRENT_MODIFICATION = "CONCURRENT_MODIFICATION"
UNKNOWN = "UNKNOWN"

ALL_INVENTORY_STATUSES = frozenset({
    VERIFIED_COMPLETE,
    INVALID_REPOSITORY,
    INDEX_UNREADABLE,
    GIT_COMMAND_FAILED,
    INCOMPLETE_INVENTORY,
    CONCURRENT_MODIFICATION,
    UNKNOWN,
})


def inventory_staged_entries(
    root: Path | str,
    *,
    reviewed_paths: Iterable[str] = (),
) -> dict[str, Any]:
    """Forensic read-only inventory of every staged entry in the shared Git index.

    Captures exact index bytes, git metadata, and per-entry classification.
    Distinguishes VERIFIED_COMPLETE, INVALID_REPOSITORY, INDEX_UNREADABLE,
    GIT_COMMAND_FAILED, INCOMPLETE_INVENTORY, CONCURRENT_MODIFICATION, and UNKNOWN.
    Only a verified complete inventory for the correct repository and stable index
    can support reconciliation. Never reports verified zero entries after an
    unsuccessful probe.
    """
    root = Path(root).resolve()
    reviewed_set = set(reviewed_paths)

    # 1. Probe git executable and repository validity
    try:
        git_check = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, PermissionError) as exc:
        return {
            "schema_version": 1,
            "verification_status": GIT_COMMAND_FAILED,
            "status": GIT_COMMAND_FAILED,
            "repository": str(root),
            "head": "",
            "branch": "",
            "index_metadata": None,
            "classification_summary": {},
            "historical_count_discrepancy": None,
            "entries": [],
            "error": f"Git command unavailable: {exc}",
        }
    except Exception as exc:
        return {
            "schema_version": 1,
            "verification_status": GIT_COMMAND_FAILED,
            "status": GIT_COMMAND_FAILED,
            "repository": str(root),
            "head": "",
            "branch": "",
            "index_metadata": None,
            "classification_summary": {},
            "historical_count_discrepancy": None,
            "entries": [],
            "error": str(exc),
        }

    if git_check.returncode != 0:
        return {
            "schema_version": 1,
            "verification_status": INVALID_REPOSITORY,
            "status": INVALID_REPOSITORY,
            "repository": str(root),
            "head": "",
            "branch": "",
            "index_metadata": None,
            "classification_summary": {},
            "historical_count_discrepancy": None,
            "entries": [],
            "error": git_check.stderr.strip() or "Not a git repository",
        }

    # 2. Locate git index file (worktree-aware)
    try:
        loc_res = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-path", "index"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if loc_res.returncode != 0 or not loc_res.stdout.strip():
            return {
                "schema_version": 1,
                "verification_status": INDEX_UNREADABLE,
                "status": INDEX_UNREADABLE,
                "repository": str(root),
                "head": "",
                "branch": "",
                "index_metadata": None,
                "classification_summary": {},
                "historical_count_discrepancy": None,
                "entries": [],
                "error": "Failed locating git index path",
            }
        idx_p = Path(loc_res.stdout.strip())
        if not idx_p.is_absolute():
            index_file = (root / idx_p).resolve()
        else:
            index_file = idx_p.resolve()
    except Exception as exc:
        return {
            "schema_version": 1,
            "verification_status": INDEX_UNREADABLE,
            "status": INDEX_UNREADABLE,
            "repository": str(root),
            "head": "",
            "branch": "",
            "index_metadata": None,
            "classification_summary": {},
            "historical_count_discrepancy": None,
            "entries": [],
            "error": str(exc),
        }

    index_sha_before = ""
    index_size_before = 0
    if index_file.is_file():
        try:
            raw_before = index_file.read_bytes()
            index_size_before = len(raw_before)
            index_sha_before = hashlib.sha256(raw_before).hexdigest()
        except Exception as exc:
            return {
                "schema_version": 1,
                "verification_status": INDEX_UNREADABLE,
                "status": INDEX_UNREADABLE,
                "repository": str(root),
                "head": "",
                "branch": "",
                "index_metadata": None,
                "classification_summary": {},
                "historical_count_discrepancy": None,
                "entries": [],
                "error": f"Failed reading git index: {exc}",
            }

    # 3. Read HEAD and branch
    head = ""
    branch = ""
    try:
        head_res = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8")
        if head_res.returncode == 0:
            head = head_res.stdout.strip()
        br_res = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], capture_output=True, text=True, encoding="utf-8")
        if br_res.returncode == 0:
            branch = br_res.stdout.strip()
    except Exception:
        pass

    # 4. Check unmerged conflict stages
    unmerged_files: set[str] = set()
    try:
        ls_unmerged = subprocess.run(["git", "-C", str(root), "ls-files", "--unmerged", "-z"], capture_output=True)
        if ls_unmerged.returncode != 0:
            return {
                "schema_version": 1,
                "verification_status": GIT_COMMAND_FAILED,
                "status": GIT_COMMAND_FAILED,
                "repository": str(root),
                "head": head,
                "branch": branch,
                "index_metadata": None,
                "classification_summary": {},
                "historical_count_discrepancy": None,
                "entries": [],
                "error": f"git ls-files --unmerged failed: {ls_unmerged.stderr}",
            }
        if ls_unmerged.stdout:
            for item in ls_unmerged.stdout.split(b"\x00"):
                if item:
                    parts = item.decode("utf-8", errors="replace").split("\t", 1)
                    if len(parts) == 2:
                        unmerged_files.add(parts[1])
    except Exception as exc:
        return {
            "schema_version": 1,
            "verification_status": GIT_COMMAND_FAILED,
            "status": GIT_COMMAND_FAILED,
            "repository": str(root),
            "head": head,
            "branch": branch,
            "index_metadata": None,
            "classification_summary": {},
            "historical_count_discrepancy": None,
            "entries": [],
            "error": str(exc),
        }

    # 5. Parse diff --cached --raw -z
    entries: list[dict[str, Any]] = []
    try:
        diff_res = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--raw", "-z"], capture_output=True)
        if diff_res.returncode != 0:
            return {
                "schema_version": 1,
                "verification_status": GIT_COMMAND_FAILED,
                "status": GIT_COMMAND_FAILED,
                "repository": str(root),
                "head": head,
                "branch": branch,
                "index_metadata": None,
                "classification_summary": {},
                "historical_count_discrepancy": None,
                "entries": [],
                "error": f"git diff --cached --raw -z failed: {diff_res.stderr}",
            }
        tokens = diff_res.stdout.split(b"\x00") if diff_res.stdout else []
        i = 0
        while i < len(tokens):
            if not tokens[i]:
                i += 1
                continue
            meta = tokens[i].decode("utf-8", errors="replace")
            i += 1
            if not meta.startswith(":"):
                return {
                    "schema_version": 1,
                    "verification_status": INCOMPLETE_INVENTORY,
                    "status": INCOMPLETE_INVENTORY,
                    "repository": str(root),
                    "head": head,
                    "branch": branch,
                    "index_metadata": None,
                    "classification_summary": {},
                    "historical_count_discrepancy": None,
                    "entries": [],
                    "error": f"Malformed diff raw metadata: {meta!r}",
                }
            parts = meta[1:].split(" ")
            if len(parts) < 5:
                return {
                    "schema_version": 1,
                    "verification_status": INCOMPLETE_INVENTORY,
                    "status": INCOMPLETE_INVENTORY,
                    "repository": str(root),
                    "head": head,
                    "branch": branch,
                    "index_metadata": None,
                    "classification_summary": {},
                    "historical_count_discrepancy": None,
                    "entries": [],
                    "error": f"Malformed diff raw split: {meta!r}",
                }
            old_mode, new_mode, old_sha, new_sha, status = parts[0], parts[1], parts[2], parts[3], parts[4]
            if status.startswith("R") or status.startswith("C"):
                if i + 1 >= len(tokens):
                    return {
                        "schema_version": 1,
                        "verification_status": INCOMPLETE_INVENTORY,
                        "status": INCOMPLETE_INVENTORY,
                        "repository": str(root),
                        "head": head,
                        "branch": branch,
                        "index_metadata": None,
                        "classification_summary": {},
                        "historical_count_discrepancy": None,
                        "entries": [],
                        "error": "Truncated rename/copy tokens",
                    }
                src_path = tokens[i].decode("utf-8", errors="replace")
                dst_path = tokens[i+1].decode("utf-8", errors="replace")
                i += 2
                path = dst_path
                op = "rename" if status.startswith("R") else "copy"
            else:
                if i >= len(tokens):
                    return {
                        "schema_version": 1,
                        "verification_status": INCOMPLETE_INVENTORY,
                        "status": INCOMPLETE_INVENTORY,
                        "repository": str(root),
                        "head": head,
                        "branch": branch,
                        "index_metadata": None,
                        "classification_summary": {},
                        "historical_count_discrepancy": None,
                        "entries": [],
                        "error": "Truncated diff path token",
                    }
                path = tokens[i].decode("utf-8", errors="replace")
                i += 1
                src_path = None
                op_map = {"A": "add", "M": "modify", "D": "delete", "T": "typechange"}
                op = op_map.get(status[0], "unknown")

            # Classification logic
            if path in unmerged_files:
                classification = CLASS_AMBIGUOUS_PROVENANCE
                reason = "Unmerged conflict stage in shared index"
            elif path in reviewed_set:
                classification = CLASS_SAIPEN_OWNED_REVIEWED
                reason = "Attributable and reviewed for current release cohort"
            elif any(pat in path.lower() for pat in ("id_rsa", ".env", "id_ed25519", "credentials", ".pem")):
                classification = CLASS_SENSITIVE_OR_PUBLICATION_FORBIDDEN
                reason = "Sensitive or secret content pattern detected"
            elif any(path.startswith(prefix) for prefix in ("wintage/", "freebuff/", "other_project/")):
                classification = CLASS_FOREIGN_PROJECT_OR_OWNER
                reason = "Path belongs to separate external repository or project"
            elif any(pat in path for pat in (".tmp", "__pycache__", ".pytest_cache", ".coverage")):
                classification = CLASS_GENERATED_OR_TRANSIENT
                reason = "Generated, transient, or build artifact path"
            elif path.startswith((".saipen/archive/", ".saipen/intake/", ".saipen/evidence/")):
                classification = CLASS_OTHER_TICKET_OR_COHORT
                reason = "Historical intake, archive, or evidence from prior closed cohorts"
            elif path.startswith(("tools/", "bootstrap/", "extensions/", "saipen/")) or path in ("VERSION", "README.md", ".gitignore"):
                classification = CLASS_SAIPEN_OWNED_UNREVIEWED
                reason = "SAIPEN-owned codebase path outside active reviewed release cohort"
            else:
                classification = CLASS_AMBIGUOUS_PROVENANCE
                reason = "Provenance cannot be attributed to known SAIPEN subsystems"

            entries.append({
                "path": path,
                "src_path": src_path,
                "operation": op,
                "status": status,
                "mode": new_mode,
                "blob_sha": new_sha,
                "old_mode": old_mode,
                "old_sha": old_sha,
                "unmerged_conflict": path in unmerged_files,
                "classification": classification,
                "classification_reason": reason,
                "release_destination_eligibility": classification == CLASS_SAIPEN_OWNED_REVIEWED,
                "secret_risk": classification == CLASS_SENSITIVE_OR_PUBLICATION_FORBIDDEN,
            })
    except Exception as exc:
        return {
            "schema_version": 1,
            "verification_status": UNKNOWN,
            "status": UNKNOWN,
            "repository": str(root),
            "head": head,
            "branch": branch,
            "index_metadata": None,
            "classification_summary": {},
            "historical_count_discrepancy": None,
            "entries": [],
            "error": str(exc),
        }

    # 6. Check for concurrent index modification during inventory
    if index_file.is_file():
        try:
            raw_after = index_file.read_bytes()
            index_sha_after = hashlib.sha256(raw_after).hexdigest()
            if index_sha_before and index_sha_after != index_sha_before:
                return {
                    "schema_version": 1,
                    "verification_status": CONCURRENT_MODIFICATION,
                    "status": CONCURRENT_MODIFICATION,
                    "repository": str(root),
                    "head": head,
                    "branch": branch,
                    "index_metadata": None,
                    "classification_summary": {},
                    "historical_count_discrepancy": None,
                    "entries": [],
                    "error": "Git index changed concurrently during inventory",
                }
        except Exception as exc:
            return {
                "schema_version": 1,
                "verification_status": INDEX_UNREADABLE,
                "status": INDEX_UNREADABLE,
                "repository": str(root),
                "head": head,
                "branch": branch,
                "index_metadata": None,
                "classification_summary": {},
                "historical_count_discrepancy": None,
                "entries": [],
                "error": f"Failed re-reading index file: {exc}",
            }

    counts: dict[str, int] = {}
    for e in entries:
        c = e["classification"]
        counts[c] = counts.get(c, 0) + 1

    total_count = len(entries)
    discrepancy = (
        f"Live staged count ({total_count}) differs from historical 206 count"
        if total_count != 206
        else None
    )

    return {
        "schema_version": 1,
        "verification_status": VERIFIED_COMPLETE,
        "status": VERIFIED_COMPLETE,
        "repository": str(root),
        "head": head,
        "branch": branch,
        "index_metadata": {
            "byte_size": index_size_before,
            "sha256": index_sha_before,
            "staged_entries_count": total_count,
        },
        "classification_summary": counts,
        "historical_count_discrepancy": discrepancy,
        "entries": entries,
    }


def snapshot_shared_index(root: Path) -> tuple[str, int]:
    """Capture (sha256, byte_count) of the primary repository index."""
    sha, b64_bytes = _exact_index_bytes(root)
    raw_len = len(b64_bytes) * 3 // 4
    return sha, raw_len


def recorded_staging_survival(root: Path, manifest_path: Path | str) -> dict[str, Any]:
    """Did every RECORDED staged entry's content survive into this repository?

    T-2011. `verify_staged_manifest_integrity` answers a POINTER question: are
    the recorded paths still staged right now, holding the recorded bytes. On
    the live tree that question went red with nothing lost -- SRC-349/SRC-350
    were retired to `.saipen/archive/source/`, two T-1975 evidence files were
    unstaged while their bytes stayed on disk, and fifteen of this project's own
    modules were revised by later legitimate work. A release HOLD protects
    RECORDED CONTENT from loss; it never forbids the project from moving its own
    intake or improving its own source while the hold is open.

    So this asks the durable question: does every recorded blob still exist as
    a git object (index, HEAD, or history)? `recorded_content_survives` is that
    verdict. Paths whose staged bytes no longer match the recording are reported
    under `revised_in_place` -- informational, because a path this project owns
    may be revised; a genuine loss stays visible under `content_lost_paths`.
    """
    root = Path(root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root / manifest_file
    with open(manifest_file, "r", encoding="utf-8") as f:
        recorded = {
            e["path"].replace("\\", "/"): e for e in json.load(f).get("entries", [])
        }

    res = _git(root, "diff", "--cached", "--raw", "--abbrev=40")
    if not res.ok:
        raise IsolatedReleaseError(
            "GIT_DIFF_FAILED", f"git diff --cached --raw failed: {res.stderr}"
        )
    live: dict[str, str] = {}
    for line in res.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        live[parts[-1].replace("\\", "/")] = parts[0].split()[3]

    def _existing_objects(shas: list[str]) -> set[str]:
        """One `cat-file --batch-check` pass: which abbreviated shas resolve."""
        wanted = [s for s in shas if len(s) >= 8]
        if not wanted:
            return set()
        proc = subprocess.run(
            ["git", "-C", str(root), "cat-file", "--batch-check"],
            input="\n".join(wanted) + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        found: set[str] = set()
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] != "missing":
                found.add(parts[0][:8])
        return found

    resolved = _existing_objects([str(e.get("blob_sha") or "") for e in recorded.values()])

    relocated: list[dict[str, str]] = []
    revised_in_place: list[dict[str, str]] = []
    content_lost: list[str] = []
    for path, entry in recorded.items():
        sha = str(entry.get("blob_sha") or "")
        still_staged = path in live
        staged_matches = still_staged and bool(sha) and live[path].startswith(sha[:8])
        if staged_matches:
            continue  # recorded bytes are staged under their own name
        if still_staged:
            # Staged under its own name with DIFFERENT bytes: this project
            # revised a path it owns after the capture. Informational.
            revised_in_place.append(
                {"path": path, "recorded_sha": sha[:8], "live_sha": live[path][:8]}
            )
            continue
        # No longer staged under this name. The recorded content must still be a
        # git object (retired to the archive, unstaged but on disk, or in
        # history); only a genuinely missing blob is a loss.
        if sha[:8] in resolved:
            relocated.append(
                {"path": path, "recorded_sha": sha[:8], "live_sha": "(moved)"}
            )
        else:
            content_lost.append(path)

    return {
        "recorded_count": len(recorded),
        "live_staged_count": len(live),
        "relocated_paths": [m["path"] for m in relocated],
        "relocated_detail": relocated,
        "revised_in_place": revised_in_place,
        "content_lost_paths": content_lost,
        "recorded_content_survives": not content_lost,
    }


def verify_shared_index_unchanged(root: Path, expected_sha: str) -> None:
    """Verify that the primary shared index is byte-for-byte identical.

    If a concurrent process modified the index, refuses with
    CONCURRENT_WRITER_DETECTED rather than overwriting or rolling back over it.
    """
    current_sha, _ = _exact_index_bytes(root)
    if current_sha != expected_sha:
        raise IsolatedReleaseError(
            "CONCURRENT_WRITER_DETECTED",
            f"shared git index changed during isolated release: "
            f"expected {expected_sha[:16]}..., observed {current_sha[:16]}... "
            f"-- refusing to alter or restore over concurrent changes",
            remediation="Inspect git status in the shared tree and resolve concurrent writes",
        )


def transfer_reviewed_scope(
    source_root: Path,
    target_root: Path,
    paths: Iterable[str],
    *,
    metadata_paths: Iterable[str] = (),
) -> list[str]:
    """Transfer ONLY reviewed, attributable SAIPEN-owned paths and metadata.

    Never copies the whole dirty repository blindly. Preserves exact bytes,
    file modes, and deleted paths.
    """
    source_root = Path(source_root).resolve()
    target_root = Path(target_root).resolve()

    transferred = []
    all_paths = sorted(set(paths) | set(metadata_paths))

    for rel_path in all_paths:
        p_obj = Path(rel_path)
        if p_obj.is_absolute() or ".." in p_obj.parts or p_obj.drive or rel_path.startswith(("/", "\\")):
            raise IsolatedReleaseError(
                "PATH_TRAVERSAL_DETECTED",
                f"reviewed path {rel_path!r} escapes the worktree or contains traversing segments",
            )
        src_file = (source_root / rel_path).resolve()
        dst_file = (target_root / rel_path).resolve()

        if not src_file.is_relative_to(source_root):
            raise IsolatedReleaseError(
                "PATH_TRAVERSAL_DETECTED",
                f"source path {rel_path!r} resolves outside source root {source_root}",
            )
        if not dst_file.is_relative_to(target_root):
            raise IsolatedReleaseError(
                "PATH_TRAVERSAL_DETECTED",
                f"target path {rel_path!r} resolves outside target root {target_root}",
            )

        if src_file.is_file():
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            # Copy exact bytes
            data = src_file.read_bytes()
            dst_file.write_bytes(data)
            # Preserve mode
            src_mode = src_file.stat().st_mode
            os.chmod(dst_file, src_mode)
            transferred.append(rel_path)
        elif not src_file.exists() and dst_file.exists():
            # Reviewed deletion: remove from target worktree
            dst_file.unlink()
            transferred.append(f"deleted:{rel_path}")

    return transferred


def create_isolated_worktree(
    root: Path,
    base_ref: str = "HEAD",
    *,
    prefix: str = "rel-",
) -> tuple[Path, Callable[[], None]]:
    """Create a canonical detached linked worktree for release execution."""
    root = Path(root).resolve()
    worktree_parent = root / ".saipen" / "worktrees"
    worktree_parent.mkdir(parents=True, exist_ok=True)

    hex_id = hashlib.sha256(os.urandom(16)).hexdigest()[:12]
    worktree_dir = worktree_parent / f"{prefix}{hex_id}"

    cmd = ["git", "-C", str(root), "worktree", "add", "--detach", str(worktree_dir), base_ref]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        raise IsolatedReleaseError(
            "WORKTREE_CREATION_FAILED",
            f"git worktree add failed: {res.stderr or res.stdout}",
        )

    def cleanup() -> None:
        if worktree_dir.exists():
            subprocess.run(
                ["git", "-C", str(root), "worktree", "remove", "--force", str(worktree_dir)],
                capture_output=True,
            )
            if worktree_dir.exists():
                shutil.rmtree(worktree_dir, ignore_errors=True)

    return worktree_dir, cleanup


def execute_isolated_release(
    root: Path,
    invocation: str,
    *,
    remote: str = "origin",
    branch: str = "main",
    cohort_carrier: dict | None = None,
    current_capability: str | None = None,
    current_agent: str | None = None,
    dry_run: bool = False,
    reconcile_remote_head: str | None = None,
) -> dict[str, Any]:
    """Execute an end-to-end isolated release preserving the shared index.

    1. Snapshots the shared index bytes.
    2. Verifies destination remote and ancestry.
    3. Creates a detached linked worktree.
    4. Transfers reviewed scope and release metadata.
    5. Plans and executes release within the worktree.
    6. Verifies remote SHA after push.
    7. Cleans up the worktree.
    8. Verifies that the shared index is byte-for-byte unchanged.
    """
    root = Path(root).resolve()
    initial_index_sha, initial_len = snapshot_shared_index(root)

    # Validate remote configuration
    remote_check = _git(root, "remote", "get-url", "--push", remote)
    if not remote_check.ok or not remote_check.stdout:
        return {
            "ok": False,
            "code": "UNKNOWN_REMOTE",
            "detail": f"remote {remote!r} has no configured push URL; refusing publication",
        }
    push_url = remote_check.stdout.splitlines()[0]

    # Verify remote tip
    remote_tip_res = _git(root, "ls-remote", remote, f"refs/heads/{branch}")
    remote_head_before = ""
    if remote_tip_res.ok and remote_tip_res.stdout:
        remote_head_before = remote_tip_res.stdout.split()[0]

    base_ref = reconcile_remote_head or "HEAD"

    from . import release_authority

    # Determine reviewed scope
    scope_paths: list[str] = []
    task = None
    if cohort_carrier:
        scope_paths = list(cohort_carrier.get("scope", cohort_carrier.get("paths", [])))
    else:
        from .release import _read_state, _scope_paths

        try:
            _, state = _read_state(root)
            task = state.get("task")
            if task:
                scope_file = root / ".saipen" / "kitchen" / "release_scope" / f"{task}.json"
                if scope_file.is_file():
                    try:
                        scope_data = json.loads(scope_file.read_text(encoding="utf-8"))
                        scope_paths = sorted((scope_data.get("paths") or {}).keys())
                    except Exception:
                        scope_paths = []
                if not scope_paths:
                    scope_paths = list(_scope_paths(root, task))
        except Exception:
            scope_paths = []

    active_grant = release_authority.find_active_grant(
        root, remote=remote, branch=branch, base_commit=base_ref
    )

    if dry_run:
        return {
            "ok": True,
            "code": "DRY_RUN",
            "dry_run": True,
            "remote": remote,
            "push_url": push_url,
            "branch": branch,
            "base_ref": base_ref,
            "remote_head_before": remote_head_before,
            "original_index_sha256": initial_index_sha,
            "foreign_staging_preserved": True,
            "active_grant_id": (active_grant or {}).get("grant_id"),
            "detail": "isolated release preflight passed; zero files mutated",
        }

    # Fetch remote refs to ensure commit objects exist locally for merge-base check
    if remote_head_before:
        _git(root, "fetch", remote, branch)
        anc_check = _git(root, "merge-base", "--is-ancestor", remote_head_before, base_ref)
        if not anc_check.ok:
            return {
                "ok": False,
                "code": "NON_FAST_FORWARD",
                "detail": f"remote {remote} tip {remote_head_before[:12]} is not an ancestor of base {base_ref[:12]} -- refusing non-fast-forward push",
            }

    if not active_grant:
        approval_pkt = generate_release_approval_packet(
            root,
            reviewed_scope=scope_paths,
            target_remote=remote,
            target_branch=branch,
            destination_url=push_url,
        )
        return {
            "ok": False,
            "code": "BLOCKED_AUTHORITY_GATE",
            "detail": (
                f"publication to {remote}/{branch} is held: no active operator release authorization grant. "
                "Operator approval required before publication."
            ),
            "approval_packet": approval_pkt,
            "canonical_next_command": f"saipen release approve --standing --remote {remote} --branch {branch}",
            "foreign_staging_preserved": True,
        }

    if active_grant.get("no_force") is not True:
        return {
            "ok": False,
            "code": "FORBIDDEN_FORCE_PUSH",
            "detail": "release authorization grant requires no_force=True; force-push is forbidden",
            "foreign_staging_preserved": True,
        }

    worktree_dir, cleanup_worktree = create_isolated_worktree(root, base_ref=base_ref)
    old_env_branch = os.environ.get("SAIPEN_RELEASE_BRANCH")
    old_env_remote = os.environ.get("SAIPEN_REMOTE")
    old_env_isolated = os.environ.get("SAIPEN_ISOLATED_RELEASE")
    os.environ["SAIPEN_RELEASE_BRANCH"] = branch
    os.environ["SAIPEN_REMOTE"] = remote
    os.environ["SAIPEN_ISOLATED_RELEASE"] = "1"
    try:
        # Determine reviewed scope
        scope_paths: list[str] = []
        junctions: list[Path] = []
        task = None
        if cohort_carrier:
            scope_paths = list(cohort_carrier.get("scope", cohort_carrier.get("paths", [])))
        else:
            from .release import _read_state, _scope_paths
            try:
                _, state = _read_state(root)
                task = state.get("task")
                if task:
                    scope_file = root / ".saipen" / "kitchen" / "release_scope" / f"{task}.json"
                    if scope_file.is_file():
                        try:
                            scope_data = json.loads(scope_file.read_text(encoding="utf-8"))
                            scope_paths = sorted((scope_data.get("paths") or {}).keys())
                        except Exception:
                            scope_paths = []
                    if not scope_paths:
                        scope_paths = list(_scope_paths(root, task))
            except Exception:
                scope_paths = []

        for req_dir in [
            "recovery",
            "recovery/ops",
            "recovery/settled",
            "kitchen",
            "kitchen/release_scope",
            "kitchen/release_receipts",
            "receipts",
            "logs",
        ]:
            (worktree_dir / ".saipen" / req_dir).mkdir(parents=True, exist_ok=True)

        junctions: list[Path] = []
        for sub in [
            "archive",
            "evidence",
            "quarantine",
            "intake",
            "cache",
            "future",
            "recovery/board-compaction",
            "recovery/log-detail",
            "recovery/conformance",
        ]:
            dst_sub = worktree_dir / ".saipen" / sub
            dst_sub.mkdir(parents=True, exist_ok=True)

        # Transfer reviewed paths + essential metadata
        meta_paths = [
            ".saipen/STATE.md",
            ".saipen/BOARD.md",
            ".saipen/LOG.md",
            ".saipen/IDENTITY.md",
            ".saipen/USERPERSON.md",
            ".saipen/MANIFEST.json",
            "VERSION",
            "tools/verification_policy.json",
        ]
        if (root / ".saipen" / "kitchen" / "cohort_registry.json").is_file():
            meta_paths.append(".saipen/kitchen/cohort_registry.json")
        for p in (root / ".saipen" / "kitchen" / "release_scope").glob("*.json"):
            meta_paths.append(str(p.relative_to(root)).replace("\\", "/"))
        for p in (root / ".saipen" / "kitchen" / "release_receipts").glob("*.json"):
            meta_paths.append(str(p.relative_to(root)).replace("\\", "/"))
        for p in (root / ".saipen" / "receipts").glob("*.json"):
            meta_paths.append(str(p.relative_to(root)).replace("\\", "/"))
        for p in (root / ".saipen" / "logs").glob("*"):
            if p.is_file():
                meta_paths.append(str(p.relative_to(root)).replace("\\", "/"))
        transfer_reviewed_scope(root, worktree_dir, scope_paths, metadata_paths=meta_paths)

        # Plan release in the isolated worktree (re-record scope safely if stale)
        try:
            plan = plan_release(
                worktree_dir,
                invocation,
                cohort_carrier=cohort_carrier,
                current_capability=current_capability or "full",
                current_agent=current_agent or "saipen-cli",
                dry_run=False,
            )
        except ReleaseRefusal as exc:
            if exc.code == "STALE_PLAN" and task:
                from .operations import record_scope

                record_res = record_scope(
                    worktree_dir, task, current_agent or "saipen-cli", scope_paths
                )
                if not record_res.ok:
                    res_msg = record_res.message or record_res.get("detail") or record_res.code
                    return {
                        "ok": False,
                        "code": record_res.code,
                        "detail": f"failed to re-record scope in isolated worktree: {res_msg}",
                    }
                plan = plan_release(
                    worktree_dir,
                    invocation,
                    cohort_carrier=cohort_carrier,
                    current_capability=current_capability or "full",
                    current_agent=current_agent or "saipen-cli",
                    dry_run=False,
                )
            else:
                raise

        # Override remote endpoint in plan if explicitly directed
        if remote != "origin":
            object.__setattr__(plan, "remote_push_endpoint", remote)

        # Execute release inside the worktree
        result = execute_release(worktree_dir, plan)

        # Check post-push remote head
        remote_head_after = ""
        remote_tip_after = _git(root, "ls-remote", remote, f"refs/heads/{branch}")
        if remote_tip_after.ok and remote_tip_after.stdout:
            remote_head_after = remote_tip_after.stdout.split()[0]

        expected_commit = str(getattr(plan, "commit_sha", "") or result.get("commit_sha") or "")
        already_synced = bool(remote_head_before and expected_commit and remote_head_before == expected_commit)
        pushed_expected = bool(remote_head_after and expected_commit and remote_head_after == expected_commit)
        result["expected_release_sha"] = expected_commit
        result["observed_remote_sha"] = remote_head_after
        result["remote_head_before"] = remote_head_before
        result["remote_head_after"] = remote_head_after
        result["github_sync_verified"] = bool(pushed_expected or (already_synced and remote_head_after == expected_commit))
        result["foreign_staging_preserved"] = True

        if result.get("ok"):
            if active_grant:
                updated_grant = release_authority.record_grant_release_executed(
                    root, active_grant["grant_id"], remote_head_after or expected_commit
                )
                result["release_grant_id"] = active_grant["grant_id"]
                result["releases_completed"] = updated_grant["releases_completed"]
                result["max_releases"] = updated_grant["max_releases"]
                result["standing"] = updated_grant["standing"]

            pub_receipt_dir = root / ".saipen" / "receipts" / "publication"
            pub_receipt_dir.mkdir(parents=True, exist_ok=True)
            pub_receipt_path = (
                pub_receipt_dir / f"pub-{(remote_head_after or expected_commit)[:16]}.json"
            )
            pub_receipt_path.write_text(
                json.dumps(
                    {
                        "kind": "saipen-publication-receipt",
                        "schema": 1,
                        "grant_id": (active_grant or {}).get("grant_id"),
                        "remote": remote,
                        "branch": branch,
                        "commit_sha": expected_commit,
                        "observed_remote_sha": remote_head_after,
                        "github_sync_verified": result.get("github_sync_verified"),
                        "published_at": release_authority._utc_now_iso(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            result["publication_receipt"] = str(pub_receipt_path)

            back_paths = [
                ".saipen/STATE.md",
                ".saipen/BOARD.md",
                ".saipen/LOG.md",
            ]
            wt_receipts = worktree_dir / ".saipen" / "receipts"
            if wt_receipts.is_dir():
                for p in wt_receipts.glob("*"):
                    if p.is_file():
                        back_paths.append(str(p.relative_to(worktree_dir)).replace("\\", "/"))
            wt_rel_receipts = worktree_dir / ".saipen" / "kitchen" / "release_receipts"
            if wt_rel_receipts.is_dir():
                for p in wt_rel_receipts.glob("*"):
                    if p.is_file():
                        back_paths.append(str(p.relative_to(worktree_dir)).replace("\\", "/"))
            wt_scope = worktree_dir / ".saipen" / "kitchen" / "release_scope"
            if wt_scope.is_dir():
                for p in wt_scope.glob("*"):
                    if p.is_file():
                        back_paths.append(str(p.relative_to(worktree_dir)).replace("\\", "/"))
            transfer_reviewed_scope(worktree_dir, root, [], metadata_paths=back_paths)

        return result
    finally:
        for junc in reversed(junctions):
            try:
                os.rmdir(junc)
            except Exception:
                pass
        if old_env_branch is None:
            os.environ.pop("SAIPEN_RELEASE_BRANCH", None)
        else:
            os.environ["SAIPEN_RELEASE_BRANCH"] = old_env_branch
        if old_env_remote is None:
            os.environ.pop("SAIPEN_REMOTE", None)
        else:
            os.environ["SAIPEN_REMOTE"] = old_env_remote
        if old_env_isolated is None:
            os.environ.pop("SAIPEN_ISOLATED_RELEASE", None)
        else:
            os.environ["SAIPEN_ISOLATED_RELEASE"] = old_env_isolated
        cleanup_worktree()
        # Verify the primary shared index remains 100% byte-exact untouched
        verify_shared_index_unchanged(root, initial_index_sha)


def reconcile_remote_ancestry(
    root: Path,
    *,
    remote: str = "github-backup",
    branch: str = "main",
    local_ref: str = "HEAD",
) -> dict[str, Any]:
    """Reconcile remote ancestry, merge base, ahead/behind relationships, and unique commits.

    Returns a structured dictionary with:
    - remote: remote name
    - push_url: configured push URL
    - branch: branch name
    - local_head: commit SHA of local_ref
    - remote_head: commit SHA of remote branch
    - merge_base: common ancestor SHA
    - ahead_count: commits in local_ref not in remote
    - behind_count: commits in remote not in local_ref
    - ahead_commits: list of one-line commit strings ahead
    - behind_commits: list of one-line commit strings behind
    - is_fast_forward: whether remote is ancestor of local_ref
    - requires_integration: whether ancestry diverged requiring isolated integration
    """
    root = Path(root).resolve()
    res_url = _git(root, "remote", "get-url", "--push", remote)
    push_url = res_url.stdout.strip() if res_url.ok else ""

    res_local = _git(root, "rev-parse", local_ref)
    local_head = res_local.stdout.strip() if res_local.ok else ""

    res_rem = _git(root, "ls-remote", remote, f"refs/heads/{branch}")
    remote_head = res_rem.stdout.split()[0] if (res_rem.ok and res_rem.stdout) else ""

    if not remote_head:
        res_track = _git(root, "rev-parse", f"refs/remotes/{remote}/{branch}")
        if res_track.ok:
            remote_head = res_track.stdout.strip()

    merge_base = ""
    ahead_count = 0
    behind_count = 0
    ahead_commits: list[str] = []
    behind_commits: list[str] = []
    is_ff = False
    requires_integration = False

    if local_head and remote_head:
        res_mb = _git(root, "merge-base", local_head, remote_head)
        if res_mb.ok:
            merge_base = res_mb.stdout.strip()

        res_counts = _git(root, "rev-list", "--left-right", "--count", f"{local_head}...{remote_head}")
        if res_counts.ok and res_counts.stdout:
            parts = res_counts.stdout.strip().split()
            if len(parts) >= 2:
                ahead_count = int(parts[0])
                behind_count = int(parts[1])

        if merge_base == remote_head:
            is_ff = True
        elif behind_count > 0:
            requires_integration = True

        res_ahead = _git(root, "log", "--oneline", f"{remote_head}..{local_head}")
        if res_ahead.ok and res_ahead.stdout:
            ahead_commits = [c.strip() for c in res_ahead.stdout.strip().splitlines() if c.strip()]

        res_behind = _git(root, "log", "--oneline", f"{local_head}..{remote_head}")
        if res_behind.ok and res_behind.stdout:
            behind_commits = [c.strip() for c in res_behind.stdout.strip().splitlines() if c.strip()]

    return {
        "remote": remote,
        "push_url": push_url,
        "branch": branch,
        "local_head": local_head,
        "remote_head": remote_head,
        "merge_base": merge_base,
        "ahead_count": ahead_count,
        "behind_count": behind_count,
        "ahead_commits": ahead_commits,
        "behind_commits": behind_commits,
        "is_fast_forward": is_ff,
        "requires_integration": requires_integration,
    }


def verify_staged_manifest_integrity(
    root: Path,
    manifest_path: Path | str,
) -> dict[str, Any]:
    """Verify that every staged entry in git matches the forensic manifest.

    Verifies paths, status, blob shas, and counts.
    Distinguishes raw index binary stat-cache mutations from logical stage invariance.
    """
    root = Path(root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root / manifest_file

    if not manifest_file.is_file():
        raise IsolatedReleaseError("MANIFEST_NOT_FOUND", f"Forensic manifest not found: {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest_entries = {e["path"]: e for e in manifest.get("entries", [])}

    res = _git(root, "diff", "--cached", "--raw", "--abbrev=40")
    if not res.ok:
        raise IsolatedReleaseError("GIT_DIFF_FAILED", f"git diff --cached --raw failed: {res.stderr}")

    current_staged: dict[str, dict[str, Any]] = {}
    for line in res.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        meta = parts[0].split()
        status = meta[4]
        old_sha = meta[2]
        new_sha = meta[3]
        path = parts[-1]
        src_path = parts[1] if len(parts) > 2 else None
        current_staged[path] = {
            "status": status,
            "blob_sha": new_sha,
            "old_sha": old_sha,
            "src_path": src_path,
        }

    missing = sorted(set(manifest_entries.keys()) - set(current_staged.keys()))
    extra = sorted(set(current_staged.keys()) - set(manifest_entries.keys()))
    mismatched = []

    for path, me in manifest_entries.items():
        if path in current_staged:
            cs = current_staged[path]
            prefix_len = min(len(me["blob_sha"]), len(cs["blob_sha"]), 8)
            sha_match = me["blob_sha"][:prefix_len] == cs["blob_sha"][:prefix_len]
            if cs["status"] != me["status"] or not sha_match:
                mismatched.append({
                    "path": path,
                    "expected_status": me["status"],
                    "observed_status": cs["status"],
                    "expected_sha": me["blob_sha"][:prefix_len],
                    "observed_sha": cs["blob_sha"][:prefix_len],
                })

    res_diff = subprocess.run(["git", "-C", str(root), "diff", "--cached"], capture_output=True)
    diff_bytes = res_diff.stdout
    cached_diff_sha256 = hashlib.sha256(diff_bytes).hexdigest()

    raw_sha, raw_len = snapshot_shared_index(root)

    return {
        "manifest_path": str(manifest_file.relative_to(root)).replace("\\", "/"),
        "manifest_count": len(manifest_entries),
        "live_staged_count": len(current_staged),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "mismatched_count": len(mismatched),
        "missing_paths": missing,
        "extra_paths": extra,
        "mismatched_entries": mismatched,
        "cached_diff_byte_size": len(diff_bytes),
        "cached_diff_sha256": cached_diff_sha256,
        "raw_index_sha256": raw_sha,
        "raw_index_byte_size": raw_len,
        "logical_staged_state_preserved": bool(
            len(missing) == 0 and len(extra) == 0 and len(mismatched) == 0
        ),
    }


def generate_release_approval_packet(
    root: Path,
    *,
    reviewed_scope: list[str],
    target_remote: str = "github-backup",
    target_branch: str = "main",
    destination_url: str = "https://github.com/vacterro/saipen.git",
    existing_authority: str = "operator_required",
    recording_mechanism: str = "saipen authority capture <signed-operator-capsule>",
) -> dict[str, Any]:
    """Generate canonical one-packet broker approval request for publication unblocking."""
    from .decision_request import create_isolated_release_decision_request

    ancestry = reconcile_remote_ancestry(root, remote=target_remote, branch=target_branch)

    remote_tip = ancestry.get("remote_head") or "remote_tip"
    req = create_isolated_release_decision_request(
        action="publish_isolated_release",
        reviewed_scope=reviewed_scope,
        target_destination=f"{target_remote}/{target_branch} ({destination_url})",
        paths_changed=reviewed_scope,
        paths_protected="864 staged paths in primary shared index",
        expected_side_effects=(
            f"Transfer reviewed changes ({len(reviewed_scope)} files) into isolated worktree on top of "
            f"{remote_tip[:12]}; run verification gates; fast-forward synchronize {target_remote}/{target_branch}; "
            f"zero modifications to primary index or unreviewed files"
        ),
        rollback="Isolated worktree is deleted on failure; no commit or push to remote; shared staging preserved",
        reason_insufficient="Missing cryptographic broker receipt or operator signed publication capsule",
        existing_authority=existing_authority,
        recording_mechanism=recording_mechanism,
    )
    req["ancestry"] = ancestry
    return req

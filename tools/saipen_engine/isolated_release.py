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


def snapshot_shared_index(root: Path) -> tuple[str, int]:
    """Capture (sha256, byte_count) of the primary repository index."""
    sha, b64_bytes = _exact_index_bytes(root)
    raw_len = len(b64_bytes) * 3 // 4
    return sha, raw_len


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
        src_file = source_root / rel_path
        dst_file = target_root / rel_path

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

    base_ref = reconcile_remote_head or remote_head_before or "HEAD"

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
            "detail": "isolated release preflight passed; zero files mutated",
        }

    if remote_head_before and base_ref != remote_head_before and base_ref != "HEAD":
        anc_check = _git(root, "merge-base", "--is-ancestor", remote_head_before, base_ref)
        if not anc_check.ok:
            return {
                "ok": False,
                "code": "NON_FAST_FORWARD",
                "detail": f"remote {remote} tip {remote_head_before[:12]} is not an ancestor of base {base_ref[:12]} -- refusing non-fast-forward push",
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

        junctions = []
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
            src_sub = root / ".saipen" / sub
            dst_sub = worktree_dir / ".saipen" / sub
            if src_sub.is_dir() and not dst_sub.exists():
                dst_sub.parent.mkdir(parents=True, exist_ok=True)
                cmd = f'cmd /c mklink /J "{dst_sub}" "{src_sub}" >nul'
                os.system(cmd)
                if dst_sub.exists():
                    junctions.append(dst_sub)

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

        result["remote_head_before"] = remote_head_before
        result["remote_head_after"] = remote_head_after
        result["github_sync_verified"] = bool(remote_head_after and remote_head_after != remote_head_before)
        result["foreign_staging_preserved"] = True

        if result.get("ok"):
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

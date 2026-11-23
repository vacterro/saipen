"""Red-before-green measurement for audit/27.md wave 2 (W2-001..W2-006).

For each finding this rebuilds a scratch engine from the current tree, reverts
exactly that one repair to the pre-fix shape quoted in the audit, and runs the
matching regression class against it. A repair is only proven when the same
test is GREEN on the current tree and RED on the reverted copy, so the
measurement never depends on a hand-written "before" claim.

Read-only against the repository: every mutation happens inside a throwaway
copy under V:/_TEMP_/.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRATCH = Path("V:/_TEMP_/t1944-w2-revert")
SOURCE_ENGINE = REPO / "tools" / "saipen_engine"


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path.name}:\n{old[:200]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _fresh_copy() -> Path:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    (SCRATCH / "tools").mkdir(parents=True)
    shutil.copytree(SOURCE_ENGINE, SCRATCH / "tools" / "saipen_engine")
    shutil.copy(REPO / "tools" / "test_t1944_wave2.py", SCRATCH / "tools")
    (SCRATCH / "saipen").mkdir()
    (SCRATCH / "saipen" / "BOOT.md").write_text("# scratch\n", encoding="utf-8")
    shutil.copy(REPO / "saipen" / "REGISTRY.json", SCRATCH / "saipen")
    for cache in SCRATCH.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    return SCRATCH


def _run(expr: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tools/test_t1944_wave2.py", "-q", "-k", expr],
        cwd=SCRATCH,
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else (proc.stderr or "").strip().splitlines()[-1:]
    return proc.returncode == 0, str(summary)


def revert_w2_001() -> None:
    """Pre-fix: the read/rebuild happens unlocked; only the write is locked."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    _replace(
        adapter,
        """        writer = lock.FileWriterLock(
            root / ".saipen" / "locks" / "saipal-history.lock", root, blocking=False
        )
        deadline = time.monotonic() + _history_lock_timeout()
        while True:
            try:
                writer.acquire()
                break
            except lock.FileLockBusy:
                if time.monotonic() >= deadline:
                    return {
                        "ok": False,
                        "status": "RECONCILE_BUSY",
                        "kind": kind,
                        "error": (
                            "another writer holds the history lock; reconciliation "
                            "refused rather than replacing a moving log"
                        ),
                    }
                time.sleep(_HISTORY_LOCK_RETRY_SLEEP)
        try:
            return self._reconcile_history_locked(root, kind=kind)
        finally:
            with suppress(Exception):
                writer.release()""",
        "        return self._reconcile_history_locked(root, kind=kind)",
    )
    _replace(
        adapter,
        """                try:
                    paths.prove_owned_dir_chain(
                        path.parent, ownership_root=root, kind="SAIPAL history"
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    paths.safe_atomic_write_bytes(
                        path,
                        payload,
                        kind="SAIPAL reconstructed history",
                        ownership_root=root,
                    )
                except (OSError, ValueError) as exc:""",
        """                try:
                    with _history_write_lock(root):
                        paths.prove_owned_dir_chain(
                            path.parent, ownership_root=root, kind="SAIPAL history"
                        )
                        path.parent.mkdir(parents=True, exist_ok=True)
                        paths.safe_atomic_write_bytes(
                            path,
                            payload,
                            kind="SAIPAL reconstructed history",
                            ownership_root=root,
                        )
                except (OSError, ValueError) as exc:""",
    )


def revert_w2_002() -> None:
    """Pre-fix: every yielded finding is recorded as delivered immediately."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    _replace(
        adapter,
        """            # The cursor tracks the WALK position, never the delivery of these
            # findings: re-yielding them is harmless because publication is
            # idempotent by operation_id, while skipping one is unrecoverable.""",
        """            for row in fresh:
                acknowledged.add(str(row.get("finding_id") or ""))
            # Pre-fix shape: yielding is treated as delivery.""",
    )


def revert_w2_003() -> None:
    """Pre-fix: the uniqueness lookup is outside the writer lock."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    _replace(
        adapter,
        """        with _history_write_lock(root):
            paths.prove_owned_dir_chain(path.parent, ownership_root=root, kind="SAIPAL history")
            path.parent.mkdir(parents=True, exist_ok=True)
            with suppress(FileNotFoundError):
                paths.prove_owned_regular(path, kind="SAIPAL history")
            history = _read_append_log(path)
            if not history["ok"] and history["status"] != "LOG_ABSENT":
                return history
            for row in history.get("records") or []:""",
        """        if True:
            history = _read_append_log(path)
            for row in history.get("records") or []:""",
    )
    _replace(
        adapter,
        """            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
            flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "ab") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            return {"ok": True, "status": "HISTORY_RECORDED", "path": str(path), "record": record}""",
        """            with _history_write_lock(root):
                paths.prove_owned_dir_chain(
                    path.parent, ownership_root=root, kind="SAIPAL history"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                with suppress(FileNotFoundError):
                    paths.prove_owned_regular(path, kind="SAIPAL history")
                flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
                flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(path, flags, 0o600)
                with os.fdopen(descriptor, "ab") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
            return {"ok": True, "status": "HISTORY_RECORDED", "path": str(path), "record": record}""",
    )


def revert_w2_004() -> None:
    """Pre-fix: any non-empty discovery batch reports delivered."""
    campaign = SCRATCH / "tools" / "saipen_engine" / "campaign.py"
    _replace(
        campaign,
        """                    if not delivered:
                        delivery_status = "NOTHING_TO_DELIVER"
                    elif len(published) == len(delivered):""",
        """                    if delivered:
                        delivery_status = "ALL_DELIVERED"
                    elif not delivered:
                        delivery_status = "NOTHING_TO_DELIVER"
                    elif len(published) == len(delivered):""",
    )


def revert_w2_005() -> None:
    """Pre-fix: a corrupt cursor is replaced and a failed write is swallowed."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    _replace(
        adapter,
        """        if not checkpoint.get("ok"):
            yield {
                "ok": False,
                "status": checkpoint.get("status") or "CURSOR_UNREADABLE",
                "error": checkpoint.get("error")
                or "the report cursor cannot be read; refusing to walk over it",
                "path": checkpoint.get("path"),
                "page_index": None,
            }
            return""",
        """        if not checkpoint.get("ok"):
            checkpoint = {"ok": True, "status": "CURSOR_ABSENT", "cursor": {}}""",
    )
    _replace(
        adapter,
        """            saved = self.save_page_checkpoint(
                root,
                {
                    "source_digest": identity["source_digest"],
                    "delivered_finding_ids": sorted(acknowledged),
                    "page_index": index,
                    "total_pages": total,
                    "updated_at": _utc_now(),
                },
            )
            if not saved.get("ok"):
                yield {
                    "ok": False,
                    "status": saved.get("status") or "CURSOR_WRITE_FAILED",
                    "error": saved.get("error"),
                    "page_index": index,
                    "page_size": size,
                    "findings": fresh,
                    "persisted": False,
                }
                return""",
        """            self.save_page_checkpoint(
                root,
                {
                    "source_digest": identity["source_digest"],
                    "delivered_finding_ids": sorted(acknowledged),
                    "page_index": index,
                    "total_pages": total,
                    "updated_at": _utc_now(),
                },
            )""",
    )


def revert_w2_006() -> None:
    """Pre-fix: corpus identity hashes finding ids only."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    old_start = '        corpus = hashlib.sha256(\n            json.dumps('
    text = adapter.read_text(encoding="utf-8")
    start = text.index(old_start)
    end_marker = '        digest = hashlib.sha256(\n            json.dumps(envelope'
    end = text.index(end_marker, start)
    old_block = text[start:end]
    new_block = (
        '        corpus = hashlib.sha256(\n'
        '            "\\n".join(str(row.get("finding_id") or "") for row in findings).encode(\n'
        '                "utf-8"\n'
        '            )\n'
        '        ).hexdigest()\n'
    )
    adapter.write_text(text.replace(old_block, new_block, 1), encoding="utf-8")


CASES = [
    ("W2-001", "the_whole_rebuild_holds_the_history_lock", revert_w2_001),
    ("W2-002", "a_yielded_but_unpublished_finding_stays_eligible", revert_w2_002),
    ("W2-003", "two_concurrent_lookups_cannot_both_see_absent", revert_w2_003),
    ("W2-004", "every_failed_delivery_never_reports_delivered", revert_w2_004),
    ("W2-005", "corrupt_cursor_is_refused_and_preserved", revert_w2_005),
    ("W2-006", "changing_audit_body_changes_identity", revert_w2_006),
]


def main() -> int:
    failures = 0
    print(f"repository: {REPO}")
    print()
    for finding, expr, revert in CASES:
        _fresh_copy()
        green_ok, green_summary = _run(expr)
        revert()
        red_ok, red_summary = _run(expr)
        verdict = "PROVEN" if (green_ok and not red_ok) else "NOT PROVEN"
        if verdict != "PROVEN":
            failures += 1
        print(f"{finding}  current={green_summary}  reverted={red_summary}  {verdict}")
    print()
    print(f"{len(CASES) - failures}/{len(CASES)} red-before-green pairs measured")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

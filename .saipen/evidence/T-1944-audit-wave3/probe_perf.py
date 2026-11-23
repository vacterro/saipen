"""Red-before-green measurement for audit/27.md wave 3 (PERF-001..PERF-005).

For each finding this rebuilds a scratch engine from the current tree, reverts
exactly that one optimization to the pre-fix shape quoted in the audit, and runs
the matching measurement test against it. A repair is only proven when the same
test is GREEN on the current tree and RED on the reverted copy.

PERF findings are measured, not asserted on code shape, so a revert has to
restore the BEHAVIOUR the audit measured -- whole-file rewrites, full-log
parses, materialised report lists, per-page id-set serialisation.

Read-only against the repository: every mutation happens inside a throwaway
copy under V:/_TEMP_/.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRATCH = Path("V:/_TEMP_/t1944-perf-revert")
SOURCE_ENGINE = REPO / "tools" / "saipen_engine"


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path.name}:\n{old[:300]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _fresh_copy() -> Path:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    (SCRATCH / "tools").mkdir(parents=True)
    shutil.copytree(SOURCE_ENGINE, SCRATCH / "tools" / "saipen_engine")
    shutil.copy(REPO / "tools" / "test_t1944_perf_wave.py", SCRATCH / "tools")
    (SCRATCH / "saipen").mkdir()
    (SCRATCH / "saipen" / "BOOT.md").write_text("# scratch\n", encoding="utf-8")
    shutil.copy(REPO / "saipen" / "REGISTRY.json", SCRATCH / "saipen")
    for cache in SCRATCH.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    return SCRATCH


def _run(expr: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tools/test_t1944_perf_wave.py", "-q", "-k", expr],
        cwd=SCRATCH,
        capture_output=True,
        text=True,
    )
    lines = (proc.stdout or "").strip().splitlines()
    summary = lines[-1] if lines else str((proc.stderr or "").strip().splitlines()[-1:])
    return proc.returncode == 0, summary


def revert_perf_001() -> None:
    """Pre-fix: every transition rewrites the whole allocator checkpoint TWICE."""
    enqueue_mod = SCRATCH / "tools" / "saipen_engine" / "audit_enqueue.py"
    _replace(
        enqueue_mod,
        '''    payload: dict = {"next_id": folded.get("next_id", 1)}
    if op is not None:
        payload["operation"] = op
    if drop:
        payload["kind"] = "drop"
    _append_journal_entry(root, payload, base_chain=folded.get("journal_chain") or "")
    _compact_if_due(root, folded)''',
        '''    payload: dict = {"next_id": folded.get("next_id", 1)}
    if op is not None:
        payload["operation"] = op
    if drop:
        payload["kind"] = "drop"
    # Pre-fix shape: the whole document is written on every transition.
    _atomic_write(allocator_path(root), _checkpoint_bytes(folded), ownership_root=Path(root))''',
    )


def revert_perf_002() -> None:
    """Pre-fix: the append path parses the whole receipt log under the lock."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    text = adapter.read_text(encoding="utf-8")
    start = text.index("def _history_snapshot_for_append(")
    end = text.index("def _history_after_append(")
    pre_fix = '''def _history_snapshot_for_append(root: Path, path: Path, filename: str) -> dict:
    """Pre-fix shape: always parse the entire log."""
    history = _read_append_log(path)
    return {"mode": "PARSED", "rows": None, "history": history, "log_absent": False}


'''
    adapter.write_text(text[:start] + pre_fix + text[end:], encoding="utf-8")


def revert_perf_003() -> None:
    """Pre-fix: each receipt re-reads the allocator instead of using a snapshot."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    _replace(
        adapter,
        """    if snapshot is not None:
        doc, allocator_state = snapshot, audit_enqueue.ALLOCATOR_OK
    else:
        doc, allocator_state = audit_enqueue.read_allocator_state(root)""",
        """    doc, allocator_state = audit_enqueue.read_allocator_state(root)""",
    )


def revert_perf_004() -> None:
    """Pre-fix: materialise the whole findings list, then slice it per page."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    _replace(
        adapter,
        """        report = opened["report"]
        total = report.total_findings
        total_pages = max(1, (total + page_size - 1) // page_size)
        identity = report.identity""",
        """        report = opened["report"]
        data = report.read_all()
        findings = data.get("findings") or []
        total = len(findings)
        total_pages = max(1, (total + page_size - 1) // page_size)
        identity = report.identity""",
    )
    _replace(
        adapter,
        """            index = 0
            try:
                for page in report.iter_pages(page_size):
                    yield index, total_pages, page, identity
                    index += 1""",
        """            index = 0
            try:
                for index in range(total_pages):
                    start = index * page_size
                    yield index, total_pages, findings[start : start + page_size], identity""",
    )


def revert_perf_005() -> None:
    """Pre-fix: the cursor carries and re-serialises every acknowledged id."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    text = adapter.read_text(encoding="utf-8")
    anchor = '''            saved = self.save_page_checkpoint(
                root,
                {
                    "source_digest": identity["source_digest"],
                    "page_index": index,
                    "total_pages": total,
                    "updated_at": _utc_now(),
                },
            )'''
    pre_fix = '''            acknowledged |= {
                str(row.get("finding_id") or "") for row in fresh
            }
            saved = self.save_page_checkpoint(
                root,
                {
                    "source_digest": identity["source_digest"],
                    "delivered_finding_ids": sorted(acknowledged),
                    "page_index": index,
                    "total_pages": total,
                    "updated_at": _utc_now(),
                },
            )'''
    if anchor not in text:
        raise SystemExit("PERF-005 anchor not found")
    adapter.write_text(text.replace(anchor, pre_fix, 1), encoding="utf-8")


CASES = [
    (
        "PERF-001",
        "test_write_volume_is_not_quadratic_in_operation_count",
        revert_perf_001,
    ),
    (
        "PERF-002",
        "test_reparse_work_follows_new_work_not_history_size",
        revert_perf_002,
    ),
    (
        "PERF-003",
        "test_one_allocator_read_per_reconciliation_pass",
        revert_perf_003,
    ),
    (
        "PERF-004",
        "test_page_size_is_the_resident_bound",
        revert_perf_004,
    ),
    (
        "PERF-005",
        "test_cumulative_checkpoint_bytes_are_not_quadratic",
        revert_perf_005,
    ),
]


def main() -> int:
    results: list[tuple[str, bool, str, bool, str]] = []
    for name, test, revert in CASES:
        _fresh_copy()
        green_ok, green_summary = _run(test)
        revert()
        for cache in SCRATCH.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
        red_ok, red_summary = _run(test)
        results.append((name, green_ok, green_summary, red_ok, red_summary))
        verdict = "PROVEN" if (green_ok and not red_ok) else "NOT PROVEN"
        print(f"{name} [{test}]")
        print(f"  current  = {'PASS' if green_ok else 'FAIL'}  ({green_summary})")
        print(f"  reverted = {'PASS' if red_ok else 'FAIL'}  ({red_summary})")
        print(f"  -> {verdict}")
    proven = sum(1 for _n, g, _gs, r, _rs in results if g and not r)
    print()
    print(f"{proven}/{len(results)} red-before-green pairs measured")
    return 0 if proven == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

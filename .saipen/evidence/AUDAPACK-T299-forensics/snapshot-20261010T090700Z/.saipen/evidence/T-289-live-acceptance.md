# T-289 Live Acceptance & Correctness Closure

**Date**: 2026-10-07  
**Ticket**: T-289 [P1]  
**Component**: Metrics Strip, Freshness Authority, Tooltip Settings, Windows Soak & Subprocess Hygiene  
**Status**: VERIFIED & CLOSED  

---

## 1. Batch Metric Integration Evidence (DEFECT 1)

- **Problem**: `MainWindow._refresh_metrics()` incorrectly referenced non-existent `self._batch_runner.is_busy()`. As a result, active parallel pack batches were ignored and the PACK metric remained stuck on IDLE during `PACK ALL` or group batch runs.
- **Fix**: Re-anchored to the canonical `self._pack_batch_runner = PackBatchRunner(parent=self)` using `self._pack_batch_runner.busy()`.
- **Verified Behaviour**:
  - Initial / idle state: PACK cell reports `IDLE` (neutral).
  - Batch start (`_pack_batch_runner.start_batch`): PACK cell immediately transitions to `BATCH` (active).
  - Terminal batch callback (`_on_batch_finished`): triggers `_refresh_metrics()` and returns PACK cell to `IDLE` (neutral).
- **Test Evidence**:
  - `tests/test_metrics_strip.py::test_main_window_pack_batch_metric_integration` PASS (real Qt widget + runner lifecycle, no artificial mock flags).

---

## 2. Nested-File Freshness Authority Evidence (DEFECT 2)

- **Problem**: `evaluate_project_metrics()` previously fell back to `src_path.stat().st_mtime > archive.stat().st_mtime`. When editing contents of an already-existing nested file (e.g. `src/pkg/nested/module.py`), the root directory mtime does not change on Windows or POSIX filesystems, causing the metrics strip to report a false-green `FRESH` and `READY`.
- **Fix**:
  - Completely removed root directory mtime check from `metrics_strip.py`.
  - Wired `evaluate_project_metrics()` to accept `canonical_freshness`.
  - Added non-blocking cached freshness read `ProjectRoomModel.get_cached_archive_freshness()` and `get_archive_freshness()`.
  - `MainWindow._refresh_metrics()` queries the model cache and schedules async probe via `TaskRunner.submit_coalesced("freshness:<pid>")` when unverified.
  - Leverages in-memory `hot_freshness.lookup()` so unchanged projects remain instantaneous without source tree traversals on the GUI thread.
  - If freshness is unverified (`None` or `UNKNOWN`), metrics strip renders `UNKNOWN` (warning) and readiness `PARTIAL`, never false-green `FRESH` or `READY`.
- **Red-Before / Green-After Proof**:
  - Root directory mtime older than archive mtime: `src.stat().st_mtime < archive.stat().st_mtime` confirmed.
  - Pre-fix fallback: would evaluate to `FRESH` / `READY` (false green).
  - Post-fix: canonical `probe_archive_freshness()` identifies `ArchiveFreshness.STALE` from nested file mtime.
  - Metrics strip with canonical STALE -> `FRESH STALE (warning)`, `READY PARTIAL (warning)`.
  - Metrics strip unverified / missing proof -> `FRESH UNKNOWN (warning)`, `READY PARTIAL (warning)`.
  - Canonical tri-state mapping verified:
    - Canonical FRESH => metrics `FRESH` (healthy), `READY` (healthy).
    - Canonical STALE => metrics `STALE` (warning), `PARTIAL` (warning).
    - Canonical UNKNOWN => metrics `UNKNOWN` (warning), `PARTIAL` (warning, never false-green).
- **Test Evidence**:
  - `tests/test_metrics_strip.py::test_nested_file_modification_not_false_green` PASS.

---

## 3. Tooltip Settings Compliance Evidence (DEFECT 3)

- **Problem**: Metric cells unconditionally called `self.setToolTip(item.tooltip)`, bypassing global UI configuration `show_tooltips` and `tooltip_duration_ms`, and rendered unbounded multi-line policy mismatch text.
- **Fix**:
  - Implemented `MetricCellWidget.set_tooltip_policy(show_tooltips, duration_ms)` and `MetricsStripWidget.set_tooltip_policy()`.
  - Applied `QWidget.setToolTipDuration()` for configured duration.
  - Added strict single-line normalization and length clamp (<= 80 characters, no `\n`).
  - When `show_tooltips=False`, metric cells expose empty tooltip `""`.
  - Replaced oversized `{mismatch}` strings in `evaluate_project_metrics()` with concise messages.
- **Test Evidence**:
  - `tests/test_metrics_strip.py::test_metric_cell_tooltips_settings_and_concise` PASS.

---

## 4. Windows Idle & Soak Acceptance Evidence (DEFECT 4)

- **Problem**: `tests/soak_leak_audit.py` previously reported GDI objects = 0 and USER objects = 0 on Windows due to unconfigured ctypes argument/return types (`GetCurrentProcess` 64-bit HANDLE truncated to 32-bit int, yielding Win32 error 87 `ERROR_INVALID_PARAMETER`), and lacked a multi-round leak verdict.
- **Fix**:
  - Explicitly defined 64-bit Windows ctypes prototypes for `kernel32.GetCurrentProcess` (`restype=wintypes.HANDLE`) and `user32.GetGuiResources` (`restype=wintypes.DWORD`, `argtypes=[HANDLE, DWORD]`).
  - Never report 0 on error; report real object counts or explicit error details.
  - Upgraded soak audit to execute 3 distinct operational rounds:
    - 10x project switches per round
    - 3x single pack operations per round
    - 1x PACK ALL batch operation per round
    - Settle & stabilization intervals
  - Implemented monotonic growth leak detection across rounds for private bytes, handles, GDI objects, and USER objects.
  - Verified zero orphan child processes (`proc.children(recursive=True) == []`).
  - Verified all recurring timers and watchers are stopped on window close.
- **Measured Live Soak Results**:
  - `baseline`: RSS=175.39 MB, Private=95.95 MB, Threads=14, Handles=1992, GDI=26, USER=40
  - `post_idle`: RSS=175.80 MB, Private=96.56 MB, Threads=14, Handles=1992, GDI=26, USER=40
  - `round 1`: RSS=175.91 MB, Private=96.61 MB, Threads=15, Handles=2000, GDI=26, USER=40
  - `round 2`: RSS=176.08 MB, Private=96.61 MB, Threads=15, Handles=2000, GDI=26, USER=40
  - `round 3`: RSS=176.16 MB, Private=96.61 MB, Threads=15, Handles=2000, GDI=26, USER=40
  - `final_stabilized`: RSS=176.16 MB, Private=96.61 MB, Threads=15, Handles=2000, GDI=26, USER=40
  - `deltas`: Private=+0.66 MB (stable across rounds 1-3), Threads=+1, Handles=+8 (flat across rounds 1-3), GDI delta=0, USER delta=0.
  - `orphan_processes`: `[]` (clean).
  - `verdict`: **PASS** across all 9 checklist items.
- **Report Location**: `tests/soak_audit_report.json`.
- **Test Evidence**:
  - `tests/test_idle_resource_hygiene.py::test_soak_leak_audit_acceptance` PASS.

---

## 5. Black Console Window Subprocess Acceptance

- **Verification**:
  - `audapack/procutil.py` provides `hidden_spawn_kwargs()`, `run_hidden()`, and `popen_hidden()`.
  - Packing Git operations in `audapack/source_inventory.py` and runtime identity checks in `audapack/runtime_identity.py` use `run_hidden`.
  - All 19 tests in `tests/test_hidden_subprocess.py` pass (18 passed, 1 skipped platform guard).
  - Confirmed no console flashes during Git inventory and revision queries.

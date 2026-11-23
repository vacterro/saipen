# HUNT-001: 6-signal defect sweep on Smart VAC Cleaner

**Producer:** `saihunt`  
**Target:** `_SMART_VAC_CLEANER.py`, `test_cleaner.py`, repository root  
**Scope:** Six canonical HUNT signals (phases/hunt.md)  
**Timestamp:** 2026-10-12T08:01:00Z  

---

### Finding 1 (Signal 1: Failing tests) — WINDIR environment poisoning vulnerability
- **Location:** `_SMART_VAC_CLEANER.py:3946`, tested by `test_cleaner.py:4361`
- **Evidence:** Running `test_cleaner.TestEnvRootProvenance.test_windir_is_os_authoritative_not_env` produces:
  ```
  AssertionError: 'PoisonWindows' unexpectedly found in 'WINDIR=C:\PoisonWindows\n'
  ```
- **Cause:** `resolve_system_roots()` queries `os.environ.get("windir")` directly, allowing an unprivileged or hostile environment variable to redirect root resolution to a fake folder.
- **Verdict:** `REPRODUCED`

---

### Finding 2 (Signal 2: Commits unverified in LOG / Worktree drift)
- **Location:** Project root worktree
- **Evidence:** `git status --short` shows 5 tracked files modified beyond commit `c826eb7`:
  `_SMART_VAC_CLEANER.py`, `_fs_helpers.py`, `build_exe.ps1`, `test_cleaner.py`, `test_package_install.py`.
- **Verdict:** `REPRODUCED`

---

### Finding 3 (Signal 3: Stale TODO/FIXME/HACK)
- **Location:** All tracked files
- **Evidence:** Grep for `TODO|FIXME|HACK` returns zero hits.
- **Verdict:** `NOT_REPRODUCED` (Signal clean)

---

### Finding 4 (Signal 4: Silent failures / swallowed exceptions)
- **Location:** `_SMART_VAC_CLEANER.py:602`, `608`, `4219`, `4242`, `4723`
- **Evidence:** Multiple bare `except Exception: pass` blocks swallow failures without logging:
  - `_SMART_VAC_CLEANER.py:602` and `:608`: Mutex release and handle close failures swallowed.
  - `_SMART_VAC_CLEANER.py:4219`: Tray close exception swallowed.
  - `_SMART_VAC_CLEANER.py:4242`: Window geometry persistence error swallowed.
  - `_SMART_VAC_CLEANER.py:4723`: Console hiding ctypes error swallowed.
- **Verdict:** `REPRODUCED`

---

### Finding 5 (Signal 5: Symmetry gaps) — Install task without uninstall task
- **Location:** `_SMART_VAC_CLEANER.py:4887`
- **Evidence:** CLI supports `--install-task` and GUI provides "Install Auto-Clean Task", but neither CLI nor GUI provides an `--uninstall-task` or task removal option.
- **Verdict:** `REPRODUCED`

---

### Finding 6 (Signal 6: Dead code / Orphan files)
- **Location:** Project root
- **Evidence:** `_SMART_VAC_CLEANER.py.bak` and `_SMART_VAC_CLEANER.py.bak.provenance.json` exist as untracked leftover artifacts in the root directory.
- **Verdict:** `REPRODUCED`

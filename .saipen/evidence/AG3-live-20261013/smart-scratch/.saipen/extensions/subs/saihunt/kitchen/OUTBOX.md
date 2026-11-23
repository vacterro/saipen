# OUTBOX

## HUNT-001: six-signal defect sweep on Smart VAC Cleaner
- **status:** reviewed
- **reviewed_by:** Core (T-199, event E-208)
- **summary:** Six-signal sensor pass reproduced 5 defects: (1) test failure: WINDIR env poisoning in resolve_system_roots(); (2) uncommitted worktree drift (5 modified files); (3) signal clean (no stale TODO/FIXME/HACK); (4) silent failures: 5 instances of swallowed except Exception: pass; (5) symmetry gap: --install-task exists with zero uninstall route; (6) orphan files: .bak artifacts in root.
- **main_project_refs:** [_SMART_VAC_CLEANER.py, test_cleaner.py, _fs_helpers.py, build_exe.ps1]
- **critical:** true
- **severity:** P1
- **producer:** saihunt
- **coverage:** six signals per phases/hunt.md: failing tests, unverified commits, stale TODO, silent failures, symmetry gaps, dead code/orphans
- **payload:** []
- **verified:** PASS -- each finding backed by file:line evidence and exact verdict (5 REPRODUCED, 1 NOT_REPRODUCED); details in kitchen/HUNT-001.md
- **instructions:** Core review kitchen/HUNT-001.md; implement authoritative GetWindowsDirectoryW in resolve_system_roots() to close test failure; route fixes via Core or saipython.
- **details:** Findings and individual verdicts are in kitchen/HUNT-001.md. Main source untouched; saihunt is read-only.

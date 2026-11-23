# T-2052 — convergence stage projection (HOVERSTRATA T-7)

Measurement date: 2026-11-13.  Owner fix: commit `00f290d90`.

## Defect

`tools/saipen_engine/convergence.py`, `ConvergenceVerdict.as_dict`, projected
`item.get("stage", "")`.  A committed convergence receipt carries its stage at
`receipt_metadata.stage` — the same field the verdict's own stage readers use
(`convergence.py:182`, `convergence.py:622`).  Every E/F/G/H/I row therefore
projected `""`.

`automation._latest_i_created_at` selects the row whose `stage == "I"`, so it
returned `None` and `closure_gate` computed C3/C4 false for a chain
`convergence_verdict` had already proved current (`ok: true`).

## Fix and oracle

One line: project `(item.get("receipt_metadata") or {}).get("stage", "")`.
A record without a metadata stage still projects `""` and still reaches the
gate as no final I — nothing is invented.

Oracle: `tools/test_t2052_stage_projection.py` (5 tests).

- Pre-fix subject, same oracle: `FAILED (failures=3)`, `'' != 'I'`.
- Post-fix: focused family record
  `.saipen/evidence/focused-unit/bf485ffe57ca5ac4-20261113T124058909854Z.json`,
  ran 43, PASS, includes `test_automation_block`.
- External oracle from HOVERSTRATA
  (`.saipen/evidence/runtime-closure/test_projection.py`) green against the
  owner module.

## Real-chain evidence (HOVERSTRATA, unmodified receipts)

`verdict-installed.json` / `verdict-owner.json` / `gate-input-*.json` were
produced by calling `convergence_verdict(project_root).as_dict()` from each
engine generation against the same project bytes.

| engine | verdict | stage labels | latest I |
|---|---|---|---|
| installed `scheduled-source` | ok true | `["","","","",""]` | `None` |
| owner `_SAIPEN` (fixed) | ok true | `["E","F","G","H","I"]` | `2026-11-13T11:45:14Z` |

`installed-status.json` is HOVERSTRATA's native read-only status under the
installed engine: `automation.convergence_current: false`,
`closure_complete: false`, `completed_at: null`.

## Deployment status: BLOCKED (not published)

`00f290d90` is committed in the canonical clone.  It is not installed:

- `%LOCALAPPDATA%/saipen/scheduled-source/tools/saipen_engine/convergence.py`
  still hashes `a9e84f23…` (pre-fix); owner copy hashes the fixed bytes.
- The owner publication task refuses every run:
  `%LOCALAPPDATA%/saipen/inject.log` 2026-11-13 14:46 → 35 dirty injected-surface
  paths → `SKIP: DIRTY_SOURCE` (rc=2).
- Those 35 paths belong to other parked Work, not to T-2052: 16 modified
  tracked files (`tools/saipen.py`, `tools/saipen_engine/{router,operations,
  journal,intake,conformance,board_scrub,remediation}.py`, `tools/freshness.py`,
  `saipen/REGISTRY.json`, `saipen/COMMANDS_REFERENCE.md`, four test files) and
  19 untracked ones (`tools/saipen_engine/gc.py`, `tools/saipen_engine/
  source_reindex.py`, 13 `test_t2040_*`, `test_t2050_*`, `test_t2051_*`,
  `test_nested_git_boundaries.py`).
- Publishing from this working tree through `bootstrap/inject.ps1` would copy
  those uncommitted edits into every installed home; publishing a hand-made
  `git archive HEAD` snapshot is the ad-hoc injector re-run RUNTIME.md forbids.
  Neither is done.

HOVERSTRATA is bound to `saipen_home:
C:/Users/vac34/AppData/Local/saipen/scheduled-source`, so T-7 cannot close from
the installed generation until the surface is clean enough for the owner's own
publication run.

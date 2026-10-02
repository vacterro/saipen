# T-1411 installed acceptance and closure evidence — 2026-09-19

Stale-COMPLETE Improve seat liveness: an ACTIVE cycle with an immutable stale
COMPLETE report and existing SWEEP dispositions had no legal finite exit. This
ticket adds one byte-preserving supersession route and proves it end to end.
No push, no tag, no public release.

## 1. Commit

- `cc86601f` on `main`: `tools/improve.py`, `tools/saipen.py`,
  `tools/validate.py`, `tools/test_t1411_stale_complete_resolution.py`,
  `saipen/IMPROVE.md`; 5 files, 1529 insertions, 47 deletions.
- Release scope recorded via `saipen scope T-1411` (E-7387).

## 2. Anchored regression pair

- verifier `tools/test_t1411_stale_complete_resolution.py` sha256
  `487D2C91AC5F97F18C93CEDB5313E28C66F93636EB2C7DEE4E4E146BA0EACBAF`
- pre-fix subject (HEAD a1e9c09f bytes in a pristine worktree) composite
  sha256 `4b51dabe5e569f49f8e494fb3d3d872a219a319fb479127d0301b07edcd884c0`:
  RED — 16 tests, failures=1 skipped=15; test_00 `STALE_COMPLETE_DEAD_END`
  (cycle-complete, abort, retire and append all refuse with no resolution
  owner). Event E-7382.
- post-fix subject composite sha256
  `ec2f4fd5ed32a2d1266c7bcf7ddb86c4af5c62b46d99321d060f507fdcea34d0`:
  GREEN — 16 tests OK. Event E-7383.

## 3. Semantics proven by the oracle

- Unswept stale COMPLETE report + fresh same-scope replacement that REPRODUCES:
  canonical CLI sequence `improve sweep` (replacement `CONFIRMED` with ticket →
  current authority; old finding `SUPERSEDED` with `--verification` successor
  binding) → `improve retire --reason STALE_COMPLETE --replacement` →
  `SEAT_SUPERSEDED` → verify/cycle-complete/clean PASS; old report, replacement
  report and SWEEP bytes unchanged.
- Unswept finding that no longer reproduces → `NOT_REPRODUCED --reproduced n`
  with the successor binding → same finite exit.
- Partial sweep: existing disposition bytes preserved; only the unswept finding
  appended; two new ledger lines total (replacement CONFIRMED + old SUPERSEDED).
- Stale `CONFIRMED` remains refused on the stale report; the replacement's own
  `CONFIRMED` carries ticket authority.
- Supersession chain old → seat-new → seat-current validates; later identity
  movement reopens only the current terminal seat; `ALREADY_APPLIED` never
  implies cycle freshness.
- Tampered preserved report and dangling replacement are rejected by
  `improve verify`, `improve cycle-complete` and `tools/validate.py` (one
  shared `validate_superseded_seat`).
- Ticket provenance resolves only to a `CONFIRMED` disposition; a historical
  `SUPERSEDED` record never satisfies `source_reports` (review fix P1,
  measured as a real gap before the fix).

## 4. Batteries

- Focused oracle: 16/16 (committed HEAD re-run).
- Improve probes `SAIPEN_IMPROVE_PROBES_ONLY=1`: 192/192, T-1406 controls green.
- Adjacent CLI/lifecycle families: 55 tests, 1 PRE_EXISTING
  (`tools/test_public_closure_cli.py` CONTROL C/D `SOURCE_SCOPE_MISSING`),
  reproduced identically on the pristine HEAD worktree.
- Live `tools/validate.py`: only the inherited stale improve seat report
  (`imp-vacterro-saipen-20260919-2/glm-5-3-max-01`) fails; unrelated to this
  patch. Ruff, `py_compile`, `git diff --check` clean.

## 5. Installed runtime acceptance

- Surface from `saipen/MANIFEST.json` clean at `cc86601f`; supported scheduled
  runner `bootstrap/schedule-run.ps1 -CloneRoot <repo>` rc=0.
- Distribution after injection: installed 6, stale 0, unknown 0, fresh true,
  `source_head == newest_installed_head == cc86601f1a158866b9e33736f76d685457d3481e`,
  `last_run` success rc=0 dirty [].
- Installed CLI field proof in a disposable project (installed generation
  8.0.1): the full stale-COMPLETE recovery route
  `sweep CONFIRMED → sweep SUPERSEDED (verification bound) →
  retire SEAT_SUPERSEDED → verify → cycle-complete → clean` PASS 9/9; old
  report bytes preserved; manifest reads `availability: superseded` and
  `cycle_status: archived`.

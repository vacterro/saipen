# T-2057 — lost regression-execution carriers and the typed refusal

Defect: `regression_execution._records` read each COMMITTED receipt's evidence
carrier with `_read(root, relative)`. Two carriers committed to the journal
(02.11.26 cycle) were absent from the working tree, so every anchored
`work regression` pair in the project died with a raw `FileNotFoundError`
(WinError 2) — no subject, no permitted next move, no way to record new pairs.

Measurements:

- Journal holds 234 COMMITTED regression receipts; exactly 2 carriers absent:
  - `regression-execution-ea60492989884b8aa9bb74dc7f414215.json`
  - `regression-execution-7967fc9849ba4104b3b7b85d63c1bbaa.json`
- Both exist byte-exact in git object commit `06fa9f073` (unreachable by any
  ref — reflog only; restore also protects the bytes locally):
  - journal `ba471cae4ec8e4a9…` == restored blob `ba471cae4ec8e4a9…`
  - journal `e0247a9766755c58…` == restored blob `e0247a9766755c58…`
- Restore used `git cat-file blob 06fa9f073:<path>` — no index staging, so the
  shared staged set stays attributable (T-1816/T-1817 class).

Repair:

- `tools/saipen_engine/regression_execution.py` `_records`: a missing carrier
  now refuses typed — `regression receipt carrier is absent: <path> (op <id>);
  restore the exact committed bytes, then re-run` — the obstacle names the move.
- Verifier `tools/test_t2057_carrier_restore.py` (hermetic: fixture root +
  stubbed journal reader): restored carriers authenticate against the journal;
  absent carrier refuses with the restore route named.
- Anchored pair recorded by the instrument (ticket T-2057, verifier
  `cd4feea746b0`): before-half (pre-fix subject bytes preserved at
  `.saipen/evidence/T-2057/regression_execution.before.py`) red with the leak,
  after-half green — same verifier, FAIL then PASS.

Contract notes (schema 1, `.saipen/evidence/T-2057/regression-contract.json`):
the sandbox is context-only and hermetic, so the context carries what the
import needs: the test, the whole `tools/saipen_engine` package, the
`tools/_module_identity.py` init dependency, and the `saipen/` protocol home
(REGISTRY.json/BOOT.md) the engine resolves at import time.
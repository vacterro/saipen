# T-2076 — external closure binds the RECORDED installed generation

Date: 2026-11-17. Scope: P0 verification of the EX-000053 provenance deadlock
and a fail-closed predicate repair, inside the operator-approved conditional
T-2058 + 8.1.1 preparation scope. No bypass, no install, no commit.

## Diagnosis (verified, not inherited from the report)

`external.resolution_problems` compared the receipt's `installed_identity`
with `engine_identity()` of the module tree answering the check. Revalidation
is refused unless the executor IS the install the project records
(`HOME_REQUIRED`), so the receipt is truthful for the installed generation —
but a read-only validation from the release candidate compared it against the
CANDIDATE's own engine and reported "the dependency moved" for a checkout that
moved nothing.

Measured identities (read-only):

| generation | path | VERSION | files | engine_digest |
| --- | --- | --- | --- | --- |
| installed | `C:/Users/vac34/AppData/Local/saipen/scheduled-source` | 8.1.0 | 170 | `sha256:d64ee12ee476fde8…` |
| release candidate (what the ship gate reported) | staged 8.1.1 release index | 8.1.1 | 175 | `sha256:37dbbc7a61ca2473…` |
| live worktree, pre-fix (HEAD `external.py` `8491319e`) | `V:\___VAC\…\_SAIPEN` | 8.1.1 | 175 | `sha256:740124ec36ff2e1f…` |
| live worktree, post-fix (`external.py` `59e53207`) | same | 8.1.1 | 175 | `sha256:e1d19bf06def7190…` |

`EX-000053` (T-1653) records `sha256:d64ee12e…` — the truthful installed
proof, not a stale or forged record. The two live-worktree digests differ only
in `tools/saipen_engine/external.py`, so the regression pair below attributes
the verdict change to that file alone.

## Change

- `tools/saipen_engine/external.py`
  - `_engine_identity_at(tools)` is the one framing; `engine_identity()`
    delegates with the running tree (digest unchanged by the refactor).
  - `installed_engine_identity(root)` reads the project's own
    `STATE.saipen_home` and authenticates it through the canonical modules:
    layout usability (`state.persisted_home_access`), machine-runtime
    projection (`machine_runtime.current_generation_for`), and a coherent
    shipped generation (`runtime_surface.runtime_generation_identity`).
  - `resolution_problems` compares the receipt with that generation. A
    declared home that cannot be authenticated FAILS CLOSED with a named
    diagnosis; a legacy pointer (no absolute home) keeps the previous
    running-engine comparison; a running engine that IS the recorded home
    short-circuits without a second read.
- `tools/test_t2076_installed_generation_binding.py` — 7-test matrix.

## Regression pair (anchored, same verifier both halves)

Verifier: `tools/test_t2076_installed_generation_binding.py`
(`sha256:1a805243275a7e4c…`). Its fixture identities are computed by a
test-owned `_identity_at()` that hashes what `engine_identity()` documents, so
the suite RUNS against the pre-fix subject instead of erroring on a missing
new symbol. Only `tools/saipen_engine/external.py` differs between halves.

- FAIL, subject `740124ec36ff2e1f…` (HEAD `external.py` `8491319e`):
  `python tools/test_t2076_installed_generation_binding.py` -> rc=1,
  `FAILED (failures=6)`, every failure the legacy
  `... running engine is sha256:740124ec... -- the dependency moved` for a
  checkout that moved nothing. Log: `regression-red.log`.
  Anchored event: `REGRESSION-EVIDENCE FAIL ...` (E-21428).
- PASS, subject `e1d19bf06def7190…` (`external.py` `59e53207`): same command
  -> rc=0, `Ran 7 tests ... OK`. Log: `regression-green.log`.
  Anchored event: `REGRESSION-EVIDENCE PASS ...` (E-21429).

Live probe on the real project (pre-fix) reproduced the same defect:

```
python - <<'PY'
import sys; from pathlib import Path; sys.path.insert(0, "tools")
from saipen_engine import board, external
root = Path(".").resolve()
t = board.parse_board((root/".saipen/BOARD.md").read_text(encoding="utf-8"))["tickets"]["T-1653"]
print(external.resolution_problems(root, "T-1653", t))
PY
```
-> `['EX-000053 was verified against installed engine generation
sha256:d64ee12ee476fde8... but the running engine is sha256:37dbbc7a61ca2473...
-- the dependency moved (rollback or upgrade): re-resolve truthfully instead of
inheriting a stale green']` (ship-gate-indexed.log line 18; `37dbbc7a` is the
release-candidate index materialization, not the live worktree).

## GREEN measurements

- New suite: `python tools/test_t2076_installed_generation_binding.py` ->
  `Ran 7 tests ... OK`.
- Focused-unit evidence for the changed verifier (3 patterns, 53 tests):
  `PASS`, record `.saipen/evidence/focused-unit/9eaf6b399a04ed45-20261117T032447091480Z.json`.
- Same live probe after the fix -> `problems: []`.
- Regression suites green: `test_external_resolution` (10), 
  `test_external_revalidation` (36), `test_external_authentication_contract`
  (13), `test_generation_migration` (8), `test_install_identity_doctor` (17),
  `test_t1840_external_renewal` (19), `test_t1914_installed_runtime_parity`
  (5), `test_t1916_external_delta` (12), `test_install_drift` (10),
  `test_t1402_readonly_reporters` (4), `test_t1736_tool_safety_and_evidence`
  (8), `test_runtime_generation_identity` (55, 1 skip).
- Ship gate with the exact 1593-path release index PLUS the fix and the
  SRC-419 work receipt staged:
  `python tools/validate.py --gate ship` -> rc=0, "Validation complete. Agent
  is conformant. (18 warning(s))", 0 problems, no `EX-000053` line, and
  `PASS: every DONE closure provenance satisfies its declared closure
  contract`. Log: `ship-gate-p0-fix.log`.
- Index restored byte-identically: `git ls-files -s -z` cmp equal (8332
  entries, the original 7 staged entries intact).

## Consequence recorded, outside this fix

The engine edit moved the source, so T-2047's current-cycle verification went
stale (designed fail-closed). Repaired canonically:
`saipen work reverify T-2047 --run 'python .saipen/evidence/T-2047-replay.py'`
-> `RV-000085`, executed PASS (exit 0), verdict `PASS_WITH_CARRIED_DEBT`.
After the verifier revision below moved the tree once more, the canonical
replay was repeated -> `RV-000086` (executed PASS, carried debt = the 28
pre-existing core problems). `validate.py --gate core` is back to the
pre-existing 28 FAILs, exactly the count in
`T-2058-release-index/core-gate-unstaged.log`; no new conformance problem was
left by this ticket.

## Still open (not this ticket)

- Gate B is untouched: SC-7 needs T-2073/T-2074/T-2075 terminal dispositions
  and a forced HUNT bound to the post-change source; those rows are excluded
  from the current operator scope.
- No commit, no injection, no re-resolution: the fix is a worktree candidate
  awaiting release-scope authorization. After injection the installed
  generation moves again, so EX-000053 must be re-resolved by the installed
  CLI before any CONFORMANCE/SHIP claim.

## Conformance diagnosis: installed 8.1.0 vs candidate 8.1.1

`saipen validate` (installed engine, `install_home = ...scheduled-source`,
receipt `receipt-edd4838d5049`) records `CURRENT_FAIL` with exactly TWO
blocking findings:

1. `STATE.md audit route not followed -- the audit inbox routes 'saipen audit
   ingest' ... but next_action is 'saipen crew'`
2. `FUTURE GATE: future gate FG-0046 names slice ticket T-1936, which is not on
   BOARD`

Both are dead ends the worktree candidate already fixes, measured live:

- `audit_route.route_violation(projection, 'saipen crew', tickets)` -> `None`
  with the live BOARD (T-2016, the layer's Work, is `## BLOCKED`), and the
  route itself is unfollowable: `tools/saipen.py audit ingest --dry-run` ->
  `SOURCE_UNRESOLVED: linked Work T-2016 is not DONE`. T-2072 owns the fix.
- `future_gate.validate_future_gate(root, tickets)` on the worktree engine ->
  `{"errors": [], "warnings": []}`, 54 documents (the ledger-closed slice
  acceptance T-2071 added).
- The worktree `tools/validate.py --gate core` reports NEITHER finding; its
  28 FAILs are the documented pre-existing release-candidate baseline.

So `CONFORMANCE_CURRENT_PASS` is gated on installing/publishing the 8.1.1
candidate (`BOOTSTRAP_PUBLISHED`), not on a repair this tree still owes. The
binding ship gate on the exact release index is already PASS
(`receipt-150b40c88fb9`, `install_home` = this worktree, 0 problems).

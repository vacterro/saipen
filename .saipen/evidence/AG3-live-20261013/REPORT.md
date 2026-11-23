# Cross-user autonomy recovery -- SRC-239 / T-1743 (SAIPEN), SRC-105 / T-287 + T-289 (SAITULS)

Date: 2026-10-13. Every claim below names its proof class.

## Primary outcome

Measured through each account's own SAI Accounts broker, non-elevated token
(REAL_MANAGED_ACCOUNT_PASS), with `sai-accounts saipen-readiness <AG> --workdir <project>`:

| Account / project | Runtime | Bootstrap | Read admission | Write admission (dry-run checkpoint) | Verdict |
|---|---|---|---|---|---|
| AG3 `SAIAG_9fabb0d5` (...1019) / SMART_VAC_CLEANER | READY 8edc8b9b | BOUND, MACHINE_RUNTIME, legacy home INACCESSIBLE_BUT_REPLACED ("No operator action is needed") | PHASE BUILD T-195 | ADMITTED | READY |
| AG3 / SUNO_DOWNLOADER | READY | BOUND | PHASE BUILD T-8 | ADMITTED | READY |
| AG2 `antigravity_b` (...1008) / SUNO_DOWNLOADER | READY | BOUND | PHASE BUILD T-8 | ADMITTED | READY |
| AG2 / SMART_VAC_CLEANER | READY | BOUND | PHASE BUILD T-195 | ADMITTED | READY |

Negative controls (same tokens): AG2 -> ungranted AUDAPACK recovery, AG3 -> ungranted
FastPrompter, AG3 -> antigravity_b profile, AG2 -> SAIAG profile, AG3 -> C:\Users\vac34,
AG3 -> vac34 `.agents\skills\saipen`: ACCESS_DENIED. AG3 write probe into
`C:\ProgramData\SAI\SAIPEN`: denied (runtime read-only). Matrix:
`__SAITULS/.saipen/evidence/T-287/matrix-summary-T289.json`.

Not proven: an AG3 *agent* session performing source edits and a lifecycle write
end to end -- that needs a human prompt in the AG3 console (one operator action).

## Root causes, by owning layer

| # | Layer | Defect | Fix |
|---|---|---|---|
| 1 | SAITULS / SAI Accounts | No way to measure SAIPEN as the managed token; T-1652 was operator-manual; managed console had no `saipen` entrypoint | T-287 broker op `saipen_readiness` + CLI verb + PATH entrypoint; T-289 write-admission dry run |
| 2 | SAIPEN engine | `audit_manifest`/`suite_record` proved owned dirs up to the drive root; `V:\___VAC\__K` is unreadable to a managed SID | `ownership_root` = project root (T-1743 F3) |
| 3 | SAIPEN engine | Machine runtime served only a project recording the checkout path; SMART records the injector home `C:\Users\vac34\.agents\skills\saipen` -> reads passed, every write refused "This needs the operator" | install records proven `projected_homes`; `projects()` serves them (F5) |
| 4 | SAIPEN engine | `rebind-home --auto` under the machine runtime records a versioned generation dir; the next upgrade prunes it -> HOME_REQUIRED loop (SUNO) | a pointer to any machine generation follows the current one (F6) |
| 5 | SAIPEN engine | `recover --adopt-legacy` DEC counted as closure evidence -> adopted rows re-flagged for a reopen approval | adoption excluded like attestation (F1) |
| 6 | SAIPEN engine | A small BOARD row with a foreign field had no repair (ticket compact refused, Fleet/recover named nothing) | explicit lossless compaction + Fleet SAFE `BOARD_FOREIGN_FIELD` + residue route (F2/F4) |
| 7 | SMART canonical memory | saihunt seat hand-wrote E-208 (no `[op:]`, `source:` field on T-199) | `saipen recover` (E-209..E-240) + `saipen ticket compact T-199` (E-241); prevention ticketed SAIPEN T-1745 |

## Changes

SAIPEN (`T-1743`): `tools/saipen_engine/{log,reconcile,board_compaction,operations,fleet,audit_manifest,suite_record,machine_runtime,host_bootstrap,state}.py`;
`tools/test_t1743_cross_user_dead_ends.py` (new, 21 tests); `tools/test_t1712_manifest_runtime.py`
(denial simulations moved inside the project root + above-root acceptance). Machine runtime
`C:\ProgramData\SAI\SAIPEN` reinstalled (generation 8edc8b9b, previous kept for rollback).

SAITULS (`T-287`, `T-289` DONE): `Scripts/accounts/SaiAccounts.cs`, `tests/test_sai_accounts.py`,
`tests/account_console_environment_test.cs`, `CHANGELOG.md`; deployed with `build.ps1 -Deploy`
(retained images `*.old-*` = rollback), AG2/AG3 brokers restarted via the helper.

SMART_VAC_CLEANER: canonical memory only, via SAIPEN operations (recover, ticket compact).
AUDAPACK: nothing changed.

## AUDAPACK

Recovery root `_AUDAPACK_RECOVERY_20261010`, lineage `0ee6b060...`, HEAD `6c6d841`: phase DONE;
T-1, T-2, T-4 DONE; T-3 BLOCKED on the filesystem cutover decision. Full pytest
2911 passed, 17 skipped, 0 failed (811 s, `audapack-recovery-full-pytest.txt`).
Original root untouched (HISTORY_LEDGER_CORRUPT, NO_GO).

## Open

- SAIPEN T-1743 SHIP waits on the declared core-unit family run (evidence file
  `core-unit-T1743.txt`), then no-publish finish (T-1644 still open: no commit, no push).
- T-1742 parked behind T-1743 (VERIFY state and E-14983 regression PASS preserved).
- SAITULS T-288 GUI consumption of the readiness facts; SAIPEN T-1744 (Fleet skew guard),
  T-1745 (stop hand-written sub-agent collects).
- SAITULS `Scripts/accounts/` and its tests are untracked in git (pre-existing).
- SMART_VAC_CLEANER is being worked right now by another agent (vac34 token, seat workbuddy,
  T-195 BUILD since 14:56): do not start a second writer there.

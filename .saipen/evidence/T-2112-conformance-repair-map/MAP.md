# T-2112 — conformance repair map: the 5 findings, owners, cures (2026-11-20)

The `cc all` route refuses `CONFORMANCE_UNHEALTHY` on the live receipt
**`receipt-ac6942f98ba7`** (generated 2026-11-20T14:59:56Z by the installed
engine's doctor *during this session's own cc calls*; snapshot
`.saipen/recovery/conformance/2026-11-20T14_59_56.821876Z_receipt-ac6942f98ba7_core_FAIL.json`).
This map binds each receipt-bound blocking finding to its true owner, repair
state and recheck condition. It registers the diagnosis; it grants no
authority and mints no duplicate ticket for a fix that already exists.

## 0. Live ownership screen (installed engine, T-2106-era projection)

`ENGINEERING_REQUIRED`, owner "SAIPEN conformance/remediation",
`engine_work_count: 4`, `operator_action_count: 0`, findings complete:
4 × ENGINE_INTERNAL (`operator_action_due: false`, route `saipen continue`)
+ 1 × unclassified. The screen's honest reading: the **protocol** owes these
repairs — but the repair **work is already built in the repo and undelivered**
(P0-A), so fresh engine Work would duplicate parked fixes. The binding
owner of the delivery is **T-2058** (BLOCKED, gates A/B).

## 1. The 5 findings

| # | key | rule / subject | repair state | recheck condition |
|---|---|---|---|---|
| 1 | `951519198641fb4b` | `closure_provenance_drift` EX-000053 (T-1653 external closure) | **generation-stale**: closure bound to `sha256:d64ee12e…`, running engine now `sha256:c4fd0203…` (moved again today); no truthful re-resolution while generations drift; "re-resolve truthfully instead of inheriting a stale green (CORE-003)" | after the authorized install stabilizes one generation: re-resolve through the installed CLI, or record the refusal — never inherit green |
| 2 | `76b48f23558dce11` | unclassified: FUTURE GATE FG-0046 → T-1936 not on BOARD | **fix exists, undelivered**: `tools/saipen_engine/future_gate.py` (M, uncommitted) answers a board-scrubbed slice ticket against `closed_in_history` (T-1936 → E-18545, per T-2058's delivered scope) | validate once on the installed fixed generation; no repo change is missing |
| 3 | `52e506b17ff19042` | `runtime_manifest_untracked` `tools/test_t10_submit_route.py` | **release-surface**: file exists in tree, untracked by git; cure is "commit the file or drop the manifest entry" — both are ship-6b operations on the T-2058 staged set | the operator's install/publication decision names the allowlist branch; then commit or drop |
| 4 | `7e40107c99ffa968` | `runtime_manifest_untracked` `tools/test_t5_ratio_is_not_a_count.py` | same class as #3 | same as #3 |
| 5 | `e54399132c79dc9d` | `coverage_gap` `tools/regression_t2089/home_extensions/subs/PROTOCOL.md` | **fix exists, undelivered**: `tools/validate.py` (M) carries EXEMPT pattern `tools/regression_*/**/*.md` — "test-fixture prose copied into throwaway sandboxes by regression oracles (t2089_oracle.py copies home_extensions/subs/PROTOCOL.md in)" | validate once on the installed fixed generation; no repo change is missing |

Generation facts: installed = AppData `scheduled-source` 8.1.0 sync (digest per
receipt `c4fd0203…` — moved twice since 19.11: `df039ef6` → today; install
fingerprint observed `5d02a60b…` this session); repo = 8.1.1 worktree
(`ff15edff`-era + uncommitted T-2058/T-2090/T-2091/T-2106/T-2109 deltas).

## 2. What actually clears CURRENT_FAIL

One operator decision (the packet in `../T-2058-release-index/BLOCKED.md`
"what unblocks it" + `../T-2110-nightshift-drift/DRIFT.md` §4): authorize the
named install mechanism for the prepared 8.1.1 delivery (or refuse). On the
fixed installed generation: findings 2 and 5 clear by the already-written
code; 3 and 4 clear by the commit-or-drop branch the decision names; 1
re-resolves against the stable generation or records the truthful refusal.
No `saipen validate` retry on unchanged inputs adds information before that
(retry discipline, LIVE_STOP_MATRIX §7).

## 3. No duplicate Work rule honored

Findings 2 and 5's fixes are the two T-2058 scoped modules
(`tools/saipen_engine/audit_route.py` M, `tools/saipen_engine/future_gate.py`
M) plus `tools/validate.py` M rules referenced by T-1592/T-1879 notes —
already built, verified on the fixed generation (same-data two-generation
probe, BLOCKED.md) and red only in the undeployed runtime. Creating new
tickets or new code for them would duplicate parked Work and weaken
provenance; this map is the registration of that fact.

## 4. Safe independent remainder (unchanged by this map)

Foreign-red owners for the family SHIP gate (T-2049 gc WIP decision,
T-2066 staged host policy completion, stale fixtures t1704/t2087), ZAICODE
P1-E regressions (cross-repo), T-2090/T-2091 re-lifecycle after the tree
cleans. All previously recorded with exact owners in DRIFT.md §5.

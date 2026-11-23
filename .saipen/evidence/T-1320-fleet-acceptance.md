# T-1320 Fleet Recovery acceptance and release hygiene

Scope: T-1320 implementation, SRC-036 and its mid-work amendment SRC-037.
The operator supplied the pre-work broad boundary: 2 PASS and one
PRE_EXISTING `ORPHAN_RECEIPT SRC-024`; T-1317's Kiro R010 remains
BLOCKED_EXTERNAL. Neither is attributed to Fleet Recovery.

## Focused proof

- The Fleet/guard/reconcile/OpenCode/launch/search/continue regression set ran
  151 tests with 151 PASS. It includes healthy, repairable, ambiguous,
  wrong-lineage, foreign-cwd, non-SAIPEN, detached, stale Edit/Write/Bash/Task,
  unchanged-condition, product-work-preservation, and read-only scan cases.
- The representative synthetic matrix named LIMISAW, PROBLIP, AUDAPACK,
  healthy-SAIPEN, and ordinary-repo classified respectively BOUND_VALID,
  BOUND_RECOVERY_REQUIRED_SAFE, BOUND_RECOVERY_REQUIRED_BLOCKED,
  BOUND_VALID, NON_SAIPEN. Explicit scan changed no canonical bytes.
  Recovery asserted to PROBLIP while cwd was AUDAPACK changed only PROBLIP.
  Live fleet repositories were not mutated.
- The no-rg case patches `subprocess.run`, `Popen`, `check_output`,
  `shutil.which`, and `os.system` to throw if invoked; canonical Python search
  still returns the expected match. The complete search/runtime-bootstrap
  focused set ran 46 tests with 46 PASS. The OpenCode adapter's Fleet path
  invokes Python, not rg or generic shell search.
- The installed OpenCode native host smoke ran 5/5 PASS in a fresh process,
  then 7/7 PASS with both ownership regressions after the final owner refactor.
  Its proof and manifest are under
  `T-1320-opencode-native-smoke/T-1320-opencode-fleet-recovery-20260913.2-05b7e3ceaa4144a988761a8d8a554e6a/`.
  Source, installed, and loaded adapter SHA256 are all
  `941c650a9301f38442820963ea8a176c70c66363f8e95a47427c4be079f08916`.
- `T-1320-fleet-native-smoke.json` is the separate real `opencode run` proof
  using one deterministic local model server. The pre-recovery Write is
  refused `RECOVERED_REISSUE_REQUIRED`; a newly issued Write succeeds and
  writes `FRESH`; product T-001 remains active in BUILD. The proof records
  the same source/installed/loaded hash.
- Historical ownership regression 2/2 PASS. After the corrected fresh smoke,
  the T-1317 manifest and proof remained byte-identical at SHA256
  `49473c96b617f16d285fd78b96c8d587a47c3dadcab84e56d3354c4317706f7c`
  and `fc1b23e2ac0025a5edcc9917cbc437808f65de6c47ab3162b8be7926b5e3fffe`.
  Those two files had already been overwritten by the old smoke owner and
  contain T-1320 bytes. `T-1317-opencode-native-smoke/OWNERSHIP-NOTICE.md`
  records this limitation; original native-smoke bytes were not recoverable
  from the current archive or Git history. The separate T-1317 live-session
  proof remains preserved. The unchanged ownership test was also run with the
  former literal T-1317 owner injected: it went red on the original-vs-later
  proof bytes, then green against the final owner. The red-control carrier is
  `.saipen/kitchen/t1320-evidence-owner-red-control.py`.

## AC-01..AC-12

| AC | Verdict | Decisive evidence |
|---|---|---|
| 01 | PASS | `fleet.preflight` and binding fixture distinguish all six states; conflict never falls back. |
| 02 | PASS | Safe malformed phase calls public `saipen recover` once, then fresh preflight returns BOUND_VALID. |
| 03 | PASS | Ambiguous journal/phase and wrong lineage tests compare canonical bytes before/after. |
| 04 | PASS | Host driver and real OpenCode proof refuse stale Edit/Write/Bash/Task payloads; fresh Write succeeds. |
| 05 | PASS | T-001 remains active in BUILD after recovery; no product DONE event or acceptance substitution. |
| 06 | PASS | CLI scan accepts only explicit bounded roots, reports machine facts, and preserves all inspected bytes. |
| 07 | PASS | A binding while cwd is B and representative matrix show no cross-project mutation. |
| 08 | PASS | Ordinary Git repository classifies NON_SAIPEN; no `.saipen` creation. |
| 09 | PASS | Unchanged condition returns RECOVERY_FAILED and a second call performs zero recovery attempts. |
| 10 | PASS | Fresh installed OpenCode process and local-model proof show binding, recovery, refusal, fresh action. |
| 11 | PASS | No-rg pure-Python search case and 46-test search/runtime set. |
| 12 | PASS for T-1320 delta | Runtime manifest is now complete (328 tracked files); final core reds are all PRE_EXISTING, listed below. Strict core is still red. |

## Full core-gate red classification

The first core run had 50 problems and 25 warnings. After staging the exact
31 distinct on-disk files selected by the canonical manifest copy trees, the manifest
check reports `PASS: runtime manifest complete (328 files, all tracked)`;
the second core run has 18 problems and 25 warnings. No evidence directory,
kitchen log, generated artifact, or unrelated path was staged. Classification
of every red from the first run:

| Initial red group | Count | Classification | Final observation |
|---|---:|---|---|
| Manifest names an untracked file | 32 | RESOLVED | 31 distinct required file paths in Git index (the adapter registry was reported twice); 328-file inventory PASS. |
| `ORPHAN_RECEIPT SRC-024` | 1 | PRE_EXISTING | Operator baseline; unchanged. |
| Missing allocation event for T-1314, T-1312, T-1313, T-1310, T-1311, T-1307, T-1308, T-1309, T-1306, T-1257, T-1099, T-407, T-406, T-442, T-575 | 15 | PRE_EXISTING | All refer to older tickets; unchanged in both runs. |
| Closed root-file-set finds `T-1318` | 1 | PRE_EXISTING | Root file existed before this T-1320 session; unchanged. |
| Coverage gap for three older documents | 1 | PRE_EXISTING | Same three paths in both runs; untouched by T-1320. |

Final core-red totals: PATCH_OWNED 0, PRE_EXISTING 18, RESOLVED 32,
UNKNOWN 0. The strict core gate still fails and is not represented as globally
clean. An additional broad `unittest discover -s tools` diagnostic ran 1836
tests with 38 failures and 2 errors (11 skips); its output was not retained
in a file. It is not asserted green or classified as a T-1320 acceptance pass.

No Production Hardening was started.

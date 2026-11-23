# T-1933 follow-up — the 20-ticket valve kept tripping because the fix was never deployed

Operator asked on 26.10.26 why the `goal_tickets: 20` blocks still trip after
SRC-339 was repaired. Measured answer: the repair reached the SOURCE artifact
only. The hook the host actually executes was still the pre-fix generation.

## The report is not new

The agent report is `_ZAICODE/audit/SAIHANDOFF_ZAICODE_20261026_1424_VALVE_AND_INGRESS_BLOCKER.md`,
sha256 `2b8979aaaeb1a65cc63d2528c3b382c65adf469f7af295c282b667bd6b102d42`.
That is byte-identical to the layer T-1933 already consumed (journal
`E-18499`), so the audit folder holds no newer finding — the same report was
being re-read while its repair sat undelivered.

## The measured defect

| surface | sha256 | `declared_action` | verdict |
| --- | --- | --- | --- |
| `extensions/adapters/zaicode/saipen-guard.py` (source, T-1933) | `4317be7f…` | 2 | repaired |
| `C:\Users\vac34\.zcode\hooks\saipen-guard.py` (installed) | `57f81cfd…` | 0 | **pre-fix** |
| `.zaicode/home/.zcode/skills/saipen/extensions/adapters/zaicode/saipen-guard.py` (delivered skill) | `57f81cfd…` | 0 | **pre-fix** |

`python tools/install_host_guard.py zaicode --check` answered
`{"installed": true, "current": false, "problems": ["artifact-stale"],
"effective": "ENFORCEMENT_GAP"}`. Nothing in the T-1933 closure path reads
that verdict, so a green ticket left the operator's host sealing every prompt
as `continue` — exactly the reported symptom.

## What was done now

1. `python tools/install_host_guard.py zaicode` — installed the repaired
   artifact; post-install `--check` reports `current: true`, `problems: []`,
   `effective: UNKNOWN` (execution is never proved by an installer).
2. `python tools/saipen.py runtime --prelaunch --adapter zaicode` — resynced
   the isolated-home skill surface; `stale: false`, `engine_diff: []`,
   `hook_problems: []`, `requires_host_restart: true`.
3. Verified both installed surfaces now digest `4317be7f…` with
   `declared_action` present, and `runtime --check-freshness` reports
   `zaicode stale=False`.
4. Ran `tools/test_t1933_zaicode_goal_seal.py` (16 tests) against the
   **installed** file, not the source: 16/16 OK. The classifiers answer
   `gg harden ingress -> goal`, `cc -> continue`, `/goal cc all -> continue`.

## What is still NOT proved

- **Host restart has not happened.** The running host may still hold the
  previous hook registration; the resync answer states
  `requires_host_restart: true`. Real delivery is therefore unverified.
- **The ZAICODE valve is still spent.** `_ZAICODE/.saipen/STATE.md` holds
  `goal_tickets: 20`, `continuation_authority: operator_required`,
  `safety_valve_mode: hard_wait`; the engine answers
  `budget_exhausted: True`, `persistent: False`, `reset_authority -> mode
  wait / required_ingress operator_carrier`. This Work did not and must not
  clear it: SRC-339:R006 records hand-editing `goal_tickets` as a non-goal.
- **Live acceptance remains UNVERIFIED.** No receipt shows a real installed
  host delivering a `goal`-sealed prompt. Only an operator prompt through the
  restarted native ingress can prove it.

## Filed

`T-1934` — a repaired adapter artifact is never redeployed; the installed hook
keeps executing the pre-fix generation while the ticket reads green. The
`install_host_guard.py --check` verdict exists but no closure gate consumes it.

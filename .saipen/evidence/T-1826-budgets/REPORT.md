# T-1826 — declared budgets must clear their measurements

## Defect, measured

The ticket names one symptom and one suspicion. Both are real, and they share
a cause: a bound was set from an expectation instead of from a measurement.

**1. The unit family budget.** `tools/saipen_engine/test_runner.py`,
`_families()`, declared 5400 s for the `unit` family. The number was chosen in
T-1344 when the family held 3475 tests and a run cost 2254 s. The family now
holds ~6950 tests, and two single-process records already on disk show what a
run costs:

| record | mode | duration | result |
|---|---|---|---|
| `4938af3e6ed9afc4-20261019T225802Z` | `--jobs 1` | 6879.7 s | PASS |
| `73e01d794f842e8c-20261020T010550Z` | `--jobs 1` | 7458.0 s | 2 red |

Both are above 5400 s, so `core_unit.py evidence` reported TIMEOUT for a suite
that had finished its work. A budget that answers "no" to success is a false
negative in the one gate SHIP depends on.

**2. The OpenCode adapter's child bound.** `extensions/adapters/opencode/saipen-guard.js`
ran every canonical check as a subprocess with `GUARD_TIMEOUT_MS = 15000`.
Measured on this host, 2026-10-20, against a fresh copy of this tree:

| condition | wall time |
|---|---|
| `response check --classify --operational-turn`, cold | 20.19 s |
| same, warm | 12.11 s |
| same, six calls concurrently | 15.67 s each |

15 s was below the measured cost. Under load the adapter therefore killed a
healthy engine and surfaced `EXEC_RESPONSE_INVALID: ETIMEDOUT` — which is the
exact message in the two `test_t1553 RealLauncherInit` reds the ticket
attributes to flakiness. They are not flaky; they are the adapter timing out.

## Change

| file | before | after | basis |
|---|---|---|---|
| `tools/saipen_engine/test_runner.py` | 5400 s | 10800 s | recorded worst case 7458.0 s + 45% |
| `extensions/adapters/opencode/saipen-guard.js` | 15000 ms | 45000 ms | measured worst check 20.19 s, and equal to the Claude hook's existing 45 s |

The family bound is a bound, not a prediction: it is raised from the slowest
recorded run, with headroom for host load, and the comment says so. The adapter
bound stops inventing a third number for the same engine call — Claude's hook
already answered 45 s, Codex's 60 s.

## Controls

`tools/test_t1826_declared_budgets.py` — six tests, all against the live
declarations:

- the unit family budget clears every recorded run with 1.2× headroom;
- it is strictly above the run that already timed out;
- `core_unit.family()` still consumes the declared family unchanged;
- the adapter bound clears the slowest measured check;
- it is not below its sibling transport (Claude's 45 s);
- the t1553 harness outlasts the adapter bound, so the harness cannot cut a
  turn off before the adapter would.

Red control: a disposable copy with 5400 / 15000 restored ran the same six
tests and failed four, exit 1 (`red-control.txt`). The two that stay green are
the ownership checks that do not read the numbers.

## Consequences checked

- `test_adapter_parity` — 17 tests OK.
- `test_t1553_mid_session_activation.RealLauncherInit` — 2 tests OK (the exact
  pair that flaked).
- `test_operator_ingress_matrix` clause R and
  `test_opencode_host_smoke.OpenCodeRealInstalledGeneration` — 3 tests OK after
  the artifact was installed through `bootstrap/inject.ps1 -AdapterId opencode`.

The first family run of this ticket found those last two red, and they were
true: the shipped adapter carried 45 s while the installed host plugin still
carried 15 s. The install is the canonical one — it copies the artifact,
verifies the digest against the shipped file, and removes the stale legacy
surface. In a running host the old plugin stays loaded until restart; the
injector says so in its own output.

## Not changed

No retry, no timeout override, no weaker gate. The family still runs the same
command; only the bound moved. `regression_execution`'s 1..5400 s contract
limit is a separate, per-verifier bound and is untouched.

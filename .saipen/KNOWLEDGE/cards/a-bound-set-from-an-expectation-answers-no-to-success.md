<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: tools/saipen_engine/test_runner.py, tools/saipen_engine/core_unit.py, extensions/adapters/opencode/saipen-guard.js, extensions/adapters/registry.json, bootstrap/inject.ps1, host hooks, declared core-unit family
trigger: a TIMEOUT verdict on a family run that was in fact green, an EXEC_RESPONSE_INVALID: ETIMEDOUT from a host adapter, or any budget/bound that a slow-but-healthy path crossed
status: active
evidence: T-1826, .saipen/evidence/core-unit/4938af3e6ed9afc4-20261019T225802Z.json, .saipen/evidence/core-unit/73e01d794f842e8c-20261020T010550Z.json, .saipen/evidence/core-unit/2e52f7cd26e1ad34-20261020T093930Z.json, tools/test_t1826_declared_budgets.py, tools/saipen_engine/test_runner.py:70, extensions/adapters/opencode/saipen-guard.js:52
supersedes: none

# A bound set from an expectation answers "no" to work that succeeded

Two bounds in this repository were set when their subject was smaller, and both
had drifted below the cost they were supposed to cover. Neither produced a wrong
result; both produced a FALSE NEGATIVE reported as a failure, which is the
expensive kind.

Why:
`test_runner._families()` declared 5400 s for the `unit` family when the family
was 3475 tests and a run cost 2254 s. At ~6950 tests the recorded single-process
runs cost 6879.7 s (clean) and 7458.0 s (loaded host), so `core_unit.py evidence`
wrote TIMEOUT for a suite that had finished, and SHIP's own gate refused a green
tree. The OpenCode adapter ran each canonical check as a child with
`GUARD_TIMEOUT_MS = 15000`, while `response check --classify --operational-turn`
measured 20.19 s cold, 12.11 s warm and 15.67 s at six-way concurrency on the same
host: under load it killed a HEALTHY engine and surfaced
`EXEC_RESPONSE_INVALID: ETIMEDOUT`, which reads exactly like a protocol defect
and was twice mistaken for a flaky test.

Rule: a bound is not a prediction, it is a measured ceiling with headroom. When
a timeout-shaped verdict appears, measure the path's actual cost in the condition
the bound runs in (cold, warm, concurrent) before changing any code the timeout
was pointing at. Set the bound from the slowest measurement plus headroom, say in
the comment which measurement and record it came from, and pin the relation in a
test so a later cleanup cannot quietly shrink it back. Do not add retries: a retry
under a bound that is already too small only moves the same wall.

Second rule, learned on the same ticket: when an adapter artifact and its
INSTALLED host copy both exist, changing the artifact alone leaves the running
host on the old bound. `bootstrap/inject.ps1 -AdapterId <id>` is the canonical
install; it copies, verifies the digest against the shipped bytes, and removes the
legacy surface. The family gate `test_operator_ingress_matrix` clause R and
`test_opencode_host_smoke.OpenCodeRealInstalledGeneration` exist to catch exactly
this, and both went red until the install ran.

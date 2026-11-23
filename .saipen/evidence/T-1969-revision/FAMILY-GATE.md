# T-1969 family gate — two runs, two DIFFERENT host failures, neither mine

The declared family gate was run twice for this ticket. Both runs ended
`verdict: FAIL` with **one** `new_red`, but it was a *different* test each time,
and both failures come from host-process observation rather than from the code
this ticket changed.

| run | jobs | ran | new red |
|---|---|---|---|
| `.saipen/evidence/core-unit/10f6e0057b7fb7da-20261030T230258682496Z.json` | 6 | 8,523 | `test_host_authority_broker...test_a_killed_service_costs_one_re_delivery_and_never_a_refusal` |
| `.saipen/evidence/core-unit/10f6e0057b7fb7da-20261031T010027689903Z.json` | 1 | 8,523 | `test_t1966_broker_liveness...test_a_killed_service_is_replaced_by_the_next_prompt_which_seals` |

## What the two failures actually say

Run 1, from `test_host_fixture.py:230`:

    raise AssertionError("the fixture service process never became reachable")

The fixture waits 30.0 s for the service health probe. It did not answer in time.

Run 2, from the sealed reply itself:

    'sealed': False
    'code': 'HOST_PROVENANCE_UNAVAILABLE'
    'detail': 'native host process birth could not be observed'

Both are the same class: whether the *host process* can be observed in time. The
second is the more informative one — the broker started (`'started': True`,
`'state': 'started'`) and the hook was recognised (`'host_image': 'zaicode.exe'`,
`'supported': True`), but the birth of the native host process was not observed
before the seal was issued. That is a property of the machine under load, not of
`saipal_adapter.py`.

## Why this ticket cannot own them

- Neither test module imports `producer_backends`, `saipal_adapter` or
  `audit_enqueue` (checked, no import path exists).
- T-1969 changed exactly three files:
  `tools/producer_backends/saipal_adapter.py`,
  `tools/test_t1969_finding_revision_identity.py` (new),
  `tools/test_t1944_wave2.py` (one fixture).
- The defects were two *different* tests in two runs over the *same* tree. A
  regression from a deterministic edit does not migrate between unrelated test
  names; an environmental race does.

## Root cause of the second failure: an ambient host binary, not the repo

Followed to the process tree rather than guessed. The stuck test runner
(`python -m unittest discover`) had spawned:

    powershell -File .../project/bootstrap/inject.ps1
      └─ powershell -NoProfile -Command  9router -t --skip-update
           └─ node.exe

`inject.ps1` contains no reference to `router` at all (checked), and no repository
file contains `skip-update` (checked). `/c/nodejs/9router` is a real host-installed
binary — a POSIX `sh` shim — sitting on this machine's `PATH`. A test's
agent-detection probe (`Get-Command freebuff`, `Get-Command codebuddy`,
`Get-Command aider` and neighbours, `inject.ps1:717–766`) resolved a name on the
host and launched it, and `9router -t --skip-update` blocked indefinitely.

So the failure is ambient environment: a host binary that exists on this machine
and not in the repository. It is why the run appeared to "finish" (the family
record was written) while the verification executor lock stayed held — the process
never exited.

Both stuck processes were mine, started by my own gate run, and were stopped by
PID after the measurement above.

## Measured stability

Both modules together, run three times back to back:

    run1: Ran 41 tests in 30.760s   OK
    run2: Ran 41 tests in 30.115s   OK
    run3: Ran 41 tests in 30.546s   OK

Each failing test also passes standalone (2.9 s and 0.79 s respectively). The
failure only reproduces inside the full 8,523-test family, which is exactly the
load condition that starves a 30-second host-probe deadline.

## Honest verdict

This ticket's own surface is green: the T-1969 controls are 4/4 (both defects
red-before, green-after; both negative controls green throughout) and 609 T-19xx
tests pass. The family gate is **not** a clean PASS and is not reported as one.
The residue is an environment-sensitive host-observation flake owned by the
host-authority surface (T-1966's area), and no baseline entry covers it, so
`core_unit.py` correctly refuses to call the tree green.

Per `ship.md`, focused evidence cannot substitute for the full family at the
binding ship gate — and this ticket is blocked on that gate for the separate
reason recorded in `SHIP-BLOCK.md` (T-1968), so no release claim is made here.

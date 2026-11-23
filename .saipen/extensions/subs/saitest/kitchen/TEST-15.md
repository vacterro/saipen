# TEST-15: bounded current-source adversarial scenarios at dc39709c

Source identity at capture: HEAD
`dc39709c0c17a3272126c01a626ffcaa4176140b`, tree
`git-delta-v1:6a857897f61278f309f56252e9d382c1f3221c91920708dc17e2d65ee16566bd`;
charter `sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08`.

Three scenarios in three charter families. The audit and validator commands
are read-only; the concurrency scenario runs only in a disposable Git project
created under this role's `kitchen/` and removes that temporary copy on exit.

## Scenario 1 -- family "damaged state": audit ingest dead end (REPRODUCED)

Minimal input: current project audit inbox, including routed SRC-386 linked to
T-2016. Exact command from the project root:
`saipen audit ingest --dry-run`.

Observed output:

```text
REFUSE [SOURCE_UNRESOLVED]
reason: linked Work T-2016 is not DONE
```

Verdict: **REPRODUCED**. This confirms the existing dead-end receipt path on
the current source. The dry-run wrote nothing. Keep the existing Core audit
ownership; the scenario adds evidence, not a new ticket.

## Scenario 2 -- family "environment": current checkout fails its declared validator (REPRODUCED)

Minimal input: current project tree, read-only. Exact command:
`python -B tools/validate.py`.

Observed: exit 1, `Validation FAILED: 29 problem(s), 34 warning(s)`. The
problems include unresolved SRC-167/T-1606, stale EX-000052 closure
provenance, the unfulfilled audit route, FG-0046 naming absent T-1936, and 25
runtime-manifest paths that Git does not track. Exact run is in
`_test15_validate.txt`.

Verdict: **REPRODUCED**. This is evidence for existing Core owners, including
cc all/T-1449; it does not claim the contents of every untracked file are
incorrect.

## Scenario 3 -- family "order and repetition": concurrent closure checkpoints race (REPRODUCED)

Bound: one temporary Git project with at most eight small fixture files, two
threads, a five-second barrier timeout and a 30-second process timeout. Input
has one committed `[op: finish-one] [T-001]` closure, a one-closure GC
interval, and one protected evidence file over a one-byte evidence budget.
The barrier makes both checkpoint calls read the same pre-checkpoint counter.
The temporary project is created inside `kitchen/` and removed on exit.

Exact command:
`python -B .saipen/extensions/subs/saitest/kitchen/_test15_concurrent_gc.py`.

Observed output:

```json
{"canonical_done": ["T-001"], "counted_done": ["T-001"], "details": [null, "WriterBusy: WRITER_BUSY"], "durable_failures": 1, "maintenance_debt": "GC_BLOCKED_PROTECTED_BUDGET", "maintenance_runs": 1, "result_codes": ["GC_RUN_COMPLETE", "GC_MAINTENANCE_FAILED"]}
```

Verdict: **REPRODUCED**. One concurrent checkpoint records a durable
`WRITER_BUSY` maintenance failure while the other completes; the counter still
matches canonical history and protected-budget debt remains visible. This is
the existing T-2062 concurrency issue, independently reproduced. Script and
raw output are `_test15_concurrent_gc.py` and `_test15_concurrent_gc.out`.

### Patch confirmation -- T-2062 pen patch (NOT_REPRODUCED against patch)

Saitest copied the patched `gc.py` into its own kitchen and ran the same
two-closure, protected-budget concurrent scenario against that isolated copy.
Exact command:
`python -B .saipen/extensions/subs/saitest/kitchen/_test15_patch_verify.py`.

Observed: 8/8 iterations passed; every round retained both canonical and
counted identities `[T-001, T-002]`, ran the protected-budget collection once,
recorded `GC_BLOCKED_PROTECTED_BUDGET`, and recorded zero durable maintenance
failures. The patch source is `.saipen/extensions/subs/saipython/kitchen/PY-15.patch`
with SHA-256 `AFB610B95DAE93BA7E3EB88FDEA241D428DD5C39A9225B65F2F587737C35CC7A`.
Raw output is `_test15_patch_verify.out`. Verdict for the patched-copy rerun:
**NOT_REPRODUCED**.

## Limits

These are three bounded cases, not a sweep of all seven scenario families.
No main project file was written or modified by saitest.

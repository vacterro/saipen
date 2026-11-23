# T-283 evidence — a finished Prepared row is history the scheduler never rewrites

Ticket: `T-283 [P3]` — the Prepared scheduler tick re-evaluates terminal job rows: the
per-job loop skips only in-flight states, so once a finished row's account leaves the
effective inventory the static branch re-saves it as `WAITING_LIMIT` ("account not
discover"). It cannot launch (the account is absent) but it rewrites a finished row's
displayed state — evidence, rewritten after the fact.

(The identical ticket `T-282` was written by the same failed `ticket add` attempt that
recovered as `T-283`; it is a duplicate of this one, not a second defect.)

## 1. RED — reproduced outside any assertion

A bare probe against the unrepaired code, same construction the tests use
(`tests/test_zz_probe_t283.py`, run then removed):

```
federation.active = True
list() sees: ['done']
after tick: state=JobState.WAITING_LIMIT reason='account not discovered' launcher='claude1'
```

A row saved as `DONE` came back from one tick as `WAITING_LIMIT` with the reason "account
not discovered" — an explanation about an account the job finished against long before.

The controls written first then failed:

```
FAILED tests/test_prepared_binding.py::test_the_worker_never_blocks_a_finished_row
FAILED tests/test_prepared_binding.py::test_the_worker_leaves_every_terminal_row_alone[DONE]
FAILED tests/test_prepared_binding.py::test_the_worker_leaves_every_terminal_row_alone[MISSED]
FAILED tests/test_prepared_binding.py::test_the_worker_leaves_every_terminal_row_alone[CANCELLED]
FAILED tests/test_prepared_binding.py::test_the_worker_leaves_every_terminal_row_alone[FAILED_TERMINAL]
5 failed, 1 passed
```

The one that passed is `test_a_finished_row_is_history_not_a_candidate`, which exercises
the T-280 migration pass and was already correct — the defect is the TICK LOOP, not the
binding resolver.

## 2. The repair — one skip

`prepared_worker.tick()` skips `TERMINAL_STATES` in the per-job loop, before anything can
decide about the row:

```python
if job.state in TERMINAL_STATES:
    # A finished row is what happened, not a candidate: this pass has
    # nothing to decide about it, so it is never re-labelled (a
    # WAITING_LIMIT rewrite would report an account as missing from a
    # job that already ended) and never re-armed.
    continue
```

`TERMINAL_STATES` is the module-level constant `T-280` derived from the existing
`PREPARED_TERMINAL_STATES` plus `DISABLED` — the same set `_settle_binding` already used to
leave finished rows alone, now hoisted to the module import so the loop and the resolver
share one definition instead of two. The redundant local import inside `_settle_binding`
was dropped with it.

Nothing else changes: in-flight rows are still owned by their execution receipt, `AUTO` /
`SYNC` / `PRIME` / `AUDIT` rows still reconcile, and an enabled armed row still runs.

## 3. Green

```
python -m pytest tests/test_prepared_binding.py tests/test_prepared_worker.py \
    tests/test_prepared_delivery.py tests/test_plane_launch.py \
    tests/test_launch_federation.py tests/services/test_audit_run_service.py -q
206 passed in 10.19s
python -m ruff check audapack tests audit     -> All checks passed!
python -m compileall -q audapack tests        -> exit 0
```

Full suite on the frozen tree is recorded in the T-283 verify checkpoint.

## 4. Residual

`tests/test_prepared_binding.py` keeps the assertion a `DONE` row is not retro-labelled
BLOCKED (T-280's ownership) AND now asserts it is not rewritten to `WAITING_LIMIT` either
(T-283's). The remaining terminal-row surface is the static branch itself, which is only
reached for non-terminal rows now — no further guard was added, because the skip is the
single entry point.

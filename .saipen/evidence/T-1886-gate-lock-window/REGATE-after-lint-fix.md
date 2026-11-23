# T-1886 addendum — post-closure re-gate on the final bytes

The ticket closed citing record `3da061c60895afed-20261024T174635441153Z.json`.
After that, REVIEW found a lint defect in my own test module: it used a
parenthesized `with` statement, which is Python 3.9+ syntax, while
`pyproject.toml` sets `target-version = "py38"`. Fixing it rewired the spy patch
in `test_the_production_path_calls_writer_lock_yielded`, so the module's final
bytes are not the bytes that gate recorded. That is exactly the staleness the
campaign forbids overlooking, so the gate was re-run.

```
python tools/core_unit.py focused T-1886 --pattern test_t1886_gate_lock_window.py
{"verdict": "PASS", "ran": 3, "reused": false,
 "record": ".saipen/evidence/focused-unit/36170b675670fc46-20261024T181532867719Z.json",
 "checkpoint": "STALE_WORK_CONTEXT"}
```

`verdict` is PASS on the current bytes with `reused: false`, so the fresh record
exists and is valid. The `checkpoint` field is `STALE_WORK_CONTEXT`, and that
refusal is correct rather than an obstacle: T-1886 is already in `## DONE`, so
`STATE.task` is `none`, and a ticket-bearing lifecycle event now would forge a
decision for work the project is not in. `tools/saipen_engine/operations.py`
refuses precisely that case. No journal entry was fabricated around it.

Also verified on the final bytes, independently of the gate:

```
python -B -m unittest tools.test_t1886_gate_lock_window tools.test_t1885_tag_peel
Ran 10 tests in 0.677s
OK
python -B -m ruff check tools/saipen_engine/release.py tools/validate.py \
    tools/test_t1885_tag_peel.py tools/test_t1886_gate_lock_window.py
All checks passed!
```

Both records exist; the closure cited the earlier one, and this one is the
authoritative PASS for the bytes now on disk.

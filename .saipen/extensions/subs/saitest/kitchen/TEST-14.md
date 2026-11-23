# TEST-14: bounded adversarial scenarios at 66ef622a

Source identity at capture: HEAD `66ef622a43ab59512735ac78ce10d1250e26f9df`,
tree fingerprint `git-delta-v1:374d12a0eb91a5d768a66863eec29c4ea0fa03a0a02190301ca437dabb5fa208`
(from the engine's own resolver), charter `sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08`.

Three scenarios, each in one charter family, each with exactly one verdict.

## Scenario 1 -- family "damaged state": audit ingest dead end (REPRODUCED)

Command: `saipen audit ingest --dry-run` from the project root.

Observed output, verbatim:

```
REFUSE [SOURCE_UNRESOLVED]
reason: linked Work T-2016 is not DONE
```

- Verdict: **REPRODUCED**.
- `consume_layer` in `tools/saipen_engine/audit_inbox.py` (around 1396-1411) admits
  a retired receipt at the first gate (`_tombstoned`) and then refuses with the
  same code because the retired receipt's linked Work is not DONE. Retirement
  therefore frees the receipt from resolution AND guarantees it can never be consumed.
- Instrument control: a home without a routed layer returns a different result,
  so this is not a blanket refusal.

## Scenario 2 -- family "environment": a checkout of this home is incomplete (REPRODUCED)

Command: `python -B tools/validate.py` from the project root, filtered for
`^FAIL: runtime manifest`.

Observed: 12 FAIL lines of the form "runtime manifest names a file git does
not track", covering `tools/_t2040_experiment.py` and eleven
`tools/test_t2040_*.py` files. `git status --porcelain tools/` counts exactly 12
untracked entries.

- Verdict: **REPRODUCED**. A fresh checkout cannot run the declared suite for
  those files; git tracks neither the files nor all of their runtime.

## Scenario 3 -- family "input abuse": the OUTBOX closed-grammar gate (NOT_REPRODUCED as product defect)

Command: `saipen outbox check saihunt` against a deliberately malformed package
whose `status:` line was empty.

Observed output, verbatim:

```
REFUSE [OUTBOX_INVALID]
reason: saihunt OUTBOX has 2 closed-grammar violation(s); the package is refused
```

and after the repair:

```
code: OUTBOX_VALID
```

- Verdict: **NOT_REPRODUCED** as a defect. The guard caught exactly the
  malformation it names and re-verified clean after the fix. Recorded because
  the failure was produced on purpose and is reproducible by construction.

## Limitations

Bounded to three scenarios in three families. Scenario 1 proves a dead end, not
downstream damage. Scenario 2 is a file-identity census and says nothing about
the correctness of the untracked files if committed. Scenario 3 tests the gate
itself. No main project file was written or modified.

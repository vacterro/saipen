# T-1890 RESULT — the R003 test now measures what it claims

## The defect

`tools/test_t1827_writer_lock_contract.py:429` exists to prove that the release
gate runs with the writer mutex released (SRC-282:R003). It called:

```python
fixture._shape()
```

`_shape` writes a VERSION only when given one, and `plan_release` refuses a
project without one, so the test died before reaching the gate:

```
saipen_engine.release.ReleaseRefusal: REFUSE [VALIDATION_FAILED] VERSION is
missing from the repository root: `saipen ship` publishes a versioned release
and does not apply to a project without one.
  release.py:702 in plan_release -> release.py:3757 in _installed_version
```

The invariant was therefore **never measured** — and it happened not to hold,
which is why T-1886 found and fixed the same thing independently. A test that
dies in setup and a test that passes are indistinguishable in a summary line
that only counts errors, so this sat as one of the 55 baseline reds.

## The change

```python
# T-1890: `plan_release` refuses a project with no VERSION, and the crew
# carrier refuses one with no owning ticket. Without both, this test died
# inside `plan_release` and never reached the gate, so the invariant it
# exists to measure was never measured. `wide=False` matches the digests
# the planner re-derives from the deferred scope.
fixture._shape(version="8.0.1", ticket="T-11", wide=False)
```

Three parameters, each load-bearing: `version` clears `_installed_version`,
`ticket` clears the crew carrier's `CREW_NOT_READY` ("no deferred crew scope
is derivable"), and `wide=False` makes the deferred digests match what the
planner re-derives (without it: `STALE_PLAN ... live '12934ce...'`). Verified
by adding them one at a time and watching the refusal change.

## Proof it is now a real oracle

The control holds the test file fixed and swaps only the module under it:

```
RED   pre-fix release.py (HEAD):        gate_ran=True held_during_gate=True
      -> assertion "lock must be free" VIOLATED (test RED)
GREEN post-fix release.py (T-1886):    gate_ran=True held_during_gate=False
      -> assertion "lock must be free" SATISFIED (test GREEN)
```

That is the property a regression test needs and did not have: it fails on the
defect and passes on the fix, on identical fixture bytes.

## Focused gate

```
python tools/core_unit.py focused T-1890 --pattern test_t1827_writer_lock_contract.py
{"verdict": "PASS", "ran": 19, "reused": false,
 "record": ".saipen/evidence/focused-unit/ab23d73353762d5d-20261024T181840713153Z.json"}
sha256 b8f5f7412654fe71a2bad0850380ff35ec54d1fcedab9decd9342744021d8509
```

19 tests, the whole module, green — it was 18/19 with one error before this
change.

## Ownership note

This file is **staged and not in HEAD** (blob `5b7c1c76`), i.e. another actor's
unpublished work. The working tree was byte-identical to the index before this
edit, so the change adds a new divergence on top of their staged bytes rather
than discarding any: nothing was unstaged, reverted or overwritten, and the
three-line fixture call is the whole delta. INV-09 is respected — I did not
replace their content, I extended the one call that could never have worked.
Whoever publishes the batch should review this hunk alongside their own.

What is NOT claimed: the module's other 18 tests were already green and are not
evidence for this fix; the full family is not green (the 55 baseline reds are
untouched); and this does not itself fix the gate — T-1886 did, and this ticket
supplies the oracle that would have caught it.

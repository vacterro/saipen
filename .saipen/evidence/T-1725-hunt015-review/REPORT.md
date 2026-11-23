# T-1725 — Core review of SubSaipen hypothesis `saihunt/HUNT-015`

Package: `package_identity=sha256:8223117b28c87819a2dcebfe173f9ec3baa40a50c39cb1f5aa54d51ec1773657`,
producer `saihunt`, source_head `025bf596`, role_revision
`sha256:4edb0418…`. Disposition only — no package patch applied at intake.

## Method

Re-measured the two signals read-only against the live tree with the engine's
own resolver and a plain reference census (`grep -rn`, excluding
`__pycache__`), independent of the package text. Line numbers are re-read from
the current bytes, so a drifted citation is visible rather than inherited.

## Finding 1 — the HUNT-013/HUNT-014 reachability claim is RETIRED: **CONFIRMED**

The earlier package claimed no shipped path could write the `crew_run` and
`producer_integration` receipts the crew circuit demands. Both halves are now
reachable in the shipped tree:

- `crew_run` — `tools/saipen_engine/crew.py:1464` defines `crew_record_run`,
  imports `record_crew_run` at `crew.py:1482`, and calls it at `crew.py:1529`;
  the canonical writer is `tools/saipen_engine/operations.py:12184`. The fix is
  tracked and closed: `[x] T-1430` on the BOARD.
- `producer_integration` — the shipped writer is
  `tools/saipen_engine/producer.py:2155`
  (`run_mutation(..., "producer_integration", ...)`), reached from
  `tools/saipen_engine/intent.py:336` `_integrate_producer`, whose only call
  site is `intent.py:1343`. Not the `operations.py` helper.

`report_producer_integration`/reachability is therefore genuinely
NOT_REPRODUCED. The package's own verdict stands.

## Finding 2 — orphaned writer pair in `operations.py`: **CONFIRMED**

Reference census over `tools/` (excluding `__pycache__`):

```
tools/saipen_engine/operations.py:12218  def _plan_producer_integration(
tools/saipen_engine/operations.py:12312  def record_producer_integration(
tools/saipen_engine/operations.py:12329      plan = _plan_producer_integration(   # inside 12312
```

- `record_producer_integration` (:12312) is referenced exactly ONCE in `tools/`
  — its own definition. It has NO caller.
- `_plan_producer_integration` (:12218) is referenced twice — its definition and
  the single call at :12329 that sits INSIDE the dead function above. It has no
  live caller either.

So two writers exist for one receipt class: one live
(`producer.py:2155`, the S0→S1 edge the crew consumes) and one inert
(`operations.py:12312`). The drift risk the package names is real: the inert
helper can rot against `producer.py`'s binding scheme with nothing failing.

Dynamic construction is excluded by the same census: the only
`getattr(operations, ...)` in `tools/` is
`tools/test_generation_migration.py:58`, and it names
`migrate_saipen_generation`, never the suspect. Positive control: the SAME
method finds the live sibling `record_crew_run` in 3 files
(`crew.py`, `operations.py`, `test_t1430_crew_run_receipt.py`), so the zero on
the suspect is a measurement, not a blind spot.

## Disposition

- Finding 1: **ACCEPTED (retirement)** — no action; the reachability premise is
  genuinely dead at this HEAD and the package already retired it.
- Finding 2: **ACCEPTED (orphan pair is real dead code)** — but a change here is
  a REMOVAL of production code that no test, registry or doc pins, so it is its
  own bounded Work, not a by-product of this intake. Recorded as a cleanup
  candidate; no package patch applied during intake (per T-1725's verify
  clause).

## Limits

Read-only review. No package patch, no source rewrite, no crew epoch mutation.
The orphan pair is left in place with its evidence recorded here.

# T-1579 core-unit red analysis (2026-10-01)

The first full family carrier
`.saipen/evidence/core-unit/7621521d20d8a7c5-20261001T083313Z.json`
ran 4,509 tests with 18 new reds. Its bound red sections identify two
causes:

- Sixteen storage tests constructed mock durable state below their module
  `ROOT`. Core-unit runs its isolated copies below `V:/_TEMP_`, so the new
  storage guard correctly rejected those paths as disposable.
- Two source-quarantine preflight tests supplied a `SimpleNamespace` release
  plan without the `mode` and `crew_closure` fields required by the existing
  `ReleasePlan` and T-1570's `_plan_publishes` decision.

The storage fixtures now create and clean their mock durable roots below
`Path.home()`, outside the OS temporary root. The preflight fixture now supplies
`mode="full"` and `crew_closure=False`. The three affected test modules ran
separately on the current tree: 10 storage-policy tests (one host symlink
privilege skip), 14 storage-artifact tests and 8 source-quarantine tests, all
other tests passing. A new full-family carrier is running; focused results do
not establish its verdict.

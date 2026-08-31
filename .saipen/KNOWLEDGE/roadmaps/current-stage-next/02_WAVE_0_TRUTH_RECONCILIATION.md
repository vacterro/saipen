# 02 — WAVE 0: TRUTH RECONCILIATION / BASELINE REPAIR

## Goal

Make current canonical project truth describe the implementation that actually exists.

No new large feature work in this wave.

## W0.1 — Reproduce all current gates

Run from the supplied tree:

- core validator;
- protocol budget;
- conformance corpus tests;
- registry tests;
- command routing tests;
- continue/improve tests;
- relevant unit suite.

Record exact current results.

## W0.2 — Repair the three current validator failures

### LOG parent continuity

Resolve the dangling parent through the canonical recovery/history contract.

Do not rewrite arbitrary historical lines without recovery evidence.

### Historical Improve linkage

For each CONFIRMED historical Improve finding:

- identify whether canonical Work already exists under another ID;
- if yes, add truthful linkage;
- if not, create or disposition through the supported legacy reconciliation path.

Do not fabricate tickets just to satisfy a parser.

### `_AUDAPACK_MANIFEST.json`

Treat as packaging/transport metadata.

It must not redefine the repository root set.

Prefer correcting package placement/exclusion.

## W0.3 — Reconcile duplicate W4 Work

Map `T-1212..T-1221` against `audit/1.md` clauses and current implementation.

For each old ticket:

- DONE if already proven;
- SUPERSEDED/MERGED if its semantics are now owned by T-1222/source coverage;
- remain TODO only if genuinely unfinished.

Do not keep two live Work items for one requirement.

## W0.4 — Reconcile T-1222 coverage

Ensure `SRC-012` or the actual source receipt bound to `audit/1.md` has requirement-level coverage reflecting current implementation.

No blanket "done."

Every actionable clause should have a terminal or remaining state.

## W0.5 — Fresh-checkout proof

The reconciled commit must reproduce:

- validator green;
- no transport artifacts at root;
- no dangling source/Work references;
- current Work and STATE consistent.

## Completion bar

1. Core validator green.
2. Duplicate W4 tickets reconciled.
3. T-1222 coverage reflects reality.
4. Current STATE points to real next action.
5. Fresh checkout reproduces green.
6. No feature code added merely to make bookkeeping pass.

Stop.

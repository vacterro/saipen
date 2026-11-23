# T-1734: read-only source-drift advisory for closed Work

Origin: SRC-231 item 8 (the bounded follow-up from the FastPrompter forensic
mission, T-1733) where T-1450 was DONE with no binding between its closure and
the verified production bytes.

## What was missing

A DONE Work can close citing a core-unit family record; that record's
`fingerprint` is a content digest of the source tree the family tested, and it
is the only durable source binding a closure carries. Nothing re-read it after
closure, so the tree could drift away from the verified bytes with no signal.
Historical closure and current product acceptance are different claims.

## Change

- New `tools/saipen_engine/source_binding.py` — `advisory(root)`, read-only:
  - only runs when the project declares the family (`core_unit.declared`);
  - reads the LOG via `read_history_events` and, per DONE ticket, takes the
    newest `CORE-UNIT-EVIDENCE` citation (`core_unit.parse_evidence`) and the
    record's `fingerprint`;
  - compares it to `core_unit.tree_fingerprint(root)` now;
  - returns `CURRENT` / `DRIFTED` / `UNBOUND` per Work, plus `drifted`,
    `unbound`, `drifted_count`, `unbound_count`, `current_fingerprint`;
  - writes nothing, re-runs no family, rewrites no LOG line.
- `tools/saipen.py` `status --json` gains a bounded `source_drift` block beside
  `closed_contracts`, in a try/except that reports a `source_drift_error`
  condition instead of hiding it. It is advisory: never a gate.

No protocol markdown changed (route budgets untouched). `saipen work reverify`
remains the manual remedy and is unchanged.

## Verification

- `tools/test_t1734_source_drift.py` — 5 focused cases: CURRENT when the tree
  matches, DRIFTED when it changed, UNBOUND when no citation exists, silent {}
  when the family is undeclared, and read-only (byte-for-byte no mutation).
- Neighboring suites: `test_response_surface_contract`, `test_t1732_protocol_hardening`,
  `test_continue_entry`, `test_command_routing`, `test_t1726_closed_contracts`,
  `test_t1645_zero_hunt` — 174 ran, 0 failures.
- Live `saipen status --json` emits `source_drift`; on this repository it
  truthfully reports the drift in the working tree (older closures cited
  build-time fingerprints the tree has since moved past) and the unbound
  closures that cite no family run — the same shape as the FastPrompter T-1450
  finding, now observed instead of silent.

## Boundaries (non-goals honored)

Advisory only; no closure is reopened, no LOG/STATE/BOARD rewritten, no source
replaced, no gate added, no publication.

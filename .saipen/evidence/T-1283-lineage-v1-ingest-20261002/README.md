# T-1283 — v2 lineage crashed on any population holding a v1 receipt

Ticket: T-1283 [P2] Receipt storage is O(N) in lifetime volume on the read path and
O(N squared) cumulatively on the append path, and the project has already crossed into
multi-second routine...
Board line: 2, state `[/]` (DOING), owner `saipen-cli`, claimed 2026-10-02T15:46:59Z.
Closure mode: `own_patch`.

## What the ticket claimed, and what was actually true

The ticket text said the settlement-time bootstrap "RUNS and succeeds and the index
it writes still fails validation immediately". That is not what happens. The bootstrap
never returns at all.

`tools/saipen_engine/conformance.py`:

- line 566 `_atomic_write_receipt` writes the receipt bytes to disk, and they are durable.
- line 568 `_update_receipt_index` is called **after** that write.
- `conformance.py:817` delegates to `advance_append` when the freshness token is present.
- `advance_append` finds no head, calls `rebuild_lineage` (`conformance_lineage.py:496`).
- `rebuild_lineage` calls `_scan_receipt_members` (`conformance_lineage.py:359`).
- `_scan_receipt_members` evaluated `record["receipt_id"]` (`conformance_lineage.py:363`).
- `advance_append` catches only `(ValueError, OSError)`, so the `KeyError` escaped a
  durable-write path.

`ReceiptDiscoveryError` is a `ValueError`, so the existing catch was already sound for
every refusal the engine raises deliberately. `KeyError` was the one uncovered case.

Three receipts in the live population carry `schema_version: 1`, and
`_RECEIPT_REQUIRED_FIELDS_V1` deliberately omits `receipt_id`. The newest receipt in
`.saipen/recovery/conformance` is dated 2026-10-02T18:37; the v2 lineage wiring landed
2026-09-09. Every conformance receipt write in that window has raised out of
`generate_conformance_receipt` after its bytes were already on disk. That is the whole
reason the v1 index is frozen at `receipt_count: 1194` against a population of 2750, and
the reason `latest_receipt` decodes 2753 files per lookup.

## The design question, settled by the engine's own grammar

`_iter_receipts` accepts all 2750 receipts, including the 3 with no id of their own. The
canonical scan the lineage exists to accelerate was therefore strictly **more** permissive
than the lineage. The fix is not to narrow the scan; it is to make lineage membership
**total over the population the engine already accepts**.

A v1 member takes a content-addressed identity derived from the exact bytes it already
binds: `legacy-<sha256[:32]>`.

- deterministic: the same bytes always give the same id, so rebuild is idempotent.
- collision-free against a real W2-005 id: the `legacy-` prefix is outside the
  issued-id namespace, which is `receipt-<12 hex>`.
- authority unchanged: `content_sha256` is still the exact written bytes, which is what
  every lookup re-verifies. The derived id is an index key, never a trust input.

## The change

`tools/saipen_engine/conformance_lineage.py`, one new helper plus two call sites:

- `_member_receipt_id(record, content_sha256)` at line 67.
- `_scan_receipt_members` line 364, and `validate_lineage_deep` line 821.

Deliberately NOT changed: `advance_append`'s `except (ValueError, OSError): return False`.
Widening it to swallow `KeyError` would mask the next bug of the same kind. The defect
is fixed at source, where the id is derived.

## The check

`tools/test_t1283_lineage_legacy_ingest.py`, 12 tests, all passing. It counts file
reads; it never asserts on a clock.

## Acceptance criteria

### AC-01 — a settlement leaves an index that validates on the next read
Already delivered by **T-1519** (BOARD line 106, `closure_mode: own_patch`, DONE). The
settlement-time bootstrap runs and the index it writes validates immediately. This ticket
did not re-deliver it; it is a `needs: T-1519` slice and that slice is closed.

### AC-02 — an operation-specific query consults index/segment offsets, no full semantic snapshot
Green before and after this change. `latest_receipt` tries `latest_receipt_bounded`
first, which reads the per-gate locator and the single generation the locator names.

### AC-03 — latest_receipt validates against a compact generation; per-receipt count stops scaling
Measured against the real 2750-receipt population in `.saipen/recovery/conformance`:

| | decodes | wall |
|---|---|---|
| strict scan (pre-fix path) | 2754 | 1.60 s |
| bounded lineage (post-fix) | 0 | 0.0018 s |

The bounded result was checked for equality against a pure strict scan at the same tree
state: both return `receipt-2dd7c77e4aba`.

`test_bounded_lookup_does_not_scale_with_the_population` proves the same property by count
against a synthetic population, so it cannot pass by accident on a fast machine.

### AC-04 — an append inside the active segment does not re-hash sealed generations
Five appends, population 2752 → 2757:

```
receipt_files_read   65 -> 69      (tracks the active tail, capped at GEN_BOUND=128)
sealed_gens_read     ['gen-0020.json']   (exactly one, every time)
active_gens_read     1
```

### AC-05 — exact-byte receipt evidence stays authoritative; deep audit remains reachable
`validate_lineage_deep` runs green over the real population. The red control rewrites a
receipt as **valid JSON** with one field changed (`verdict` flipped), so the parse gate
still passes and only the digest authority is under test. The audit answers
`"receipt bytes disagree with lineage"`.

### AC-06 — red controls prove each new bound can go red
Four independent controls, all in the suite:

- `test_v1_receipt_is_accepted_by_the_canonical_scan` — the premise. If the engine ever
  stops admitting v1 receipts the ticket is moot.
- `test_out_of_band_sibling_is_degraded_never_laundered` — an out-of-band file moves the
  directory mtime; the bounded path must REFUSE and fall back, never serve an
  unauthenticated record.
- `test_tampered_referenced_generation_degrades` — corrupts the generation the locator
  actually references (an earlier attempt of mine aimed at a sealed generation the
  locator never names, which is why it wrongly read green).
- `test_foreign_object_is_refused_fail_closed` — a foreign object **raises**
  `ReceiptDiscoveryError` rather than being skipped into a partial membership. The raise
  is the refusal; the pre-existing authority is left untouched and still serves.

## The decisive red control

`.git/redctl.py` runs in one process: textually revert both fix sites, run the suite,
restore, rerun. Output in `.git/redctl.txt`.

```
PRE-FIX  exit code = 1
         FAILED (errors=10)   all KeyError: 'receipt_id'
RESTORED: True
POST-FIX exit code = 0
         Ran 12 tests ... OK
```

The tree was restored byte-identical. Note the shape: 10 errors, 0 failures. The pre-fix
code does not compute a wrong answer, it raises, which is why the ticket looked like a
stale index rather than a crash.

Four of my own controls were wrong before they were right, and each is corrected above:
the AC-04 read count (first included module-import noise), the AC-05 byte control (first
replaced the last byte, producing a parse error instead of a digest disagreement), the
AC-06(b) target (a sealed generation nothing references), and the AC-03 equivalence
control (compared across an append that legitimately changed the latest).

## Gate

- `ruff check` on both files: clean.
- `python -m unittest tools.test_t1283_lineage_legacy_ingest`: 12/12 OK, 1.220 s.
- Declared core-unit family: `python tools/core_unit.py evidence T-1283`, recorded in
  `family.json`. Baseline `tools/core_unit_baseline.json` has `red: []`, so any red in the
  result is a NEW red and blocks SHIP.

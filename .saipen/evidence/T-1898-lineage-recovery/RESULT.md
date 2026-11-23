# T-1898 — a frozen lineage head never recovered itself

## What was measured

The v2 conformance lineage head on this repository:

```
head receipt_count      3669
receipt namespace       3936 files
head mtime token        eight days older than the receipt directory
```

Detection was working. `advance_append` refused, `latest_receipt_bounded`
returned `(True, None)`, and `conformance.latest_receipt` degraded to
`_receipt_content_inventory` — a hash of every receipt in the namespace.
Nothing recovered the head, and no field anywhere reported the bounded path as
broken, so the cost was paid forever and invisibly.

| | frozen head (before) | repaired head (after) |
|---|---|---|
| `latest_receipt_bounded` | `(True, None)` — refuse | a record |
| `conformance.latest_receipt` path | strict scan + content inventory | bounded lookup |
| full-namespace content hash | **1.49 s** (3937 files, 8.6 MB) | not paid |
| `latest_receipt` wall time | **1.49 s** | **0.002 s** |

Measured on the live tree (`measure.json`, `python -m unittest` free, direct
function timing, best of 3–5 runs).

## The defect

Two halves, and only the first existed:

1. **Refuse** — `advance_append` must never adopt a receipt the lineage was not
   told about. That is correct and stays; the existing lineage tests pin it.
2. **Recover** — nothing ran when a head was *already* stale.
   `rebuild_lineage` was the canonical repair and had **zero callers** outside
   tests and no CLI route. So one out-of-band receipt, or one crash between
   the receipt write and the head publish, froze the fast path for the
   remaining lifetime of the project.

The measured consequence on this tree was 8 days of degradation: every
`saipen status` and every `continue` hashed 37 MB of receipt bytes it did not
need.

## Where the repair lives, and why

`saipen/COMMANDS_REFERENCE.md:50` documents `saipen status` as **read-only**.
The first implementation repaired the head from `latest_receipt_bounded` — a
write on a documented read path. That was wrong on contract, so it was
reverted and the repair moved to the writer:

- `conformance_lineage.latest_receipt_bounded` — **unchanged behaviour**: on a
  stale token it returns `(True, None)` and the caller degrades to the strict
  scan. It never mutates. Pinned by
  `test_the_read_path_stays_read_only`, which snapshots every byte of the
  project before and after a read.
- `conformance_lineage.repair_stale_head(root)` — the canonical deep rebuild.
  Returns False when no v2 authority can be published (corrupt sibling, no
  head); returns True without a rebuild when the head is already current
  (measured 0.34 ms), so a healthy append pays one stat.
- `conformance._update_receipt_index` — the writer path. It is already
  publishing projection documents and already holds a pre-append token, so
  after `advance_append` refuses it runs the rebuild. A rebuild it cannot
  publish writes nothing, exactly like the old refusal.

`repair_stale_head` takes the project writer lock itself. `rebuild_lineage`
requires it, and `project_writer_lock` is **not reentrant** — but a
same-process second acquisition refuses immediately with `WriterBusy` rather
than blocking, so a caller that already holds the lock gets `False`, never a
deadlock (the same pattern `debt.py` documents for `_create_snapshot_apply`).

## The test that changed, and why

`test_out_of_band_sibling_refuses_advance_and_never_becomes_indexed` asserted
that both the head and the locator stay byte-identical after a foreign
sibling — i.e. it pinned the permanent freeze as a requirement. It is renamed
and rewritten to
`test_out_of_band_sibling_is_folded_truthfully_by_the_writer_rebuild`, which
pins the property that actually matters: the **writer's own receipt is never
advertised as latest** across a foreign sibling, the locator names the true
latest (`out-of-band`), the head's population is the true 5, and both the
strict and the bounded lookup answer the same receipt.

## Red/green control

`test_t1898_lineage_recovery.py` run against two trees with the same test file:

```
PREFIX (git archive HEAD)   1 failure + 1 error
  test_the_writer_path_repairs_the_head_and_restores_the_bounded_path  FAIL
  test_a_current_head_costs_one_stat_not_a_rebuild  AttributeError
POSTFIX (working tree)      5 tests, OK
```

`prefix-red-control.log` and `postfix-green-control.log` hold the verbatim
output. The two tests that pass on both trees are the *detection* and
*read-only* halves; they pass before and after, which is what makes the two
red ones specifically about the recovery.

## Verification

- `tools/test_t1898_lineage_recovery.py`: **5 passed** (0.09 s).
- `tools/test_conformance_lineage.py`: **22 passed** (70.9 s, includes the
  10 000-receipt bounded-cost controls).
- `tools/test_t1283_lineage_legacy_ingest.py` +
  `test_audit_2026_08_28_all3.CoreConformanceAppendRaceTests`: **15 passed**.
- Wider conformance family (`test_conformance_corpus`,
  `test_conformance_projection`, `test_conformance_remediation_evidence`,
  `test_conformance_repair_boundary`, `test_t1412_conformance_truth`):
  **51 passed** (74.8 s).

## What this does NOT claim

- It does not reduce `saipen status` from 12 s to anything small. The measured
  components are dominated by `convergence_verdict` (3.6 s over 16 275 settled
  receipts), `compute_source_identity` (3.3 s) and `conformance_decision`
  (2.3 s). This ticket removes **one** of those costs — 1.49 s of unnecessary
  content hashing — and restores the mechanism that was supposed to prevent
  it. End-to-end `status` measured 11.2–12.2 s over three runs; that is a
  partial number, not a headline.
- It does not make the bounded path do corruption detection. `convergence_verdict`
  still scans the full settled history because that is its corruption input
  (INV-13); that is a separate, larger change.
- It does not add a CLI route. The repair runs where a writer already is, which
  is what keeps `status` honest. A forensic deep rebuild stays available
  through `conformance_lineage.validate_lineage_deep` for tests and recovery
  work.

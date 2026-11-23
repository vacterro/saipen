# T-1903 — stop paying for the receipt projection the router discards

## What was slow, measured

`continue` spends its time in `_next_action`, and inside it
`queued_source_projection` walks every active Source receipt to find the oldest
unprojected explicit operator request. On the live project that is 195 active
receipts.

That walk iterated `intake.active_receipts(project_root)`, the FULL projection.
For every receipt the full form computes:

    _read_meta                        (needed)
    coverage_summary                0.122 s total over 195
    _distribution_projection        0.203 s total over 195
    -------------------------------------------------
    active_receipts(root)           0.450–0.516 s

`queued_source_projection` reads exactly one key from each item -- `receipt` --
and then re-reads that candidate's metadata itself for `linked_work` and
`source_kind`. Both expensive fields were computed for all 195 receipts and
discarded on every routing pass.

The docstring on `active_receipts` claimed "index + metadata only", which was
already untrue before this ticket; that sentence is now corrected rather than
left as a false contract.

## What changed

`active_receipts` gained `coverage: bool = True`. With `coverage=False` it
returns identity and membership only:

    {"receipt": ..., "source_sha256": ..., "linked_work": ...}

**The default is still `True`.** This adds a cheaper projection; it does not
remove a field from the expensive one, so `context.py`, `readiness.py`,
`source_append.py` and the intake self-read all keep exactly the dicts they
had, key set included.

`queued_source_projection` now asks for `coverage=False`, with a comment saying
what it reads and why the rest was waste.

Every safety property of the walk is untouched, because the cheap form still
goes through the same code: `_read_index`, the `_valid_receipt_id` check, the
per-receipt `_read_meta`, and the index-metadata-drift comparison all run in
both modes. What is skipped is only the coverage ledger read and the
distribution projection.

## Measured result

In the `continue --json` profile, `queued_source_projection` fell from
**0.713 s to 0.297 s** (−58 %). In isolation on the live tree, with the same
195 receipts:

| | wall |
| --- | --- |
| `active_receipts(root)` | 0.516 s |
| `active_receipts(root, coverage=False)` | 0.126 s |
| saved per routing pass | 0.391 s |

Honest note on the end-to-end number: `continue` wall time did **not** drop
measurably across five runs (median 3.045 s after, versus 2.93 s in an earlier
sample on a busy machine). The projection saving is real and shows up in the
profile, but the command is now dominated by `reconcile_protocol_state`
(1.97 s) and two full `read_history_snapshot` passes (0.74 s). Those are the
actual remaining hot path, and they are not this ticket's subject. Quoting the
projection's 0.39 s as a command-level win would be dishonest, so it is stated
as a component win only.

## Verification

    python -B tools/core_unit.py focused T-1903 \
      --pattern test_t1903_lean_receipt_projection.py \
      --pattern test_source_receipts.py \
      --pattern test_source_multiwork.py \
      --pattern test_command_routing.py --timeout 300
    # PASS, 249 ran, 210.031 s
    # record: .saipen/evidence/focused-unit/bd594eecc9dcd39a-20261025T043950401606Z.json

The new file pins five behaviours, with no timing assertion anywhere:

- lean and full agree on receipt order and on `linked_work`/`source_sha256`;
- `work=` filtering still narrows in lean mode;
- the lean dicts do not fabricate coverage fields -- a caller reading
  `item["requirements"]` gets a `KeyError`, never a silent zero that would read
  as "this receipt has no requirements";
- the default projection still carries `requirements`, `terminal`,
  `unresolved`, `distribution`;
- index metadata drift still raises in BOTH modes, so "cheaper" did not become
  "less careful".

## Honest limits

- This is a component win, not a command-level one. The routing pass still
  walks 195 receipts and re-reads each candidate's metadata; that second read
  is a deliberate design choice (the queue asks the same owner that
  `start --receipt` asks) and was not removed.
- `_restored_detail_text` runs 18 093 times per history snapshot to restore 554
  compacted events, and a snapshot is taken twice per `continue`. That is the
  next measurable target, and it is a separate ticket: 0.239 s of the 0.414 s
  snapshot is 554 detail-file reads, each re-validating digest and lineage on
  purpose. Making that cheaper means proving a within-pass memo cannot hide
  tampering, which is exactly the kind of change that needs its own evidence.
- `reconcile_protocol_state` at 1.97 s inside `_next_action` is larger than
  either of the two wins above. Nothing was done to it here.

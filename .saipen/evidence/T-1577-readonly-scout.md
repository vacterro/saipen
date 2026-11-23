# T-1577 — read-only scout (2026-09-30, no production bytes touched)

Produced during T-1578's full core gate, through the T-1575 parallel lane. No
claim was taken, no production file was edited.

## 1. The canonical op-id grammar owner

Two distinct owners, and the ticket must not add a third:

- `tools/saipen_engine/journal.py:374 validate_op_id` -> `safeid.validate_safe_id`.
  This is the single path-component grammar (no `..`, no separators, safe id).
  It governs op DIRECTORIES, not the `[op: ...]` LOG tag.
- `tools/saipen_engine/journal.py:415 resolvable_op_ids(root)`. This is the single
  provenance owner of the `[op: ...]` tag: an id is canonical when it resolves to
  a real operation record on this checkout (live dirs, settled dirs, settled index).
  `tools/validate.py:3546-3577` is its only non-test consumer.

## 2. Every registered op class — there is no registry today

Ids are `<class>-<uuid4 hex>` produced by callers, not by one grammar function:

- `operations.py:99` `uuid.uuid4().hex` (32 hex) for the canonical writer.
- Prefixes seen in LOG/`: claim-, transition-, checkpoint-, ticket-, finish-,
  recover-, converge_intent-, undo-, refine-, reload-, sub-sync-, sub-spawn-,
  sub-adopt-, sub-pause-, receipt-` (subs.py:2312/2687/2859/2991 truncate the
  hex to 8; conformance.py:213 truncates to 12).

So "registered op class" is currently implicit and scattered. T-1577 needs ONE
registry; it does not exist to be reused.

## 3. Active-log FAIL vs sealed-history WARN boundary

`tools/validate.py:3559-3575` (the T-1282 `[saio]` gate) already draws exactly the
boundary T-1577 needs:

- `_resolved_floor` = the newest event whose op id IS in the ledger.
- Only events ABOVE the floor are FAILed; older ones are exempt "exactly like a
  sealed segment".
- No ledger on the checkout => UNAVAILABLE, never red (fresh clone).

T-1577 should reuse this floor; a new boundary would double-report the same
class of finding.

## 4. Where phase/closure evidence filters consume op ids

- `tools/saipen_engine/log.py:58` is the only producer of `op_id` on an event.
- `verification_evidence`, `_is_verify_boundary`, `_is_regression_evidence` and
  the finish-provenance gate all read `event["text"]` / `taxonomy`, never `op_id`.
  Consequence: today a hand-authored `verify -> PASS ... conf: high` line IS phase
  evidence regardless of its op id. That is the ticket's real exposure.
- `tools/validate.py:3553` and `resolvable_op_ids` are the only op-id consumers.

## 5. Prepared RED carrier shape

AUDAPACK-shaped active LOG above the floor with hand-minted ids:

    - ... [E-101] [T-261] [agent: auda] [op: scout-<31 hex>]  RUN: transition to SCOUT
    - ... [E-102] [T-261] [agent: auda] [op: build-<31 hex>]  RUN: transition to BUILD
    - ... [E-103] [T-261] [agent: auda] [op: verify-<31 hex>] RUN: verify -> PASS ... conf: high

Expected pre-fix: the validator accepts all three as ordinary structural events,
and `verification_evidence` treats E-103 as a real VERIFY PASS.
Expected post-fix: each is named as hand-authored external mutation (FAIL in the
active log, WARN below the floor / inside a sealed segment), and no phase or
closure evidence is derived from any of them.

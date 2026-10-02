# T-1587 — producing-path hunt (handoff section 8)

Question: can a CURRENT canonical operation write a closure-contract field
onto a row that does not sit under `## DONE`?

## Inventory (current tree, 01.10.26)

Writers that PUT closure fields on a row (all in `tools/saipen_engine/operations.py`):

| site | operation | target row |
|---|---|---|
| 4013/4023 `_close_ticket` | finish / cohort close | the row being moved INTO `## DONE` in the same proposal (3762, 10374, 10510) |
| 4293-4306 | `ticket supersede` (`superseded_by` triple) | old ticket moved INTO `## DONE` in the same proposal |
| 4660-4673 | `ticket resolve-external` | ticket moved INTO `## DONE` in the same proposal |

Writers that MOVE a row OUT of a section:

| site | operation | from -> to | closure risk |
|---|---|---|---|
| reconcile `_apply_lifecycle_repairs` (CURRENT_DONE_JOURNAL_GAP, T-1572) | recovery reopen | `## DONE` -> `## DOING` | strips `CLOSURE_METADATA_FIELDS` via `_reopen_field_removals` — the ONE canonical DONE exit |
| reconcile `_board_lifecycle_repairs` (unstarted DOING) | recovery | `## DOING` -> `## TODO` | DOING rows cannot legally carry closure fields |
| operations 2744/2754 (T-1473 handback) | unblock handback | live `## DOING` -> `## TODO` (demote), parked -> `## DOING` | demoted row is DOING; parked row is `## BLOCKED` (`continuation_parent`, board.py:1360, returns BLOCKED parents only) |
| operations 3052 | `block` / `block-for` | refuses any source other than `## DOING` / `## TODO` (2941) | neither source section may carry closure fields |
| operations 3774, 5699 | finish / retire with parent resume | `## BLOCKED` parent -> `## DOING` | source is BLOCKED (`continuation_parent`) |

## Conclusion

No current canonical operation can produce the FastPrompter shape. Closure
fields are written only by the close family onto rows simultaneously moved
into `## DONE`, and the only canonical exit from `## DONE` (the T-1572 gap
reopen) strips exactly the closure vocabulary. The movers that leave DOING or
BLOCKED operate on sections whose rows cannot legally carry closure metadata
in the first place.

The reported row (`| closure_mode: own_patch` under `## TODO`, T-1371) carries
`own_patch`, the value every canonical finish writes by default — consistent
with a hand-authored or externally-projected row (a re-added TODO line written
from a closed row's bytes, or an older-generation/manual mutation). Per the
handoff this is recorded honestly, not invented: provenance beyond the bytes
is not provable from here, and recovery must handle the defect regardless of
its producer because the field defect is deterministic.

Guard added so this stays true: `ProducingPathTests` (in
`tools/test_t1587_stale_closure_recovery.py`) pins that the reopen strip set
equals `board.CLOSURE_METADATA_FIELDS`, so a NEW closure field cannot be added
to the vocabulary without also entering the reopen strip set.

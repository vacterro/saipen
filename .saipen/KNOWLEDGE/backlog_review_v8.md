# Backlog review after DOGFOOD V (T-614, 2026-08-10)

Every remaining open ticket was reviewed with current evidence after the
DOGFOOD V provenance wave shipped. Dispositions:

| Ticket | Status | Disposition |
|---|---|---|
| T-613 | TODO, needs T-614 | next wave: v8 evaluation from the repaired foundation (see below) |
| T-473 | HELD, needs T-442 | keep held -- Rosary A3 collision guard belongs to the Crew/concurrency design; do not pre-empt T-442..T-451 |
| T-609 | BLOCKED (producer) | keep honestly blocked -- the saiwiki producer must regenerate OUTBOX W-031 against the current HEAD + tree fingerprint; Core cannot fabricate producer evidence (SAIPEN protocol, directive note) |
| T-576 | BLOCKED (human) | keep blocked -- deletion of the orphaned recovery scripts requires an explicit human decision; untouched |
| T-407 | BLOCKED (permanent warning owner) | keep -- `goal-reauth-untripped` still emits (immutable E-1659); ownership ticket stays while the slug warns |
| T-406 | BLOCKED (permanent warning owner) | keep -- `subsaipen-never-ran` still emits; ownership ticket stays while the slug warns |
| T-442 | BLOCKED (v8 gate) | keep gated -- v8 Concurrent Mode must not start while any foundational defect is open; the DOGFOOD V wave closed the Improve provenance P0/P1s, and one ordinary sequential release (the dogfood V wave itself) completed without a new foundational defect, but the gate decision belongs to T-613's evaluation with fresh gates |
| T-575 | BLOCKED (v9 gate) | keep gated -- v9 requires ACTUAL v8 to exist and be stable; research/prototypes only |

T-464 (board-soft-cap owner) was closed on current evidence in the same pass:
the board was pruned to 12.7 KB and the warning stopped emitting, so the
permanent-warning-owner premise expired.

Conclusion: the board is honest. Nothing to advance, nothing to prune beyond
the DONE-body compaction already done. The only real next work is T-613 (v8
evaluation), which now has its dependency satisfied (T-614 done).

# W6-W9: bounded reads, engine reuse and evidence processing

CURRENT UPDATE: POST-FULL1-CORRECTION.md supersedes the final-verification
position below. Full run 1 failed; all 75 prior red IDs and 90 scoped contract
tests now pass; full run 2 is pending. The 20/8 import observation remains
evidence for its original consolidation generation, not a fresh byte benchmark.

STATUS: Scoped local improvements verified; full-family run pending. No campaign
completion, storage migration or publication claim.

## Context read correction

ROOT CAUSE: orientation capped the complete STATE file at 8192 bytes although
the canonical STATE parser stops at its first closing frontmatter fence.
FastPrompter's approximately 20KB historical Markdown body therefore hid a
small valid current header. No header or historical data needed deletion.

CHANGED COMPONENT: cold_truth's STATE reader reuses bounded prefix IO, accepts
only a complete terminated fence, then uses the same strict state parser.
It reports state_body_omitted, preserves the 8192/65536 limits, and remains
read-only. Small-file behavior is retained. Prefix short-read races refuse.
Duplicate authority fields and a closing-fence fragment at the cap cannot pass.

BEFORE/AFTER: real FastPrompter orientation changed from
READ_ONLY_DIAGNOSIS_ONLY (whole-file oversize) to COLD_ORIENTATION, with 8192
STATE bytes and 57344 total declared input bytes. No state rewrite or budget
increase occurred. This is availability/bounded processing evidence, not a
claim that a formerly successful 20KB read became faster.

VERIFICATION: frozen control failed on the old reader; 21 complete cold-agent
tests passed afterward, including malformed and multibyte boundary controls.
SEMANTIC PARITY: the complete authoritative header is parsed identically;
only non-authoritative historical body is omitted from the read-only projection.
SAFETY: all mutation admission and Source/handoff authority checks remain due.

## Cohesive engine consolidation

ROOT CAUSE: equivalent goal-budget thresholds and their values were repeated
in operations, reconciliation, entry, router, CLI, state proof and status.
Read-only state proof imported the complete mutation engine just for two caps.

CHANGED COMPONENTS: one registry fact (3 waves / 20 tickets), one goal-authority
predicate, and existing compatibility exports. The one-axis counter-update
logic, full proof reconstruction and independent authority decision were not
collapsed into a generic helper because they answer different questions.

BEFORE/AFTER: a fresh-process fixed proof loaded 20 engine modules representing
1,318,131 source bytes before, versus 8 / 254,294 afterward. The latter is
80.7% smaller for THIS import surface. The fixed input's proof remains true.
The recorded elapsed samples (about 45 ms / 25 ms) are individual observations,
not a comparable whole-engine performance campaign or global speed percentage.

VERIFICATION: import-cost oracle red/green, 48 input boundaries preserve results,
public operations cap exports unchanged, 80 related tests green. Native
origin/goal/budget proof remains the authority gate, not this predicate.

## Other named engine boundaries retained

| Owner | Inspected responsibility | Decision |
|---|---|---|
| operations | immutable PLAN/APPLY, under-lock readback, claim and phase counters | retain temporal revalidation; centralize only equivalent budget policy |
| intake | exact body/contract integrity and work_closure_gate | retain full linked-receipt closure; do not fake partial Source completion |
| journal | exact prepared bytes, before/after hashes, roll-forward conflicts | retain distinct preflight and post-write checks; no opaque transaction abstraction |
| release | NUL-safe staged paths, reviewed scope, yielded-gate revalidation, intended-tree journal | retain correct foreign-index refusal; isolated Git feasibility does not replace this contract |
| subs | one manifest parser, producer epoch and Core-only disposition | retain source/role isolation and intake-versus-review distinction |
| reconcile | one proposed-surface plan and evidence-derived counters | retain proposal/commit consistency; derive cap values from one owner |
| board/router | one pick rule and shared idle/blocker projection | audit/status reuse its classification; independent work still wins |
| continue_loop | closed bounded auto-execution vocabulary, fixed-point proof | retain model-judgment boundaries and iteration cap |
| goal_authority | original grant, current budget, native event and worker proof | keep independent proof checks; share only facts and resume policy |
| context | one call-scoped ProjectSnapshot, BOARD and LOG capture | already shares render inputs; do not add stale global snapshots |

This is bounded subsystem review, not a claim that every function in these
large modules was exhaustively refactored or proven duplicate-free.

## Historical/evidence processing

The read-only inventory uses size grouping before hashing and a 128MiB hash
budget. In its live snapshot `.saipen` contained 1,514,948,359 logical bytes;
134,217,721 bytes were hashed, exposing 96,473,551 potential identical bytes.
The initial user figures were historical; no unsupported before/after storage
claim is made. The snapshot may include live run material. Actual saving: ZERO.

Active state, original Sources, evidence, generated indexes, live inflight
records and historical archives are classified from their CORE/SOURCES/STORAGE
contracts, not folder names. Exact duplicate bytes do not by themselves prove
immutable aliases, all reference readers, rollback or crash-safe migration.
No hardlink, deletion, compression migration or archive replacement occurred.
The current physical retention policy also requires the operator's pending
decision for this project's .saipen. Unknown data remains protected.

## Verification cost discipline

Development used static, focused and controlled before/after checks. The
existing impact planner requires FULL for the final shared-policy revision;
one full family is running now. No earlier narrow record is relabeled full,
no unchanged full gate was restarted, and no stale PASS was transplanted.
Per-run counts and wall times remain in the actual logs. A hypothetical
all-features/full-rerun baseline was not measured, so no invented verification
cost-reduction percentage is reported.

NEXT EXACT ACTION: finish the live verification, preserve its scoped evidence,
and keep native/publication/history acceptance open until genuine proof exists.

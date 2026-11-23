# T-2023 — SRC-395 local ship closure (pending publication)

`saipen ship` for T-2023 refused at two gates, both correctly, and neither
wrote to the repository or a remote. This records the local closure and the
exact reason publication did not happen, following the T-2021 and T-2025
pending-publication precedent.

## Refusals, in order

| attempt | refusal | meaning |
|---------|---------|---------|
| `saipen ship` | `VALIDATION_FAILED` | foreign pre-existing staged paths would enter the release: `.saipen/BOARD.md`, `.saipen/KNOWLEDGE/INDEX.md`, `.saipen/KNOWLEDGE/cards/*`, `.saipen/KNOWLEDGE/roadmaps/*`, `.saipen/LOG.md`, `.saipen/MANIFEST.json`, `.saipen/STATE.md`, … (the T-1816/T-1817 external cohort plus protocol memory). Those paths are not this ticket's, so they must not be committed by it. |
| `saipen ship --isolated` | `NON_FAST_FORWARD` | remote `origin/main` tip is `60783ac4abb7`, which is **not** an ancestor of local `HEAD` (`66ef622a`). The publication lineage has diverged; fast-forwarding or reconciling that is an operator decision, never a force-push. |

## Zero external writes (measured)

- `HEAD` before and after: `66ef622a43ab59512735ac78ce10d1250e26f9df` (unmoved).
- Git index tree before and after: `c025cf8dd110c6db351f87496980c3c90c7522ef` (identical — the shared index and the sibling/foreign staging are byte-identical to what they were).
- No commit, no tag, no push, no remote write was performed by either attempt.

## Verified deliverable (focused + full)

- Focused receipt PASS, ran 143 — `.saipen/evidence/focused-unit/1e1d7f8154371f36-20261105T003039487102Z.json`
- Full core-unit family PASS on the final tree, ran 9022, red 3 = declared `test_t1816_provenance_inventory` baseline, `new_red: []` — `.saipen/evidence/core-unit/1e1d7f8154371f36-20261105T010450917088Z.json`

## Release scope (this ticket only)

`tools/saipen_engine/goal_authority.py`, `tools/saipen_engine/replenishment.py`,
`extensions/adapters/zaicode/saipen-guard.py`, `saipen/REGISTRY.json`,
`tools/test_t2023_goal_management_and_maintenance_binding.py`,
`tools/test_t2023_maintenance_policy_identity.py`.

## State

`publication_state: pending`. The change is evidence-complete and correct in
this tree; publishing it is blocked only on the operator's decision about the
diverged remote lineage (and on clearing the foreign staged cohort that is not
this ticket's to touch).

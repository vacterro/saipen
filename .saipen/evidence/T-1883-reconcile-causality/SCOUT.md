# T-1883 (SRC-308) — SCOUT

Source: operator paste `SAIHANDOFF — SAIPEN P0 RECONCILIATION SELF-DEADLOCK /
AUTOMATIC CAUSAL RECOVERY`, registered as SRC-308 via `saipen user-request`
(witness `model_supplied`, so it is a projected Work carrier, not new authority).

## Reproduction (measured on this tree, unchanged code)

`tools/saipen_engine/reconcile.py:352`:

```python
if live_blocked or cls is not None:
```

`live_blocked` is every ticket the BOARD puts in `## BLOCKED`, regardless of any
relation to `STATE.task`. Two identical STATEs, one difference:

```
CASE A  phase=SHIP task=T-1517
        blocker="operator_required (continuation_authority) for REVIEW -> SHIP"
        board: no ## BLOCKED tickets
      -> [{field: blocker, from: <the blocker>, to: "none", surface: state,
           reason: "... proven stale blocker (SAFE_CANONICAL_REPAIR)"}]

CASE B  identical STATE, board += T-1469, T-1480, T-1483, T-1505 in ## BLOCKED
      -> [{field: blocker, from: <the blocker>, to: None, surface: state,
           refuse: True, operator_decision_available: True,
           canonical_next_command: "saipen recover resolve-blocker <SRC-###>",
           reason: "... live ## BLOCKED board ticket(s) T-1469, ..."}]
```

The gate and its evidence did not change. Only unrelated project inventory did.
That is the confirmed defect: global inventory substituting for causality.

## Why it cannot be fixed by deleting the `live_blocked` term

`live_blocked or cls is not None` also covers the real case the closed rule
exists for: a genuinely related blocker whose text carries no recognised class.
`cls` alone would then clear a live gate. The handoff says this explicitly.
The fix has to classify RELATION, not presence.

## What "related" can be established from, without prose

Every input below is a canonical identifier the engine already parses:

- `STATE.task` — the active ticket id.
- `board["tickets"][tid]["section"] == "## BLOCKED"` — the blocked set.
- `board["tickets"][tid]["needs"]` — the parsed dependency list (`parse_board`
  returns it; verified: `needs: T-1` yields `['T-1']`).
- `blocker` opening token — `board.blocker_class`, exact head match only.
- `blocker` body `ACTIVE_DEPENDENCY:<T-###>` — already parsed by
  `board.py:1871` and by `operations.py:6004`.
- The journal: a committed `transition to <PHASE>` for that ticket.

Prose similarity is never consulted.

## Causal classes (mapped onto the existing result contract)

The handoff lists eight proposed names. `_state_blocker_repairs` already returns
dicts carrying `field`/`from`/`to`/`surface`/`reason`, optionally `refuse`,
`operator_decision_available`, `canonical_next_command`. The new classification
is an ADDED `classification` key on that same dict — not a parallel framework:

| classification | condition | result |
|---|---|---|
| `STALE_ACTIVE_BLOCKER` | active phase, no class token, no related blocked ticket | repair to `none` |
| `RELATED_ACTIVE_GATE` | a blocked ticket needed by, or needing, the active ticket; or `ACTIVE_DEPENDENCY:<active>`; or the blocker names the active ticket | refuse, operator decision |
| `UNRELATED_BOARD_BLOCKER` | live blocked tickets exist but none is related | irrelevant to this verdict; still repairs |
| `AUTHORITY_EVIDENCE_MISSING` | class token present but no journal gate evidence | refuse |
| `AUTHORITY_SCOPE_MISMATCH` | journal gate belongs to a different ticket | refuse |
| `JOURNAL_CONFLICT` | the committed transition contradicts the blocker | refuse, name the conflict |
| `SAFE_CANONICAL_REPAIR` | stale, and the journal proves the transition committed | repair |
| `GENUINE_OPERATOR_DECISION_REQUIRED` | live class token with matching scope | refuse |

Keep the existing `refuse: True` / `to: None` contract exactly so every current
consumer (`reconcile.py:2658`, `3166`, `3257-3263`) is unchanged.

## Prevention half (Workstream E)

- `_plan_transition` (`operations.py:4489`) already builds `owned` with
  `phase`/`next_action`/`transition_from`/`last_event`/`updated`/`agent` and
  NEVER writes `blocker`. So an ordinary transition cannot create one — the
  incident's blocker was typed directly into STATE by a session, which is the
  real hole: `patch_state` will write any field a caller passes.
- The invariant to enforce: in an ACTIVE phase a non-empty blocker must be a
  typed gate (`blocker_class is not None`) or it is not authority. Anything else
  is stale by definition and `reconcile` repairs it — which is what the
  classifier above already concludes. No second mechanism needed.
- E02 must NOT be implemented by rejecting the write at `patch_state` level:
  `reconcile` itself must write `blocker: none`, and fixtures seed blockers.

## Test correction (Workstream F)

`test_recovery_reachability.BlockerClassificationTests.test_a_live_board_block_refuses`
(line 103) asserts refusal because the board merely contains a blocked ticket.
Per the handoff that expectation is too broad. Replace with:
- an UNRELATED blocked ticket leaves the stale verdict unchanged (AC-01..AC-04),
- a RELATED blocked ticket refuses (AC-05),
- ambiguity fails closed (AC-06).

Its security coverage is preserved by the related cases, not dropped.

## Scope boundary

Files this ticket may touch: `tools/saipen_engine/reconcile.py`,
`tools/test_recovery_reachability.py`, and one new test module for the AC matrix.
`tools/saipen.py` auto-doctor changes are the P1 half and land only after the
classifier is proven. `tools/validate.py` is NOT touched (staged foreign batch).

## Not claimed

- FastPrompter live state is not accessible from this workspace, so live
  acceptance stays pending per the handoff's own instruction.
- The installed runtime carries a different `reconcile.py`; deployment parity is
  measured and reported separately, never assumed.

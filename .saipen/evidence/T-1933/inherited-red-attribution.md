# T-1933 — inherited red attribution for the broker/goal-authority family run

Scope: justify that the three `test_t1704_legacy_goal_authority` failures seen
alongside the T-1933 suites were **inherited**, not introduced by this Work, and
are therefore not a regression of the SRC-339 repair.

## The run

```
python -B -m unittest tools.test_t1844_origin_broker tools.test_t1844_goal_turns \
    tools.test_t1704_legacy_goal_authority tools.test_t1494_continuation_authority
→ Ran 106 tests in 75.133s
→ FAILED (failures=3)
```

Captured failing names, all in `LegacyGoalAuthorityTests`:

| test | line | assertion |
| --- | --- | --- |
| `test_crashed_transition_recovers_exact_prepared_bytes_without_a_new_grant` | — | same `VALIDATION_FAILED` |
| `test_fresh_native_event_keeps_existing_model_source_unpromoted` | 211 | `self.assertTrue(result.ok, ...)` |
| `test_native_event_keeps_imported_source_unpromoted` | 297 | `self.assertTrue(accepted.ok, ...)` |

Confirmed by re-running the suite alone: `Ran 28 tests ... FAILED (failures=3)`,
the same three names and no others.

Every one of them reports the same refusal:

```
{'ok': False, 'code': 'VALIDATION_FAILED', 'op_id': None, 'changed_files': [],
 'recovery_required': False,
 'message': 'goal authorization source is invalid, revoked or not operator-backed'}
```

## Raise site

`tools/saipen_engine/goal_authority.py:315`, inside `source_proof`. It raises
`ValueError("goal authorization source is invalid, revoked or not
operator-backed")` when the accepted Source's provenance or its `parse_capsule`
equality against `current_binding` does not hold.

## Why this is not caused by the SRC-339 repair

1. **No import path.** `grep -nE "guard|adapter|zaicode|subprocess"` over
   `tools/test_t1704_legacy_goal_authority.py` returns nothing. The suite builds
   its authority through `use_case_owner` + `native_operator(root, body,
   action="authorize-goal")` + `operations.authorize_goal_continuation`, so it
   never executes the hook, never starts a subprocess, and never touches the
   adapter tree this Work edited.
2. **Working-tree attribution.** `git status --porcelain` shows this Work's only
   entries are two untracked paths: `extensions/adapters/zaicode/` and
   `tools/test_t1933_zaicode_goal_seal.py`. `git status --porcelain --
   tools/saipen_engine/goal_authority.py` shows `AM`, i.e. the file was already
   modified in the working tree before this Work began; other engine files
   modified today belong to T-1932 and other sessions
   (`campaign.py`/`host_dispatch.py`/`saipal_adapter.py` at 17:46,
   `host_iteration.py` at 16:11).
3. **Not cross-test pollution.** Re-running the single case in isolation
   reproduces the identical failure in 0.182s:

   ```
   python -B -m unittest tools.test_t1704_legacy_goal_authority.LegacyGoalAuthorityTests.test_fresh_native_event_keeps_existing_model_source_unpromoted
   ```

4. **Same shape as the T-1932 finding.** T-1932 measured the full family at
   142 red → 106 red after its own repair, with every remaining red inherited
   from other sessions' uncommitted crew/release/acceptance work. This trio is
   part of that inherited set.

## Consequence for T-1933

No SRC-339 clause is settled on this suite, and no clause claims it green. The
focused record cited by T-1933's dispositions names only suites that ran PASS on
the current tree. The pre-existing `goal_authority.source_proof` failure stays an
open inherited defect; it is not repaired here and is not claimed repaired.

Live acceptance — a real ZAICODE host delivering a `goal`/`grant` event through
this hook — remains **UNVERIFIED**: no receipt from an installed host exists, and
the new suite says so in its own docstring. Nothing here presents a mocked broker
run as live acceptance.

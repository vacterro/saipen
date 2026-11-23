# T-1865 red-before-green control

One subject, one test module, two engine states. Nothing else differs.

## Subjects

- **prefix (red)** — `V:/_TEMP_/t1865-red-iPG9c3`: a full copy of `tools/` and
  `saipen/` from the post-fix worktree with exactly seven surgical reverts
  applied (each guarded by an assertion that the pre-fix text was present and
  that the revert took): the `ANTIGRAVITY_SOURCE_METADATA` carrier entry, the
  `LAUNCHER_ONLY_ENV` membership, `identity_environment()` returning the whole
  environment, `capture()` hashing the whole environment, the `identity_rule`
  stamp, the focused gate's reason suffix, and the full-family gate's reason
  suffix. The copy is used because the test imports `saipen_engine` as a
  package; reverting files in place would leave the remaining modules pairing
  to a half-staged package.
- **postfix (green)** — the live worktree.

## Commands

```
python -B tools/test_t1865_launcher_identity.py -v
```

identical in both, run with cwd = the subject root.

## Result

| state   | outcome                 | log                          |
|---------|-------------------------|------------------------------|
| prefix  | `FAILED (failures=13)`  | `prefix-red-control.log`     |
| postfix | `OK` — 14 tests         | `postfix-green-control.log`  |

The one test green on BOTH sides is
`test_a_real_environment_change_still_invalidates_the_identity`: it is the
control's own red control. It must pass before the fix too, because it asserts
that a *semantic* environment change keeps invalidating evidence. A fix that
made it fail would have turned the identity into a no-op rather than narrowing
it, so its passing in the prefix is the evidence that the seven reverts were
surgical rather than destructive.

Three of the thirteen reds are `GateMessageTests`, added by this ticket's own
REVIEW self-audit after noticing that the full-family gate in `core_unit.py`
still emitted the opaque sentence once the focused gate named its reason. The
reviewed delta therefore grew, the ticket returned canonically to BUILD, and
this pair was re-cut against the final bytes; the earlier pair (10 red / 11
tests) is superseded and not cited.

`subject.diff` is the pre-fix → post-fix delta across the four touched modules,
computed with `git diff --no-index` between the two subjects, so it is exactly
this ticket's change and carries none of the unrelated pre-existing worktree
edits.


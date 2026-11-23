# T-1864 (SRC-296) red-before-green control

One subject, one test module, two engine states. Nothing else differs.

## The bug, measured

On 23.10.26 T-1865's `VERIFY -> REVIEW` transition was the twentieth ticket of
this goal. The operation wrote:

```
WAIT: safety valve reached (0 waves / 20 tickets) -- run 'cc' to continue
```

and the turn ended. No question existed to ask: the grant that authorized the
first ticket authorized the twentieth, and the very next command (`cc`) cleared
the same counters with no operator anywhere in the chain. The engine stopped to
ask permission for a decision it had already made, and the cost fell on the
operator as a command to type.

## Subjects

- **prefix (red)** — `V:/_TEMP_/t1864-red-xqr5889v`: a full copy of `tools/`
  and `saipen/` from the post-fix worktree with exactly five surgical reverts
  applied, each guarded by an assertion that the pre-fix text was present
  exactly once and that the revert took:
  1. the ticket trip site back to its unconditional `WAIT:`;
  2. the wave trip site back to its unconditional `WAIT:`;
  3. the `expected["goal_tickets"]` payload back to `pre + 1`;
  4. `operations._trip_checkpoint` removed entirely;
  5. `goal_authority.trip_checkpoint` removed entirely.
- **postfix (green)** — the live worktree.

## Commands

```
python -B tools/test_t1864_autonomous_valve.py -v
```

identical in both, run with cwd = the subject root.

## Result

| state   | outcome                         | log                          |
|---------|---------------------------------|------------------------------|
| prefix  | `FAILED (failures=4, errors=6)` | `prefix-red-control.log`     |
| postfix | `OK` — 15 tests                 | `postfix-green-control.log`  |

The ten failures split along the ticket's two claims. The six errors are all of
`TripCheckpointOwnerTests`: with `goal_authority.trip_checkpoint` removed there
is no owner to call, which is the point — the decision has one name. The four
failures are the live behaviour: counters stay `(0, 20)` instead of `(0, 0)`,
the route stays `WAIT: safety valve ...` instead of `PHASE REVIEW T-010`, no
`goal checkpoint` marker reaches LOG, and the wave branch keeps its own WAIT
instead of clearing to `PHASE ADD`.

The five tests green on BOTH sides are the ones that keep this fix honest, and
they must pass before the fix too:

- `test_a_consumer_bounded_grant_still_waits_for_its_operator` — a consumer
  project's bounded grant still writes the WAIT and still binds a brake. This
  is the red control on the *policy*: if it failed before the fix, the test
  would be proving nothing about autonomy and everything about ignoring caps.
- `test_the_checkpoint_agrees_with_the_counters_recovery_rebuilds` — the
  pre-fix path leaves 20 in STATE and 20 in the derived history, which agree;
  the post-fix path leaves 0 and 0, which also agree. A checkpoint marker whose
  reset disagreed with STATE would open a permanent heal loop.
- `test_the_fix_does_not_touch_the_twentieth_ticket_count_itself` — both
  polarities log `DEC: goal_tickets 19->20`; only the response to the cap
  differs, so autonomy did not delete the periodic look at the work.
- `test_the_untripped_count_still_reports_the_increment` — the same payload
  field below the cap still reports `pre + 1`.
- `test_the_result_payload_reports_the_committed_counters` — green on both, but
  for different reasons and only one of them is load-bearing. Pre-fix the
  payload is `pre + 1` and the committed value is also 20, so it agrees by
  arithmetic; the assertion only discriminates once the trip site clears the
  counters, where a stale `pre + 1` would report a ticket the STATE does not
  have. It is listed here rather than as a red test because the prefix cannot
  fail it: the payload revert and the trip-site revert cancel each other out.
  Its value is as a guard on the post-fix invariant, not as proof of the fix.

One test was added by REVIEW rather than by BUILD.
`test_the_same_checkpoint_clears_the_wave_budget` is red before the fix and
green after, exactly like the ticket-counter test, but it exists because the
self-audit found the HUNT -> ADD trip site had *no test at all* -- the
symmetric half of this change was carried by the same helper and left
unpinned. It now measures waves 2 -> 3 -> checkpoint -> 0 with the `PHASE ADD`
route preserved.

`test_an_untripped_budget_gets_no_answer` and
`test_a_non_goal_intent_is_never_a_budget_question` are part of the six red
errors, not this group: both call the owner directly, so removing the owner
removes the thing under test. Their job is the owner's refusal boundary, not
the engine's behaviour.

## What the two-polarity grant tests pin

`TripCheckpointOwnerTests` proves the authority claim in both directions
against the same fixture:

- `test_a_proven_persistent_grant_clears_itself` — a persistent grant whose
  journal proves cleanly renews the budget and names `E-5` as the source. This
  is the branch that matters: a granted run with an *unreadable* journal must
  not clear itself on the strength of a grant it cannot read.
- `test_an_unproven_persistent_grant_still_waits` — the same grant with a
  journal that does not prove returns `None`, so the caller keeps the WAIT.
- `test_an_unreadable_grant_journal_degrades_to_the_human_boundary` — a
  `ValueError` from `prove()` returns `None` instead of raising inside
  `_plan_transition`. Found by this ticket's own REVIEW self-audit: the first
  build called `prove()` unguarded, so a corrupt grant journal would have
  crashed the very transition that tripped the cap.

`subject.diff` is the pre-fix → post-fix delta across the two touched modules,
computed with `git diff --no-index` between the two subjects, so it is exactly
this ticket's change and carries none of the unrelated pre-existing worktree
edits.

## What is deliberately NOT changed

`goal_authority.bounded_resume_requirement()`, the router's `RESTATE_AND_STOP`
branch for a *persisted* `WAIT: safety valve`, and `disposition`'s
`requires_human` classification are all untouched. They describe how an
already-tripped, already-persisted bounded valve behaves, and for a consumer
project that behaviour is correct. This ticket removes the *duty* from the
protocol home and from a proven persistent grant at the moment of the trip,
instead of teaching the engine to talk itself out of a brake it already wrote.

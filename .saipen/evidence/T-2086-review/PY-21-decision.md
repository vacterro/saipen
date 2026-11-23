# T-2086 review -- saipython/PY-21 at dc39709c / 0f69fe84

- package_identity: sha256:60378de9f51a2bd8829e3a0988f3dd821079cbb4d0d44c8daa93c930bf8453c9
- producer: saipython; package: PY-21
- reviewer: saipen-cli (current session)
- verdict: VERIFIED-ACCEPTED -- patch reproduces and fixes the race at the declared identity

## Independent measurements (fresh reviewer sample)

- `git apply --check .saipen/extensions/subs/saipython/kitchen/PY-21.patch`
  from the repo root: exit 0 on the live target bytes.
- Baseline overlay, 2 fresh samples (`baseline_sample.out` in this
  directory): both `["GC_RUN_COMPLETE","GC_MAINTENANCE_FAILED"]`,
  `durable_failures: 1`, `counted_done: ["T-001"]` -- the lost-checkpoint
  race reproduces on the unpatched bytes.
- Patched overlay, 8 fresh rounds: `durable_failures` total 0, both closures
  counted in 8/8 rounds, `maintenance_runs` = 1 in every round.
- The role's own captures (`_py21_baseline.out` 4/4 fail, patched 8/8,
  `_py21_gc_suite.out` `Ran 63 tests -- OK (skipped=1)`) are consistent
  with this sample; the suite was not re-run for the reviewer sample.

## Disposition

The patch is real, applies cleanly and is verified, but integration belongs
to T-2062, not to this review ticket; applying a package patch during intake
is explicitly out of scope. No truthful closure mode exists:
`own_patch` would claim T-2086 integrates a patch it does not own,
`inherited_verified` needs a committed release naming T-2086 (none), and
`finding_invalidated` would falsify reproduced results. Blocked with
`WAIT_USER_DECISION` on the T-2058 publication staging (gates A/B); package
disposed as reviewed after the block. T-2062 itself remains unmeasurable by
the installed generation: `saipen ticket unblock T-2062` still refuses with
WAIT_USER_DECISION because the installed 8.1.0 classifier reads the whole
blocker prose (the repo 8.1.1 fix T-2077 is not installed), and the repo
engine refuses mutation with HOME_REQUIRED home-divergent.

## Re-check after the autonomous-resolution directive (17.11)

The runtime directive asked to unblock T-2086 and resolve it autonomously.
The canonical routes were re-measured against the installed runtime, all
zero-write:

- `saipen ticket unblock T-2086 "<review decision + directive text>"` ->
  `WAIT_USER_DECISION`, "unblocking requires verified operator authority or
  authentic proof" (the gate triggers on the blocker prose, and no sealed
  operator carrier exists; the host broker is unreachable from agent
  processes).
- `saipen claim T-2086 --explicit` -> `TICKET_NOT_WORKABLE`.
- `saipen ticket done T-2086` -> `ILLEGAL_TICKET_LIFECYCLE` (needs DOING).
- `saipen transition DOING T-2086` -> `ILLEGAL_TRANSITION` (phase DONE).
- `saipen checkpoint DEC T-2086 ...` -> `STALE_WORK_CONTEXT` (no active
  work context; claim is the precondition).
- Repo 8.1.1 `ticket unblock` cannot run at all:
  `HOME_REQUIRED: home-dead: home-divergent`.

No canonical operation moves a BLOCKED row to TODO/DOING without a sealed
operator carrier, so the review ticket stays blocked. A reviewed package
whose linked Core ticket is terminal is the protocol's own REVIEW_PENDING ->
CURRENT path (PROTOCOL.md sec. 4), which is why the crew circuit accepted the
disposition. The standard engineering default cannot override the unblock
authorization rule; only the operator act named in the release index lifts it.

One new observation from the refusal: the installed gate returns
`unregistered_code: true` for `WAIT_USER_DECISION` -- the code is absent from
`REGISTRY.json` `error_codes` in both the repo and installed generations, and
the repo refusal-registry completeness test still passes (it does not see the
variable-assigned code). Recorded here for the next sweep; no ticket created
and no tree write made.

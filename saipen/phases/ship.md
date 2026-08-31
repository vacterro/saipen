# Phase: SHIP

## Purpose

Publish the reviewed ticket: local release metadata, then commit, branch push
and tag push, then the atomic finish. "PUBLISH" names the action, not a phase
value -- CORE.md § 1.6's enum has 16 entries and no `PUBLISH`.

## Entry

Only on `saipen ship`, or repo has `origin` AND LOG shows a prior ship, or
`execution_intent: goal` (MAINTENANCE.md § 2.4) with an existing `origin`.
Never auto-publish an unopted project. Needs 100% green.

**Fixable preflight failure -> BUILD, not BLOCKED.** Steps 0-4 and the 6a
validator rerun can expose a defect before anything is committed, tagged or
pushed. LOG the failure, transition `SHIP -> BUILD`, fix, repeat
`VERIFY -> REVIEW -> SHIP`. `BLOCKED` is only for a failure needing user input
or with no safe known fix; using it for ordinary repair falsely ends goal
execution (MAINTENANCE.md § 2.4). Pre-publish only: once commit/tag/push
begins step 10 governs, and after a successful push there is never a return to
BUILD for that ticket.

## `mode: no-publish`

The phase is still entered. CORE.md § 1.3 blocks the git-dependent steps
(commit, tag, push), not `SHIP` itself; a blanket ban would mean a git-less
project can never close a ticket (`phases/review.md` makes `SHIP` mandatory
before `DONE`).

**`no-publish` means publishing is not permitted. It does NOT mean git is
absent.** Fusing the two is the defect this split prevents: git's existence is
observable (`git rev-parse --short HEAD`), permission is `mode:`. Ask
separately. Same error class as `phases/markhunt.md`'s `no-git` manifest
hashes (T-462).

| Step | Under `no-publish` | Why |
|------|--------------------|-----|
| 0, 1, 2, 4 | **DO** | Board pre-flight, README, version bump, junk sweep -- local |
| 3 | **DO, minus the tag clause** | README/CHANGELOG still agree with `VERSION`; no tag to match |
| 5 | **SKIP** | Authorizes a push that will not happen |
| 6a | **DO** | CHANGELOG plus validator re-run: local by construction |
| 6b | **SKIP** | Commit AND push -- both forbidden; this is why 6 is split in two |
| 7 | **SKIP** | Tag creation and tag push |
| 8 | **SKIP** | First publish is settled at step 5, which is skipped |
| 9 / 10 | **REPLACE** | See the LOG line below |

Replace steps 9/10's LOG line with: `- DATE [E-###] [parent: E-###]
RUN: ship vX.Y.Z -> skipped publish (no-publish: <reason>)` (this exact text
after the taxonomy), where `<reason>` is `policy` when git works and
publishing is off, or `no git` when `git rev-parse` genuinely cannot answer.
**Write the one that is true** -- a fabricated `no git` on a host with a live
remote is a false record in an append-only file. Never phrase either as a
failure: nothing failed, publish was not attempted. Write the human digest as
always, `awaiting:` noting `git needed to publish` when true. Then STATE ->
`DONE`, as for a normal ship.

## Procedure

0. **Board pre-flight: every work unit done this session MUST have a ticket in
   `## DONE`.** Inline fixes and sweeps without a ticket get one first. Stale
   `## DONE` blocks SHIP (CORE.md § 1.2).
1. README beautiful: pitch, features, install, usage, version + changelog link.
2. Version bump (micro -> 3.2.1, feature -> 3.2.0, breaking -> major).
3. Before push, one release identity MUST agree across the complete version
   surface:
   - `VERSION` is the canonical release value.
   - The root README badge and every mechanically mirrored locale README badge
     match `VERSION` exactly once.
   - `CHANGELOG.md`'s head entry matches `VERSION`.
   - The exact git tag about to be created is `vVERSION`.

   `tools/validate.py --gate ship` discovers the locale mirrors from the
   translation kitchen; never replace that discovery with a handwritten list.
   The intended tag is checked here before creation, then against the
   committed `VERSION` before its push.
4. .gitignore covers junk + secrets. Empty tmp/, strip debug prints.
5. **Classify the remote BEFORE any external write, and clear the
   first-publish gate here.** `git remote get-url origin` (absent -> no
   remote), then `git ls-remote --heads --tags origin` (empty -> the remote
   exists but never received a commit or tag). Either answer is a first
   publish, and a first publish stops here for confirmation --
   `next_action: WAIT: first-publish -- confirm repo name '<name>' and
   public/private before I push` (CORE.md § 1.2) -- ALWAYS, even under the goal
   intent (MAINTENANCE.md § 2.4's SHIP exception). A new public artifact is a
   one-way door. The gate sits BEFORE the pushes it authorizes; it once sat at
   step 7, downstream of the act, which is not a gate at all.
6a. **LOCAL. Touches no repository and no remote.** Prepare the FINAL release
    metadata: `VERSION`, the root README badge, every discovered locale badge,
    `CHANGELOG.md` newest-top. Re-run the required validators after every
    metadata edit -- a mutation invalidates earlier VERIFY/REVIEW/gate
    evidence, which described old bytes. The signal gate is
    `tools/validate.py --gate core`.

    **A stale, malformed or unrefreshed producer package does not block it** --
    an EE or QQ package is required fresh when consumed
    (`--gate collect:<producer>`) or at CONVERGE.md stage M, never as a
    precondition for an unrelated Core commit; it still WARNs, naming the
    producer. Reversing this once put a one-line Core ship behind regenerating
    every producer (T-568).

    This run is a **signal, not the authorization**: some gates need the
    staging set, so the binding run is 6b's. `--gate ship` ALWAYS requires the
    release index and refuses an empty one.
6b. **GIT. Writes the repository and the remote.** Once 6a is green, in this
   exact order. **Staging comes before the binding gate**, because a gate that
   cannot see the index cannot answer questions about it.

   1. **Read the index and the working tree.** `git status --porcelain=v1
      -uall` and `git diff --cached --name-only`. Snapshot the pre-ship index
      (`git write-tree`) before adding anything -- it is the rollback source.
   2. **Attribute every intended file** to the ticket or wave being shipped.
      An unattributed change is step 0's problem.
   3. **Preserve anything the user staged before this run.** It stays staged
      and is named in the ship report. Never `git reset` a staged set you did
      not create. A foreign staged path may not enter this release: stop
      before committing unless the intended index can be isolated without
      changing that entry.
   4. **Stage ONLY the reviewed files this ship owns**, by explicit path:
      `git add -- <path> [<path> ...]`. **`git add .` and `git add -A` are
      forbidden here** -- both stage whatever else the tree carries, which is
      how an unreviewed file reaches a release.
   5. **Re-read the staged set and prove it equals the intended scope**
      (`git diff --cached --name-only` against 2). A difference stops the
      ship; it is not committed and explained.
   6. **Run `tools/validate.py --gate ship` NOW.** The binding gate: it fails
      unless every discovered release path is staged, and refuses any
      staged/working divergence on the version surface. A runtime file added
      by this ticket is tracked from the moment it is staged, so the MANIFEST
      check can be satisfied (T-569).
   7. **`git diff --cached --check`** -- the exact bytes about to be
      committed, not the working tree.
   8. **Commit exactly the staged scope.** No `-a`, no widening path args.
   9. **Push the branch.** **Re-read the remote immediately before this push**
      and again before the tag push: step 5's answer is a measurement that a
      concurrent publish makes stale. Changed to established -> proceed;
      changed the other way -> stop and re-run step 5's gate.

   **If 6 or 7 fails: no commit, no push, no tag.** Restore each release path
   in the index from the pre-ship index tree of step 1, NOT from `HEAD` --
   that destroys a pre-existing partial stage of the same path. Foreign
   staging stays byte-identical. Then take the fixable SHIP -> BUILD edge.

   *Why 6 is two steps.* As one step the `no-publish` table had to say "do
   step 6" and "skip the push half" at once, leaving the commit that mode
   forbids. A step is local or it is not; staging is repository state, so it
   lives in the git half.
7. ONLY AFTER step 6b's branch push has LANDED -- confirmed by the push
   returning success, or by `git rev-parse origin/BRANCH` ==
   `git rev-parse BRANCH` after a fetch -- create the release tag, then push
   that exact ref only: `git tag -a vVERSION -m "line"` followed by
   `git push origin refs/tags/vVERSION:refs/tags/vVERSION`.
   A rejected or failed branch push means NO tag push at all: the tag stays
   local and step 10 owns recovery. Publishing a tag whose commit is on no
   remote branch is the defect that hit twice (E-1787, E-1882). `git push
   --tags` and `git push --follow-tags` are forbidden here: both select from
   unrelated local tag state, so an inspection tag can become a published
   artifact outside the release plan.
8. First publish is settled at step 5, re-checked at 6b and 7. Both shapes are
   brand-new: no `origin`, and an `origin` that never received a commit or
   tag.
9. LOG one normal Event Graph line per CORE.md § 1.2 -- `- DATE [E-###]
   [parent: E-###] RUN: ship vX.Y.Z -> pushed HASH` (this exact text after the
   taxonomy).
10. Push rejected or fails: LOG `- DATE [E-###] [parent: E-###] RUN: ship
    vX.Y.Z -> push FAILED <reason>` (this exact text after the taxonomy) --
    never claim success on a failed push. Commit/tag stay local. Then by
    failure class:
    - Transient (network, auth hiccup)? Retry once, then `BLOCKED` -- and the
      retry still owes CORE.md § 1.6's question: name what is different in the
      LOG line (token refreshed, remote reachable again, a different branch).
      "Nothing, but maybe this time" is not a delta.
    - **Non-fast-forward (someone pushed meanwhile) is ROUTINE, not a
      blocker.** `git fetch`, inspect what landed (touches `.saipen/` or this
      ship's own files -> read before acting; unrelated -> proceed), rebase
      onto the new remote tip, re-run the validator, delete and recreate the
      tag on the rebased HEAD (verify `git rev-parse HEAD` == `git rev-parse
      vX.Y.Z^{commit}`; a tag on the pre-rebase commit is a stale pointer),
      push again. **The delete-and-recreate is always purely local**: step 7
      gates the tag push on the branch push having landed, so on a failed
      attempt the tag never left this machine. A tag of this name already
      pushed by an EARLIER completed ship is a remote history rewrite instead,
      under the force-push confirmation gate below, never silently redone.
      Rebase conflicts -> stop, `BLOCKED` with the conflicting files as facts.
      NEVER resolve a rejected push with force-push (CORE.md § 1.1).
    - Anything else non-transient? `STATE.phase: BLOCKED` -- pushing is the one
      SHIP step an agent must not guess its way through.

## Exit

**Human digest.** After a successful push, (over)write
`.saipen/kitchen/digest.md` -- exactly three short lines: `done:` (what this
session shipped), `remaining:` (top open `TODO`, or `nothing`), `awaiting:`
(anything parked on a `WAIT:`/decision, or `nothing`). Overwrite every time --
a snapshot, not history. Same file `saipen stop` writes (COMMANDS.md,
CMD-ROUTING-01).

The ticket is closed by the atomic `finish_ticket` operation (`saipen ticket
done`): the SHIP -> DONE transition, the `## DOING` -> `## DONE` move and the
completion LOG event in ONE journaled plan (T-602). The gate is mechanical:
`finish_ticket` accepts the ticket ONLY from `phase: SHIP`; from
SCOUT/BUILD/VERIFY/REVIEW it REFUSEs `ILLEGAL_PHASE` and writes zero canonical
bytes. `execution_intent: goal`? Not a stopping point even momentarily --
`next_action` MUST already name the next step. `phases/done.md` § 1 sends you
to HUNT (MAINTENANCE.md § 2.4).

**The shipped ticket was still in `## DOING` when this phase began**, and is
`## DONE` only after the atomic finish -- REVIEW keeps it claimed
(`phases/review.md`, T-466). That is what makes REVIEW's `PHASE SHIP T-###`
a legal pick and the finish gate sound: the ticket cannot leave `## DOING`
until it has really passed through REVIEW into SHIP.

## Failure / Blocked

Pre-publish and fixable -> `SHIP -> BUILD` (see Entry). Push failure -> step
10 by class. Anything needing user input or with no safe known fix ->
`STATE.phase: BLOCKED` with the facts.

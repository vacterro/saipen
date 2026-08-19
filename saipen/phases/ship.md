# Phase: SHIP

## SHIP -> PUBLISH

"PUBLISH" names the action this phase performs (tag + push), not a
separate `STATE.md phase:` value -- `SHIP` is the only phase here; CORE.md
§ 1.6's 16-value enum has no `PUBLISH` entry. The arrow above is
descriptive, not a transition-table row.

Only on `saipen ship`, or repo has `origin` AND LOG shows prior ship, or
`execution_intent: goal` (MAINTENANCE.md §2.4) with an existing `origin`. Never auto-publish
unopted project. Needs 100% green.

**Fixable preflight failure -> BUILD, not BLOCKED.** Steps 0-4 plus release
metadata preparation and the validator rerun in step 6a can expose a defect
before anything is committed, tagged, or pushed: a broken release script, a
stale generated file, a failing validator, or another fault with a known local
fix. LOG the exact failure, transition the current ticket
`SHIP -> BUILD`, fix it, and repeat `VERIFY -> REVIEW -> SHIP`. `BLOCKED` is
reserved for a failure that genuinely needs user input or has no safe known
fix; using it for ordinary repair would falsely end goal execution (MAINTENANCE.md section
2.4). This edge closes the pre-publish loop only. Once commit/tag/push begins,
the failure-specific recovery in step 10 governs; after a successful push there
is never a return to BUILD for that shipped ticket.

`mode: no-publish`? This phase is still entered -- CORE.md §1.3 blocks
git-dependent steps only (commit, tag, push), not `SHIP` itself; a blanket
ban here would mean a git-less project can never close a ticket at all
(`phases/review.md` makes `SHIP` mandatory before `DONE`, no exception).

**`no-publish` means publishing is not permitted. It does NOT mean git is
absent.** Two different facts, and this block used to fuse them: it called
the remote steps skippable because "no remote exists to publish to" and
made the mandatory LOG line say `no git`, on a host that may well have a
repository, a remote, and a perfectly readable `HEAD`. Whether git exists
is observable -- `git rev-parse --short HEAD` answers or it does not -- and
whether publishing is permitted is `mode:`. Ask them separately. (Same
error class as `phases/markhunt.md`'s `no-git` manifest hashes, fixed in
T-462.)

**Do exactly this, and nothing is half-permitted:**

| Step | Under `no-publish` | Why |
|------|--------------------|-----|
| 0, 1, 2, 4 | **DO** | Board pre-flight, README, version bump, junk sweep -- local, no repository touched |
| 3 | **DO, minus the tag clause** | README and CHANGELOG must still agree with `VERSION`; there is no tag to match |
| 5 | **SKIP** | Remote classification and the first-publish gate authorize a push that will not happen |
| 6a | **DO** | CHANGELOG plus the validator re-run: local by construction |
| 6b | **SKIP** | Commit AND push. Both are forbidden here -- this is the step whose "push half" the old wording tried to skip while leaving the commit |
| 7 | **SKIP** | Tag creation and tag push |
| 8 | **SKIP** | First publish is settled at step 5, which is skipped |
| 9 / 10 | **REPLACE** | See the LOG line below |

Replace steps 9/10's LOG line with: `- DATE [E-###] [parent: E-###]
RUN: ship vX.Y.Z -> skipped publish (no-publish: <reason>)` (this exact
text after the taxonomy), where `<reason>` is `policy` when git works and
publishing is switched off, or `no git` when `git rev-parse` genuinely
cannot answer. **Write the one that is true.** A fabricated `no git` on a
host with a live remote is a false record in an append-only file, and the
next agent reading it will believe this project cannot publish at all.
Never phrase either as a failure: nothing failed, publish was not
attempted. Write the human digest same as always, `awaiting:` noting
`git needed to publish` when that is the actual reason. Then STATE ->
`DONE` directly, same as a normal successful ship.

0. **Board pre-flight: every work unit done this session MUST have a ticket in `## DONE`.** Inline fixes and sweeps without a ticket must get one before proceeding. Stale `## DONE` blocks SHIP (CORE.md §1.2).
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
   translation kitchen and checks the README plus CHANGELOG surfaces; do not
   replace that discovery with a handwritten locale list. The intended tag is
   still checked here before creation, then against the committed `VERSION`
   before its push.
4. .gitignore covers junk + secrets. Empty tmp/, strip debug prints.
5. **Classify the remote BEFORE any external write, and clear the
   first-publish gate here.** `git remote get-url origin` (absent -> no
   remote), then `git ls-remote --heads --tags origin` (empty -> the remote
   exists but has never received a commit or tag). Either answer is a first
   publish, and a first publish stops here for confirmation --
   `next_action: WAIT: first-publish -- confirm repo name '<name>' and
   public/private before I push` (CORE.md §1.2) -- ALWAYS, even under
   the goal intent (MAINTENANCE.md §2.4's SHIP exception). Creating a new public artifact
   is a one-way door.
   **This gate used to sit at step 7, after the branch push and the tag
   push.** Its own wording said "before I push" while the push it named had
   already happened two steps earlier, so on the one run it exists for the
   irreversible act preceded the authorization -- or, with no `origin` at
   all, the push failed first and dropped into generic push recovery, which
   never asks the question. A gate downstream of the act it authorizes is
   not a gate.
 6a. **LOCAL. Touches no repository and no remote.** Prepare the FINAL release
    metadata: `VERSION`, the root README badge, every discovered locale badge,
    and `CHANGELOG.md` newest-top. Re-run the required validators after every
    release metadata edit. Any metadata mutation invalidates earlier
    VERIFY/REVIEW/gate evidence: proof produced before the mutation describes
    old bytes and cannot authorize the release bytes. The signal gate is
    `tools/validate.py --gate core`: everything required to ship THIS tree
    safely, short of the release-index binding. **A stale, malformed or
    unrefreshed producer package does not
    block it** — an EE or QQ package is required fresh when it is consumed
    (`--gate collect:<producer>`) or at CONVERGE.md stage M
    (`--gate converge`), never as a precondition for an unrelated Core commit.
    Those packages still report, as WARNs naming the producer, so nobody
    mistakes soft for invisible. Reversing this once put an ordinary one-line
    Core ship behind regenerating every producer in the project (T-568).

    A run here is a **signal, not the authorization**: some gates can only be
    answered once the staging set exists, so the binding run is 6b's, after
    staging. The ship gate ALWAYS requires the release index — `--gate ship`
    refuses an empty index. There is no "non-binding ship gate" shape; the
    pre-staging signal uses `--gate core` instead.
6b. **GIT. Writes the repository and the remote.** Once 6a is green, in this
   exact order. **Staging comes before the binding gate**, because a gate
   that cannot see the index cannot answer questions about it.

    1. **Read the index and the working tree.** `git status --porcelain=v1
       -uall` and `git diff --cached --name-only`. Two separate facts: what
       is already staged, and what has changed at all. Snapshot the pre-ship
       index exactly (`git write-tree`) before adding anything; this tree is
       the rollback source for release paths if a later check fails.
   2. **Attribute every intended file** to the ticket or wave being shipped.
      An unattributed change is step 0's problem, not something to stage and
      explain in the commit message.
    3. **Preserve anything the user staged before this run.** It is not
       yours; it stays staged and it is named in the ship report. Never
       `git reset` a staged set you did not create. A foreign pre-existing
       staged path may not enter this release: stop before committing unless
       the release mechanism can isolate the intended index without changing
       that foreign entry.
   4. **Stage ONLY the reviewed files this ship owns**, by explicit path:
      `git add -- <path> [<path> ...]`. **`git add .` and `git add -A` are
      forbidden here** — both stage whatever else the tree happens to be
      carrying, which is how an unreviewed file reaches a release.
   5. **Re-read the staged set and prove it equals the intended scope.**
      `git diff --cached --name-only` compared against the list from 2.
      A difference stops the ship; it does not get committed and explained.
    6. **Run `tools/validate.py --gate ship` NOW.** This is the
       binding gate; it fails unless every discovered release path is staged.
       It also refuses any staged/working divergence on that version surface;
       otherwise a clean working badge could hide stale bytes already selected
       for commit.
       A required runtime file added by this ticket is tracked from the moment
      it is staged, so the MANIFEST check can finally be satisfied — before
      this order existed, the gate ran first and a newly-added required file
      could not pass it at all without an undocumented staging step the
      protocol never named (T-569).
   7. **`git diff --cached --check`** — whitespace and conflict markers in
      the exact bytes about to be committed, not in the working tree.
   8. **Commit exactly the staged scope.** No `-a`, no path arguments that
      would widen it past what 5 proved.
   9. **Push the branch.** **Re-read the remote immediately before this
      push** and again before the tag push below: step 5's answer is a
      measurement, and a remote someone else published to in between makes
      it stale. Classification changed from first-publish to established ->
      proceed; changed the other way -> stop and re-run step 5's gate.

   **If 6 or 7 fails: no commit, no push, no tag.** Restore each release path
   in the index from the exact pre-ship index tree recorded in step 1; do not
   restore it from `HEAD`, because that destroys a pre-existing partial stage
   of the same path. Foreign/pre-existing staging stays byte-identical. Then
   return through the ordinary fixable SHIP -> BUILD edge; a failing gate is
   work to do, not a gate to route around.

   *Why this is two steps.* It was one, and the `mode: no-publish` block
   above then had to say "do step 6" and "skip the push half of step 6" in
   the same breath -- leaving the commit, which that mode forbids. A step
   that is half-permitted cannot be followed; a step is local or it is not.
   Staging lives in this half for the same reason: the index is repository
   state, so `mode: no-publish` reaches nothing here at all.
7. ONLY AFTER step 6b's branch push has LANDED -- confirmed by the push
   returning success, or by `git rev-parse origin/BRANCH` ==
   `git rev-parse BRANCH` after a fetch -- create the release tag, then
   push that exact ref only:
   `git tag -a vVERSION -m "line"` followed by
   `git push origin refs/tags/vVERSION:refs/tags/vVERSION`.
   A rejected or failed branch push means NO tag push at all: the tag stays
   local and step 10 owns recovery. Pushing the tag while the branch is
   unlanded is the exact defect that hit twice -- E-1787 for v7.171.0,
   E-1882 for v7.176.0, each time a rejected branch push was followed by a
   successful tag push publishing a tag whose commit was on no remote
   branch. `git push --tags` and `git push --follow-tags` are forbidden
   here: both select from unrelated local tag state, so a temporary
   inspection tag can become a published artifact without appearing in the
   release plan. The branch push in step 6b and this one named tag push are
   separate commands, and the second MUST NOT run unless the first landed.
8. First publish is settled at step 5, before anything leaves this machine,
   and re-checked at step 6b and step 7. It is named here only because this
   is where the list used to carry it, and a reader who learned the old
   order needs to be sent forward rather than left looking. Both shapes
   count as brand-new: no `origin` at all, and an `origin` that exists but
   has never received a commit or tag (added early by `git remote add`,
   never published to) -- the same one-way door reached two ways.
9. LOG one normal Event Graph line per CORE.md §1.2 -- `- DATE [E-###]
   [parent: E-###] RUN: ship vX.Y.Z -> pushed HASH` (this exact text after
   the taxonomy).
10. Push rejected or fails: LOG one normal Event Graph line per CORE.md §1.2
   -- `- DATE [E-###] [parent: E-###] RUN: ship vX.Y.Z -> push FAILED
   <reason>` (this exact text after the taxonomy) -- never claim success
   on a failed push. Commit/tag stay local. Then by failure class:
   - Transient (network, auth hiccup)? Retry once, then `BLOCKED` -- and
     the retry still owes CORE.md §1.6's question: name what is different
     in the LOG line (token refreshed, remote reachable again, a
     different branch). "Nothing, but maybe this time" is not a delta,
     and a counter of one does not make it into one.
    - **Non-fast-forward (someone pushed meanwhile) is ROUTINE, not a
      blocker** -- for a protocol built around multiple sessions
      touching one project, "the remote moved" is expected life,
     not an anomaly: `git fetch`, inspect what landed (it touches
     `.saipen/` or files in this ship's own commits? -> read before
     acting; unrelated files? -> proceed), rebase the local commits onto
     the new remote tip, re-run the validator, delete and recreate the
     tag on the rebased HEAD (verify `git rev-parse HEAD` ==
     `git rev-parse vX.Y.Z^{commit}` -- a tag left on the pre-rebase
     commit is a stale pointer), push again. **This delete-and-recreate is
     always a purely local correction, never a remote one** -- it only
     applies to a tag from *this same*, still-failed ship attempt, which by
     definition was never successfully pushed (the code push that would have
     carried it already got rejected). The definition holds because step 7
     gates the tag push on the branch push having LANDED: on this attempt the
     tag never left this machine, so correcting it here touches nothing
     public. Discovering instead that a tag
     with this name was already pushed in an *earlier*, separate, since-
     completed ship -- a genuinely different and much rarer situation, not
     what this recovery path is for -- is a remote history rewrite and
     falls under the same force-push confirmation gate as the line below,
     never silently redone the same way. Rebase conflicts -> stop,
     `BLOCKED` with the conflicting files as facts. NEVER resolve a
     rejected push with force-push (CORE.md §1.1 destructive list).
   - Anything else non-transient? `STATE.phase: BLOCKED` -- pushing is
     the one SHIP step an agent must not guess its way through.

**Human digest.** After a successful push, (over)write
`.saipen/kitchen/digest.md` -- exactly three short lines, written for the
human so they read one small file instead of scrolling `LOG.md`:
`done:` (what this session actually shipped), `remaining:` (the top open
`TODO`, or `nothing`), `awaiting:` (anything parked on a `WAIT:`/decision,
or `nothing`). Overwrite every time -- it's a snapshot, not history (history
stays in `LOG.md`). This is the same file `saipen stop` writes (CORE.md §1.10).

After SHIP: the ticket is closed by the atomic `finish_ticket` operation
(`saipen ticket done`) -- the SHIP -> DONE transition, the `## DOING` ->
`## DONE` move and the completion LOG event in ONE journaled plan (NITRO
dogfood IV, T-602). The gate is mechanical: `finish_ticket` accepts the
ticket ONLY from `phase: SHIP`; from SCOUT/BUILD/VERIFY/REVIEW it REFUSEs
`ILLEGAL_PHASE` and writes zero canonical bytes. `execution_intent: goal`? Do
not treat this as a
stopping point even momentarily -- `next_action` MUST already name the
next step, never a wait. `phases/done.md` § 1 sends you straight to HUNT;
board-empty is a waypoint, not an exit (MAINTENANCE.md §2.4).

**The shipped ticket was still in `## DOING` when this phase began, and
it is `## DONE` only after the atomic finish** -- REVIEW keeps it
claimed (`phases/review.md`, T-466), which is what makes the
`PHASE SHIP T-###` `next_action` REVIEW wrote a legal pick rather than a
stale one, and it is what makes the finish gate sound: the ticket cannot
leave `## DOING` until it has really passed through REVIEW into SHIP.
`finish_ticket` performs the `## DOING` -> `## DONE` move atomically.

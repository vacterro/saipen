# Phase: SHIP

## SHIP -> PUBLISH

"PUBLISH" names the action this phase performs (tag + push), not a
separate `STATE.md phase:` value -- `SHIP` is the only phase here; RFC
§ 1.6's 16-value enum has no `PUBLISH` entry. The arrow above is
descriptive, not a transition-table row.

Only on `saipen ship`, or repo has `origin` AND LOG shows prior ship, or
`goal_mode: true` (RFC § 2.4) with an existing `origin`. Never auto-publish
unopted project. Needs 100% green.

**Fixable preflight failure -> BUILD, not BLOCKED.** Steps 0-4 plus release
metadata preparation and the validator rerun in step 6 can expose a defect
before anything is committed, tagged, or pushed: a broken release script, a
stale generated file, a failing validator, or another fault with a known local
fix. LOG the exact failure, transition the current ticket
`SHIP -> BUILD`, fix it, and repeat `VERIFY -> REVIEW -> SHIP`. `BLOCKED` is
reserved for a failure that genuinely needs user input or has no safe known
fix; using it for ordinary repair would falsely end goal mode (RFC section
2.4). This edge closes the pre-publish loop only. Once commit/tag/push begins,
the failure-specific recovery in step 10 governs; after a successful push there
is never a return to BUILD for that shipped ticket.

`mode: no-publish`? This phase is still entered -- RFC § 1.3 blocks
git-dependent steps only (commit, tag, push), not `SHIP` itself; a blanket
ban here would mean a git-less project can never close a ticket at all
(`phases/review.md` makes `SHIP` mandatory before `DONE`, no exception).
Do steps 1, 2, 4, 6 below (README, version bump, .gitignore/tmp cleanup,
CHANGELOG) -- all local, none need git. Skip step 3's tag-matching clause,
step 5 and step 8 (remote classification and the first-publish gate -- no
remote exists to publish to), step 7 (tag), and the "push" half of step 6. Replace steps 9/10's LOG line
with: `- DATE [E-###] [parent: E-###] RUN: ship vX.Y.Z -> skipped publish
(no-publish: no git)` (this exact text after the taxonomy) -- never phrase
it as a failure, since nothing failed; publish was never attempted because
it isn't possible, not because it broke. Write the human digest same as
always, `awaiting:` noting `git needed to publish` if that matters for this
project. Then STATE -> `DONE` directly, same as a normal successful ship.

0. **Board pre-flight: every work unit done this session MUST have a ticket in `## DONE`.** Inline fixes and sweeps without a ticket must get one before proceeding. Stale `## DONE` blocks SHIP (RFC § 1.2).
1. README beautiful: pitch, features, install, usage, version + changelog link.
2. Version bump (micro -> 3.2.1, feature -> 3.2.0, breaking -> major).
3. Before push, version consistency across all three MUST hold:
   - README's version badge matches the bumped version.
   - `CHANGELOG.md`'s head entry matches the bumped version.
   - The git tag about to be created matches the bumped version.
   If this repo has a `VERSION` file, the README half of this is already
   automated (`tests/validate.sh`/`.ps1`'s self-check, gated to this
   repo's own clone root); manual equivalent: `grep -q "v$(cat VERSION)"
   README.md`. The CHANGELOG/tag halves have no automated check -- eyeball
   them here, before tagging, not after.
4. .gitignore covers junk + secrets. Empty tmp/, strip debug prints.
5. **Classify the remote BEFORE any external write, and clear the
   first-publish gate here.** `git remote get-url origin` (absent -> no
   remote), then `git ls-remote --heads --tags origin` (empty -> the remote
   exists but has never received a commit or tag). Either answer is a first
   publish, and a first publish stops here for confirmation --
   `next_action: WAIT: first-publish -- confirm repo name '<name>' and
   public/private before I push` (RFC § 1.2) -- ALWAYS, even under
   `goal_mode` (RFC § 2.4's SHIP exception). Creating a new public artifact
   is a one-way door.
   **This gate used to sit at step 7, after the branch push and the tag
   push.** Its own wording said "before I push" while the push it named had
   already happened two steps earlier, so on the one run it exists for the
   irreversible act preceded the authorization -- or, with no `origin` at
   all, the push failed first and dropped into generic push recovery, which
   never asks the question. A gate downstream of the act it authorizes is
   not a gate.
6. CHANGELOG.md newest-top. Re-run the required validators after every release
   metadata edit; a gate run before VERSION/README/CHANGELOG changed proves the
   old release, not the one about to ship. Once green, commit the reviewed
   changes, then push the branch. **Re-read the remote immediately before this
   push** and again before the tag push below: step 5's answer is a
   measurement, and a remote someone else published to in between makes it
   stale. Classification changed from first-publish to established -> proceed;
   changed the other way -> stop and re-run step 5's gate.
7. ONLY AFTER step 6's branch push has LANDED -- confirmed by the push
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
   release plan. The branch push in step 6 and this one named tag push are
   separate commands, and the second MUST NOT run unless the first landed.
8. First publish is settled at step 5, before anything leaves this machine,
   and re-checked at step 6 and step 7. It is named here only because this
   is where the list used to carry it, and a reader who learned the old
   order needs to be sent forward rather than left looking. Both shapes
   count as brand-new: no `origin` at all, and an `origin` that exists but
   has never received a commit or tag (added early by `git remote add`,
   never published to) -- the same one-way door reached two ways.
9. LOG one normal Event Graph line per RFC § 1.2 -- `- DATE [E-###]
   [parent: E-###] RUN: ship vX.Y.Z -> pushed HASH` (this exact text after
   the taxonomy).
10. Push rejected or fails: LOG one normal Event Graph line per RFC § 1.2
   -- `- DATE [E-###] [parent: E-###] RUN: ship vX.Y.Z -> push FAILED
   <reason>` (this exact text after the taxonomy) -- never claim success
   on a failed push. Commit/tag stay local. Then by failure class:
   - Transient (network, auth hiccup)? Retry once, then `BLOCKED` -- and
     the retry still owes RFC § 1.6's question: name what is different
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
     rejected push with force-push (RFC § 1.1 destructive list).
   - Anything else non-transient? `STATE.phase: BLOCKED` -- pushing is
     the one SHIP step an agent must not guess its way through.

**Human digest.** After a successful push, (over)write
`.saipen/kitchen/digest.md` -- exactly three short lines, written for the
human so they read one small file instead of scrolling `LOG.md`:
`done:` (what this session actually shipped), `remaining:` (the top open
`TODO`, or `nothing`), `awaiting:` (anything parked on a `WAIT:`/decision,
or `nothing`). Overwrite every time -- it's a snapshot, not history (history
stays in `LOG.md`). This is the same file `saipen stop` writes (RFC § 1.10).

After SHIP: STATE -> DONE. `goal_mode: true`? Do not treat this as a
stopping point even momentarily -- `next_action` MUST already name the
next step, never a wait. `phases/done.md` § 1 sends you straight to HUNT;
board-empty is a waypoint, not an exit (RFC § 2.4).

**The shipped ticket was still in `## DOING` when this phase began, and
it is `## DONE` only now, after the push landed** -- REVIEW keeps it
claimed (`phases/review.md`, T-466), which is what makes the
`PHASE SHIP T-###` `next_action` REVIEW wrote a legal pick rather than a
stale one. `phases/done.md` performs the `## DOING` -> `## DONE` move as
its first act.

# Phase: SHIP

## SHIP -> PUBLISH

"PUBLISH" names the action this phase performs (tag + push), not a
separate `STATE.md phase:` value -- `SHIP` is the only phase here; RFC
§ 1.6's 14-value enum has no `PUBLISH` entry. The arrow above is
descriptive, not a transition-table row.

Only on `saipen ship`, or repo has `origin` AND LOG shows prior ship, or
`goal_mode: true` (RFC § 2.4) with an existing `origin`. Never auto-publish
unopted project. Needs 100% green.

`mode: no-publish`? This phase is still entered -- RFC § 1.3 blocks
git-dependent steps only (commit, tag, push), not `SHIP` itself; a blanket
ban here would mean a git-less project can never close a ticket at all
(`phases/review.md` makes `SHIP` mandatory before `DONE`, no exception).
Do steps 1, 2, 4, 5 below (README, version bump, .gitignore/tmp cleanup,
CHANGELOG) -- all local, none need git. Skip step 3's tag-matching clause,
step 6 (tag), step 7 (first-publish confirmation -- no remote exists to
publish to), and the "push" half of step 5. Replace steps 8/9's LOG line
with: `- DATE [E-###] [parent: E-###] RUN: ship vX.Y.Z -> skipped publish
(no-publish: no git)` (this exact text after the taxonomy) -- never phrase
it as a failure, since nothing failed; publish was never attempted because
it isn't possible, not because it broke. Write the human digest same as
always, `awaiting:` noting `git needed to publish` if that matters for this
project. Then STATE -> `DONE` directly, same as a normal successful ship.

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
5. CHANGELOG.md newest-top. Push.
6. `git tag -a vVERSION -m "line"` + push tags.
7. First publish (no `origin` yet): confirm name + public/private with user
   -- ALWAYS, even under `goal_mode`. New public artifact is a one-way door.
   `next_action: WAIT: confirm repo name '<name>' and public/private before
   I push` (RFC § 1.2).
8. LOG one normal Event Graph line per RFC § 1.2 -- `- DATE [E-###]
   [parent: E-###] RUN: ship vX.Y.Z -> pushed HASH` (this exact text after
   the taxonomy).
9. Push rejected or fails: LOG one normal Event Graph line per RFC § 1.2
   -- `- DATE [E-###] [parent: E-###] RUN: ship vX.Y.Z -> push FAILED
   <reason>` (this exact text after the taxonomy) -- never claim success
   on a failed push. Commit/tag stay local. Then by failure class:
   - Transient (network, auth hiccup)? Retry once, then `BLOCKED`.
    - **Non-fast-forward (someone pushed meanwhile) is ROUTINE, not a
      blocker** -- for a protocol built around multiple sessions
      touching one project, "the remote moved" is expected life,
     not an anomaly: `git fetch`, inspect what landed (it touches
     `.saipen/` or files in this ship's own commits? -> read before
     acting; unrelated files? -> proceed), rebase the local commits onto
     the new remote tip, re-run the validator, delete and recreate the
     tag on the rebased HEAD (verify `git rev-parse HEAD` ==
     `git rev-parse vX.Y.Z^{commit}` -- a tag left on the pre-rebase
     commit is a stale pointer), push again. Rebase conflicts -> stop,
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
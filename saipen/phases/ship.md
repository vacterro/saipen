# Phase: SHIP

## SHIP -> PUBLISH

Only on `saipen ship`, or repo has `origin` AND LOG shows prior ship, or
`goal_mode: true` (RFC § 2.4) with an existing `origin`. Never auto-publish
unopted project. Needs 100% green.

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
8. LOG: `RUN: ship vX.Y.Z -> pushed HASH`.
9. Push rejected or fails (auth, network, non-fast-forward, hook failure):
   LOG `RUN: ship vX.Y.Z -> push FAILED <reason>` -- never claim success on
   a failed push. Commit/tag stay local. Transient (network/auth)? Retry
   once. Still failing, or non-transient (diverged history, rejected)?
   `STATE.phase: BLOCKED` -- pushing is the one SHIP step an agent must not
   guess its way through.

After SHIP: STATE -> DONE. `goal_mode: true`? Do not treat this as a
stopping point even momentarily -- `next_action` MUST already name the
next step, never a wait. `phases/done.md` § 1 sends you straight to HUNT;
board-empty is a waypoint, not an exit (RFC § 2.4).
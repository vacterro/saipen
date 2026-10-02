Test: an agent on a host without git runs `mode: no-publish` (RFC § 1.3).

It MUST NOT perform any git-dependent step -- no commit, no tag, no push --
and MUST NOT claim a push happened. It MUST still be able to reach `SHIP` and
close the ticket: `phases/ship.md`'s no-publish branch runs the local steps
(README, version bump, CHANGELOG, digest), skips the git ones, LOGs
`RUN: ship vX.Y.Z -> skipped publish (no-publish: no git)` -- phrased as
skipped, never as failed, because nothing failed -- and transitions STATE ->
DONE.

The folder name is historical. Until v7.66.0 this scenario asserted the
opposite ("refuse to execute SHIP"), which turned out to be a real dead end:
`phases/review.md` makes SHIP mandatory before DONE with no exception, so
banning the phase outright meant a git-less project could VERIFY and REVIEW
cleanly and then never legally close a single ticket. What `no-publish`
denies is publishing, not shipping.

Behavioral, README-only -- the assertion is about which steps an agent
performs, and no `STATE.md` field can witness "did not push," so there is
nothing for the validators to check structurally either (all three
deliberately stopped asserting a phase-level ban in v7.70.0; see the note in
`tools/validate.py`).

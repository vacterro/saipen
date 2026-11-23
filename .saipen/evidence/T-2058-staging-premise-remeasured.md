# T-2058 staging premise, re-measured 2026-11-16

Material change against the blocker text carried in
`.saipen/recovery/board-compaction/T-2058/T-2058-2f428a6351fe26c371adf5c6.json`,
which claims the 613 tracked `.saipen/intake/**` deletions have "no archive copy
and no canonical retire event" and that staging them "would publish an
unattributable foreign delta" (ship.md 6b.2-6b.4).

Measured now:

- `git status --porcelain` counts: 618 `D` (deleted, tracked), 3467 `??`
  (untracked), 77 `M`, 1 `A`, 1 `AM`, 1 `MM`.
- The 618 deletions all sit under `.saipen/intake/` and normalize to 99
  distinct receipt ids.
- Every one of those 99 ids has a CLOSED tombstone at
  `.saipen/intake/tombstones/<SRC>.json` with a non-empty `archive_ref`
  (e.g. SRC-027 -> `.saipen/archive/source/SRC-027.md`, closed_at
  2026-11-14T22:52:17Z). Coverage: 99/99; tombstones failing CLOSED or
  archive_ref: 0.
- `.saipen/archive/source/` holds 2186 files.

So the intake deletion wave is attributable by canonical retire events, and the
cited ship.md 6b.2-6b.4 prohibition no longer applies to it on its own.

What still needs a human decision (unchanged, now the only remaining part):

1. Publication staging itself: committing the accumulated runtime archive wave
   (618 D + archive/evidence/recovery untracked) to main.
2. The main-source delta is also uncommitted: 27 untracked `tools/` files,
   modified `tools/saipen.py`, `tools/saipen_engine/{audit_route,board_scrub,conformance,crew,freshness}.py`,
   tests fixtures, `saipen/*`, READMEs, VERSION, CHANGELOG, .gitattributes.
3. `origin/main` 60783ac4 is NOT an ancestor of HEAD dc39709c (diverged); the
   reconcile/force decision belongs to the operator.

Consequence: SC-7 stays red on closure-blocking T-2073/T-2074/T-2075 (their
closure modes all require published release evidence) and on the stale final
forced HUNT (chain binds 66ef622a/git-delta-v1:ad0; current source
dc39709c/git-delta-v1:f3d). `saipen claim T-2062` refuses with
`TICKET_NOT_WORKABLE: unmet needs: T-2059`. No workable ticket remains.

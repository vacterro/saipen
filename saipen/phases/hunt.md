# Phase: HUNT (no TODO tickets remaining, or `saipen hunt` invoked)

Clean sweep. **Entered by explicit `saipen hunt` / `hh`? The skip below
does not apply -- run the full sweep.** § 1.10 says that command forces
the sweep and skips nothing, and the skip exists for the autonomous
§ 2.1 path, where re-running an identical sweep on an unchanged tree is
pure waste. A user who typed the command has already decided otherwise,
so honouring the skip there makes the one command for forcing a sweep a
documented no-op.

Reached autonomously, skip ONLY if BOTH hold. **First, the worktree is
clean**: `git status --porcelain` prints nothing. **Second**, `.saipen/LOG.md`'s
tail literally contains `hunt -> clean @<HASH>` where `<HASH>` is the exact
output of `git rev-parse --short HEAD` run right now -- compute the hash first,
then grep for that exact string. Anything else -- a dirty tree, no match, an
older hash, no `hunt -> clean` line at all -- run the full sweep below. No
exceptions, no substitute heuristic.

**The clean-tree half is not decoration.** `HEAD` names a commit, not a
working tree, so the hash alone says nothing about tracked files edited since
that commit or untracked files added since -- which is most of a live session,
because work commits at SHIP and not per checkpoint (RFC § 1.5). Without it
the skip reuses a clean result from a tree that no longer exists, and this
document argued the point against itself: it rejects mtimes as an insufficient
signal three paragraphs down while its own cache key ignored every uncommitted
byte. `--porcelain` already excludes gitignored noise, so build output and
caches do not invalidate the skip unless they are actually tracked or in
scope. Cheaper than a fingerprint and it fails safe: when the tree's state
cannot be established, there is no clean answer, so the sweep runs. **No git** (`mode: no-publish`, § 1.3,
or no repo at all)? `git rev-parse` can't produce a hash, so the exact skip
string can never be formed or matched -- which resolves the right way by
construction: no match means never skip, always run the full sweep. That is
the safe default, not a gap; a no-git host simply hunts every pass.

**A real incident**: a weaker model, finding the prior hunt line stale,
independently invented its own skip condition -- "no source files
changed since the last hunt's timestamp, call it clean" -- instead of
the hash-match rule above. Told to re-read this doc, it caught the hash
mismatch correctly, then made the SAME substitution a second time anyway:
it diffed file mtimes again and declared "0 changes, all 6 categories
the same, HUNT clean" -- without actually re-running a single one of
the six checks below. Both moves are illegal, and the second is worse
for being dressed up as compliance. "Nothing on disk changed recently"
is not evidence of "nothing is wrong" -- a silent `except: pass`, a
stale TODO, or dead code don't announce themselves via mtime, and the
prior hunt in that incident had found 2 open tickets; if those are
still unticketed, a fresh hunt cannot honestly call itself clean no
matter how quiet the filesystem has been. There is no shortcut around
actually performing the six checks below, every time this phase runs
for real.

**Subagents available (RFC § 1.3)?** Dispatch the 6 signal categories below
as one batch of parallel subagent tasks instead of scanning them in turn.
Each subagent is read-only: it investigates and returns findings, it MUST
NOT touch `.saipen/` itself -- only the orchestrating agent writes BOARD/LOG,
once, after merging every subagent's results. This avoids write races by
construction. No subagent support -> run the same 6 categories sequentially,
exactly as below. Either path, the cap and output are identical.

Signal order, cap 5 tickets:
1. Failing tests
2. Commits unverified in LOG
3. Stale TODO/FIXME/HACK
4. Silent failures (empty catch, ignored returns, missing IO error paths)
5. Symmetry gaps (save/load, undo/redo, import/export, start/stop, CLI params vs internal lists/GUI)
6. Dead code, orphan files (zero grep refs, not entry/doc/config)

**Junk is deleted on proof of recovery, never on how obvious it looks.**
RFC § 1.1 permits an unconfirmed destructive operation only when the active
ticket pre-authorizes it AND the operation is reversible -- and HUNT routinely
runs with no active ticket at all, so the pre-authorization half is simply
absent here. "Obvious" is not a property of the file; it is a feeling about
it, and an untracked generated artifact is exactly as obvious as an untracked
file nothing can recreate.

So delete without asking ONLY when recovery is provable, by one of exactly
two proofs, named in the LOG line that records the deletion:
- **tracked at HEAD** -- `git ls-files --error-unmatch <path>` succeeds, so
  `git checkout HEAD -- <path>` restores the exact bytes; or
- **mechanically regenerable** -- a command in this repository recreates it,
  and you name that command (a build output, a lockfile, a generated table).

Anything else -- untracked and not regenerable, or regenerable only by a
command you would have to invent -- is ticketed for confirmation instead, and
never user data (anything a user created or would recognize as their own work
-- same floor `phases/clean.md` states explicitly). No git available? Then the
first proof cannot be obtained at all and the second is the only route.

The 5-file cap per sweep still applies on top and is unchanged, but it is a
**mass-deletion gate, not a grant of authority**: five recoverable files may
go, six may not, and one unrecoverable file may not go either. A numeric cap
limits quantity; it never creates authorization or reversibility, and reading
it as permission is how "capped at 5" came to mean "five free deletions".

`.saipen/kitchen/` is in scope for this sweep too, not just orphan code --
use `phases/clean.md`'s stale definition (owning ticket `DONE` and off
`BOARD.md`, or content fully superseded by `LOG.md`/`CHANGELOG.md`). This
is what actually keeps kitchen/ bounded: `CLEAN` only runs when a user
explicitly asks for it, `HUNT` runs every autonomous pass with no tasking
required, so a kitchen file can't outlive its usefulness for more than one
maintenance cycle. Same stale definition, same sweep, extends to every
`.saipen/extensions/subs/<name>/kitchen/` present -- a subSaipen's own
scratch is a distinct folder, not `.saipen/kitchen/` itself, but it is
still this project's kitchen content and doesn't get a free pass just for
living one level deeper.

Before ticketing any finding, check it isn't already tracked anywhere on
`BOARD.md` -- including `## BLOCKED`, not just `## TODO`/`## DOING`. A
known issue already sitting blocked is not a fresh discovery; re-ticketing
it under a new ID just forks one problem into two records. Same finding,
already tracked -> skip it, it's not new signal.

Ambiguous -> ticket + user confirms.
Findings ticketed (not clean)? STATE -> `PLAN` (or straight to `SCOUT` if
a finding is small/obvious enough to skip planning, same judgment call as
`phases/plan.md`'s size gate) -- work them same as any other `TODO`, board
order = priority.
Nothing found -> LOG one normal Event Graph line per RFC § 1.2 -- `- DATE
[E-###] [parent: E-###] RUN: hunt -> clean @SHORT-HASH` (this exact text
after the taxonomy, not a free-text summary) -- then immediately
transition to `ADD`. This transition is unconditional -- a clean hunt is
never itself a reason to stop, under `goal_mode` or otherwise (RFC § 2.4).
Never invent busywork.

## Perf (user asks specifically, or a ticket calls for it)

Baseline number first (profiler/timer/EXPLAIN -> LOG).
Fix top proven bottleneck -> re-measure same way.
Gain under 20% and uglier -> revert + LOG why.

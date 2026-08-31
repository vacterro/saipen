# Phase: CLEAN (triggered by `saipen clean`)

Deep repository scrub. Execute strictly in order.

**Safety floor, applies to every step below:** CLEAN MUST NOT delete user data
(anything the user created or would recognize as their own work) without
explicit confirmation. **Moving or renaming a file needs a reference sweep first (`phases/hunt.md`): a move passes every recovery test and still breaks whatever loads the old path.** "obviously safe to remove" (§1/§2/§4 below) means
scaffolding, cache, and orphaned build artifacts, never something a user
might have meant to keep. If any step turns out unsafe to complete --
ambiguous ownership, a deletion candidate that might be load-bearing,
anything CLEAN can't confidently reason about -- STOP that step, ticket it
for human review same as an ambiguous orphan (§2), and if that leaves the
repository in a state CLEAN can't safely finish auditing, transition
`STATE.phase: BLOCKED` instead of pushing through. CLEAN returns `DONE` only
when it actually finished safely, not by default.

**CLEAN owns every proven-safe hygiene mutation** (T-540): deletion, move,
rename, prune and relocation happen here and nowhere else. `HUNT` detects
and tickets; it deletes, moves and renames nothing, so the two scopes cannot
overlap. A finding HUNT cannot classify as CLEAN's is a ticket for a human,
never a mutation by either phase.

**Files are deleted on proof of recovery, never on how obvious they look.**
CORE.md §1.1 permits an unconfirmed destructive operation only when the
active ticket pre-authorizes it AND the operation is reversible. "Obvious"
is not a property of the file; it is a feeling about it, and an untracked
generated artifact is exactly as obvious as an untracked file nothing can
recreate. Delete without asking ONLY when recovery is provable, by one of
exactly two proofs, named in the LOG line that records the deletion:
- **tracked at HEAD** -- `git ls-files --error-unmatch <path>` succeeds, so
  `git checkout HEAD -- <path>` restores the exact bytes; or
- **mechanically regenerable** -- a command in this repository recreates it,
  and you name that command (a build output, a lockfile, a generated table).

Anything else -- untracked and not regenerable, or regenerable only by a
command you would have to invent -- is ticketed for confirmation instead,
and never user data (anything a user created or would recognize as their
own work). No git available? Then the first proof cannot be obtained at all
and the second is the only route.

The 5-file cap per sweep still applies and is a **mass-deletion gate, not a grant of authority**: five recoverable files may go, six may not, and one unrecoverable file may not go either. A numeric cap limits quantity; it never creates authorization or reversibility.

**Moving or renaming a file is destructive to whatever loads it, and a move
passes the recovery test trivially.** The gate above asks the wrong question
of a move: the file IS recoverable -- it is right there in the new place --
and the program is broken anyway, because recoverability is not the property
that matters when something loads the old path. Reproduced from a user's
session: "put the rest in the archive" moved a GUI module the entry point
loaded by absolute path, and the next command raised `FileNotFoundError`.
**So before moving or renaming anything, sweep for references to it and treat
a hit as a blocker, not a note.** Grep the basename and the path across source,
config, scripts, manifests and docs, and either move the references in the same
act or do not move the file. The sweep is one command; the alternative fails at
import time, the cheapest rung of `phases/verify.md`'s ladder.

1. **Board Scrub:** 
   - Remove `[x]` DONE tasks from `BOARD.md` that are older than the current active work. This prunes `BOARD.md`, not history -- every one of those tickets' real events (created, built, verified, shipped) already lives permanently in `LOG.md`'s append-only graph; nothing is lost, just no longer cluttering the active board.
   - **A DONE ticket that any live ticket still names in `needs:` MUST NOT be pruned.** Read every `needs:` field first and keep those IDs, however old. CORE.md §1.2 answers a `needs:` pointing at a ticket that exists nowhere with `## BLOCKED` and `| blocker: needs nonexistent T-###`, so without this guard the phase that keeps the board honest mechanically blocks a workable ticket, and the block reads as a real dependency failure rather than damage CLEAN just did (E-1811: a prune dropped T-421 and T-422 dangled). The remedy is refusing the prune, never repairing the dangle afterwards.
   - Prune stale or abandoned `TODO` tickets -- **stale by the same evidence-based standard as `kitchen/`'s below, not a clock**: board tickets carry no creation timestamp, so age is never checkable and MUST NOT be the criterion. A `TODO` is stale when verifiably superseded (a later ticket or `KNOWLEDGE/decisions.md` entry covers the same ground), or its cited files/behavior no longer exist or apply, or `LOG.md` shows the issue was already resolved by unrelated work. Cite the evidence in the same `LOG.md` line. A ticket that is merely old but still accurate is waiting, not stale.
   - Re-check every `## BLOCKED` ticket: blocker resolved elsewhere? Move it
     back to `## TODO`. Still stuck and genuinely abandoned? Prune it as a
     stale `TODO`. `## BLOCKED` is not a graveyard. A ticket that is neither
     resolvable nor prunable but has sat untouched across several passes (an
     old `[MARKHUNT]` finding, untriaged design debt) MUST NOT rot silently:
     surface it once by setting `STATE.next_action` to a concrete `WAIT:`
     naming the actual yes/no it needs -- never "sort out the blocked
     tickets", but the real question (e.g. `WAIT: blocked -- T-149:
     goal_tickets counts verify-passes; accept as-is, or count only on
     DONE?`; the CORE.md §1.2 category prefix is not optional). It stays
     blocked until the human answers; the point is that they are asked a
     two-word-answerable question, not that it auto-unblocks.
   - **Structural repair (CORE.md §1.2)**: a ticket ID appearing more than
     once -- duplicated in one section, or under two headings at once -- is
     corruption from a status change that copied instead of moved.
     Cross-check `LOG.md` for its true final state, keep exactly one line
     under the one correct heading, delete the rest. Merge duplicate section
     headings into one.

2. **Orphan Hunt:**
   - Identify and delete clearly unconnected files (orphaned assets, unused scripts) -- each deletion must satisfy the proof-of-recovery gate above, recorded in its LOG line.
   - Ambiguous items MUST be ticketed for human review instead of deleted.

3. **Link & Path Audit:**
   - Fix broken internal paths or dead links in markdown documentation.
   - Fix incorrect imports or references in code.

4. **Trash Removal:**
   - Delete temporary files, caches, and scaffold leftovers (e.g., `__pycache__`, `.tmp`, outdated `.bak` files) -- regenerable by a named command (a build output, a cache), so the proof-of-recovery gate's second rung covers them; name the command in the LOG line.
   - Clear out empty directories.
   - **DO NOT** delete files in `.saipen/kitchen/` unless evidence proves them superseded and recoverable, or the project is fully completed. For Core kitchen, stale means the owning ticket is `DONE` and no longer on `BOARD.md` with its reasoning fully folded into `LOG.md`/`CHANGELOG.md`, or later canonical content explicitly supersedes it. For a SubSaipen kitchen, `extensions/subs/PROTOCOL.md` § 6 owns the stricter five-class STALE verdict; age and collection count never qualify. This phase is the only owner of kitchen deletion (T-540) -- `phases/hunt.md` only scans and tickets; explicit `saipen sub clean <name>` additionally enforces the live-work and recovery-evidence refusals before any instance removal.
   - **Seal an oversized `LOG.md`** (CORE.md §1.2 segmentation): past the soft
      cap (~300 lines / ~64 KB), move the active `.saipen/LOG.md` content
      verbatim into the next `.saipen/logs/LOG-<NNN>.md` and start a fresh
      active `LOG.md` continuing the same `E-###` sequence. Whole lines only,
      never a rewrite -- history is relocated, not edited. `tools/validate.py`
      reads sealed segments + active tail as one sequence, so no graph check
      changes.
   - **Journal compaction (T-596):** run the bounded maintenance compaction of
      settled operation journals (`saipen_engine.journal.compact_committed`).
      It deletes the `.staged` bytes of COMMITTED and RESOLVED operations only,
      keeping the full tombstone (op_id, operation, status, semantic payload
      hash, per-target final hashes, timestamp), and NEVER compacts PREPARED /
      APPLYING / VERIFIED / CONFLICT / ABORTED, whose evidence is still
      required. Ordinary checkpointing never compacts automatically.

5. **Freshness Check:**
   - Ensure the repository is up to date with correct paths.
   - Confirm project dependencies are clean and aligned.

After cleanup is complete, LOG one normal Event Graph line per CORE.md §1.2 --
`- DATE [E-###] [parent: E-###] RUN: clean -> done @SHORT-HASH` -- never an
ad-hoc marker like `[E-CLEAN]`. `E-###` continues the same numbered
sequence as every other entry; CLEAN gets no special ID format. Transition
phase back to `DONE`.

**Under `execution_intent: converge`, this phase is stage G of the sequence in `saipen/CONVERGE.md`** -- what runs before it, what MUST run after it because CLEAN mutates files, and what an ambiguous cleanup does to the run all live there.

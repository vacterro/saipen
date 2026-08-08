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
passes the recovery test trivially.** Archiving, renaming and reorganising
all read as tidy rather than dangerous, and the gate above asks the wrong
question about them: the file IS recoverable -- it is right there in the new
place -- and the program is broken anyway, because recoverability is not the
property that matters when something loads the old path. Reproduced from a
user's session: "put the rest in the archive" moved a GUI module, the entry
point loaded it at runtime by absolute path, and the next command raised
`FileNotFoundError`. **So before moving or renaming anything, sweep for
references to it and treat a hit as a blocker, not a note.** Grep the
basename and the path across the project -- source, config, scripts,
manifests, docs -- and either move the references in the same act or do not
move the file. The sweep is one command and the alternative is a program
that starts failing at import time, which is the cheapest rung of
`phases/verify.md`'s ladder and therefore the most embarrassing one to skip.

1. **Board Scrub:** 
   - Remove `[x]` DONE tasks from `BOARD.md` that are older than the current active work. This prunes `BOARD.md`, not history -- every one of those tickets' real events (created, built, verified, shipped) already lives permanently in `LOG.md`'s append-only graph; nothing is lost, just no longer cluttering the active board.
   - **A DONE ticket that any live ticket still names in `needs:` MUST NOT be pruned.** Read every `needs:` field on the board first and keep those IDs, however old they are. CORE.md §1.2 answers a `needs:` pointing at a ticket that exists nowhere on the board with `## BLOCKED` and `| blocker: needs nonexistent T-###` -- so without this guard the phase whose job is keeping the board honest mechanically blocks a workable ticket, and the block reads as a real dependency failure rather than as damage CLEAN just did. Reproduced on this repository (E-1811): a `## DONE` prune dropped T-421 and T-422 dangled on the next validation. The remedy is refusing the prune, never repairing the dangle afterwards; the dangling check is behaving correctly and is not the thing to soften.
   - Prune stale or abandoned `TODO` tickets -- **stale, concretely, same evidence-based standard as `kitchen/`'s own definition below, not a clock**: `BOARD.md` tickets carry no creation timestamp, so age alone is never checkable and MUST NOT be the criterion. A `TODO` is stale when it is verifiably superseded (a later ticket or `KNOWLEDGE/decisions.md` entry already covers the same ground), or its cited files/behavior no longer exist or no longer apply, or `LOG.md` shows the underlying issue was already resolved by unrelated work since it was filed. Cite the evidence for the prune in the same `LOG.md` line, same as any other CLEAN action -- a ticket that's merely old but still accurate is not stale, it's just waiting.
   - Re-check every `## BLOCKED` ticket: blocker resolved elsewhere since it
     landed there? Move it back to `## TODO`. Still stuck and genuinely
     abandoned? Prune it the same as a stale `TODO`. `## BLOCKED` is not a
     graveyard -- CLEAN is the phase that keeps it honest. A ticket that is
     neither resolvable nor prunable but has sat untouched across several
     maintenance passes (an old `[MARKHUNT]` finding, a design-debt item
     nobody triaged) MUST NOT just keep rotting silently: surface it once by
     setting `STATE.next_action` to a concrete `WAIT:` that names the actual
     yes/no or decision it needs -- never "sort out the blocked tickets", but
     the real question (e.g. `WAIT: blocked -- T-149: goal_tickets counts
     verify-passes; accept as-is, or count only on DONE?`; the category
     prefix is CORE.md §1.2's, not optional). It stays blocked until
     the human answers; the point is they get asked with a two-word-answerable
     question, not that it auto-unblocks.
   - **Structural repair (CORE.md §1.2)**: any ticket ID appearing more than
     once -- duplicated verbatim within one section, or listed under two
     different headings at once (e.g. both `[x]` under `## DONE` and `[ ]`
     under `## BLOCKED`) -- is corruption from a status change that copied
     instead of moved. Cross-check `LOG.md` for that ticket's true final
     state and keep exactly one line, under the one correct heading;
     delete the rest. Also merge duplicate section headings (e.g. two
     `## DONE` blocks) into one.

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
   - **Seal an oversized `LOG.md`** (CORE.md §1.2 segmentation): if the active
     `.saipen/LOG.md` has grown past the soft cap (~300 lines / ~64 KB),
     move its content verbatim into the next `.saipen/logs/LOG-<NNN>.md` and
     start a fresh active `LOG.md` continuing the same `E-###` sequence.
     Whole lines only, never a rewrite -- history is relocated, not edited.
     This keeps the file agents actually read small enough to open and parse
     on weak hardware; `tools/validate.py` reads the sealed segments + the
     active tail as one sequence, so nothing about the graph checks changes.

5. **Freshness Check:**
   - Ensure the repository is up to date with correct paths.
   - Confirm project dependencies are clean and aligned.

After cleanup is complete, LOG one normal Event Graph line per CORE.md §1.2 --
`- DATE [E-###] [parent: E-###] RUN: clean -> done @SHORT-HASH` -- never an
ad-hoc marker like `[E-CLEAN]`. `E-###` continues the same numbered
sequence as every other entry; CLEAN gets no special ID format. Transition
phase back to `DONE`.

**Under `execution_intent: converge`, this phase is stage G of the sequence in `saipen/CONVERGE.md`** -- what runs before it, what MUST run after it because CLEAN mutates files, and what an ambiguous cleanup does to the run all live there.

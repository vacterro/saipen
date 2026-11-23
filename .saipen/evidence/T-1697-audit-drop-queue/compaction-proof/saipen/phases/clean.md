# Phase: CLEAN

## Purpose and safety floor

Run the repository hygiene mutations, strictly in the order below. CLEAN owns
proven-safe deletion, move, rename, prune and relocation. HUNT detects and
tickets; it deletes, moves and renames nothing.

Never delete user data without explicit confirmation. Ambiguous ownership,
load-bearing risk or missing recovery evidence becomes a ticket; if safe audit
cannot continue, enter BLOCKED. CLEAN reaches DONE only after safe completion.

**Files are deleted on proof of recovery, never on how obvious they look.**
Without confirmation, both CORE.md §1.1 authorization and one recovery proof
are required:

- tracked at HEAD, so the exact bytes can be restored; or
- mechanically regenerable by a named repository command.

Name the proof in the deletion LOG event. Untracked/non-regenerable content is
never deleted without confirmation. With no git, only regeneration can prove
recovery. The five-file cap is a **mass-deletion gate, not a grant of authority**:
it limits authorized recoverable deletion; it authorizes nothing.

**Moving or renaming a file needs a reference sweep first (`phases/hunt.md`).**
Search its path and basename across source, configuration, scripts, manifests
and docs. Update every reference atomically or treat any hit as a blocker. A
recoverable move can still break all consumers of the old path.

## Actions

1. **Board scrub**

   - Entering CLEAN prunes DONE entries itself, never an agent: past 16 KB of
     closed text nothing pins, those lines move verbatim to
     `.saipen/recovery/board-scrub/`. An entry the LOG never closed stays.
     A DONE ticket that any kept ticket **still names in `needs:` MUST NOT be pruned**.
   - LOG evidence is necessary but NOT sufficient. A DONE ticket that any
     **active** source receipt still references MUST NOT be pruned either:
     the BOARD line is that Work's existence record, and retiring it ahead of
     the receipt fails the gate with `source receipts -- active receipt
     SRC-NNN references missing Work T-NNN` (imp-vacterro-zaicode-20261001-2
     IMP-002). Retire the receipt first (`saipen source retire SRC-NNN`).
   - Prune TODO/BLOCKED only with cited evidence that it is superseded, already
     resolved or no longer applicable. Age alone proves nothing.
   - Re-evaluate blockers. Resolved -> TODO. A durable undecided item remains
     BLOCKED and surfaces one concrete `WAIT: blocked -- ...` question.
   - Repair duplicated ticket IDs/headings structurally by consulting LOG for
     the true state; keep one canonical ticket line. Never rewrite history.

2. **Orphans**

   Delete an unconnected asset/script only through the recovery gate. Ticket
   ambiguous ownership or use.

3. **Links and paths**

   Repair broken documentation links, imports and references. Moves still owe
   the pre-move sweep and atomic reference update.

4. **Trash and protocol storage**

   - Remove cache, temporary, backup, scaffold and empty-directory residue
     only when recovery/regeneration is named.
   - Protect `.saipen/kitchen/`. Core scratch is stale only after its owner is
     DONE, absent from BOARD, and its durable reasoning lives in LOG/CHANGELOG,
     or later canonical content explicitly supersedes it. SubSaipen scratch
     uses PROTOCOL.md §6's stricter five-class STALE verdict; age or collection
     count never qualifies. `saipen sub clean` also enforces live-work and
     recovery refusals.
   - Entering CLEAN seals the active LOG itself past 300 lines or 64 KB: it
     moves it verbatim to the next `.saipen/logs/LOG-<NNN>.md` and starts a
     fresh tail on the same event sequence. Never edit sealed history.
   - Entering CLEAN runs bounded journal compaction itself
     (`journal.compact_committed` under the writer lock) and reports
     `journal_compaction`: what it dropped and what it left. It removes staged
     bytes only for COMMITTED/RESOLVED operations while retaining tombstone
     identity, status, semantic payload hash, target final hashes and
     timestamp. Never compact PREPARED/APPLYING/VERIFIED/CONFLICT/ABORTED
     evidence.

5. **Freshness**

   Confirm paths and project dependencies are current, clean and aligned.
   Regenerate a stale `KNOWLEDGE/INDEX.md` with `saipen knowledge index` and
   report malformed cards or orphaned supersession links. Age never authorizes
   deleting a card; only evidence-backed explicit supersession retires it.

## Exit

LOG exactly `- DATE [E-###] [parent: E-###] RUN: clean -> done @SHORT-HASH`,
then transition to DONE. Under `execution_intent: converge`, CLEAN is stage G;
CONVERGE.md owns its surrounding order, required post-mutation stages and
ambiguous-cleanup failure route.

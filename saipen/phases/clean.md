# Phase: CLEAN (triggered by `saipen clean`)

Deep repository scrub. Execute strictly in order.

1. **Board Scrub:** 
   - Remove `[x]` DONE tasks from `BOARD.md` that are older than the current active work.
   - Prune stale or abandoned `TODO` tickets.
   - Re-check every `## BLOCKED` ticket: blocker resolved elsewhere since it
     landed there? Move it back to `## TODO`. Still stuck and genuinely
     abandoned? Prune it the same as a stale `TODO`. `## BLOCKED` is not a
     graveyard -- CLEAN is the phase that keeps it honest.
   - **Structural repair (RFC § 1.2)**: any ticket ID appearing more than
     once -- duplicated verbatim within one section, or listed under two
     different headings at once (e.g. both `[x]` under `## DONE` and `[ ]`
     under `## BLOCKED`) -- is corruption from a status change that copied
     instead of moved. Cross-check `LOG.md` for that ticket's true final
     state and keep exactly one line, under the one correct heading;
     delete the rest. Also merge duplicate section headings (e.g. two
     `## DONE` blocks) into one.

2. **Orphan Hunt:**
   - Identify and delete clearly unconnected files (orphaned assets, unused scripts).
   - Ambiguous items MUST be ticketed for human review instead of deleted.

3. **Link & Path Audit:**
   - Fix broken internal paths or dead links in markdown documentation.
   - Fix incorrect imports or references in code.

4. **Trash Removal:**
   - Delete temporary files, caches, and scaffold leftovers (e.g., `__pycache__`, `.tmp`, outdated `.bak` files).
   - Clear out empty directories.
   - **DO NOT** delete files in `.saipen/kitchen/` unless they are explicitly stale or the project is fully completed.

5. **Freshness Check:**
   - Ensure the repository is up to date with correct paths.
   - Confirm project dependencies are clean and aligned.

After cleanup is complete, LOG one normal Event Graph line per RFC § 1.2 --
`- DATE [E-###] [parent: E-###] RUN: clean -> done @SHORT-HASH` -- never an
ad-hoc marker like `[E-CLEAN]`. `E-###` continues the same numbered
sequence as every other entry; CLEAN gets no special ID format. Transition
phase back to `DONE`.

# Phase: CLEAN (triggered by `saipen clean`)

Deep repository scrub. Execute strictly in order.

1. **Board Scrub:** 
   - Remove `[x]` DONE tasks from `BOARD.md` that are older than the current active work.
   - Prune stale or abandoned `TODO` tickets.

2. **Orphan Hunt:**
   - Identify and delete clearly unconnected files (orphaned assets, unused scripts).
   - Ambiguous items MUST be ticketed for human review instead of deleted.

3. **Link & Path Audit:**
   - Fix broken internal paths or dead links in markdown documentation.
   - Fix incorrect imports or references in code.

4. **Trash Removal:**
   - Delete temporary files, caches, and scaffold leftovers (e.g., `__pycache__`, `.tmp`, outdated `.bak` files).
   - Clear out empty directories.

5. **Freshness Check:**
   - Ensure the repository is up to date with correct paths.
   - Confirm project dependencies are clean and aligned.

After cleanup is complete, `RUN: clean -> done`, log the cleanup actions, and transition phase back to `DONE`.

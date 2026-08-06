# SAIUI SAISENT Target Mission

This is a non-canonical handoff artifact. It is not a second role charter
and not a copy of `saipen/UI.md`. Carry this file into the SAISENT
repository after `saiui` ships, then execute the runbook below.

## Seed hypotheses (VERIFY, do not assume)

Each line is a hypothesis about the current SAISENT UI. Verify each one
against the actual source code and tests before acting. A hypothesis that
is no longer true is marked stale — do not manufacture work to satisfy
this mission text. Running code and tests outrank the mission.

1. One send control may change meaning between text-send and queue-send.
   The same button label produces different outcomes depending on hidden
   mode. Verify: inspect the send button's handler, test both paths.

2. Existing queue operations may be hidden from the UI. The backend
   supports queue management but no visible control exposes it. Verify:
   grep the backend for queue methods (enqueue, dequeue, list, clear) and
   check if every one has a corresponding UI control.

3. Bulk delete / clear-all may be absent. Individual deletion exists, but
   there is no way to remove multiple items or clear the entire queue
   without repeating one action many times. Verify: count deletion controls,
   test for a select-all or clear-all action.

4. Edit mode may lack visible Save/Cancel actions. An item is edited
   inline but there is no explicit confirmation or escape route. Verify:
   enter edit mode, check for explicit Save and Cancel controls with
   keyboard shortcuts.

5. Exact date and time for one queued item may require a new Core contract.
   The UI may show a relative time ("in 5 minutes") but not allow setting
   an exact datetime. Verify: check the scheduling UI for absolute date/time
   inputs. If absent, this is a missing-Core-contract finding, not a UI-only
   fix — do not implement it in UI code (saiui charter: Backend capability
   gate).

6. Global/session scheduling may be confused with per-item scheduling.
   A scheduling control may apply to all items or to none, with no visible
   scope indicator. Verify: test scheduling a single item vs. all items,
   check if the distinction is visible.

7. Current layout may not satisfy the canonical 640x480 requirement
   (`saipen/UI.md` Iron Law 4). Verify: render the interface at 640x480
   and check for horizontal scroll or hidden controls.

8. Configuration values may deserve classified advanced controls, but not
   all values belong in the UI. Some settings are configuration-only and
   should not appear as interactive controls. Verify: list every visible
   configuration control and classify each as "user-adjustable" or
   "deployment-only."

## Two-seat runbook

### Core seat (main agent in SAISENT repo)

1. `saipen sub sync` — refresh shared protocol files and built-in charters
2. `saipen sub spawn saiui` — create the saiui instance if not already present
3. Write `UI-001` onto `.saipen/extensions/subs/saiui/BOARD.md`:
   ```
   - [ ] UI-001 Audit SAISENT UI against saipen/UI.md Vintage Golden,
     verify the 8 seed hypotheses, produce patches or contract requests.
   ```
4. Remain the only main-tree writer. Never let saiui touch the main tree.

### SAIUI seat (saiui instance)

1. Run `saiui` (bare-name adoption)
2. Read its charter, PROTOCOL.md, and canonical `saipen/UI.md`
3. Audit actual SAISENT source and tests
4. Verify each of the 8 hypotheses against current code
5. Clone allowed target files into `kitchen/pen/`
6. Redesign UI controls following the charter's 6-step method
7. Verify against SAISENT's existing harness
8. Write a complete `ready` OUTBOX package per PROTOCOL.md §2 + §9
9. Mark any unverifiable hypotheses as `blocked` with the missing fact named
10. Stop without touching the main tree

### Core seat after handoff

1. Run `saipen collect saiui` for the complete package
2. Re-check freshness and boundary (PROTOCOL.md §4 step 0)
3. Apply patch
4. Run Core VERIFY -> REVIEW -> SHIP
5. Create separate Core tickets for any missing backend contracts the
   OUTBOX details section identifies

## Explicit prohibitions

- saiui MUST NOT edit the main project tree directly.
- saiui MUST NOT add fake controls with no backend behavior.
- saiui MUST NOT change queue JSON, persistence, or worker semantics in a
  UI patch.
- saiui MUST NOT claim manual or screenshot QA that was not performed.
- saiui MUST NOT treat README claims as stronger than current code.
- Core MUST NOT collect a saiui patch without re-running Core VERIFY.

# T01 — MAKE START AUDIT TRULY ONE CLICK

Priority: P0

## Current defect

The toolbar says `START AUDIT`, but code still flashes `SEND AUDIT` messages.

When no worker exists, `_ensure_free_browser_worker()` currently tells the user:

`Wait for CLEAN then click SEND AUDIT again.`

This directly violates the desired UX and contradicts the actual flow, because `_on_send_audit()` continues packing and submitting the dispatch.

## Required changes

1. Use `START AUDIT` terminology everywhere.
   Remove `SEND AUDIT` from normal Qt user-facing strings.

2. Never instruct the user to click START again for the same run.

3. Change worker-launch messaging to:

`START AUDIT: queued · preparing audit worker`

or equivalent.

4. If no worker exists:
   - launch dedicated worker;
   - continue the same start request;
   - queue the job when archive is ready;
   - worker claims automatically when CLEAN.

5. If workers exist but are busy:
   - queue normally;
   - state becomes `WAITING FOR WORKER`;
   - this is not a failure.

6. If the user double-clicks START quickly:
   - exactly one start request;
   - exactly one dispatch.

7. If an active job already exists for the project:
   - bind UI to that job;
   - do not create another;
   - display `AUDIT ACTIVE`.

## Tests

- one click, zero workers -> launch once + one queued dispatch.
- no second click required.
- rapid ten clicks -> one dispatch.
- busy workers -> one queued dispatch, no failure.
- active existing dispatch -> no duplicate.

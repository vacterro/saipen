# UI WIREFRAME — TRANSPARENT AUDIT START

## Project Room toolbar

Recommended primary controls:

`PACK | START AUDIT | CANCEL AUDIT | AUDIT RESULT | IA | ...`

Rules:
- START AUDIT is enabled when selected project has no active run.
- While active, the button becomes disabled or changes to `AUDIT ACTIVE`.
- CANCEL AUDIT is only enabled when safe/meaningful for the current run.
- AUDIT RESULT is enabled only when `AUDIT READY`.

Do not make the user infer whether a second click is required.

## Selected project row

Before:
`A3 0/3`

Immediately after click:
`PREPARING`

Then:
`WAITING FOR WORKER`
or:
`ATTACHING · Chromium #1`

Then:
`STARTING`

Then:
`AUDIT 1/3`
`AUDIT 2/3`
`AUDIT 3/3`

Then:
`SAVING`

Finally:
`AUDIT READY ✓`

Failure:
`! BLOCKED`
with short human reason.

The normal row should not expose internal UUIDs.

## Audit Runs panel

Add a compact dock/panel/tab, not a giant dashboard.

Title:
`AUDIT RUNS`

Top summary:
`ACTIVE 4/6 · READY 2 · WAIT 1 · ! 0`

Rows:
- slot/run number
- project
- simple state
- wave progress
- elapsed
- one compact action

Possible actions:
- `DETAILS`
- `CANCEL`
- `OPEN RESULT`
depending on state.

## Details pane

Advanced diagnostics only:

Project
Profile
Dispatch ID
Campaign Run ID
Worker label
Browser
Archive
Current internal transport state
Current wave
Retries
Last error
Created
Updated
Final handoff path
Conversation locator if available

This keeps normal operation simple without sacrificing auditability.

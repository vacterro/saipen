# T06 — AUDIT RUNS PANEL: SIX CLEAR LANES

Priority: P0
Depends on: T03, T04

## Goal

Represent the six-worker architecture in terms the user actually cares about:
six audit runs.

Add a compact Project Room panel/tab/dock:
`AUDIT RUNS`

Maximum highlighted active capacity:
6.

## Lane ownership

A lane belongs to:
`project + dispatch`

not to a permanent worker.

If pre-start reassignment occurs, the lane remains the same.

## Row format

Example:

[1] TERMISAI      AUDIT 2/3           08:42
[2] FastPrompter  AUDIT READY ✓       12:10
[3] AUDAPACK      WAITING FOR WORKER  00:21
[4] SAIPEN        STARTING            00:07
[5] Example       SAVING              15:03
[6] Example2      AUDIT READY ✓       11:54

## Summary

`ACTIVE 4/6 · WAIT 1 · READY 2 · ! 0`

## Actions

Context-sensitive:
- CANCEL
- DETAILS
- OPEN RESULT
- COPY RESULT PATH
- OPEN AUDIT FOLDER

Do not expose raw UUIDs in the lane.

## Completed retention

Keep recently completed runs visible until:
- user clears completed;
- or a bounded recent-run history policy evicts them.

This is how the user can visibly reach:
`6/6 READY`.

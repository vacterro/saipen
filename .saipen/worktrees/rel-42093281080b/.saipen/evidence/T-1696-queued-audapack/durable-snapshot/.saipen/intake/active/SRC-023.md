# T09 — MAKE `AUDIT READY` A REAL RESULT CONTRACT

Priority: P0
Depends on: T03, T04

## Goal

The user should stop caring once a lane says:
`AUDIT READY ✓`

That label must be trustworthy.

## READY proof

Require all:
- dispatch COMPLETE;
- campaign_run_id present;
- matching AuditSnapshot;
- campaign_complete;
- completed_waves == total_waves;
- final_handoff_ready;
- final_handoff file exists;
- final_handoff SHA-256 matches terminal proof where available.

## Transitional states

Browser is finished but disk not final:
`SAVING`

Transport COMPLETE but local audit index not refreshed yet:
`VERIFYING RESULT`

Do not display READY until both converge.

## Result actions

When READY:
- `OPEN RESULT`
- `COPY RESULT PATH`
- `OPEN AUDIT FOLDER`

Optional:
- `OPEN CHAT` when a trustworthy conversation locator exists.

## Notification

Native notification:
`<Project>: AUDIT READY`

not generic:
`audit saved successfully`

The notification should occur only on real READY transition.

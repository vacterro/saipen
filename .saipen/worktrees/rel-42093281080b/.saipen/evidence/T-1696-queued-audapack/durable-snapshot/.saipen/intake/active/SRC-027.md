# T13 — ONE-CLICK AUDIT DIAGNOSTICS

Priority: P1
Depends on: T03, T10

## Goal

When a run is BLOCKED, debugging should not require searching five files manually.

Add `COPY DIAGNOSTICS` for a selected run.

Safe text bundle:
- AUDAPACK version
- project name/id
- operator state
- internal dispatcher state
- profile
- completed_waves / total
- worker friendly label/browser
- dispatch_id
- campaign_run_id
- retry count
- last error code/message
- timestamps
- Bridge healthy
- worker counts
- final handoff presence

Never include:
- Bridge auth token
- browser cookies
- full private conversation
- unrelated audit bodies

This makes support/audit loops much faster.

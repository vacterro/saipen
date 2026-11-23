# T12 — RUN HISTORY / TRACEABILITY

Priority: P1
Depends on: T03, T09

## Goal

After six audits become READY, the user should still know which result belongs to which run.

Persist/read a bounded run history view from existing durable sources.

Per run:
- project
- profile
- dispatch_id
- campaign_run_id
- started_at
- completed_at
- final_handoff_path
- result hash
- terminal state
- conversation locator if available

## UI

Audit Runs:
- Active
- Recent Ready
- Attention

Optional tabs/filters, keep compact.

## Never infer by filename alone

Use project_id + campaign_run_id as the canonical lineage.

## Restart

READY runs remain READY after GUI restart without re-notifying historical completions.

# T11 — SURVIVE GUI RESTART DURING PREPARING

Priority: P1
Depends on: T02, T03

## Gap

Before a dispatch_id exists, START AUDIT currently lives only in the running Qt task.

If AUDAPACK closes during a long pack/Bridge-start phase, the user's click has no durable identity.

## Add a tiny start-intent journal

State directory:
`audit_start_intents.json`

Record:
- request_id
- project_id
- profile
- created_at
- phase
- dispatch_id when known
- archive when known
- last_error

## Recovery

On AUDAPACK startup:

If dispatch_id exists:
- bind to canonical dispatch.

If phase is pre-dispatch and operation was interrupted:
- show:
  `INTERRUPTED · Resume Start`
or safely auto-resume only if the operation is provably pre-START and idempotent.

Completed/failed/cancelled intents may be pruned after bounded retention.

## Important

Do not create a database.
Do not duplicate BrowserDispatcher persistence.
This journal only covers the gap before durable dispatch ownership exists.

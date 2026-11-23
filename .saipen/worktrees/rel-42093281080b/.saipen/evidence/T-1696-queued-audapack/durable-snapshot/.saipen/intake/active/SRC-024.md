# T10 — FAILURE / CANCEL / RECOVERY THAT A HUMAN CAN UNDERSTAND

Priority: P0
Depends on: T03

## Problem

Low-level failures currently exist, but normal UI does not always tell the operator:
- whether work stopped;
- whether it will retry;
- whether START already happened;
- whether Cancel is safe.

## Operator categories

### WAITING
No failure. No clean worker yet.

### RETRYING
Automatic bounded pre-start retry.
Show:
`RETRYING 2/3 · attachment timeout`

### BLOCKED PRE-START
No Core was sent.
Safe actions:
- RETRY
- CANCEL

### BLOCKED POST-START
Core may have been sent.
Do NOT offer blind new START.
Actions:
- RECONCILE
- DETAILS
- OPEN CHAT if available

### FAILED
Terminal failure with no automatic retry.

### CANCELLED
Terminal.

## Cancel button

Enable only when the coordinator/composite state says cancellation is safe/meaningful.

Do not let the user infer safety from raw dispatcher state.

## Error copy

Use short human messages in rows:
- `No audit worker`
- `Attachment timed out`
- `Bridge offline`
- `Result save failed`

Advanced error code remains in Details.

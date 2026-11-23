# STATE MAPPING — INTERNAL TO OPERATOR

Do not invent a second competing state machine. Build a composite view.

## Local start coordinator

REQUESTED / BRIDGE_CHECK / PACKING:
    -> PREPARING

worker launch pending before durable dispatch:
    -> PREPARING · STARTING WORKER

## Dispatcher

QUEUED:
    if CLEAN worker count == 0:
        -> WAITING FOR WORKER
    else:
        -> WAITING

RETRYABLE:
    -> RETRYING

LEASED:
    -> ATTACHING

ARTIFACT_FETCHED:
    -> ATTACHING

ATTACHED:
    -> STARTING

START_PREPARED:
    -> STARTING

STARTED:
    -> AUDIT 0/N or STARTING until first wave ownership is known

AUDITING:
    -> AUDIT completed_waves/N
    if current wave known:
        prefer `AUDIT K/N · <wave short label>`

FINALIZING:
    -> SAVING

COMPLETE:
    do not immediately render READY.
    Apply READY invariant using durable AuditSnapshot/final handoff proof.

BLOCKED:
    -> BLOCKED

FAILED:
    -> FAILED

CANCELLED:
    -> CANCELLED

## Durable AuditSnapshot

completed_waves:
    provides K/N progress.

campaign_complete + final_handoff_ready:
    contributes to READY proof.

## Packing

PACKING:
    PREPARING · PACK x%

Packing must not be confused with audit wave progress.

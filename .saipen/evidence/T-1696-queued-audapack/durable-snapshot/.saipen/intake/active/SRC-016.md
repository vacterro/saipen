# T02 — EXTRACT AUDIT RUN COORDINATOR FROM QT

Priority: P0
Depends on: T01

## Why

`_on_send_audit()` currently coordinates too many domains directly.

Create a testable service/controller such as:

`AuditRunCoordinator`

It should own the start workflow, while Qt only:
- requests a run;
- receives snapshots/events;
- renders them.

## Coordinator workflow

Input:
- project_id
- profile

Phases:
1. START REQUESTED
2. active-run dedupe
3. Bridge health/start
4. worker-capacity hint/supervision
5. fresh pack
6. durable browser dispatch enqueue
7. bind dispatch_id
8. follow until terminal/result-ready

## Start result object

Return structured data, not only flash text:

- request_id
- project_id
- phase
- dispatch_id
- profile
- archive
- error_code
- human_message

## Failure honesty

Bridge fails:
`FAILED · Bridge unavailable`

Pack fails:
`FAILED · Pack failed`

Worker launch fails:
Do not fail the audit if the durable queue is still valid.
Show:
`WAITING FOR WORKER · worker launch failed`
and expose Retry Worker in Details.

## Threading

All network / pack / process-launch work stays outside Qt GUI thread.

## Tests

Coordinator should be extensively testable without creating a QMainWindow.

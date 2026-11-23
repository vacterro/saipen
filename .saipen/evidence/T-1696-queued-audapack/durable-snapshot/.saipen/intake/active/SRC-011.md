# PRODUCT CONTRACT — ONE CLICK IN, AUDIT READY OUT

## Canonical user contract

For one project:

`START AUDIT`
    -> one run is created
    -> one run progresses automatically
    -> one result becomes `AUDIT READY`

No second click.

No manual browser assignment.

No requirement to open Settings.

No requirement to understand worker internals.

## Default visible state language

Use only these operator states in the normal Project Room / Audit Runs panel:

- `PREPARING`
- `WAITING FOR WORKER`
- `ATTACHING`
- `STARTING`
- `AUDIT 1/N`
- `AUDIT 2/N`
- `...`
- `SAVING`
- `AUDIT READY`
- `BLOCKED`
- `FAILED`
- `CANCELLED`

Optional:
- `RETRYING`
only when retry is materially visible.

Do not show raw:
- LEASED
- ARTIFACT_FETCHED
- START_PREPARED
- dispatch UUID
- lease UUID

unless the user opens Details.

## READY invariant

`AUDIT READY` is allowed only when all are true:

- BrowserDispatcher job == COMPLETE;
- matching project_id;
- matching campaign_run_id;
- durable campaign state == COMPLETE;
- completed_waves == expected total_waves;
- final_handoff_ready == true;
- final_handoff_path exists;
- final_handoff hash/proof matches the terminal job.

Anything less remains:
`SAVING` / `VERIFYING RESULT` / `BLOCKED`.

Never show READY because the browser merely finished generating.

## Six-run contract

The main UI supports up to six simultaneously active audit lanes because the browser broker already has a six-worker ceiling.

A lane belongs to an AUDIT RUN, not permanently to a browser worker.

Worker assignment may change pre-start without changing the lane.

Example:

AUDIT RUNS 6 MAX

[1] TERMISAI      AUDIT 2/3          08:42
[2] FastPrompter  AUDIT READY ✓      12:10
[3] AUDAPACK      WAITING FOR WORKER 00:21
[4] SAIPEN        STARTING           00:07
[5] Project E     SAVING             15:03
[6] Project F     AUDIT READY ✓      11:54

This is the primary mental model.

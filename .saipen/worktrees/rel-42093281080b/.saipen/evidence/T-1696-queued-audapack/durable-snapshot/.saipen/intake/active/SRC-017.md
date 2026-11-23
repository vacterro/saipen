# T03 — CANONICAL COMPOSITE AUDIT RUN SNAPSHOT

Priority: P0
Depends on: T02

## Goal

Create one UI-facing model that merges:
- local start coordinator phase;
- pack progress;
- BrowserDispatcher job;
- worker summary;
- durable AuditSnapshot.

Suggested model:

AuditRunSnapshot:
- request_id
- dispatch_id
- project_id
- project_name
- profile_id
- expected_waves
- completed_waves
- current_wave
- operator_state
- internal_state
- worker_label
- browser_name
- started_at
- updated_at
- elapsed
- retry_count
- error_code
- error_message
- campaign_run_id
- final_handoff_path
- final_handoff_ready
- result_ready

## One source for rendering

Project row, Audit Runs panel, notifications and Details must use this same composite snapshot.

Do not duplicate state-mapping logic in four widgets.

## Ready proof

`result_ready` must implement the exact READY invariant in `01_PRODUCT_CONTRACT.md`.

## Restart reconstruction

When no local request object exists after application restart:
- reconstruct from BrowserDispatcher jobs + AuditSnapshot;
- do not lose active runs from the UI.

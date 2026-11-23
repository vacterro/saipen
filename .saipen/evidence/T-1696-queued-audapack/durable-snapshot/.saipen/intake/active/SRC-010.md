# AUDAPACK — CURRENT TRUTH: AUDIT START / RUN TRANSPARENCY

Source snapshot:
- `_AUDAPACK_31.08.26-T10-33-53.zip`
- SHA-256: `ec985e6e3de5bb69eb678f680dec5e26b0e0c370f7edf3de640d2080a8b6f4d3`
- Git branch: `main`
- Git HEAD: `9750a4a3cdcaa12041128cf75120e35911e074bd`
- Version: `0.2.1`
- SAIPEN phase: `REVIEW`
- SAIPEN task: `T-51`

## Verified implementation already present

The current tree is not an empty prototype. Preserve these systems:

- Project Room `START AUDIT` button.
- Bridge auto-start fallback.
- canonical fresh project packing.
- durable BrowserDispatcher jobs.
- max 6 browser workers.
- CLEAN-chat scheduling proof.
- exact ZIP attachment waiting.
- exactly-once `START_PREPARED` + start receipt.
- campaign_run_id ownership.
- state-aware LEASED / ARTIFACT_FETCHED / ATTACHED recovery.
- bounded retry/backoff.
- `FINALIZING`.
- durable Bridge-owned `COMPLETE`.
- final_handoff path/hash storage.
- audit generation watcher.
- native terminal notifications.
- INAUDIT capture system, unrelated to this roadmap.

Observed verification from this snapshot:
- Widget: **156/156 PASS**
- Focused browser/Bridge Python gate: **94 PASS / 1 SKIP + 29 subtests PASS**
- `test_two_workers_never_get_the_same_job` still waits on the production empty long-poll path when probed directly because its second empty poll is not forced to `wait_seconds: 0`.

## Why START AUDIT still feels unclear

### 1. The visible contract contradicts itself

Toolbar:
`START AUDIT`

But messages still say:
`SEND AUDIT`

And the no-worker path says:
`Wait for CLEAN then click SEND AUDIT again.`

This is especially confusing because the current `_on_send_audit()` keeps going after worker launch:
- it packs;
- it submits the dispatch;
- the queued job can later be claimed automatically.

So the UI verbally asks for a second click while the implementation is already attempting one-click behavior.

This must be removed.

### 2. The orchestration is buried in Qt code

`_on_send_audit()` currently owns:
- duplicate check;
- Bridge health/start;
- worker launch decision;
- fresh packing;
- dispatch submit;
- flash messages.

There is no first-class Audit Run coordinator/view model.

This makes testing and transparent UI state difficult.

### 3. User-facing progress is split across different state sources

Transport:
- QUEUED
- LEASED
- ARTIFACT_FETCHED
- ATTACHED
- START_PREPARED
- STARTED
- AUDITING
- FINALIZING
- COMPLETE / BLOCKED / FAILED / CANCELLED

Durable audit result:
- profile
- completed_waves
- total_waves
- campaign_complete
- final_handoff_ready
- final_handoff_path

Packing:
- PACKING / progress / COMPLETE / FAILED

The user should not need to understand these three state machines separately.

### 4. Project row hides useful wave progress while a dispatch is active

During an active dispatch the row collapses states into labels such as:
- WAIT
- ATTACH
- START
- AUDIT
- SAVE

But once it says `AUDIT`, it no longer clearly says:
`AUDIT 1/3`, `AUDIT 2/3`, `AUDIT 3/3`.

### 5. No first-class `AUDIT READY` result state exists

After transport COMPLETE the row falls back to normal audit snapshot rendering such as:
`✓ A3 3/3`.

That is technically meaningful, but the desired operator contract is simpler:

`AUDIT READY ✓`

Only then should the user need to care about the result file.

### 6. Live transport refresh is still mostly a 10-second HTTP fallback

`browser_dispatch_generation.json` already exists and changes on dispatcher transitions, but Project Room does not watch it.

The UI can therefore appear stale for several seconds even when the worker already moved to the next state.

### 7. The six-worker architecture is not represented as six understandable audit runs

The broker supports six workers, but the main UI does not provide one obvious place showing:

- which projects were started;
- which are waiting;
- which are running;
- which wave each is on;
- which are ready;
- which need attention.

The operator should think in AUDIT RUNS, not worker UUIDs.

### 8. Worker auto-launch is only a helper, not a managed six-slot capacity system

When zero workers exist, one dedicated Chromium is launched.

There is no clear queue-driven policy that prepares enough CLEAN dedicated workers for a batch of up to six audits.

## Product target for this roadmap

The normal experience must become:

1. Select project.
2. Click `START AUDIT` once.
3. Never click it again for that run.
4. Immediately see one stable run row/card.
5. Watch only understandable states:
   - PREPARING
   - WAITING
   - STARTING
   - AUDIT 1/N
   - AUDIT 2/N
   - ...
   - SAVING
   - AUDIT READY
6. When READY, open/copy the final result.
7. Repeat for up to six projects and clearly see all six runs become READY.

Technical details remain available in a details/diagnostics view, not in the normal operator path.

The user should never have to reason about:
- dispatch_id;
- lease_id;
- worker UUID;
- START_PREPARED;
- artifact fetched;
unless diagnosing a failure.

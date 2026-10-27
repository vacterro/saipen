# Host-Scheduler Integration and Dispatch Contract

## Overview

In autonomous engineering campaigns, model completion (`MODEL_TURN_FINISHED`) does **not** signify goal completion (`SAIPEN_GOAL_FINISHED`). When an LLM finishes streaming its response or executing tool calls, the SAIPEN engine evaluates the canonical iteration verdict via `iteration_verdict.project_iteration_verdict` and `assess_continuation`.

When the canonical verdict yields `AUTO_KICK` (or an executable continuation status):
1. SAIPEN generates a structured dispatch request payload.
2. The payload is delivered to the host scheduler via push (callable, webhook, or command) or durable pull (`dispatch_inbox.jsonl` / `next_turn.json`).
3. An external pump loop or native scheduler activates the next model turn.

---

## Why Single-Turn API Hosts Require a Host-Level Pump Loop

LLM execution environments (e.g., standard API harnesses, web UIs, or CLI tools without an autonomous agent supervisor) terminate after a single assistant turn. They do not know whether the repository's tickets, tests, or maintenance tasks have completed.

If the host halts after one turn:
- Durable state on disk remains valid (`DOING` ticket or active goal), but no CPU or process is pumping the next model prompt.
- The campaign enters an artificial pause despite remaining workable items.

Therefore, an autonomous harness (such as **ZAICODE**, **Antigravity**, or a local supervisor) must maintain an outer execution loop that pumps the next turn whenever `AUTO_KICK` or `KICK_NEXT_ITERATION` is signaled.

---

## Dispatch Payload Schema

Every turn dispatch request adheres to `schema_version: 1`:

```json
{
  "schema_version": 1,
  "campaign_id": "CAMPAIGN-00000000-0000-0000-0000-000000000000",
  "project_lineage": "lineage-...",
  "project_root": "V:/path/to/project",
  "worker_generation": 1,
  "iteration_id": 5,
  "action": "KICK_NEXT_ITERATION",
  "decision": "AUTO_KICK",
  "goal_binding": {
    "path": ".saipen/STATE.md",
    "fingerprint": "intent-goal-..."
  },
  "authority_proof_reference": "authority/continuous_maintenance_proof",
  "checkpoint_reference": ".saipen/cache/autonomy-worker.json",
  "idempotency_key": "sha256(campaign_id + project_lineage + worker_generation + iteration_id)",
  "created_at": "2026-10-25T18:40:00Z"
}
```

### Key Fields:
- `campaign_id`: Durable campaign identity across host and worker restarts.
- `project_lineage`: Portable project lineage ensuring cross-repository isolation.
- `worker_generation`: Monotonically increasing counter for worker lifecycle generations.
- `iteration_id`: Monotonically increasing counter for turn iterations within the worker/campaign.
- `idempotency_key`: `sha256(campaign_id:project_lineage:worker_generation:iteration_id)` preventing duplicate execution.
- `authority_proof_reference`: Proof verifying that continuous maintenance or goal continuation was granted by an operator.

---

## Dispatch Modes

### 1. Push Dispatch (Registered Native Host)

If the host harness registers a callback, command, or endpoint:
- **Python Callable**: Passed to `HostIterationController(host_hook=...)` or `dispatch_next_turn(..., host_hook=...)`.
- **CLI Command Hook**: Set via `HOST_SCHEDULER_DISPATCH_CMD` environment variable. The command is invoked with the JSON payload passed as an argument.
- **HTTP Endpoint**: Set via `HOST_DISPATCH_ENDPOINT` environment variable. An HTTP `POST` request is sent with `Content-Type: application/json`.

### 2. Pull Dispatch (Advisory Fallback)

When no native push hook is configured:
1. The dispatch payload is appended atomically to:
   `.saipen/campaign/dispatch_inbox.jsonl`
2. The latest turn request is written atomically to:
   `.saipen/campaign/next_turn.json`
3. A structured `[SAIPEN_HOST_DISPATCH_ADVISORY]` block is logged to stderr:
   ```text
   [SAIPEN_HOST_DISPATCH_ADVISORY]
   action: KICK_NEXT_ITERATION
   campaign_id: CAMPAIGN-00000000-0000-0000-0000-000000000000
   iteration_id: 5
   worker_generation: 1
   idempotency_key: a3f8...
   inbox_path: .saipen/campaign/dispatch_inbox.jsonl
   advisory: Native host iteration dispatch not registered; pump turn via host harness or external watcher.
   [/SAIPEN_HOST_DISPATCH_ADVISORY]
   ```
4. An external scheduler or supervisor monitors `next_turn.json` or tailing `dispatch_inbox.jsonl` to invoke the next agent step.

---

## Idempotency and Crash Safety

- **Duplicate Callbacks**: If `on_model_turn_finished` is invoked multiple times for the same iteration (e.g. repeated turn completion hooks), the idempotency guard matches `idempotency_key` against `.saipen/campaign/dispatch_idempotency.json`. Exactly **one** dispatch action and **one** log block are emitted.
- **Crash Prior to Dispatch**: State remains preserved on disk. Re-evaluating continuation triggers dispatch.
- **Crash Following Dispatch**: The recorded `idempotency_key` ensures replacement generations do not re-dispatch concurrent iterations for the same slot.

---

## Standard Exit Codes

| Exit Code | Constant | Meaning |
|-----------|----------|---------|
| `0` | `EXIT_OK` | Clean completion of bounded slice or task |
| `2` | `EXIT_USAGE` | Invalid command line arguments or config |
| `3` | `EXIT_NO_AUTHORITY` | Ambiguous authority or missing operator grant |
| `4` | `EXIT_STOPPED` | Campaign stopped cleanly (operator wait, safety, or budget exhausted) |
| `5` | `EXIT_FENCED` | Worker lease fenced by supervisor or successor generation |

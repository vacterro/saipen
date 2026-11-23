# CROSS-PROJECT IMPLEMENTATION HANDOFF: FreeBuff Operator Provenance Integration

**Target Host**: FreeBuff (Desktop Orchestrator & CLI)
**Target Model**: Luna
**Target Protocol**: SAIPEN v8 (SRC-277 / T-1818)
**Status**: SPECIFIED, NOT INSTALLED -- the carrier mechanisms below are a FreeBuff-side obligation that SAIPEN has measured as absent (T-1822 live: a real operator prompt reaches the engine with no `SAIPEN_TASK_FILE`, no `SAIPEN_TASK_SHA256` and no host ingress envelope). Nothing on the SAIPEN side is waiting on a FreeBuff build step; SAIPEN refuses the unprovenanced call correctly until this is implemented.

**Scope note**: this repository does not contain FreeBuff sources, so no FreeBuff file path, symbol or class named below has been read or verified here. Locate the real integration points in the FreeBuff tree before editing; the names in section 4 are descriptions of the kind of surface to find, not inspected facts.

---

## 1. Problem Statement & Incident Forensics

In FastPrompter incident (T-1479 SCOUT), the human operator approved corrective work in the FreeBuff chat UI. However, when Luna invoked shell tools to run `saipen`, the spawned subprocesses arrived in SAIPEN with:
- No `SAIPEN_TASK_FILE`
- No `SAIPEN_TASK_SHA256`
- No host ingress envelope in `.saipen/cache/ingress/`
- Resulting witness: `model_supplied`
- When safety valve tripped (`continuation_authority: operator_required`, `safety_valve_mode: hard_wait`), SAIPEN strictly and correctly refused to execute model-fabricated text as operator authority, returning `NO_ADMISSIBLE_WORK`.
- Simultaneously, prior validation was `STALE_FAIL` (due to source edits after an earlier test run). `saipen recover` returned `CLEAN`. Because `STALE_FAIL` was not revalidated by Auto-Doctor, the session became deadlocked.

SAIPEN has bounded the Auto-Doctor deadlock (T-1818/T-1823): a conformance refusal whose cause is recoverable staleness of the validation receipt -- the receipt is a stale view of an unchanged tree -- is revalidated once through `saipen validate` under active authorized work, and the continuation resumes. The authority for that is typed, never textual: the receipt must carry one of the closed recoverable codes (`source-binding-stale`, `aged-beyond-freshness-window`, `checkpoint-hashes-stale`, `remediation-evidence-advanced`). `CURRENT_FAIL` (a measured failure), `INVALID_RECEIPT` and any unknown or absent code fail closed and stop exactly as before. Revalidation re-runs the validator and re-reads the gate; it never manufactures operator authority and never converts `model_supplied` into trusted evidence. Missing operator provenance therefore still stops, and that stop is the correct behaviour described in this handoff.

**This handoff specifies the FreeBuff-side implementation** to ensure operator provenance is faithfully captured and transported to SAIPEN subprocesses.

---

## 2. FreeBuff Architecture & Ownership Boundaries

| Component | Owner | Responsibility |
| :--- | :--- | :--- |
| **Human Input Event Loop** | FreeBuff | Capture human input text, assign unique `message_id`, record timestamp. |
| **Host Session Identity** | FreeBuff | Track `session_id`, workspace root (`cwd`), and bind active conversation. |
| **Tool Execution Spawner** | FreeBuff | When spawning child processes (`powershell.exe`, `cmd.exe`, `bash.exe`), export operator provenance into process environment or stage ingress cache. |
| **Model Ingress Gate** | FreeBuff / Luna | Distinguish user prompt from model reasoning/completions; never fabricate operator carrier from model text. |
| **Protocol Admission** | SAIPEN | Verify carrier hash against supplied arguments; admit or reject into canonical lifecycle. |

---

## 3. Required Technical Integration (Choose Carrier A or B)

FreeBuff must implement at least one of the following two trusted carrier mechanisms when launching tool processes.

### Mechanism A: Environment Variable Transport (Recommended for CLI / Shell Tools)

When FreeBuff spawns a tool process executing inside a SAIPEN workspace (a directory containing `.saipen/`):
1. **Stage Task File**:
   Write the exact raw user request text (from the human chat message) to a temporary file:
   `%TEMP%\freebuff_task_<session_id>_<message_id>.txt`
2. **Export Environment Variables**:
   In the spawned process environment:
   ```ini
   SAIPEN_TASK_FILE=C:\Users\<user>\AppData\Local\Temp\freebuff_task_<session_id>_<message_id>.txt
   SAIPEN_TASK_SHA256=<sha256_lowercase_hex_of_exact_user_text>
   FREEBUFF_HOME=%USERPROFILE%\.freebuff
   FREEBUFF_SESSION=<session_id>
   ```
3. **Subprocess Inheritance**:
   Ensure that when Luna launches nested scripts or tools, these environment variables are inherited by child process trees.

### Mechanism B: Native Ingress Cache (Recommended for Desktop Orchestrator / Pre-Tool Hooks)

When FreeBuff detects a user prompt in a workspace with `.saipen/`:
1. Compute SHA256 lowercase hex of user prompt: `computed_sha`.
2. Write JSON envelope to `<project_root>/.saipen/cache/ingress/ing-<computed_sha[:16]>.json`:
   ```json
   {
     "ingress_id": "ing-<computed_sha[:16]>",
     "message_id": "<freebuff_message_uuid>",
     "request_text": "<exact_raw_user_prompt>",
     "request_digest": "<computed_sha>",
     "session_id": "<freebuff_session_id>",
     "project_lineage": "<project_lineage_from_identity_md_or_null>",
     "destination_op": "continue",
     "consumed": false,
     "created_at": "<ISO8601_UTC>",
     "witness": "operator_carrier",
     "declared_by": "host_ingress"
   }
   ```
3. When Luna invokes `saipen continue` or `saipen start`, SAIPEN's `admit_host_ingress` / `active_host_ingress` consumes this record, proving `witness: operator_carrier` without requiring manual hashes.

---

## 4. FreeBuff Surfaces to Find (not inspected from this repository)

FreeBuff's own sources are not in this repository; nothing below has been read or proved here. Each line names the surface the FreeBuff agent must locate in its own tree before it can implement Mechanism A or B.

1. **Process launch environment builder** -- wherever the host builds the environment for a spawned tool process. That builder needs to detect a workspace containing `.saipen/`, compute the user turn's digest, and inject `SAIPEN_TASK_FILE` / `SAIPEN_TASK_SHA256` (Mechanism A).
2. **Tool execution hook** -- wherever spawned subprocess environments are constructed or filtered; it must not strip inherited `SAIPEN_*` variables.
3. **Operator prompt handler / approval interaction** -- wherever a human turn or approval is recorded. That is where the ingress envelope of Mechanism B is written, and where an approval must become the next turn's input rather than a request to open an external terminal.

---

## 5. FreeBuff Regression Test Requirements

FreeBuff test suite must include assertions verifying:
1. `test_saipen_process_env_injection`: Spawning a shell tool in a SAIPEN workspace includes `SAIPEN_TASK_FILE` and `SAIPEN_TASK_SHA256`.
2. `test_model_text_does_not_forge_carrier`: Model-generated continuation does not synthesize a false `operator_carrier`.
3. `test_nested_process_preservation`: Nested CLI executions retain `SAIPEN_TASK_*` in their environment.

---

## 6. SAIPEN Compatibility Status (as landed, T-1823)

- `extensions/adapters/registry.json`: the `freebuff` adapter records installed behaviour only -- `host_prompt_available: false`, `prompt_to_work_binding: NOT_INSTALLED`, `supported_carrier_mechanisms: []`. It stays that way until a real FreeBuff-launched tool process delivers a carrier that host-to-engine acceptance can verify. SAIPEN must not manufacture a carrier for itself.
- `tools/saipen.py`: Auto-Doctor revalidation is gated on a typed conformance condition, not on the wording of a refusal -- `_DOCTOR_REVALIDATE = {STALE_PASS, NOT_RUN, VALIDATOR_VERSION_MISMATCH}`, and `STALE_FAIL` only when the receipt carries a closed recoverable stale reason under active authorized work. `CURRENT_FAIL`, `INVALID_RECEIPT` and unknown codes fail closed.
- `tools/saipen_engine/operator_task.py`: FreeBuff detection and structured diagnostics (`FREEBUFF_OPERATOR_PROVENANCE_MISSING`).
- `tools/saipen_engine/admission_doctor.py`: structured decision requests for provenance insufficiency (`CAUSE_E_PROVENANCE_INSUFFICIENT = E_OPERATOR_PROVENANCE_INSUFFICIENT`).
- `tools/test_freebuff_operator_provenance.py`: 19 tests, 1 skipped. Categories are separated in the module: unit contract verification, simulated host integration (this module's own `CATEGORY`), actual FreeBuff process integration, and real operator-origin end-to-end acceptance (`FreebuffLiveHostAcceptance`, skipped in this environment because no trusted FreeBuff carrier exists). A green run here is category 2 only; it is not GUI acceptance.

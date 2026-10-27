# FreeBuff native operator provenance: implementation handoff

Owner: T-1819 / SRC-278. Receiving owner: FreeBuff Desktop input and tool-launch
integration. Status: implementation and real UI/Luna acceptance remain BLOCKED
outside this repository. This document is prepared locally and has not been sent.

The defect is loss of independently verifiable operator origin between the
native input boundary and the spawned model tool. A task file, environment
digest, session string or model-written ingress cache cannot authenticate a
human. The host must perform the transport without asking the operator to
write files, calculate hashes or execute recovery commands.

## Inspected installed generation

Desktop 0.0.182 is installed at
`C:/Users/vac34/AppData/Local/Programs/@codebufffreebuff-desktop`.
`resources/app.asar` SHA256 is
`ef8563ad25eb9b71ef29952fd2b97546687c517a6c0573fd576637e41bb943f8`;
`resources/orchestrator/orchestrator.js` SHA256 is
`416a4352c9483d7a04837d27fc2a6973c3a78b549d21451d706a85168fa06b7b`.
Both were rechecked for this continuation. Source extracts and per-file digests
are in `.saipen/evidence/T-1819-freebuff-route/installed-source-manifest.json`.
An editable FreeBuff checkout has not been established; do not modify vendor
installation files or invent an upstream checkout path.

The actual Luna thread/harness selection remains unobserved. The Codebuff route
below is an inspected available route, not proof that the incident selected it.
Do not substitute ZAICODE or assume every FreeBuff session uses Claude Code.

## Actual interfaces

Locations below are in the exact installed bundle unless stated otherwise.
Embedded source comments identify the upstream modules to change in FreeBuff.

| Interface | Observed location | Required change |
| --- | --- | --- |
| Native launch | extracted `electron/main.cjs:710`, spawn `:758` | Preserve existing stdin bootstrap for launch secrets and `FREEBUFF_APP_VERSION` child marker. Authenticate the native integration to the existing broker. |
| Native API boundary | extracted `electron/ipc-sender.cjs:16`, `orchestrator-request.cjs:30`; bundle `src/server/http/origin-guard.ts:214775` | Retain the top-level IPC sender and launch-bound HttpOnly/SameSite cookie checks. A renderer `human=true`, HTTP Origin or thread UUID cannot replace native caller proof. |
| User message ingress | `threadRoutes`, message/edit-message `:251295` | `engine.postMessage(threadId, text, attachments)` currently receives no authenticated user-event capsule. Preserve exact raw human bytes and stable event ID separately from expanded prompts. |
| Engine admission | `postMessage:235599`, `messageThread:235602`, `admitMessage:235608` | Default `postMessage` options carry no origin. `messageThread`'s origin label is not independently authenticated human input. Preserve event/task/session identity through queuing and re-entry. |
| Input expansion | `buildUserInput:237102` | Keep raw request separate from attachment expansion, skill content and trimmed display text; bind the original bytes to one authenticated event. |
| Harness dispatch | `src/server/harness/codebuff.ts`, `runTurn:213427`, `client.run:213540` | Resolve the actual selected model/provider and thread before dispatch; pass an event-bound context through its real tool path. |
| Terminal binding | same module, `run_terminal_command:213664` | Current call passes command/cwd and tool controls without native event proof or registered worker. Carry only the corresponding event, never a shared last-user-event global. |
| Direct spawn | `../sdk/src/tools/run-terminal-command.ts`, `spawnDirectTerminalCommand:138488`, `runTerminalCommand:138513` | The actual child uses `request.env`. The native spawner must register the newly created PID and hold execution until registration succeeds. |
| Alternate spawn | `src/server/services/terminal.ts`, `start:244920`, `Bun.spawn:244924` | Cover the selected broker/PTY launch as well; direct-shell coverage cannot establish alternate-path acceptance. |

The inspected message route retains user text but drops an independently
verifiable user-origin context before engine/model execution. The inspected
terminal interface also provides no event proof or native worker registration.
The missing task variables are a consequence of that unwired interface. No
live FreeBuff process or genuine UI event was available in the current probe.

## Existing SAIPEN interface

T-1844 supplies the existing separated authority broker's operator-origin
methods in `tools/saipen_engine/host_authority_client.py`:
`issue_operator_origin`, `register_operator_worker`, `revoke_operator_origin`,
`verify_operator_origin`, `prepare_operator_goal`, `verify_operator_goal`.
The broker-owned `OperatorOrigins` implementation verifies event, root/lineage,
session, task/goal/budget, action, issuer, expiry, worker birth and ancestry.
See `.saipen/evidence/T-1844-operator-origin/NATIVE-ORIGIN-CONTRACT.md`.

1. At the genuine native user-input/approval boundary, issue the intended
   bounded action for the exact original request and stable event identity.
   The caller must satisfy the broker's actual OS/shipped-artifact identity
   policy. Adding an API call alone does not prove native writer acceptance.
2. The native spawner registers only the worker PID it actually created with
   `register_operator_worker`. Do not register the shared orchestrator or a
   model-selected PID. Keep issue/register/revoke out of unrestricted model
   tools. Model-readable proofs alone cannot authenticate another worker.
3. Transport the resulting `operator_origin` in the existing `host_ingress`
   envelope with exact `request_text`, `request_digest`, `session_id` and
   `message_id`. `admit_host_ingress` stores transport; independent broker
   verification determines trust. Files/hashes remain integrity carriers.
4. Keep queued, nested, delayed and restarted execution bound to its own event.
   Same-event redelivery is idempotent; identical text in different events is
   distinct. Revocation/issuer loss/mismatch/expiry produce a precise refusal.
   Unknown native capabilities never fall back to model-authored authority.
5. An already committed goal may continue only within its proven goal/budget
   epoch. Delivery expiry cannot restore fresh delivery or reset authority.
   Historical `model_supplied` Sources remain unchanged. Routine approval is
   native FreeBuff UI; no external terminal or manual hash workflow.

Do not introduce another signer, same-user key file, admission bypass, marker
exception or caller-selected production endpoint. The native FreeBuff writer
proof and process handshake are still receiving-owner implementation gates.

## Required receiving-owner acceptance

Preserve every SRC-278 A-Q outcome. Exercise actual Desktop approval and Luna
continuation, verified broker-origin delivery and canonical SAIPEN admission;
model-forged real task variables/cache/proofs; replay; wrong repository/task/
session/model/provider; expiry/revocation/issuer loss; nested and alternate
spawns; independent queued events and delayed callbacks; restart; stale
validation with/without authority; duplicate retries; and actionable tool errors
without a retry loop. Simulated broker positives establish local kernel
behavior only. Record the actual selected harness, native caller, worker and
UI result. Do not turn a skipped live-host test into acceptance.

SAIPEN's adapter registry continues to report FreeBuff ingress NOT_INSTALLED.
T-1850 repairs diagnostic detection/classification and native-proof doctor
instructions; it does not install this host bridge. Safe stale-receipt
Auto-Doctor remains bounded and cannot mint operator authority.

## FastPrompter recovery boundary

The actual checkout is `V:/___VAC/__K/__CODE/_PY/_FastPrompter`, lineage
`lineage-c13f771bc2924a5a81b65fc79e5aca08`. The original T-1479 is already DONE
in its current BOARD; its current read-only contract projection remains
`UNVERIFIED / DEPENDENCY_BINDING_MISSING`. The latest orientation probe refuses
`COLD_ORIENTATION_BLOCKED`: STATE is 20038 bytes against the 8192-byte bound,
with no advertised safe mutation. An existing T-1480 also carries Chest work.

After native provenance is genuinely repaired, obtain fresh legitimate scoped
host authority and have that project's owner reconcile existing T-1479/T-1480
and canonical recovery. Do not invent a third Chest ticket, blindly reopen a
DONE row, promote historical model text or mutate unrelated dirty files. Actual
Chest/Stash correction, regression and Windows GUI proof remain due; GitHub
publication retains its separate restriction.

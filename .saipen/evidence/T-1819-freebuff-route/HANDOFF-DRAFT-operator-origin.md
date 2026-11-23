# FreeBuff native operator origin: inspected implementation handoff draft

Owner: T-1819 / SRC-278. Prepared during T-1844's frozen verification window.
This is a local draft for the receiving FreeBuff owner, not an installed host
integration, a sent message, a completed acceptance gate or a replacement for
SRC-278. The old root `SAIHANDOFF_FREEBUFF_PROVENANCE.md` needs revision under
the parent: its plain-file/hash/cache mechanism does not authenticate origin.

## Current source evidence and limits

The actual installed Desktop archive remains at
`C:/Users/vac34/AppData/Local/Programs/@codebufffreebuff-desktop/resources/app.asar`.
Its SHA256 was rechecked as
`ef8563ad25eb9b71ef29952fd2b97546687c517a6c0573fd576637e41bb943f8`, matching
`installed-source-manifest.json` and the saved read-only Electron extracts.
The installed orchestrator at the sibling
`resources/orchestrator/orchestrator.js` currently hashes to
`416a4352c9483d7a04837d27fc2a6973c3a78b549d21451d706a85168fa06b7b`.
All bundle lines below refer to those exact current bytes. Embedded source-path
comments identify upstream modules; no editable FreeBuff repository root has
been established by this investigation. Do not invent one or patch installed
vendor artifacts from this draft.

The current bundle contains zero case-insensitive `saipen` literal matches.
That is a bounded lexical observation, not proof that every dynamically named
integration is absent. The concrete paths below independently show a missing
operator-origin field at the inspected interfaces.

## Observed call chain

| Surface | Inspected installed location | Current behavior and integration point |
| --- | --- | --- |
| Desktop starts orchestrator | saved `electron/main.cjs:710`, spawn at 758 | Electron owns Bun startup. `FREEBUFF_APP_VERSION` is passed in env. Launch/bridge secrets are scrubbed from env and sent through stdin bootstrap. Preserve this boundary. |
| Desktop IPC and authenticated API transport | saved `electron/ipc-sender.cjs:16`, `apiTokenReply:31`; `electron/orchestrator-request.cjs:30`; bundle `src/server/http/origin-guard.ts:214775` | IPC checks the app's top-level sender. Main installs a launch-specific HttpOnly, SameSite=Strict `/api` cookie in its own window session; the orchestrator accepts the launch token/header or cookie. Reuse this actual native boundary, subject to its threat model and the broker's separate native-client proof. A plain HTTP Origin field alone is insufficient. |
| Thread message route | bundle `threadRoutes`, message/edit-message cases at 251295 | The message route calls `engine.postMessage(threadId, text6, attachments)` without origin options. Request text/attachments alone carry no authenticated human-event proof. |
| Engine message admission | bundle `postMessage:235599`, `messageThread:235602`, `admitMessage:235608` | `postMessage` delegates with default opts. `messageThread` separately supplies `origin`; this proves that an origin label exists for another route, not that it is authenticated human UI input. |
| Input materialization | bundle `buildUserInput:237102` | Constructs a UUID row, threadId, expanded prompt, trimmed display text, queue/source fields, and optional origin preamble/note. No inspected field is an independently authenticated exact human-event capsule. Preserve raw text independently of prompt expansion. |
| Codebuff harness | embedded `src/server/harness/codebuff.ts`; `runTurn:213427`, `client3.run:213540` | Selects actual `turn.model`/BYOK/hosted configuration and supplies tool handlers. This is a verified available path; the incident's actual Luna thread/harness selection still needs live metadata and must not be guessed. |
| Terminal tool binding | same bundle `run_terminal_command:213664` | Calls `runTerminalCommand` with command, resolved cwd, process type, timeout, abort, credential scrubbing and optional sponsored broker. It supplies no exact user-event provenance or registered-worker binding. |
| Ordinary terminal spawn | embedded `../sdk/src/tools/run-terminal-command.ts`, `runTerminalCommand:138513`, `spawnDirectTerminalCommand:138488` | Merges system env plus optional env, selects Windows Bash, and spawns a hidden child with `request.env`. A host-owned pre-execution worker-registration handshake belongs at the actual spawn boundary. Plain env inheritance cannot authenticate that child. |
| Alternate broker/PTY spawn | `src/server/services/terminal.ts`, `start:244920`, `Bun.spawn:244924` | Uses `launch3.env` for explicit launches. Cover this path when it is selected; do not assume the direct-shell path covers sponsored or other brokered execution. |

The missing interface is more precise than a missing task file: the inspected
native message admission stores no independently verified exact human event,
and the harness/tool spawner passes no event proof into a broker-registered
worker. The model therefore cannot repair the lost origin by writing a file,
hash, session string, cache envelope or an `operator_carrier` label itself.
These are source observations, not a live UI reproduction of the entire chain.

## SAIPEN contract supplied by T-1844

`tools/saipen_engine/host_authority_client.py` exposes
`issue_operator_origin`, `register_operator_worker`, `revoke_operator_origin`,
`verify_operator_origin`, `prepare_operator_goal` and `verify_operator_goal`.
`operator_origin.OperatorOrigins` is owned by the existing separated broker.
Production methods use its authenticated endpoint; no caller-selected test
endpoint, new signer, same-user key file, trust env flag or generic admission
fallback is acceptable.

1. At a genuine native human-input/approval boundary, retain the exact original
   UTF-8 text and stable event identity separately from expanded model prompt,
   model messages, queued assistant suggestions and inter-thread messages.
   Authenticate the native callback through the broker's existing OS/shipped
   artifact identity policy. A route name, HTTP Origin header, thread UUID or
   renderer-supplied `human=true` flag is not that authentication. The exact
   FreeBuff native writer proof remains an implementation and acceptance gate;
   the presence of the new API does not establish it.
2. The authenticated native owner issues an exact permitted action with
   project root/lineage, host/session, model/provider, current task, goal and
   budget scope. Preserve the returned broker capsule as `operator_origin` in
   the existing ingress transport alongside `request_text`, `request_digest`,
   `session_id` and `message_id`. Hashes/files may transport bytes, never grant
   authority by themselves. Action-specific effects need their exact action.
3. The trusted spawner registers only the actual newly created worker PID with
   `register_operator_worker`; the broker observes process birth and ancestry.
   Hold execution until registration succeeds. Cover actual direct, nested and
   brokered launch paths. Never register the shared orchestrator as a model
   worker, accept a model-chosen PID, or expose the native issue/register API as
   an unrestricted model tool.
4. Give each response/tool callback its own event/session capsule, clear stale
   inherited selectors, and retain queue/delayed-callback identity. Source
   binding is idempotent for the same event; identical text from distinct
   events must remain distinct. Revocation, issuer loss, mismatch or unknown
   native capabilities produce a precise structured refusal, without fallback
   that upgrades model text.
5. Existing committed goal continuation can survive delivery expiry and genuine
   same-session/model/provider worker replacement only within its original
   goal/budget epoch. It must not restore delivery or spend another budget
   reset. Restart/reconnect must recover only authority the existing owner can
   still independently prove. Historical `model_supplied` Sources stay intact.

Detailed scope, replay, Source and goal semantics are in the current
`T-1844-operator-origin/NATIVE-ORIGIN-CONTRACT.md` and actual implementation.
T-1844 simulated broker positives prove its local kernel only. The genuine
native identity, actual Desktop input and process launch require host-side
integration tests; neither a fixture nor a model invoking a CLI is a substitute.

## SAIPEN diagnostic work still owned by the parent

The saved Electron main and current bundle demonstrate `FREEBUFF_APP_VERSION`.
A current direct read-only engine probe gives
`is_freebuff_host({'FREEBUFF_APP_VERSION': '0.0.182'}) == False` and
`host_taxonomy.known(CODE_FREEBUFF_PROVENANCE_MISSING) == False`.
These are existing SRC-278 Stage 7 gaps, reproduced under the current source.
Once T-1844 releases the frozen tree, repair them within the parent's owned
BUILD/VERIFY scope with the same negative/control obligations. A detected host
marker is diagnostic context and must never grant operator capabilities.

## Receiving-owner acceptance and remaining mission

Preserve every SRC-278 A-Q gate. Exercise real Desktop user approval and the
actual Luna continuation; distinguish those results from isolated unit tests.
Include model-authored real carrier variables/cache/proof fields, copied and
expired/revoked grants, wrong repo/task/session/model/provider, nested tools,
separate queued messages, delayed callbacks, restart/issuer loss, stale
validation with/without authority, exact duplicate retry, and clear terminal
failure with no retry loop. Verify that the operator uses the native UI and
never has to create task files, hash text or run recovery shell commands.

The live FastPrompter application process supplies the actual source path
`V:/___VAC/__K/__CODE/_PY/_FastPrompter/FastPrompter.pyw`; a read-only Git query
confirms `V:/___VAC/__K/__CODE/_PY/_FastPrompter` as the project root. Its current
lineage is `lineage-c13f771bc2924a5a81b65fc79e5aca08`. Current files supersede
the old incident's SCOUT position: STATE is PLAN/task none at E-4995, and
T-1479 is already in DONE, `closure_mode: own_patch`, with model-supplied
SRC-121. This row is not proof of successful current host admission or GUI
acceptance. The current canonical read-only `work contracts T-1479` result is
UNVERIFIED / DEPENDENCY_BINDING_MISSING. Existing T-1480 already names a Chest
corrective directive and is BLOCKED on pre-BUILD findings capture exit 143;
do not create a third ticket or blindly reopen/resume DONE T-1479.

The current external `context orient` also refuses
READ_ONLY_DIAGNOSIS_ONLY / COLD_ORIENTATION_BLOCKED: STATE is 20026 bytes
against its 8192-byte bounded cap, with no advertised safe repair or canonical
next command. Unrelated dirty protocol/source files exist. These were read-only
observations; no recovery, canonical/source mutation, admission or GUI action
was performed in FastPrompter. After the actual FreeBuff path is repaired,
obtain fresh legitimate host authority and have that project's owner reconcile
the existing T-1479 completion proof and T-1480 blocker through canonical
operations, then verify the requested correction and actual Windows GUI.
Preserve unrelated dirty files and the independent publication restriction.
No duplicate Chest ticket or retroactive promotion of model evidence.

This draft is not sent. Parent source dispositions, actual native writer proof,
UI/Luna acceptance, T-1479 admission/correction/GUI evidence and final delivery
remain due. T-1844's active full-family operation is not completion evidence.

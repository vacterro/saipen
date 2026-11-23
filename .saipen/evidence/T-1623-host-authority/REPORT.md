# T-1623 — separated local host-authority broker

Evidence for the change that replaces the `HOST_AUTHORITY_UNAVAILABLE` dead end
on the Claude Code GUI prompt path with a real separated authority.

## What the defect was

T-1563 established, correctly, that a same-user Python hook cannot prove host
provenance: the hook and any model-executed Python run as the same OS principal,
so every locally minted token is self-attestation. That finding disabled local
minting and left Claude admission `UNAVAILABLE`, which meant every prompt from a
normally launched Claude Code GUI was blocked with a diagnostic that named no
component, no attempted recovery and no action. Architecturally true,
operationally unusable.

## What now supplies the authority

| Piece | Artifact | Owns |
|---|---|---|
| Broker | `tools/saipen_engine/host_authority_broker.py` | authentication, key, capability, ledger write, lifecycle |
| Client | `tools/saipen_engine/host_authority_client.py` | the ask, bounded autostart recovery, degraded policy |
| Transport | `tools/saipen_engine/host_authority_transport.py` | Windows named pipe (Unix socket on POSIX), one JSON frame per connection |
| Identity | `tools/saipen_engine/host_authority_process.py` | OS-derived image and parent chain; supplies facts, decides nothing |
| Entry | `tools/authority_service.py` | the service process; `start/stop/status/identify/mode/install-startup` |
| Owner | `tools/saipen_engine/protocol_admission.py` | asks and transports; never mints |

## Security invariants, and where each is enforced

| Invariant | Enforcement | Regression test |
|---|---|---|
| Importing the module cannot admit | `establish` refuses when the broker does not answer; `_write_record` raises | `test_t1563_authority_minting.*`, `LedgerTests.test_the_ledger_write_is_still_refused_for_an_ordinary_caller` |
| A same-user Python client cannot connect and ask | broker derives the peer pid from the pipe/`SO_PEERCRED` and matches the image chain against configured host images | `AuthenticatorTests.*`, `ClaudeGuiPathTests.test_an_ordinary_python_client_is_still_blocked_with_recovery_detail` |
| Another session's capability cannot be replayed | capability id must be in the live broker's in-memory issue set | `test_a_sha256_shaped_capability_forges_nothing` |
| A capability cannot move to another project/session/model/provider | HMAC binds project fingerprint, session, host, model, provider | `test_a_capability_transplanted_to_another_session_or_model_is_refused`, `test_a_capability_is_bound_to_the_project_it_was_minted_for` |
| Ordinary SHA-256 data cannot forge a capability | mac is HMAC under a key generated in broker memory and never written to disk | `test_a_sha256_shaped_capability_forges_nothing` |
| An expired capability fails | TTL compared against the broker clock, both sides | `test_an_expired_capability_is_refused` |
| Reuse after a generation change fails | key + instance id are per-process; a restart invalidates everything it issued | `test_a_capability_from_another_broker_generation_is_refused`, `test_a_broker_restart_readmits_the_same_session_automatically` |
| A hand-built ledger record is not authoritative | provenance is an HMAC only the live broker can reproduce; the owner asks it | `LedgerTests.test_the_owner_reads_the_broker_record_and_refuses_a_hand_built_one`, `test_an_edited_record_fails_the_broker_provenance_too` |
| No env var, prompt text or magic phrase admits | `TransportAuthorityTests.*`, `DiagnosticTests.test_no_environment_variable_and_no_prompt_text_changes_the_answer` |

## Lifecycle

Singleton by owner pid (`broker.lock`, stale locks reclaimed), detached child
(`DETACHED_PROCESS`/`start_new_session`), health via an unauthenticated `ping`,
shutdown only for an authenticated client, per-user login autostart through the
`HKCU\...\Run` entry the operator can remove, idle exit when nothing has been
served. Duplicate launch and crash recovery are covered by
`OwnerLifecycleTests` and `ClaudeGuiPathTests.test_a_crashed_broker_is_recovered_on_the_next_prompt`.

## Recovery UX

The refusal now reads as a control surface, not a dead end:

```
SAIPEN PROTOCOL ADMISSION REFUSED -- HOST_AUTHORITY_UNAVAILABLE: ... the separated
SAIPEN host-authority broker is required; the broker refused this client
(BROKER_CLIENT_NOT_AUTHENTICATED): the connecting process is not a descendant of a
registered host application ... -- component SAIPEN host-authority broker;
automatic recovery attempted [connect, start]; state started -- operator actions:
Retry the prompt | Start the authority service: saipen authority start | Open
diagnostics: ~/.saipen/authority/broker.log | Policy permitting only: saipen
authority mode degraded
```

Degraded mode is never automatic, is read only from the operator's own
`~/.saipen/authority.json`, writes no ledger record, mints no capability and is
marked `UNVERIFIED/DEGRADED` in the host's own surface.

## Verification run

| Suite | Result |
|---|---|
| `tools/test_host_authority_broker.py` (new, 36 tests) | OK |
| `tools/test_protocol_admission.py` | OK (9 skipped, unchanged skips) |
| `tools/test_t1563_authority_minting.py` | OK |
| `tools/test_claude_stop_hook.py`, `test_adapter_parity.py`, `test_guard_admission.py`, `test_native_host_guard.py` | OK (1 skipped) |
| `tools/test_guard_hostile_matrix.py`, `test_guard_execution_reachability.py`, `test_host_bootstrap.py`, `test_guard_root_parity.py`, `test_runtime_generation_identity.py`, `test_t1568_opencode_chat_style.py`, `test_codex_stop_hook.py` | OK (2 skipped) |
| `python tools/t1623_broker_demo.py` (real hook artifact, real project, real pipe, real broker) | admitted with no block in 0.8s, broker recovered from absent, record written by the broker, second prompt not re-delivered, ordinary Python client refused, shutdown refused to an unauthenticated client |

## One test assertion was changed, on purpose

`test_protocol_admission.CapabilityMatrixTests.test_claude_is_mechanical_at_the_prompt_boundary_and_not_universal`
asserted `admission_enforcement == "UNAVAILABLE"`. That is the state the operator
asked to replace. Its teeth were moved rather than removed: the same test now
requires `MECHANICAL` **and** that the entry names an existing broker artifact
and recovery client, and the sibling tests still require every other host to stay
non-mechanical.

## Known limits, recorded not hidden

1. The anchor is the OS process tree plus configured image names. It separates
   the host's own hook path from an unrelated same-user script. It is not a
   boundary against code injected INTO the host process, and a same-user process
   that fabricates an image name of a configured host is not distinguished by
   name alone. Pin absolute image paths in
   `protocol_admission.host_authority.host_images` for the stronger claim.
2. `_host_component` verifies the installed hook entry against the running
   engine's own root, so the adapter home must delegate to the generation being
   authenticated. This is why the end-to-end proof installs its scratch adapter
   home from the host interpreter.
3. The operator's real `~/.claude/hooks/saipen-guard.py` currently delegates to
   `C:/Users/vac34/AppData/Local/saipen/scheduled-source` and reports
   `root_current: false`; the scheduled injector is itself blocked with
   `DIRTY_SOURCE`. Until that generation is published and injected, a normally
   launched GUI runs the previous generation's hook, which still refuses. This is
   an integration/publish step, not a code defect in this change.

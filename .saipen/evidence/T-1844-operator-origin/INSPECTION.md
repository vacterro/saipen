# T-1844 exact revision inspection

Read-only inspection of the finished b6dc79950e870846 source while its complete
post-resync family runs. This is the executing agent's own inspection, not a
human or second-agent review, and not yet a formal REVIEW/SHIP verdict.

## Scope and attribution

`review-owned-deltas.json` pins 62 attributable changed paths, seven created in
this Work, every current SHA256 and preserved exact preimage. Its companion
`review-owned-deltas.diff` gives the 6249-line unified review carrier. The early
CLI snapshot is the preserved `resume-prefix/saipen-cli.py`; it includes the
response CLI root propagation that the later scope-prefix snapshot cannot
show. Two saved but unchanged files (Claude guard and guard_events.py) are
excluded. This scope does not claim unrelated initial worktree/index changes.
All 62 current hashes were rechecked after inspection; no source was edited.

## Security, failures, state and workflow effects

Inspected the complete new origin module, modified broker/client dispatch,
capability derivation and direct production callers found by exact symbol
search: CLI capture/response, entry, goal authority and journal operations,
acceptance, gate decisions, handoff, retirement, append and supersession.
New native writers retain the existing shipped-hook/OS identity boundary.
Consumers verify only at the authenticated production endpoint; test runtime
selection is absent from the new production APIs. There is no signer/key file,
new daemon, generic admission fallback or self-asserted trust flag.

The broker retains and seals the exact event, intent, project/lineage, native
host birth, session/model/provider, task/goal/budget scope and bounded nonce.
Malformed inputs, wrong scopes, PID reuse/broken ancestry, foreign workers,
revocation, expiry and issuer loss refuse. Worker selection uses the nearest
observed registered ancestor. Native registration cannot use the shared host
as its worker or transplant a live ancestor into another event. The RLock
serializes event/Source/goal bindings. Capacity refusal preserves existing
records rather than evicting live authority. Broker lifetime still uses its
existing idle-and-real-host policy; no separate lifecycle was added.

Only mutating durable capture/entry callers opt into first Source binding;
ordinary receipt, response and decision reads are existing-only. A read cannot
consume a Source grant. Default byte-only duplicate queries retain their read
contract; actual capture uses exact event identity and immutable provenance.
Integrity errors are checked before filtering another event. Body-only and
metadata/index crash recovery preserve the original event and metadata. START
projects its already captured exact Source, without a second model-labelled
capture. Raw carriers retain fidelity refusal and ordinary local-work access.

One native nonce reserves one stable goal operation and semantic hash. The
accepted goal requires that original COMMITTED operation and exact grant;
new native workers can continue only within its original same-host/session/
model/provider goal and budget epoch. This does not restore delivery or reset
powers. Bound goal Sources compare the signed budget with current state before
reset. Historical accepted Source origin has a distinct typed verdict and is
used for exact report/history checks, never as current authority. System
retirement cannot infer historical fabrication from lost current capabilities.
Action-specific consumers independently check their exact capsule/target;
a report cannot become append, retirement, supersession, handoff or gate grant.

Inspected both actual response callbacks and their CLI consumer. Each passes
its own event session; responseCarrierEnv clears inherited task/file/session
selectors first. Digest/session select transport only; independent proof and
registered worker still authenticate. Unverified protocol diagnosis refuses
before it can fall back to ordinary chat. Failure paths preserve rejected
response data and original assertions through the actual adapter/CLI.

## Test and oracle integrity

Read changed legacy test hunks and the new kernel, event, preview, goal/budget,
forged-carrier and isolated host helper controls. The original eight-test
forgery oracle stays byte-identical (d51851cf7b403b1e07eb6bc1832b523b936f2ddd9b390e2b2de9cf8075369560).
Five native executed same-oracle pairs in final-measurements.json measure
original carrier, goal/budget, diagnosis, preview and actual node transport
before FAIL/after PASS. Unavailable instrumentation attempts remain separate,
with identical repaired context/encoding on both measured subjects.

Legacy positives now supply an explicit private broker fixture; real HMAC,
canonical Sources/journals, cold CLI, nested validator and node remain active.
Only native identity/process facts and the origin transport are simulated.
Other authority ops retain their own endpoints; cleanup stops the fixture
thread and scoped patches. No production flag or installed test shim exists.
Repeated event tests reuse one event; fresh native events get a separate
Source. Changed old-model/import expectations preserve the original Source
metadata and BOARD, still reject raw-carrier promotion, and independently
check a distinct authenticated receipt. Matrix SRC-043 now has a valid full
canonical body/metadata, allowing the old-origin assertions to test the
intended behavior rather than succeed because of corruption.

Post-effect assertions inspect authority actually spent and historical origin,
then explicitly reject another budget reset. They do not demand a replayable
reset after the accepted budget changed. Matrix R keeps actual ambient installed
parity, including a real mismatch failure; unavailable install is explicit SKIP.
Actual OpenCode fresh-process installed-generation smoke remains unchanged.
No native/UI requirement was replaced by the simulated matrix PASS.

## Actual installed generation and remaining gates

Finished-source complete family ended FAIL 7207/2 solely on actual stale
OpenCode installation. After terminal, canonical prelaunch resynced the
existing managed surface; read-only prelaunch then proved RUNTIME_CURRENT.
Engine/hook/launchers/provenance match 2fcd13a4. Actual complete smoke and matrix
modules PASS 29 in fresh native focused record
`b6dc79950e870846-20261021T142051125376Z.json`. These observations prove installed
generation convergence/loading only, not human-input issuance or Freebuff UI.

No confirmed additional implementation finding in this scoped inspection.
Security/performance root extensions contain example templates only; no active
project scanner/benchmark contract is configured. No hardcoded secret or key
persistence was introduced. Memory promotion: NO; existing origin/identity and
Source fidelity owners already hold the durable lesson, with no new separate
non-transient decision rule justified.

Formal REVIEW still needs terminal full-family evidence, its own ticket verify
run and exact hash recheck before reusing this inspection. Parent T-1819 keeps
the complete SRC-278 real native route/spawner/handoff and A-Q live acceptance,
including original FastPrompter T-1479 recovery. Preserve SRC-268 real native
requirements and T-1644 no-push/no-tag boundary. Pending cohort is local
completion only. General source conformance remains a separate actual gate.

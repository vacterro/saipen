# SRC-254 / T-1794: Freebuff Luna runtime recovery

STATUS: PARTIAL. Actual failure owner proven and handoff ready. Host correction
and real cold-start acceptance remain blocked on independently owned work.

ROOT CAUSE: **G — Freebuff Desktop SDK's Windows CWD normalization**.
The reported Bash executable is present and works. The original Luna thread's
first `cwd="."` command worked; seven later commands pass `/v/...`, which
`executeTool` resolves to nonexistent `V:\v\...`. Installed Bun reproduces the
identical Bash-named ENOENT for that CWD. The native/translated CWD both work.
`SAIPEN_HOST_RUNTIME_UNAVAILABLE` was the model's label after a host spawn
failure, not a SAIPEN lifecycle refusal. See `incident-history.json` and
`windows-spawn-probe.json`.

SAIPEN CORRECTION: none required in the launcher or CLI for this defect.
Existing native entry, ProgramData machine integrity and project binding were
verified. No new implementation, shell layer, runtime manager or authority
source was added. The exact request is immutable SRC-254, appended to SRC-253,
with scoped Work T-1794. Previously admitted T-1749 and T-1792 were completed
before this Work entered BUILD. Artifacts only were added for this mission.

FREEBUFF DEPENDENCY: required. `FREEBUFF_HANDOFF.md` names the precise SDK
boundary, existing path translator, correct immediate CWD, diagnosis changes,
native-route capability limits, regression matrix and independent authorization.
Freebuff source and the T-52 consumer source were not patched. No other agent
was sent this handoff and no foreign lifecycle was claimed.

RUNTIME ACCEPTANCE: **SOURCE_VERIFIED** for the inspected contracts and cause;
**WINDOWS_RUNTIME_VERIFIED** for the observed Windows launch paths. The source
`.cmd` returns `HOST_BOOTSTRAP_BOUND` even with no discoverable Bash in a child
environment. The real ProgramData runtime returns `MACHINE_RUNTIME_READY` from
its own engine with generation, interpreter, launcher and ACL proof. Comparing
it with the newer working tree returns `MACHINE_RUNTIME_STALE`; no false
current-source equivalence or software refresh is claimed.

FREEBUFF_HOST_VERIFIED: **FAIL** as acceptance. The original and new live host
records prove the CWD failure. Ordinary `run_terminal_command` is Bash-only,
with no per-call native selector; the sponsored broker's PowerShell support
does not authorize a normal thread to use it. Controlled SDK-function checks
are Windows evidence, not a claimed repair of the running app.

LUNA ACCEPTANCE: **REAL_LUNA_ACCEPTANCE = FAIL**. Freebuff Desktop 0.0.173,
actual `openai/gpt-6-luna` (`m-5a5d0e255e`), fresh thread
`587918ed-22b5-46c3-82e3-9c926ea84f3c`, exact user input `cc`, mission OFF.
The host-loaded account SAIPAL skill still claims `cc`; Luna loaded it and read
SAIPAL's protocol. It later reproduced the CWD ENOENT, reached a genuine
`NOT_SAIPEN_PROJECT` refusal, then investigated another project. The owned test
was stopped and confirmed idle. No SAIPAL command executed, no fixture lifecycle
was created, and the fixture's instruction/README bytes remained unchanged.
The cold test is a failed acceptance record, not a successful continuation.
`luna-cold-dispatch.json`, `luna-cold-observation.json`, `luna-cold-stop.json`.

T-52: independently located in `_FREEBUFF_SAI`, lineage
`lineage-fe5afd6d81564116bfdc3b0184adc0ec`, BUILD / owner saipen / E-685;
source SRC-020 is still active with its original digest. Runtime entry resolves
that exact project. Admission is DEGRADED/permitted, verified:false (advisory
host, no admission evidence channel). This SAIPEN Work grants no consumer
implementation authority. T-52 was not resumed, duplicated, force-claimed or
repaired. Its read-before-lock race and conformance remain unverified.
`target-entry.json`, `target-admission.json`, `target-source-status.json`,
`preservation-after.json`.

REGRESSION: 9 controlled Windows checks passed: 3 actual spawn controls,
4 installed-SDK/native route checks, missing-machine refusal, absent-project
authority refusal. Three existing machine integrity/ownership/registration
negative-control unit tests passed (8.959s); some ownership inputs are injected
by that existing harness and are not another-account live acceptance. One real
Luna cold test FAILED and was stopped. No foreign fixed-source pair exists
because Freebuff was not patched. The earlier coherent SAIPEN tree had 6609/0
full-family evidence for T-1749/T-1792; that does not certify a Freebuff repair.

| Case | Observed result | Acceptance limit |
|---|---|---|
| A: Bash present | Installed SDK `pwd` exits 0; original/new real host also execute Bash | Existing path works with valid native CWD |
| B: configured Bash missing | Discovery chooses existing supported Bash; independent native `.cmd` bootstrap works with no discoverable Bash | Normal Freebuff tool exposes no native fallback |
| C: all Bash absent | Unchanged SDK rejects before spawning SAIPEN | Accurate host-owned limitation required; old message recommends Git only |
| D: absent/untrusted runtime | `MACHINE_RUNTIME_ABSENT`; 3 integrity/ownership/registration negative controls PASS | No untrusted fallback; live registered runtime is intact |
| E: no lifecycle authority | Native `PROJECT_BINDING_INVALID`; real host `NOT_SAIPEN_PROJECT`; no `.saipen` created | Runtime availability grants no mutation authority |
| F: real Luna `cc` | FAIL: stale SAIPAL `cc` collision, wrong CWD, project scope drift | Host/skill repair and a fresh real acceptance run remain due |

OPERATOR ACTION: no Git installation, PATH edit, elevation or manual SAIPEN
recovery is needed for the demonstrated spawn failure. The outstanding source
fix belongs to an independently admitted Freebuff Desktop executor; the stale
SAIPAL account skill needs its supported synchronization owner. The stale SAIPEN
activation deployment remains subject to T-1644's existing policy, not bypassed.

NEXT EXACT ACTION: independently admit `FREEBUFF_HANDOFF.md` in the actual
Freebuff Desktop source project, fix CWD conversion and precise spawn diagnosis,
refresh the conflicting account skill through its owner, then repeat real Luna
`cc`. A separately authorized T-52 executor can use the JSON route in that
handoff with `cwd="V:/___VAC/__K/__CODE/_PLUG_SCRIPT/_FREEBUFF_SAI"` and current
canonical gates. **BLOCKED** remains true for end-to-end host recovery and T-52
continuation; no whole-mission or goal completion is claimed.

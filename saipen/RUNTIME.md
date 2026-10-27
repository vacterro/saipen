# SAIPEN Adaptive Runtime

This document owns runtime identity/capability semantics. CORE owns Work,
state, commands, precedence, checkpointing and completion. Runtime data is
replaceable session telemetry; it cannot make project truth provider-specific.

## Host bootstrap / runtime binding

A host opening a SAIPEN-managed project must reach a canonical runtime before
ordinary work. One read-only operation answers that:

    saipen host bootstrap [--host <registry-id>] [--project-root PATH] [--json]

It resolves the binding in this order, never scanning disks or guessing:

1. project binding -- `.saipen/` present, or an asserted carrier verifies;
2. a canonical `saipen` on PATH (reported, never trusted as the binding);
3. a SAIPEN-controlled pointer -- the project's `STATE.saipen_home` or an
   exported `SAIPEN_SKILL_ROOT` carrier;
4. the executing engine itself, which IS a canonical runtime.

`HOST_BOOTSTRAP_BOUND` is the only green code. Otherwise the stable diagnostic
`SAIPEN_HOST_RUNTIME_UNAVAILABLE` names the unsupported boundary
(`project_binding`, `activation_contract`, `canonical_runtime`,
`direct_entrypoint`, `host_bridge`), the candidates and the remediation, with
a `fingerprint` so a host suppresses unchanged repeats.

Three verdicts never merge. **Runtime discovered**: proven from a candidate's
own bytes. **Host admitted**: an explicit `--host` must be a registered
adapter, else `HOST_UNSUPPORTED` with `ok: false`, discovery kept under
`runtime_discovered`/`runtime_boundary`. **Transport reachable**: only an
executable launcher (POSIX `+x`, a Windows `.cmd` shim) or a `saipen` on PATH
counts. No cross-boundary transport is probed; `bridge.cross_boundary` is
always false.

Fail-closed writes: an absolute `STATE.saipen_home` that does not resolve to a
usable install refuses consequential mutation (`HOME_REQUIRED`) at the shared
admission gate; canonical operations and diagnostic reads stay available.
`saipen rebind-home --auto` converges a DEAD pointer onto the already-PROVEN
runtime (the executing engine or a verified installed carrier, never a scanned
path), journaled as `HOST_BINDING_CONVERGED` with the previous pointer in LOG
evidence. It is idempotent (`HOME_ALREADY_BOUND`, zero writes) and refuses
`HOME_REQUIRED` naming the explicit form only when nothing proves. `cc` and
`start` run the same convergence first. `saipen rebind-home <candidate>` is the
route for an install the resolver cannot prove itself. A host with no
before-tool hook (`declared_strength` ADVISORY) is reported as such.

`saipen host activation --project-root PATH` asks whether the MANAGED
PROJECT's resolved runtime carries the canonical activation contract
(`ACTIVATION_PRESENT`). The argument is the project root, never the install
home; a flattened installed home has no `.saipen/` and still answers green.

## Scoped campaign authority

Scope amplification by an attached proof: an authentic operator event used to
authorize arbitrary permission fields in a model-written grant file. Campaign
authority now binds the complete original request through the existing separated
native-event broker. `tools/saipen_engine/campaign_authority.py` owns the closed
capsule/carrier schemas and permission vocabulary.

A whole `saipen-campaign-authorization` JSON request enters through START as an
authority-only Source. It preserves active Work, goal and counters; it is never
projected as an engineering task. The returned campaign admission route consumes
one campaign reservation in the exact project/goal/host/session scope and within
the declared resources and expiry. A file carrier contains that original request
and its operator-origin proof; labels, ordinary journal events and generic Source
capabilities supply no additional campaign permission.

`saipen campaign status` reads state. `admit --authority SRC-###` or `--grant PATH`
uses the native issuer; `step` revalidates the original carrier and admission at
protected boundaries. Revocation, changed carrier bytes, foreign target/epoch,
issuer loss or consumed authority never become inferred permission. `cancel`
retains its stopping semantics. Campaign mutations refuse `--dry-run` without
executing; START's authority-intake preview remains read-only. Native kernel
contracts and simulated host fixtures are distinct from live host acceptance.

## Machine runtime — an account that cannot read the home

A managed account opens a granted project while `saipen_home` and the
interpreter sit in the operator's profile; ACCESS_DENIED must not read as a
dead home. `saipen host machine [status|install|remove]`: `install` projects
the running runtime, read-only for other accounts, into
`%ProgramData%\SAI\SAIPEN`; `status` answers `saipen_runtime_ready`;
`host repair` refreshes it. Under it the unreadable `STATE.saipen_home` it
projects is covered and unchanged; any other engine refuses
`CROSS_USER_RUNTIME_UNAVAILABLE` and never rebinds it.

## Host integration — state, doctor, repair (HOST-INTEGRATION-01)

Lockout-by-integration: a supported host that could run was refused every
prompt by its own hook, a substring of a failure message decided whether it
blocked, and installer, launcher and hook reported different states for one
host. One owner each:

- `host_taxonomy` -- every failure is ONE registered code (family, severity,
  automatic recovery, one operator action, fallback). `decide(mode, problems)`
  is the only policy: a conflict (a forged, replayed or transplanted
  capability; a binding that contradicts the project) is BLOCK in every mode;
  a gap is ALLOW_DEGRADED under `degraded`, the default, and BLOCK under
  `strict`. An unregistered code blocks, and `problem()` refuses to build one.
- `host_integration` -- what a host CAN do is `capability_contract(adapter)`,
  a pure projection of `extensions/adapters/registry.json` (an undeclared cell
  reads UNDECLARED). What it IS, is one of nine states derived from observed
  facts; installed, current, healthy and verified are four facts.
  `HEALTHY_VERIFIED` needs a recorded ADMITTED prompt newer than the installed
  hook; a host with no evidence channel stays `INSTALLED_UNVERIFIED`.

    saipen host doctor [--host ID] [--json]    read-only; writes and starts nothing
    saipen host repair [--host ID] [--json]    the canonical installer, host-scoped
    saipen host mode [strict|degraded|default]

Claude profile conflation (T-1635): doctor lists default, `CLAUDE_CONFIG_DIR`,
registered launcher `env.CLAUDE_CONFIG_DIR` and sibling `.claude-*` directories
separately. `saipen host repair --host claude --profile PATH` installs only the
named profile; other profiles are observed only. Hook proof uses the host
process's observed profile, never the authority service's environment.
Credentials are neither read nor copied.

All three run outside a bound project. `repair` acts only on present hosts
that are BROKEN, STALE_RUNTIME or INSTALLING, retires an authority service of
another generation and never touches a project.

A hook that can block a prompt (`tools/install_host_guard.py`):

- is installed stage -> self-test -> activate: one that would block with its
  engine missing is never activated, and the replaced generation is kept for
  `--rollback`;
- runs the INSTALLED runtime, never a checkout; an engine that cannot run is
  `ENGINE_UNREACHABLE`, decided by the same policy inside the hook;
- is started through `HOOK_BOOTSTRAP` (`host_authority_identity`): a missing
  script exits 2 and a host reads 2 as "block", so the command is a no-op when
  its file is gone, and an uninstall under a live host leaves the inert
  `tools/retired_host_hook.py` for sessions that loaded an older command.

The authority service starts only for the host's own hook invocation
(`host_authority_client.hook_invocation`). `bootstrap/uninstall.ps1` needs no
Python.

## Authenticated continuation when native ingress is absent

Defect class: a host without a native operator bridge keeps asking the human
to retype `cc`, although no spelling can supply the missing authenticated event.
`RECONCILE_REAUTH_REQUIRED` preserves hard_wait; command aliases do not renew it.

1. Run `saipen host doctor --host <registry-id> --json` read-only. Check the
   installed generation and the adapter's declared prompt/authority capability
   separately. `hook: not-applicable`, no hook artifact, or
   `operator_ingress_capability.prompt_to_work_binding: NOT_INSTALLED` means
   the installer has no native bridge to restore. An installed advisory skill
   and `HOST_DOCTOR` success do not prove authenticated operator ingress.
2. A declared, damaged hook uses `saipen host repair --host <registry-id>`
   after its source generation is verified, then the host's ordinary reload.
   Repair refreshes declared artifacts; it does not grant authority. If no
   bridge is declared, its owner is the native host integration plus SAIPEN
   core. Reinstalling the same advisory adapter cannot satisfy this boundary.
3. That owner must connect the actual native user-input callback to the
   separated broker, preserve the original event/root/session, register only
   the worker the host actually created, and carry the bound origin through
   the real execution path. `host_authority_client` owns issue/register/verify;
   the broker's OS-observed caller and installed-artifact checks remain due.
   A file, environment variable, test hook or model-replayed event supplies no
   operator identity. Do not relax publisher/caller verification to admit an
   unsigned or unsupported host.
4. Pending that integration, a human may use another healthy installed host
   whose adapter already proves native operator ingress, open the SAME project
   and submit a fresh `cc` there. Confirm the canonical reauthorization and
   resumed Work before returning to the original host. A CLI replay, copied
   receipt or instruction to this agent is not that native user event. If no
   such supported host is available, retain the refusal and name this exact
   missing native capability; no reset/stash/state edit is a recovery path.
5. Acceptance requires a fresh genuine event in the deployed host, successful
   canonical continuation, and rejection of missing/forged/replayed/wrong-scope
   origins. Test doubles prove kernel behavior only. Preserve the old counters
   until the canonical authority transaction accepts that event. The budget
   compares processed wave/ticket counters with registry limits using `>=`;
   a large TODO queue by itself does not exhaust it.

ZAICODE's current registry entry declares no hook artifact or prompt binding.
Until the native integration above is installed and proved, report that gap;
do not promise that `cc`, `continue` or `saipen continue` can repair it.

## Turn entry — AUTO_RECALL / AUTO_KICK

The agent is disposable; the execution is not. A host may swap model, provider
or session mid-Work; the successor has no private memory, only the conversation.

    saipen autonomy recall [--carrier-json JSON | --carrier-hex HEX] [--directive] [--json]

is a read-only projection over STATE/BOARD/LOG plus a host carrier (`host`,
`host_session`, `provider`, `model`, `previous_incarnation`, `cold`,
`ingress: {id, text, consumed}`). It answers:

- `execution_epoch` -- anchored on the LOG event that claimed the Work, never
  `claim_time` (checkpoints refresh that lease); a model/session change writes
  no claim event and cannot move it;
- `agent_incarnation` -- the physical actor; `replacement_detected` reports a
  session change against `claim_session`, a model change, or a cold successor;
- the active Work, phase, last event, claim, lease, blocker, due gates,
  canonical next action and `exact_resume_command`;
- ONE turn-entry decision, in order: `RECOVER` (unreadable state or pending
  recovery) > `USER_INPUT` (new unconsumed message) > `OPERATOR_WAIT` >
  `AUTO_KICK` (active executable DOING Work) > `RUN_CONTINUE` (the message is
  `cc`, old or new) > `ORDINARY`.

A kick means: run `saipen continue --json` before any conversational text. A
message becomes HISTORICAL only after the host saw an admitted canonical
`saipen` command after it; identity comes from the host, never prose
similarity, and unreadable input stays NEW. The injected directive carries only
closed-grammar fields, so project text never becomes system instruction.

Host seams. The OpenCode plugin runs the recall before EVERY model request.
Hosts without a per-request hook get the rule only as instruction text: an
external host boundary, not a solved case.

## Iteration exit — turn finality vs goal finality

Premature-goal-handback (a model turn ending read as task completion on an
ADVISORY host) and unadmitted-executor routing (a worker without
shell/filesystem owning SAIPEN execution). Prose never owns terminality;
`saipen iteration` does — the ONE public verdict, derived read-only from
STATE/BOARD/router/recall/valve via `iteration_verdict.project_iteration_verdict`
(schema v1); the reference HOST FLOW lives in `host_iteration`. After every
model turn the controller queries that verdict:

- executor unfits what the phase needs (STATE `requires`, control, plus
  run/patch only where the phase runs or edits, plus the active ticket's
  `requires:` -- `name[@PHASE[+PHASE]]`, or `read_only` for reading and
  control only -- set by `saipen ticket requires`; shared names in
  `iteration_verdict.CAPABILITY_INVENTORY`; per switch via
  `iteration.admit`, never from model identity) →
  `EXECUTOR_CAPABILITY_MISMATCH`: reroute with bounded failover
  (`iteration.Failover`, epoch-scoped), never a BOARD/STATE blocker; all
  routes exhausted → `RUNTIME_PAUSED` with Work preserved;
- operator due or safety valve tripped → `OPERATOR_WAIT` (the valve is
  never weakened);
- canonical terminal boundary proven and nothing executable remains →
  `VALID_TERMINAL` — the only decision on which the UI may print goal
  completion (`iteration.may_report_goal_complete`);
- executable action remains → `AUTO_KICK`: run the next iteration;
- otherwise → `OPERATOR_WAIT`: an unproven end pauses truthfully.

`response_surface`'s `AUTONOMOUS_HANDBACK` and `autonomy recall`'s
`AUTO_KICK` are the same invariant at their own layers; this section only
names the exit order. A host with no iteration gate enforces this at its
iteration controller by querying
`saipen iteration --json` (guard-safe: `--caps-file PATH`, `--cap NAME=VALUE`,
`--executor ID`, `--all-exhausted`) instead of trusting the model's final
return. Unknown or unreadable verdicts fail safe to `RUNTIME_PAUSED`, never
to goal completion.

## Unattended execution owner

`supervisor.decide` names ONE verdict; `worker.supervise` acts on it. From
`<saipen_home>/tools`:

    python -m saipen_engine.worker supervise --project-root P \
        --agent-json '["opencode","run","--model","{model}","cc"]' \
        --model M [--fallback-model M2 ...] [--max-cycles N] \
        [--slice-timeout IDLE_S] [--max-slice-seconds HOST_S]

Each cycle: decide; stop cleanly on IDLE, OPERATOR_ACTION_DUE,
NO_PROGRESS_LOOP or AMBIGUOUS_AUTHORITY; await (never steal) a HEALTHY or
SUSPECT foreign lease; otherwise take ONE lease generation, launch the host,
heartbeat the lease while it lives, kill it on freeze or outside fence, then
fence the finished generation. QUALITY-TIME-01: `--slice-timeout` bounds time
without durable canonical progress (STATE last_event/phase/task/next_action/
blocker) and every progress restarts it; `--max-slice-seconds` (default 4x) is
the host bound, and a progressing generation reaching it ends SLICE_BOUNDED,
not failed: the next generation continues the same epoch. A fenced generation
reads EXPIRED, fails `mutation_allowed` and cannot heartbeat itself back.

Failures use one closed vocabulary (`supervisor.FAILURE_CLASSES`): WORKER_CRASH
and HOST_RUNTIME_FAILURE replace the generation; RATE_LIMITED,
PROVIDER_UNAVAILABLE and NETWORK_UNAVAILABLE back off and retry;
QUOTA_EXHAUSTED and MODEL_UNAVAILABLE move to the next model ONLY from the
operator's `--fallback-model` list, else stop with an operator action;
AUTH_FAILED always stops; UNKNOWN stops after a repeat. A class is read only
from error channels (stderr, non-JSON stdout, JSON error events), never the
agent transcript; a silent nonzero exit is WORKER_CRASH. CAPABILITY_UNAVAILABLE
(absent host, runtime without tools) is never reasoning failure: it moves only
to an authorized runtime, else stops as a truthful blocker. The model-selection
cache stays separate from canonical Work. An Attempt-open event may carry an
immutable runtime provenance snapshot from the launch context; it changes no
Work, Source, checkpoint or epoch. No failure writes canonical state; only the
agent incarnation changes.

## Wave 1 — identity and capabilities

`agent != model`. `--agent <id>` selects the acting SAIPEN seat for
ownership/handover; it never identifies a provider or model. Read-only:

```text
saipen runtime [--runtime-info <json-file>] [--json]
```

Metadata precedence: explicit `--runtime-info`, then the `SAIPEN_RUNTIME_INFO`
JSON-file path, then UNKNOWN. Nothing is guessed from prose, seat name or
executable. Metadata is read once, <= 64 KiB, strict UTF-8 JSON, from a regular
non-symlink/non-reparse file, and never persisted by this projection.

Schema version 1 accepts optional `harness`, `provider`, `model`, `variant`,
`effort` and `capabilities`. Identity values are bounded strings or null;
capability values are `true`, `false` or null (absent = null = UNKNOWN):

Canonical Attempt provenance is captured only from a host-launch
`SAIPEN_RUNTIME_INFO`; `--runtime-info` is read-only telemetry, never
provenance. Attempt opening snapshots the stable `executor_identity` from the
LOG actor separately from `runtime_provider`, `runtime_model` and
`runtime_effort`; the snapshot and its SHA-256 digest live in the append-only
Attempt-open LOG event, so restarts reconstruct the original values instead of
sampling a successor. Missing or rejected metadata records null runtime fields;
no seat, executable, prompt or default fills the gap. Legacy Attempt events
project as unavailable benchmark evidence.

The capability vocabulary is operational: `shell`, `filesystem`, `patch`,
`browser`, `web`, `subagents`, `parallel_subagents`, `skills`, `mcp`,
`structured_output`, `persistent_session`, `context_compaction`,
`reasoning_effort`, `tool_search`, `programmatic_tool_calling`. It holds no
personality claims. A runtime document may not define `agent`.

## Wave 2 — executable task classes, strategies and context budgets

The strategy vocabulary is ONE deterministic decision, not prose. Read-only:

```text
saipen runtime [--task-class IMPLEMENT|REPAIR|VERIFY|RESEARCH|AUDIT|MAINTENANCE]
              [--helper-reason isolated-research|independent-verification|
                              noisy-investigation|genuinely-parallel]
              [--control-plane] [--runtime-info <json-file>] [--json]
```

A task class describes the WORK, never a vendor, model or seat; no strategy
decision is persisted anywhere. An out-of-vocabulary class or helper reason is
REFUSED (`VALIDATION_FAILED`, zero writes), never coerced to the default.

| strategy | reached from | helper ceiling | context class |
|---|---|---|---|
| `LONG_BUILD` | `IMPLEMENT`, `MAINTENANCE`, ordinary `REPAIR` | 0 by default | `ORDINARY` |
| `BOUNDED_RESEARCH` | `RESEARCH` | 1 ephemeral scout | `MINIMAL` |
| `VERIFY_ONLY` | `VERIFY`, `AUDIT` | 0, or 1 independent verifier | `BOUNDED` |
| `RECOVERY` | `REPAIR --control-plane` | 0 | `RECOVERY` |

`LONG_BUILD` is the DEFAULT: one primary worker, ZERO helpers (`parent 1 /
subagents 0`). A helper needs a concrete reason from the list above; "more
agents might be faster" buys none. The highest ceiling any reason buys is 2.
Control-plane repair is RECOVERY only when declared, never inferred.

Recursion is DENIED BY POLICY (`max_subagent_depth = 1`); host ENFORCEMENT of
that depth is reported `UNKNOWN`, since the vocabulary exposes no depth
control. A child never inherits the parent transcript: its packet carries only
objective, relevant acceptance criteria, necessary paths, known evidence,
constraints, small needed excerpts and the result format, bounded by
`child_packet_ceiling_bytes`. A child RETURNS only conclusion, evidence,
changed paths, focused test result, unresolved blocker and next action.
Research and one-shot reviewer helpers are ephemeral; only the primary worker
keeps continuity.

Noisy deterministic commands save full output ONCE as durable evidence; the
model receives only the command, exit code, failure count, relevant failures, a
bounded tail and the artifact path. Expensive validators re-run at meaningful
boundaries after their inputs change, not after every small edit.

Progress is DURABLE progress -- a repository diff, an acceptance clause moved
to VERIFIED, a focused regression turning green, a blocker narrowed by new
evidence, a canonical checkpoint advanced, a contradiction removed -- never
model prose. Expensive cycles without durable progress change the method, NOT
the worker count; budget exhaustion is reported `PAUSED_BUDGET`, never DONE.

## Installed-runtime freshness (prelaunch)

A managed host loads an INSTALLED runtime, not the clone, so the installed
generation is protocol state and proving it is SAIPEN's job, never the
operator's (no hand hash comparison, no ad-hoc injector re-run). One operation
owns it:

    saipen runtime --prelaunch --adapter <registry-id> [--no-resync] [--json]

It is install-scoped and runs OUTSIDE a bound project, because a stale runtime
is exactly when no project can resolve yet.

| `code` | meaning | may a host start? |
|--------|---------|-------------------|
| `RUNTIME_CURRENT` | installed generation matches canonical; nothing written | yes |
| `RUNTIME_RESYNCED` | stale generation restored by the canonical installer; verified | yes |
| `RUNTIME_STALE` | stale, and `--no-resync` was requested | no |
| `RUNTIME_RESYNC_FAILED` | installer did not run, failed, or left a differing surface | no |
| `CANONICAL_RUNTIME_SOURCE_UNPROVEN` | no provenance marker and the executing tree fails the architecture proof, or the shipped surface is unprovable (nothing installed) | no |
| `HOST_UNIDENTIFIED` | no adapter named and none inferable from provenance | no |

`ok` is true exactly for the two green codes. `requires_host_restart` is true
exactly when bytes changed; its only honest consumer is a launcher starting the
host AFTER the call -- a loaded plugin is never hot-replaced.

Every result carries `canonical_fingerprint`, `installed_fingerprint`,
`fingerprint_match`, `marker_fingerprint`, `engine_diff`, `hook_problems`,
`launcher_problems` and `provenance_problems`. Freshness covers the ENGINE
surface, the blocking guard plugin, the installed `bin/` launchers (which must
name the INSTALLED `tools/saipen.py`, never the clone) and the installer's
provenance marker.

Both fingerprints are the ONE shipped-runtime generation identity
(`tools/saipen_engine/runtime_surface.py`): every `copy_trees` member and
required `files` entry of `MANIFEST.json`, LF-normalised text and byte-exact
binary, source and flattened layouts under one logical name. Each side is
digested over its OWN inventory, so an extra installed module is a different
generation; `fingerprint_match` is the verdict and `engine_diff` only names
files. The marker's `runtime_fingerprint` must equal that identity; a stamp in
a tree never proves the tree. `saipen status` applies the same rule: a home is
current only when its bytes, the engine its guard hook delegates to and the
home its instruction block names all prove the source generation.

Authority is proven, never guessed, and PATH is never identity: the
installer's `.saipen_runtime.json` marker first, else the executing tree when
it passes the shipped architecture proof; a canonical clone serves every host,
so it requires `--adapter`.

`saipen --agent <seat> launch <host>` runs this first and refuses the launch on
any non-green code. A host already running when its installed bytes change is
refused per-tool with `PLUGIN_RESTART_REQUIRED`, which names a restart, not an
injector.

## Staged delivery

Waves 1-2 claim no speed, quality, token or cost gain. Until Waves 3-5 land,
no strategy/model/evaluator recommendation is inferred; adapters preserve
UNKNOWN where the harness cannot establish a fact, never fake unsupported
reasoning controls, and keep project state portable across provider/model
switches.

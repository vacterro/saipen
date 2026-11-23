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

## Turn entry — AUTO_RECALL / AUTO_KICK (T-1446)

The agent is disposable; the execution is not. A host may swap model, provider
or session mid-Work; the successor has no private memory but still sees the
conversation, including the `cc` that started the mission.

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
closed-grammar fields, so project text never becomes system instruction (P0-1).

Host seams. OpenCode `saipen-guard.js` runs the recall in
`experimental.chat.system.transform` (before EVERY model request), takes
message identity from `chat.message` and marks consumption in
`tool.execute.before`. Hosts without a per-request hook get the rule only as
instruction text: an external host boundary, not a solved case.

## Unattended execution owner (T-1446)

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

```json
{"schema_version": 1, "harness": "opencode", "provider": "openai",
 "model": "example-model", "variant": "high", "effort": "xhigh",
 "capabilities": {"shell": true, "parallel_subagents": null,
                  "structured_output": true}}
```

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

Wave 1 supplies truthful identity/capability discovery; Wave 2 the executable
strategy/context economy. Neither claims a speed, quality, token or cost gain.
Waves 3-5 (thin host adapters, measured evaluations, evidence-only adaptive
routing) are not landed: until they are, no strategy/model/evaluator
recommendation is inferred, adapters preserve UNKNOWN when the harness cannot
establish a fact, never fake unsupported reasoning controls, and keep project
state portable across provider/model switches.

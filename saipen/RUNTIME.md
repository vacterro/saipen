# SAIPEN Adaptive Runtime

This document owns runtime identity/capability semantics. CORE still owns Work,
state, commands, precedence, checkpointing, and completion. Runtime data is
replaceable session telemetry; it cannot make project truth provider-specific.

## Wave 1 — identity and capabilities

`agent != model`. `--agent <id>` selects the acting SAIPEN seat and participates
in ownership/handover. It never identifies a provider or model. The read-only
projection is:

```text
saipen runtime [--runtime-info <json-file>] [--json]
```

Runtime metadata source precedence is explicit `--runtime-info`, then the
documented `SAIPEN_RUNTIME_INFO` JSON-file path, then UNKNOWN. No model/provider
is guessed from prose, the seat name, or the running executable. Metadata is
read once, bounded to 64 KiB, strict UTF-8 JSON, and must be a regular
non-symlink/non-reparse file. It is never persisted into STATE, BOARD, LOG, a
cache, or a handover.

Schema version 1 accepts optional `harness`, `provider`, `model`, `variant`, and
`capabilities`. Identity values are bounded strings or null. Capability values
are `true`, `false`, or null; absent values render as null (UNKNOWN):

```json
{
  "schema_version": 1,
  "harness": "opencode",
  "provider": "openai",
  "model": "example-model",
  "variant": "high",
  "capabilities": {
    "shell": true,
    "parallel_subagents": null,
    "structured_output": true
  }
}
```

The bounded capability vocabulary is operational: `shell`, `filesystem`,
`patch`, `browser`, `web`, `subagents`, `parallel_subagents`, `skills`, `mcp`,
`structured_output`, `persistent_session`, `context_compaction`,
`reasoning_effort`, `tool_search`, `programmatic_tool_calling`. It contains no
personality claims. A runtime document may not define `agent`.

## Wave 2 — executable task classes, strategies and context budgets

Wave 2 turns the strategy vocabulary into ONE deterministic decision instead of
prose. The read-only surface is:

```text
saipen runtime [--task-class IMPLEMENT|REPAIR|VERIFY|RESEARCH|AUDIT|MAINTENANCE]
              [--helper-reason isolated-research|independent-verification|
                              noisy-investigation|genuinely-parallel]
              [--control-plane] [--runtime-info <json-file>] [--json]
```

A task class describes the WORK, never a vendor, provider, model or seat, and
no strategy decision is ever persisted into STATE, BOARD, LOG, a cache, or a
handover. An out-of-vocabulary task class or helper reason is REFUSED
(`VALIDATION_FAILED`, zero writes); it is never coerced into the default.

The bounded strategy vocabulary is:

| strategy | reached from | helper ceiling | context class |
|---|---|---|---|
| `LONG_BUILD` | `IMPLEMENT`, `MAINTENANCE`, ordinary `REPAIR` | 0 by default | `ORDINARY` |
| `BOUNDED_RESEARCH` | `RESEARCH` | 1 ephemeral scout | `MINIMAL` |
| `VERIFY_ONLY` | `VERIFY`, `AUDIT` | 0, or 1 independent verifier | `BOUNDED` |
| `RECOVERY` | `REPAIR --control-plane` | 0 | `RECOVERY` |

`LONG_BUILD` is the DEFAULT. Ordinary implementation is one primary worker and
ZERO helpers: the expected topology is `parent 1 / subagents 0`. A helper needs
a concrete reason from the bounded list above; "more agents might be faster" is
deliberately absent, so an unnamed reason buys no helper at all. The highest
ceiling any justification buys is 2. Protocol/control-plane repair is RECOVERY
only when it is declared; it is never inferred from an ordinary repair.

Helper policy facts, stated exactly as far as they are enforced: recursion is
DENIED BY POLICY (`max_subagent_depth = 1`), while the host ENFORCEMENT of that
depth is reported `UNKNOWN`, because the capability vocabulary exposes no depth
control. A child never inherits the accumulated parent transcript: a child
packet carries only the objective, the relevant acceptance criteria, the
necessary paths, known evidence, explicit constraints, the small excerpts
needed to work, and the requested result format, and it is bounded by
`child_packet_ceiling_bytes`. A child RETURNS only the conclusion, the evidence,
changed paths, the focused test result, the unresolved blocker and the next
action. Research/scout and one-shot reviewer helpers are ephemeral; only the
primary implementation worker keeps continuity.

Context economy is bounded the same way for noisy deterministic commands: the
full output is saved ONCE as durable evidence, and only the command, exit code,
failure count, the relevant failures, a bounded tail and the artifact path are
returned to the model. Expensive validators are re-run at meaningful boundaries
after the relevant inputs change, not after every small edit.

Progress is judged by DURABLE progress — a repository diff, an acceptance
clause moved to VERIFIED, a new focused regression turning green, a blocker
narrowed by new evidence, a canonical checkpoint advanced, or a state
contradiction removed — never by model prose. Several expensive cycles without
durable progress trigger checkpoint/investigation-method change, NOT more
workers, and budget exhaustion is always reported as `PAUSED_BUDGET`; it is
never reported as DONE.

## Installed-runtime freshness (prelaunch)

A SAIPEN-managed host loads an INSTALLED runtime, not the canonical clone. The
installed generation is therefore protocol state, and proving it is SAIPEN's
job, never the operator's: comparing hashes by hand and re-running an injector
is not a supported workflow.

One operation owns it:

    saipen runtime --prelaunch --adapter <registry-id> [--no-resync] [--json]

It is install-scoped, so it runs OUTSIDE a bound project -- a stale runtime is
exactly the condition in which no project can be resolved yet.

Consumer contract, stable and machine-readable:

| `code` | meaning | may a host start? |
|--------|---------|-------------------|
| `RUNTIME_CURRENT` | installed generation already matches canonical; nothing was written | yes |
| `RUNTIME_RESYNCED` | installed generation was stale and the canonical installer restored it; verified | yes |
| `RUNTIME_STALE` | stale, and `--no-resync` was requested | no |
| `RUNTIME_RESYNC_FAILED` | the installer did not run, failed, or left a surface that still differs | no |
| `CANONICAL_RUNTIME_SOURCE_UNPROVEN` | no provenance marker and the executing tree fails the architecture proof | no |
| `HOST_UNIDENTIFIED` | no adapter named and none inferable from provenance | no |

`ok` is true exactly for the two green codes. `requires_host_restart` is true
exactly when bytes changed, and the only honest consumer of that flag is a
launcher that starts the host AFTER the call: a loaded plugin is never
hot-replaced and a running process never changes generation in place.

Evidence carried on every result: `canonical_fingerprint`,
`installed_fingerprint`, `fingerprint_match`, `marker_fingerprint`,
`engine_diff`, `hook_problems`, `launcher_problems`, `provenance_problems`.
Freshness covers the ENGINE surface, the blocking guard plugin, the installed
`bin/` launchers (which must name the INSTALLED `tools/saipen.py`, never the
clone) and the installer-written provenance marker.

Authority is proven, never guessed, and PATH is never identity: the installer's
`.saipen_runtime.json` marker first, otherwise the executing tree when it
passes the shipped architecture proof -- and a canonical clone serves every
host, so it requires `--adapter` rather than inferring one.

The supported explicit launch (`saipen --agent <seat> launch <host>`) invokes
this before starting the host and refuses the launch on any non-green code, so
an ordinary session never reaches an unproven runtime. A host already running
when its installed bytes change is still refused per-tool with
`PLUGIN_RESTART_REQUIRED`; that refusal names a restart, not an injector.

## Staged delivery

Wave 1 supplies truthful identity/capability discovery. Wave 2 supplies the
executable strategy/context economy above. Neither claims a speed, quality,
token, or cost improvement.

1. Wave 3 adds thin OpenCode, Codex, Antigravity, and Claude Code adapters that
   map supported capabilities without copying Core semantics.
2. Wave 4 adds representative evaluations, telemetry, configuration comparison,
   and harness ablations.
3. Wave 5 permits explainable adaptive routing only from measured evidence.

Until those waves land, no strategy/model/evaluator recommendation is inferred.
Adapters must preserve UNKNOWN when the harness cannot establish a fact, must
not fake unsupported reasoning controls, and must keep canonical project state
portable across provider/model switches.

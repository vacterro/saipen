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

## Staged delivery

Wave 1 supplies only truthful identity/capability discovery and its diagnostic.
It does not claim a speed, quality, token, or cost improvement.

1. Wave 2 adds bounded task classes, logical strategies, context budgets, and
   just-in-time context/skill selection.
2. Wave 3 adds thin OpenCode, Codex, Antigravity, and Claude Code adapters that
   map supported capabilities without copying Core semantics.
3. Wave 4 adds representative evaluations, telemetry, configuration comparison,
   and harness ablations.
4. Wave 5 permits explainable adaptive routing only from measured evidence.

Until those waves land, no strategy/model/evaluator recommendation is inferred.
Future adapters must preserve UNKNOWN when the harness cannot establish a fact,
must not fake unsupported reasoning controls, and must keep canonical project
state portable across provider/model switches.

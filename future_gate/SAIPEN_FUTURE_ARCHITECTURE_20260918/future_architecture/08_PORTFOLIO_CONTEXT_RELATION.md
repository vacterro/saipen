# RELATION TO OPTIONAL PORTFOLIO CONTEXT

STATUS: ARCHITECTURE REFERENCE

Expected related file:

    ../future_gate/FUTURE GATE — OPTIONAL PORTFOLIO CONTEXT PROVIDER_20260918.md

## Separation

Portfolio Context answers:

    what deserves attention?

Global Dispatcher answers:

    which free worker gets which eligible project now?

Local SAIPEN answers:

    what is legally actionable inside this project?

Global Lease Broker answers:

    who may attempt mutation of this project now?

Worker runtime answers:

    execute the assignment

## Dependency direction

Dispatcher MAY consume Portfolio Context.

Dispatcher MUST NOT require Portfolio Context.

If AUDAPACK disappears:

    project registry still works
    local SAIPEN still works
    lease broker still works
    dispatcher uses deterministic fallback ordering

## No circular dependency

Allowed:

    AUDAPACK understands SAIPEN project metadata

Allowed:

    SAIPEN dispatcher reads optional portfolio snapshot

Forbidden:

    SAIPEN Core requires AUDAPACK to start/status/recover/continue

Forbidden:

    AUDAPACK priority grants SAIPEN mutation authority

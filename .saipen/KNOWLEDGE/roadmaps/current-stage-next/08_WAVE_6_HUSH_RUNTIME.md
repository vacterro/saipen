# 08 — WAVE 6: REAL HUSH RUNTIME

## Goal

Activate the already-planned execution policy only after phase narration independence and Audit Inbox routing are stable.

## Current truth

REGISTRY currently marks HUSH:

`planned`

Do not flip it until an actual runtime path exists.

## Syntax

Support:

`hush <task>`

and slash form where applicable.

HUSH is a modifier over normal task semantics.

Not a phase.

Not a domain skill.

## Execution

Conceptually:

```text
parse HUSH modifier
→ activate task-local execution policy
→ remove modifier
→ normal SAIPEN routing
→ normal semantic state/evidence
→ suppress discretionary narration
→ mandatory interaction still allowed
→ bounded final summary
→ eject policy
```

## Must compose with Audit Inbox

`hush cc`

must still:

- resume active Work correctly;
- discover audit;
- capture Source;
- execute;
- verify;
- close;
- delete safely.

Only narration changes.

## Required tests

- modifier activation;
- command meaning unchanged;
- phase lifecycle unchanged;
- tool effects unchanged;
- mandatory destructive/blocked prompt not suppressed;
- audit transition narration suppressed;
- final result contract enforced;
- policy does not leak into next task.

## Completion bar

1. real runtime path;
2. REGISTRY status changes from planned only after proof;
3. fake/no-op HUSH tests removed;
4. `hush cc` dogfood green;
5. semantics equivalent to normal cc.

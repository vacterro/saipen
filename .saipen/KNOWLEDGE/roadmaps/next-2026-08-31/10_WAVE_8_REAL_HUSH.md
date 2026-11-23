# 10 — WAVE 8: REAL HUSH RUNTIME

## Goal

Turn the prepared EXECUTION policy into actual task-local behavior.

Current REGISTRY status is correctly planned.

Do not change it until runtime proof exists.

## Semantics

`hush <task>`

means:

```text
activate task-local execution policy
→ strip HUSH modifier
→ normal resolver
→ normal phases/tools/state/evidence
→ suppress discretionary narration
→ preserve mandatory interaction
→ bounded final
→ eject policy
```

## Not a phase

HUSH does not change:

- Work ownership;
- phase transitions;
- Source intake;
- Audit Inbox;
- evidence;
- recovery;
- safety.

## Required composition

Must prove:

`hush cc`

behaves semantically the same as `cc`.

If audit is present:

- same audit selected;
- same receipt/work;
- same phase path;
- same close/delete semantics.

Only narration differs.

## Mandatory output

HUSH cannot suppress:

- destructive authorization;
- unresolved ambiguity;
- irrecoverable BLOCKED;
- required manual verification;
- safety refusal.

## Lifecycle

HUSH must not leak into the next independent task.

## Completion bar

1. actual parser/runtime modifier exists;
2. task-local policy state exists;
3. narration suppression tested;
4. mandatory interaction preserved;
5. `hush cc` parity green;
6. REGISTRY flips from planned only after proof.

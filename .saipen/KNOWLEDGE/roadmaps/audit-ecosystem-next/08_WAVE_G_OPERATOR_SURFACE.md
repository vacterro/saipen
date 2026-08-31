# 08 — WAVE G: OPERATOR SURFACE

## Goal

Keep the user-facing workflow absurdly simple.

Primary workflow:

```text
cc
```

That is the feature.

## `cc`

At the correct routing stage:

- close pending audit cleanup if safe;
- discover workable audit;
- continue it;
- otherwise ordinary Work;
- Improve only last.

No separate "scan audits first" ritual.

## `saipen status`

Add compact optional projection:

- audit pending count;
- active layer;
- bound Source Receipt;
- bound Work;
- closed-pending-delete count;
- invalid count;
- last allocated audit ID.

Do not dump audit body text.

## `saipen next`

Read-only answer should identify an audit carrier when it would own the next continuation.

## Optional explicit admin commands

Only if useful:

- `saipen audit status`
- `saipen audit enqueue`
- `saipen audit inspect <N>`

Do not require them for ordinary operation.

## Notifications

No noisy popup/log spam.

A future UI may show:

`Audit 18 → SRC-055 → T-1301`

but the protocol must not depend on UI.

## Wave G completion bar

1. User can operate with `cc`.
2. status is compact.
3. next is read-only.
4. admin commands are optional.
5. no duplicate command system appears.

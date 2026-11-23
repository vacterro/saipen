# T-1943 — operator acceptance: the one remaining action

Both agent-side preconditions this ticket used to list are done. What is left is
a single native action only you can perform. This file is the exact procedure.

## What is already true (measured 2026-10-30, canonical HEAD 66ef622a)

```
installed hook   C:\Users\vac34\.zcode\hooks\saipen-guard.py
sha256           7864a6d8209809b91345da5ebfb6f3f17910779ca953cea94e261458f886b408
bytes            31593
canonical        extensions/adapters/zaicode/saipen-guard.py — identical, committed
host doctor      hook: current, delegated_current: true, problems: []
registration     ~/.zcode/cli/config.json hooks.enabled = true
                 events.UserPromptSubmit[0].hooks[0] = python -c <HOOK_BOOTSTRAP>
                   saipen-guard.py --host zaicode --saipen-root <canonical>
native seal      3 ingresses sealed with broker HMAC: 2026-10-28T19:30:48Z,
                 2026-10-28T19:30:54Z, 2026-10-29T11:07:45Z
mechanism        46 tests OK (test_t1494_continuation_authority,
                 test_t1875_maintenance_wiring, test_t1933_zaicode_goal_seal)
current STATE    continuation_authority: operator_required
                 authority_source: E-18977   goal_ingress: None
                 goal_tickets: 18 of 20       next_action: "saipen continue"
```

## The action

In the **native ZAICODE UI**, in this project
(`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`), send one message that is a
single command whose head is the goal verb. Copy either line exactly:

```
gg hold the current objective and continue the backlog to fixpoint
```

or, equivalently:

```
saipen goal hold the current objective and continue the backlog to fixpoint
```

Requirements the hook enforces by reading your own bytes:

- it must be **one** command, not prose and not a multi-line handoff;
- the objective must be non-empty after the verb;
- `cc` alone stays a continuation and will never produce persistence.

## What you should see when it worked

`saipen status` then reports:

```
continuation_authority: operator_persistent
authority_source: E-<the new goal pivot event>
authority_until: goal_complete
safety_valve_mode: checkpoint
goal_ingress: goal-<16 hex>
execution_intent: goal
```

and a new `DEC: goal pivot -- …` line appears in the journal. From that point the
20/21/28/50/100-ticket checkpoints pass mechanically under the grant, and
`SRC-342:R005` becomes observable → `T-1943` closes.

If `continuation_authority` still reads `operator_required`, the seal did not
happen. The hook prints a typed `seal` block naming the stage and the exact
broker refusal code (`issue-origin` vs `register-worker`); that block is the
diagnosis, and it is worth pasting back here.

## Why this cannot be done from a seat

- An agent shell is refused by design: measured
  `BROKER_CLIENT_NOT_AUTHENTICATED / HOOK_NOT_FOUND`, "a shell tool call is not a
  hook". The agent's shell is the hook's *sibling*; a seal verifies only from a
  child of the hook.
- Replaying a sealed envelope cannot work: the seal binds `request_digest`,
  `nonce`, `expires` and the registering worker.
- Editing `.saipen/STATE.md` is barred by SRC-342 §5 and R007, and `prove()`
  would reject it anyway — it walks the pivot, the committed receipt and the
  separated broker.

## Deliberately not done

`saipen host repair` was **not** run. The six drifted bundle entries include
`tools/freshness.py` and `tools/saipen_engine/core_unit.py`, which are staged
uncommitted edits from another live session; repairing now would publish an
uncommitted tree, which SRC-342 §5 forbids. The part that matters for this
ticket — the hook — is already current and byte-identical.

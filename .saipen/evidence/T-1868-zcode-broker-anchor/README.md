# T-1868 — the operator's reauthorization never reached the engine

## The defect the operator reported

> "продолжай до конца … излечи этот баг с reauth tickets 20+ … это должно
> решаться автоматически и никогда не должно тревожить юзера и заставлять его
> там какие то команды выполнять"

A bounded goal run stopped at the 20-ticket cap and asked the operator to send
`cc` "through authenticated native ingress". The operator sent it. The run
asked again. That loop is the bug, and it had two independent causes — each one
sufficient on its own to make every operator message arrive as
`witness: model_supplied`.

## Cause 1 — the hook read a field the host never sends

ZAICODE's `UserPromptSubmit` hook input is built by
`createCompatibleHookStdin` (`apps/zcode-cli/packages/core/src/hooks/
configured-runner-input.ts`). It carries `prompt`, `hook_event_name`,
`session_id`, `cwd`, `turnId`. It **never** carries `host_ingress`.

The shipped adapter read only `event["host_ingress"]` and returned before it
looked at anything else:

```
ingress = event.get("host_ingress")
if not isinstance(ingress, dict):
    print(json.dumps({"ok": True, "ingress_id": None, "sealed": False}))
    return 0
```

So on the one host that actually delivers operator prompts, the hook ran,
answered green, and minted nothing. `operator_task.witness` then found no
carrier and recorded the operator's own words as `model_supplied` — and
`goal_authority.reset_authority` fell through to `bounded_resume_requirement()`,
which demands exactly the carrier the hook had just dropped.

Measured on a real host payload, same event, both readers:

| Reader | Answer |
|---|---|
| pre-fix | `{"ok": true, "ingress_id": null, "sealed": false}` |
| post-fix | `{"ok": true, "ingress_id": "ing-199d82481af0f7c7", "destination_op": "start", "sealed": false}` |

The hook was not unreachable: `~/.zcode/cli/config.json` has
`hooks.enabled: true`, and config hooks are registered by
`createConfiguredHookRegistrations` with **no** workspace trust-admission gate
(that gate applies only to workspace-snapshot hooks). The absent
`~/.zcode/security/workspace-hook-trust-v1.json` was never the problem.

## Cause 2 — the session string outranked the broker's proof

`operator_task.witness` bound each envelope to the delivering session by
comparing `SAIPEN_HOST_SESSION` to the envelope's `session_id`. ZAICODE exports
no such variable to the processes the model runs, so `delivering_session` was
`None` while the envelope named a real host session. The refusal fired **before**
the separated broker was asked, so a genuinely broker-sealed origin was refused:

```
'code': 'HOST_PROVENANCE_UNAVAILABLE'
'delivering_session': None
'carrier_session': 'host-session-1'
```

The string compare exists because a bare envelope file is writable by anyone.
A broker-sealed `operator_origin` is verified against the **caller's OS
ancestry** (`verify_operator_origin` → `_worker`) — a stronger fact about the
same question. The fix orders the broker above the string, and only when an
origin is actually present.

## The fix

`extensions/adapters/zaicode/saipen-guard.py` — new `_declared_ingress(event)`:
honours a declared `host_ingress` first and unchanged, otherwise builds the
envelope from the host's own fields, computing `request_digest` with the
engine's own `ingress_digest` so admission recomputes exactly the declared
value instead of rejecting a format the hook invented. `main()` binds the
project before ingress, reads the session from `session_id` **or** `sessionId`,
and takes `message_id` from `turnId`/`trace_id` so two sends of the same words
stay two deliveries.

`tools/saipen_engine/operator_task.py` — inside `witness()`, before the
`matching is None and candidates` refusal, a sealed candidate is preferred over
the session-name filter **only when `delivering_session is None`**. An unsealed
envelope keeps the old refusal unchanged.

### The correction the family gate forced

The first revision deferred to a sealed candidate whenever the session compare
failed, and the declared core-unit family reded on
`test_response_delivery.CompletedPartDelivery.test_a_response_cannot_borrow_another_native_sessions_proof`:
native session A's broker-sealed proof was answering for a **different named**
session B. That is the replay hole T-1822 closed, reintroduced by treating "the
engine has no name" and "the engine has a different name" as the same case.

The deferral is now bounded to the one shape it exists for. A named foreign
session keeps the exact `HOST_PROVENANCE_UNAVAILABLE` refusal.

The cross-session case had also been written as
`assertFalse(authority_for_provenance(witness)["user_explicit"])` — which a
refusal satisfies just as well as a legitimate denial, so it stayed green while
the hole was open. It now asserts the refusal itself: the code, both session
identities, and the absence of a `witness` key.

## Evidence in this directory

| File | What it shows |
|---|---|
| `diagnosis.log` | The six-step SCOUT chain, including the earlier hypothesis (Claude-only `HOST_IMAGES`) that measurement **disproved**: `saipen/REGISTRY.json` already declares `hosts.zaicode`, so no registry or broker-policy change was needed. |
| `regression.json` | The measured-pair contract: one oracle set (`test_t1868_zaicode_ingress`, `test_t1822_carrier_binding`), two subjects, pre-fix carriers under `before/`. |
| `before/` | The pre-fix subject bytes. The hook carrier restores the exact early return; the `operator_task` carrier removes only the sealed-origin deferral (915 bytes). Both compile. |

Executed record (second cycle, after the correction):
`.saipen/evidence/regression/regression-execution-58f965accf814edd8b03e29f2fdb086b.json`

| Half | Result | Verifier | Ran | Failed | Exit |
|---|---|---|---|---|---|
| pre-fix subject | FAIL | `851a7de4…` | 19 | 6 | 1 |
| post-fix subject | PASS | `851a7de4…` | 19 | 0 | 0 |

The verifier is identical on both halves and the subject digest changed, so
`oracle.regression_pair_verdict` admits the pair: `ADMISSIBLE`.

The six pre-fix failures are the two defects measured independently — the four
transport cases that require an ingress, the in-test red control (which searches
for a marker the pre-fix reader does not have), and the sealed-origin survivor.

The first cycle's record (`regression-execution-c55cf5a7…`) used an oracle that
still allowed the replay hole, so it is superseded, not cited.

## Tests

`tools/test_t1868_zaicode_ingress.py` (7 cases) pins the transport contract:
a real host event admits ingress; the envelope carries the engine's digest of
the prompt (the admission path recomputes it and would refuse a private
format); `cc` stays `continue`; a `Stop` event and an empty prompt deliver
nothing; a declared envelope still wins; and `test_the_pre_fix_hook_fails_this_suite`
runs the pre-fix reader through the operator's real bootstrap and asserts it
answers green-with-null.

`tools/test_t1822_carrier_binding.py` gains `SealedOriginOutranksTheSessionName`
(3 cases): a sealed origin survives an unnamed delivering session, an unsealed
envelope keeps `HOST_PROVENANCE_UNAVAILABLE`, and a sealed origin still cannot
grant authority to a different session. The 8 pre-existing replay cases stay
green, so the relaxation is not a replay hole.

That third case is the one the family gate proved was too weak, and the one that
now carries the correction: it asserts the refusal, not merely the absence of
`user_explicit`.

## Coupled surfaces

`saipen-guard.py` (host transport) → `operator_task.admit_host_ingress`
(envelope) → `operator_task.witness` (authority) → `goal_authority`
(reauthorization). The hook still mints nothing itself; it only forwards what
the host delivered and binds the broker's seal to it.

## Note on the installed copy

`~/.zcode/hooks/saipen-guard.py` is byte-identical to this artifact
(sha256 `bf9e9a900c86502ce78bd07b3e4eada0f09f69a7ab116602551e74510ca25755`)
and passes `--self-test`. The hook resolves the engine through
`--saipen-root <project>/tools`, which is why the transport suite passes a
throwaway project as the event `cwd` while the root points at this repository —
envelopes land in the project, the engine loads from the repo.

# T-1859 — host repair performed 2026-11-17; the two operator facts still gate AC-01

Measured read-only before acting:

```
saipen host doctor --json
  authority.running: false
  authority.generation_current: null
  authority.expected_generation: svc-29bc598bc7951d8ee87c0db0
  authority.mode: degraded (DEGRADED_ALLOWED, operator-set)
  needs_action: opencode, claude, claude, codex, zcode-production, gemini,
                codebuddy, freebuff
  next_action: saipen host repair
```

This is the same failure the incident recorded on 30.10: the live authority
service was down, so genuine operator prompts could not be independently
authenticated and were recorded as `model_supplied`.

## Repaired with the canonical command

```
saipen host repair --json
  ok: true, code: HOST_REPAIRED
  authority.running: true
  authority.pid: 34688
  authority.instance: broker-420d203c539e843260112b10
  authority.generation_current: true
  needs_action after: [claude]
  broken: []
```

The remaining `claude` item is the second profile
`C:\Users\vac34\.claude-account2` (`STALE_RUNTIME`, hook generation differs). It
is not the deployed ZAICODE UI and is unrelated to T-1859's surface; the
`zcode-production` adapter is now current (`needs_action` no longer lists it).

## What the repair does not and cannot supply

`saipen acceptance T-1859 --dry-run` still reports AC-01 `UNVERIFIED`, witness
LIVE, `counts: {"UNVERIFIED": 1}`; AC-02/03/04 are satisfied on the recorded
current-cycle evidence (focused gate ran=147, records e0e4cbab… and …).

AC-01 needs two operator facts this agent cannot mint:

1. An operator-signed `acceptance_witness` Source whose body is
   `{schema:1, kind:'acceptance_witness', work:'T-1859',
   contract_sha256:'002caf9420a3083c77217ffc3ec1bcc1710e0a90ff106ea3dad00ee5eae35cab',
   build_boundary:19475,
   criteria:{'AC-01':{result:'PASS', witness:'LIVE', surface:'<operator surface>'}}}`.
   The gate resolves it through `acceptance_contract._observation` and refuses a
   model-written file by construction (P0-07 class).
2. A genuine operator `cc` submitted through the deployed ZAICODE UI **into
   AUDAPACK** at a moment when that project is in goal mode with a spent bounded
   grant. Measured today, read-only:
   `V:\___VAC\__K\__CODE\_PY\_AUDAPACK\.saipen\STATE.md` has
   `execution_intent: converge` and no `goal_waves`, `goal_tickets` or
   `authority_source`, so `budget_exhausted` and `_valve_tripped` are both False
   and the hook `_renew` branch has no object.

No agent act may create AUDAPACK's goal authorization or submit the operator's
cc; doing either would manufacture the very witness the acceptance gate exists
to authenticate.

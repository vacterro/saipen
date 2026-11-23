# T-1954 BUILD -- Core disposition on saihunt/HUNT-016

The ticket forbids a package patch during intake (`payload: []`, and the verify
text says so). BUILD here is therefore a disposition plus a tracked decision,
not a code change.

## Verdict

**REPRODUCED.** HUNT-016 finding 2 holds on b152e6de: `record_producer_integration`
(`operations.py:26460`) is a complete, functioning writer with zero callers,
while `producer.py:2155` emits the same `producer_integration` receipt through a
separate `run_mutation` call.

saihunt's instrument behaved correctly -- its positive control (`record_crew_run`)
reported a definition, an import and a caller in the same `git grep` run that
reported the suspect as definition-only.

## What the independent pass added beyond HUNT-016

HUNT-016 established zero callers. SCOUT added the question that decides the
remedy: **is the orphan still compatible with the live path?**

It is not. Comparing the two writers on the same receipt contract:

| | orphan (`_plan_producer_integration`, `:26272`) | live (`producer.py:2155`) |
|---|---|---|
| `op_id` | `producer-integration-<uuid4>` -- random per call, so a re-integration of the same package against a moved HEAD collides and is REFUSED | `producer-integrate-<identity[:32]>-<head[:12]>` -- deterministic, bound to the input source |
| resulting source | taken from caller-supplied `resulting_source` / `resulting_source_fingerprint` arguments | measured inside the mutation by `_integration_receipt_metadata` against the live root |
| metadata finalizer | none | `_integration_receipt_metadata` records the real resulting identity |

The `op_id` difference is not a style preference: the comment at
`producer.py:2133-2145` records that a deterministic-but-identity-only `op_id`
was the E-3836 "treadmill root cause", and the orphan carries the older and
weaker of the two forms -- a fresh uuid on every call, which cannot be
idempotent at all.

So "wire the orphan as the canonical writer" is not a drop-in change: adopting
it would regress the E-3836 fix and lose the measured resulting identity.
**Deleting the orphan (and its `_plan_producer_integration` helper) is the
correct resolution**, and the live path already does what the orphan was meant
to do.

## Why this is filed rather than fixed

The ticket is an intake REVIEW hypothesis. Three separate tickets have now
measured this same fact without changing it:

1. HUNT-015 (2026-10-12) reproduced it and told Core to decide.
2. T-1725 (2026-10-16) reproduced it independently and closed as review-only.
3. T-1954 (this ticket) reproduced it again and added the compatibility
   finding above.

A fourth measurement with no action would be the actual defect. So BUILD files
a TODO that carries the decision, the evidence and the reason the delete is
correct -- and T-1954 closes on that disposition rather than silently absorbing
a finding it was not authorised to patch.

No source file is modified by this ticket. The evidence is read-only, as
saihunt's `payload: []` requires.

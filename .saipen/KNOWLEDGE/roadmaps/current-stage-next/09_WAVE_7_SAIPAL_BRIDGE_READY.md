# 09 — WAVE 7: SAIPAL BRIDGE READINESS

## Goal

Prepare SAIPEN as a safe consumer before launching full SAIPAL implementation.

Use the separate SAIPAL founding roadmap for the forensic analyzer itself.

## Producer-neutral envelope

Audit files may optionally carry:

- producer;
- producer_version;
- producer_item_id;
- created_at;
- severity claim;
- confidence claim;
- observed_project;
- related/amends audit;
- maintainer_verdict=PENDING.

All producer metadata is source claim, not maintainer truth.

Plain Markdown remains valid.

## SAIPAL capability

SAIPAL receives only:

- constrained audit enqueue;
- later optional read-only disposition lookup.

No Core write.

No BOARD write.

No STATE/LOG write.

## Provenance chain

Preserve:

```text
SAIPAL finding
→ audit/N
→ Source Receipt
→ Work
→ maintainer outcome
→ optional fix commit
```

## Feedback

Provide compact read-only disposition projection suitable for SAIPAL calibration.

Do not expose unrelated project data.

## No producer special cases

SAIPEN must not contain semantic branches like:

`if producer == SAIPAL: trust this`

SAIPAL audit enters normal Source lifecycle.

## Completion bar

1. SAIPAL-like synthetic producer enqueues.
2. normal cc consumes it.
3. producer item ID survives closure.
4. maintainer can reject it cleanly.
5. disposition can be queried read-only.
6. no autonomous protocol editing loop exists.

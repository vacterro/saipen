# 11 — WAVE 9: SAIPAL BRIDGE READINESS

## Goal

Prepare SAIPEN to receive SAIPAL findings through the generic producer boundary.

The forensic SAIPAL implementation belongs to its separate founding roadmap.

## Capability

SAIPAL receives:

- constrained audit enqueue;
- optional read-only disposition lookup.

Nothing else.

No Core write.

No BOARD write.

No STATE/LOG write.

## Generic behavior

SAIPEN must not branch semantically on:

`producer == SAIPAL`

SAIPAL output is just a well-formed external audit source.

## Producer item identity

Preserve:

`PAL-xxxx`

or future equivalent through:

- audit envelope;
- Source metadata;
- closure result projection.

## Trust

SAIPAL fields remain claims:

- severity;
- confidence;
- Rule IDs;
- proposed fix surface.

Maintainer verifies them.

## Synthetic dogfood

Before connecting real SAIPAL:

enqueue a synthetic SAIPAL-shaped audit.

Then run:

`cc`

through full lifecycle.

Prove:

- intake;
- Work;
- rejection/confirmation;
- evidence;
- closure;
- deletion;
- feedback.

## Completion bar

1. narrow SAIPAL capability;
2. no special-case lifecycle;
3. producer ID survives;
4. rejection supported;
5. feedback works;
6. no autonomous protocol self-edit loop.

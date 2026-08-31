# 09 — WAVE H: SAIPAL BRIDGE CONTRACT

## Goal

Prepare the exact boundary SAIPAL will use later.

Do NOT implement SAIPAL forensic analysis in this repository wave.

## SAIPAL privileges

SAIPAL receives only the audit enqueue capability.

It does NOT receive write access to:

- CORE;
- COMMANDS;
- REGISTRY;
- BOARD;
- STATE;
- LOG;
- analyzed projects.

## Expected SAIPAL call

Conceptually:

```text
enqueue_audit(
  producer="SAIPAL",
  producer_item_id="PAL-0042",
  content_sha256=...,
  bytes=...
)
```

Returned:

- audit number;
- path;
- hash;
- operation ID.

## Maintainer feedback

Later SAIPAL may read the compact disposition projection from Wave E.

Read-only.

## Audit schema compatibility

The SAIPAL audit template from the founding roadmap must fit the generic audit envelope.

SAIPEN must not need a `if producer == SAIPAL` semantic branch.

Producer-specific content stays source text.

## Dedup responsibility split

SAIPAL owns root-cause dedupe before enqueue.

SAIPEN owns exact enqueue idempotency.

SAIPEN must not try to semantically merge two SAIPAL audits because their prose looks similar.

## Trust boundary

SAIPAL's:

- Rule IDs;
- severity;
- confidence;
- fix recommendation;

are source claims.

The maintainer verifies them.

## Wave H completion bar

1. SAIPAL can enqueue without filesystem-wide write access.
2. SAIPEN consumes SAIPAL audit like any other audit.
3. No SAIPAL-specific Source lifecycle.
4. Producer item ID survives closure.
5. Read-only disposition feedback exists.
6. No automatic protocol edit loop.

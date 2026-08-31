# 08 — WAVE 6: SHARED AUDIT PRODUCER API + ENVELOPE

## Goal

Create one constrained programmatic writer for AUDAPACK, SAIPAL, and future producers.

## Central capability

Implement conceptually:

`saipen audit enqueue`

or equivalent engine API.

Input:

- producer;
- audit bytes/file;
- producer operation ID;
- optional producer item ID;
- optional generic metadata envelope.

Output:

- audit ID;
- `audit/N.md`;
- exact SHA-256;
- durable operation ID.

## Monotonic allocator

Do not use first free gap.

Use durable monotonic allocation.

Deleted IDs are not reused.

Manual high-numbered drops advance allocator safely.

## Atomicity

Under a narrow writer lock:

- allocate;
- write temp;
- flush/verify;
- atomic final placement;
- commit allocation.

Consumer sees either no file or complete final bytes.

## Idempotency

Retry with same producer operation must return the original enqueue result.

Crash after final file creation must not allocate another audit.

## Generic envelope

Optional fields:

- audit_schema;
- producer;
- producer_version;
- producer_item_id;
- created_at;
- severity claim;
- confidence claim;
- observed_project;
- related_audit;
- amends_audit;
- maintainer_verdict=PENDING.

Plain Markdown without envelope remains valid.

## Trust boundary

Producer metadata is Source claim.

SAIPEN does not trust severity/confidence/fix recommendation automatically.

## Security

Producer can create one new canonical audit.

Producer cannot:

- overwrite;
- edit;
- delete;
- choose arbitrary path;
- mutate BOARD/STATE/LOG.

## AUDAPACK

AUDAPACK may later call the shared capability.

SAIPEN must not depend on AUDAPACK.

## Completion bar

1. monotonic IDs;
2. no collision;
3. concurrent writer tests;
4. crash-idempotent retry;
5. no overwrite/path escape;
6. manual drop compatibility;
7. native inbox consumes API-created audit normally.

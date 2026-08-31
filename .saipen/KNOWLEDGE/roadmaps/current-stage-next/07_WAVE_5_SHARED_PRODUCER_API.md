# 07 — WAVE 5: SHARED AUDIT PRODUCER API

## Goal

Create one safe programmatic enqueue boundary for AUDAPACK, SAIPAL, and future producers.

## Capability

Implement one constrained operation such as:

`audit enqueue`

or engine API equivalent.

Inputs:

- producer;
- prepared bytes/file;
- producer operation ID;
- optional producer item ID;
- optional metadata envelope.

Outputs:

- monotonic audit ID;
- canonical `audit/N.md` path;
- exact hash;
- durable operation ID.

## Allocation

Use a narrow central writer lock.

IDs must be monotonic and not reused after deletion.

Manual high-numbered audit drops must safely advance allocator state.

## Atomicity

Write temp → verify → atomic final placement.

Consumer must never observe partial final bytes.

## Idempotency

Retry of same producer operation returns the original allocation.

No duplicate audit after producer crash.

## Security

Producer may create exactly one new canonical audit.

Producer may not:

- choose arbitrary path;
- overwrite existing audit;
- delete audit;
- edit BOARD/STATE/LOG;
- claim maintainer acceptance.

## AUDAPACK migration

AUDAPACK should eventually call this capability rather than independently managing shared numbering.

Do not make SAIPEN runtime depend on AUDAPACK.

## Completion bar

1. monotonic allocation;
2. concurrent producer safety;
3. atomic final file;
4. retry idempotent;
5. no overwrite/path escape;
6. manual drops remain compatible;
7. native consumer processes API-created audit.

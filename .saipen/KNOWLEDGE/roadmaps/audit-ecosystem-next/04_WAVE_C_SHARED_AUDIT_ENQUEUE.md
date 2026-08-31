# 04 — WAVE C: SHARED AUDIT ENQUEUE PRODUCER API

## Goal

Create one safe producer boundary for:

- SAIPAL;
- AUDAPACK;
- human helper tools;
- future audit producers.

Do not let every producer invent its own numbering and write logic.

## Central capability

Provide a constrained operation such as:

`audit_enqueue(...)`

or a CLI equivalent.

It must accept:

- producer identity;
- prepared audit bytes/file;
- optional producer finding ID;
- optional provenance metadata.

It returns:

- allocated audit number;
- canonical relative path;
- exact SHA-256;
- durable operation ID.

## Atomic allocation

Under one audit-inbox writer lock:

1. read durable allocator state;
2. choose monotonic next ID;
3. create temp file;
4. fsync where applicable;
5. atomically place `audit/N.md`;
6. verify bytes;
7. commit allocator state;
8. return receipt.

## Monotonic IDs

Do not reuse deleted gaps.

If durable last allocated ID = 17, the next is 18 even if earlier files were deleted.

This preserves chronology and provenance.

## Collision resistance

Two producers enqueue concurrently:

- both may prepare;
- only one owns allocation at a time;
- results must be N and N+1;
- no overwrite;
- no duplicate filename.

## Idempotency

Producer may supply:

`producer_operation_id`

and/or:

`producer_finding_id + content_sha256`

A retry after crash must return the existing enqueue result, not allocate a second audit.

## External writer rule

Producers do not write arbitrary `audit/N.md` paths directly once this API exists.

Raw/manual file drops remain supported for humans, but programmatic producers should use the constrained capability.

## Security boundary

The enqueue API may:

- create one new canonical audit layer.

It may not:

- edit existing audit;
- delete existing audit;
- write outside `audit/`;
- manipulate BOARD/STATE/LOG;
- mark findings confirmed.

## Wave C completion bar

1. Monotonic IDs.
2. Atomic writes.
3. Concurrent producers cannot collide.
4. Retry is idempotent.
5. Existing audit never overwritten.
6. Producer cannot choose arbitrary path.
7. Human raw-drop compatibility retained.
8. Audit Inbox consumer discovers API-created audits normally.

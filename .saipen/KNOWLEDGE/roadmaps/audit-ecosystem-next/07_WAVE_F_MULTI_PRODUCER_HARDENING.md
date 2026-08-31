# 07 — WAVE F: MULTI-PRODUCER / CONCURRENCY HARDENING

## Goal

Make audit transport reliable when several tools exist.

v1 may remain mostly sequential, but audit allocation must already be concurrency-safe.

## Producer isolation

A bad producer must not corrupt another producer's audit.

Each enqueue is independent.

## Lock scope

Use one narrow writer lock for:

- allocator mutation;
- final file placement.

Do not hold it during:

- LLM analysis;
- audit generation;
- Source processing;
- maintainer Work.

## Reader/writer interaction

Consumer scanning while a producer writes must see either:

- old state;
- complete new file;

never partial final bytes.

Atomic temp→final placement is mandatory.

## Crash matrix

Test:

- producer crashes before lock;
- after allocation reservation;
- after temp write;
- after final rename;
- before allocator commit;
- consumer scans during each boundary.

Recovery must not create duplicate IDs or partial files.

## Manual drops

A human may still place `audit/99.md` manually.

Allocator must reconcile safely.

If manual ID exceeds durable next counter, advance future allocator state.

Never overwrite the manual file.

## Malicious/invalid files

Canonical filename alone does not make content trustworthy.

Invalid UTF-8, symlink/reparse escape, oversized file, unstable read:

- never delete;
- never mark complete;
- report diagnostics;
- allow later workable layers when safe.

## Wave F completion bar

1. Concurrent enqueue proven.
2. Scanner never reads partial final file.
3. Manual high-number drop advances allocator safely.
4. Crash boundaries are idempotent.
5. Invalid producer cannot escape directory.
6. No producer can edit another audit.

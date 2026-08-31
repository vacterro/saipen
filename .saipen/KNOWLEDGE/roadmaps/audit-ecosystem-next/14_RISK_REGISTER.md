# 14 — RISK REGISTER

## R1 — Automatic inbox duplicates the current manual queue

Mitigation:
explicit Wave A migration/reconciliation before enabling scanner.

## R2 — Fresh audit preempts active Work

Mitigation:
routing position after active continuation.

## R3 — Improve runs before audit

Mitigation:
Audit Inbox precedes maintenance/Improve fallback.

## R4 — Old cleanup deletes new same-path bytes

Mitigation:
exact digest recheck immediately before delete.

## R5 — Naked unlink loses recovery truth

Mitigation:
journaled deletion operation.

## R6 — Producer collisions

Mitigation:
single central allocator lock + atomic final placement.

## R7 — Deleted IDs reused

Mitigation:
durable monotonic allocator.

## R8 — AUDAPACK and SAIPAL each invent incompatible formats

Mitigation:
small generic producer envelope and one enqueue capability.

## R9 — Producer metadata treated as canonical truth

Mitigation:
all producer statements remain Source claims pending maintainer evidence.

## R10 — Audit body parsed as commands

Mitigation:
capture as external source bytes; never command-route body.

## R11 — Invalid low-number audit starves all work

Mitigation:
lowest WORKABLE layer rule and explicit diagnostic.

## R12 — Manual file races allocator

Mitigation:
allocator reconciles observed max/manual reservations under lock.

## R13 — Audit deletion erases provenance

Mitigation:
Source tombstone/archive + compact producer/result linkage.

## R14 — SAIPAL gets broad filesystem privileges

Mitigation:
only audit enqueue + read-only disposition capability.

## R15 — Engine grows a SAIPAL special case

Mitigation:
producer-neutral audit envelope and Source lifecycle.

## R16 — Current core-gate debt hidden by feature work

Mitigation:
Wave A fresh-checkout gate before producer work.

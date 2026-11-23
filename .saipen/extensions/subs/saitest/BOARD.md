# Board

<!-- Same checkbox ticket shape as Core (RFC § 1.2), never the OUTBOX.md
     bold-field shape (PROTOCOL.md § 2) -- that shape is for the deliverable
     leaving via OUTBOX, not for this board. Example, shown without its
     leading "- " so nothing parses it as a live ticket (a validator reading
     this file does NOT skip HTML comments):

       [ ] HUNT-001 short description | critical: true

     Real lines start with "- ", and use your own ID prefix (PROTOCOL.md
     § 3), never Core's T-###. -->

<!-- BOUNDARY: this is YOUR board. The main project has its own BOARD.md
     elsewhere -- never touch it directly, never write a ticket there
     yourself. Findings leave through kitchen/OUTBOX.md only; the main
     agent folds them into its own BOARD.md when it runs `saipen sub
     collect`, never the other way around. -->

## DOING

## TODO

## DONE

- [x] TEST-017 Bounded current-source scenarios at dc39709c/1a368781: audit-route dead end no longer reproduces; home split, plan idempotency, stale-package refusal reproduced | verify: kitchen/TEST-17.md; S1 NOT_REPRODUCED; S2 REPRODUCED 3/18 vs 29/38; S3/S4 REPRODUCED; S5 NOT_REPRODUCED as reachable; no project write

- [x] TEST-016 Bounded current-source scenarios: audit route dead end, verifier-home manifest split, crew-plan idempotency, unknown-package refusal | verify: kitchen/TEST-16.md; 4/4 REPRODUCED; installed 3/17 vs repo 27/35 with identical validator bytes; no project write

- [x] TEST-015 Bounded current-source audit, manifest and concurrent-GC scenarios | verify: kitchen/TEST-15.md; 3/3 baseline REPRODUCED; T-2062 pen patch 8/8 reruns pass; no project write

- [x] TEST-011 Bounded continuation and timing-classification scenarios | verify: kitchen/TEST-11.md; three clean scenarios, T-1347 reproduced
- [x] TEST-006 independently reproduce HUNT-13 sole locale failure | verify: validator reports exactly one failing gate and 32 locale files
- [x] TEST-005 independently reproduce HUNT-12 validator failures | verify: 4/4 scenarios REPRODUCED with exact command and output in kitchen/TEST-5.md
- [x] TEST-004 independently reproduce HUNT-11 after T-1115 | verify: both scenarios REPRODUCED with exact commands in kitchen/TEST-4.md
- [x] TEST-003 independently reproduce HUNT-10 Ruff and release-scenario failures | verify: both scenarios carry minimal input, exact command, observed output, and REPRODUCED verdict in kitchen/TEST-3.md

## BLOCKED

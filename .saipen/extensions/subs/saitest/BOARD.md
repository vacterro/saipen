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

- [x] TEST-006 independently reproduce HUNT-13 sole locale failure | verify: validator reports exactly one failing gate and 32 locale files
- [x] TEST-005 independently reproduce HUNT-12 validator failures | verify: 4/4 scenarios REPRODUCED with exact command and output in kitchen/TEST-5.md
- [x] TEST-004 independently reproduce HUNT-11 after T-1115 | verify: both scenarios REPRODUCED with exact commands in kitchen/TEST-4.md
- [x] TEST-003 independently reproduce HUNT-10 Ruff and release-scenario failures | verify: both scenarios carry minimal input, exact command, observed output, and REPRODUCED verdict in kitchen/TEST-3.md

## BLOCKED

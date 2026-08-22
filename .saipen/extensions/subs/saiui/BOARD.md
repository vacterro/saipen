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

- [x] UI-005 final pre-translation interface sweep -- no visual delta or palette drift
- [x] UI-004 post-PY-7 interface sweep -- no visual delta; Golden Default unchanged
- [x] UI-002 current interface contract sweep -- no visual surface or Golden Default drift; CLI shortcut semantics verified
- [x] UI-003 post-T-1115 interface sweep -- no visual surface; Golden Default and write-boundary validators pass

## BLOCKED

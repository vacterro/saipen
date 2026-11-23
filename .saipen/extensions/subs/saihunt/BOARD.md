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

- [x] HUNT-022 Bounded six-signal sweep at dc39709c/1a368781: repo gate 29 problems/38 warnings with both payload repairs measured absent; installed gate 3 problems/18 warnings all payload-or-wall; 101 focused tests OK | verify: kitchen/HUNT-022.md; installed validate CURRENT_FAIL 3 problems; tools/validate.py 29 problems/38 warnings; 6 modules 101 tests PASS

- [x] HUNT-021 Bounded six-signal sweep at dc39709c/c9c3e86c: installed gate 3 problems reproduced, 26 untracked runtime-manifest files measured, focused controls 9/9 PASS | verify: kitchen/HUNT-021.md; saipen validate 3 problems/18 warnings; tools/validate.py 27 problems/36 warnings; refusal 6/6 and crew receipt 3/3 OK

- [x] HUNT-020 Bounded six-signal sweep at dc39709c/6a857897: 29 validator problems reproduced; 9 focused controls and 63 GC tests pass | verify: kitchen/HUNT-020.md; validator 29 problems/36 warnings; refusal+crew controls 9 PASS; GC 63 PASS, 1 skipped

- [x] HUNT-019 Bounded six-signal sweep at 66ef622a/e4fe1f84: 23 conformance failures reproduced; two controls green | verify: kitchen/HUNT-019.md; validate.py 23 problems/33 warnings; refusal registry 6 PASS; crew receipt 3 PASS

- [x] HUNT-014 Bounded current closure/conformance/crew continuation sweep | verify: kitchen/HUNT-014.md; 47 tests, 4 known T-1346 failures, 6 closure tests PASS
- [x] HUNT-016 Bounded six-signal sweep at 66ef622a: 17 conformance problems reproduced; registry and crew-receipt gates green | verify: kitchen/HUNT-016.md; validate.py 17 problems 27 warnings; test_refusal_registry 6 ok; test_t1430 3 ok
- [x] HUNT-015 Bounded six-signal pass at 025bf596: previous reachability claim retired, orphaned operations.py writer pair reproduced | verify: kitchen/HUNT-015.md; caller census with positive control; test_t1430_crew_run_receipt.py 3 passed exit 0

## BLOCKED

# Board
## DOING

## TODO

## DONE
- [x] T-344 [P0] CONFORMANCE rows can no longer claim an enforcement that was deleted. 144 rows, zero retirements, and nothing made a dead rule loud. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-345 [P0] RFC 1.6: a repeated attempt must name what changed; nothing changed means the retry is forbidden. verify.md said this for debugging hypotheses only. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-346 [P1] ship.md's retry-once and verify.md's hypothesis line now inherit the general rule by name instead of restating a fragment of it. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-347 [P1] BUILD gained the reuse ladder: project code, stdlib, an existing dependency, then write it. Adding a dependency is a ticket, not a build step. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-348 [P2] Ship v7.124.0. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-341 [P0] v7.122.0 shipped a gitlink: git add -A swallowed saiwiki's nested wiki clone as a 160000 entry pointing at a commit nobody can fetch. Removed from the index, path ignored. | verify: git ls-files -s .saipen \| grep 160000 -> empty (2026-07-30)
- [x] T-342 [P0] The validator now FAILs any gitlink under .saipen/. Git warns about this, but the hint scrolls past inside 50 lines of CRLF warnings -- noticing is what a check is for. | verify: git ls-files -s .saipen \| grep 160000 -> empty (2026-07-30)
- [x] T-343 [P2] Ship v7.123.0. | verify: git ls-files -s .saipen \| grep 160000 -> empty (2026-07-30)
- [x] T-336 [P0] `verify:` was enforced by the tool, used by 72 live tickets, cited by plan.md and by the validator as an RFC 1.2 rule -- and named nowhere in the RFC. 1.2 now states the closed ticket-field list. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-337 [P1] Sets 7 and 8 drift-checked: 1.10's command surface and 1.2's ticket fields. Both agreed today; a copy with no comparison is a bet nobody edits either side. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-338 [P1] Recorded the citation checker's blind spot: it proves a section exists, never that it says what the citer claims. That is how three citations to a non-existent clause all resolved. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-339 [P0] saiwiki sat at BUILD -> DONE, illegal twice over: not in the transition table, and BUILD is a phase no subSaipen may enter. Claim five hours stale, taken over and logged per 1.4. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-340 [P2] Ship v7.122.0. | verify: tools/validate.py PASS (2026-07-30)
- [x] T-333 [P0] audit_parity picked `sh` as its fallback shell; on Ubuntu that is dash, and tests/validate.sh is #!/bin/bash. Died in CI in 0.4s. Prefers a real bash now, never sh. | verify: dash tests/validate.sh exit 2, reproduced (2026-07-30)
- [x] T-334 [P0] Its control-failure message said 'one of the two tools' without naming which, its exit code, or what it printed -- a whole CI round trip to learn nothing. | verify: dash tests/validate.sh exit 2, reproduced (2026-07-30)
- [x] T-335 [P2] Ship v7.121.0. | verify: dash tests/validate.sh exit 2, reproduced (2026-07-30)
- [x] T-329 [P0] The portable floor said 'Agent is conformant' in the canonical validator's exact words while catching 11 of 41 defects it catches. Both halves now name themselves a subset. | verify: tools/audit_parity.py PASS 11/41 (2026-07-30)


## BLOCKED


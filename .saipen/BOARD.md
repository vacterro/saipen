# Board
## DOING

## TODO
- [ ] T-355 Remove UTF-8 BOM before YAML frontmatter in audit-domains and templates so Codex loads both skills. | verify: both SKILL.md files begin with ASCII --- and parse as YAML frontmatter
- [ ] T-357 [P0] audit_floor launches Git Bash without its usr/bin on PATH, so 18 shell controls fail at missing grep and report the wrong phase defect. | verify: python tools/audit_floor.py PASS 20 checks x 2 halves on Windows
- [ ] T-358 [P0] SHIP requires 100% green but its only exits are DONE/BLOCKED; a fixable pre-publish failure has no legal route back to BUILD, and BLOCKED would falsely end goal mode. | verify: RFC transition table, ship.md, validator transition checks, and scenario fixture agree on SHIP -> BUILD for failed preflight

## DONE
- [x] T-356 [P0] Fixed shell injector delete-after-create order, added PowerShell unsafe-destination parity, and made the validator enforce recreation order. | verify: functional shell install PASS; ordering red-test PASS; audit_checks 42/42
- [x] T-354 Inject updated SAIPEN into the Codex skill copy so Codex boots from the current protocol, including VERSION. | verify: Codex skill copy reports current VERSION and tools/validate.py PASS from the installed copy
- [x] T-353 [P0] Scenario READMEs re-listed the old four-phase Core read-only ban while RFC 1.3 and validators use seven; added a scenario prose drift check and fixed both stale READMEs. | verify: tools/validate.py PASS; tools/audit_checks.py PASS 41/41; tools/audit_order.py PASS; tools/run_scenarios.py PASS; red-test old four-phase text FAILed
- [x] T-349 [P0] 1.4 compares agent: against 'itself' and never said what 'itself' is. Six invented names in this project's own history for two or three actors, plus a LOG line reading [agent: id]. | verify: tools/validate.py PASS (2026-07-31)
- [x] T-350 [P0] agent: now names the seat and is inherited from STATE; a model upgrade is not a different actor. BOOT carries it, since a cold agent writes the field on its first checkpoint. | verify: tools/validate.py PASS (2026-07-31)
- [x] T-351 [P1] Placeholder agent values FAIL. The stability rule itself is behavioral and recorded as such. | verify: tools/validate.py PASS (2026-07-31)
- [x] T-352 [P2] Ship v7.125.0. | verify: tools/validate.py PASS (2026-07-31)
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

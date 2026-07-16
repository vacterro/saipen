# Board
## DOING
- [ ] T-045 UPDATE STYLE.md -- make "дед с района" the default chat style and remove haiku | files: vacskill/STYLE.md | verify: grep haiku clean, chat style updated | needs: 
## TODO
- [ ] T-046 UPDATE README.md + CHANGELOG.md -- document style change | files: README.md, CHANGELOG.md | verify: README reflects new style | needs: T-045
- [ ] T-047 SHIP v5.1.0 | files: VERSION | verify: git push and tag | needs: T-046
## DONE
- [x] T-044 SHIP v5.0.1 (verified: git push main 920ce8c, tag v5.0.1 pushed PASS, conf: high)
- [x] T-043 UPDATE README.md for phases/ dir (verified: verify and review added, BOM=False ctrl=0 PASS, conf: high)
- [x] T-042 IMPLEMENT missing lazy-load phases (verified: verify.md, review.md, done.md, blocked.md extracted from build.md and ship.md, conf: high)
- [x] T-041 SHIP v4.1.0 (verified: git push main 6ad68fe, tag v4.1.0 pushed PASS, conf: high)
- [x] T-040 README v4.1 public-grade -- clean ASCII art, no garbled chars (verified: BOM=False ctrl=0 PASS, conf: high)
- [x] T-039 PROTOCOL.md rebuilt clean -- 240 lines, no control chars (verified: BOM=False ctrl=0 PASS, conf: high)
- [x] T-038 FIX encoding corruption PROTOCOL.md + README.md + CHANGELOG.md (verified: BOM=0 ctrl=0 all files, path scan clean PASS, conf: high)
- [x] T-037 REVIEW + SHIP v4.0.0 (verified: P0 dead-refs clean, BOM fixed, injector idempotent, conf: high)
- [x] T-036 README v4 protocol positioning (verified: renders, version+changelog link present, conf: high)
- [x] T-035 injectors -> PROTOCOL.md scheme + stale-block upgrade (verified: live run, 4x upgraded PASS, conf: high)
- [x] T-034 style/ voices: pointers not copies, opt-in switches (verified: grep switch phrases 4/4 PASS, conf: high)
- [x] T-033 templates/ + KNOWLEDGE seed + schemas frozen README (verified: init dry-run PASS, conf: high)
- [x] T-032 adapters/ 9 files, each -> vacskill/PROTOCOL.md (verified: grep 9/9 + BOM scan clean PASS, conf: high)
- [x] T-031 SKILL.md -> thin skill-reader adapter, 26 lines (verified: frontmatter + PROTOCOL.md pointer PASS, conf: high)
- [x] T-030 vacskill/PROTOCOL.md vendor-neutral canon + capability table (verified: 240 lines, 23-key grep PASS, conf: high)

# Board
## DOING
- [ ] T-042 IMPLEMENT 2-tier protocol (lazy load) | files: vacskill/PROTOCOL.md, vacskill/phases/*.md | verify: PROTOCOL.md < 100 lines | needs: 
## TODO
- [ ] T-043 UPDATE README.md for phases/ dir | files: README.md | verify: no garbled chars, accurate | needs: T-042
- [ ] T-044 SHIP v5.0.0 (Major architectural change) | files: VERSION, CHANGELOG.md | verify: push PASS | needs: T-043
## DONE
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

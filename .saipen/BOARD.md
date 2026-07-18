# Board
## DOING
## TODO
## TODO
## TODO
## TODO
## TODO
## DONE
- [x] T-062 ADD: CLEAN phase and saipen clean trigger | files: saipen/phases/clean.md, saipen/RFC.md, GUIDE*.md | verify: saipen clean commands documented and protocol updated | needs: none
- [x] T-061 ADD: Session State Export tool for backups | files: bootstrap/export.ps1, bootstrap/export.sh | verify: archives .saipen memory into a timestamped zip/tar file | needs: none
- [x] T-060 ADD: Uninstaller scripts for max user control | files: bootstrap/uninstall.ps1, bootstrap/uninstall.sh | verify: cleanly strips SAIPEN from host configs without deleting the repo | needs: none
- [x] T-059 ADD: Backup host config before injection | files: bootstrap/inject.ps1, bootstrap/inject.sh | verify: .bak files created before modification | needs: none
- [x] T-058 DEEP AUDIT FOR RESIDUALS | files: repo-wide | verify: all files point to saipen, commits pushed | needs: T-057
- [x] T-057 CONCURRENCY BOUNDARIES | files: SPEC.md | verify: v7.1.1 pushed | needs: T-056
- [x] T-056 TOTAL BOOTSTRAP DECOUPLING | files: init.md, inject.* | verify: v7.1.0 pushed | needs: T-055
- [x] T-055 SAIPEN v7.0.0 RENAME | files: repo-wide | verify: tests passed, schema versioning enabled, v7.0.0 pushed | needs: T-054
- [x] T-054 CORE STRIP v6.3.0 | files: PROTOCOL.md, GUIDE.md | verify: v6.3.0 pushed | needs: T-053
- [x] T-053 STRICT CONFORMANCE REFACTOR | files: PROTOCOL.md, validate.md | verify: v6.2.0 pushed | needs: T-052
- [x] T-052 REFRAME SAIPEN around Continuation Test | files: README.md, SPEC.md, PROTOCOL.md | verify: v6.1.0 pushed | needs: T-051
- [x] T-051 SAIPEN OVERHAUL | files: PROTOCOL.md, schemas, docs | verify: v6.0.0 pushed | needs: T-050
- [x] T-050 IMPLEMENT conformance layer and test scenarios | files: tests/, vacskill/phases/validate.md | verify: scripts run and pass/fail properly | needs:
- [x] T-049 UPGRADE PROTOCOL.md to strict RFC spec v5.2.0 (verified: 14 sections strictly defined, schemas updated, conf: high)
- [x] T-048 REWRITE README.md to English "РґРµРґ" style (verified: README updated and committed, conf: high)
- [x] T-047 SHIP v5.1.0 (verified: git push main da71032, tag v5.1.0 pushed PASS, conf: high)
- [x] T-046 UPDATE README.md + CHANGELOG.md (verified: README reflects new style, CHANGELOG updated, BOM=False ctrl=0 PASS, conf: high)
- [x] T-045 UPDATE STYLE.md -- make "РґРµРґ СЃ СЂР°Р№РѕРЅР°" default chat style, remove haiku (verified: grep haiku clean, chat style updated, conf: high)
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

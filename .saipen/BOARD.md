# Board
## DOING

## TODO
- [ ] T-219 [P1] Ship v7.92.0 -- VERSION, CHANGELOG, README badge, 32 locale badges, commit, tag, push | needs: T-218 | verify: tools/validate.py PASS + badges match VERSION
## DONE
- [x] T-220 [P0] PLAN was a from-any-phase command in § 1.10 but not in § 1.6's list or the validator's ANY_FROM -- § 2.4's mandatory pivot PLAN produced a state the validator rejected. Both fixed; SHIP added to § 1.6's text too. | verify: tools/validate.py PASS on REVIEW -> PLAN (2026-07-28)
- [x] T-218 [P0] subs/PROTOCOL.md: three Core-shape copies removed (board line, LOG skeleton, STATE field list) -- pointers + sub-specific delta only. | verify: tools/validate.py PASS + grep clean (2026-07-28)
- [x] T-209 [P0] One required-field set -- RFC § 1.2 is now the only place it is written; § 1.5, BOOT, CONFORMANCE 44, state.schema.json all point there. Five copies had drifted into five answers. | verify: tools/validate.py PASS + red test (transition_from removed -> FAIL) (2026-07-28)
- [x] T-210 [P0] § 1.2's own progress-tag example was non-conformant under § 1.19; PHASE/RUN/RESUME had no argument grammar. Example corrected, all five prefixes defined. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-211 [P0] § 1.11 UNBLOCK exception for DONE + empty TODO + non-valve WAIT; both legal WAITs given fixed wording; validator WARN -> FAIL. | verify: 3 fixtures -- drift FAIL, user brake PASS, valve PASS (2026-07-28)
- [x] T-212 [P1] § 1.11 one-DOING stated as total, matching validate.py and CONFORMANCE 50; multi-agent carve-out points at § 1.4. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-213 [P1] § 1.10 `saipen stop` gained the read-only branch -- three lines to chat, digest untouched, stated plainly. | verify: § 1.10 carries the branch; tools/validate.py PASS (2026-07-28)
- [x] T-214 [P1] § 1.2 inline-DONE now requires a verify trace (`| verify:` that ran, or a LOG RUN:/H: line); no trace -> ticket stays TODO and SHIP stays blocked. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-215 [P1] § 2.4 tripped-valve shape pinned across five fields, phase explicitly NOT BLOCKED (would re-create the v7.86.0 deadlock); bare `saipen goal` under goal_mode: false defined. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-216 [P1] validate.py enforces the tripped valve -- missing valve WAIT = FAIL, phase: BLOCKED = FAIL. CONFORMANCE 54/55. | verify: 4 fixtures red/green as designed (2026-07-28)
- [x] T-217 [P2] BOOT.md 84->70 lines, 5609->3760 bytes; defines no rule, so it cannot drift from RFC. Step-number cross-refs replaced with named ones. | verify: 70 lines, no field list, tools/validate.py PASS (2026-07-28)
- [x] T-208 [P0] Core logical-hole repair -- CONFORMANCE IDs, BOARD heading guard, LOG corruption guard, timestamp inversion guard, next_action/task lint, v7.86.0 chain. (2026-07-27)
- [x] T-207 [P3] Clean stale recovery dirs (.saipen/recovery/saitranslate*) from completed translate runs — user confirmed, 414 files cleaned. (2026-07-27)
- [x] T-202 [P3] Wave 4 phase HUNT: BLOCKED — 1 fix: blocked.md LOG mandate. validate.py PASS. (2026-07-27)
- [x] T-201 [P2] Wave 3 phase HUNT: MARKHUNT, ADD, CLEAN, TRANSLATE, PREPARE — clean, 0 defects. validate.py PASS. (2026-07-27)
- [x] T-200 [P2] Wave 2 phase HUNT: REVIEW, SHIP, DONE, VALIDATE, HUNT — 2 fixes: ship.md 14→16, done.md LOG. validate.py PASS. (2026-07-27)
- [x] T-196 [P2] Wave 1 phase HUNT: INIT, PLAN, SCOUT, BUILD, VERIFY — 5 edits: scout.md LOG/checkpoint + KNOWLEDGE/ guard + grep scope, build.md clean-tree cross-ref. validate.py PASS. (2026-07-27)
- [x] T-192 [P2] 29 stale locale batch refresh — all 32 locale badges already at v7.82.0 (done in earlier session work).
- [x] T-195 [P0] Tag all missing releases v7.65.0..v7.82.0 — 21 tags created and pushed.
- [x] T-194 [P0] Self-critique output enforcement — caveman mode, no emoji, no apologies.
- [x] T-191 [P1] close subSaipen mechanism — PASS.
- [x] T-170 [P1] CANCELLED — subsumed by T-191 (2026-07-27, PASS).
- [x] T-193 [P3] board scrub — cleaned (T-170 duplicate removed, tickets rotated).
- [x] T-197 [P3] Clean old recovery backups — pruned.
- [x] T-198 [P2] Stale version refs in shipped docs — bumped.

- [x] T-203 [P0] STATE.md transition_from + validate.py transition validation — schema, RFC doc, CONFORMANCE row 14 automated, init.md first-transition guard. (2026-07-27)
- [x] T-204 [P0] BOOT cold-start chain sync — README.md + extensions/adapters/generic.md + claude.md paste line: BOOT.md first. SKILL.md frontmatter corrected. (2026-07-27)
- [x] T-205 [P0] STATE snapshot WAIT fix — phase HUNT (not DONE+WAIT), RFC § 2.1 empty-board auto-transition. LOG-001.md:660 [T-none] fix. (2026-07-27)
- [x] T-206 [P1] SHIP added to ANY_FROM in validate.py (RFC § 1.10). 32 locale badge bump 7.82.0→7.83.0. (2026-07-27)

## BLOCKED

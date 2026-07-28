# Board
## DOING

## TODO

## DONE
- [x] T-249 [P1] Core guides (EN/RU/EE/DED) now teach `WAIT: <category> -- <question>` with the seven categories named. | verify: four Core locales carry the category form, tools/validate.py PASS (2026-07-28)
- [x] T-250 [P1] Drift detector walks guides/ at WARN severity -- guides mislead a human, they do not break a continuation, and a FAIL would block every release on 29 translations Core may not write. | verify: sees exactly 29 stale, four Core clean (2026-07-28)
- [x] T-240 [P0] `saipen ship` is a command from any phase; `phase: SHIP` is enterable only from REVIEW. SHIP out of the from-any-phase transition set (RFC + validator); § 1.10 now names the exact next_action it writes. | verify: INIT->SHIP FAIL, REVIEW->SHIP PASS, `saipen ship` legal (2026-07-28)
- [x] T-241 [P0] Four shipped docs prescribed category-less `WAIT:` after v7.93.0 made the category mandatory. All fixed; drift detector now walks phases/ and extensions/ and found the fourth itself. | verify: red fixture FAILs, restore green (2026-07-28)
- [x] T-242 [P0] BOOT re-read all three checkpoint files (was STATE only, drift from § 1.5) + § 1.11 priority pointer for a cold agent. | verify: row 58 green, tools/validate.py PASS (2026-07-28)
- [x] T-243 [P0] § 1.11 RECOVER now triggers on a `next_action` failing § 1.2's prefix/category checks; DONE+empty invalid-WAIT still routes to UNBLOCK. | verify: rule stated, tools/validate.py PASS (2026-07-28)
- [x] T-244 [P1] Pick Rule is topmost-workable, not just eligibility -- determinism restored inside Determinism Invariants. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-245 [P1] read-only bans ADD; § 1.3 + validator + CONFORMANCE 15 synced. | verify: read-only+ADD FAIL, read-only+HUNT PASS (2026-07-28)
- [x] T-246 [P1] README zero-prompt claim now carries § 2.1's BLOCKED exception. | verify: README matches § 2.1, tools/validate.py PASS (2026-07-28)
- [x] T-247 [P1] § 1.5 checkpoints after every phase transition, not only after a ticket. | verify: § 1.5 + BOOT agree (2026-07-28)
- [x] T-248 [P2] Ship v7.94.0. | verify: tools/validate.py PASS, 33 badges match VERSION (2026-07-28)
- [x] T-236 [P0] Sealed LOG.md -> logs/LOG-003.md (119 events, E-762..E-880). Cold-start read 66.9 -> 14.5 KB (-78%). § 1.2 gained the outer cap guard the idempotency check cannot substitute for. | verify: sealed copy byte-identical, E-### unique+monotonic across 4 segments (2026-07-28)
- [x] T-237 [P0] RFC compressed 102682 -> 100359 bytes (~4.9 KB total across both waves); MUST/SHOULD/MAY 163/9/28 unchanged. | verify: counts unchanged, tools/validate.py PASS incl. cross-doc anchors (2026-07-28)
- [x] T-238 [P1] CONFORMANCE 20589 -> 19746 bytes, 60 rows and every ID unchanged. | verify: row IDs identical, tools/validate.py PASS (2026-07-28)
- [x] T-239 [P1] Ship v7.93.0 -- VERSION, CHANGELOG, README + 32 locale badges. | verify: tools/validate.py PASS, 33 badges match VERSION (2026-07-28)
- [x] T-232 [P0] `WAIT:` gained a closed seven-word category vocabulary and a mechanical membership check; five live call sites updated. | verify: 2 vague fixtures FAIL, 7 categories PASS (2026-07-28)
- [x] T-233 [P0] Cross-document drift detector -- six sets parsed out of RFC and compared to schema/validator; BOOT/CONFORMANCE FAIL if they re-enumerate the field set; a moved anchor is itself a FAIL. | verify: 7 desync fixtures red, restore green (2026-07-28)
- [x] T-235 [P0] § 1.5 now requires reading back all three checkpoint writes, not just STATE -- from this run's own silent BOARD no-op. | verify: rule + CONFORMANCE 60 + scenario README (2026-07-28)
- [x] T-234 [P2] RFC diet -- 4 incident narratives moved to tests/scenarios/, 11 archaeology passages compressed: 104706 -> 102064 bytes, MUST 162 -> 162. Cold-start cost measured: 66.9 KB, of which LOG is 55. | verify: MUST count unchanged, tools/validate.py PASS (2026-07-28)
- [x] T-221 [P0] Self-inflicted in v7.92.0: § 1.2 whitelisted two WAITs at DONE+empty TODO, § 1.11 allowed one; § 1.2's "Anything else" also read as banning the very PHASE HUNT § 2.1 requires. Both aligned. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-222 [P0] CONFORMANCE resync -- 43 retired into 54 (two rows, one state, WARN vs FAIL), 47 "per agent" -> "in total", 38 unhardcoded, 44 step-number ref named, new row 56 for duplicate headings. | verify: 56 rows unique+monotonic, tools/validate.py PASS (2026-07-28)
- [x] T-223 [P0] LOG timestamp: found the third check dead since feae149 -- its regex anchored `^(\d{2})\.` against lines starting `- `, so it never once fired, and its abs() would have WARNed every idle repo. Removed; signed >3h future FAIL and >5min inversion WARN remain. | verify: +5h future FAILs, idle-30h PASSes (2026-07-28)
- [x] T-224 [P0] § 1.10 "Overrides goal_mode" -> "Overrides autonomous continuation"; stop MUST NOT mask a tripped valve as a user brake. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-225 [P0] § 1.11 FINISH now covers an unclaimed ## DOING (crash orphan) instead of skipping it into a second claim. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-226 [P0] Ticket-less phases derived as the complement of § 1.2's five ticket-bearing phases instead of a second hand-kept list. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-227 [P0] read-only bans INIT and PLAN too (both write); § 1.3 leads with the principle, validator + CONFORMANCE 15 synced. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-228 [P1] § 2.1 halt has one definition -- no workable ## TODO AND no ## DOING; "workable" defined once. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-229 [P1] § 1.5 Recovery: live ## DOING outranks a T-none LOG tail; Recovery and § 1.11's trace rule both gained read-only branches. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-230 [P1] § 2.4 Entry PLAN is wave 1; bare-goal resume onto an empty board falls through to § 2.1. | verify: tools/validate.py PASS (2026-07-28)
- [x] T-231 [P1] § 1.2 states checkbox<->section; validator FAILs all three mismatches; § 2.2 RETURN guard; BOOT fresh-INIT note. | verify: 3 red fixtures, [ ] under DONE FAILs (2026-07-28)
- [x] T-219 [P1] Ship v7.92.0 -- commit 8fd7d1a, tag v7.92.0, pushed to main. | verify: tools/validate.py PASS + all 33 badges match VERSION (2026-07-28)
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
- [ ] T-251 [P2] 29 non-Core locale guides still teach the pre-v7.93.0 `WAIT: <question>` shape | blocker: subSaipen translation work by standing rule -- Core owns en/ru/et/ded only; live list is validate.py's `guide-wait-shape` WARN

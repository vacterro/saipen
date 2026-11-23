# Use-Cases

## 1. Cold agent resumes project

**Scenario:** Return to project after 2 weeks. Agent has no chat history.

> saipen continue

Agent reads STATE.md (phase: BUILD, task: T-7), BOARD.md (T-7 in DOING), LOG tail. Executes next_action: `PHASE BUILD T-7`. Resumes coding without asking "what was I doing?"

## 2. Overnight autonomous evolution

**Scenario:** Leave agent running with goal mode.

> saipen goal 'make the UI responsive'

Agent: PLAN -> 5 tickets. Builds, verifies, reviews, ships. Then HUNT -> clean -> ADD -> finds symmetry gaps -> tickets -> builds -> ships. Hits wave 3 cap. Writes `WAIT: safety valve`. Stops. Morning: 3 releases, 15 tickets, zero questions asked.

## 3. Parallel subSaipen research

**Scenario:** Need to audit codebase while building a feature.

> saipen sub spawn saihunt
> saipen sub spawn saipython

saihunt scans 6 HUNT categories. saipython finds Python issues (untyped defs, bare excepts), patches them in its own kitchen/pen/ sandbox. Both write OUTBOXes. Main agent collects after current BUILD.

**Collect discipline:** main agent runs `git status` against whole tree before folding. A confused sub that wrote outside its folder gets caught by boundary check (v7.98.0+).

## 4. Safety valve prevents runaway

**Scenario:** Agent running autonomously for hours. Goal caps prevent infinite loops.

After 3 waves or 20 tickets: agent stops, writes `WAIT: safety valve -- X waves completed, re-invoke saipen goal to authorize more`. User reviews, re-authorizes or stops. Never burns unlimited compute.

## 5. Multi-vendor handoff

**Scenario:** Start with Claude, continue with Gemini, ship with Codex.

Claude: `saipen goal 'build auth'` -> builds, ships v0.5.0.
Gemini: `saipen continue` -> reads STATE, HUNTs, ADDs next feature.
Codex: `saipen ship` -> bumps to v0.6.0, tags, pushes.

All three agents from the same STATE.md. No context loss between vendors.

## 6. Blocked project recovery

**Scenario:** T-14 depends on T-12 which is stuck.

```
Agent at DONE: empty board? No, T-14 blocked.
BLOCKED: T-14 needs T-12, T-12 needs human decision.
WAIT: blocked -- T-12 needs UX mockup approval before build can start
```

Human sees WAIT, provides mockup. Next continue: T-12 unblocked, builds, ships, T-14 builds on top.

## 7. First-publish gate

**Scenario:** First release of a new project.

SHIP detects no origin, writes:
`WAIT: first-publish -- confirm repo name 'my-project' and public/private before I push`

Human confirms. Agent pushes, tags, creates first release. One-way door protected.

## 8. Portable floor validation

**Scenario:** CI server without Python.

GitHub Actions (has Python) -> runs `tools/validate.py`.
Minimal Docker container (no Python) -> runs `tests/validate.sh` or `tests/validate.ps1`.

Both probe all 9 STATE fields, catch read-only bans, check WAIT categories.
**Proved red:** `tools/audit_floor.py` breaks a scratch project 20 ways, asserts both halves report each failure (v7.100.0+).

## 9. Translation pipeline

**Scenario:** Locale packs for 32 languages.

> ee

Agent quarantines in `.saipen/saitranslate/`, scans both real docs and real in-app UI strings, builds all 32 locales plus дед voice, verifies coverage, and writes a complete `status: ready` OUTBOX. It never touches the main tree or pushes. Later `eee` accepts only that fresh ready package, integrates its declared payload through VERIFY→REVIEW→SHIP, and pushes; anything incomplete replies `Not ready: run ee first.` with zero main write.

## 10. Crash recovery

**Scenario:** Agent crashes mid-BUILD. STATE says phase: BUILD but work incomplete.

Next agent: RECOVER. STATE stale? BOARD shows T-17 in DOING with old claim_time. LOG says `RUN: BUILD T-17` with no VERIFY. Adopts T-17 (new claim_time). Continues BUILD. No data loss, no duplicate work.

## 11. Citation resolution (v7.101.0+)

**Scenario:** A shipped doc references SS N.N that was renumbered. Nothing signals the break.

SAIPEN's validator now resolves every SS N.N and phases/<name>.md reference across 103 shipped documents. Dead citation = FAIL. Caught: 7 orphaned citations when SS 1.11 was renumbered, phases/add.md teaching a RETURN SCOUT rule phases/hunt.md had already replaced, KNOWLEDGE/traps.md describing LOG drift check as WARN when it is FAIL.

## 12. Push-claim honesty (v7.99.0+)

**Scenario:** Agent claims "shipped, committed, pushed" in next_action. Three CI commits never left the machine. Nothing contradicts because nothing looks.

Now FAILs: STATE.next_action mentioning push while commits sit local-only. Degrades to WARN only when no git or no upstream. The repository itself adjudicates the claim.

## 13. Continue from a subfolder (v7.132.0+)

**Scenario:** You `cd` into `src/auth/`, type `saipen continue`. Where does memory land?

Before v7.132.0: checkpoints were relative to ambient cwd — a `cd` could make STATE.md name a different project without any error. Now BOOT binds one project root for the session: Git worktree/common-dir identity, linked worktrees use the main worktree's memory, non-Git projects use the nearest ancestor with `.saipen/`. An unowned cwd fails instead of creating a second memory tree. From another machine: `saipen continue --project-root <path>` overrides deliberately.

## 14. Release guard vs stray tags (v7.130.0+)

**Scenario:** A leftover annotated tag sits in local state with the same name as a release. `git push --follow-tags` publishes it beside the intended tag.

SHIP now pushes the branch and one exact `refs/tags/vVERSION` in separate commands. `--tags`/`--follow-tags` are forbidden for releases; the temporary bare-origin probe proved the prescribed refspec publishes only the intended tag. Same intent, one more line: "publish the release you named."

## 15. Shortcuts on a Russian layout (v7.152.0+)

**Scenario:** You type on a Russian keyboard layout. `сс` (two Cyrillic 'с') looks like `cc` but is not the same codepoint.

The recognizer normalizes through the lowercase confusable set (аеорсух) before matching — six shortcuts have homoglyph twins (`сс`, `ссс`, `аа`, `ее`, `еее`, `рр`), seven have none. Replying "unrecognized command" to a key the user pressed correctly was the worst available response, and it landed on the most-used shortcut. The table stays Latin: canonical spelling, not the only accepted form.

## 16. The brake vs the status report (v7.149.0+)

**Scenario:** You want to stop a run, but `ss` used to mean status. `s` alone collides across stop/set/ship/status/scout.

`ss` = `saipen stop`, `sss` = `saipen status`; `gg` starts a new goal, `cc` continues or resumes the active convergence target, and `ccc` continues plus the shipping chain. Length has no global meaning: `sss` is read-only while `eee`/`qqq` are ready-only integration chains. Read the exact row; never invent an undeclared repeated form.

## 17. Translation and wiki prepare at the same time (v7.226.0+)

**Scenario:** Both locale docs and the wiki are stale, but Core must remain a single writer.

Run `ee` and `qq` as isolated producer prepares. Each claims its own lock and monotonic epoch, writes a non-READY staging generation, verifies payload/dependency hashes, then atomically publishes READY. Cross-producer work may overlap; a second job for the same producer serializes or refuses as busy. Neither producer can mutate Core STATE/BOARD/LOG or ship. Core later integrates named packages in deterministic order and rejects only real read/write dependency drift, not unrelated whole-tree movement.

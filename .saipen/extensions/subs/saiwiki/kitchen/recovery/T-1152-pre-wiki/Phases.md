# Phases

16 phases total. Core (9) + Maintenance (5) + Infrastructure (2).

## Core phases

| Phase | Entry | What it does |
|---|---|---|
| INIT | `saipen set` | Bootstrap .saipen/. Confirm no existing .saipen first. Create STATE/BOARD/LOG/templates. |
| PLAN | `saipen plan` or `saipen goal` | Amplify user intent into tickets. <=8 lines analysis. Safe defaults over interrogation. |
| SCOUT | After PLAN | Claim top TODO ticket. Read KNOWLEDGE/. Understand code before BUILD. |
| BUILD | After SCOUT | Smallest safe change. Full code: no stubs, null/empty/error paths. Match repo style. **Reuse ladder** (v7.124.0): own code → stdlib → an existing dependency → then write it. Adding a dependency is a ticket, not a build step. |
| VERIFY | After BUILD | Does it work? Write+run test. If broken: fix, don't REVERT. If unreachable: manual-verify WAIT. **Gate-stuck-red guard** (v7.101.0): before reporting that *everything* failed, run a control with known result. A real defect is almost never total; a misconfigured harness almost always is. **Retry owes an answer** (v7.124.0): a repeated attempt MUST name what changed since the last one; "nothing" means the retry is forbidden. |
| REVIEW | After VERIFY | Is it well made? `mode: manual-verify` -> human. Otherwise: self-review against quality gates. Max 2 passes — after that, ticket to BLOCKED. |
| SHIP | `saipen ship` or after REVIEW | Version bump, README/CHANGELOG update, tag, push. `no-publish`: skip git steps. **Release guard** (v7.99.0): `release.yml` refuses to publish when VERSION or CHANGELOG disagrees with the tag name. **Preflight repair loop** (v7.128.0): a fixable pre-commit failure returns `SHIP -> BUILD` (narrow edge, current ticket only) then repeats VERIFY/REVIEW/SHIP; publish failures and already-pushed work stay under recovery. Release order explicit: prepare VERSION/README/CHANGELOG → rerun validators → commit → push. **Exact-ref publish** (v7.130.0): pushes branch + one exact `refs/tags/vVERSION`; `--tags`/`--follow-tags` forbidden for releases. |
| DONE | After SHIP | Move ticket to DONE [x]. If TODO remains: SCOUT. If empty: HUNT (auto). |
| BLOCKED | Unworkable board | All tickets stuck. Write WAIT: blocked with category + exact question. |

## Maintenance phases

| Phase | Entry | What it does |
|---|---|---|
| HUNT | Auto on empty DONE | 6 signal categories, cap 5 tickets. Skip only if exact hash match in LOG. Subagents: parallel dispatch. |
| MARKHUNT | `saipen markhunt` | Dry exhaustive audit. Record only, never fix. Findings carry evidence (file:line or command output). |
| ADD | After clean HUNT | Evolutionary completion. Priority: bugfix > complementary > workflow > UX > convention. 2 paths: direct minimal, or planned. |
| CLEAN | `saipen clean` | Deep scrub: board prune, orphan hunt, link audit, trash removal. Seal oversized LOG. |
| TRANSLATE | `saipen translate` / `ee` preparation path | Isolated full real-surface locale build in .saipen/saitranslate/. A collectable run writes the seven-field ready handoff; never touches main tree. |

## Infrastructure phases

| Phase | Entry | What it does |
|---|---|---|
| PREPARE | `saipen prepare [producer]` | FORCE-FRESH execute the named role, verify complete coverage, bind source head/tree + role revision + exact read/write sets, then atomically publish payload bytes from staging to READY under a producer-local lock and epoch. `ee` and `qq` stop here: no Core write, integration, commit, or push. Missing canonical role execution returns `ROLE_NOT_RUN`; an old OUTBOX is not evidence. |
| VALIDATE | `saipen validate` | Run conformance script. Fix structural corruption (shape only, never content rewrite). |

## Phase transitions

```
All phases have -> BLOCKED available (universal).

Core flow: INIT -> PLAN -> SCOUT -> BUILD -> VERIFY -> REVIEW -> SHIP -> DONE
                         |                    v
                         +---> BLOCKED <------+

Maintenance flow:
  DONE (empty board) -> HUNT -> ADD -> SCOUT -> BUILD -> ...
                     |        |
                     |        +-> (mature) -> DONE
                     v
                   (hash match) -> skip, go to ADD

Explicit commands jump to target phase from anywhere:
  saipen clean   -> CLEAN
  saipen ship    -> REVIEW gates first, then SHIP
  saipen validate-> VALIDATE
  saipen markhunt-> MARKHUNT
  saipen translate-> TRANSLATE
  saipen prepare -> PREPARE
  saipen stop    -> checkpoint, halt
```

## WAIT categories in phases

Every phase doc that prescribes a WAIT uses the closed 7-word vocabulary:
- `manual-verify`, `destructive-op`, `first-publish`, `user brake`, `blocked`, `safety valve`, `init`

**Enforced** (v7.101.0+): `phases/done.md` previously endorsed `next_action: wait for user command` — no legal prefix, TEST-001 couldn't execute it. Replaced with `WAIT: user brake -- <reason>`. Every phase doc's prescribed next_action is now checked against CORE § 1.2's prefix rules, not just WAITs (v7.103.0).

## Phase-level checks added (v7.104.0–v7.226.0)

- **last_event enforced** (v7.115.0): STATE.md `last_event` field catches state that drifted from its own LOG. RECOMMENDED field, validated against LOG tail.
- **review_passes enforced** (v7.117.0): the field exists so `phases/review.md` can enforce its 2-pass cap mechanically. Number now read.
- **digest.md freshness** (v7.117.0): `kitchen/digest.md` shape + version checked against VERSION. Live digest was 33 releases stale.
- **claim_time validated** (v7.116.0): `claim_time` checked as ISO-8601 UTC. Liveness judged from it against 15-minute window.
- **MARKHUNT manifest validated** (v7.118.0): `.saipen/kitchen/markhunt_progress.md` checked for shape, cursor vocabulary, vector completeness.
- **no-git head pair guarded** (v7.118.0): one real hash + one `no-git` = FAIL (was silently skipped).
- **Ticket-field list closed** (v7.122.0): CORE § 1.2 states the field list — `needs/owner/claim_time/blocker/verify/review_passes` — each field's job, the `\|` escape. `verify:` was enforced with no document naming it.
- **agent: seat defined** (v7.125.0): `agent:` names the seat and is inherited from STATE. Placeholders FAIL; changing it logs a `DEC` naming both values.
- **SHIP→BUILD edge** (v7.128.0): DFA row added — pre-commit fixable failure returns to BUILD (current ticket only, must repeat VERIFY/REVIEW/SHIP).
- **Project-root binding** (v7.132.0): BOOT binds one root per session — Git worktree/common-dir, linked worktrees use main worktree's memory, non-Git nearest ancestor with `.saipen/`, `--project-root` overrides. Checkpoint paths never leave the bound root.
- **Sealed LOG mutations** (v7.133.0): mutation targets resolve to active or newest sealed segment with a skipped mutation fatal, not a shrunken denominator.
- **last_event migration boundary** (v7.135.0): schema v1 missing it WARNs and stays readable; v2 with an event-bearing LOG and no marker FAILs; Recovery derives the same value idempotently.
- **Tag audit fails closed** (v7.136.0): `git cat-file --batch` process failures exit nonzero with focused FAIL; legal `<spec> missing` stays a warning.
- **Bootstrap reports process truth** (v7.137.0): failed writes exit nonzero without `Done.`; PowerShell block regex preserves user-owned whitespace bytes.
- **Exports bind to project owner** (v7.138.0): archive beside the `.saipen/` owner; foreign Git repos rejected unless explicit root supplied.
- **Crew launch truth** (v7.139.0/v7.145.0): Unix + Windows launchers observe every seat; refusal stops the run and names the window.
- **Bytecode not a release artifact** (v7.140.0): injectors clean installed trees; repository ignore rules cover cache dirs.
- **Shell predicates fail closed** (v7.141.0): grep status >1 fails the operation; uninstall handles file/symlink/directory skill paths.
- **Lost enumeration is not a skip** (v7.142.0): nonzero `git tag -l v*` exits nonzero; missing Git may SKIP loudly.
- **LOG filter propagates failure** (v7.143.0): sed shim returning 7 → `FAIL: LOG.md read/filter failed`, no LOG PASS.
- **Hook resolves Bash** (v7.144.0): no-Python floor invoked through resolved `bash`; floor-without-Bash fails focused.
- **Re-authorization survives crash** (v7.146.0): validator replays the counter rebuild and compares against STATE.md; `DEC: goal reauthorized` must explain the counters.
- **Append targets end on a line boundary** (v7.147.0): all 21 append targets' last byte read; red control strips a fixture's final newline.
- **Shortcut resolves to a defined command** (v7.148.0): table's right-hand column parsed; `hh` at a phase name = FAIL. Exact current assignments are additionally pinned by scenario 183.
- **Empty DONE board goes to HUNT** (v7.148.0): one document decides; `phases/done.md` defers to § 1.11 by name.
- **Phase-named commands checkpoint** (v7.151.0): phase-switching list derived from phase docs, not hand-kept; `init` excluded structurally.
- **Skill triggers match the CORE table** (v7.153.0): SKILL.md frontmatter must exactly equal § 1.10's shortcuts plus confusable mapping; both drift halves red-tested.
- **No-op mutations are rejected** (v7.155.0): harness refuses every unchanged callable result before running the validator; identity-mutation self-control stays red-capable.
- **Root device-name snapshots** (v7.156.0): a real Windows `nul` entry is ignored at repository root and excluded from canonical audit copies without deleting the original artifact.
- **Translated shortcut parity** (v7.156.0): locale README is the source; mirrors and non-Core guides consume the same callout with exact keys, Cyrillic twins, order, and CORE target.
- **Chat language + voice contract** (v7.157.0): CORE, BOOT, STYLE, and SKILL metadata carry one exact EE/EN/RU precedence and persistent caveman-дед duty; separate mutations prove both can fail.

- **A typed command outranks `next_action`** (v7.177.0): § 1.11 OBEY — the user's message names a command, it supersedes the previous session's pre-computed pick and clears a live `WAIT:`; two live MUSTs with no precedence cost a bare `qq` twice (E-1913).
- **A `WAIT:` body is one sentence** (v7.185.0): the category token bounds what KIND of stop; a period+capital ends the body — session notes belong in `kitchen/digest.md`, never the field.
- **`PHASE <enum> [T-###]` is paired** (v7.174.0): the ticket ref is required for exactly SCOUT/BUILD/VERIFY/REVIEW/SHIP, checked in both directions on Core and sub states.
- **The ticket stays in `## DOING` through SHIP** (v7.213.0): `PHASE SHIP T-###` names a DOING ticket; it reaches `## DONE` only after the push lands.
- **VERIFY's retry cap lives on the ticket** (v7.214.0): `verify_attempts:` counts 3 dead hypotheses / 2 failed cycles on the line, never in the agent's head.
- **REVIEW re-runs the ticket's own `verify:`** (v7.215.0): same check, run twice — REVIEW never takes VERIFY's claim as given.
- **The first-publish gate runs before the act** (v7.211.0): remote classification is step 5, decided while everything is still local, re-read before each external write.
- **The release tag is pushed after the branch** (v7.212.0): a published tag whose commit is on no remote branch is a defect the validator names.
- **`saipen hunt` can actually enter HUNT** (v7.210.0): `ANY_FROM` includes HUNT; forcing a sweep forces one; the hash-skip has no carve-out.
- **The MARKHUNT brake has a legal wording** (v7.209.0): untriaged findings stop the auto-proceed with the fixed WAIT wording; the deadlock check stops exempting whole situations.
- **execution_intent replaces goal_mode** (v7.207.0): the clean-HUNT destination and the valve resume key follow the intent — converge pauses say `-- run 'cc' to continue`, never `saipen goal`.
- **HUNT detects, CLEAN mutates** (v7.212.0): the ownership split — HUNT finds and tickets, CLEAN deletes under proof-of-recovery gates; no phase does both.
- **Session BLOCKED means nothing is workable** (v7.226.0): `phase: BLOCKED` with any workable `## TODO` FAILs; BLOCKED with goal intent FAILs on § 2.4's own Exit list.
- **Producer READY is atomic and dependency-aware** (v7.226.0): prepare publishes only after every payload and dependency verifies; epochs reject stale workers, same-role locks serialize writers, terminal packages leave the active READY hot set only after journaled Core integration becomes recoverable.
- **Attempt lifecycle events** (T-1148): STATE.md carries an optional `attempt: A-###` pointer naming the open episode; LOG.md gets machine-owned DEC lines for `attempt A-### open` and `attempt A-### close result <R> stop <S>` with bounded vocabularies (result: candidate/failed/interrupted/yielded/superseded; stop: completed_execution/context_limit/provider_limit/provider_failure/process_crash/user_stop/capability_missing/validation_failure/deliberate_handoff/unknown). One episode open project-wide at a time; a successor closes a crashed predecessor before claiming the Work. A ticket MUST NOT finish while its producing episode is open.

## ДED Voice: phases rant

> "INIT? Создал папку — и работай. PLAN? Расписал задачу — и вперёд. BUILD? Чини, не ломай. VERIFY? Тест написал — работает? Отлично. SHIP? Залил — и забыл. BLOCKED? Сиди и жди, пока человек решит. Всё. Не надо выдумывать. Шестнадцать фаз — и каждая делает своё дело. Агент не думает — агент делает."

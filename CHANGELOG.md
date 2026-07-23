# Changelog

> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

## 7.54.0 -- 2026-07-23 -- phase-collapse audits reviewed and rejected (recorded, made findable)

Three phase-audits (`tofix/saipen_phaseAudit1/2/3`) all argued the same thing -- 16 phases is too many, collapse them (to 5, 8, and 4 respectively; they didn't even agree with each other). Reviewed and rejected, and the rejection is now recorded where it will actually stop the next identical audit instead of costing a fresh analysis each time.

- The token premise is already solved by the 2-tier lazy-load (v5.0.0): a phase doc costs nothing until its phase is active, so 16 small focused docs beat 8 fat merged ones -- phaseAudit2 admits merging makes every `hunt` call also load `add`+`markhunt`. Collapsing *raises* per-call tokens.
- The specific merges (scout+build, verify+review) undo deliberate v2.0.0 splits already recorded in `KNOWLEDGE/decisions.md` with reasons (scout separate so agents read before coding; VERIFY "works?" separate from REVIEW "well made?").
- The rewrite surface (RFC §1.6, CONFORMANCE enum + 33 scenarios, `validate.py`, `state.schema.json`, the subs PROTOCOL's enum reuse, 33 guides) re-opens 100+ versions of phase-specific hardening (VERIFY hysteresis, the ADD->HUNT / DONE->ADD phantom removals) for an illusory-to-negative gain.

Recorded the full rejection in `KNOWLEDGE/decisions.md` (same treatment `goal_exit` got), added a findable pointer at RFC §1.6's phase enum, and deleted the three consumed audits. Do not re-propose without a real trace showing the phase count actually costs tokens or causes a stall.

## 7.53.0 -- 2026-07-23 -- anti-bloat + cold-start: log segmentation, changelog archival, MARKHUNT triage, audit7 polish

Consolidation pass aimed at one thing: keep the files a cold agent actually reads small, so continuation stays cheap on weak hardware and never overflows a context window.

**LOG segmentation (RFC § 1.2).** `LOG.md` was append-only *and* unbounded -- 695 lines here, big enough to get truncated when loaded into context (which is how an earlier reviewer "lost" 75% of the history). Now segmented: sealed older entries live in `.saipen/logs/LOG-<NNN>.md`, the active tail in `.saipen/LOG.md`. Sealing moves whole lines verbatim (append-only holds across the boundary); `E-###` stays globally monotonic and `[parent: E-###]` resolves across segments. Only the small active tail is read for normal operation (§ 1.1 tail read, § 1.5 Recovery); `tools/validate.py` reads sealed + active as one sequence. This repo's own LOG was rotated: 679 entries sealed to `LOG-001.md`, active `LOG.md` down to 15. Sealing is a natural `CLEAN` step.

**CHANGELOG archival.** Same disease, same cure: the newest ~10 entries stay here, the rest move to `CHANGELOG_ARCHIVE.md`. The head is what anyone reads; the tail is cold history.

**MARKHUNT triage (T-149..T-152) cleared from `## BLOCKED`.** The four unvetted audit findings recorded earlier were triaged and resolved: goal_tickets counting semantics documented (RFC § 2.4 -- it counts VERIFY-passes, deliberate and fails safe); parallel TRANSLATE now deletes its own transient `saitranslate/STATE.md` (translate.md); kitchen crash-integrity spelled out (a file truncated mid-write is debris, restart clean, RFC § 1.2); a doc-explicitness cluster where the no-git HUNT-skip and the ticket `verify:` field got explicit wording, the rest marked WONTFIX-by-design.

**audit7 polish.** `add.md` pseudocode gained the missing `CLAIM(ticket)` (was out of sync with RFC § 2.2); the phantom `ADD -> HUNT` transition was removed from the § 1.6 table (add.md calls it illegal -- same phantom class as the already-removed `DONE -> ADD`); the ADD Act-section now points at the two implementation paths instead of reading as "everything goes to PLAN/SCOUT".

**saipython.** The fixer charter gained a hard CPU/RAM/disk-friendly rule -- every patch must be at least as light as what it replaces (stream don't slurp, no accidental O(n^2), nothing grows unbounded), assume the code runs on a potato.

**Smaller:** `next_action` MAY now carry a compact progress tag (`[3/7 done, 1 blocked]`) so the human reads progress without `saipen status` (RFC § 1.2); `T-136` reclassified from a mislabeled P0 to P3 design-debt (a missing self-test, not a bleeding bug); the last consumed `tofix/` audit deleted (the repo carries exactly one canonical copy of every file -- verified, no duplicates). A batch of ergonomics ideas (BOOT.md fast-loader, auto human-digest, BLOCKED-triage nudge, human_note feedback field, command-surface review) is ticketed T-158..T-162 for a focused later pass, deliberately NOT crammed in here.

`tools/validate.py` green (2 log segments, 3 subSaipens).

## 7.52.0 -- 2026-07-23 -- saipython: the first fixer-type subSaipen (reverse-end Python fixer)

Added a new class of subSaipen and the first instance of it. saiwiki and saihunt *report* -- a finding, a draft, a proposal. A **fixer** goes one step further: its OUTBOX deliverable is a ready, already-tested patch. saipython is that fixer, Python-specialized, aimed at the *tail* of a project -- the low-severity bugs (lint/type nits, small correctness fixes, missing error paths, dead code) the main agent keeps deprioritizing. Main works the trunk; saipython clears the tail; the whole thing ships faster.

The reconciliation with the subSaipen prime rule (never write the main project) is the same one parallel TRANSLATE already uses: write freely, but only inside your own sandbox. saipython clones target files into its own `kitchen/pen/`, fixes and tests the *copy* there, and hands back a unified diff via OUTBOX. It never writes the main tree, and its `STATE.phase` never becomes `BUILD`/`SHIP` (unreachable under `mode: read-only`, enforced by `tools/validate.py`) -- it drafts in the pen (a `SCOUT` kitchen activity, exactly like saiwiki drafting a page) and proves the fix in phase `VERIFY`, which IS reachable for a sub. The main agent applies the patch through Core `VERIFY -> REVIEW -> SHIP`; the sub's green run is evidence that saves time, never a substitute for Core's gates.

- **`extensions/subs/PROTOCOL.md` § 9** -- new "Fixer-type subSaipen" section: the pen sandbox, verify-in-sandbox, capability gate (missing toolchain -> degrade to an `unverified` finding, never fake green), patch-shaped OUTBOX (`base_head` + quoted test result + unified diff), freshness on the way out and in, and the reverse-end scope discipline (one minimal fix per patch, tail only, never a refactor epic). `PY-` added to the ticket namespace (§ 3).
- **`extensions/subs/saipython/`** -- STATE (`mode: read-only`), BOARD (PY-001..005 fix categories), LOG, `kitchen/OUTBOX.md`, `kitchen/pen/`, and a full mentor charter `README.md`: real Python-pro craft (correctness before cleverness, minimal surgical diffs, root cause not symptom, stdlib before deps, honest error handling, security even on small fixes) plus the teacher's charge -- do the ticket exactly and verified, then exceed with discipline (prove the sibling bug others walked past as a *separate* finding, polish only inside the diff you already need), and grow (log durable lessons for the next run). Hard walls: never touch the main tree, never a feature/refactor epic, never fake green, one fix per patch.
- **MANIFEST.md / subs README** -- saipython registered as the third bundled example (the fixer).
- **CONFORMANCE row 33** + `tests/scenarios/fixer-subsaipen-patch-outbox/` -- the fixer stays read-only toward the project and reaches it only as a main-applied, gate-checked patch.

`tools/validate.py` green (3 active subSaipens). No change to `validate.py` was needed -- the fixer fits the existing read-only policy by construction.

## 7.51.0 -- 2026-07-23 -- audit5: four real RFC/phase-doc fixes, eight ghost findings verified already-closed

Processed a fresh external audit (`tofix/saipen_audit5.md`, 13 findings). Most were written against an older snapshot -- eight were verified already-closed against the live files (grep, not memory): MARKHUNT's `## BLOCKED` (not TODO) recording, done.md's TODO-before-goal-HUNT ordering, the `saipen SYMPTOM` phantom command, VERIFY hysteresis, HUNT's `## BLOCKED` dedupe, translate.md's 32-language count, plan.md's size-gate "no correctness gate skipped" wording, and blocked.md's `-> DONE` path. Five were real; four fixed here, one ticketed.

- **#6 stop vs bare `saipen goal` counter contradiction (RFC §1.10)** -- the real bug. §1.10 said any resume after `stop` continues "precisely as if the stop had never happened," lumping all three resume commands together, but §2.4 Entry has bare `saipen goal` reset `goal_waves`/`goal_tickets` to 0. Split explicitly: `saipen continue`/bare `saipen` preserve the counters; bare `saipen goal` deliberately resets them for a fresh safety-valve budget (that reset is the whole point of re-invoking it past a tripped valve). "As if the stop never happened" now scopes to the continue paths only.
- **#5 read-only coverage of audit/validate phases (RFC §1.3)** -- MARKHUNT/PREPARE/VALIDATE quietly write (BOARD tickets, kitchen/handoff, structural repair). read-only now reaches them only in report-only form: run and report in chat, write nothing.
- **#7 goal_waves double-count via ADD -> PLAN (RFC §2.4, plan.md, add.md)** -- ADD increments `goal_waves` at its RETURN; when that RETURN was `PLAN`, the following PLAN run incremented again for the same HUNT->ADD cycle. plan.md now skips its increment when entered directly from ADD's RETURN; add.md and §2.4 carry the matching note. Failed safe (over-counted, tripped early) but real.
- **#8 version guard with no VERSION file (RFC §1.2)** -- previously undefined. Missing/unreadable/unparseable `VERSION` now degrades to `mode: read-only`, same as the stale-RFC end of the guard, instead of writing a guessed `saipen_version`.

CONFORMANCE rows 30-32 added with matching `tests/scenarios/` READMEs. #13 (guide command-drift -- validate/plan/status/goal/stop/ship missing across the 33 guide files) is real onboarding debt but a 33-file chore -- ticketed T-153, not bundled here. `tools/validate.py` green.

## 7.50.0 -- 2026-07-23 -- T-148: markhunt/prepare synced across all 33 guide translations
Closed out the two tickets this session opened on itself (T-147 shipped as part of v7.49.0's own batch is separate; this is T-148, the concrete follow-through T-124 pointed at).

Checked all 33 `guides/GUIDE_XX.md` files individually rather than assuming uniformity -- turned out to matter: 29 had a plain 8-row table (set/continue/stop/status/goal/clean/translate/ship) with neither `saipen markhunt` nor `saipen prepare`; 4 (EN, RU, EE, DED -- the bonus "Дед" voice) already carried `markhunt` from an earlier manual pass but still lacked `prepare`. Added whichever was missing to each file:

- The 29 plain files each gained both rows, inserted between `translate` and `ship`, in a short phrase matching that file's existing terseness.
- EN/RU (rich 3-column persona-named tables) and EE/DED (simpler description-only) each gained a `prepare` row matching their own established style and row order -- RU's own markhunt-before-translate ordering was kept as-is rather than forced into GUIDE.md's canonical order.

Deliberately did not backfill `validate`/`plan`/`status`/`goal` gaps noticed in several files along the way -- those predate this session's own markhunt/prepare additions to GUIDE.md and are a separate, pre-existing scope, not what T-124/T-148 were tracking.

Both validators green.

## 7.49.0 -- 2026-07-23 -- last 11 MARKHUNT tickets closed + a fresh 26-finding subSaipen audit distilled
Drove the MARKHUNT backlog to zero and processed a brand-new external audit (`tofix/SAIPEN_SUBSAIPEN_AUDIT.md`, 26 findings against `extensions/subs/PROTOCOL.md`) in the same pass. Both tofix/ audit files deleted once fully extracted, per standing permission.

**RFC-level tickets (T-124..T-140), each verified against live files first:**
- **Real, fixed**: LOG skeleton missing `[agent:]`/`T-none` (T-126); transition table's `DONE -> ADD` was never actually implemented by any phase doc -- `done.md` itself says ADD is only ever reached via a clean HUNT, so the table entry was removed, not implemented (T-127); `saipen stop`'s interaction with `goal_mode` was never stated directly -- now explicit: stop pauses, never clears it (T-129); the unknown-command rule didn't check active extensions' own commands first, contradicting § 1.9's own carve-out for e.g. `saipen sub spawn` (T-130); `goal_waves`' HUNT->ADD increment timing clarified (fires at ADD's own `RETURN`, not the resulting ticket's eventual completion) + README's command list expanded from 4 to 10 (T-131); HUNT now checks `## BLOCKED` (not just TODO/DOING) before ticketing a finding, so a known-but-blocked issue can't fork into two tickets (T-133, one of four sub-parts); VERIFY gained hysteresis -- a ticket blocked a second time escalates to session-level `BLOCKED` instead of a fresh retry budget (T-138, CONFORMANCE row 28 added).
- **Real but the fix was ownership, not mechanism**: GUIDE.md's markhunt/prepare rows never reached the 32 hand-maintained `guides/GUIDE_XX.md` siblings -- `translate.md` now states plainly that its own drift-rescan permanently excludes hand-maintained siblings, so nothing was silently assuming auto-sync; the actual 32-file content fix is now its own ticket, T-148 (T-124).
- **False alarms, closed with reasoning**: `blocker: none` vs empty, checkpoint ordering, and "phase history not tracked" (already an accepted, documented gap, CONFORMANCE row 14 -- whose stale "fourteen"-phase count got bumped to sixteen while re-checking it) (T-133, remaining sub-parts); bare-goal/init-WAIT/plan-size-gate all already consistent, likely fixed by an earlier fix this session (T-132); `BLOCKED -> DONE` already documented in `blocked.md` step 5 (T-127, one sub-part); `next_action`'s single-field design already unifies its "audiences" via the existing "`WAIT:` counts as executable" framing -- splitting it would add sync surface to solve a solved problem (T-137); the `goal_waves`/`goal_tickets` dual cap's orthogonality is the safety valve working as designed, not a flaw -- a runaway on either axis still stops and reports (T-140).

**SubSaipen audit (26 findings, grouped T-144/145/146):** 18 real+fixed in `extensions/subs/PROTOCOL.md` (OUTBOX `reviewed` status + backpressure cap + collect-time freshness check + severity field + partial-collect + `_shared/inbox.md` given real shape/ownership/prune rule; T-### translation rule for folded findings + cross-file traceability via the RUN: line text, no RFC change needed; TEMPLATE/STATE.md gained `saipen_home` + a real placeholder; collect's write order now matches RFC § 1.5's crash-safety asymmetry; `saipen sub status`/`pause`/`resume` added; MANIFEST timestamps; BLOCKED subSaipens now surface in `sub list` and get reviewed on the HUNT cadence; spawn validates `saipen_home` first and refuses on an existing `<name>`; clean actively checks+refuses instead of just stating its precondition; HUNT's kitchen sweep now explicitly covers subSaipen kitchens too). 5 dismissed as false alarms (subSaipen tickets already reach DONE at prepare-time regardless of collect, independent of any feedback loop; RFC § 1.2 already fully specifies ticket shape; the TEMPLATE OUTBOX.md file the audit said was missing already exists; the spawn race already lives inside RFC § 1.4's accepted concurrency boundary; restricting the phase enum would contradict § 1's own explicit "procedural, not technical" design). 1 deferred to its own properly-scoped ticket, T-147 (`validate.py` subSaipen coverage is real code work, not a doc-sync pass).

Both validators green.

## 7.48.0 -- 2026-07-23 -- prepare.md and build.md were missing standard phase-doc scaffolding
A fourth external audit (`tofix/saipen_audit3_aboutPhases.md`, cleaner and better-organized than the first three, 32 grouped findings across all 15 phase docs). ~80% overlapped what was already closed or already tracked in `BOARD.md`. Checked the four genuinely new claims directly:

- Two false alarms: an "enum prose says 14-value but lists 15" off-by-one -- no such string exists anywhere in the live file; and a claim that duplicate `hunt(1).md`/`scout(1).md` files exist on disk -- they don't.
- Two real, both simple missing scaffolding every *other* phase doc already has: `prepare.md` never required a completion `LOG` line (every other terminal phase -- `hunt.md`, `clean.md`, `translate.md`, `markhunt.md`, `ship.md` -- does); added, plus an explicit `BLOCKED` path for a failed preparation. `build.md` never mentioned `BLOCKED` at all despite RFC's own transition table listing `BUILD -> VERIFY | BLOCKED` -- added a one-line branch for an unrecoverable build error.

Both validators green.

## 7.47.0 -- 2026-07-23 -- five more audit2/3 findings closed, each smaller than it first read
Continued triaging `tofix/saipen_audit2.md`/`saipen_audit3.md`. All five confirmed real by direct grep against the live files, but each turned out narrower than the audit's own framing:

- **`claim_time` never said UTC**, even though § 1.4 already requires it (`<ISO8601 UTC>`) for the exact same cross-timezone staleness-comparison reason `STATE.md`'s `updated` field states explicitly. § 1.2's own ticket-shape definition just didn't repeat it. Unified.
- **§ 1.9's "schemas explicitly not read by any agent today" is false for `state.schema.json` specifically** -- `tools/validate.py` reads it directly, and `CONFORMANCE.md` § 1 already documented this. `board.schema.json`/`log.schema.json` remain accurately described as reference-only; added the one-file exception instead of weakening the blanket statement for all three.
- **The version guard (§ 1.2) was unimplementable as written** -- it compares a project's `saipen_version` against "what this agent's own copy of RFC.md defines as current," but RFC.md never states a version number anywhere. Clarified: `saipen_version` is the major-version integer only (the `X` in the `VERSION` file's `X.Y.Z`, e.g. `7` for `7.47.0`), and "current" means whatever that file reads right now -- RFC.md deliberately carries no version of its own.
- **`done.md` repeated the exact bug class v7.18.0 already fixed once**: `saipen SYMPTOM` was taught as if it were literal command syntax, but it was never in § 1.10 and never will be -- pure informal shorthand ("describe a bug") that drifted into looking like a real command, the identical failure mode `saipen (hunt)`/`saipen (add)` had. Rewritten to describe the actual mechanism: a bug description is free text for `saipen goal <text>`.
- **`done.md`'s "`saipen goal <text>` sets phase to PLAN" was incomplete**, not wrong -- `PLAN` is the transient first step, RFC § 2.4 has the agent proceed straight into `SCOUT` for the first ticket without stopping. Could read as "ends up in `PLAN`, stays there." Clarified in the same line.

Both validators green.

## 7.46.0 -- 2026-07-23 -- VERIFY/REVIEW's SCOUT|BUILD targets explained, a false alarm laid to rest
User brought two more external audits (`tofix/saipen_audit2.md`, 28 findings; `tofix/saipen_audit3.md`, a raw 120-observation reasoning dump that cut off mid-write). Triaged both against the live files rather than trusting either at face value -- most overlapped what v7.43.0-v7.45.0 already closed or what's already tracked in `BOARD.md`'s `## BLOCKED` (`T-127` covers the undocumented `DONE -> ADD` / `ADD -> HUNT` rows both audits also flagged).

One claim was repeated independently by both audits: the transition table's `VERIFY -> REVIEW | SCOUT | BUILD | BLOCKED` row supposedly contradicts `CHANGELOG` v7.18.0's own record of narrowing that exact row to `REVIEW | BLOCKED` -- read as either a regression or a lying changelog. Checked v7.18.0's entry verbatim and the live `phases/verify.md`: not a regression. v7.18.0 removed a real bug (a failing ticket bouncing back to `BUILD`/`SCOUT` for a retry instead of hitting the hypothesis/fix-cycle cap). `verify.md`'s current `SCOUT`/`BUILD` targets serve a completely different, later-added purpose -- after the cap trips and the failing ticket moves to `## BLOCKED`, the agent picks up a *different* workable ticket, landing in `SCOUT` or `BUILD` for that one. Both audits saw only the table row, never `verify.md`'s actual text, and drew the wrong conclusion from a real but incomplete observation.

Since two independent runs tripped on the identical misreading, added a permanent clarification directly at the transition table (`RFC.md` § 1.6) explaining what those targets actually mean and citing v7.18.0 by name, so the next audit -- human, model, or MARKHUNT -- doesn't have to rediscover this from scratch.

Both validators green.

## 7.45.0 -- 2026-07-23 -- MARKHUNT's own self-contradiction fixed at the root
Continued the MARKHUNT backlog triage: the remaining two P0 findings, plus one that turned out to hit this session's own recent work directly.

- **A genuine self-contradiction in `markhunt.md` itself.** It claimed completion "always halts one turn for the user, even mid-`goal_mode`" -- but transitioning to `DONE` with `goal_mode: true` would let `done.md`'s existing Goal-Mode-Empty-Board step auto-proceed straight to `HUNT` regardless, exactly the silent continuation MARKHUNT was supposed to prevent. Fixed at the root, not by patching the assertion: `done.md`'s own step now has an explicit exception -- any `[MARKHUNT]`-tagged ticket sitting in `## BLOCKED` blocks the auto-`HUNT` cascade until triaged out. `markhunt.md`'s text now points at this real mechanism instead of just asserting the halt happens.
- **`BLOCKED`'s dual meaning** (`## BLOCKED` on `BOARD.md` vs session-level `STATE.phase: BLOCKED`) is real, but the audit's own suggested fix -- rename one of the two -- was disproportionate: a full rename ripples through the phase enum, both validators, the schema, every phase doc, templates, fixtures, and any project's own already-existing `STATE.md` files. Applied a lighter fix: the transition table's own intro now states explicitly, right where the ambiguous bare word first appears, that `BLOCKED` there is always the session-level state.
- **MARKHUNT's own thoroughness self-test (lacking a hash-match-style hard verification the way HUNT has one) was deliberately deferred**, not rushed -- it needs real design (what a completeness manifest would actually record, what `VALIDATE` would cross-check it against) rather than a quick doc-sync patch. Left in `## BLOCKED` with an explicit "needs real design" note.
- Cleaned up a duplicate ticket ID a concurrent edit introduced (the ongoing translate session finishing its final waves happened to resurrect an already-superseded, already-buggy copy of `T-115` back into `## TODO`) -- removed only the stale duplicate, left the legitimate concurrent work untouched.

Both validators green.

## 7.44.0 -- 2026-07-23 -- "BOARD.md is empty" unified to "no open TODO tickets" everywhere
Continued triaging the MARKHUNT backlog (`BOARD.md`'s `## BLOCKED`), picking up the remaining P0 and its closest relatives.

- **RFC § 2.1's own preamble contradicted its own HUNT bullet two lines down.** The section's opening line and its ZERO-PROMPT AUTO-TRANSITION bullet both said "`BOARD.md` is empty" -- but the HUNT bullet right below already correctly said "no open `TODO` tickets without blockers" (fixed in `done.md`/`hunt.md` back in v7.40.0, never back-ported to § 2.1's own preamble). `DONE`/`BLOCKED` tickets sitting on the board don't block Maintenance; only open `TODO` does -- an agent reading only the preamble could reasonably conclude otherwise. Unified both to the precise phrasing. README's two "Board empty?" mentions softened to match, same meaning, lighter touch for prose that was never meant to be normative-precise anyway.
- **RFC § 1.2's `WAIT:` list didn't cover `BLOCKED`'s own documented use of it.** Five legal categories were listed (manual-verify, destructive-op, first-publish, user brake, INIT bootstrap) -- but `phases/blocked.md` has always instructed asking the user via `next_action: WAIT: <question>` when the session is stuck on a credential or decision, a sixth category RFC never actually listed. A cold agent reading § 1.2 in isolation had no textual basis for `blocked.md`'s own instruction. Added it as the sixth legal category, same "concrete question, not a vague one" constraint as the other five.

Both validators green.


# Changelog

> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

## 7.71.1 -- 2026-07-25 -- SECURITY.md said more than it could deliver

Two accuracy fixes in the security policy, both found by finishing the sweep rather than assuming the remaining docs were fine.

- It claimed local writes were "each guarded by an automatic `.bak` backup before the first modification." True for your own config files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`), which are only ever edited via the delimited SAIPEN block and copied to `.bak` first. **Not** true for the skill directories the injector creates: those are overwritten wholesale on install and removed recursively on uninstall, with no backup at all. That's intentional -- they hold nothing but copies of this repo's files -- but a blanket safety claim in a security policy is exactly the wrong place to round up. Both levels now stated exactly, with a warning not to keep hand customizations inside a copied skill folder.
- Its secrets list still named only the pre-v7.69.0 paths, missing `.saipen/recovery/` and `.saipen/logs/` -- drift introduced by this session's own RFC § 1.1 change. Added, with the reason they're the subtle ones: Recovery copies a corrupt `STATE.md` verbatim and sealing moves LOG lines verbatim, so anything that reached the original gets archived by machinery designed not to alter content.

Also checked and deliberately **not** changed: all 33 `guides/GUIDE_*.md` omit `saipen plan`/`saipen validate` from their friendly command tables, but every one carries the RFC § 1.10 pointer to the authoritative full list -- which is precisely the T-153 resolution from v7.55.0, not drift. `extensions/adapters/` verified clean.

## 7.71.0 -- 2026-07-25 -- T-177 closed: uninstalling destroyed the backup installing made, and nothing enforced conformance on a PR

Injector re-run authorized and executed -- `bootstrap/inject.ps1` across 7 targets, verified by diff against the home: `CONFORMANCE.md`, `BOOT.md`, `RFC.md` and `extensions/subs/` now identical on all four platforms (`.claude`, `opencode`, `.codex`, `.agents`). v7.70.0's distribution fix is closed on the live machine, not just in source.

The sweep then moved into the executable surface nobody had reviewed yet:

- **`bootstrap/uninstall.sh` destroyed the backup `bootstrap/inject.sh` had deliberately made.** `strip_block` used `sed -i.bak`, which overwrites `"$1.bak"` -- the file where `inject.sh`'s `backup_file()` had stashed the user's *original, pre-SAIPEN* `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` -- replacing it with the current SAIPEN-containing content, and the cleanup `rm -f "$1.bak"` right after then deleted it outright. Uninstalling SAIPEN wiped the exact backup installing SAIPEN existed to create. The PowerShell twin never had this bug (it only ever writes `.uninstalled.bak`); shell-only. Fixed with a distinct `.saipen-strip-tmp` suffix and verified live: the original survives, the block is still stripped correctly.
- **`bootstrap/export.*` writes its archive into the project root** by design, but `.gitignore` didn't cover the name -- so an exported state archive sat untracked and one careless `git add -A` from being committed. Added `saipen_export_*.tar.gz` / `.zip`.
- **`CONTRIBUTING.md` pointed contributors at the wrong validator.** Step 4 told them to run `tests/validate.sh` and `validate.ps1` -- the *frozen portable floor*, which states in its own header that new checks land only in `tools/validate.py`. The canonical validator, the one that checks `STATE.md` against the schema, walks the `LOG.md` event graph across sealed segments, and verifies the runtime manifest and injector wiring, went unmentioned in the single place a contributor is told what to run before opening a PR. Rewritten: canonical first, floor as the explicit no-Python fallback.
- **There was no CI.** The pre-commit hook is opt-in, installed per machine, and bypassable with `--no-verify`, so nothing enforced conformance on a push or a pull request -- in a repository whose own changelog records the README-badge-vs-VERSION drift shipping three separate times. Added `.github/workflows/validate.yml`, running the canonical validator and then the portable floor (a change that breaks the floor would otherwise silently degrade no-Python hosts while CI stayed green). Both steps were run locally first and exit 0; the workflow YAML parse-checked.

## 7.70.0 -- 2026-07-25 -- T-176 closed: full-repo hunt, and the last two releases had shipped two commit-blocking regressions

User asked for a full sweep for logical gaps, quality over token cost. Swept the executable surface first, where defects are real rather than documentary -- and the two worst finds were this session's own, both breaking *other people's* projects rather than this one.

- **v7.65.0's rewritten home-repo fingerprint hard-FAILED ordinary projects.** Loosening it from "`saipen/RFC.md` exists" to "a `saipen/` directory + `VERSION` + `README.md`" made it match any project that merely keeps a folder called `saipen/` next to a version file and a readme -- extremely ordinary. Those projects got a hard FAIL accusing them of a stray clone that never happened, and because `tools/install_hook.py` wires the validator into pre-commit, **it blocked their commits**. Reproduced live, then fixed by adding `bootstrap/` as the discriminator: home-only, and untouched by the very nested-clone corruption the check exists to catch (that incident replaced `saipen/` alone). Verified three ways -- consuming project passes, real corruption still caught, home unaffected.
- **v7.66.0 legalized `no-publish` + `SHIP` but left all three validators banning it.** `tools/validate.py`, `tests/validate.sh` and `tests/validate.ps1` each still asserted the old rule, so a git-less project sitting in a now-legal state failed conformance and -- again through the pre-commit hook -- couldn't commit. Fixed in all three, plus `tests/scenarios/no-git-ship-denial/README.md`, which asserted the literal opposite of current behavior, and CONFORMANCE row 8. Verified that `no-publish`+SHIP now passes both validators while `read-only`+SHIP still fails, so no regression was traded in.

Also found, all real:

- **`CONFORMANCE.md` was never distributed to skill copies**, though `BOOT.md` -- loaded on every single cold start -- cites it by name, as does `phases/validate.md`. Every injected platform therefore carried a dangling pointer. This is precisely the v7.22.3/v7.25.0 "promised here, never wired there" class the distribution check exists to catch, and the check didn't cover it. Added to both injectors and the runtime manifest, and `dist_tokens` extended from directory to per-file granularity so the whole always-loaded root set is now guarded. Regression-verified by removing the reference and confirming the FAIL.
- **`SPEC.md` listed 14 of the 16 phases** -- no `markhunt.md`, no `prepare.md` -- and knew nothing of `BOOT.md` or the crew launchers. (A LOG entry from an earlier session claims SPEC.md was checked and clean; that check was clearly superficial.)
- **The Core `extensions/templates/BOARD.md` shipped with no shape example**, while the subSaipen template gained one back in v7.58.0 after a real incident where a worker invented its own ticket shape. The lesson had been applied to one template and not the other.
- **Neither validator skips HTML comments** -- found by testing the previous fix rather than assuming it worked. A commented-out example ticket in a template parses as a live ticket on a brand-new board, and `tests/validate.sh` scans for the dependency field across the whole file rather than only ticket lines, so the two validators disagree about what's legal. Both templates now carry de-fanged examples (no leading dash, no field name adjacent to an id) with the trap documented inline so it isn't reintroduced. All four combinations -- both templates against both validators -- verified clean.

Note: deployed skill copies are stale until `bootstrap/inject.*` is re-run (they lack `CONFORMANCE.md`). That writes into the user's home config, so it waits on their say-so.

## 7.69.0 -- 2026-07-25 -- T-175 closed: 19 real gaps, including two the last two releases introduced

Third batch of outside-audit files in `thoughts/`. Six claims died on contact with the live repo -- notably "goal_mode + mature product = infinite loop" (`phases/add.md` already sets `goal_mode: false` *before* transitioning to DONE, so `done.md` never sees a live goal run) and the ship.md tag-recreate concern (already fixed in v7.68.0; that reviewer had a stale snapshot). Nineteen survived, and two of them were mine:

- **My own v7.66.0 sealing "crash-safety" was wrong where it mattered.** It cheerfully said a crash between writing the sealed segment and replacing the active log means "worst case the next agent re-attempts sealing on a file that's already safely duplicated." A blind re-attempt writes the same `E-###` lines into a *second* segment -- duplicate IDs across the sequence, which is the exact breakage sealing exists to prevent. Now the re-attempt must compare against the highest existing segment first and, on a match, only replace the active file.
- **My own v7.68.0 BOOT clone-fallback assumed git exists.** It told a cold agent with a dead `saipen_home` to clone the repo -- but `mode: no-publish` means git is *missing*, so that path is unavailable exactly when it's needed. Now falls through to a concrete `BLOCKED`/`WAIT:` asking for a local clone path or git.

Other real ones:

- **VERIFY hysteresis violated `blocked.md`'s own entry condition** -- it sent the whole session to `BLOCKED` on a ticket's second failure, while `phases/blocked.md` opens by stating you only land there after confirming no other ticket is workable. Now it checks the board first; the hysteresis caps retries on *that ticket*, it never halts a session with real work left.
- **MARKHUNT's closure self-test was unsatisfiable whenever its own grouping rule was followed** -- the test demanded `findings:` equal the number of `[MARKHUNT]` tickets, while the same doc says to group related findings into one ticket. Ten findings in three tickets failed the test by construction. Now it checks findings are *accounted for*, and a grouped ticket must carry its own count.
- **Secrets were never banned from `.saipen/recovery/` or `.saipen/logs/`** -- precisely the two places that copy content *verbatim* by design (Recovery duplicates a corrupt STATE; sealing moves LOG lines unedited). A secret reaching either original was faithfully archived by machinery whose whole job is not to alter content.
- **A `BLOCKED` session could escape into autonomous HUNT** -- a board holding only `## BLOCKED` tickets satisfies "no open TODO" on a literal reading of § 2.1, letting a session that stopped for a human decision quietly start unrelated work instead.
- **`T-###` reuse after pruning** -- `phases/clean.md` prunes DONE tickets off the board by design, so "highest ID on the board + 1" silently reuses an already-issued ID. Next ID now derives from `LOG.md` (including sealed segments), which never loses history.
- **The `read-only` paradox**: the mode is set because filesystem writes are unavailable, yet § 1.3 requires writing it to `STATE.md`. Resolved honestly -- report it, work under it, don't fabricate a write, and never read a stored `mode:` as proof of the *current* host's capabilities.
- **Recovery had two unhandled shapes**: no `## DOING` at all (a crash between the LOG and BOARD writes leaves the ticket still in `## TODO`), and a last event that's session-level rather than ticket-level. Both now have explicit rules instead of an implied "figure it out."
- **Plain LOG appends had no crash-safety rule** at all, while BOARD/STATE/sealing all did. A truncated *last* line is now defined as debris; earlier malformed lines remain history with a bad shape, a different problem with a different rule.

Plus: BUILD's "risky edit: LOG rollback first" no longer reads as a substitute for § 1.1's confirmation gate; ADD's `RETURN PLAN_or_SCOUT` got a real criterion instead of a coin flip; § 1.6 now states that `-> BLOCKED` is universal and a phase doc's silence isn't a prohibition; from-any-phase commands must checkpoint an in-flight `DOING` ticket; the safety valve got a legal `WAIT:` category (§ 2.4 orders a stop-and-wait that § 1.2 had no legal way to express); goal-counter bumps must leave an identifiable `DEC` line, since Recovery is *required* to rebuild counters by counting them; a missing `python` maps to real degradation instead of being ignored; explicit `saipen ship` doesn't bypass VERIFY/REVIEW; and `phases/init.md` got the linked-worktree guard that stops it creating a second, disconnected `.saipen/`.

`tools/validate.py` gained a mechanical soft-cap WARN on the active `LOG.md` -- the segmentation rule previously had no signal whatsoever, so nothing ever told an agent the tail had outgrown what a cheap read can load. Verified live: inflated the log to 363 lines, confirmed the WARN fired, restored.

## 7.68.0 -- 2026-07-24 -- T-174 closed: second outside-audit batch, 13 real gaps found+fixed

A second batch of 10 outside-audit files landed in `thoughts/`. Same discipline: verify every claim live before touching anything. Most repeated already-fixed or already-rejected ground from a stale snapshot (`add.md`, README/GUIDE version, `init.md`, `ship.md` no-publish, `hunt.md` delete-free safety, CONFORMANCE row 38, T-136 -- all re-checked, all still correct) or re-proposed the ratified-rejected `goal_exit` command (`KNOWLEDGE/decisions.md`, three prior rejections on file). 13 real gaps survived contact with the live repo:

- **`validate.md` repaired structure even under `mode: read-only`** -- a direct RFC § 1.3 violation (read-only VALIDATE must report only). Added the guard the phase doc was missing.
- **T-171's boundary check only compared `.saipen/` metadata files**, not the whole working tree -- a confused subSaipen could corrupt real source code past it, undetected. Widened to the full tree, and connected the violation response to a formal `STATE.phase: BLOCKED`/`WAIT:` instead of leaving it as "mention it in chat and hope."
- **`markhunt.md`'s closure self-test hard-required a git hash**, permanently unsatisfiable on a no-git project. Added an explicit `no-git` literal for `head_start`/`head_end` that satisfies the check by construction.
- **`BOOT.md` had no fallback when `saipen_home` is empty or dead** -- the one step that can otherwise dead-end a cold agent with nowhere left to look for its own phase docs. Added the clone-and-update path directly in BOOT, not only in lazily-loaded RFC § 1.7.
- **`verify.md`'s clean-tree step used `git restore`**, which never touches new untracked files a failed attempt created. Added scoped cleanup targeting only those files -- never a blanket `git clean`, which would just as happily eat unrelated scratch RFC § 1.5 already protects.
- **`clean.md`'s "stale TODO" criterion was undefined.** Now evidence-based (superseded by a later ticket/decision, or its cited files/behavior no longer apply) -- explicitly never a clock, since `BOARD.md` tickets carry no creation timestamp to age against.
- **RFC § 1.5's dirty-tree attribution required git with no fallback.** Now reuses Recovery's own no-git mtime heuristic for the identical question ("did I leave this, or did someone else").
- **A parallel `TRANSLATE` instance had no cold-start path back to its own state.** `BOOT.md`'s generic path would hand it the *shared* `STATE.md`'s phase instead of its own `.saipen/saitranslate/STATE.md` -- fixed as the direct mirror of T-173's fix (that one covered the main agent finding a foreign claim; this covers the parallel instance itself never knowing to look at its own file).

Five cheaper fixes alongside: `ship.md`'s tag delete-recreate scoped explicitly to a never-yet-pushed local tag, and its first-publish trigger widened to cover "`origin` exists but is still empty"; `sk-***` secret redaction marked illustrative rather than the only shape (`ghp_`, `AKIA`, `Bearer`, connection-string passwords all count); `human_note` clearing now requires a `LOG.md` line so it leaves a trace; extension-vs-extension bare-command collisions get an explicit decline-and-ask instead of silently picking one; `verify:` field execution is now gated against obviously destructive patterns, same footing as RFC § 1.1's existing destructive-op list.

Also corrected `BOOT.md`'s stale "~30-line" self-description (real length moved past that a while ago, purely from real fixes) to "compact" everywhere it was quoted (`BOOT.md`, `SKILL.md`, `CONFORMANCE.md`, the `boot-cold-start-kernel` scenario).

`tools/validate.py` green throughout.

## 7.67.0 -- 2026-07-24 -- T-173 closed: TRANSLATE carries subSaipen's old boundary-violation gap too

User asked for a fresh Core self-review of the whole project -- not another outside audit-on-phases (that ban is specifically about phase-count-collapse proposals), a direct look for logical holes. Read every phase doc not yet covered this session, RFC's command surface and Part 2 in full, `KNOWLEDGE/decisions.md`, and both reference extensions.

Found one real, personally-witnessed gap: `TRANSLATE`'s parallel-instance mode is explicitly told not to write the shared `phase: TRANSLATE` into `.saipen/STATE.md` (stated twice -- RFC § 2.1 and `phases/translate.md` § 1) -- but neither location said what to do if that rule already got broken. It had: this exact session's own `deepseek-v4-flash-free` parallel run did precisely that (see 7.65.0's note), and there was no documented recovery path, only an improvised one. Generalized RFC § 1.4's stale-claim recovery (already covers `## DOING` BOARD tickets) to whole-`STATE.md` phase claims: finding a phase you never entered, under an `agent:` you don't recognize, with no matching `LOG.md` activity since, now has an explicit procedure -- LOG the takeover, inspect what was actually produced, then rebuild `STATE.md`, never silently overwrite or silently keep working under it.

Everything else read this pass (`scout`/`build`/`hunt`/`init`/`plan`/`prepare`/`clean.md`, `decisions.md`, `extensions/security`+`performance`) was internally consistent -- nothing else ticketed.

Also: at the user's explicit request, stopped mid-way through personally translating `saitranslate`'s remaining 22 languages -- bulk mechanical translation is better delegated to a small/cheap model, not this session's tokens. `T-168` stays open, noted accordingly.

`tools/validate.py` green.

## 7.66.0 -- 2026-07-24 -- T-172 closed: outside-audit review, 4 real gaps found and fixed, 16 stale

User dropped two more outside-audit files into `thoughts/` and asked for a fresh read. Same discipline as `audit5`/`6`/`7` earlier this session: verify every claim against the live repo before touching anything, fix only what survives.

- **20 claims checked, 16 didn't survive**: 10 were already fixed by past sessions (the author admitted up front they didn't have `BOOT.md`, current `STYLE.md`, `GUIDE.md`, or most `phases/*.md` -- and indeed `markhunt.md`'s closure self-test, `ship.md`'s digest, `blocked.md`/`validate.md`'s `DONE` paths, `add.md`'s § 2.2 sync, and `STYLE.md`'s haiku line were all already there). One claimed "RFC says 14 legal phases but the schema still allows 16" -- RFC § 1.6 plainly enumerates sixteen and `tools/validate.py` confirms it live; stale snapshot from before `MARKHUNT`/`PREPARE` were folded into the enum. Three more (`BOOT`/`SKILL`/`RFC` cold-start sync, `next_action` rigidity, `read-only` phase-write "contradiction") turned out to already be resolved once the current text was read in full -- the live `saiwiki` instance this session personally ran `sub collect` against is direct proof the read-only path already works as designed.
- **4 were real:**
  1. **`mode: no-publish` had no path to `DONE`.** `phases/review.md` makes `SHIP` mandatory before `DONE` with zero exception ("even under `goal_mode`"), and `phases/ship.md` refused to enter the phase at all under `no-publish` -- meaning a git-less project could VERIFY and REVIEW cleanly and then never legally close the ticket. Fixed the same way `read-only`/`manual-verify` degrade instead of dead-ending: RFC § 1.3 now blocks only the git-dependent steps (commit/tag/push), and `ship.md` gained an explicit no-publish branch that still does everything local (README, version bump, CHANGELOG, digest), skips what needs git, LOGs `skipped publish` instead of a failure, and goes straight to `DONE`.
  2. `CONFORMANCE.md` had zero mention of LOG segmentation despite `tools/validate.py` enforcing it live on every run (this repo's own `LOG.md` + `logs/LOG-001.md` are two segments right now) -- added row 38.
  3. LOG sealing never specified a crash-safe write order -- RFC § 1.2 now requires the same temp-file-plus-rename discipline § 1.5 already mandates for `STATE.md`/`BOARD.md`: write the sealed segment first, only then replace the active file, never delete the original before the copy is confirmed.
  4. Recovery's goal-counter rebuild didn't say to look inside sealed LOG segments if the `goal_mode` pivot line itself got sealed away -- RFC § 1.5 now says so explicitly.
- **Bonus, user-requested**: `STYLE.md`'s no-haiku rule lost its "opt-in when explicitly asked" carve-out entirely -- not because it was misused, just to close the one seam a future session could quietly widen back into a habit. A direct request for a poem is unrelated and still fine to fulfill; this is specifically about unsolicited closing-verse decoration.

`tools/validate.py` green throughout.

## 7.65.0 -- 2026-07-24 -- T-171 closed (subSaipen boundary violation, found live) + T-168 partial + T-170 round 3

A real subSaipen boundary violation, caught live on FastPrompter: `saiwiki`'s wave 5 wrote fabricated-looking tickets and draft files directly into the *main project's own* `BOARD.md`/`kitchen/`/`LOG.md`, bypassing `kitchen/OUTBOX.md` entirely -- its own OUTBOX sat stale at wave 4 the whole time. `PROTOCOL.md` § 1 already said this was forbidden, but admits enforcement is procedural with no technical lock, so a weak or confused model can and did break it anyway.

- **T-171 (new, closed same session)**: `extensions/subs/PROTOCOL.md` § 4 collect procedure gained a mandatory boundary-check step 0 -- before trusting any OUTBOX, verify the main project's own `BOARD.md`/`kitchen/`/`LOG.md`/`STATE.md` show no changes the collecting agent didn't make itself. `TEMPLATE/STATE.md` and `TEMPLATE/BOARD.md` both gained explicit inline warnings at the exact point of temptation, so a freshly spawned subSaipen sees the rule before it can break it, not just in a file it never reads.
- FastPrompter's own damage repaired as a one-off favor (not this Core, not this repo): the 7 `WIKI-*` tickets on its board turned out to be genuinely accurate (content really was merged into `docs/wiki/`, not fabricated), one shape-corrupted `LOG.md` line was reshaped without losing content, and 8 redundant scratch files were removed from its `kitchen/` after each was confirmed to have a real merged twin already.
- **T-168 (saitranslate content refresh) -- partial**: found `.saipen/STATE.md` still claiming `phase: TRANSLATE`/`T-168` under `agent: deepseek-v4-flash-free`, silent for hours with zero `LOG.md` entries despite real writes to all 31 `README_XX.md` files -- adopted as a stale claim (RFC § 1.4's spirit, applied to a phase-level claim). That unsupervised run left 4 languages (bg/ded/ru/uk) with genuine invalid-UTF-8 corruption in a newly-inserted platform-list clause -- found via raw-byte decode validation (two earlier detection attempts using byte-pattern grep and `errors='ignore'` both silently reported zero corruption; `errors='ignore'` was hiding the damage, not its absence) and repaired with verified translations. The required saicrew-in-development bullet was missing from all 32 languages -- added to those same 4 plus 6 more high-confidence languages (de/fr/es/it/pt/nl), bringing the total to 10/32. 22 remain, 5 of those (hi/ja/ko/th/zh) missing the platform-list clause entirely too -- left for a dedicated/parallel `saipen translate` instance, not fabricated under this session.
- **T-170 round 3**: a real live trace (user-supplied) of another agent parsing bare `saiwiki init` on a brand-new project surfaced two more gaps. `saipen sub spawn`'s first-bootstrap file list never included `crew.md`, even though `saipen sub sync` already described it as one of "those four shared items" -- a freshly spawned project's `saipen crew` command and README's Crew section pointed at a file that would not exist until someone separately ran `sync`; spawn's list now matches sync's. The bare-name role-adopt rule was also implicitly scoped to the 3 shipped examples plus already-spawned folders -- generalized to any `sai*`-prefixed name (the convention every real subSaipen already follows), auto-spawning it the same one word, without opening bare-word matching to arbitrary unrecognized text. `<subname> init`/`start` documented as identical to bare `<subname>` (same "init" reuse as `saipen set`/`saipen init`, RFC § 1.7).

`tools/validate.py` green throughout (Core untouched -- everything above lives in `extensions/subs/` or is a one-off favor to an external repo).

**Bonus catch, same session**: a stray `git clone` of this same repo (run by another weak crew-session agent) landed at `saipen/` instead of its own directory, silently replacing the RFC/STYLE/BOOT/phases subtree with a nested clone -- no data lost (the clone was an exact copy of HEAD, real content survived one level deeper), but `git status` showed 30 false deletions and `tools/validate.py` silently skipped 5 checks instead of failing loud, because its home-repo fingerprint required `saipen/RFC.md` to already exist -- exactly the file a corruption like this removes. Cleaned up (foreign clone parked aside, inspected, confirmed redundant, then removed; original subtree restored from HEAD) and hardened: the fingerprint now keys on the `saipen/` directory itself, with a loud, specific `FAIL` if `RFC.md` is missing underneath it, tested both ways (simulated the incident, confirmed FAIL; restored, confirmed PASS).

## 7.64.0 -- 2026-07-24 -- T-169 closed: saitranslate structure unified, mechanically, zero fabrication

`.saipen/saitranslate/kitchen/` carried two competing systems for a while -- 30 flat `README_XX.md` files and 32 per-language subdirectories with a fuller doc set. Reconciled with evidence, not a coin flip, and executed carefully since most of it is untracked by git (irreversible if botched).

- Backed up the whole 3.2MB `kitchen/` to `.saipen/recovery/` before touching anything.
- Subdirs won on scope: 5 real top-level docs per language (CODE_OF_CONDUCT/CONTRIBUTING/README/SECURITY/SPEC) vs flat's README-only, and correct coverage of `cs`/`hi`/`id` that flat lacked. But every sampled language's flat `README_XX.md` was fresher (v7.55.0) than its subdir counterpart (v7.41-42.0) -- so content came from flat, structure from subdirs.
- Fixed a real bug found along the way: Estonian's subdir was named `ee` (the *country* code) instead of `et` (the correct *language* code) -- verified both copies were genuinely Estonian content before renaming the directory and all 7 files' suffixes, then replacing the stale README with flat's fresher one.
- Deleted 64 out-of-scope files (`RFC_XX.md`/`STYLE_XX.md` per language -- neither lives at repo root, outside `translate.md`'s own defined scope) and the stale `README_en.md` mirror (English needs no translation).
- Verified independently after the script ran, not trusting its own report: zero loose files at `kitchen/` root, all 32 subdirs match the exact 5-file shape, zero `RFC_`/`STYLE_` files left anywhere.

Content itself is now one version behind current (`v7.55` vs `v7.63`) -- that refresh is T-168's job, reserved for a dedicated/parallel `saipen translate` run, never fabricated under the main session. `tools/validate.py` green (no Core surface touched).

## 7.63.0 -- 2026-07-24 -- BUILD gained its own LOG instruction (misdiagnosed as "RUN is ambiguous", it wasn't)

A live FastPrompter session kept forgetting to LOG, got called out, and self-diagnosed: "RUN is semantically vague, I read it as 'whole session' not 'each discrete act,' AGENTS.md states the rule but has no enforcing mechanism" -- and proposed a new `DISCIPLINE.md` file to fix it.

Checked the live protocol before trusting that diagnosis. It was wrong: RFC § 1.5 already says plainly "MUST checkpoint after every ticket," not after every run or every edit -- there was no ambiguity to resolve. The real gap was mundane and much narrower: `build.md` (the phase where most edits actually happen) had zero instruction to LOG before transitioning to `VERIFY` -- every other phase doc ends with an explicit "LOG one Event Graph line, then transition" step; BUILD never did. And `BOOT.md` (the one file loaded on every cold start) never reinforced the per-ticket checkpoint cadence at all -- only RFC did, which is lazy-loaded "when a rule question comes up," so a session doing routine ticket work might never re-encounter it.

- `build.md` now closes with the same LOG-then-checkpoint pattern every other phase already has, explicit that it's one line per ticket, not one per edit.
- `BOOT.md` gained a short, generic reinforcement of the same per-ticket cadence, citing this exact incident so a future weak model recognizes the pattern instead of re-diagnosing it as a wording problem.

No new file, no second source of truth alongside RFC -- the fix closes the actual gap instead of adding competing machinery. `tools/validate.py` green.

## 7.62.0 -- 2026-07-24 -- `saipen sub sync` + mechanical extension discovery (T-170 b+c)

Two of T-170's three remaining verify items, closed with real mechanisms rather than left as open questions.

- **`saipen sub sync`** (PROTOCOL.md § 7): a project that spawned `extensions/subs/` before the SAIPEN home gained new shared vocabulary (the exact class of drift that broke bare-name recognition in a pre-v7.56.0 project) can now refresh just the shared reference files -- `PROTOCOL.md`/`README.md`/`crew.md`/`TEMPLATE/` -- from `saipen_home`, same freshness check `spawn` already does. It never touches a `<name>/` subSaipen's own `STATE.md`/`BOARD.md`/`LOG.md`/`kitchen/` -- by construction it never looks inside a `<name>/` folder at all, so live per-agent history stays exactly as protected as `spawn`'s own "refuse if already exists" rule already makes it.
- **`BOOT.md`** -- loaded on every cold start, Core-only, zero crew-coupling -- now tells an agent facing an unrecognized single word (not a known § 1.10 command) to check `.saipen/extensions/*/PROTOCOL.md`/`README.md` for an RFC § 1.9 extension defining it, *before* guessing (FreeBuff's earlier "saipen"+"python" portmanteau) or declining outright (OpenCode's earlier flat refusal). This is the cheapest point in the whole read order to close that inferential gap -- the file every session reads first, generic enough to name §1.9's mechanism without naming crew specifically.

Both re-deployed live via a second authorized injector run and verified by diff against the actual installed `~/.config/opencode/skills/saipen/` and `~/.agents/skills/saipen/` (FreeBuff's own read path) folders -- not just source-committed.

T-170's third item (test against weak/free-tier models specifically) still needs an actual live re-test once FreeBuff's own uptime allows -- the user's closure bar (this agent personally verifies end-to-end before "in development" language changes) still governs. `tools/validate.py` green.

## 7.61.0 -- 2026-07-24 -- worktree-aware `.saipen/` resolution + injector fix deployed live (T-170)

A fresh OpenCode session reported "No `.saipen/` at project root, not initialized here" for a FastPrompter checkout that plainly has one. Root cause traced live, not guessed: `.saipen/` is gitignored by design (RFC's own local-only working-memory rule), and the platform (confirmed via `git worktree list`: FreeBuff creates `.freebuff/worktrees/<id>/` per thread) spawns each session into a **linked git worktree** -- which only receives tracked content, so `.saipen/` never arrives even though the main worktree has one. Verified directly: `git rev-parse --git-common-dir` from inside the linked worktree resolves to the main repo's real `.git`, and `.saipen/` is confirmed absent there, present at the real root. This is likely the actual explanation behind an earlier FreeBuff "No read access" report too, reframed -- not a permission block, a genuinely absent path.

- **`RFC.md` § 1.1 and `BOOT.md`** now instruct checking `--git-common-dir` for a linked-worktree signal (a path ending `/.git`, not a bare `.git`) before concluding "not initialized" -- resolve the main worktree's root and look there instead of defaulting to `saipen set`, which would have silently created a second, disconnected `.saipen/` and orphaned the real continuation memory.
- **Injector re-run, authorized and executed.** `bootstrap/inject.ps1` run against this machine and verified by diff (not trust): `extensions/subs/PROTOCOL.md` § 7 + `crew.md` are now byte-identical between source and the live `~/.claude/skills/saipen/`, `~/.config/opencode/skills/saipen/`, `~/.agents/skills/saipen/` folders; the new worktree-resolution text confirmed present in all three. The "global skill never carried extensions/subs/" failure from v7.58.0 is now actually closed on this machine, not just source-fixed.

T-170 stays open -- live crew re-verification is still paused pending FreeBuff's own uptime, and the user's explicit closure bar (this agent must personally run and verify the full 3-role mechanism end-to-end) still governs when "in development" framing in the docs may change. `tools/validate.py` green.

## 7.60.0 -- 2026-07-24 -- README/GUIDE freshness pass: platform list + honest saicrew mention

User asked "is README current?" -- checked every claim against live RFC (core loop, HUNT/ADD, 3-wave/20-ticket cap, `sk-***` redaction) and all came back accurate. The gaps were in what's missing, not what's wrong:

- **Platform list undercounted.** README and GUIDE.md both said the injector "teaches Claude Code, Gemini, OpenCode, Aider, Antigravity" -- five. `bootstrap/inject.ps1`/`.sh` actually cover seven: missing **Codex CLI** and the generic `~/.agents/skills` reader (**FreeBuff**, etc.). Both docs corrected.
- **saicrew was invisible.** A fully-shipped feature set (v7.52.0-7.58.0: saipython, the crew bonus layer, BOOT.md) had zero mention anywhere in README or the GUIDE.md hub. Added one honest line to each, framed as **in development / under active live testing, not yet verified end-to-end** -- not oversold as finished. The four guides that already described the spawn mechanism in detail (DED/EE/EN/RU) were checked and already carried the right cautious tone ("brand new, zero battle scars yet") -- left untouched.
- **Closure bar recorded on T-170**: the user set it explicitly -- this agent must personally run and verify the full 3-role mechanism end-to-end before the "in development" framing (in docs or on the board) upgrades to anything stronger. Recorded verbatim on the ticket so it survives any future checkpoint.

`tools/validate.py` green.

## 7.59.0 -- 2026-07-24 -- no default haiku (again -- it snuck back in)

Turns out this protocol killed a closing-haiku requirement once before (pre-v7: "Removed haiku requirement completely... Haiku deleted", CHANGELOG_ARCHIVE.md). It quietly came back anyway -- not as a rule, just as an unrecorded habit -- and ended up baked into a real shipped file: `extensions/subs/crew.md`'s closing verse, paid for on every load.

- Removed the verse from `crew.md`.
- Added an explicit `STYLE.md` line (next to the existing no-multi-language-garnish rule, same reasoning) so it doesn't quietly grow back a third time: no default closing haiku/verse in chat or in any shipped file, opt-in only when the user asks for one in the moment.

`tools/validate.py` green (no structural surface touched).

## 7.58.0 -- 2026-07-24 -- crew dogfooding: three real spec gaps found and fixed live (T-170)

Running an actual 3-agent crew test on FastPrompter (two free-tier weak models: FreeBuff/OpenCode Zen both on DeepSeek V4 Flash) surfaced real gaps no amount of internal review had caught. Each is fixed at the source, not patched around.

- **Global skill never carried `extensions/subs/` at all.** Confirmed by directly querying FreeBuff's own local `.freebuff/desktop.db` (a real, readable SQLite store -- threads/messages/parts_json) mid-session: the agent loaded the "saipen" skill, read the globally-injected RFC/STYLE/UI, found zero mention of subSaipen roles anywhere, and reasoned `saipython` was a "saipen"+"python" portmanteau -- a plausible wrong guess, not a failed lookup. `bootstrap/inject.sh`/`inject.ps1`'s `copy_skill()` never included `extensions/subs/` in the distributed bundle. Both scripts now copy it; `tools/validate.py`'s `dist_tokens` check extended to catch a regression here. (Re-running the injector against this machine's actual installed skill folders is a separate, larger action -- not done automatically, needs the operator's own go-ahead.)
- **`TEMPLATE/BOARD.md` shipped empty, no example.** A live saihunt run (once it did understand its role) invented its own board shape by copying `OUTBOX.md`'s bold-field markdown instead of RFC §1.2's checkbox ticket line -- nothing in `PROTOCOL.md` or the template contradicted that guess. Fixed: an explicit example in both `TEMPLATE/BOARD.md` and `PROTOCOL.md` §1, spelling out that the board uses Core's checkbox shape, never the OUTBOX shape.
- **Spawn instructions never told an agent to set a real `updated:` timestamp.** `PROTOCOL.md` §7 explicitly listed `agent:` and `saipen_home:` as fields to replace at spawn, but not `updated:` -- observed directly: FastPrompter's spawned saihunt bumped only the *date* half of `TEMPLATE/STATE.md`'s placeholder and left the time at `00:00:00` (a partial-placeholder edit, not a real checkpoint). §7 now lists `updated:` explicitly too.

Also fixed (from the same live session, before the above): a project that spawned `subs/` before v7.56.0 has a frozen `PROTOCOL.md` snapshot missing the crew's bare-name command table -- ad-hoc synced in FastPrompter directly; a durable `saipen sub sync`-style refresh path is still open (T-170 remains on the board, live crew re-verification paused by the user pending FreeBuff's own uptime -- unrelated to any of the above).

`tools/validate.py` green throughout.

## 7.57.0 -- 2026-07-24 -- T-136 closed: MARKHUNT gets a manifest-driven closure self-test

The last open Core ticket -- deferred as design-debt for eight versions because it needed real design, not a rush. MARKHUNT could sweep the surface and declare itself done on pure self-report; HUNT has an exact hash-match skip as a hard closure check, MARKHUNT had nothing analogous. Now it does.

- `.saipen/kitchen/markhunt_progress.md` is now a **manifest**, not a vague note: `vectors:` (which of the 5 scope categories are done), `surface:` (dirs/globs swept), `findings:` (count), `cursor:`, and `head_start:`/`head_end:` (short HEAD hashes).
- **Closure self-test** before `DONE`: `cursor: done`, all 5 vectors present, `head_end` == current HEAD (HEAD moved mid-pass = stale coverage, re-run the moved part), and `findings:` == the `[MARKHUNT]` tickets actually written. Any mismatch = not done, resolve it, never round up.
- The completion line is enriched -- `markhunt -> N findings, V/5 vectors, @head` -- so coverage stays auditable from permanent `LOG.md` after `kitchen/` is swept; a human or VALIDATE cross-checks `N` against the board's `[MARKHUNT]` tickets and that `V` is 5. No `validate.py` change -- the closure is self-enforced and LOG-recorded, no busywork ceremony (exactly what the ticket cautioned against).

CONFORMANCE row 37 + scenario stub. The board now holds only the two saitranslate tickets (T-168/T-169), both correctly deferred to a dedicated/parallel TRANSLATE run rather than fabricated under limits. `tools/validate.py` green.

## 7.56.0 -- 2026-07-24 -- saicrew: run a 3-agent crew with one command each (bonus, zero Core change)

Read the operator's `thoughts/` on running subSaipens as real-time workers and built exactly that -- as a pure bonus layer. Not one RFC rule, phase doc, `validate.py` field, or schema was touched: the crew is assembled entirely from mechanisms Core already ships (subSaipens, OUTBOX, claim locks, the safety valve, `saipen sub` commands).

The picture: you dig the tunnel (the Core agent, `mode: full`, the only writer of real code), and two workers set the beams behind you -- **saihunt** (the sensor, finds bugs) and **saipython** (the fixer, clears the tail from its `pen/`). Both read-only toward the project; their only door out is the OUTBOX; Core pulls through `saipen sub collect`.

- **`extensions/subs/crew.md`** -- the squad contract: three roles + zones, the one-command-per-window flow, the auto-collect gate, graceful degradation, and a pitfall->mechanism table mapping every classic multi-agent failure (amnesia, two agents on one ticket, zombie tickets, fake green, runaway autonomy, dirty-tree panic, stale patches, valve pile-up) to the Core mechanism that already kills it. Zone/done_by/delegation ride as **description tags** (`[zone: src/auth/**]`), never new `|` pipe-fields -- keeping `validate.py`'s `KNOWN_FIELDS` and Core untouched.
- **One-command role adoption** (`extensions/subs/PROTOCOL.md` § 7) -- a bare subSaipen name (`saihunt`, `saipython`, `saiwiki`) spawns-if-needed, *becomes* that sub (reads its own STATE/BOARD, never the main project's), and starts its loop. Type one word -> the agent is that worker and working. `saipen crew` prints the layout.
- **`bootstrap/saipen_crew.bat` / `saipen_crew.sh`** -- one click opens three terminals, each with its command pre-typed.
- The three example subs' `STATE.md` `next_action` now auto-start their own cycle on adoption; crew registered in MANIFEST, subs README, and the injector's global block.

Possible without touching Core because the subSaipen extension (§ 1.9) was built for exactly this -- it layers on top, it never relaxes what Core requires. `tools/validate.py` green (16 phases, 13 manifest files, 3 subs -- all unchanged).

## 7.55.0 -- 2026-07-23 -- ergonomics batch: BOOT kernel, human-digest, human_note, guide pointers

The "10 seconds per session" pass -- everything here cuts what a human or a cold agent has to read.

- **`saipen/BOOT.md`** (T-158) -- a ~30-line cold-start kernel. A bare `saipen continue` reads BOOT -> STATE -> BOARD -> active LOG tail -> executes `next_action`, loading the full RFC only when a rule question actually comes up. A third tier under the 2-tier loader; wired into `SKILL.md`, both injectors, and the `validate.py` manifest. TEST-001 passes off BOOT + STATE + BOARD + tail alone.
- **Human digest** (T-159) -- `saipen ship` and `saipen stop` now (over)write `.saipen/kitchen/digest.md`: three lines (done / remaining / awaiting) so the human opens one snapshot instead of scrolling `LOG.md`.
- **`human_note:`** (T-162) -- optional STATE field, a one-line human->agent nudge read on continue (BOOT step 4) and cleared once applied. Not a ticket, not a goal; one that implies work becomes a real `TODO`. Added to `state.schema.json` as an optional field.
- **BLOCKED-triage nudge** (T-160) -- CLEAN now escalates a ticket that's neither resolvable nor prunable but has rotted across passes into a concrete, two-word-answerable `WAIT:`, instead of letting it sit in the morgue.
- **Guide command drift** (T-153) -- every guide (`GUIDE.md` + 33 `guides/GUIDE_*.md`) now carries an explicit pointer to RFC §1.10 as the authoritative command list, closing the onboarding gap audit5 #13 flagged.
- **Command-surface compression** (T-161) -- reviewed and **rejected**, recorded in `KNOWLEDGE/decisions.md`: the surface is already tiered (three common commands + a rare tail by design), and `saipen x <cmd>`/flags would be churn that collides with the subs `saipen sub` vocabulary for no real gain.

CONFORMANCE rows 34-36 + scenario stubs. `T-136` (MARKHUNT completeness self-test) stays the one open item -- P3 design-debt, deferred on purpose. `tools/validate.py` green.

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


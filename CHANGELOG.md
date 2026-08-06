# Changelog

> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

## 7.201.0 -- 2026-08-06 -- saiui: first-class built-in fixer SubSaipen for UI work

T-506: Built-in role charter `extensions/subs/saiui.md` -- 6 design roles (senior product designer, interaction designer, UI systems designer, accessibility reviewer, UI fixer/implementer, Vintage Golden guardian), 4-tier asymmetric authority boundary, 7-step deterministic read order on every adoption, 6-step design method (Task Map, Action/State Map, Capability Gap Map, IA, Patch Wave, Verification), 17 control heuristics, 7 control-type rules, backend capability gate, and full OUTBOX patch contract with 9 required analysis items in details.

T-507: Deterministic built-in role loading. PROTOCOL.md §3.1 defines built-in charters as first-class inherited material (`sai*.md`). Bootstrap copies charters alongside protocol files. Sync refreshes charters without touching live sub folders. Bare `<subname>` adoption loads project-local charter; missing + shipped exists -> stop with sync recovery. UI- ticket prefix added to namespace table.

T-510: Validation. validate.py checks charter integrity (UI.md reference, no second palette, write ban, fixer contract, UI- prefix, sai*.md in bootstrap). Mission file checked for hypothesis labelling. audit_checks.py: 7 red controls covering charter mutations.

T-509: SAISENT target mission artifact -- 8 seed hypotheses labelled verify-not-assume, two-seat runbook, explicit prohibitions.

T-511: Scenario `tests/scenarios/saiui-adoption/` with saiui instance carrying complete fixer OUTBOX package.

T-508: OUTBOX contract defined in charter §OUTBOX patch contract.

## 7.200.0 -- 2026-08-06 -- expert skill injection lifecycle contract

T-501: Defined a deterministic lifecycle contract for just-in-time expert skill routing in `.saipen/extensions/skill_injection/SPEC.md`. Nine sections cover problem class identification (2-of-4 evidence threshold), smallest-first candidate selection with token budget, injection constraints (what skills may add, base protocol outranks), retain (re-use without re-evaluation), deterministic conflict resolution, replace on confidence shift, eject with post-eject invariant, verification before unload, and five invariants: determinism, no fabrication, canonical state survival, base rules outrank, auditability. Implementation is T-502.

## 7.199.0 -- 2026-08-06 -- a session may not halt a project that has work to do

T-505: `CORE.md` says session-level `phase: BLOCKED` is reserved for when no ticket anywhere on the board is workable, and only the first half was ever checked. So a session halted with a full board is indistinguishable from a legitimate stop: a real obstacle in `blocker:`, a conformant `WAIT: blocked --` naming it, and nobody coming.

Found live rather than reasoned about. A session halted this project with 18 open tickets, two of them workable that instant, over a ticket to translate 29 locales -- which `phases/translate.md` gives to a dedicated instance and forbids Core to grind through, making it a TICKET-level block that CONFORMANCE 232 already places on the ticket's own line. The same state carried `goal_mode: true` beside `phase: BLOCKED`, which section 2.4's Exit list makes contradictory: a blocked session is not a running goal, and left true a resume walks straight back into the autonomous run the block existed to stop. Both new checks fired on the live state before anything was repaired.

T-399: `tools/audit_parity.py` is bounded and observable now -- per-case `timeout=15` with a process-group kill, and a `[i/155]` progress line that names the case being measured. Its result is PASS at 12 of 155 against a stated baseline of 11, recorded as 12 rather than as the ticket's "remains 11", because one more case is genuinely caught by the portable floor.

Its cache could never hit, and the cause is worth naming: the key hashed `repr(ac.CASES)`, and a CASES entry holds callables, so the repr embedded MEMORY ADDRESSES -- `<function demote_the_pick at 0x000001A898177880>` -- and the key changed every process. Proven by comparing a stored key against a freshly computed one with nothing edited in between. The "skipped, unchanged floor and case list" line could never print and the long run ran every time. It is keyed on `tools/audit_checks.py` source bytes now, which is deterministic and strictly stricter: it invalidates on any change to a case, its mutation or its expected substring.

Also repaired from the previous session: a duplicate `E-2115` carrying two different events under one ID with one parent, and `scratch_fix.py` left untracked at the repository root -- caught by the root-file-set check on its first real outing, which is exactly the class it exists for.

CONFORMANCE 242.

## 7.198.0 -- 2026-08-06 -- the installed validator and the repository validator agree about the same tree

T-413: run the INSTALLED validator against this repository and it reported two problems the repository's own validator did not. Same tree, same commit, two verdicts. Reproduced before touching anything, and again after each fix.

Both failures were the same shape and it is the shape worth naming: a check gated on the PROJECT while resolving its subject from the TOOL. `IS_SAIPEN_HOME` is project-relative -- `os.chdir(PROJECT_ROOT)` runs before it -- so it correctly asks "is the project under validation the SAIPEN home". The two checks it gated then went looking in `_tools_parent`, the directory the tool ships from, which in an install is an agent home containing neither a `.gitignore` nor entry READMEs. One reported "root `nul` is not excluded" about a repository whose `.gitignore` excludes it on line 7; the other reported "only 0 entry README(s) resolved" about a project that has four. Absence in the wrong directory, read as a violation in the right one.

One wrong turn is recorded because it was instructive. The first fix redefined `IS_SAIPEN_HOME` to measure the tool's location instead, and 29 scenario fixtures went red immediately: that is a different question with a different answer, since the tool ships from a home while validating somebody else's project almost always. The flag was right; the paths were wrong. A second, smaller wrong turn followed -- resolving the entry READMEs from the project without also gating their CONTENT check, which then demanded a reply-language note from any project's own README.md, and ten fixtures said so.

Evidence is the before/after measurement run end-to-end: fix, re-inject, re-run the installed validator against this repository, compare. Recorded rather than dressed up as a control -- an audit case cannot express it, because that harness mutates project files and runs the repository validator, and a marker asserting the tool's own source would be a guarantor that can only go red once the tool has already crashed. The standing guard is `tools/run_scenarios.py`'s two injector probes, which run the installed validator against a real flattened home and caught the constitution-shipped-out-of-installs break the same day.

CONFORMANCE 241.

## 7.197.0 -- 2026-08-06 -- the changelog says what shipped last, and an invisible byte has nowhere left to hide

T-500: the user opened `CHANGELOG.md` and could not tell what had shipped. Correctly -- its head entry read 7.189.0 while `VERSION` read 7.196.0. Four defects at once, every one a rule stated in prose that nothing checked.

Entries were out of descending order, with 7.192.0 above 7.196.0, because each session prepended relative to whatever it found at the top. One version appeared twice in two heading formats. The archive pointer sat in the middle of the newest entry instead of above all of them. And 153 entries stood against the file's own stated "most recent ~10" -- 1719 lines to scroll for the last release, which is the cost that hid the rest. Worst of the four: 7.188.0's heading had been renumbered to 7.189.0 by a bulk version replace, so a released and tagged version had no entry while another had two.

Order, uniqueness and head-equals-`VERSION` are checked now, each hand red-tested on its own condition. The ~10 bound WARNs rather than FAILs, on the board soft cap's reasoning: overflow is housekeeping debt, not a broken release, and a gate that blocks shipping for tidiness gets switched off. The repair moved 142 entries into `CHANGELOG_ARCHIVE.md` verbatim, the way LOG segments are sealed.

A repo-wide sweep followed, on the same ask. Broken repo-relative links: two, both a placeholder in archived prose. Non-UTF8 or mojibake across every tracked text file: none. Empty tracked files: none. Control characters: five, in two files -- and both files were DESCRIBING this exact defect, a sealed LOG segment and the CHANGELOG archive each carrying raw bytes where the prose meant an escape sequence. The bug had bitten the record of itself. Repaired to their literal escapes as a declared repair, and the control-character check widened from `tools/*.py` to every shipped markdown surface: 11 files swept, now 75. The first scan reported one hit per file and hid two more; the widened check found the pair immediately.

audit_checks 153 -> 154 standing controls. CONFORMANCE 240.

## 7.196.0 -- 2026-08-06 -- a habit that claimed no counter had two

T-487: `HABITS.md`'s habit 8 -- summarising work instead of doing it -- read "None currently. Tracked in open ticket T-487". Both counters already existed, and both predate the ticket that was filed to invent one.

The habit has two shapes and each is answered. A session that produced nothing and talked about it is caught by the session-trace rule: a session that did anything ends having produced a LOG line, a BOARD change, a STATE change or a change to the project's own files, and one with none of those must say exactly that "rather than summarising activity in chat". A session that produced a trace which is itself a plan is caught by the LOG rule that an entry records what already happened and never what is about to -- and that one is mechanically enforced, rejecting `will`, `going to`, `about to`, `plans to` and their relatives in an entry's first clause, with a standing red control behind it.

A claimed gap is the same waste as a claimed counter that does not exist, arrived at from the other side: it sends the next agent to build a duplicate of an already-enforced rule. No checker can see it, because the absence of a counter is not observable from the text; what closed this was checking before building.

One thing was written and then removed rather than shipped: a guarantor tying the new citation to the future-tense gate's identifier. It could only go red in a state where the validator had already crashed, which makes it not evidence. The gate's own standing control is what keeps the citation honest.

CONFORMANCE 239.

## 7.195.0 -- 2026-08-06 -- a move is destructive to whatever loads the moved file

T-498: the deletion gate asks whether a file can be recovered. An archive, a rename or a reorganisation passes that test trivially -- the file is right there in the new place -- and the program is broken anyway, because recoverability is not the property that matters when something loads the old path. Archive, rename and tidy: none of those words sound destructive, and all three are.

Reproduced from a user's session rather than reasoned about. "Put the rest in the archive" moved a GUI module; the entry point loaded it at runtime by absolute path; the very next command raised `FileNotFoundError`. That same session had already reported the work done and verified.

So: sweep for references BEFORE the move. Grep the basename and the path across source, config, scripts, manifests and docs, treat a hit as a blocker rather than a note, and either move the references in the same act or do not move the file. It binds `CLEAN` identically -- pruning and relocating is what that phase does, and tidiness is the exact framing that hides the breakage.

Evidence class is STRUCTURAL_ONLY and cannot be otherwise: nothing here moves a consuming project's files, so no fixture can witness the breakage. What a fixture could witness already exists one layer down -- `phases/verify.md`'s import rung catches this class in a single command, which is why the transcript is best read as two rules missed rather than one.

audit_checks 151 -> 153 standing controls. CONFORMANCE 238.

## 7.194.0 -- 2026-08-06 -- `sc` can actually be walked, and a circuit stage must name a real command

T-499: `sc` shipped defined but not runnable. Four jams, every one found by probing the thing rather than reading it back.

The live `.saipen/extensions/subs/MANIFEST.md` had no saitest entry -- it was registered only in the shipped library -- so spawn and list discovery could not see the sub the circuit's second stage depends on. `saipen collect saitest` had no refusal string while both its siblings have exact ones, leaving stage 3 with no defined no-op. saitest had no invocation route at all: `tt` belongs to `saipen test`, a different command that runs a project's declared suite, and the bare-subname route `extensions/subs/README.md` already defines for every `sai*` sub was never named for it. The refusal is `Not ready: run saitest first.` and the text says why it names the sub rather than a key that would send the reader to the wrong command.

And nothing checked that a circuit stage points at a command that exists. That is the fabricated-command failure with a table around it -- the same shape as the transcript where `hh` produced a ten-row card naming six commands that appear nowhere in the surface. An unchecked circuit is that card with more ceremony. `tools/validate.py` now resolves every verb the circuit names against the command set: the six real ones are collect, continue, hunt, prepare, ship and sub, and a seventh invented one FAILs. Hand red-tested with `saipen sniff`, then red-controlled.

Repository hygiene, since it was asked for and was genuinely untidy: two scratch worktrees left registered in git are pruned, one branch, `main` tracking `origin/main` at 0/0. Three alpha tags from v2/v3 exist locally and not on the remote; deleting a tag is destructive and they are history, so they stay and are named here instead.

audit_checks 150 -> 151 standing controls.

## 7.193.0 -- 2026-08-05 -- `sc`: the circuit, and a stage may not hand forward a claim

T-497: `sc` (`saipen crew`) walks the factories in one fixed order -- sense, reproduce, intake, build, translate, document, publish -- instead of the operator driving each by hand and remembering what the last one said. It adds no mechanism: every stage is a command that already exists, the ledger is the `BOARD.md`/`LOG.md`/`OUTBOX.md` that already exist, and a multi-command chain behind one key is what `ccc` and `qqq` already are. If it ever needs a new phase, field or file format, that is the signal it was designed wrong.

What it adds is the hand-off contract, and the contract has a witnessed cost. In a user transcript an agent archived a file its own entry point loads at runtime, reported "Production Ready" and "проверил: всё работает", and the next command anyone typed raised `FileNotFoundError`. The import rung of `phases/verify.md`'s ladder -- one command, second cheapest after parse -- was never run. A claim travelled where evidence belonged, and every stage downstream inherited it.

So: a stage hands the next stage a reproduction or a verdict, never a claim. What passes forward is a file another agent can read -- an OUTBOX entry, a ticket with its `verify:`, a LOG line carrying the command and its output. Chat is not a hand-off surface. An empty stage is a result and is recorded as one. A stage that cannot finish stops the circuit with `BLOCKED` and the missing fact named, rather than passing a partial result forward with a note to be careful.

Found while wiring it in: the callout check asserted "the complete 14-key map" from a hardcoded literal, so adding a fifteenth row left it asserting a number that had stopped being true -- and passing. That is how the previous key shipped half-rolled-out across 70 documents. The count is read off the table now, and it FAILed all 70 callouts the moment the row existed, which is the behaviour the literal could not produce.

And one defect recorded rather than smoothed: the derived count first read `rfc_path`, a name bound hundreds of lines below its use, and the NameError took the entire callout section down SILENTLY -- zero FAILs, no output. A worse failure than the false PASS it replaced, and the second occurrence of row 118's invariant in a single session.

audit_checks 149 -> 150 standing controls. CONFORMANCE 237.

## 7.192.0 -- 2026-08-05 -- T-491: Lazy Load Index
Added `saipen/INDEX.md` as the table of contents and updated `BOOT.md` to reference it instead of directing agents to blindly read the full 120KB+ protocol. A cold agent can now complete a ticket reading < 50KB of rules total.

## 7.191.0 -- 2026-08-05 -- the constitution reaches installed homes again, and saitest joins the crew

T-495 (P0): the RFC split shipped the constitution out of every installed agent home. T-488 moved section 1 into `CORE.md` and section 2 into `MAINTENANCE.md` and left `RFC.md` a three-line stub, while both injectors and the runtime manifest still copied `RFC.md` alone. Every home injected after that commit received three lines and no rules -- no phase table, no `WAIT:` categories, no Pick Rule. `_read_rfc` handles the split correctly when both files are present, which is exactly why the repository looked fine: the defect only exists where the files are absent. The injector probes are the only reason it was visible, because they run the INSTALLED validator against a real flattened home. Third occurrence of the install-layout blind spot.

T-496: the same split left 24 red controls anchored on a file that no longer holds their text, so 17 percent of the harness silently stopped being evidence -- each mutation changed nothing and reported SKIP. Two others went FAIL because the validator's own sweeps still read only the stub, meaning those checks had quietly stopped covering sections 1 and 2 at all. Every case is repointed at the file that now holds its anchor, chosen by testing membership rather than guessing; audit_checks goes from 25 not-evidence to 1.

T-493: a shortcut reached the routes map and the command surface but not the 70 documents that advertise it. `tt` was added to the table, the command list and the route map while every locale README, every guide, the root mirrors and `SKILL.md` still said 13 keys -- the tree FAILed 72 ways until someone finished the rollout. A shortcut addition is a 74-file edit, not a 3-file one.

T-494: a future-stamped LOG line had no sanctioned repair. The rule FAILed a stamp more than five minutes ahead and named no way to clear one, so the only precedent was to wait -- affordable at eleven minutes, not at E-2053's 142, where it holds every gate red while asserting work happened at a time it had not. Restamp to a defensible bound, append a `DEC` naming the original, the replacement, and that the minute is inherited rather than measured.

T-492: `saitest`, the adversary subSaipen. `saipen test` (`tt`) runs the suite a project declares; nothing authored the runs nobody wrote. saitest invents them across seven closed scenario families -- input abuse, boundaries, order and repetition, hostile environments, resource pressure, damaged state, adversarial content -- and returns one of exactly three verdicts: REPRODUCED with the minimal case, NOT_REPRODUCED with what was tried, BLOCKED with what was missing. Read-only toward the project like every sub, so the deliverable is a reproduction and never a fix. Built entirely from mechanisms that already exist: no new command verb, no new phase, no new field.

CONFORMANCE 236.

## 7.190.0 -- 2026-08-05 -- the wiki mirror is checked by ID, and three controls that could not go red

T-400: W-027 reported 180/180 with zero drift while rows 117-168 of the wiki Scenarios page carried titles belonging to other IDs. The page had been built by POSITION, so equal row counts read as equal meaning and the report was confidently, specifically wrong. Counting proves nothing about which invariant a row names.

The drift itself was already gone when this was built -- rows 118, 130, 150 and 168 match their canonical invariants, because a later refresh rebuilt the page by ID mirror. What was still missing is the half that matters: the guard that stops it recurring. The page carries the digest of the canonical id-to-title map it was built from, over the ID RANGE it claims to cover, so adding new canonical rows below that range never invalidates it while editing a mirrored row's title always does. The range gap is reported separately rather than folded in, because "intact but 17 invariants behind" and "a mirrored row moved" are different facts and a reader needs to know which one they hold. Deliberately not a semantic comparison: nothing here can judge whether a paraphrase still means the same thing, and a checker pretending to would be a fresh false PASS of exactly the kind this closes.

Three broken controls came out of running the harnesses rather than reading them. The shortcut-memory-ban case mutated `Do not copy the table here` while the validator tests for `a second copy drifts` -- different strings in the same paragraph, so the mutation landed, the check stayed silent, and the case shipped as coverage. `BOOT.md`'s own wording had wrapped that anchor across a line break, so a second case reported SKIP for a literal that no longer existed on one line. And this session's new wiki check read `conformance_path`, a name bound further down the file, crashing the validator with a NameError in every scenario run while passing on the live tree where execution happened to reach the assignment first -- literally row 118's own invariant, which did not catch it.

Also: `STATE.md`'s `saipen_home` had lost its escaped backslashes to an unquoted rewrite, which orphaned another control. Restored.

audit_checks 145 -> 148 standing controls. CONFORMANCE 234, 235.

## 7.189.0 -- 2026-08-05 -- HABITS.md, the read-to-the-end invariant, and parser repairs
### Added
- Added saipen/HABITS.md enumerating statistical LLM habits and mapped them to protocol limits
- Added RFC 1.11 invariant 'Read to the end, never truncate' to combat board-empty auto-transitions
- Added saipen/HABITS.md to exempt list in tools/validate.py

### Fixed
- Fixed STATE.md and LOG.md parsing edge cases related to quotes and timestamps
- Restored BOARD.md structural integrity broken during automated string replacements

## 7.188.0 -- 2026-08-04 -- a new section names the defect class it eliminates, or it does not get written

T-420: one question with a yes-or-no answer -- what can a conformant agent do today that this text makes non-conformant tomorrow? No answer means no section. Prose that eliminates no defect costs every agent that reads it forever and implies coverage that does not exist, which is worse than silence: the next reader stops looking for the check that was never there.

Three shapes fail the question and all three are common in this repository. A restatement of a rule that already exists somewhere else -- most of RFC's own history, and the reason so many CONFORMANCE rows record two copies disagreeing. An explanation of why a rule is good rather than what it forbids. And a requirement made of a phrasing nobody reads: row 220 is the worked example, where the exact halt SENTENCE was made normative while the validator matches only the category token, guarded by a marker check and a red control that both descended from that same sentence. It lasted one release before it had to be narrowed.

No byte cap ships with this, and the reason is stated so nobody adds one later. `BOARD.md` has a soft cap because it is read in full at every cold start; none of these files are. `BOOT.md` is the cold-start read, RFC is reached only when a rule question arises, and `CONFORMANCE.md` is never read by a working agent at all. A cap without that cost behind it is a number to argue with, not a defect prevented -- which is exactly what this gate rejects.

Stated once in section 1.1 and cited from `phases/build.md` and `phases/add.md`, the two phases where additions actually happen. Cited, never restated: a third copy would be the first of the three failing shapes.

audit_checks 143 -> 145 standing controls. CONFORMANCE 233.

## 7.187.0 -- 2026-08-04 -- the Pick Rule stops handing Core work Core is forbidden to do

T-483: `phases/translate.md` gives 29 of the 32 languages to a dedicated saitranslate instance and tells a Core agent that finds them stale not to start grinding through them "while it's here". T-422, whose body is 28 locale guides, sat in `## TODO` passing every workability test the Pick Rule applies -- open checkbox, `needs:` satisfied, unclaimed. Two honest agents diverge there and both can defend themselves: one does the forbidden work, the other skips a ticket the rule says it must take.

Same divergence as v7.185.0's, arrived at from the other side. There the completion condition could never be met; here the performer is wrong. `## BLOCKED` answers both, and `| blocker:` must now name the owner AND the command that clears it -- for T-422 that is an `ee` run -- so the block is one somebody can lift rather than a shelf to park things on.

No new field, ticket kind or scheduling concept was added. The Pick Rule already ignores `## BLOCKED` and section 2.1 already keeps it out of the halt test, so the board still reaches `HUNT` with these tickets parked.

Known limit, the same one v7.185.0 states: no checker can tell that a ticket belongs to another instance, so nothing stops the next one being filed into `## TODO`. The rule tells an agent where to put it; the control only proves the section is honoured once it is there.

audit_checks 142 -> 143 standing controls. CONFORMANCE 232.

## 7.186.0 -- 2026-08-04 -- a stale translation next to updated source finally has a signal

T-423: `phases/translate.md` section 3 stated the duty and named the gap in the same sentence -- a stale translation is worse than none "since nothing signals they've gone wrong" -- and for 32 languages nothing did. Commit dates cannot serve: every release bumps the version badge in all 65 locale files, so they always look exactly as fresh as their source. The badge check that reports `32 locale README badge(s) match VERSION` measures the badge, not the prose, while reading like freshness.

Each locale README carries, as its last line, the digest of the English source it was translated FROM, with every `N.N.N` version string normalised to the literal `VERSION` first. That is `style_contract`'s shape one surface over: a scalar whose truth lives in another file, so the claim can be checked against evidence instead of believed. Normalising the version out is what makes it usable at all -- a digest that included it would move on every release and mean nothing, which is the same reason commit dates cannot serve. The translator recomputes and writes the marker for the locales it actually translated and no others: stamping a file nobody touched is the exact lie the marker exists to prevent.

WARN, not FAIL, and the severity is a decision rather than a default. The duty is a SIGNAL; Core edits English prose constantly and 29 of the 32 languages are subSaipen work by rule, so a FAIL would gate every Core release on a translation pass and be switched off the first time it was inconvenient -- which is how a check stops existing. A WARN that survives releases is owned by a live ticket under the existing ownership rule rather than a new mechanism.

The digest half is a HAND red-test and the row says so: an audit case cannot assert a WARN, because that harness requires the validator to exit non-zero. Three properties proven by hand -- editing README.md's prose WARNs all 32 locales by name, removing one marker WARNs that locale as unstamped, and bumping only the version badge produces nothing at all.

audit_checks 141 -> 142 standing controls. CONFORMANCE 231.

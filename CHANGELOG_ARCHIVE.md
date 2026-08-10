# Changelog -- archive

Older entries sealed from CHANGELOG.md (newest kept there). Append-only history, newest-top.

## 7.185.0 -- 2026-08-04 -- the board stops ordering work nobody can finish

T-427: two tickets sat in `## TODO` for months owning warnings that immutable history guarantees forever. T-406 owns subsaipen-never-ran, which `MANIFEST.md` makes emit until saipython actually runs; T-407 owns goal-reauth-untripped, which E-1659 put in an append-only file. Both exist so their slug has an owner under row 185, and both carry a `verify:` saying that closing them while the warning emits FAILs that same check.

In `## TODO` they passed every workability test the Pick Rule applies -- open checkbox, no unmet `needs:`, unclaimed -- so the board ORDERED an agent to take work nobody can finish. Two honest agents diverge there and both can defend themselves: one adopts the ticket and produces nothing, the other skips it and breaks the rule that the topmost workable ticket wins. That is the contradiction, and it was reproducible by reading the board.

No new mechanism was added, and the ticket's own three suggestions -- a waiver registry, a known-warnings section, a non-executable ticket kind -- were all declined. `## BLOCKED` already excludes a ticket from the Pick Rule, section 2.1 already excludes it from the halt test so the board still reaches `HUNT`, and `| blocker:` already carries the reason. What had to change was one line of the ownership check, which counted only `## DOING` and `## TODO` as live and therefore pinned these tickets to the one section that hurt. `## DONE` still does not count: that is a closure claim, and nothing was closed. T-464 moved with them for the same reason.

The ownership half of the evidence is a HAND red-test and the row says so rather than shipping a case that cannot fail. Breaking the slug on the blocked owner's line FAILs naming 61 consecutive releases; an audit case cannot reach that check, because it only fires once a slug has survived `WARN_OWNER_SPAN` releases and the harness's synthetic copy carries no release history to age against. The case was written, went not-red for exactly that reason, and was removed rather than left standing as coverage.

audit_checks 140 -> 141 standing controls. CONFORMANCE 230.

## 7.184.0 -- 2026-08-04 -- `no-publish` is a permission, not an absent git, and no ship step is half-permitted

T-463: `phases/ship.md`'s `mode: no-publish` block fused two independent facts. It called the remote steps skippable because "no remote exists to publish to", and it hardcoded `no git` into the mandatory skipped-publish LOG line -- on a host that may have a repository, a remote and a perfectly readable `HEAD`. That is a false record in an append-only file, and the next agent reading it concludes the project cannot publish at all. Whether git exists is observable: `git rev-parse` answers or it does not. Whether publishing is permitted is `mode:`. They are asked separately now, and the line carries `policy` or `no git`, whichever is true.

The worse half was an instruction nobody could follow. The block said "do step 6" and "skip the push half of step 6" in the same breath -- and after v7.176.0 renumbered the phase, step 6 both committed AND pushed. So a mode whose entire content is "do not commit, tag or push" told its reader to commit, and the reader had no legal way to comply. The release step is split: 6a is LOCAL (CHANGELOG plus the validator re-run, no repository touched) and 6b is GIT (commit, then push the branch). The mode's instructions are a per-step DO/SKIP table rather than prose with exceptions, so there is nothing to interpret.

Same error class as v7.182.0's MARKHUNT fix one phase over, where `no-git` covered a readable repository for the same reason.

The split moved the `[tag-after-branch]` anchor and that check FAILed on the first run. It was repointed at the new step name rather than loosened: it compares the branch-landed gate's position against the tag push, and a check that stops naming a real step stops checking.

audit_checks 137 -> 140 standing controls. CONFORMANCE 229.

## 7.183.0 -- 2026-08-04 -- two orphans, the habit that let them in, and a closed root

The user spotted `.saipen/_scen_cand.md` by its name and was right about it: a leftover. A 194-row snapshot of the saiwiki `Scenarios.md` page, frozen at CONFORMANCE 194 while the maintained page is at 216, committed by accident in 8b8d58c -- a change whose entire subject was the Pick Rule check. A sweep for siblings found one more: `button33.wav`, an 8-bit mono WAV at the repository root, on the v7.176.0 push-failure checkpoint.

Both arrived the same way, `git add -A` in a commit about something else, and neither was referenced by any document or tool. That is exactly why nothing caught them: every cross-doc check in `tools/validate.py` works by comparing a file against something that cites it, so a file nothing cites sits outside all of them, and the stale scenario table could have been read as truth by any agent grepping for one. `.gitignore` already carried three patterns added AFTER a leak -- `/nul`, the saiwiki gitlink, `settings.local.json` -- each closing one instance and leaving the class.

The root is a closed set now. `ROOT_ALLOWED` names the sixteen files that belong there, and anything else FAILs. It reads the DIRECTORY rather than the git index, which catches the file before the commit rather than months later and works where git is absent; it honours `.gitignore` when git answers; it is gated to this repository's own clone, because an installed agent home is a flattened copy whose root legitimately differs; and it excludes `.git` structurally, since a linked worktree makes that a file rather than a directory. The last two were caught by the existing harnesses on the first run, which is T-413's install-layout blind spot arriving in new code.

The sweep cleared the rest. Of 452 tracked files, the `.github/` templates, the nine adapters and the sealed LOG segments are read by convention or glob rather than by name, and the two dual-location pairs (`extensions/subs/MANIFEST.md`, `_shared/inbox.md`) are the shipped library against this project's live state -- RFC 1.9's model, not a conflict. No reorganisation was performed: nothing conflicts, and moving files with no reproduced conflict is the speculative work this protocol spends its time removing.

Two red controls were repaired rather than left standing. `demote_the_pick` demoted the topmost BOARD line and went vacuous the moment that line was an unworkable ticket -- it demotes the ticket `next_action` actually names now, which is the pick by definition. The root-set control could not go red at all while the check read the git index.

audit_checks 136 -> 137 standing controls. CONFORMANCE 228.

## 7.182.0 -- 2026-08-04 -- a MARKHUNT pass stays countable after triage, and `no-git` stops covering a readable repo

T-461: the closure rule tells a later validator or human to sum "this pass's `[MARKHUNT]` tickets" against the manifest's `findings:` count, and nothing recorded which tickets those were. The rule reads durable history while depending on a surface that legitimately changes -- the same document sends a triaged finding from `## BLOCKED` to `## TODO` with the tag and the `unvetted audit` blocker dropped, and a dismissed finding leaves the board entirely. `BOARD.md` is not append-only; `LOG.md` is. Four passes had already run here (findings=3, 12, 6, 1) and not one can be re-checked today. `tickets=` joins the completion line, `tickets=none` when a pass found nothing, and triage or dismissal LOGs a `DEC` naming the ticket and the pass event.

The pass identity the ticket asked for needed no invention: the completion line's own `E-###` is already unique, monotonic and immutable, so two passes with overlapping findings are separately reconstructable by construction. No ID scheme, no registry, no ticket field. Known limit, stated: the check enforces that a list exists, not that it is complete -- no checker can tell a short list from an honest one.

T-462: two faults in one clause of the manifest check. It named `mode: no-publish` as a case where the hashes are the literal `no-git`, but RFC 1.3 makes that a PUBLISH capability -- commit, tag and push are blocked while `git rev-parse` answers exactly as it always did, so writing `no-git` there mislabels the host and switches the tree-movement check off on a repository whose HEAD is sitting right there. And where git really is absent, both ends reading `no-git` was declared "satisfied automatically, nothing to compare": a check reporting success for the one case where it measured nothing, and doing so precisely where movement is most likely, since an exhaustive pass can span sessions while files change underneath it.

No fingerprint mechanism was invented for the git-less case. There is no cheap deterministic surface to compare, so the closure is LOGged carrying `tree_movement=unverified` and any vector whose covered paths are believed to have changed is re-run. An honest unproven closure beats an automatic pass, because the next reader can tell which one they are holding.

Both tickets edit the same three files, so each was verified in its own isolated worktree carrying that ticket's hunks alone -- 134/134 controls for the accounting half, 135/135 for the no-git half -- and one green run over the pair would have been evidence for neither.

audit_checks 133 -> 136 standing controls. CONFORMANCE 226 and 227.

## 7.181.0 -- 2026-08-04 -- the seat is derived from the agent home, not chosen

T-456: section 1.4 gave `agent:` a definition and left the one question that made the definition usable unanswered -- where a first value comes from. INIT cannot inherit a name that does not exist yet, and "write your own seat name" is a free choice. This repository's own history is what that costs: claude-opus, claude-sonnet-5, opencode, antigravity, antigravity-gemini, gemini-pro -- six names for two or three actors, four of them naming a MODEL rather than a seat.

The source is the agent home the protocol was loaded from: take that directory's own name, strip a leading dot, lowercase it. `.claude` to `claude`, `.codex` to `codex`, `.config/opencode` to `opencode`. `BOOT.md` already resolves that path to find the phase docs, so the value costs no new lookup and there is nothing to remember or invent. Every property 1.4 needs falls out of it -- deterministic per tool and machine, stable across model upgrades because the home does not move when the model behind it changes, distinct between real actors because two tools read from two homes, and observable because it is a directory rather than a self-report.

A model build name is never a seat, and that is now mechanical rather than behavioural: a value carrying a model-family token from a closed list FAILs. It caught the session that wrote the rule, whose own STATE read `claude-opus`; renamed to `claude` with the `DEC` 1.4 requires. Matching is on the closed list rather than on shape, because digits or hyphens would fail ordinary tool names.

Two things are stated rather than papered over. The degraded path: no agent home identifiable means the platform's canonical name plus a `DEC` recording that it was self-reported, so the one case a checker cannot distinguish is at least visible in history. And the known limit: two sessions of the SAME tool derive the same seat and are indistinguishable -- which is the concurrency case the Concurrency boundary already puts outside Core's envelope, and the parallel-session damage this repository actually recorded at E-1863 was two different tools, which this does separate.

One audit case was dropped rather than repaired: it anchored on `phases/init.md`'s "what this does NOT do" clause, which the derivation superseded. The harness reported it as not-evidence instead of letting it sit there looking green.

audit_checks 132 -> 133 standing controls. CONFORMANCE 225.

## 7.180.0 -- 2026-08-04 -- the prepare record names its producer, and `dd cc` stops being a dead pair

T-460: `phases/prepare.md` fixed the completion event as `RUN: prepare -> done` and the failure event as `RUN: prepare -> FAILED <reason>` -- the same two strings for `saitranslate`, for `saiwiki`, and for an unqualified main-project package. A cold agent or `saipen status` reading `LOG.md` could not tell which handoff had become ready, and two prepares of different producers were indistinguishable rather than dedupable. The evidence that the shape was wrong is in this repository's own history: both live prepare events read `RUN: prepare saiwiki -> done`, agents writing the producer in by hand against the phase doc's own fixed format. `<producer>` is required now, with the literal `unqualified` when none was requested. The source revision is deliberately NOT duplicated into the LOG line -- the handoff's own `source_head:` carries it per producer, and a second copy in an append-only file goes stale against the one that refreshes. The check is a FAIL rather than a WARN because the repository holds zero unqualified records to grandfather, verified before the severity was chosen.

T-480: two findings, one from a user transcript. Row 217's OBEY step shipped saying several commands in one message run in the order written -- ordering stated, disposal not -- so a second command whose preconditions are not met had one honest-looking outcome: answer it in chat and forget it, which is the same loss OBEY exists to stop, one command later. Such a command is now recorded before the session ends, in `next_action` when it will be legal at the next continue or at the top of `## TODO` when it will not.

And `dd cc` was dead by construction. Bare `dd` is Proposal Mode, which ends at `phase: DONE` with `goal_mode: false`, and a bare goal key at `goal_mode: false` is not a command at all -- so the shortcut table invited a combination that could never complete, row 207's defect at the level of a PAIR instead of a row. The carve-out is a pair, not a loosening: a bare goal command standing in the SAME message immediately after a plan command starts the plan that command just wrote, `goal_mode: true`, counters from zero, and the `PLAN` it follows is that run's wave 1 counted once. Bare `cc` alone is unchanged, because what the ban guards against is E-1468 -- a lone key typed out of habit mid-run handing itself a fresh 3-wave/20-ticket budget for an objective nobody stated -- and a key pressed immediately after asking for a plan has its objective sitting on the board.

Both T-480 clauses are STRUCTURAL_ONLY and CONFORMANCE 224 says so: nothing here dispatches a shortcut, so no fixture can witness a command being dropped or a pair completing.

audit_checks 129 -> 132 standing controls. CONFORMANCE 223 and 224.

## 7.179.0 -- 2026-08-04 -- a compound defect gets a compound fixture, and HUNT stops reading a cap as permission

T-457: `tools/audit_checks.py` mutates ONE file per case, so a validator condition whose trigger spans several files cannot be red-tested there -- mutate `STATE.md` alone and the board still disagrees, mutate `BOARD.md` alone and `next_action` is still legal, and every single-file attempt goes not-red, which reads exactly like a passing control. The route did not have to be invented: a `tests/scenarios/` fixture constructs a whole `.saipen/`, which is what a compound state is. `done-wait-deadlock-goal-mode/` is the worked pair for the branch that had only a hand red-test, and restoring the old `goal_mode is not True` exemption makes ONLY that fixture stop failing while its twin is unaffected -- targeted cause, not incidental red. Sweep result: that branch was the one unowned multi-file condition.

Also from T-457: an `expect: fail` fixture with no `expect_fail_contains:` line is a FAIL now, not a WARN. Unpinned, it asserts only that something somewhere went wrong, so any unrelated failure scores it green. All eleven existing fail-fixtures already carried the pin, so it migrated nothing -- and it caught a real one on its first outing, a fixture left unpinned by this session's own hand red-test.

T-458: HUNT's "obvious junk -> delete free, capped at 5" read a quantity limit as an authorization. RFC section 1.1 permits an unconfirmed destructive operation only when the active ticket pre-authorizes it AND it is reversible, and HUNT routinely runs with no active ticket, so the pre-authorization half was simply absent. "Obvious" is a feeling about a file, not a property of it. Deletion without asking now needs a named proof of recovery -- tracked at HEAD, or regenerable by a command named at the time -- and the cap survives unchanged as the mass-deletion gate it always was.

T-459: the clean-result cache was keyed on `git rev-parse --short HEAD`. A commit hash says nothing about tracked files edited since or untracked files added since, which is most of a live session because work commits at SHIP rather than per checkpoint. The document argued against itself, rejecting mtimes as insufficient three paragraphs from where its own key ignored every uncommitted byte. Reuse now also requires `git status --porcelain` to print nothing: fails safe, no fingerprint machinery, and gitignored noise is already excluded.

Both HUNT tickets are STRUCTURAL_ONLY and CONFORMANCE 222 says so rather than dressing it up -- nothing here executes a sweep, so no fixture can witness a deletion that did not happen. Each was verified in its own isolated worktree carrying that ticket's hunks alone, because the two edit the same three files and one green run over the pair would be evidence for neither.

Correction to v7.178.0, recorded rather than defended: `tests/scenarios/proposal-mode-halt/` shipped described as "the behavioral half". It runs the validator against a state and proves the halt is admissible, which is a STATIC_STATE_SCENARIO; it does not exercise continue then pick then SCOUT, and no fixture here runs an agent.

audit_checks 126 -> 129 standing controls. CONFORMANCE 221 and 222 added, 209 and 220 amended.

## 7.178.0 -- 2026-08-04 -- Proposal Mode can write down its own halt, and two rules got smaller after a provenance check

T-455: `phases/plan.md` step 4 ordered `phase: DONE` plus a halt, forbade a `WAIT:` prefix as "a violation of RFC section 1.2", and forbade proceeding to `SCOUT`. That leaves only the four prefixes that each mean "do this now", so the one halt the bare `saipen plan` command exists to produce was recordable only as an action the agent was forbidden to perform -- and a cold agent reading `PHASE SCOUT T-###` executes it. There is no parked `PHASE`. The prohibition was wrong on its own terms too: section 1.2 restricts `WAIT:` to three fixed forms at `DONE` only when `## TODO` is EMPTY, and Proposal Mode has just filled it.

The fix got smaller after a provenance check the user asked for. The first draft made the exact halt SENTENCE normative and guarded it with a marker check and a red control -- both descendants of that same sentence, while `tools/validate.py` reads only the category token `user brake` and nothing past it. Normative now: the category, and the ban on recording a `PHASE` nobody executes. The reason clause is for the human. `tests/scenarios/proposal-mode-halt/` is the behavioral half, because a marker proves a sentence is still in a file, not that the state validates.

T-479: `agent: none` was ordered by `phases/init.md`, shipped by `extensions/templates/STATE.md`, and accepted by the validator, so every project ever bootstrapped was born with an identity section 1.4's own comparison cannot use -- one side undefined fires both ways, a false alarm on a renamed seat and a missed one on two actors sharing the value. Unlike `<name>` it reads as a deliberate answer, which is why it outlived four placeholder sweeps. It is rejected now, and the shipped template must carry a value the live checks refuse so the field cannot survive as-copied.

What that does NOT do is derive a first seat name, and the docs say so out loud. "Write your own seat name" is the same free choice that put six names in this repository's history for three actors; formalising it through schema plus validator would have dressed the gap as a rule. T-456 stays open on the deterministic source alone. CONFORMANCE 148 was amended rather than given a new row -- this narrows an existing check, and a row per narrowing is how a table stops being readable.

audit_checks 123 -> 126 standing controls; one of the three was caught not being evidence by the harness before it shipped, mutating the template to a value that had just become a placeholder. CONFORMANCE 220 added, 148 amended.

## 7.177.0 -- 2026-08-04 -- the user's command outranks the pre-computed pick, and three red controls that were never evidence

T-474: § 1.11's action-priority list had no entry for the commonest event in a live project -- the user naming a command. `BOOT.md` step 7 ordered `next_action` executed immediately, § 1.10 ordered a declared shortcut executed as the exact row it resolves to and never answered as a greeting, and nothing said which won. Two live MUSTs, no precedence, and at a cold start `BOOT.md` is the file an agent reaches first, so the newest fact in the session lost to the oldest. It cost the same key twice: a bare `qq` went to a stale `PHASE SCOUT T-455` at E-1913, and a second agent's session lost it to the same pick again, recovering only because the user asked about it directly. `OBEY` sits below `RECOVER` -- every command's first act is reading the state it would run against -- and above `UNBLOCK`, which exists to stop the AGENT finding its own work, not to outlast the user. Inserting it moved three of five step numbers, so every cross-reference into the list now names the step rather than its number.

T-477: two shipped rules left no legal state between them. Row 213 keeps a passed ticket in `## DOING` through SHIP and closes it only after the push lands; the row-citation check FAILed any CONFORMANCE row citing a ticket not in `## DONE`. So a ticket whose work adds a row could not validate at all between BUILD and the post-push close -- the pre-commit hook runs the validator, the row cannot land before the ticket closes, and the ticket cannot close before the push. Hit on the first row written after row 213 shipped. `## DOING` is exempt now; the defect the check was built for had both its tickets in `## TODO`.

T-478: three red controls reported green while testing nothing, and the harness that exists to catch that could not see any of them. Two carried a literal `\x01` byte where the regex replacement wanted the backreference `\x01`, so each mutation swapped the whole ticket line for a control character and the validator FAILed on shape rather than on `phases/verify.md`'s cap -- invisible to ruff and to the doc text lint, because the file is valid UTF-8 and valid Python. `tools/validate.py` FAILs a C0 byte in any shipped `tools/*.py` now. The third mutated `STATE.md` only, and the pick check skips its comparison whenever anything sits in `## DOING`, so it stopped being evidence exactly while the repository was working; it mutates `BOARD.md` now and goes red from both board states.

T-475: the `gg` row promised the outcome CONFORMANCE 207 had just proved that destination cannot produce -- one row above the row that got repaired, because the check named `cc` by key. The requirement is derived from the route column now, so a third row assigned to `saipen goal` inherits it instead of escaping by not being named.

T-476: a `WAIT:` body is one sentence. The category token bounds what KIND of stop it is and bounds nothing after it, so `next_action` became a scratchpad -- and this repository's own live state carried a `user brake` that ran three sentences of handoff status and finished by naming a ticket as still open "for a future run", after which the next agent scouted that ticket instead of honouring the brake. Session status belongs in `.saipen/kitchen/digest.md`, queued work belongs on `BOARD.md`.

audit_checks 118 -> 121 standing controls. CONFORMANCE 217-219, with rows 47, 172 and 199 corrected in place.

## 7.176.0 -- 2026-08-03 -- the first-publish gate runs before the push, HUNT can be entered, and the MARKHUNT brake has a wording

Three protocol self-contradictions, each one a phase doc against the constitution rather than the constitution against itself -- the half the previous wave did not read. T-452: `phases/ship.md` cleared the first-publish confirmation at step 7, after the branch push at step 5 and the tag push at step 6, with its own `WAIT:` text reading "before I push" about a push two steps behind it. On the one run that gate exists for, the one-way door opened before the user was asked; with no `origin` at all the push simply failed first and fell into generic push recovery, which never asks. Remote classification is step 5 now, decided while everything is still local, re-read immediately before each external write.

T-454: `saipen hunt` is recognised from any phase (§ 1.10) while `HUNT` sat outside § 1.6's from-any-phase set, so the DFA's only route in was `DONE -> HUNT` and invoking the command from `BUILD` produced a transition the validator rejects -- the same two-halves disagreement CONFORMANCE 61 records for `SHIP`. § 2.1 compounded it by phrasing the halt as a precondition on the phase rather than on the autonomous transition, and `phases/hunt.md`'s hash skip had no carve-out, making the one command whose purpose is forcing a sweep a documented no-op on an unchanged tree. A fourth copy fell out with them: § 1.2 restated the set as "the five user-command phases", already missing `PLAN` before `HUNT` joined.

T-453: the MARKHUNT brake had no legal way to exist. `phases/done.md` and `phases/markhunt.md` both held that untriaged findings stop the auto-proceed to `HUNT`, while § 1.2 whitelisted two `WAIT:` forms at `DONE` with an empty `## TODO` and § 1.11 ordered an agent to ignore any third -- and `KNOWLEDGE/traps.md` defended the brake by claiming such a board "has not halted", contradicting § 2.1's own definition. § 1.2 carries the third fixed wording now. Two validator exemptions died with it: the deadlock check was switched off entirely under `goal_mode: true`, the one mode where an unattended run parks on a WAIT nobody was asked.

New: `tools/autoinject.py` (T-465). The injector copies rather than links, because the readers that matter ignore junctions, so every installed agent home drifts silently after a pull and the standing rule for it was a sentence nobody could check. It digests the shipped surface, stamps each home with what it actually received, re-injects only on a real content difference, and prints version, HEAD, drift, phase/task/next_action, board counts and the validator line. It never pulls: this clone carries uncommitted in-flight work by design.

audit_checks 101 -> 104 standing controls. One control was removed rather than left standing: the goal-mode deadlock branch needs an empty `## TODO` and a bogus `WAIT:` together, an audit case mutates exactly one file, and every single-file attempt proved nothing. It is hand red-tested and CONFORMANCE 209 states that as a limit instead of claiming coverage. CONFORMANCE 209-211.

## 7.175.0 -- 2026-08-03 -- five contradictions the constitution had with itself, each one now carrying a witness

A maintenance wave read the protocol through five layers -- cognition, execution, memory, governance, observability -- and closed what each turned up. Governance: § 2.1's ZERO-PROMPT rule is a MUST that named one exception while § 1.3 bans `ADD` outright under `mode: read-only`, so a read-only agent on a clean HUNT was ordered into a phase it may not enter and both rules looked followed on their own; the list now declares itself complete and names the carve-out (T-437). Memory: § 1.2's legacy-upgrade sentence -- the single instruction for escaping legacy state -- said "MUST upgrade to v2" for as long as the schema had been at 3, so obeying it produced state the validator WARNs as legacy on the spot. It names no number now, and the new [stale-schema-version] sweep found the defect it was written for on its first run: the shipped subSaipen TEMPLATE was frozen at `schema_version: 1`, so every `saipen sub spawn` ever run was born legacy (T-436).

Observability: § 1.10 has ordered `saipen status` to report "the result of the last `tools/validate.py` run if one is recorded in `LOG.md`" without anything ever giving that record a shape, so the report either grepped prose and guessed or truthfully answered "none recorded" over a LOG holding the answer. § 1.2 now fixes `RUN: validate.py -> PASS` / `-> FAIL`, the same argument § 2.4 already won for `DEC: goal_waves N->M`; this repository tripped the new warn on its own 1800-plus events (T-438). Execution: CLEAN's board scrub pruned `## DONE` with no inbound-`needs:` guard, so the phase whose job is keeping the board honest could orphan a live dependency and block a workable ticket -- found by executing the rule rather than reading it, when a live prune dropped T-421 and T-422 dangled on the next validation (T-440). Cognition: the `cc` row's Notes promised a Goal Mode pivot its bare form is forbidden to perform (T-439).

`tools/audit_checks.py` 91 -> 101 standing red controls. Two of them broke when `LOG.md` crossed its cap and sealed into `LOG-007.md`, carrying their anchors out of the active log -- caught, re-anchored, and the misleading SKIP message that blamed a missing file corrected. CONFORMANCE 204-208.

## 7.174.0 -- 2026-08-03 -- the phase/ref pairing is witnessed, the goal budget is conditional, and every locale README grew a Commands table

Two tickets closed the loop on rules the validator never watched. `PHASE <phase> [T-###]` pairing: RFC § 1.2 requires the ticket ref on exactly SCOUT/BUILD/VERIFY/REVIEW/SHIP and omits it everywhere else, and RFC's own § 2.2 example taught the violation until T-435 corrected it and shipped the witness both directions (validate.py FAILs a ref on PLAN and a bare PHASE BUILD; audit_checks 95/95). The goal budget: § 1.10's `saipen stop` paragraph claimed bare `saipen goal` resets the counters unconditionally while § 2.4 Entry resets them only at/over the caps -- T-434 deferred the claim to the section that owns it and the [goal-counter-reset] check now FAILs if the conditional clause goes missing.

Translation surface: the Core-owned README family (ru/et/ded kitchens, README.ee.md/README.ded.md mirrors) restructured to the v7.172.0-era outline -- How it works, a full 16-row Commands table, a Documentation table, Built with SAIPEN -- and README.ee.md got its language switcher back. Palette name unified to Vintage Golden. 29 locales remain on the old outline, ticketed SAIT-009 on the saitranslate sub board.

## 7.173.0 -- 2026-08-02 -- the LOG clock is read, not estimated

The forward bound on a LOG timestamp was 3 hours, and in the whole life of this protocol it caught nothing. That is not because agents keep good time -- it is because nobody misses the clock by hours. They miss it by twenty minutes, because reading the clock costs a tool call and writing a plausible minute costs nothing, and a plausible minute is what a language model produces when it is not stopped.

Caught here on the author of the two releases before it: E-1788..E-1793 were stamped up to 37 minutes ahead of real UTC and every line was green. Those stamps are still in the LOG, because append-only means they stay as the evidence.

The bound is 5 minutes now -- the same slack the backwards-drift check already allows, standing for the same thing, clock skew between machines. Past that, the stamp was invented rather than read, and the ordering a § 1.5 Recovery rebuild reads off these stamps is fiction. The FAIL message carries the exact command that answers the question, because the failure being corrected is estimation, not ignorance.

This is the same class the future-tense LOG gate closed one release ago, one field over: a line claiming a moment that had not arrived yet.

## 7.172.0 -- 2026-08-02 -- the CI-status hook ships with the tool it calls

Generation 4 of the pre-commit hook asks GitHub what the last workflow run for the branch was, and says so when it is red -- the active counterpart to a badge nobody is forced to look at, written after this repository's own CI sat red for 30+ commits while every local gate stayed green. It was wired to an UNTRACKED `tools/ci_status.py`: present on the machine that wrote it, absent from every clone. That is the v7.166.1 manifest defect one layer up, and it is why the tool sat undecided rather than shipped.

Shipped now, with four quiet failures closed. A missing `ci_status.py` is skipped by the hook's `-f` guard instead of leaking an error into every commit. The branch query asks for COMPLETED runs -- without that the newest run wins even while it is still queued, and the RED run underneath is never looked at, which is exactly the moment someone is committing on a red base. The cache path is resolved through git, because a linked worktree's `.git` is a FILE and the literal path can only fail to write, silently spending one of the 60 unauthenticated requests per hour on every commit made there. An unreachable API exits 0 in silence.

Warn-only in both directions, and now the docstring, the hook comment and the behaviour all say it: a red CI must never block the commit that fixes it, and a network hiccup must never block any commit at all.

Seven probes, all offline. Three drive the tool in-process with a stubbed network; four run the real installed hook under dash, including one where `ci_status.py` exits 1 loudly and the hook must still leave the commit at exit 0. The tool is in the runtime manifest, which FAILs on an untracked entry, so the dependency cannot go local-only again.

## 7.171.0 -- 2026-08-02 -- a completion claim carries its evidence, and a LOG line stays in the past tense

Three gaps, all of them ways a claim could outrun what actually happened.

A LOG entry could be written in the future tense and nothing stopped it. `RUN: will ship the release` and `RUN: ship the release -> pushed abc1234` read identically to everything downstream -- RFC § 1.5's Recovery rebuild, an audit, the next agent's cold start -- so a line written ahead of its own work manufactures completion at the moment it is appended, and append-only means it can never be withdrawn. The gated span is the text's FIRST CLAUSE, up to its first ` -- `, ` -> `, `; ` or `. `: that is where a line states what its event WAS. Later clauses may still name a future that is not the writer's own claim, such as a ticket's pending content. Measured across all 7 sealed segments, the active log and 4 subSaipen logs before shipping: zero first-clause hits, so the gate starts clean rather than inheriting debt. FAIL in the active log, WARN in sealed history -- the same severity split the DATE check already uses.

`## DONE` required no `verify:` field. Moving a line into that section was by itself enough to make the board assert a proven result, and this repository did exactly that at E-1767: a ticket went DOING -> DONE with "no verify -- not built work" and every gate stayed green. Closing a ticket without building it is still legal -- superseded, withdrawn, decided away by the user -- but it has to say so in the field now. Presence only: the field's content is evidence for a human to weigh, and a checker pretending to grade it would add a claim rather than remove one.

A CONFORMANCE row could ship citing a ticket that had not been done. The row asserts an invariant is enforced NOW and names the ticket that landed it; nothing compared that against `BOARD.md`. Reproduced verbatim while writing this release: rows 193 and 196 cited T-419 and T-426 with both still in `## TODO`, their code already sitting in the working tree, and no LOG event for either. That makes this check the only mechanical witness the protocol has for the wider failure behind it -- work landing with BOARD and LOG untouched, which nothing can detect in general, but which surfaces here as two shipped documents contradicting each other.

Also: the reply-language guard now covers every document a new reader lands on -- the four root entry READMEs and all 32 locale copies, 36 in total -- instead of the three Core writes by hand, and FAILs if fewer than the four always-present root documents resolve, so an empty candidate list cannot pass by reading nothing.

## 7.170.0 -- 2026-08-02 -- the validator stops reporting on a tree nobody edited

Root resolution asked the git-common main worktree before the active one. A linked worktree carrying its own `.saipen/` was therefore never consulted: a local `STATE.md` reading `phase: NOT-A-PHASE` validated EXIT=0 and named the main repository. Honest output, invisible consequence -- green about a tree the agent was not editing.

The active worktree is asked first now. A linked worktree with no `.saipen/` of its own -- the normal case, since the folder is gitignored and a fresh worktree starts without one -- still falls back to the shared state, so the design that made worktrees usable is intact. Only a deliberately created local `.saipen/` changes the answer, and then it is the right answer.

Both controls run against real worktrees in `tools/run_scenarios.py`: an invalid local state must FAIL and name the linked root, and a worktree without `.saipen/` must keep using the main owner.

One control caught its author. The first version of the new probe mutated `phase: PLAN` in a fixture that says `phase: BUILD` -- a silent no-op that passed a mutation it never applied. That is the exact defect class `tools/audit_checks.py` exists to catch, committed by hand inside the harness.

## 7.169.0 -- 2026-08-02 -- the pre-computed pick is checked against the rule that computed it

`next_action` IS the Pick Rule's answer, written down in advance, and nothing ever checked it. This repository's own board carried `PHASE SCOUT T-417` under four newer tickets and validated clean: filing a ticket at the front of `## TODO`, which RFC section 1.10's `dd <text>` contract requires, silently invalidates a pick written earlier. A cold agent executes the stale one and believes it followed the rule.

The named ticket must now exist, sit in an executable section, have every dependency DONE, not be another agent's claim, and be the topmost workable one -- five conditions, one diagnostic each, no silent repair.

The new check immediately broke the warn-ownership probe, which filed its synthetic ticket at the front of `## TODO` and so invalidated the state's own pick. It appends at the end now: it tests warning ownership, not board order, and a fixture that fails for a reason it does not test is exactly what this repository keeps catching in itself.

Two smaller things. The default language set is fixed at six -- English, Russian, Estonian, Ukrainian, Japanese and Дед -- and the guide-opening contract covers all six rather than the four Core writes by hand; Дед is not a bonus voice, caveman+Дед is SAIPEN's own style. And `.claude/settings.local.json` is gitignored: an untracked per-machine allowlist carrying `Bash(rm -f *)`, in a repository where `git add -A` is routine.

## 7.168.0 -- 2026-08-02 -- guides open with why, not with what

Guides were filed under Artifacts, whose rule is "professional, plain, boring on purpose". So they opened by naming the problem in the reader's own jargon -- "your AI agents remember nothing" -- which lands only if you already know what an AI agent is. The reader who does not is exactly the reader a guide exists for, and they stopped at line one.

`STYLE.md` gives guides their own surface now: open by saying why the thing exists, starting further back than feels necessary, for someone who does not know the domain. Tone is not machine-checkable. Structure is, and it is the half that matters: the first paragraph after the title carries no command, no path, no fence. Mechanics come after the hook.

The five Core-owned guides (en/et/ru/Дед) were rewritten to it. The other 28 are saitranslate's, ticketed as T-422 -- the point there is the same reader, not a literal translation of the English hook.

## 7.167.0 -- 2026-08-02 -- the default says its own name now

`reply_language:` ships as `et`, so someone who clones this and writes English gets Estonian back. That is the setting working. It also reads exactly like a broken tool, because nothing on the way in mentioned it and no reader has a reason to suspect one line in `STYLE.md` is the fix.

`README.md`, `README.ee.md` and `README.ded.md` now say it in their first screen: the default, the four values, the file, and the fact that nothing else about SAIPEN is Estonian -- protocol, code, commits and every document stay English at every value. The validator requires all three to name the setting, and the red control strips that name out of one of them, removing the reader's only pointer rather than reweighting prose.

`README.ja.md` and the 32 locale copies are saitranslate's, ticketed as T-419 rather than machine-translated here.

## 7.166.2 -- 2026-08-02 -- the ledger probe's repository was not a repository

v7.166.1 required every runtime-manifest file to be tracked by git. The release-ledger probe in `tools/audit_checks.py` builds its synthetic repository with `git init` and a single EMPTY commit -- so nothing in it was tracked, and the fixture failed for a reason it does not test. Caught by CI on the very commit that added the requirement, which is the first useful thing the red CI has done all day.

The probe now commits the tree it copied. A synthetic repository has to resemble a real clone in every way the validator can see, or it is testing the harness rather than the rule.

## 7.166.1 -- 2026-08-02 -- the manifest listed a file no clone had

CI had been red since v7.164.0 while every local gate stayed green, and the reason is embarrassing in the useful way. `tools/validate.py` carried an uncommitted working-tree edit when v7.164.0 was prepared -- one runtime-manifest entry naming `tools/ci_status.py` -- and the release committed the whole file. The tool it names was never committed. Locally the manifest check found the file on disk and passed on every commit; every clone, CI included, got a home missing a runtime file and failed on every run.

The entry is gone. The check that let it through is what actually mattered: completeness tested `is_file()` against the working tree, and an untracked file satisfies that permanently on the machine that created it. Manifest entries must now also be tracked by git wherever git is available -- present on this disk stopped counting as present in the repository. Homes without git keep the path check unchanged.

Its red control builds a real repository and removes one manifest file from the index while leaving it on disk, which is precisely the state that shipped. It lives in `tools/run_scenarios.py` rather than `tools/audit_checks.py` for the third time this session: that harness snapshots without `.git`, where this check correctly stands down and a control would report a green mutation.

## 7.166.0 -- 2026-08-02 -- the reply language is a setting now, and Estonian is what it ships as

Four documents carried one precedence rule: explicit user prose first, a Russian-repository tie-breaker for bare input, Estonian as the fallback. It worked, and it was unchangeable in practice -- a user who simply wanted every answer in Estonian had to edit all four documents plus the validator check that keeps them identical. A rule that costs five coordinated edits to express a preference is not a preference, it is a policy.

`STYLE.md` now opens with one bold line: `reply_language: et`. That is the whole interface. `et` means Estonian always, whatever language the message arrived in, and it is what ships. `en` and `ru` pin those. `auto` restores the precedence rule, kept verbatim rather than deleted, because it is genuinely useful and reconstructing it from memory is how it drifted twice already.

At a pinned value there is nothing left to weigh -- no detection, no tie-breaker, no repository-language reasoning -- and answering in the user's language because it seems more helpful is the violation, not the courtesy. A value outside the closed set FAILs rather than falling back: an agent guessing what `reply_language: eesti` meant answers in a language nobody chose.

The setting governs chat and only chat. Protocol, code, commits, `KNOWLEDGE/` and this file stay English at every value; it selects which language дед swears in, not which language the project is written in.

The value is validated where it is declared, and all four contract documents must now name the setting -- otherwise one of them keeps presenting the precedence rule as the whole rule, which is exactly the drift the four-copy check exists for. Three red controls: an out-of-set value, a deleted declaration, and `BOOT.md` stripped back to prose. Canonical mutations 79/79.

Editing `STYLE.md` also moved its boot marker twice during this change, on purpose and out loud -- v7.164.0's machinery working exactly as designed.

## 7.165.0 -- 2026-08-02 -- two rules that decided nothing now decide something

A sweep of CONFORMANCE's own enforcement column: 70 of 188 rows name no tool. Most are honest -- the assertion is an agent decision and no artifact records it. Two were not.

`needs:` had two guards from the start, neither of which asked the question the DAG exists to answer. Dangling references FAIL, cycles FAIL, and a `## DOING` ticket whose dependencies are still sitting in `## TODO` passed every check ever written. RFC § 1.11 itself records that two phrasings of "workable" once coexisted and a ticket with unsatisfied `needs:` passed one and failed the other -- settled in prose, while the board stayed unable to show it. Claimed tickets now have their dependencies verified against `## DONE`; `## BLOCKED` is exempt, because a blocked ticket is not a claim. The check caught this repository's own board on the way in: an agent finding filed at the front of `## TODO` had made a P2 the topmost workable ticket above two P1s.

`phases/hunt.md` allows skipping the six-category sweep only when the newest `hunt -> clean @<HASH>` matches HEAD exactly. The hash IS the mechanism -- no hash, no skip, by construction -- and nothing ever read it. The recorded incident is an agent that invented a substitute signal, was corrected, then produced the identical substitution a second time dressed as compliance. A fabricated skip has no commit behind it: unresolvable marks now FAIL in the active LOG, WARN in sealed segments that append-only history cannot correct, and the check stands down entirely where git is absent.

Its red control lives in `tools/run_scenarios.py` rather than `tools/audit_checks.py`, because that harness snapshots the tree without `.git` -- a hash check is skipped there, and the control would have reported a green mutation. An instrument measuring nothing while printing a result is the same defect class this whole sweep is about.

The 26 rows that genuinely cannot be checked now say why, one line each, and four of them dropped to partly-mechanical. Canonical mutations 76/76.

## 7.164.0 -- 2026-08-02 -- the voice contract now carries a value, so skipping it stops being silent

Three releases went into making `STYLE.md` unskippable: v7.159.0 removed the contradiction that let a live session file it under lazy rule-questions, v7.160.0 moved the read into the numbered fast path. Both fixed what the documents SAY. Neither could tell a session that obeyed from one that did not, because a read leaves no trace -- and every other required STATE field is derivable from `.saipen/` itself, so an agent that never opened the file fills its checkpoint in completely and looks perfectly conformant.

`STYLE.md` now declares a boot marker derived from its own text, and `schema_version: 3` STATE MUST carry it -- the same shape `last_event` has: a scalar whose truth lives outside `STATE.md`, so a checkpoint claiming it can be checked against evidence instead of believed. Absent at current schema FAILs, present-and-wrong FAILs, any lower revision stays readable legacy that WARNs and migrates at its next checkpoint. The token appears in no other shipped document on purpose: a value reachable from `BOOT.md` is copyable by an agent that never read the contract it stands for. Edit the contract and the token changes, which invalidates every state that has not re-read it; the validator prints the current value whenever it disagrees.

This does not prove the read. Nothing can. It removes the silence -- the duty now has a value attached, and a value can be wrong out loud.

Two existing checks turned out to be wrong, both found by their own red controls going green. The fast-path test scanned the whole numbered region, so a mention of `STYLE.md` in any later step satisfied a check about step 1; it now reads step 1 alone. And shipped docs were resolved only at `saipen/<name>`, the repository layout -- `bootstrap/inject.*` flattens that folder, so the entire cross-document contract check had been SKIPping itself in every injected install. Canonical mutations 75/75, portable-floor parity 11.

## 7.163.0 -- 2026-08-02 -- `dd <text>` is the user's request, not a prompt for four inventions

`saipen plan` is two commands wearing one name and only the bare one was written down. Section 1.10 said "explicit trigger for PLAN phase" plus a sentence about the bare form; `phases/plan.md` led with its Proposal Mode paragraph. A weak model reading either one answers a specific instruction with four autonomous proposals of its own -- a request replaced by a menu, politely.

Both documents now carry the with-text half. The text IS the work: the user's own items become tickets, reworded so a cold agent can execute them while the human still recognises what they asked for, and inserted at the FRONT of `## TODO`. Board order is priority (section 1.6), so filing a request behind existing work answers it politely and never. Anything the agent spots that the user missed goes BELOW their items, never in place of them.

The validator checks the placement rule in both documents, because that is the half a paraphrase drops first. Red control softens `FRONT of \`## TODO\`` to "front of the board" in the phase doc, so the mutation is the rule's operative words rather than a checker's wording.

## 7.162.0 -- 2026-08-02 -- the validator was more permissive than the format it validates

`saipen_home` lost its backslash doubling in commit 4012bae, so RFC section 1.7's bootloader pointer stopped being a path. A YAML reader consumes each single backslash as an escape -- and `\_` is a perfectly legal one, yielding U+00A0 -- so the pointer parsed to a value with five non-breaking spaces where five separators belong. Any agent resolving the SAIPEN home from STATE got a path that cannot exist.

It survived three releases for two reasons, and the second one matters more. `state.schema.json` types the field `string`, and corruption is a string. And `tools/validate.py` does not use a YAML parser at all: it reads the subset STATE.md actually uses, strips quotes, and never processes escapes -- so the corrupted pointer looked perfect to every check in the file while a real reader saw something else. Fourteen mentions of `saipen_home` in the validator, zero parses.

The check is therefore the escaping rule itself, with no parser and no dependency: inside a double-quoted scalar the only defensible backslash is a doubled one. The first draft of this check accepted `\_`, because YAML does -- legal, and wrong, which is exactly how the bug got in. Red control un-doubles the backslashes the way the original commit did, so the mutation is the state file rather than any wording.

## 7.161.0 -- 2026-08-02 -- warning ownership from release history

A WARN category that survives release after release is standing debt, and nothing said so. `tools/release_ledger_baseline.json` now records each tracked slug's first/last seen release and an explicit rationale; a slug still emitted this run that has outlived `WARN_OWNER_SPAN=3` consecutive releases FAILs `tools/validate.py` unless a live BOARD ticket names that exact slug. Calibrated against board-soft-cap, log-soft-cap, subsaipen-never-ran and goal-reauth-untripped; resolved slugs stay as history and re-own only if they return. A new behavioral probe ages an unowned slug in baseline DATA to prove the FAIL, then proves the identical aged slug with a live naming ticket passes; three canonical mutations red-test the baseline shape (68/68). Standing owner tickets T-406/T-407 keep the emitted warnings owned after T-401 closes.

## 7.160.0 -- 2026-08-02 -- the read is now a step, not a wish

T-404 (v7.159.0) proved the mandate EXISTS but the read itself still lived as a trailing "Anything else" bullet below the numbered fast path -- the execution order a cold agent actually walks. A weak model reads steps 1-8, executes next_action, stops; the bottom bullet is never reached. Worse, the path `<saipen_home>/STYLE.md` requires saipen_home to resolve, and an empty or dead value silently skips the read.

The read is now BOOT.md fast-path step 1: read `STYLE.md` -- the file in the same folder as this `BOOT.md` -- before any output. Self-locating, no home resolution. RFC § 1.1 pins the placement; SKILL.md reads STYLE right after BOOT, before RFC; the validator checks the fast-path region and fails loud if the section headings vanish so the check cannot pass vacuously. Three new red controls prove all three regressions (read out of the fast path, self-locating reference lost, heading renamed); all 65 canonical mutations fire and portable-floor parity stays 11.

## 7.159.0 -- 2026-08-02 -- one file, two mandates, the cheap one won

`BOOT.md` told STYLE.md two things eight lines apart: line 101 filed it under lazy "rule questions" -- open only when the phase doc fails to answer -- while line 108 ordered applying it before any output. Measured, not theorised: a live DeepSeek v4 flash session read BOOT, RFC, the phase docs and PROTOCOL.md, never opened STYLE.md, and said so when asked. It obeyed the cheaper line; T-381's red-test had proven the mandate EXISTS, never that nothing contradicts it.

The fix is structural, not louder wording. The operative caveman-дед contract now lives inline in the cold-start kernel as text, and STYLE.md stays the reference for nuance. The validator FAILs when a before-output file reappears on BOOT's on-demand rule-question list, fails loud when either anchor bullet is lost so the check cannot pass vacuously, and rejects an adapter filing STYLE.md as a rule-question escalation -- all seven adapters carried the same lazy classification. Three new red controls prove all three regressions; all 62 canonical mutations fire and portable-floor parity stays 11.

## 7.158.0 -- 2026-08-01 -- ready packages, exact keys, cleaner front door

Repeated keys are assignments now, not weak-model vibes. `ee` and `qq` prepare complete translation/wiki packages into explicit seven-field `status: ready` handoffs without touching the target or a remote. `eee` and `qqq` consume only a fresh ready package, integrate its declared payload through VERIFY/REVIEW/SHIP, and push; incomplete input is an exact no-op naming the doubled prerequisite. `cc` stays mapped to Goal Mode. The validator pins all 13 routes, rejects valid-but-wrong destinations, rejects stale global claims about doubled/tripled cost, and keeps six Cyrillic twins aligned across skill activation, 32 locale sources, mirrors, and guides. All 59 canonical mutations fire; portable-floor parity remains 11.

The README front door is now seven real sections instead of loose headings and walls of links. The full 16-command surface is a one-command-per-row table, all 33 translated guides sit in a compact details block, and the package shortcuts remain visible near the opening. CLEAN finally pruned 65 shipped tickets and sealed the 389-line active LOG as `LOG-006.md`; the board/log soft-cap warnings disappeared. The stale untracked root `saipen.wiki/` duplicate is gone; the live saiwiki kitchen clone remains the sole wiki source.

## 7.157.0 -- 2026-08-01 -- one language contract, one stubborn дед

Chat-language selection had two constitutions: STYLE defaulted a prose-free command to Estonian, while RFC and the cold-start BOOT kernel defaulted it to English. The skill discovery metadata carried neither that choice nor the rule that caveman-дед survives every response. Weak models could therefore pick whichever fragment they loaded first, drift into corporate prose later, or mistake a translated repository file for the user's language.

RFC, BOOT, STYLE, and SKILL metadata now carry one exact three-language precedence. Explicit current Estonian, English, or Russian prose wins. A clearly Russian root README plus ordinary first-party project docs may select Russian only for bare or ambiguous input; otherwise Estonian is the default, and another detected language bridges through English. Quotes, code, paths, logs, locale trees, OS/IDE locale, and platform UI are not user-language evidence. Caveman-дед remains active until explicit `stop caveman` or `normal mode`.

The validator requires both contracts on all four boot surfaces. Independent mutations remove the SKILL language marker and STYLE persistence marker, proving the checks go red; all 54 canonical mutations fire, and portable-floor parity remains at its 11-case baseline. Review also retired the old English-default guarantee and a lower STYLE sentence that contradicted the three-language fallback. The clean Windows parity run exposed a separate 544.6-second observability problem, queued as T-399 rather than mixed into this release.

## 7.156.0 -- 2026-08-01 -- device names and weak translations get guards

A real zero-byte NTFS entry named `nul`, left by an external agent or shell, made Git advertise junk and made both mutation audits abort inside `shutil.copytree` before they could print a useful diagnosis. Root `/nul` is now ignored by Git and canonical audit snapshots. A behavioral self-control creates the real extended-path device-name entry on Windows, copies the tree, and proves the ordinary marker survives while `nul` does not; the original workspace entry remains in place and no longer interferes.

The SAIT-008 translation pass reached all 32 locale READMEs, three root mirrors, and 28 non-Core guides, but its weak read-only worker wrote shared files directly and independently translated the guide half. The keys were structurally present while several sentences had missing verbs, Korean misspellings, and broken Thai. Core reviewed the output, corrected the visible HE/JA/KO/TH/TR defects, and made each locale README the single source for its non-Core guide. The validator now guards all 32 sources, three mirrors, 33 locale guides, and both root entry docs for one early callout, canonical key order, five Cyrillic twins, exact RFC targets, and source/consumer equality. All 52 canonical mutations fire; portable-floor parity remains at its 11-case baseline.

## 7.155.0 -- 2026-08-01 -- a no-op mutation is not evidence

The goal-counter recovery control wrote the literal value `7` into live `STATE.md`. Once the real counter itself reached 7, that mutation changed nothing; the canonical validator received the untouched control tree, and the audit suite still counted the case as proof that its check could go red.

The case now increments the integer it observes instead of guessing a value. More importantly, the mutation harness rejects every callable whose output equals its input before running the validator, so the same defect cannot move to another hard-coded replacement. An identity-mutation self-control keeps that harness guard capable of failing. All 50 canonical mutations still fire, and portable-floor parity remains at its 11-case baseline.

## 7.154.0 -- 2026-08-01 -- shortcuts belong at the front door

The shortcut table existed deep in RFC section 1.10 while every human entry point still taught the long command names first. README and its six directly linked guides now surface the safe core trio near the opening: `cc` continues an active Goal Mode run, `sss` reports status without touching code, and `ss` checkpoints and stops.

The callouts stay deliberately small. They link to the canonical 11-key RFC table instead of cloning it into seven documents, and name the five Cyrillic-confusable forms (`сс`, `ссс`, `аа`, `ее`, `рр`) so a Russian keyboard does not look broken. Each guide keeps its own language and voice; the shortcut semantics stay identical.

## 7.153.0 -- 2026-08-01 -- every shortcut can wake the protocol up

Skill discovery happens before an agent has read the RFC. The RFC carried eleven shortcuts plus five Cyrillic-confusable twins, while `SKILL.md` advertised only part of that set; the missing forms worked inside an initialized SAIPEN project by accident and could fail to activate the skill anywhere else. Discovery metadata now carries the full set.

The validator derives the expected triggers from the canonical RFC table and its confusable mapping, then requires exact equality with `SKILL.md` frontmatter. It rejects both halves of drift: a missing live shortcut and a stale shortcut left advertised after its RFC row disappears. Separate mutation controls prove both directions can still go red; the canonical mutation suite is now 50 of 50.

This release also carries the user's `cc` mapping to bare `saipen goal`, so the short key resumes an active Goal Mode run without resetting an untripped valve, and a skill-entry path hint that stops external installations from hunting the filesystem for protocol files. Both changes were committed after v7.152.0 and are published here with the discovery guard that keeps their trigger surface honest.

## 7.152.0 -- 2026-08-01 -- a shortcut typed in Cyrillic is the same shortcut

The user works on a Russian layout, where the visually identical letters carry different codepoints. Five of the eleven shortcuts have lowercase homoglyph twins and six have none, so the recognizer normalizes through the confusable set before matching rather than carrying a second column of aliases.

Answering "unrecognized command" to a key pressed correctly, on the layout the user actually types in, is the worst available response -- and the shortcut it hits is the most-used one. The table stays Latin: that is the canonical spelling, not the only accepted one.

## 7.151.0 -- 2026-08-01 -- a command named after a phase carries the phase switch's duty

`saipen hunt` joined the command surface in v7.148.0 and was never added to section 1.10's phase-switching list -- the closed enumeration that makes those commands checkpoint a claimed `## DOING` ticket before switching phase. For two releases `hh` was the one phase switch that could leave half-finished work unwritten. Its own definition said a claimed ticket outranks it, which orders which runs first and says nothing about writing the checkpoint; ordering and checkpointing are two rules and only one was stated.

The list is no longer hand-kept. Membership is derived from the phase docs: a command whose name is a phase switches into it and belongs there. `init` is the single exclusion and it is structural rather than a taste call -- it creates `.saipen/`, so there is no board to hold a claimed ticket at the moment it runs. Red-tested by removing `hunt` again, which now FAILs instead of passing quietly.

`phases/hunt.md` was titled "no TODO tickets remaining", true of the auto-transition and stale for an explicit invocation since the same release.

## 7.150.0 -- 2026-08-01 -- length is collision order, not cost

`sss` routes to `saipen status`, restoring the shortcut it lost a release earlier.

That row killed a rule one release old. v7.148.0 said the tripled form was the one that reaches a remote, and `ccc` was the only three-letter shortcut, so length told the reader what a key cost before they finished typing it. `sss` touches nothing outside the repository, and the claim stopped being true the moment it was added.

Length now means what stayed true: where two commands want the same first letter, the doubled form goes to one and the tripled form to the next -- `cc`/`ccc` for continue and its shipping chain, `ss`/`sss` for stop and status. That `ccc` is the only shortcut whose chain pushes is now stated on its own row, as a fact the table carries rather than an inference drawn from counting keys.

The row and the rule changed together, on purpose. The same defect shipped twice in the previous two days -- a citation that outlived its claim, and a `cc` row that had stopped matching the rule above it -- and both times the prose was left vouching for a table it no longer described.

## 7.149.0 -- 2026-08-01 -- the brake gets the short key

`ss` routed to `saipen status`. The user assigns it to `saipen stop` instead: `s` alone collides across stop, set, ship, status and scout, which is why the table resolves those by fiat, and the brake is the one worth two keystrokes.

`saipen status` loses its shortcut rather than taking a tripled one. Section 1.10's own prose, shipped a release earlier, reserves the three-letter form for the chain that reaches a remote, so `sss` on a read-only report would have contradicted a rule one day old. Status is also no longer the only way to see parked work: a resume must name blocked tickets, untriaged findings and live gates in its reply.

## 7.148.0 -- 2026-08-01 -- one key to maintain, one to reach a remote

`cc` is the button you press to keep the project moving, so three things that made it unreliable are fixed together.

RFC section 1.11 step 5 and section 2.1 both say an empty board at `DONE` auto-transitions into `HUNT` with no human asked. `phases/done.md` step 2 said the opposite under `goal_mode: false`: park with a manufactured `WAIT: user brake`. Same state, two mandates -- whether a plain continue kept maintaining or stopped depended on which document the agent had read. Section 1.11 wins and `done.md` now defers to it. A brake the user actually asked for is still legal to sit at; what is gone is a phase doc inventing one from an empty board.

Bare `saipen goal` reset the safety-valve counters unconditionally, so typing it out of habit mid-run silently granted a fresh 3-wave/20-ticket budget nobody authorized. It now resets only when the valve has actually tripped, and carries the counters over otherwise. That is what makes the shortcut safe to type at any time.

A resume must now name what is stuck -- blocked tickets, untriaged findings, a live gate -- in its reply. That view came only from `digest.md`, which is written at stop and ship, so a blocked ticket could sit unmentioned across any number of otherwise truthful sessions.

The shortcut table itself did not hold: `hh` routed to `HUNT`, a phase with no command behind it, and `cc` routed to a "Full pipeline" that was not a command either and quietly added commit and push to the most-typed key. `saipen hunt` now exists as an explicit trigger, `cc` is plain `saipen continue`, and the pushing chain moved to `ccc` -- doubled is safe, tripled reaches a remote, so the length of the shortcut says what it costs before you finish typing it. The validator now reads the table's right-hand column and FAILs any shortcut that does not resolve to a command the same section defines.

## 7.147.0 -- 2026-08-01 -- a file that stops mid-line swallows the next write

Every file the protocol appends to has to end on a line boundary. Appending to a file that stops mid-line does not add a line, it extends the last one -- and nothing here had ever read a file's last byte.

`.saipen/LOG.md` had reached exactly that state: a literal escape written where a newline belonged. Every LOG mutation `tools/audit_checks.py` appends then landed inside the final entry instead of after it, and two of its 45 red controls stopped being evidence while the suite still printed PASS. Three more live files were mid-line when this check was written, including a subSaipen `BOARD.md` ending on `## BLOCKED`, where one appended ticket would have cost both the heading and the ticket, and a subSaipen `STATE.md` ending on its own closing `---`.

The validator now reads the last byte of all 21 append targets -- the checkpoint trio, sealed LOG segments, the subSaipen manifest, and each worker's own three files -- and FAILs when one ends mid-line. Three shipped scenario fixtures turned out to be in the same state and were repaired. The red control strips the final newline from a fixture `BOARD.md`, so the mutation is the file's bytes rather than any check's wording, and the mutation harness now stands at 46 of 46.

## 7.146.0 -- 2026-08-01 -- a re-authorization that survives the next crash

Bare `saipen goal` clears a tripped safety valve by resetting `goal_waves`/`goal_tickets` to `0`, and nothing required that reset to leave a line. The bumps it cancels stay in the LOG, so Recovery -- which rebuilt the counters by counting completion events since the `saipen goal <text>` pivot -- restored the pre-reset totals and re-tripped a valve the human had just cleared, while RFC section 2.4 forbids tidying those counters back down. Not a one-time slip: every later Recovery revoked the same re-authorization again, from a count that only grows.

The bare path now writes `DEC: goal reauthorized -- goal_waves N->0, goal_tickets M->0`, section 1.5 counts from the NEWEST goal marker rather than the first, and only increments count as completion events so a reset line's own drop cannot be miscounted as work.

The validator replays that rebuild and compares the result against `STATE.md` instead of grepping for the line, because a marker that exists but does not explain the counters is the same defect. Its red control is a fixture pair -- `goal-reauthorization-trace` and `goal-reauthorization-untraced` -- identical except for whether the reset left evidence, so the control breaks the behavior rather than the wording of a check.

Shipped alongside it, from the same run: the `digest-stale` warning now distinguishes an in-progress pre-tag release from a digest actually carried past a published one, with executable pre-tag and post-tag probes; the guard sweep from the behavioral-red-test rule; the doubled-first-letter command shortcuts (`gg`/`cc`/`ss`); and the STYLE/RFC language-detection rules.

Two repairs to that work were needed before the gates went green. `.saipen/LOG.md` had been written with a literal `
` in place of its final newline, so the file ended mid-line: every LOG mutation the audit harness appends or swaps landed inside the last entry instead of after it, and two of the 45 red controls silently stopped being evidence. One byte restored both. The new digest probes also shipped five lines over the length limit, which took Ruff red.

## 7.145.0 -- 2026-07-31 -- the Windows crew launcher reports what happened

`bootstrap/saipen_crew.bat` fired three `start` calls and then printed "Three crew windows opened." unconditionally. None of the three statuses was read, so a launcher that refused every window still reported full success -- the same defect the Unix twin lost in T-370.

Each launch now goes through one status-observing subroutine. A refused window stops the run, names which of the three failed, and exits nonzero without the success line. The accepted count in that message comes from the counter the script actually maintains rather than a literal typed into each branch, so the numbers cannot drift from the launches.

Four executable controls run the real BAT under real `cmd.exe` with a shim launcher that refuses call 1, 2, or 3, plus a run where all three are accepted. A behavioral red-test -- making the subroutine swallow the shim's status instead of returning it -- turns all three failure controls red with `got rc=0 calls=3`, and restoring it returns them to green. Coverage stops at status propagation: `start` itself is not exercised, because exercising it means opening three real windows.

## 7.144.0 -- 2026-07-31 -- hooks resolve Bash for the Bash floor

The generated POSIX pre-commit hook runs under `/bin/sh`, but its no-Python fallback invoked the Bash-only portable floor through that same `sh`. On systems where `/bin/sh` is dash, a healthy project was rejected on the floor's Bash syntax before validation began.

Hook generation 3 now resolves and invokes `bash` explicitly. When the floor exists but Bash does not, the hook fails nonzero with a focused dependency message instead of reporting a structural validation failure or silently skipping the check.

Executable controls copy the real installer into an isolated SAIPEN home, generate a real hook, and run it through real dash. With only Bash reachable, a here-string floor executes and prints its marker; with Bash absent, the hook fails focused without the marker. The canonical validator, all 44 mutation checks, both portable floors, scenarios, tag audit, order audit, and Ruff pass.

## 7.143.0 -- 2026-07-31 -- portable LOG filtering propagates failure

The shell portable floor ended its LOG-validation pipeline with `|| true`. That made an empty malformed-line set convenient, but also converted a failed `sed`, `grep`, or file read into success before printing both the LOG-format PASS and final floor completion.

The filter stages now normalize only `grep` status 1, the legitimate no-match result. A locally scoped `pipefail` preserves any process error without changing the rest of the frozen shell floor, and a focused failure exits before either success claim.

The floor audit supplies a targeted executable `sed` shim: earlier invocations delegate to the real tool, while the LOG BOM-strip invocation returns 7. The real validator must fail with `FAIL: LOG.md read/filter failed`, without LOG PASS or completion. All normal 27-by-2 floor mutations, the canonical validator, 44 mutation checks, scenarios, tag audit, order audit, Ruff, and shell syntax pass.

## 7.142.0 -- 2026-07-31 -- tag enumeration failures are not skips

The historical tag audit mapped every failure of its initial `git tag -l v*` command to `SKIP: git unavailable` and exited zero. A launched Git process could return an IO, repository, or protocol error before producing any tag list, yet CI reported the dedicated audit as green after losing its entire subject set.

Only a genuinely absent Git executable now takes the loud, successful skip path. Startup errors and nonzero enumeration results exit one with a focused diagnostic, including the process status and captured stderr. Empty tag lists still skip because there is genuinely nothing in that checkout to compare.

The existing executable Git shim now covers the initial query as well as batch processing. An empty-PATH control proves the allowed missing-Git branch; an rc9 enumeration control proves observed process failure cannot print PASS or SKIP. The canonical validator, all 44 mutation checks, both portable floors, scenarios, tag audit, order audit, and Ruff pass.

## 7.141.0 -- 2026-07-31 -- shell predicates fail closed

The shell installer and uninstaller treated every failed `grep` as an ordinary no-match. A read or process error could therefore select an append, retain, or clean path and still let the script print `Done.`. The uninstaller also ignored a managed skill path when it existed as a regular file instead of a directory or symlink.

Every affected predicate now distinguishes match, absence, and error. Status 1 selects the legitimate absence branch; statuses above 1 return a focused failure and prevent completion. Managed skill paths are removed regardless of whether they are directories, symlinks, or regular files.

Executable controls replace `grep` with an rc2 shim during real install and uninstall runs, assert nonzero exit without completion, and verify user configs remain byte-for-byte unchanged. A normal uninstall control seeds a regular-file skill path and proves it is removed. The canonical validator, all 44 mutation checks, portable floors, scenario suite, tag audit, order audit, Ruff, and shell syntax checks pass.

## 7.140.0 -- 2026-07-31 -- generated bytecode is not a release artifact

Six compiled `tools/__pycache__/*.pyc` blobs were tracked in Git. They changed whenever local Python versions or source changed, and both recursive injectors copied them into every installed SAIPEN skill. Merely ignoring future cache files would not fix distribution because filesystem copy commands do not consult `.gitignore`.

The tracked blobs are removed and repository ignore rules now cover cache directories and `*.py[cod]`. Both injectors clean `__pycache__` directories and loose `.pyc`/`.pyo` files from the installed tools tree inside their existing fail-closed copy path before they may report success.

Each real injector probe now creates both bytecode shapes in the source tree before installation, asserts neither reaches the installed layout, runs the installed validator, and removes the skill byte-for-byte. A separate installed-bytecode red-control proves the layout assertion itself can fail. Full validation leaves no tracked or untracked cache status.

## 7.139.0 -- 2026-07-31 -- crew launch success means three terminals accepted

The Unix crew launcher selected a terminal executable by name, backgrounded some variants, ignored every launch status, and always printed that three windows were launched. A missing display, rejected option, or immediately failing launcher therefore produced the same completion claim as three accepted terminals.

Each detached launcher is now observed through a bounded startup window. A nonzero exit advances to the next available launcher; an accepted process stops fallback for that crew seat. Exhausting installed launchers exits nonzero without `Done.`, while the no-emulator command-printing fallback explicitly reports zero launched windows. The completion line is reachable only after all three seats are accepted.

The executable scenario harness supplies controlled terminal shims. Its all-fail run records nine attempted processes across three launchers and three seats, exits nonzero, and cannot print `Done.`; its first-success run records exactly three calls and reports exactly three launched windows.

## 7.138.0 -- 2026-07-31 -- exports belong to the project, not the shell

Both export scripts treated ambient cwd as the project root. Invocation from a nested directory failed, a foreign repository could export the wrong state, and a linked worktree could not reach the main worktree's shared `.saipen/`. The scripts now use the same explicit/Git-common/non-Git ownership contract as the Core bootstrap and write the archive beside the resolved owner.

Root selection fails closed: an empty explicit path, an unowned Git worktree, or an external git-dir whose parent happens to contain another `.saipen/` cannot become an implicit export target. Shell and PowerShell retain focused failure text and cannot report completion without a real non-empty archive.

`tools/run_scenarios.py` executes twelve ownership paths across both formats: nested, foreign, explicit, empty-explicit, linked-worktree, and separate-git-dir. Success cases open the real tar or zip and compare the archived owner marker; rejected and non-owner directories must remain archive-free.

## 7.137.0 -- 2026-07-31 -- bootstrap success means the writes landed

The shell injector and both uninstallers could print success after failed backups, transforms, removals, or writes. Shell command substitutions discarded function status; PowerShell collected `"FAILED"` as ordinary report text and still reached `Done.`. PowerShell's block regex also consumed user-owned surrounding whitespace, so install followed by uninstall changed a config it promised to leave alone.

All four bootstrap scripts now fail closed. Shell reports retain each operation's status, PowerShell uses terminating IO errors and converts caught copy/removal failures into a nonzero final result, and completion text is unreachable after any reported failure. Config block removal deletes only the managed content and separator it added.

The executable injector harness now completes both full lifecycles: replace a stale skill, validate the installed layout, uninstall it, and compare the seeded CRLF config bytes exactly, including space-only and tab-only lines. Four failure controls exercise a shell write error, a broken shell transform, a caught PowerShell copy failure, and a terminating PowerShell read failure; every control must exit nonzero without `Done.`.

## 7.136.0 -- 2026-07-31 -- a lost tag audit is not a passing tag audit

`tools/audit_tags.py` enumerated release tags, launched one efficient `git cat-file --batch`, and never checked whether that process succeeded. A started process that exited nonzero or returned truncated output became a list of historical missing VERSION warnings; with no comparable records left, the audit still printed PASS.

Once tag discovery succeeds, the batch step now fails closed on process errors and strict protocol violations. It accepts only complete SHA-1 or SHA-256 blob records and the exact legal `<spec> missing` response, checks declared sizes and record delimiters, and rejects malformed headers, truncation, and surplus bytes.

`audit_checks.py` executes the guard through a Python Git shim. Four controls make the batch process exit 9, return an empty-OID header, truncate a blob, and append surplus bytes. Every one must exit nonzero with focused FAIL text and no PASS; the normal audit still compares 201 tags with only the five recorded historical mismatches.

## 7.135.0 -- 2026-07-31 -- make STATE a real commit pointer

`last_event` was documented as the freshness marker that would eventually become required, but normal checkpoints and Recovery did not write it and the validator checked it only when present. The stale-state guard therefore disappeared from the usual state shape: an omitted marker looked green forever.

Core STATE schema v2 now requires the marker whenever the LOG has an event. Missing or v1 state remains readable legacy with a focused warning and upgrades at its next checkpoint; a genuinely fresh empty bootstrap still omits the marker because no event exists to name. Every checkpoint writes the numeric ID of the real LOG tail last, and Recovery derives the same value from sealed plus active history, so replaying Recovery is idempotent.

The schema's `x-current-schema-version` metadata is the single current-revision authority used by the validator. Six executable migration controls prove legacy readability, missing-v2 rejection, exact agreement, stale detection after a LOG append, recovery to the new tail, and above-tail corruption. Canonical mutation coverage is 44/44 with all four marker and schema-metadata failure paths held red.

## 7.134.0 -- 2026-07-31 -- known history is not a permanent warning

The release ledger repeated the same two tag-only and nine changelog-only releases on every validation. Tagged releases 7.81.0 and 7.82.0 now have truthful backfilled entries. The nine 7.84.0-7.91.0 commits whose tags were never published are recorded in a structured baseline with their release commits and reasons; no local or remote historical tag was created or changed.

The validator reads both current and archived changelogs, suppresses only those explicit historical exceptions, and fails when an exception becomes stale. `audit_checks.py` builds a temporary Git repository and executes four controls: clean ledger, new unmatched tag, new unmatched changelog entry, and resolved exception. New divergence stays focused and loud without forcing every normal run to reread old noise.

## 7.133.0 -- 2026-07-31 -- a skipped guard is a failed guard

Normal LOG sealing left active `LOG.md` without two events. The canonical backwards-ID mutation therefore skipped; `audit_checks.py` still exited 0 after reporting 40/41, while parity silently changed its denominator from 41 to 40. A green suite had lost a case because routine protocol maintenance changed the storage layout.

Logical LOG mutations now resolve to active or the newest sealed segment carrying an event pair. Both runners save, mutate, and restore that same physical file. Availability is checked before the expensive matrix, and any preflight or runtime skip is fatal. An active-empty sealed layout still applies 41/41; removing every eligible LOG makes both tools exit nonzero and name the missing backwards-ID case.

## 7.132.0 -- 2026-07-31 -- bind memory before touching it

Checkpoint paths were relative to ambient cwd. After an agent changed directories, `.saipen/STATE.md` could name a different project without any error; persisting an absolute root in STATE would only replace that with false corruption whenever a clone moved.

BOOT now binds one project root for the session. Git projects resolve their worktree and common directory, linked worktrees deliberately use the main worktree's gitignored memory, non-Git projects choose the nearest ancestor already carrying `.saipen/`, and `--project-root` is the intentional override from another cwd. Every later checkpoint path stays under that bound root. An unowned cwd fails instead of guessing or creating a second memory tree.

Six executable scenarios cover the correct Git root, nested Git cwd, foreign-repository rejection, explicit override, nested non-Git cwd, and linked-worktree ownership. Both injectors also run their installed validator against an explicit project root. The mutation audit caught one regression during development: root discovery initially swallowed the precise `STATE.md missing` diagnosis; location discovery now recognizes `.saipen/` and leaves file integrity to validation.

## 7.131.0 -- 2026-07-31 -- run the guard, not its spelling

The injector distribution guard read both scripts as text. Its last version pinned one exact `mkdir -p "$1" "$1/extensions" "$1/tests"` line; a harmless reflow killed the guard, while its token-only predecessor had passed an injector that created `tests/`, deleted it, and then could not copy the validators. The check observed spelling and called it behavior.

`tools/run_scenarios.py` now runs both injectors in isolated homes seeded with stale managed directories. Each must remove the sentinels and install `VERSION`, `tests/validate.sh`, and `tests/validate.ps1`; a deleted-`tests/` layout is the red-control. The old shell line was deliberately reflowed and stays green because no check reads its formatting.

The sweep found two more behavioral claims made from source text. Portable-floor parity now derives required fields and read-only phase bans from RFC.md, mutates a known-good project for every value, and executes both shell implementations: 27 cases across two halves. The release-ledger single-query invariant now uses Git Trace2 to observe one real process; an AST-located duplicate produces two, and a deliberately invalid validator control is rejected. Canonical mutations remain 41/41 and portable parity remains at its baseline of 11/41.

## 7.130.0 -- 2026-07-31 -- publish the release you named

`remote-v7101` was not an alias of the current `v7.101.0` object. It was a distinct, earlier annotated object whose embedded tag name was also `v7.101.0`, preserved under a temporary local ref while a mistag was investigated. That ref was created by a one-off Claude session command, not by a live repository script. It later escaped because SHIP said only "push tags", and `git push --follow-tags` selected the unrelated annotated tag from ambient local state.

The explicitly approved local and remote refs are gone. Their peeled commit, `1e42a89`, remains an ancestor of `main` and is contained by `v7.101.0` and every later release, so deleting the names discarded no commit. SHIP now pushes the branch and one exact `refs/tags/vVERSION` ref in separate commands; `--tags` and `--follow-tags` are forbidden for releases. A temporary bare-origin probe with both an intended and a stray annotated tag proved that the prescribed refspec publishes only the intended one.

## 7.129.0 -- 2026-07-31 -- one observation, two checks

The release ledger asked Git for its tag list twice. The first query fed the phantom-version check and warned when tags were unavailable; the second independently fed the tag-vs-CHANGELOG comparison and swallowed its own error with `except: pass`. A transient failure between those calls could therefore make one validation run say tags were available and silently skip the comparison that needed them.

The validator now observes tags once and reuses that immutable snapshot for both checks. A failed or non-zero query produces one warning with the actual cause. `audit_checks.py` pins the single-query invariant and proves its duplicate-query red-control fails.

The maintenance sweep also removed one completed MARKHUNT manifest and cleared three subSaipen OUTBOX files whose entries were already `reviewed` or explicitly `stale`. Their durable results remain in the main LOG, BOARD, and CHANGELOG; the kitchen no longer keeps second copies indefinitely.

## 7.128.0 -- 2026-07-31 -- SHIP could fail only by giving up

SHIP requires 100% green, but its DFA row allowed only `DONE` or `BLOCKED`. A fixable failure found during release preparation therefore had no legal route back to BUILD. This happened immediately in v7.126.0: preflight found the shell injector deleting `tests/` after creating it. The fix was known and local, but returning to BUILD was non-conformant; entering BLOCKED would have lied about needing human input and ended goal mode.

SHIP now has a narrow pre-commit repair edge to BUILD. The current ticket must repeat VERIFY, REVIEW, and SHIP after the fix. The edge ends when commit begins; push rejection and any later failure remain under SHIP's existing publish-recovery rules, and already-pushed work never returns to BUILD.

The release order is explicit now: prepare VERSION/README/CHANGELOG, rerun validators against that metadata, commit, then push the branch. Previously step 5 said only `Push`; a protocol that meticulously gates releases had omitted the command that creates the commit being released.

An executable scenario proves `SHIP -> BUILD` is legal, while the transition mutation now pins a fixed illegal `INIT -> SHIP` pair instead of depending on whichever phase the repository happened to occupy during the audit.

## 7.127.0 -- 2026-07-31 -- bash existed; its tools did not

The Windows floor harnesses correctly stopped choosing `sh` and the WSL `bash.exe` stub, then launched Git Bash by absolute path. That still was not enough: a directly launched Git Bash inherited the Windows process `PATH`, which did not contain Git's `usr/bin`. Bash ran, but `grep`, `sed`, and `sort` did not. Eighteen of twenty shell controls therefore failed at the first phase check and blamed `STATE.md`; the subject was healthy and the instrument had lost its tools.

`audit_floor.py` and `audit_parity.py` now add the detected Git `usr/bin` only to their child environment, leaving the user's global `PATH` untouched. Both reject the System32 WSL stub case-insensitively. The floor passes all 20 checks in both shell and PowerShell halves on Windows, and full parity passes 42 mutations at its frozen baseline of 11 shared detections.

## 7.126.0 -- 2026-07-31 -- the installed protocol forgot its own version

The installed Codex/Claude/OpenCode skill carried `RFC.md` but not `VERSION`, even though RFC section 1.2 names that file as the only source of truth for the version guard. A clean install therefore had enough protocol to refuse work and not enough protocol to prove which version it was running. Both injectors now ship `VERSION`, and the runtime manifest makes forgetting it again a validation failure.

Refreshes were overlays, too. Deleted source directories survived indefinitely in installed copies; the Codex skill still contained three old live subSaipen worker trees after the source layout moved them elsewhere. Injectors now replace the managed runtime directories before copying, with bounded destination guards. The installed validator was run from the Codex copy against this repository and passes; source and installed hashes agree, and stale worker directories are absent.

The same run caught a second kind of copied-contract drift: two scenario READMEs still listed the old four-phase Core read-only ban after RFC section 1.3 expanded it to seven. Scenario prose is now swept against the RFC-owned set, not trusted because executable floor scripts happen to agree.

During verification, the shell cleanup was found using the invalid `rm -rF` spelling. After that became portable `rm -rf`, a functional install exposed the next fault: `tests/` was created and then deleted before the floor scripts were copied into it. The order is now cleanup, recreation, copy; the validator checks that order instead of merely grepping for a cleanup token. PowerShell now carries the same empty-destination guard as shell.

## 7.125.0 -- 2026-07-31 -- a comparison with one side undefined

Asked whether a second Core could be added to this project, the useful answer turned out to be a defect rather than a yes. RFC § 1.4 decides whether another agent is live by comparing `STATE.md`'s `agent:` against "itself" -- and nothing in the protocol said where an agent gets its own value. One side of that comparison was never defined.

The consequence is measurable in this repository's own history: **six** distinct `agent:` values for what were two or three actual actors -- `claude-opus`, `claude-sonnet-5`, `opencode`, `antigravity`, `antigravity-gemini`, `gemini-pro` -- because every session invented one. A LOG line also reached disk reading `[agent: id]`: the placeholder itself, not a name.

An undefined side makes the test fail in both directions. A model upgrade renames the seat, so the next session sees a stranger and must assume a live concurrent agent that does not exist. And two genuinely different actors both writing a generic value are indistinguishable, which is the case the section exists for.

So the field is defined: `agent:` names the **seat**, not the model build, and a returning agent **inherits** whatever `STATE.md` already carries -- continuing another session's work under the same seat is what this protocol is for. Change it only when genuinely a different actor, and LOG a `DEC` naming both values so the graph shows a handover rather than an unexplained stranger. A model version change is not a different actor.

`BOOT.md` carries it too, because a cold agent writes this field at its first checkpoint, long before it would ever open § 1.4.

The stability half is behavioural and recorded as such: nothing can distinguish an honest handover from a renamed seat. Placeholders are mechanical, and they are the shape that actually escapes -- `id`, `<name>`, `AgentID`, `unknown` all FAIL now.

## 7.124.0 -- 2026-07-30 -- how a rule dies, and why a retry owes an answer

Two findings, both from checking a list of proposals against the repository instead of against intuition. Most of the list was already here in a finer form -- "acceptance is not completion" is `VERIFY -> REVIEW -> SHIP -> DONE` plus a per-ticket `verify:`, and the suggested five-state outcome taxonomy is coarser than the seven `WAIT:` categories § 1.2 already closes over. Two things were genuinely missing.

**A rule had no way to die.** `CONFORMANCE.md` has only ever grown: 144 rows, not one retirement, and a grep for `retire|obsolete|no longer needed` across it and the RFC returns nothing. Nothing made a rule loud when the tool, CI step or fixture behind it went away -- and a row naming something deleted reads exactly like a row that is enforced. That is the whole difference between a guarantee and a decoration. Row 78 sat wrong for several releases and was corrected only because somebody measured it by hand.

Deciding that a rule is obsolete is not a thing a validator can do. Refusing to let one claim an enforcement that no longer exists is. So it does, and the choice -- restore it or retire the row -- now has to be made by a person, out loud. Red-tested by deleting a named tool, renaming a named CI step, and removing a named fixture.

**A retry owed an answer nobody asked for.** RFC § 1.6 now requires a repeated attempt to name what changed since the last one -- new evidence, a changed input, a narrowed hypothesis -- and forbids the retry outright when the honest answer is "nothing". Counters never carried this: `phases/verify.md`'s 3-hypothesis/2-fix-cycle cap and `phases/ship.md`'s retry-once both bound how MANY times something repeats, and neither asks whether the second attempt could possibly go differently.

`verify.md` had in fact said "never re-test without new evidence" for a long time -- of debugging hypotheses. True of every repeated attempt, written for one of them: the same fixed-where-noticed shape this protocol keeps finding in itself, and the reason both phase docs now inherit the general rule by name instead of each restating a fragment.

It is behavioural and recorded as such. No artifact witnesses whether the agent really had new information. What the LOG line does is remove the excuse rather than the possibility.

Also taken, from a proposal that arrived with a rule attached: BUILD looks for existing code before writing new -- this project's own, the standard library, a dependency the project ALREADY has (adding one is a ticket, not a build step), then implement. One pass, deliberately. The attached "hard limit: never revisit" was left out, being a rule no artifact could witness.

## 7.123.0 -- 2026-07-30 -- the commit that added two checks also shipped a gitlink

`saiwiki` keeps a clone of the GitHub wiki inside its own kitchen, which is exactly what a subSaipen's kitchen is for. `git add -A` turns a nested repository into a mode-160000 entry -- a pointer to a commit no clone of this repository can fetch, carrying none of the content. That is what v7.122.0 shipped, in the same commit that added two new cross-document drift checks.

Git does warn about this. The hint arrived in the middle of roughly fifty lines of `LF will be replaced by CRLF`, which is to say in the one place nobody reads.

The path is ignored now and the entry is out of the index. More usefully, `tools/validate.py` FAILs any gitlink under `.saipen/`, and it introduced itself the way these checks keep doing: a fresh clone of the pushed v7.122.0 tree came back red.

A clone inside a kitchen is legitimate. Recording it in history as a pointer nobody can resolve is not.

## 7.122.0 -- 2026-07-30 -- a field the tool enforced and no document defined

`tools/validate.py` has rejected any ticket field outside `needs / owner / claim_time / blocker / verify / review_passes` since the beginning, with a message citing "RFC § 1.2's field list is closed". `phases/plan.md` tells every ticket to carry `| verify: <command or criterion>` and cites § 1.2 for it too. Seventy-two of this repository's own tickets carry the field.

§ 1.2 named neither the list nor `verify:`. All fourteen occurrences of the word in the constitution are the `manual-verify` mode or the VERIFY phase. Three places pointed at a clause that did not exist.

The citation checker could not see this, and the reason is worth stating rather than patching around: it proves a cited section EXISTS, never that the section says the thing being cited. § 1.2 is real, so all three citations resolved. Closing that in general would need every clause to carry an id, which the RFC does not have -- so the closed vocabularies get compared one at a time instead, and this release brings that to eight: § 1.10's command surface and § 1.2's ticket fields join required fields, the phase enum, from-any-phase, the read-only bans, the `next_action` prefixes and the WAIT categories.

The command surface agreed on the day it was checked, which is exactly the point. A vocabulary copied into a tool with no comparison is a bet that nobody ever edits either side.

Separately, a live catch by a rule shipped eleven releases ago: `saiwiki` was sitting at `transition_from: BUILD` with `phase: DONE` -- illegal twice, since the table does not allow it and `BUILD` is a phase no subSaipen may enter at all. Its own log explains why it looked that way: it cloned the GitHub wiki into its kitchen and pushed, which lands work outside its own folder. Its last entry was five hours old, twenty times past § 1.4's claim window, so the takeover was recorded in its LOG and the state rebuilt as a self-transition rather than a path the log does not support. The work itself was left alone.

## 7.121.0 -- 2026-07-30 -- 0.4 seconds was the diagnosis

The `Floor parity` step added one release ago failed on its first CI run, in **0.4 seconds**. That number is the whole finding: neither of the two tools it compares could have executed in that time, so what failed was the harness, not the subject.

`find_bash()` tried the Git-for-Windows paths first -- because a bare `bash` on Windows resolves from Python to the WSL stub, which without an installed distro prints a UTF-16 error and runs nothing, a trap `KNOWLEDGE/traps.md` has carried since an audit scored all twenty floor checks dead. Its fallback was `sh`. On Ubuntu `sh` is **dash**, and `tests/validate.sh` is shebanged `#!/bin/bash`. Reproduced locally: `dash tests/validate.sh` exits 2 immediately.

Both halves of the same trap, in one file, in one release: the wrong shell on Windows and the wrong shell on Linux. It takes a real `bash` now, and `sh` is never acceptable.

The second half matters more. The precondition that caught it printed `one of the two tools rejects an UNMODIFIED copy` and stopped. True, useless, and it cost a full CI round trip to learn nothing -- which tool, what exit code, what it actually said, all absent. It names all three now.

Twenty releases of this work have been spent finding checks that report without diagnosing. Writing a fresh one is the same defect wearing a new hat.

## 7.120.0 -- 2026-07-30 -- the floor was claiming conformance in the validator's own words

Yesterday's 41 mutations were built to prove `tools/validate.py`'s checks still go red. Pointing the same table at the portable floor answers a different question, and the answer is uncomfortable: **the floor catches 11 of 41.**

The gap itself is not the defect. `tests/validate.sh` / `.ps1` exist for hosts without Python, they are frozen against new checks on purpose, and a `grep` pipeline cannot parse a phase transition table or walk an event graph. Twenty-eight of those defects genuinely need Python.

The defect is what the floor said about itself. Both halves ended with `Validation complete. Agent is conformant.` -- the exact sentence the canonical validator prints on a clean run. A host without Python was reading a claim four times larger than the file can support, in wording chosen to be indistinguishable from the real thing. They now print `Portable floor complete: no structural break found` and name themselves a subset that `tools/validate.py` should be run against wherever Python exists. Correcting a claim is not adding a check, so the freeze permits it -- the same footing as v7.96.0's corrections.

CONFORMANCE row 78 has been rewritten for the same reason. It stated ONE known floor gap, `next_action` presence without executability. Stating one where there are twenty-eight is not a cautious understatement, it is the wrong shape of reassurance.

`tools/audit_parity.py` keeps the number from rotting, and guards the direction that actually matters: it fails when the floor drops BELOW its recorded baseline. A permanent gap that everyone knows about is a design decision; a floor getting quietly weaker is the failure.

Two cases are caught by neither tool -- a `schema_version` from the future and a `requires:` capability nobody defines. Both are deliberate WARNs, so both exit 0. The tool prints them by name instead of folding them into a count, because "caught by neither" and "warned by one" are different facts.

## 7.119.0 -- 2026-07-30 -- sixteen releases of red tests, all thrown away

Row 84 said it in general terms; this release measured it. `tools/validate.py` carries about 160 failure paths. The inputs this repository ships -- its own `.saipen/` plus the 14 executable fixtures -- produce **17 distinct FAIL/WARN lines** between them. Every other check rests on a hand test from the day it was written, which is precisely how one check in that file lay dead from `feae149` to v7.99.0 and how the first draft of the portable-floor check could not go red at all.

The uncomfortable part is not the number. It is that the previous sixteen releases red-tested roughly twenty-five checks, each in a scratch directory, each deleted seconds later. This repository's own rule is that a hand test proves a check worked once and a fixture proves it still works -- and every one of those tests was a hand test.

`tools/audit_checks.py` is those tests, kept: 41 mutations of a known-good copy, each asserting the validator names that specific failure. `tools/audit_floor.py` has done this for the floor's 20 checks since v7.101.0; the canonical validator had nothing.

The harness lied three ways before it worked, and all three are the shapes this repository keeps meeting. It searched the whole output, so "at most one", "cyclic" and "dangling needs" matched the PASS lines announcing those very checks had succeeded -- five cases scoring as proving nothing when the harness was at fault. Its UTF-16 sentinel evaluated to `None`, so that case deleted the file it meant to re-encode. And the `goal_mode` mutation was a no-op, because this repository already runs with `goal_mode: true`.

So the control run is now a precondition rather than a formality: a case whose expected text is already present before the mutation fails loudly, because a message that is always there is not evidence. Comparison is against FAIL/WARN lines only.

Red-tested twice, in both directions that matter: raising one cap out of reach kills exactly one case, and silencing `fail()` entirely kills 39 of 41 -- the two survivors being the WARN-based cases, which is correct rather than a gap.

One case was deliberately retired instead of kept. The phantom-version check needs the tag half of the release ledger, and this harness copies the tree without `.git` on purpose; without tags the check correctly declines to run, so a case for it could only ever match the WARN saying it was skipped. That is on the record in the file, rather than a case that quietly proves nothing.

## 7.118.0 -- 2026-07-30 -- the file that exists to end self-report, read by nobody

Three releases running found the same shape -- a field with a full specification and no reader -- and all three found it by luck. So this one stopped hunting by luck: every `MUST` sentence across the 18 normative documents, pulled out and cross-checked against the artifacts any tool actually mentions. 192 MUSTs, 77 named artifacts, 14 candidates, one real.

That one is `.saipen/kitchen/markhunt_progress.md`. `phases/markhunt.md` specifies it completely -- `vectors:` (which of scope categories 1-5 are done), `surface:`, `findings:`, `cursor: partial | done`, `head_start:`/`head_end:` -- and states plainly why it exists: the file IS MARKHUNT's closure check, "the thing HUNT gets from its exact hash-match skip and MARKHUNT historically lacked, leaving completeness pure self-report". No tool had ever opened it. Completeness was back to pure self-report by a different route.

Checked now: the shape, the `cursor` vocabulary, the rule that `cursor: done` requires every scope category present in `vectors:` (markhunt.md: a missing vector means the surface is NOT exhausted, keep going rather than round up), and the contradiction of a `partial` manifest sitting under a phase that has already moved on -- a pass the manifest says never finished, closed anyway.

Reading the spec closely enough to enforce it also turned up a gap in the spec itself. `no-git` is permitted in both `head_start` and `head_end`, and the head-equality closure test is then "satisfied automatically". A mixed pair -- one real hash, one `no-git` -- is undefined by that wording, and would skip the equality test on the strength of half a reason. It fails now.

The 1-in-14 signal ratio is why the sweep is recorded as a technique rather than shipped as a gate: a check that cries wolf thirteen times out of fourteen teaches people to ignore it, which is the opposite of what this repository has spent fifteen releases building.

## 7.117.0 -- 2026-07-30 -- two more fields with a spec and no reader

RFC § 1.2 states why `review_passes` exists, in as many words: so `phases/review.md` can "enforce its two-pass cap mechanically instead of from memory". The board grammar recognised the field name and nothing ever read the number, which left the cap in precisely the place the RFC says it must not be.

`.saipen/kitchen/digest.md` is the three-line snapshot `phases/ship.md` promises: `done:`/`remaining:`/`awaiting:`, "(over)write ... exactly three short lines", "overwrite every time", and `saipen stop` writes the same file. Neither the shape nor the freshness was checked, and the live digest turned out to name a release **33 versions old** -- every ship since had skipped the write silently, fourteen of them in this very session. A snapshot nobody refreshes is worse than no snapshot: it reads as current.

Freshness is checked without comparing file times, which are meaningless in a fresh clone. The digest usually names the version it describes, so a version in that text that is not `VERSION` is the signal -- narrow, but it is exactly the shape this failure takes, and it introduced itself on the live file within a second of existing.

## 7.116.0 -- 2026-07-30 -- a field name everyone spelled right and nobody read

`claim_time` sat in the validator's list of recognised ticket fields and its value was never once looked at. RFC § 1.4 decides from that value whether a ticket is live or forfeitable, by comparing it against a 15-minute window -- and a stamp carrying no zone marker is not comparable across agents at all. That is the identical argument § 1.2 already makes for `updated`, which is checked. The field was recognised, not read.

It found a shipped fixture immediately: `multi-agent-claim-conflict` had carried a zone-less `claim_time` for releases. The fixture was fixed rather than the check, because its own README says it exists to demonstrate the *shape* of a claimed ticket -- and the shape includes the zone.

An `owner` with no `claim_time`, or the reverse, is half a claim and now warns. Liveness is read from the pair; one alone cannot be judged live or stale.

The last finding is about the tooling and matters more than either. The red test for that half-claim warning came back empty -- and the test was wrong, not the check: it grepped for `warn()`'s category key, which was never printed. Individual warnings were anonymous; the key appeared only in the "... and N more" roll-up. That trap is recorded in `KNOWLEDGE/traps.md`, has been since a warn-coverage audit scored 8 of 8 categories unreachable, and it has been walked into five more times since being written down -- twice while writing checks in this session.

A trap that keeps catching people after it is documented is a missing affordance, not a discipline problem. Every `WARN` line now carries its `[category]`. There is nothing left to catch.

## 7.115.0 -- 2026-07-30 -- a fully specified MUST with nothing behind it

`last_event` is the one `STATE.md` field whose entire job is catching a state that has drifted from its own log. RFC § 1.2 specifies it exactly -- "lower than the LOG tail means stale, higher than the LOG tail means corrupt or from an incompatible branch" -- and `tools/validate.py` contained zero references to it. Nothing is broken today, because the field is RECOMMENDED and nobody writes it. The RFC says it will become REQUIRED, and that is precisely when an unchecked value starts doing damage: Recovery rebuilds from the LOG tail, and a `last_event` above it points at an event nobody ever wrote.

How it survived is worth as much as the fix. v7.108.0 added a rule-coverage check requiring every RFC section that states a MUST to be cited by a CONFORMANCE row -- and § 1.2 is cited by dozens. A single unenforced MUST inside a heavily-cited section is invisible at section granularity. That blind spot is now stated in the table rather than quietly narrowed: the check is worth keeping, and knowing what it cannot see is worth more than pretending it sees everything. Per-MUST granularity would need every clause to carry an id, which the RFC does not have.

Second hole, the mirror of one already closed. `TEMPLATE/STATE.md` ships placeholders that `saipen sub spawn` replaces: `agent: <name>`, an empty `saipen_home`, a fixed `updated:`. A check already stopped a concrete machine path leaking INTO the shipped template. Nothing stopped a placeholder surviving OUT of it into a live subSaipen -- and that is not cosmetic, because RFC § 1.4 decides concurrency by comparing `agent:` against itself. A spawned worker still called `<name>` makes every liveness comparison meaningless.

And a note on the tooling, because it is the first time it paid for itself unprompted: writing the placeholder check produced the fourth use-before-define `NameError` of this session, and `tools/audit_order.py` -- added one release ago for exactly that -- caught it with no fixture and no human looking.

## 7.114.0 -- 2026-07-30 -- the rule that governs the first token sat behind an escalation

A session answered a Russian-speaking user in Ukrainian. The user has never written a word of Ukrainian to it.

The rule against exactly this has been in `STYLE.md` since v7.23.0: reply in the language the user themselves typed, and where a first message carries no prose at all -- a bare command -- default to English. It even records the incident that produced it, a session that went fully German off a bare `saipen hunt`. The rule was not missing. It was unreachable.

`BOOT.md` is the cold-start kernel, and it is all a bare `saipen continue` reads. It mentioned `STYLE.md` in exactly one place: the line listing what to open when `STATE`/`BOARD`/`LOG` and the active phase doc *don't answer a rule question*. An agent that boots and simply works never has a rule question, so it never opens `STYLE.md`, so it never sees the one rule that applies before its first token. `BOOT.md` now states the rule itself -- the single thing it repeats rather than points at, because a pointer to a rule that governs the first token is too late by construction.

The second half is worse, because the rule was incomplete where it lives. `STYLE.md` banned inferring the user's language from "IDE/OS locale, platform UI language, unrelated prior context" -- three ambient sources, and it missed the one this project is made of. SAIPEN ships 33 translated guides and 32 locale directories. An agent working inside it is surrounded by Ukrainian, Japanese and Estonian prose that neither it nor the user wrote, and nothing said that was not a signal. It says so now: files are content to produce, never a cue for which language to speak.

Both copies are checked against each other, because a rule deliberately duplicated into the kernel is a drift surface by definition.

While counting locales for the above, the two sides turned out to name Estonian differently: `et` in the kitchen (ISO 639-1, a language) and `EE` in `guides/` (ISO 3166, a country, picked to sit beside the flag in a human-facing badge). Both are defensible in their own role, and nothing stated which governs where -- so the sets could drift apart in silence, and the first tool to join them would have dropped Estonian without a word. The alias is written down now and the join is checked in both directions, with English exempt by name as the source language.

## 7.113.0 -- 2026-07-30 -- the only gate a consuming project has, and nothing checked its age

In a project that merely uses SAIPEN, `.git/hooks/pre-commit` is the whole enforcement surface: no CI, no release workflow, just that one file deciding whether a corrupt `.saipen/` reaches a commit. Its text is baked in at install time and never updates itself, so a hook installed twenty releases ago goes on running exactly the logic it was born with -- and nothing anywhere said so.

That is the failure `KNOWLEDGE/traps.md` already records for the injector's skill copies, which have to be re-injected after every pull. The hook had no equivalent signal at all. It carries a generation stamp now, and `tools/validate.py` compares it against the number the installer ships -- parsed out of `install_hook.py` rather than imported, because that module does its work at import time.

The check introduced itself: this repository's own hook had no stamp, having been installed before one existed.

The second half is the hook's final `exit 0`. Reaching it means neither `validate.py` nor the portable floor could be found -- usually a moved `saipen_home`, and if `STATE.md` happens to be UTF-16 then the `sed` fallback recovers nothing either. The commit was allowed through, which is right, and in complete silence, which is not: an unvalidated commit that LOOKS validated is the same silent PASS this protocol has spent ten releases digging out of its own checks. It stays fail-open -- blocking every commit on a broken install is worse than letting one through -- and now prints what it could not find and the command that repairs it.

## 7.112.0 -- 2026-07-30 -- three NameErrors in one day, none of them visible locally

`tools/validate.py` is a 2300-line straight-line script: its checks run in file order, so a constant placed below its first use is a `NameError` waiting for the one input that reaches that branch. Three landed in a single day. `SAIPEN_COMMANDS` was declared beside its second consumer, and the branch that reads it first only runs when `next_action` starts with `saipen ` -- this repository's own says `WAIT:`, so every local run passed and a fixture caught it. `IS_SAIPEN_HOME` was read by a check spliced above the line that computes it. And `saipen_dir` was a name that never existed at all.

Ruff cannot see any of them: the name IS bound in the module, just later, and `F821` reports only names never bound anywhere. Nothing else was looking, so `tools/audit_order.py` now does -- walking each tool's top-level statements in order and reporting any read of a name nothing binds until later.

The instrument lied twice before it worked, and both lies are the signature this repository keeps meeting. The first version reported several hundred findings: reads inside a top-level `for` body were checked against the set of names bound *before* the loop, so the loop variable itself came back as used-before-assigned. The second reported five: function and lambda parameters, which are bindings resolved at call time, not reads happening where they sit. A misconfigured harness is almost always total; a real defect almost never is, and that is now four instruments in one session caught by that test rather than by inspection.

Three smaller holes in the same pass, all of the same shape -- a field with a type and no meaning:

`requires:` was checked as an array of strings and its values compared to nothing. RFC § 1.3 says an entry with no mapping "is not a licence to ignore it": the agent MUST degrade to the mode describing what is lost. It cannot do that for a capability nobody defines, so `requires: [pyhton]` silently REMOVED a requirement instead of tightening it.

`saipen_version` was checked as an integer and compared to nothing at all -- a project declaring 6 while running against a v7 home had every v7 rule applied to a v6 state, with no signal anywhere.

And the release-ledger warning printed "10 release(s)" and then listed eight, silently truncated. Small, and exactly how a reader learns to stop trusting the numbers in a message.

## 7.111.0 -- 2026-07-30 -- read-only meant two different things and one document said they were identical

Looking for asymmetry -- which checks Core's `STATE.md` gets and a subSaipen's does not -- turned up four: RFC § 1.2's ninth required field, transition legality, the ISO-8601 UTC form of `updated`, and § 1.10's command vocabulary were all Core-only. Meanwhile the validator printed `subSaipen STATE.md shape valid`, a message claiming a shape it had not checked. That is the mirror of the inversion fixed in v7.101.0, where the prefix rule was stricter for a read-only worker than for the state a cold agent actually boots from.

Closing the parity opened something bigger. `mode: read-only` means two different things in this protocol. Core's is a **capability** lock: filesystem write is unavailable, so RFC § 1.3 bans all seven phases whose work product is a file write -- `PLAN` writes tickets and `ADD` writes a board, so both are out of reach. A subSaipen's is a **scope** lock: it writes its own `STATE.md`, `BOARD.md`, `LOG.md` and `kitchen/` freely -- § 8's fixer edits copies in `kitchen/pen/` -- and is forbidden only from the shared tree. Its ban is the four phases whose product lands outside its own folder.

`extensions/subs/PROTOCOL.md` § 1 asserted that "the behavioral contract is identical either way". `tools/validate.py` has always enforced four. So the document was **stricter than the tool** -- drift in the rarer and more confusing direction: a reader obeying the document would never enter `PLAN`, while every real subSaipen plans its own backlog, including the shipped `TEMPLATE`, `saipython` right now, and § 5's own backpressure note. Both documents now state the distinction, both lists are named constants, and the drift detector parses PROTOCOL.md's own sentence -- failing on a missing anchor as loudly as on a changed list.

One transition follows from the same reasoning. RFC § 1.6 routes `HUNT` to `ADD`/`PLAN`/`SCOUT`/`BLOCKED` because for Core a clean sweep still has to decide what work it creates. A reporting subSaipen's deliverable is its OUTBOX, and the add step happens in the main project during `collect` (§ 4). `HUNT -> DONE` is therefore legal for a subSaipen and only for one. `saihunt` had been sitting in exactly that state, truthfully, since its first sweep -- nothing had ever looked at a subSaipen's transitions.

Two tooling defects surfaced on the way. `SAIPEN_COMMANDS` was declared after its first use, and the branch that reads it never executes in this repository, because this `STATE.md`'s `next_action` is a `WAIT` -- so only a fixture could reach the `NameError`, and one did. And `tools/run_scenarios.py` reported that crash as "failed as declared, but for the wrong reason": both a crash and a wrong-reason failure exit non-zero, and the softer wording sent the reader at the fixture when the defect was in the tool. A crash is now named a crash.

## 7.110.0 -- 2026-07-30 -- the validator died on the first file it read

`.saipen/STATE.md` is the first thing `tools/validate.py` opens, and it opened it as `utf-8-sig`. A UTF-16 file -- which is what PowerShell 5.1's `Set-Content` and `Out-File` produce by default, a trap `KNOWLEDGE/traps.md` has recorded since v3.1.1 -- raised `UnicodeDecodeError` and killed the whole run. A Python traceback, zero FAILs, not one other check performed, and all of it out of a pre-commit hook. A project could carry ten defects and the only thing reported was a decode error nobody can act on.

Found by transferring a defect out of SAIPENVIEW, where the same `read_text(encoding="utf-8")` habit meant the viewer could not display the project it lives in.

What makes this shape expensive is that the three corruption forms break every tool differently, which hides the cause rather than exposing it. This validator died on a traceback. The `grep`-based portable floor matches nothing and reports missing fields. And a BOM alone raises nothing at all: it survives as a leading character, `^---` stops matching, and the frontmatter parses as silently empty -- a project rendering with no fields and no error anywhere.

So all three checkpoint files are encoding-checked up front, by name, before anything is parsed, and the run continues: one FAIL that says which file, which encoding, and what the other tools will do about it, plus every remaining check still performed. Red-tested with UTF-16 with and without a BOM, and with BOM-carrying UTF-8; each gives one named FAIL and seven surviving PASSes where the traceback gave none.

Separately, `schema_version` was checked as `>= CURRENT`, which is written from the wrong end. A state NEWER than this validator is not reassuring: it may carry required fields this file has never heard of, or the same field names with changed meaning, and every PASS underneath is a claim with nothing behind it. `schema_version: 99` validated clean at exit 0. That is the same defect class as the release-ledger check running on half a ledger one release ago -- a check reporting on data it cannot evaluate. It is a WARN rather than a FAIL on purpose: a FAIL would block every commit in a project the moment the protocol bumps its schema, including during the bump itself, and the point is to kill the silent PASS, not the work.

## 7.109.0 -- 2026-07-29 -- the tag guard had never looked behind itself

`release.yml` refuses to publish a tag whose `VERSION` file disagrees with it. That guard is forward-only by construction: it was added in v7.99.0 *because* a tag had already reached origin pointing two releases behind, and it can say nothing about the tags that were already there. Nothing ever swept them.

The sweep found four mismatches nobody knew about, on top of the one that caused the guard: `v7.61.0` landed one release behind, `v7.74.0` one ahead, and `v7.81.0` and `v3.1.1a` sit on the right commit with a `VERSION` that was never bumped. All four confirmed by hand.

The audit lied twice before it told the truth, and both lies are worth recording because they are the same failure this repository keeps meeting. First, the `git cat-file --batch` parser advanced two lines per record where a record is `header + contents + newline`, so every reading after the first was matched against the wrong tag: 82 of 174 tags "broken", including ones created minutes earlier. That is the total-failure signature -- a misconfigured harness is almost always total, a real defect almost never is. Second, a dozen historical `VERSION` blobs turned out to be UTF-16 written by PowerShell; read as UTF-8 they come back as spaced-out digits, and every one was reported as a mismatch. Decode by what the bytes are, not by what they ought to be.

The pre-existing mismatches are recorded with a per-entry reason rather than rewritten. Moving a published tag re-runs `release.yml` from the TAG's commit -- for these, a workflow with no guard at all -- and could republish or reorder releases years old. The repository already decided this way about `CHANGELOG.md`: history records what happened, mistakes included.

And the exemption list is itself rechecked. A tag listed as a known mismatch that has since come to agree with its `VERSION` FAILs, because an entry that no longer describes a real defect is exactly how a check quietly stops covering what it claims to -- which this session has already found to be where coverage rots.

## 7.108.0 -- 2026-07-29 -- nine MUSTs nobody had claimed

Since v7.101.0 this repository checks that every shipped document is accounted for -- each one either matches a pattern some check reads, or is listed exempt with a stated reason. That check exists because twice running the real defect was not two documents disagreeing but nobody looking at a document at all.

The same question was never asked one level up, about rules. Ask it and three RFC sections come back stating nine MUSTs between them with no CONFORMANCE row citing any of them: § 1.7 workspace hygiene, § 1.8 batch input parsing, § 2.3 the completion rule. Not disputed, not exempted, not deferred -- unaccounted for. And structurally invisible to every existing check, because they all compare things that ARE written to each other, and this is an absence.

One of the three was mechanically checkable all along. § 1.7 forbids `saipen set` from copying phases or scripts into a project: the bootloader POINTS at `saipen_home`, and a copy goes stale the moment the home moves with nothing in the project to say so -- which is precisely the failure `KNOWLEDGE/traps.md` already records for the skill-directory copies. `.saipen/` carrying `phases/`, `tools/`, `tests/`, `schemas/`, `adapters/`, `templates/` or a core doc now FAILs. `extensions/subs/` is deliberately not in that list; those are the project's own subSaipen instances, not a copy of the home.

The other two are judgement about scope and intent, and no artifact in `.saipen/` witnesses them. A board with twenty tickets from one prompt is shape-identical to a board with twenty tickets from twenty prompts; an invented "etc." item reads exactly like a real one. They get rows saying exactly that. A MUST with a row admitting no tool stands behind it is a known limit; a MUST with no row is indistinguishable from one nobody remembered.

Housekeeping in the same pass: the active log crossed its cap and was sealed into `logs/LOG-004.md` -- 147 events, E-881..E-1027, 169 lines down to 22. Running the seal a second time refused, which is the outer threshold guard added in v7.93.0 doing its job at the exact spot where an earlier run had sealed a four-hundred-byte fresh log.

## 7.107.0 -- 2026-07-29 -- the guard could not survive its own name being wrong

The palette named one release ago carried a one-letter slip. Correcting it meant travelling the same 49 files the rename had, and it exposed a flaw in the guard shipped alongside it: that guard enforced exactly ONE superseded name, so the moment its own canonical name changed, the name it had been created to enforce became the thing it needed to reject.

A constant would have made every future rename a code change. A list makes it a one-line append -- which is the difference between a rule that survives being wrong and a rule that gets deleted the first time it is inconvenient. Two entries now; it grows by one per rename.

`CHANGELOG.md` is exempt, deliberately. It records what the name WAS, and so do the append-only logs. A rule that forces a rewrite of the past is a rule nobody keeps.

Red-tested with both superseded names, and confirmed silent on the CHANGELOG entry that legitimately carries one.

## 7.106.0 -- 2026-07-29 -- the palette has a name now, and every document uses it

`UI.md` declares **Wintage Golden** the default palette. Not a theme, not a preset, not one option among several -- it is what a saipen interface looks like unless the user asks otherwise in so many words, and there is deliberately no second palette in the document to choose from. A document with two defaults has none.

The eighteen tokens under that heading are the reference: an interface that has drifted from them is wrong rather than merely different. The values themselves are the lighter set that had been sitting uncommitted since before this session -- the original numbers proved hard to read on a glossy panel in daylight -- and they are already exactly what SAIPENVIEW ships, verified token by token, eighteen of eighteen. The old numbers are not preserved as an alternative; superseded is superseded, and `git log` remembers them.

`UI.md` also now says how to extend the palette, because iron law 5 forbids inline hex and an implementation with a domain-specific colour needs somewhere to put it: declare it in the same `:root`, name it by role, never by colour.

The name it replaced lived in 46 files -- two shipped root documents and 44 locale copies, every one of which would have gone on naming a palette the defining document no longer knows. That is the shape this repository keeps re-finding: the 33 guides teaching a superseded `WAIT:` form, the root `GUIDE.md` sitting outside the glob, seven adapters pointing a cold agent at the constitution. A change that lands where it was written and nowhere else.

So the rename is guarded, not swept: `UI.md` must name its palette, and no shipped document may name the superseded one. Red-tested in both directions. The superseded literal is assembled in code rather than written into `CONFORMANCE.md`, because that file is itself scanned -- the fourth rule this session that had to stop quoting its own illustration.

## 7.105.0 -- 2026-07-29 -- the ledger check ran on half a ledger and failed a correct repo

Yesterday's release added a check that a cited version must exist in the release ledger -- git tags plus CHANGELOG entries. It reddened CI on its first run, on a repository that was correct.

`actions/checkout` clones shallow and fetches no tags. So in CI the ledger arrived with only its CHANGELOG half, and the two releases recorded solely by a tag (`v7.81.0`, `v7.82.0`) read as versions that never happened. Every citation to them became a phantom. The check had been red-tested locally, in a full clone, where the failure is invisible by construction -- which is the same shape as every dead check this repo has found: verified once, in one environment, and never asked what it depends on.

A partial view of external state is worse than none: it does not weaken the check, it inverts it. Both halves present, or the check is skipped and says so with a WARN naming the missing half. Red-tested against a working-tree copy with no git at all, and confirmed still able to go red with tags present -- the first attempt at that test proved nothing, because it cloned the committed tree and ran the version of the validator that predated the fix.

The release job died the same way, on `git fetch --tags` against a shallow clone, so `v7.104.0` was tagged with no GitHub Release published. Both workflows now check out with `fetch-depth: 0`.

One thing worth stating because it shapes every future fix of this kind: repairing a workflow on `main` does nothing for a tag already pushed. GitHub runs the workflow file from the ref that triggered it, so a broken release job must be fixed forward with a new release, never by re-pushing the old tag.

## 7.104.0 -- 2026-07-29 -- below VERSION is not the same as shipped

Forty-two lines across `CONFORMANCE.md`, `extensions/subs/PROTOCOL.md`, both JSON schemas, `tools/validate.py`, the PowerShell floor and sixteen scenario READMEs named `v7.100.0` as the release they shipped in. There is no such release: no tag, no CHANGELOG entry, and no commit whose `VERSION` file ever said it. The number was skipped and the citations were written anyway.

The check that exists to catch exactly this certified every one of them. It bounds citations by `VERSION` -- a version above the current one is a promise the repo cannot keep -- and that bound silently assumes the sequence is dense. It is not. A cited version now has to exist in the release ledger, which is git tags plus CHANGELOG entries; below the older of those two floors the repo genuinely has no memory and the check stays quiet, which is honest. Silence above it was the defect.

The scan also had to widen past markdown. `_cite_docs` is `.md` only, and a version citation rots identically inside a JSON schema, inside the validator itself, and inside the frozen portable floor -- all three carried the phantom number. That is the third time in one day a rule was right about content and wrong about coverage. The check earned it immediately: it found twenty-five citations that a manual sweep run minutes earlier had missed, including every scenario README and both schemas.

Two more findings came out of the same audit, both about records nobody had ever compared.

The release ledger's halves disagree: two releases carry a git tag with no CHANGELOG entry, nine carry a CHANGELOG entry with no tag. That is now a WARN rather than a FAIL, deliberately -- closing it means either rewriting CHANGELOG or pushing nine backdated tags, and pushing a tag publishes a release. It is a fact the repo should carry, not a gate it should trip on.

And `release.yml` left `make_latest` at its default, so re-pushing an old tag marks that old release "Latest". Re-pushing an old tag is precisely what correcting a mistagged release requires, so the fix for one mistake caused another: correcting `v7.101.0`, whose tag had been pushed at a commit two releases behind, buried `v7.103.0`. The workflow now decides from `git tag -l | sort -V` instead of from the clock.

Also repaired: `saipen/phases/hunt.md` carried a UTF-8 BOM and five cp1251-mangled section signs from an uncommitted PowerShell edit, caught by the text lint widened one release earlier. The author's content change was kept.

## 7.103.0 -- 2026-07-29 -- the lint knew one mojibake shape and walked four files

`KNOWLEDGE/traps.md` documents three shapes of the cp1251 corruption PowerShell inflicts on non-ASCII text -- a mangled em-dash, a mangled arrow, a mangled section sign. The text lint in `tools/validate.py` recognised exactly one of them. It also walked a curated list of four core docs rather than the shipped surface, so `KNOWLEDGE/`, `extensions/` and the fixture READMEs were never scanned at all. Two gaps at once, content and coverage, and the second is the one that hid the first.

Widening the walk made it FAIL on the first run, on `traps.md` itself: a mangled arrow had been sitting in the very file that documents this corruption, invisible to the check whose subject it describes. Five sequences are recognised now, across every shipped doc.

`traps.md` now describes the shapes instead of reproducing them. That is the third rule this session to trip over its own illustration, after the required-field count and the future-version bound -- and the answer was the same all three times: a rule that cannot survive its own example is one nobody can keep.

## 7.102.0 -- 2026-07-29 -- seven of nine adapters sent a cold agent at the constitution

`extensions/adapters/*.md` tell each platform how to load SAIPEN. Seven of the nine never mentioned `BOOT.md` at all -- they said only "follow `saipen/RFC.md`", which inverts the entire 2-tier design. The constitution is around 100 KB; the cold-start kernel is under 4, and BOOT is all a bare `saipen continue` needs. Every cold start on those seven platforms was paying twenty-five times the necessary read.

T-204 corrected two of them and nobody looked at the other seven. That is the third instance of one shape this week: the 33 guides teaching a superseded `WAIT:` form, the root `GUIDE.md` sitting outside the `guides/` glob, and now this. A fix applied where it was noticed rather than everywhere it applies. All nine adapters now carry the boot order, and an adapter that never names `BOOT.md` FAILs.

Two things confirmed rather than assumed, which is the other half of the work: CI's seven steps carry no `continue-on-error`, no `allow_failure`, no trailing `|| true` -- every one of them actually gates. And the release guard added in v7.99.0 earned itself in production this week: a tag reached origin pointing at the wrong commit for the second time, and the release job failed in 16 seconds on the tag-vs-VERSION check instead of publishing a false release the way the first occurrence did.

The habit behind that tag is now recorded in `KNOWLEDGE/traps.md`: `git commit ...` followed by `git tag ...` as separate statements lets the tag outlive a failed commit and label the previous one. Chain them with `&&`. The guard works; the habit that needs it is the defect.

## 7.101.0 -- 2026-07-28 -- every exemption turned out to be an un-audited boundary

Twenty commits of hardening, and one pattern underneath all of them: the places this repo had declared out of scope were exactly the places defects were living. Not once by coincidence -- five times in a row.

**The subSaipen TEMPLATE was skipped by name, and that is where the defect was.** `extensions/subs/TEMPLATE/STATE.md` shipped a `next_action` with no legal prefix, so every subSaipen `saipen sub spawn` ever produced was born failing RFC § 1.2. It survived because the validation walk carried `if p.parent.name != "TEMPLATE"` -- the single file exempted from the check was the source every instance inherits. `phases/done.md` had the twin defect, endorsing `next_action: wait for user command`; a phase doc prescribing a state the validator rejects is worse than one that says nothing, because the agent obeys it.

**`.saipen/KNOWLEDGE/` was blanketed as "project data, not protocol text".** RFC § 1.2 makes it durable truth an agent reads before planning. Reading it -- rather than grepping it, which had reported clean -- found `traps.md` and `decisions.md` both teaching a WAIT-at-DONE rule superseded nine releases earlier, and `traps.md` describing the LOG drift check as a WARN when it is a FAIL and its WARN half had already been deleted as dead code.

**"Exempt" was doing more work than it should.** Five of seven exemptions name protocol files and three ship into every install; `SKILL.md` is the entry point telling a platform which file to read first. Exempt now means no rule-CONTENT check applies. Citations are verified everywhere, because a pointer at a section or file that no longer exists is wrong wherever it sits -- and they now resolve named protocol files too, not just `§ N.N` and `phases/*.md`.

**Checks that could not fire.** One warn category, `unknown-field`, sat behind a branch on `additionalProperties` that both call sites set to false: it had never appeared in any run ever produced. `LOG_RE` accepted a dateless line while § 1.2 calls DATE mandatory, which quietly disarmed both timestamp checks by giving them an empty harvest -- the same death as the check removed in v7.99.0, reached by another road. 125 sealed entries predate the rule, so severity splits: FAIL in the active log, one collapsed WARN for immutable history.

**And the instruments themselves lied, three times.** A harness said 20 of 20 portable-floor checks were dead (it was invoking the WSL `bash` stub). Another said 8 of 8 warn categories were unreachable and the repo was dirty (it matched an internal key that is never printed, and tested `"FAIL" in output` while the validator's own prose says FAILs). Each would have shipped a confident, false finding about a healthy subsystem. `phases/verify.md` guarded only the pole where a gate is stuck green; it now guards the other: **a run claiming total failure is a claim about your instrument first**, because a real defect is almost never total while a misconfigured harness almost always is. Run a control whose result is already known before reporting any negative.

New standing coverage rather than one-off proof: `tools/audit_floor.py` breaks a scratch project one way per check and asserts both halves of the portable floor still go red (20 checks x 2, and it found the two halves wording the same defect differently). Five fixtures now stand behind the checks guarding TEST-001, the checkpoint contract, the DONE deadlock, the tripped valve and the one-DOING rule -- failure modes with a fixture went from 3 to 8 of 93. Fail-fixtures can pin their reason with `expect_fail_contains:`, which immediately caught three that had been failing for the wrong reason for months while the suite reported green.

Also: doc coverage is accounted for -- 184 shipped documents, every one either under a check or exempt with a stated reason, which found an orphan fixture README at a phantom path tracked since `00c7557`. The locale badge line counted directories rather than checked files, so deleting a README left it reporting "all 32 match" having checked 31. And no document may now cite a version that has not shipped, a rule this release had to obey before it could be written.

CONFORMANCE 89 rows to 96.

## 7.99.0 -- 2026-07-28 -- the validator had never been linted, and nine of its own error messages were corrupt

Two threads: a review of how the four subSaipens actually did, and the first linter ever pointed at this project's own Python.

**`tools/validate.py` is 1418 lines, is the most load-bearing file here, and nothing had ever linted it.** ruff found 14 items. None were correctness bugs -- but `RUF001` found nine cp1251-mangled section signs sitting inside the validator's own `FAIL` and `WARN` messages. A section sign decoded as cp1251 and re-encoded round-trips as perfectly valid UTF-8, which is exactly why the validator's own U+FFFD corruption check could never see them. Repaired, and the doc text lint now catches that byte sequence too, since U+FFFD detection structurally cannot. CI gained a `ruff` step so it cannot rot back; `ruff.toml` carries a written reason for every rule switched off, because a lint config without reasons becomes a place to hide findings.

The cleanup itself was verified the boring way: `tools/validate.py`'s full output was captured before and after and diffed byte-for-byte. Identical. A cleanup of the file every other check depends on is worth exactly that much paranoia.

**A push claim is now adjudicated by git.** v7.98.0 shipped with `next_action` reading "shipped, committed, pushed. CI green" while three commits -- two of them changes to CI itself -- had never left the machine. Nothing could contradict the claim because nothing looked. `STATE.next_action` mentioning a push while commits sit local-only now FAILs, degrading to a WARN where there is no git or no upstream. This is the same shape as v7.93.0's read-back rule: a claim nobody verified is not a fact, and here the repository itself holds the answer.

**SubSaipen review.** Three of four did their work, and `saitranslate`'s was confirmed independently rather than taken on its word -- the `guide-wait-shape` WARN it was supposed to clear is gone. No isolation boundary was crossed, `mode: read-only` held on all four, and all six OUTBOX entries are well-formed. Both slips were bookkeeping and both were invisible until someone opened the files:

- `saipython` was spawned and never run -- 5 open tickets, 0 done, empty OUTBOX -- and looked identical to a healthy sub in `MANIFEST.md`. That now WARNs.
- `saitranslate` left `SAIT-002` at `status: ready` after its finding was collected and its main-board ticket closed. Harmless by design (PROTOCOL § 4 orders the writes so the worst case is a duplicate ticket, never a lost finding), but nothing surfaced it. `ready` entries now WARN as findings waiting on `collect`.

CONFORMANCE 69-71. Both new warnings and the push check were red-tested.

**One incident, recorded because it cost an hour.** A red test destroyed the work it was testing: an empty commit followed by `git reset --hard HEAD~1`, which also wipes the uncommitted tree -- and every `validate.py` edit was uncommitted. RFC § 1.1 calls that a destructive operation requiring confirmation, and it was applied self-inflicted, inside a test, without thought. Mutate-and-restore is safe while the blast radius is one backed-up file; a git command inside a test has the whole tree as its radius. Restored from the scratchpad scripts, which is the only reason this is a paragraph and not a lost afternoon.

## 7.98.0 -- 2026-07-28 -- drift hunt: subs README, sub states, self-transitions, adapters

Systematic drift hunt across surfaces outside validate.py coverage. Sub-sections:

- **subs README** said "Not yet field-tested" with four live instances running on this repo. Now states honest production status.
- **Sub next_action format fixed**: saipython (no prefix → `RESUME:`), saihunt (bare prose → `WAIT: user brake`), saiwiki ("Wait for user command..." → `WAIT: user brake`). All three validate.py now catches.
- **saihunt STATE** was `phase: HUNT` with board showing HUNT-001 DONE and no TODO. Transitioned to DONE.
- **Self-transition guard** in validate.py skipped *all* validation for `transition_from == phase`. Now checks the source phase is a known enum value; self-transitions are legal, but an unknown phase is always a FAIL.
- **Adapter cross-ref check** added: every `saipen/` path referenced in `extensions/adapters/*.md` must exist in the home. 9 adapters, all pass.
- **saitranslate saipen_home** used single backslashes (YAML ambiguity). Fixed to double backslashes matching siblings.

## 7.97.0 -- 2026-07-28 -- the CI that has not run all day, and a claim I made about it without looking

This one started by checking a sentence I wrote myself hours earlier. v7.96.0 shipped CONFORMANCE row 65 asserting that `validate.yml` runs both halves of the portable floor. I had not opened the workflow. It runs `validate.sh` and has never run `validate.ps1` -- which is precisely why that script's `needs:` regex drifted apart from its sibling and FAILed conformant boards until yesterday. The root cause of the v7.96.0 defect was still sitting there, under a row claiming it was covered.

**Then the worse half.** `gh run list` shows no runs at all for 2026-07-28. `c022677` removed the `push` trigger on purpose -- "no notification spam" -- leaving `pull_request` and `workflow_dispatch`. This repo has never opened a pull request; zero merge commits in its entire history. So the workflow hangs on an event that does not occur here, and the five releases shipped today (v7.92.0 through v7.96.0) went out without a single CI run. Its header meanwhile read: *"nothing actually enforced conformance on a push or a PR. This does."*

What actually gated those five releases is the pre-commit hook, installed on this machine on 2026-07-27, which runs `tools/validate.py` before every commit. That is a real gate and it did its job -- it is simply not the one the documentation credits, and it is opt-in, per-machine, and bypassable with `--no-verify`.

Fixed: `validate.ps1` added to the workflow as a `pwsh` step (it ships on `ubuntu-latest`, so this is a step and not a job); the header now states the real trigger and names the pre-commit hook as the real gate; row 65 corrected to say the scripts were verified by hand.

**Not fixed, deliberately.** Re-adding `push:` would turn this into a gate that actually fires, at the cost of a notification per push. Removing it was a considered decision by the repo owner, so reversing it is theirs to make, not something to flip back quietly while they are not looking. The workflow now says exactly that, so the next reader sees the trade rather than inheriting a false sense of coverage.

Also verified this pass, and clean: `tools/run_scenarios.py` -- 9 executable fixtures all matching their declared outcome, 33 behavioral skipped by design, including the two scenario directories added in v7.93.0.

CONFORMANCE 66 added.

## 7.96.0 -- 2026-07-28 -- the fallback validator was more permissive than the thing it stands in for

HUNT over `tests/validate.sh` and `tests/validate.ps1` -- the frozen portable floor a host without Python runs *instead of* `tools/validate.py`. Nothing had opened either file all session. Three defects, and the worst kind: a checker that says PASS when the real answer is FAIL.

**It required 7 of RFC § 1.2's 9 fields.** No `saipen_version`, no `transition_from`. So a Python-less host validated a `STATE.md` the canonical validator rejects, and got a green light. It also banned `read-only` from only `BUILD`/`SHIP`/`CLEAN`/`TRANSLATE` -- `INIT` and `PLAN` (v7.93.0) and `ADD` (v7.94.0) never reached it. Both corrected, which the file's own comment already authorises in as many words: frozen against *new* checks, never against fixing one that now contradicts the RFC.

**The two halves disagreed with each other.** `validate.ps1` matched `needs: (.*)` to end of line where `validate.sh` used `[^|]*`. So a perfectly conformant `| needs: T-252,T-253,T-254 | verify: ...` line parsed its dependencies as `T-254 | verify: ...`, and the PowerShell floor reported a dangling reference on a legal board. This one was found by running it -- this repo's own board tripped it on the first invocation. Nobody had, because the repo runs the Python validator.

**And now something checks all of it.** The drift detector parses § 1.2's required set and § 1.3's ban list and asserts both portable scripts still probe every member. That is the fifth surface added to it in four releases -- schema and validator constants (v7.93.0), phase docs and extensions (v7.94.0), guides (v7.95.0), the portable floor (now).

Worth recording how the check itself failed first: the ban half originally searched for `INIT` anywhere in the script, which can never go red, because the phase enum lists `INIT` a few lines above. It passed its own red test by accident. The fix parses the phases out of each script's own error message. **A check that cannot go red is decoration**, and the only way to find out which kind you wrote is to break the thing on purpose and watch.

CONFORMANCE 64-65 added.

## 7.95.0 -- 2026-07-28 -- the same rule failed to reach a third place, so now something looks there

A HUNT over the two surfaces this session had never examined -- `guides/` (33 files) and `extensions/adapters/` (9). The adapters came back clean: no copied field lists, no stale `WAIT:` forms, nothing to fix. The guides did not.

**All 33 guides still taught `WAIT: <question>`**, the shape from before v7.93.0 introduced the mandatory category token. Two releases changed the format underneath them and nothing looked. This is the third instance of one pattern in three releases: v7.93.0 enforced the category against `STATE.md` but not the phase docs that prescribe it; v7.94.0 fixed the phase docs and extensions; v7.95.0 finds the guides. Each time the rule was right and its propagation was manual.

So `tools/validate.py` now walks `guides/` too, at WARN rather than FAIL. The severity is the honest one: guides are not in the injector manifest and no agent boots from them, so a stale guide misleads a human reading the docs, which is real but is not a broken continuation. Making it a FAIL would also block every release until 29 translations land, and those are not Core's to write.

Core owns `en`/`ru`/`et`/`ded` by standing rule -- those four now carry `WAIT: <category> -- <question>` with the seven categories spelled out. The remaining 29 are subSaipen translation work and sit in `## BLOCKED` naming exactly that, with the validator's own WARN as the live list. The warning is expected to stay lit until they are done, which is what an honest signal looks like when the work is real and simply belongs to someone else.

CONFORMANCE 63 added.

## 7.94.0 -- 2026-07-28 -- three of six defects were mine, from the last two releases

The question this release had to answer was whether the last three were going in circles. They were not, but the pattern changed and that is worth naming: v7.92.0 and v7.93.0 found defects older than themselves -- one dead check had been dead since `feae149`. This round, three of six findings were introduced by those same two releases. New rules were outrunning their own propagation. The fix is not more rules; it is making propagation mechanical, which is what most of this release does.

**A recognized command is not a legal transition.** § 1.10 has always said "the transition table's only route into `SHIP` is from `REVIEW`". The validator has had `SHIP` in its from-any-phase set since v7.83.0, and in v7.92.0 I copied that into § 1.6's text -- so one half of the protocol told an agent to run the gates while the other half made jumping straight to `phase: SHIP` a legal transition. Worse, v7.93.0's cross-document drift detector then certified the agreement, because both sides now said the same wrong thing. `SHIP` is out of the transition set; `saipen ship` stays recognized from anywhere and now says concretely what it writes: the next unmet gate on that ticket's chain, `PHASE SHIP` only after `REVIEW` passes, and `WAIT: blocked -- saipen ship has no verified work to ship` when there is nothing to ship at all.

**A rule has to reach the docs that emit it.** v7.93.0 made the `WAIT:` category mandatory and enforced it against `STATE.md` -- while `blocked.md`, `build.md`, `clean.md` and `extensions/subs/PROTOCOL.md` went on prescribing category-less WAITs. An agent following its own phase doc verbatim produced a state this validator then failed. All four fixed, and the drift detector now walks `phases/` and `extensions/` for any prescribed `next_action: WAIT:` and FAILs a missing category. It found the fourth one itself, seconds after being written.

**`BOOT.md` still told agents to re-read only `STATE.md`** after a checkpoint, three days after § 1.5 started requiring all three. Same self-inflicted class, same fix: BOOT points at the rule instead of paraphrasing half of it, and now also carries § 1.11's priority order for a cold agent that must decide what to do at all.

**RECOVER had a hole exactly where it hurts.** Its triggers were unreadable, missing-field, or contradicted-by-LOG/BOARD. A `next_action: continue work` is none of those -- present, non-empty, contradicted by nothing -- so a conformant agent fell through to FINISH or START and *executed* a value § 1.2 calls non-conformant. RECOVER now covers a `next_action` that fails § 1.2's prefix or category checks, with the `DONE` + empty-board invalid-`WAIT:` case still routed to UNBLOCK's auto-transition instead.

**The Pick Rule never said which ticket to pick.** It defined eligibility and stopped, inside the section named Determinism Invariants -- two conformant agents handed one board could choose differently and both be right. It is now the topmost workable line, which is what § 2.4's Entry already assumed when it inserts a new objective's tickets at the top.

Smaller: `read-only` now bans `ADD`, whose entire work product is tickets -- the principle in § 1.3 covered it, the enumeration did not. `§ 1.5` checkpoints after a phase transition too, since one ticket walks four phases and a crash mid-walk left `STATE.phase` naming a phase the work had left. And `README.md` promised auto-`HUNT` on an empty board with no mention of § 2.1's `BLOCKED` exception -- the single place a weak agent walks straight past a real blocker to go find busywork.

Rejected from the patch, with reasons: adding a `-> BLOCKED` line to every phase doc (§ 1.6 states outright that `-> BLOCKED` is universal, not per-phase vocabulary, and that a doc's silence never removes it -- adding nine copies is the second constitution the same patch objects to); deleting CONFORMANCE row 43 (it is a tombstone from the v7.86.0 duplicate-43 incident, and removing it invites reuse); and rewording the LOG skeleton again, which already says exactly what the patch asked for and has now been misread by three separate audits.

CONFORMANCE 61-62 added. Enforcement: 23 mechanically-checked rows of 62.

## 7.93.0 -- 2026-07-28 -- a dead check, a deadlock I shipped myself, and the diet that actually mattered

Three more audit patches arrived. Verifying them first turned out to matter more than applying them: a good half described a tree that no longer existed, one would have re-introduced a deadlock, and the same false claim about LOG lines arrived for the third time. What survived verification was real, and shipping it surfaced four defects nobody had reported.

**I shipped a contradiction in v7.92.0 and it took one release to find.** § 1.2 whitelisted two `WAIT:` forms at `DONE` with an empty board; § 1.11's new UNBLOCK exception, added in the same release, allowed one. Whichever section an agent read decided whether a legitimate user brake was a deadlock to break. Both now name the same two, and § 1.11 defers to § 1.2 if the whitelist ever changes. Related, same section: "Anything else in that exact state is non-conformant" read as banning every `next_action` except `WAIT:` -- which would forbid the `PHASE HUNT` that § 2.1 requires from precisely that state, i.e. ban the only conformant exit.

**A validator check had never once fired.** Row 42's LOG timestamp guard, added in `feae149`, anchored its regex at `^(\d{2})\.` against lines that begin `- DD.MM.YY`. It matched nothing, ever. That is also why nobody noticed the second half: it compared `abs(now - last_entry)`, so had it worked it would have warned on every repository idle for an afternoon -- a project nobody touched today is not a corrupt project. Removed. The two checks RFC § 1.2 actually asks for were already there and correct: signed >3h-in-the-future FAILs, >5min-backwards between consecutive events WARNs.

**`WAIT:` now carries a category, and the set is closed.** § 1.11 has always named the guessing agent as the one failure this protocol cannot detect afterwards. Its twin is the stopping agent: `WAIT: need more context` is byte-identical in shape to a real authorization gate, passes every check, and parks the project on a question nobody can answer. Seven tokens -- `manual-verify`, `destructive-op`, `first-publish`, `user brake`, `blocked`, `safety valve`, `init` -- make the two mechanically separable at a cost of one word, and tell the human what kind of answer unblocks it. Five live call sites in the phase docs and the STATE template were updated; both already-fixed wordings (`safety valve`, `user brake`) matched without churn.

**Cross-document drift is now detected instead of stumbled upon.** v7.92.0 found the required-field list living in five documents with five different answers. v7.93.0 found the from-any-phase list living in three with three. Both were caught by a human reading two files side by side, which is luck with extra steps. `tools/validate.py` now parses six sets straight out of RFC.md -- required fields, phase enum, from-any-phase, read-only bans, `next_action` prefixes, `WAIT` categories -- and FAILs when the schema or the validator's own constants disagree, plus FAILs if BOOT or CONFORMANCE re-enumerate the field set at all. A moved RFC anchor is itself a FAIL: a drift check that quietly stops checking still prints PASS. Seven desync fixtures, one per check.

**Then the protocol caught me.** Pivoting into goal mode failed validation instantly: `REVIEW -> PLAN` is not a legal transition, yet § 2.4 mandates a `PLAN` for the new objective from wherever the pivot lands, and § 1.10 had listed `saipen plan` as a from-any-phase command all along. Two rules followed exactly, one invalid state. Later, a board write silently did nothing -- a pattern substitution whose anchor did not match, followed by a hardcoded success message -- and eleven tickets of work went by with an empty `## TODO`, the validator green the whole time, because an empty board is perfectly conformant. § 1.5 now requires reading back all three checkpoint writes, not just `STATE.md`. The generalization is the part worth keeping: **a write you did not read back is a claim, and a success message your own tool printed is not evidence.**

Smaller, same shape. `saipen stop` opened with "Overrides `goal_mode`" two clauses above the paragraph explaining `goal_mode` is untouched -- a weak model executes the first clause it can. § 1.11's FINISH said "under your own claim", so a crash-orphaned `## DOING` was skipped, a second ticket claimed, and the board failed § 1.11's own one-DOING rule. `read-only` banned four writing phases and not `INIT` or `PLAN`, which write `.saipen/` and `BOARD.md`; the principle above the list was right all along, the list read as exhaustive. § 2.1 stated its halt test two different ways, and a ticket with unsatisfied `needs:` passed one and failed the other. The ticket-less phase list is now derived as the complement of the five ticket-bearing phases instead of hand-kept, so it cannot drift. Recovery gained a `## DOING`-wins rule and, like `saipen stop` before it, an honest read-only branch -- rebuilding `STATE.md` is a write.

**The diet, measured rather than argued.** The critique that the protocol is bloated is fair, and the fix was not where anyone was pointing. A cold start reads `BOOT.md` + `STATE` + `BOARD` + the LOG tail: 66.9 KB, of which 55 KB was `LOG.md`. RFC.md is not in that path at all. Sealing the log took the cold-start read to **14.5 KB, down 78%**. RFC.md itself was trimmed ~4.9 KB (four incident narratives moved into the `tests/scenarios/` directories that already name them, twenty-odd restatements compressed, MUST/SHOULD/MAY counts unchanged) -- but it still grew this release, because sixteen new rules landed in it. That is the honest trade and worth stating plainly rather than claiming a diet that did not happen.

Sealing the log also exposed a gap in its own rules: § 1.2's idempotency check guards a crash between steps 1 and 2, when the active log is still a prefix of the segment. After a *successful* seal the active log is a new file, so a second run sails past that test -- which is exactly what happened when the script was re-run to test it, producing a 0.4 KB segment. Folded back, repair LOGged, and § 1.2 now states the outer guard: sealing does not begin unless the cap is crossed.

CONFORMANCE 54-60 added; row 43 retired into 54, which described the same board at a different severity. Enforcement ratio: 15 mechanically-checked rows of 55, now 21 of 60.

## 7.92.0 -- 2026-07-28 -- the required-field list existed in five places and all five disagreed

An external audit patch arrived proposing 16 protocol fixes. Seven carried real weight, one would have re-introduced a deadlock fixed six releases ago, and roughly half was already in the tree. This release ships the seven, plus two more holes found while shipping them.

**Five copies of the required STATE fields, five different answers.** RFC § 1.2 listed eight. § 1.5's checkpoint self-check listed the same eight. `BOOT.md` listed ten (it counted `schema_version`). `CONFORMANCE.md` row 44 said "all eight required fields". `state.schema.json`'s `required` array held eight. And `tools/validate.py` had been failing any state without `transition_from` since v7.82.0 -- so whichever document an agent happened to read, it was reading a different rule from the one being enforced. § 1.2 is now the single place the set is written down; the other four point at it. The schema gained an explanation of why its `required` array is deliberately narrower (JSON Schema cannot say "except on a fresh INIT"), so a reader can no longer mistake "absent from `required`" for "optional".

**A `WAIT:` at `DONE` with an empty board deadlocked the project.** § 1.11's UNBLOCK step said stop on any `WAIT:`; § 2.1 says an empty board at `DONE` MUST auto-transition to `HUNT` without asking anyone. A state hitting both froze permanently -- nobody was coming, and the `WAIT:` named no answerable question. `tools/validate.py` had flagged it since v7.86.0, meaning the tool was right and the constitution was wrong. § 1.11 gained an exception exactly three conditions wide. To keep the FAIL from catching a legitimate pause, both surviving `WAIT:` forms now have fixed wording -- the § 2.4 valve, and `WAIT: user brake -- <reason>`. A pause nobody can distinguish from drift is drift.

**The tripped safety valve had no pinned shape, and the obvious "fix" was a trap.** The audit proposed setting `phase: BLOCKED` on a trip. That would have restored the exact deadlock v7.86.0 removed: `BLOCKED` is a § 2.4 Exit condition, Exit clears `goal_mode`, and with `goal_mode: false` the bare `saipen goal` the valve's own message tells the user to run is illegal under § 1.10. The valve would destroy its own continuation path. § 2.4 now pins all five fields of the tripped state, and names `phase` as the one that must not be touched. `tools/validate.py` enforces both halves.

**`## DONE` was being ordered to lie.** § 1.2 requires inline work to reach `## DONE` before SHIP; § 1.6 forbids marking any ticket `DONE` without a successful `VERIFY`. Read together, an agent under ship pressure could conclude the protocol wanted `[x]` on work nothing had checked. Inline work now reaches `## DONE` only with a verify trace -- a `| verify:` criterion that actually ran, or a `RUN:`/`H:` line proving it. No trace, no `DONE`, and SHIP stays blocked, which is the correct outcome rather than a problem to route around.

Smaller, same shape: `saipen stop` ordered `mode: read-only` to write `digest.md`, which that mode exists because it cannot do -- it now reports the three lines in chat instead. § 1.11's "one ticket at a time" said "an agent" while the validator failed any board with two `## DOING` tickets, inviting the reasoning "that one isn't mine, so I may claim a second"; it says "in total" now. § 1.2's own progress-tag example was non-conformant under § 1.19's prefix rule -- an example that fails its own rule is worse than no example, because a weak model copies the example and never reaches the rule. And three of the five legal `next_action` prefixes were listed but never defined, passing every shape check while telling an agent nothing; all five now have an argument grammar.

**Two holes found while shipping the other seven.** The pivot into goal mode failed validation immediately: `REVIEW -> PLAN` is not a legal transition, yet § 2.4's Entry mandates a `PLAN` for the new objective from wherever the pivot happens, and § 1.10 had listed `saipen plan` as a from-any-phase command all along. § 1.6's list said five such phases, the validator's set held six, § 1.10 implied seven. Two rules followed exactly, one invalid state. `PLAN` joined both; `SHIP` was added to § 1.6's text, where it had been missing since v7.83.0 put it in the validator. Then `extensions/subs/PROTOCOL.md` gave up its last three convenience copies of Core shapes -- the board ticket line, the LOG skeleton (which showed every optional bracket as mandatory), and the STATE field list. That last one admitted in its own text that it had drifted: between v7.82.0 and v7.88.0 it promised "no extra required fields" while the validator required two more, so any subSaipen built from it was born non-conformant. Removed rather than corrected again, for the same reason Core collapsed its own five.

`BOOT.md` went from 84 lines to 70, 5609 bytes to 3760 -- incident prose that duplicated RFC, and the field list that made it one of the five disagreeing copies. It now defines no rule at all, only the order of execution, so there is nothing left in it that can drift from RFC. Cross-references of the form "BOOT.md step 4" were replaced with named ones in RFC, CONFORMANCE, `validate.py`, and one fixture: step numbering is precisely what broke the moment the file was edited.

Rejected from the audit and worth recording: the claim that LOG lines have no leading dash (they do -- the regex requires it and every live line has one); moving RFC's incident prose into `.saipen/KNOWLEDGE/` (that directory is project memory, and protocol rationale living there violates § 1.7's workspace hygiene); and downgrading `last_event` from RECOMMENDED to MAY, which weakens a norm rather than fixing a hole.

Enforcement ratio: 13 mechanically-checked CONFORMANCE rows of 53, now 15 of 55. Every new check was break-tested before being trusted -- `transition_from` removed, three `WAIT:` variants at `DONE`, four tripped-valve fixtures. All red where they should be, green where they should be.

## 7.91.0 -- 2026-07-27 -- the only channel out of a subSaipen had never been validated

Continuing the push to move rules from prose into enforcement.

**`kitchen/OUTBOX.md` was completely unchecked.** `tools/validate.py` had zero mentions of it. That file is the single door out of a subSaipen (`extensions/subs/PROTOCOL.md` § 1) -- everything a read-only worker ever hands back passes through it -- and a malformed entry became a bad `collect` in silence. Now checked: a recognized `status:`, and on `ready` a `summary:` and `critical:` (the two fields `collect` actually reads to decide what to do with it). An entry carrying a `patch:` additionally needs `base_head:` and `verified:` per § 9, because a diff with no provenance is one nobody can re-check before applying it.

**MARKHUNT findings now have to carry their evidence.** `phases/markhunt.md` has always said "no cite, no ticket" -- every finding recorded with a real `file:line` or command output in its `| blocker:` -- and nothing enforced it. A `[MARKHUNT]` ticket whose blocker reads only "unvetted audit" now FAILs. That rule is the whole thing separating a dry audit from a generator of confident-sounding vibes, and it was running on trust.

Six deliberate breaks before trusting any of it: a patch marked ready without `base_head`/`verified` (both flagged), `ready` without `summary`, a status of `probably-fine`, a MARKHUNT ticket with a bare blocker, and the same ticket with a real citation passing clean. This repo's own three live OUTBOX entries pass.

Enforcement ratio moved from 9 mechanically-checked rows of 49 to 13 of 53. The remaining 28 behavioral rows are still the honest majority, and the reason has not changed: a guessed finding and a known one are byte-identical, so no check can separate them. What changed is that four things which *did* leave a checkable trace stopped relying on good behaviour.

## 7.90.0 -- 2026-07-27 -- two invariants shipped as prose, now actually enforced

Measured the enforcement ratio for the first time: of CONFORMANCE's 49 rows, 9 were mechanically enforced and 28 were behavioral-only. Roughly a fifth held by tooling, the rest by agents behaving.

Some of that gap is permanent -- "did you guess or did you know" leaves no artifact, and no validator will ever rule on it. But some of it was just unbuilt, and two of the unbuilt ones were invariants shipped days earlier in this same session:

- **One ticket at a time** (§ 1.11, v7.86.0) -- nothing counted `## DOING` entries. The rule existed to stop ticket-hopping (claim T-12, drift, claim T-27, drift) and had no way to notice it happening. `tools/validate.py` now FAILs a board carrying more than one.
- **Goal counters leave a countable trace** (§ 2.4; the three phase docs were fixed in v7.87.0) -- nothing verified the result. A non-zero counter with no matching `DEC: goal_waves N->M` in any LOG segment now WARNs: § 1.5's Recovery rebuilds those counters by counting exactly those lines, so their absence means a crash losing `STATE.md` loses the safety-valve budget with it. WARN rather than FAIL, since states written before v7.87.0 legitimately lack the lines and a sealed segment may hold an old run's.

Both break-tested: two `## DOING` tickets goes red, non-zero counters with no `DEC:` line warns, this repo passes clean.

Worth stating the ceiling honestly, since the question came up: `ruff`/`mypy`/`pytest` can be merciless about Python because they read the artifact and rule on it. SAIPEN's artifacts -- `STATE`/`BOARD`/`LOG` -- are judged just as hard, and there are 17 checks doing it. What cannot be mechanized is the part where the artifact looks correct either way: a guessed finding and a known one are byte-identical. That is not a tooling gap to close, it is why § 1.11 states the rule and `phases/verify.md` insists on breaking a gate before trusting it. The honest split is: shape and consistency get enforced, judgement gets stated and audited.

## 7.89.0 -- 2026-07-27 -- `next_action` was checked for shape but never for vocabulary

Full protocol re-sweep. Cross-references came back clean -- every `§ N.M` cited across RFC, BOOT, CONFORMANCE, SKILL, PROTOCOL, crew.md and all 16 phase docs resolves to a section that exists, and every fixture named in CONFORMANCE exists on disk. So the sweep went at the one thing never tested directly: whether this repo's own state actually passes TEST-001.

It did not. `STATE.md` read `next_action: "saipen hunt ..."` -- and **`saipen hunt` is not a command.** RFC § 1.10's list is closed and does not contain it; `HUNT` is a phase reached autonomously via § 2.1, never invoked by name. § 1.10 requires a cold agent facing an unrecognized `saipen <word>` to decline and stop, which means the gold-standard continuation test failed on a state that looked entirely healthy -- and which the validator had passed, twice, because the `next_action` check verified the *prefix* (`WAIT:`/`saipen `/`PHASE `/`RUN:`/`RESUME:`) and never the word after it. An entire class of "looks executable, isn't" walked straight through.

Both halves fixed. The check now resolves the verb against § 1.10's actual list, and the live state was corrected to `saipen continue` -- which is right anyway: the board is empty and `goal_mode` is false, so § 2.1 auto-transitions to `HUNT` without anyone naming it.

Verified in both directions, per `phases/verify.md`: the new check fired on this repo's own `STATE.md` before the repair, went quiet after it, accepted `saipen continue` / `saipen sub collect` / `saipen goal <text>` / `saipen markhunt`, and rejected `saipen hunt` and `saipen frobnicate`.

Worth noting who wrote the bad value: I did, twice this session, while shipping rules about exactly this kind of drift. The shape check gave it a green light each time. That is what a gate checking the wrong property looks like from the inside -- not obviously broken, just quietly permissive.

CONFORMANCE row 49.

## 7.88.0 -- 2026-07-27 -- a subSaipen had no way to say "I don't know"

subSaipen pass, closing the priority Core > phases > subSaipens.

**The real gap.** RFC § 1.11 requires an agent short of a fact to stop and write a `WAIT:` naming it. A subSaipen cannot do that -- it has no `WAIT:` any human reads, its own `STATE.md` is nobody's dashboard, and its single door out is `kitchen/OUTBOX.md`. So the invariant existed in Core with no expression where a sub could obey it. `status: blocked` already existed for "waiting on something external"; it is now also the documented home for "I do not have enough information", with the missing fact quoted in `details`.

This is the sub failure mode that matters most, because it is the only one the main agent cannot catch. Everything else is mechanically detectable at collect: a boundary violation shows in `git status`, a stale `main_project_refs` fails its freshness check, a patch cut against an old `base_head` will not apply. A guess arrives looking exactly like knowledge -- correctly formatted, confidently worded, `status: ready`, and wrong -- and the main agent then tickets it as fact, laundering the error onto the project's own board. `blocked` costs one round trip; a swallowed guess costs however long it takes someone to notice what got built on it.

**§ 8's field list had gone stale**, which is the same drift class this session keeps finding. It enumerated the required fields and stated "No extra required fields" -- while `transition_from` had been required since v7.86.0 and `schema_version` was validator-checked. The live instances and `TEMPLATE/STATE.md` both carry them (a fresh spawn validates clean, verified), so nothing was broken in practice; the authoritative prose was simply wrong, and anyone writing a state from that list by hand would have produced a non-conformant one. Fixed, and the list now says outright that it is a convenience copy which goes stale -- `TEMPLATE/STATE.md` is the copy that cannot, since `spawn` copies it verbatim and the validator checks it.

Also stated plainly: **Core's § 1.11 invariants bind a subSaipen too** -- one ticket in its own `## DOING` at a time, every run leaves a trace in its own `LOG.md` including "found nothing", same fixed action priority. A subSaipen is a SAIPEN instance, not a lesser thing.

CONFORMANCE row 48 + the `subsaipen-blocked-not-guessed` fixture.

## 7.87.0 -- 2026-07-27 -- Recovery's counter rebuild was unexecutable: nothing ever wrote the events it counts

Phase-doc pass, per the priority Core > phases > subSaipens.

§ 2.4 requires every `goal_waves`/`goal_tickets` bump to leave an identifiable LOG line (`DEC: goal_waves N->M`), and § 1.5's Recovery rebuilds the counters after a crash by *counting those lines*. Three phase docs actually bump a counter -- `add.md`, `plan.md`, `verify.md` -- and **none of them mentioned the line**. So the events Recovery is instructed to count were never written by anybody: the rebuild path was dead code, and a crash that lost `STATE.md` lost the safety valve's count with it, on exactly the long unattended runs the valve exists to protect.

All three now name the exact line at the point of the bump, with the reason attached, since a rule whose purpose is invisible is the kind that gets dropped in the next rewrite.

Found alongside it: **`add.md` had no closing LOG instruction at all** -- the only phase doc missing one, which is how the `goal_waves` line went unwritten there longest. It is also the phase that creates and claims tickets and performs the mature-exit that clears `goal_mode`, so its silence covered the three events most worth recording. It now ends like every other phase: one Event Graph line for whichever branch it took, including the case where it found nothing -- RFC § 1.11 requires a session to leave a trace, and "ADD ran and found nothing" is a real finding, not a reason for silence.

Swept the other 13 phase docs against the new § 1.11 invariants at the same time. The `assume`/`probably` hits were all false positives -- `markhunt.md`, `prepare.md` and `translate.md` mention those words only to forbid them ("'probably', 'seems like' are vibes, not evidence"; "verify coverage is real, not assumed"). Nothing else contradicted the invariants.

## 7.86.0 -- 2026-07-27 -- the safety valve made its own escape hatch illegal, plus four determinism invariants

**The Core deadlock.** § 2.4's safety valve stops an autonomous run at 3 waves / 20 tickets and tells the user to "re-invoke `saipen goal` to continue". § 2.4's Exit list then set `goal_mode: false` on a valve trip. But § 1.10 recognizes bare `saipen goal` ONLY while `goal_mode: true` -- so tripping the valve made the single documented continuation path illegal in exactly the state the trip produced. The objective could not be continued at all, only replaced by `saipen goal <text>`, which demotes the board and re-plans: a substitution, not a continuation.

Resolved by naming what a valve trip actually is -- a budget pause awaiting re-authorization, the same shape as `saipen stop`, which was likewise never on the Exit list. The valve is off that list now; the two real exits (mature `ADD`, session `BLOCKED`) are the objective genuinely ending, which a trip is not. What stops a restart from walking straight past the valve is the counters, not the flag: `goal_mode: true` with `goal_waves >= 3` or `goal_tickets >= 20` *is* the tripped state, an agent resuming into it MUST re-state the stop rather than continue, and bare `saipen goal` resetting both to `0` is precisely the human's re-authorization. No new field -- and § 1.2's safety-valve `WAIT:` category already presumed this design, which is how the contradiction surfaced.

**New § 1.11, Determinism Invariants.** Four rules closing places where the protocol said "the agent decides" and two models would decide differently. Deliberately not new machinery -- no files, no fields:

- **Action priority is fixed**: RECOVER > UNBLOCK > FINISH > START > MAINTAIN, first match wins, no weighing. Previously nothing said whether a corrupt STATE or a blocked session or an in-flight ticket went first.
- **One ticket at a time**: at most one `## DOING` per agent. Finish it, block it, or demote it with a LOG line before claiming another. Without this a weak model ticket-hops and leaves three tickets whose state nobody can determine.
- **A session MUST leave a trace**: a LOG line, a BOARD change, a STATE change, or a project file change. If none happened the session did nothing and must say so, rather than summarising activity in chat -- a run whose entire output lived in a conversation is indistinguishable from one that never ran.
- **Insufficient information is a stop, not a guess**: if writing the next action needs a sentence beginning "presumably" or "I'll assume", the information is insufficient by definition -- `WAIT:` naming the exact missing fact. Guessing is the one failure this protocol cannot detect afterwards, because a wrong guess produces confident, well-formed, fully-logged work that looks exactly like right work.

**Recovery is now required to be idempotent** (§ 1.5). `continue -> crash -> continue -> crash -> continue` is the expected life of an autonomous run, so recovery that is only safe the first time is worse than none -- the crash it exists to survive is what invokes it repeatedly.

Also repaired, both shape-only per `phases/validate.md`: a `LOG.md` entry dated `27.07.27` (a year ahead -- caught by the timestamp freshness check), and a `next_action` rewritten as lowercase prose that no longer matched any recognized form.

Checked and deliberately **not** added, because they already exist: the infinite-`VERIFY` guard (`phases/verify.md`'s 3-hypothesis / 2-fix-cycle caps plus hysteresis), multi-source Recovery (§ 1.5 already reconciles `git status`, `LOG`, `BOARD` and mtimes), and evidence requirements on findings (`HUNT`/`MARKHUNT` both require a citation per finding).

## 7.85.1 -- 2026-07-27 -- two pre-commit installers were fighting over one file

`githooks/` shipped a `pre-commit` hook doing the locale badge-drift check, with install instructions to symlink it into `.git/hooks/pre-commit`. `tools/install_hook.py` writes that same path, with a hook that runs the full `tools/validate.py`.

So the repo shipped two competing installers for one file. Whoever ran second won, silently, and a user following either doc lost the other's protection without being told. Worse, the contest was pointless: `validate.py` has done the locale badge check since v7.81.0, so the specialised hook duplicated logic the general one already ran, while displacing every other check it carries -- schema, LOG graph, manifest, injector wiring.

Retired `githooks/`. Nothing is lost: the check it performed runs on every `validate.py` invocation, which is what `tools/install_hook.py` installs, and what CI runs. It was also undocumented outside subSaipen internals -- absent from README, GUIDE, CONTRIBUTING and SPEC -- so no user-facing instruction pointed at it.

Also repaired a stale checkpoint, caught by the rule shipped one version earlier: `STATE.md` still read `agent: opencode` / `updated: 02:22:30Z` twelve hours later, after five LOG entries and two ships by a different agent, with a `next_action` naming work already committed. v7.85.0's own staleness signal -- `agent:` is not you, `updated:` older than your last write -- flagged its own author. Fixed.

## 7.85.0 -- 2026-07-27 -- the returning agent is the dangerous one, not the cold one

§ 1.1 has said "MUST NOT rely on chat context for project state" since the beginning, and it reads as advice for a cold agent -- which is the harmless case. A cold agent has no memory to mislead it; `BOOT.md` is written for exactly that reader.

The warm agent is the problem. It worked here before, it remembers real specifics, and it is wrong because somebody else moved the project in between. Recollection feels like knowledge, so nothing prompts a re-read, and the resulting mistakes come out stated with full confidence.

This was found the honest way -- by doing it. An agent resumed this repo believing it had last shipped `v7.80.0`. Another agent had taken it to `v7.83.0` in the meantime: 36 logged events and an entire subSaipen refactor. It was one step from reviewing "the protocol" against a three-version-old mental model and reporting those findings as fact. It noticed only by chance, spotting a field in `tools/validate.py` it knew it had never written.

The fix costs one comparison and needs no new field, since both already exist:

- `STATE.md`'s `agent:` is not you -> someone else wrote the last checkpoint.
- `STATE.md`'s `updated:` is newer than your own last write -> the project moved without you.

Either one means memory is stale by definition: re-read `STATE`, `BOARD` and the active `LOG` tail, and treat every prior belief -- versions, ticket states, what you think you shipped -- as unverified until a file says otherwise. RFC § 1.1 states it; `BOOT.md` opens with it, since that is the file a resuming agent actually reads.

Confident staleness is worse than ignorance, because ignorance asks. CONFORMANCE row 44 + the `returning-agent-stale-memory` fixture.

## 7.84.0 -- 2026-07-27 -- a checkpoint you cannot resume from is not a checkpoint

Two things land together: a subSaipen layout refactor that had been sitting complete-but-uncommitted in the working tree, and a protocol fix found while reviewing it.

**The protocol fix.** A checkpoint written earlier in the day produced a `STATE.md` with `next_action` and `blocker` simply absent -- both REQUIRED by § 1.2. Nothing stopped it. `tools/validate.py` catches it, but the pre-commit hook only fires at commit time and that checkpoint was never committed, so the project's *live continuation state* was a file no cold agent could boot from. `next_action` missing means `CONFORMANCE.md`'s TEST-001 fails outright -- the single guarantee this protocol exists to make -- on a project that otherwise looked completely healthy.

§ 1.5 already ordered the three writes LOG -> BOARD -> STATE so a crash always leaves `STATE.md` behind the others rather than ahead. That guards the gap *between* steps. It said nothing about a step producing a malformed file. Meanwhile § 1.4 has had the guard for the analogous case since v7.28.0: after writing a claim, re-read `BOARD.md` and confirm the claim survived. Identical failure mode; only one of the two paths was protected.

Now symmetric. RFC § 1.5 and `BOOT.md` step 7 both require re-reading the `STATE.md` you just wrote and confirming all eight required fields survived -- and where a validator is reachable, running it, since that is cheaper and more reliable than eyeballing. CONFORMANCE row 43 + the `checkpoint-self-confirmation` fixture.

The broken state itself was repaired under `phases/validate.md`'s shape-only rule: the two missing fields restored from facts already on the board and in the log, no history rewritten.

**The refactor** (by the preceding agent, reviewed before shipping rather than taken on trust): the shipped library at `extensions/subs/` no longer carries live per-instance state. `saihunt`/`saipython`/`saitranslate`/`saiwiki` each kept a `STATE.md`/`BOARD.md`/`LOG.md`/`OUTBOX.md` inside the distributed library -- meaning every consumer received one machine's working state as if it were a template, the same class of defect as the absolute path removed in v7.72.0. Instance state now lives in `.saipen/extensions/subs/`, the library holds only `TEMPLATE/` plus the shared reference files, and `MANIFEST.md` points at the live paths. Verified before committing: no dangling references to the deleted paths, all four live instances schema-valid and `read-only`, `saipen sub spawn`'s prerequisites intact, injector wiring green. CONFORMANCE row 29 updated -- it still named the now-deleted library dirs as the pass case.

Version badges bumped across `README.md`, `CONFORMANCE.md` and all 32 locale READMEs. A version string is a mechanical substitution, not a translation, so `phases/translate.md` § 2's Core/subSaipen split does not apply to it.

## 7.83.0 -- 2026-07-27 -- transition_from + BOOT cold-start sync finished

`STATE.md` gained an explicit `transition_from` field tracking the last phase transition, and `tools/validate.py` validates every non-self transition against RFC § 1.6's table (including from-any-phase user commands). Five phases were already covered by a conceptual-only CONFORMANCE row; that row is now mechanical.

The BOOT cold-start chain is now authoritative for all cold-start paths -- bare agents paste BOOT.md first, then RFC + STYLE. All three adapter files (README.md, generic.md, claude.md) updated to match. SKILL.md frontmatter corrected from "boot RFC.md loads always" to "boot BOOT.md first." The README cold-start paragraph synced to the same chain (STATE -> BOARD -> LOG -> human_note -> next_action) that BOOT.md already defined.

STATE snapshot no longer parks on DONE+WAIT with an empty board (RFC § 2.1 auto-transition). LOG-001.md:660's illegal `[T-119..T-121]` ticket-range reference replaced with `[T-none]`.

CONFORMANCE row 14 (invalid phase transition): automated via transition_from.
CONFORMANCE row 43 (DONE+WAIT auto-transition guard): enforced by validate.py.
validate.py: SHIP added to ANY_FROM (enterable from any phase per RFC § 1.10, was missing).

## 7.82.0 -- 2026-07-27 -- versioned translation templates

Backfilled from tagged commit `40a6304`. VERSION and every translated README moved to 7.82.0, and the shipped translation template gained the current badge and continuation metadata. This entry repairs the non-destructive half of the historical release ledger; no tag was created or changed.

## 7.81.0 -- 2026-07-27 -- hunt, translation, and badge drift guard

Backfilled from tagged commit `e2ded74`. The release integrated the saihunt sweep, refreshed Russian, Estonian, and Ded translation artifacts, and added a pre-commit guard against translated README badge drift. The tag's commit still carries VERSION 7.80.0; this entry records what the published tag actually names rather than rewriting it or pretending its metadata was clean.

## 7.80.0 -- 2026-07-26 -- status answers the question people actually ask

Almost nobody runs `saipen status` to find out which phase they are in. They run some form of *"is this in good shape, and does anything need me?"* -- twice in this session's own transcript. The command answered only the first kind of question, so an agent that had been in the conversation answered the second from chat scrollback, and a cold agent -- the whole point of this protocol -- could not answer it at all.

Anything reconstructed from scrollback is not state. `status` now reports, alongside phase / in-flight ticket / queue, each line omitted when empty rather than padded with "none":

- **Waiting on you** -- every open `WAIT:` and every `## BLOCKED` ticket whose blocker names a human decision, quoted as the concrete question. The human's to-do list, and the most useful line in the report.
- **Claimed but unproven** -- work finished but whose `| verify:` never ran, or ran only `conf: low`/`med`. "Done" and "verified" are different states, and conflating them is how a project feels healthier than it is.
- **Conformance** -- the last recorded `tools/validate.py` result and when, or plainly that none is recorded, which is itself the answer. Never re-run it: `status` is read-only and a validator run is work.
- **Staleness** -- how old `STATE.updated` is, when the gap is large enough to matter. A tidy board nobody has touched in three weeks is not a tidy board from an hour ago.

It reports; it does not pronounce. No "healthy", no "ready", no "good to ship" -- an agent grading its own work is the least valuable opinion in the room, and `phases/verify.md`'s manufactured-confidence warning applies to prose exactly as it does to a green check. Where `kitchen/digest.md` is a snapshot *left behind* at ship/stop, this is the same picture *asked for* live; on disagreement, say so and trust the live files.

Dogfooded against this repo before shipping: every field the spec demands is derivable from `STATE`/`BOARD`/`LOG` alone, nothing requires memory. On this repo it immediately surfaces the honest caveat -- `T-170`'s `verify:` explicitly needs a live re-test that has never happened.

CONFORMANCE row 41 + `status-answers-the-real-question` fixture (behavioral, README-only, correctly declaring no expected outcome so the new runner skips it).

## 7.79.0 -- 2026-07-26 -- the test suite runs now

`tests/scenarios/` held 34 fixtures that nothing had ever executed -- no script, no CI job, no phase doc -- and that could not have passed if anything had: most shipped only the single file their concept concerned. v7.75.0 stopped CONFORMANCE.md from overstating them. This makes them real.

- **Completed the four partial fixtures.** `blocked-ticket` got the LOG its own README says the agent writes; `dependency-cycle` and `multi-agent-claim-conflict` got STATE+LOG; `resume-after-crash` got a BOARD carrying the very ticket its `STATE.task` names. Nothing was invented to make anything pass -- each added file states what that fixture already claimed in prose.
- **Every executable fixture declares its expected outcome** as `expect: pass` or `expect: fail` in its README. The 25 behavioral ones declare nothing, correctly: there is nothing to run, and a declaration there would be a promise no one keeps.
- **`tools/run_scenarios.py`** runs each and holds it to that declaration. It is built not to rot into a no-op: a fixture with a `.saipen/` and no `expect:` is an error, a behavioral fixture that declares one is an error, and a run that collects zero fixtures exits non-zero rather than reporting success.
- **Wired into CI** and added to the runtime manifest, so it cannot quietly stop shipping.
- **Broken on purpose three ways** before being trusted, per `phases/verify.md`: flipped a declaration, deleted an `expect:` line, corrupted a fixture's actual state. Red each time, green again after restoring.

One fixture also contradicted itself and now says so: `multi-agent-claim-conflict` describes an *active* claim (under 15 minutes, RFC § 1.4) while carrying a fixed past `claim_time` that reads as stale. That is unavoidable in a checked-in file -- any "fresh" timestamp goes stale tomorrow -- so the README states it plainly rather than leaving a reader to trust a sentence the data contradicts.

Result: 9 executable fixtures, 9 matching their declarations, running on every push and pull request.

## 7.78.0 -- 2026-07-26 -- uninstall did not put the file back exactly, and it compounded

Ran T-184: the full `inject.sh` -> `uninstall.sh` round-trip against a sandbox `HOME`. This was the last path that writes into real user config (`~/.claude/CLAUDE.md` and friends) and had never been tested end-to-end -- the T-178 backup fix had only ever been verified through an isolated `sed` reproduction, not through the actual script.

Most of it held: user content survives, `$1.bak` is byte-identical to the pristine original, the block-refresh path leaves that backup pristine (T-178 confirmed for real this time), no temp residue, `.uninstalled.bak` written, skill directories removed. The test was itself proven capable of failing first -- temporarily restoring the T-178 bug turned it red, per `phases/verify.md`.

One step failed, and it was a real defect. **`uninstall.sh` did not reverse `inject.sh` exactly.** `$BLOCK` begins with a newline, so every install appended one blank line that the `BEGIN..END` range-delete never removed. It compounds: a 2-line `CLAUDE.md` grew to 7 lines across five install/uninstall cycles, one stray line each time, unbounded -- while README promises uninstall "strips exactly the marked block (leaving the rest of your file alone)."

Fixed with an awk pass that drops exactly one blank line immediately before `BEGIN` -- the one we added -- and preserves any the user had of their own. `uninstall.ps1` never had the bug; its regex already consumed the surrounding whitespace. Same bash-lags-PowerShell asymmetry as T-178 and the v7.76.0 `validate.ps1` hole.

Verified: byte-identical after five round-trips, and a file with the user's own trailing blank lines comes back untouched.

## 7.77.0 -- 2026-07-26 -- UI.md v2, plus the half it was missing: behaviour

Operator rewrote `saipen/UI.md` into a v2 -- tighter typography and layout rules, explicit accessibility floor, maintenance guidance, fewer places a code generator can invent noise. Reviewed against the principle behind it: *the interface has no right to surprise the user; press the button, get the result; the computer is a tool, not a creature.*

The visual half was already well covered -- zero animation and transition enforced in the base CSS, instant state changes, a static `...` instead of a spinner, no transparency, no control depending on hover alone. What the spec did not say anywhere was the **behavioural** half: it stopped the UI from *looking* alive without stopping it from *acting* alive. Added a `## Predictability` section covering the nine ways a static-looking interface still ambushes people:

- nothing happens unless asked -- no background refresh, silent autosave, or polling that swaps content under a reading eye
- the layout never moves after first paint (late content must not slide a button under a cursor already heading for it -- not cosmetic when that button is `Delete`)
- same input, same outcome: no adaptive menus, no control that changes meaning with context
- nothing disappears on a timer -- an auto-vanishing toast is either unimportant (don't show it) or important (don't hide it)
- state changes are visible in text, or they did not happen: silent success is indistinguishable from silent failure
- focus belongs to the user; irreversible actions name the actual object in the confirm text, and never focus the destructive default
- long work reports a count, not motion -- a spinner says only "not dead", a number also says how long and whether it is stuck
- `button:active`'s 1px shift is the entire motion budget, and is not precedent

Also resolved a real contradiction found while reviewing: iron law 2 bans transparency, but "disabled buttons must remain visible, just quieter" never said *how* -- `opacity` was the obvious wrong reading, and it would also fail the accessibility floor and vanish in screenshots. Disabled now means `--textMuted` on the same raised surface, border and position kept. A disabled control must additionally be explainable: a dead button with no stated reason is a surprise the user cannot resolve.

QA checklist gained five behavioural checks, including "left the screen open and untouched for a minute: nothing happened."

## 7.76.0 -- 2026-07-26 -- the Windows floor kept the LOG hole one release longer

v7.75.0 closed the "a `.saipen/` with no `LOG.md` passes as conformant" hole in `tools/validate.py` and `tests/validate.sh` -- and missed `tests/validate.ps1`, the floor every no-Python **Windows** host falls back to. Same asymmetric-fix pattern this session keeps catching: fix N of N+1 sites, ship, find the last one later. Break-tested it four ways after fixing: absent LOG goes red, empty LOG (what a fresh `INIT` writes) stays green, a malformed LOG line goes red, `read-only` + `BUILD` goes red.

Also verified end-to-end, first time for any of them:

- **The pre-commit hook actually blocks a commit.** Installed into a throwaway repo, committed a valid `.saipen/` (passed), corrupted `LOG.md` and committed again (blocked, non-zero), then confirmed `--no-verify` still gets through as documented.
- **`install_hook.py` / `uninstall_hook.py` round-trip preserves a foreign hook.** Seeded a pre-existing non-SAIPEN `pre-commit`, installed over it (original preserved in `.pre-saipen.bak`), uninstalled (original restored byte-for-byte), then ran uninstall again against the now-foreign hook (correctly refused to touch it).

Still untested and now tracked as **T-184**: the `inject.sh` -> `uninstall.sh` round-trip against a sandbox `HOME`. It is the only remaining path that writes into the user's real agent config, and the T-178 backup fix has been verified only through an isolated `sed` repro, never through the real script.

## 7.75.0 -- 2026-07-26 -- applied the new gate rule to our own gates; one could not fail

v7.74.0 added "a gate that cannot fail is not a gate" to `phases/verify.md`, including the instruction to prove a gate by breaking it once on purpose. Turned that on this repo's own validators.

**Both gates do work** -- broke them four ways (malformed LOG line, README badge drift, duplicate ticket id, injector wiring regression) and each went red as it should. But one hole showed up immediately:

- **A `.saipen/` with no `LOG.md` at all passed both validators and printed "Agent is conformant."** `STATE.md` and `BOARD.md` absence each FAIL loudly; `LOG.md` absence hit `if log_files:` / `if [ -f ... ]` and skipped every LOG check silently -- the "suite that collected 0 tests" case exactly. `LOG.md` is equally required by RFC § 1.2 and is the file § 1.5 Recovery rebuilds from, so its absence is if anything the worse of the three. Now FAILs in both validators, verified all four ways: absent goes red, empty (what a fresh `INIT` writes) stays green, home repo unaffected.

That new check immediately earned itself by exposing shipped debt:

- **`tests/scenarios/` has never been executed. By anything.** No script, no CI job, no phase doc. And the fixtures could not pass if it had been: 6 of 9 fail for reasons unrelated to what they test, because each ships only the one file its concept concerns. CONFORMANCE.md nevertheless claimed they "include a `.saipen/` that `tests/validate.sh`/`validate.ps1` runs against directly" -- both halves false, the second guaranteeing nobody discovered the first. That claim is now replaced with an honest status note, and the real work (complete the fixtures, declare per-fixture expected outcomes, add a runner, wire it to CI) is ticketed as **T-183** rather than papered over.
- **`invalid-mode-phase-combination` had been asserting a deleted rule for eight releases.** It existed to prove the validator caught `no-publish` + `SHIP` -- the ban v7.66.0 removed on purpose. Nothing ran it, so nothing noticed; meanwhile all three validators went on enforcing that same dead rule until v7.70.0 caught them. Repurposed into the inverse and more useful test: it now asserts the combination stays **legal**, so re-adding that ban turns it red. CONFORMANCE row 15 repointed at `read-only-restriction`, which is the only mode x phase ban still live -- and which does fail as intended.

## 7.74.0 -- 2026-07-26 -- a gate that cannot fail is not a gate

Found in the field, not in theory. A repo's CI was reporting green while being structurally incapable of reporting red: the smoke job carried `continue-on-error: true`, and its import check wrapped every module in a `try/except` that printed `SKIP: <module> -> <error>` and moved on. So a genuine `ImportError` and a healthy import produced the same outcome. Separately the lint job installed an unpinned `ruff`, so a new upstream release changed the default rule set and surfaced 46 findings on a codebase nobody had touched -- the build went red with zero code changes, which is the fastest way to train a team to ignore CI entirely.

`phases/verify.md` already said **never fake** a result. That covers lying. It did not cover the quieter failure where nobody lies and the instrument was simply never connected -- which is harder to catch precisely because every artifact looks correct.

Added to `phases/verify.md`, after the `conf:` line:

- The named tells: `continue-on-error`/`allow_failure`/`|| true`, a step that catches its own failure and prints a soft word instead of exiting non-zero, a suite that collected 0 tests or matched files that no longer exist. All treated as UNVERIFIED until proven otherwise.
- The proof, mandatory when you rely on the gate: **break it once on purpose.** Feed known-bad input, confirm red. Still green -> that is a second defect, not a passing test. LOG both the real green run and the deliberate red one.
- `conf: high` is not available for a gate never shown capable of failing.
- Pin the tools a gate depends on, and state the rule set explicitly -- an unpinned linter's "defaults" are whatever shipped that week, not a decision the repo made. A gate that fires randomly and a gate that never fires end in the same place: ignored.

Deliberately scoped to `verify.md` alone -- this is a VERIFY-discipline rule, and duplicating it into `hunt.md`/RFC would be the protocol bloat this project keeps rejecting.

## 7.73.0 -- 2026-07-26 -- who translates what is now a rule, not a budget decision

Operator ruling, written into the protocol so it binds every agent and survives the session: the Core agent handles **English, Russian, Estonian and the `Дед` voice, and nothing else**. All 29 remaining languages are subSaipen work -- a dedicated `saitranslate`/`saiwiki`-class instance on a small, cheap model.

This replaces a softer version of the same idea. Two days earlier the same call had been made as a one-off ("leave the remaining 22 to a cheap model, not worth your tokens"), which left it re-decidable every session by whoever felt they had room. It is now a scope rule in `phases/translate.md` § 2: bulk translation is high-volume and low-complexity-per-unit -- real work, but not work that needs the expensive seat, and "I have budget right now" is not a reason to take one.

- `Дед` stays Core's precisely because it is a *voice*, not a language: getting it right is a STYLE.md judgement (blunt, compressed, mocking, still factually exact) that a cheap model flattens into neutral Russian.
- Japanese moved out of the old "prioritize EN/RU/ET/JA" line -- that list predated the split and now contradicted it.
- What Core still does at any language: verify (byte-valid UTF-8, structure, spot-checks against the real source) and repair genuine corruption. That is a correctness fix, not a translation pass -- exactly what happened when four languages turned up with invalid UTF-8 in v7.65.0.
- `T-168` restated: of its 22 outstanding languages, zero are Core's.

## 7.72.1 -- 2026-07-26 -- the fix shipped an hour ago had a false positive; HUNT caught it

Routine HUNT over this session's own diff, and it found a regression v7.72.0 introduced.

That release added a check stopping a shipped subSaipen template from carrying a concrete `saipen_home` -- correct in itself, but it keyed on the path starting with `extensions/` and nothing else. A *consuming* project is allowed to keep its subs exactly there: RFC § 1.9's legacy root-level `extensions/subs/`. In that project a real `saipen_home` is not pollution, it is what `saipen sub spawn` is required to write. So those projects got a hard FAIL, and via the pre-commit hook, blocked commits.

Third time this session a validator change has been too eager and reached into other people's repos (v7.70.0 caught two others). Gated behind the same home fingerprint the distribution self-check already uses -- `saipen/` + `bootstrap/` + `VERSION` + `README.md` -- and verified in all three directions: a legacy consuming project passes, the home still checks every library state, deliberate re-pollution is still caught.

## 7.72.0 -- 2026-07-26 -- MARKHUNT triage: all 6 findings closed, including a backup-destroying installer bug

`saipen markhunt` ran a dry, uncapped audit across the whole repo (5/5 scope vectors, 6 findings, recorded as T-178..T-181 in `## BLOCKED` and fixed nothing, as that phase requires). The user then triaged all four in. Every finding was evidence-backed and reproduced before being written down.

- **`bootstrap/inject.sh` silently destroyed the user's pristine pre-SAIPEN backup on every re-run.** `add_block()` correctly refuses to overwrite an existing `$1.bak`, then immediately ran `sed -i.bak ...` -- and sed's own suffix overwrote that same `.bak` with the current, already-SAIPEN-containing file. The only copy of what the user had before installing was gone, unrecoverably. Reproduced live before fixing and re-run after. What makes it notable: `bootstrap/uninstall.sh` carries a comment describing this exact hazard and avoids it, and `inject.ps1`'s writer is guarded too -- v7.71.0 had fixed three of the four sites and left the installer's bash path.
- **A shipped library template carried one machine's absolute path.** `extensions/subs/saipython/STATE.md` had a concrete `saipen_home` pointing at the author's local clone (plus a live timestamp where both siblings had the placeholder) -- in a public repo, in a file `saipen sub spawn` copies and the injector distributes to every platform. Reset to template state, and the root cause closed: `tools/validate.py` only ever walked `.saipen/extensions/subs/` (this project's live instances), never `extensions/subs/` (the library that actually ships), so nothing could have caught it. It now walks both, and a concrete `saipen_home` in a shipped template is an explicit FAIL.
- **README told users to run the injector into their home config and never mentioned the uninstaller.** `bootstrap/uninstall.*` existed and worked but appeared only in SPEC.md and SECURITY.md. Added an undo block plus a plain statement of exactly which files the installer touches. Also restored `saipen plan` and `saipen ship` to the trigger list -- both were absent from README entirely while GUIDE.md covered all twelve commands.
- **`BOARD.md` had no size discipline while `LOG.md` had three**, despite `BOOT.md` reading both on every cold start. Resolved by taking the cheap half only: no sealing machinery (the board is prunable rather than append-only, and `phases/clean.md`'s scrub is already the mechanism), but a validator WARN past ~16 KB so growth surfaces on its own. This repo's own board tripped it immediately -- 28 KB, of which 16 KB was closed-ticket prose already duplicated into `LOG.md` and `CHANGELOG.md` -- and was scrubbed to 9.4 KB in the same pass.

CONFORMANCE rows 39-40 added for the two new mechanical checks.

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


## 7.43.0 -- 2026-07-23 -- ADD's stale RFC pseudocode fixed; MARKHUNT's first real run triaged
User brought an external audit (`tofix/saipen_audit1.md`) and asked to work through it starting with its biggest finding. Confirmed against the live files, not just the audit's claims:

- **RFC § 2.2's ADD pseudocode was still pre-v7.40.0** -- `add.md` itself had already been fixed (`bugfix -> TICKET; RETURN SCOUT`, `minimal_delta -> TICKET; RETURN BUILD`), but RFC carried its own separate copy of the same logic that nobody had touched: `bugfix -> RETURN HUNT` (the exact ADD<->HUNT infinite loop v7.40.0 fixed, reachable again by an agent that reads RFC directly) and `minimal_delta -> IMPLEMENT; RETURN VERIFY` (skips BUILD's own discipline entirely). Synced both, replaced the stale "VERIFY, then HUNT" cadence claim with the real `BUILD -> VERIFY -> REVIEW -> SHIP -> DONE` flow, and folded in a second real finding from the same audit: `add.md`'s minimal_delta branch created a ticket and jumped straight to `BUILD` with no claim step, leaving it unclaimed in `TODO` while `STATE.phase` had already moved on -- both RFC's pseudocode and `add.md`'s prose now explicitly claim the ticket first.
- **`saipen prepare` was missing its own command-surface entry.** The user's own direct edits (made while this session was mid-task) wired MARKHUNT and PREPARE into the phase enum (now 16 values), transition table, § 2.1, CONFORMANCE row 27, and GUIDE.md -- thorough and correct. One thing fell through: `saipen prepare` was named in § 1.10's grouping sentence but never got its own bullet, and never made GUIDE.md's command table either. Added both.
- **A real MARKHUNT pass had already run against this exact audit** -- `BOARD.md`'s `## BLOCKED` section held 22 `[MARKHUNT]`-tagged tickets (T-122 through T-143), ingesting all 20 of the external audit's findings plus 9 more MARKHUNT found on its own (`BLOCKED`'s dual meaning, HUNT's inconsistent trigger wording, MARKHUNT's own lack of a verifiable-thoroughness test, `next_action`'s three-audience overload, VERIFY/BLOCKED retry hysteresis, goal_waves/goal_tickets measuring different things, and -- critically -- two tooling bugs). Triaged and closed six: the ADD fix above (T-122, T-128), and two real, verified, P1 tooling bugs MARKHUNT itself surfaced -- `tests/validate.sh`/`validate.ps1`'s phase regex and `extensions/schemas/state.schema.json`'s enum both still only knew the old 14 phases, meaning any `STATE.md` actually set to `MARKHUNT` or `PREPARE` would fail validation the moment either phase was used for real. Fixed both. Checked T-143 (a STATE/BOARD desync finding) against the live file -- already self-resolved by the ongoing translate session's own subsequent progress, no action needed. 16 `[MARKHUNT]` tickets remain in `BLOCKED`, untouched, for further triage.

Both validators green.

## 7.42.0 -- 2026-07-23 -- MARKHUNT and PREPARE phases introduced
- **MARKHUNT Phase**: Dry, exhaustive, uncapped audit phase. Records findings as blocked tickets on `BOARD.md` without autonomously fixing anything. Triggered via `saipen markhunt`.
- **PREPARE Phase**: Explicit subSaipen handoff packaging phase. SubSaipens now rigorously verify freshness, write injection instructions, and format findings in `OUTBOX.md`.

## 7.41.0 -- 2026-07-23 -- HUNT skip hardened against a real field-observed fake-clean heuristic
User flagged a real transcript: a weaker model (a small OpenCode-hosted model), finding the prior `hunt -> clean @HASH` line stale, invented its own substitute -- "no source files changed since the last hunt's timestamp, call it clean" -- skipping the sweep entirely. Corrected once (told to re-read `hunt.md`), it caught the hash mismatch, then made the identical substitution a second time: diffed file mtimes again and declared "0 changes, all 6 categories the same, HUNT clean" without literally re-running a single one of the six checks. The prior hunt in that same transcript had found 2 open tickets -- if nothing changed since, those were still sitting there unaccounted for, so "clean" wasn't just unproven, it was wrong on the model's own logic.

- `phases/hunt.md`'s skip condition is now mechanically spelled out: compute `git rev-parse --short HEAD` first, then grep `.saipen/LOG.md`'s tail for that *exact* string in a `hunt -> clean @<HASH>` line -- no match of any kind (stale hash, no line at all) means run the full sweep, no exceptions.
- Added an explicit real-incident callout naming the exact failure mode -- "nothing changed on disk" is banned as a substitute for both the hash check and for actually performing the six categories, since silent failures, stale TODOs, and dead code don't leave an mtime trail.
- Scenario row 26 + `hunt-skip-requires-exact-hash-match` fixture (behavioral, README-only, matching the pattern of every other agent-decision-making assertion in this table).

Separately checked a second transcript the user flagged: an agent invoking `anthropic-skills:caveman` mid-session, worried SAIPEN might depend on an external skill that isn't always available. Traced it -- SAIPEN's own `STYLE.md` is fully self-contained prose, never invokes any external skill tool; `bootstrap/inject.ps1`'s injected block only uses the word "caveman" as the *name* of SAIPEN's own fused style, pointing the agent at `STYLE.md` to read directly. The behavior in that transcript came from that machine's own separate, personal global `CLAUDE.md` (unrelated to SAIPEN, coincidentally using the same word). Not a SAIPEN issue -- no fix made.

Both validators green.

## 7.40.0 -- 2026-07-23 -- ticket-priority order formalized in DONE/VALIDATE/BLOCKED, plus 2 review fixes
User hand-edited RFC.md and 9 phase docs directly (10 commits, no ship ritual yet -- backfilled here). Core theme: `DONE` previously jumped straight into `goal_mode`/HUNT logic without ever handling "there are still other TODO tickets" as its own first-class case. Fixed with an explicit priority order, and the transition table + validate.md/blocked.md updated to match:

- **`done.md`** rewritten: (1) pending `TODO` tickets first -> `SCOUT` (or `BLOCKED` if all remaining are unworkable), (2) only if `TODO` is truly empty, check `goal_mode` -> `HUNT`, (3) manual empty-board bare `saipen` -> `HUNT` per § 2.1, (4)-(6) user-driven alternatives unchanged. `hunt.md` retitled "(no TODO tickets remaining)" to match -- `DONE`/`BLOCKED` tickets sitting on the board no longer block the maintenance transition.
- **State machine table (RFC § 1.6)** gained `PLAN -> BUILD|DONE`, `VERIFY -> SCOUT`, `REVIEW -> SCOUT`, `DONE -> SCOUT`, `VALIDATE -> DONE`, `BLOCKED -> DONE`, and `ADD -> BUILD` (was `-> VERIFY`) to legalize what the phase docs already needed. `PLAN -> BUILD`/`DONE` were already load-bearing in `plan.md`'s pre-existing Size-gate and Proposal-Mode text -- the table just hadn't caught up.
- **`add.md`**: fixed a real ADD<->HUNT infinite loop -- `bugfix -> RETURN HUNT` assumed HUNT would independently rediscover the same bug via its own 6 mechanical signals; if it didn't, ADD would re-evaluate the same priority and bounce to HUNT forever. Now ADD tickets the bugfix itself and goes straight to `SCOUT`. Also stopped ADD from implementing minimal-delta features inline (bypassing BUILD's own discipline) -- it now tickets and hands off to `BUILD` properly.
- **`scout.md`** gained an explicit step 0: claim the ticket (`TODO` -> `DOING`, checkbox `[/]`, `owner:`/`claim_time:`) -- previously implicit, owned by no specific step.
- **`verify.md`**/**`review.md`**: closed a gap where VERIFY could pick up the next ticket directly, skipping REVIEW/SHIP for the one just verified -- there is no next-ticket branch from VERIFY anymore, REVIEW and SHIP are mandatory first. REVIEW's cap-exceeded path now explicitly says where to go next instead of leaving the agent stranded.
- **`saipen plan [text]`** registered in RFC § 1.10's command surface and `GUIDE.md`'s command table -- it already existed and was fully specified in `phases/plan.md` (bare/Proposal Mode halts at `DONE` for the user to pick a ticket, never auto-runs one), just never actually listed as a recognized command, non-conformant per § 1.10's own closing rule.

Two more holes found reviewing the above, fixed here:
- RFC § 1.10's `saipen goal <text>` entry never mentioned that bare `saipen goal` (no text) is separately meaningful -- § 2.4 already used it to resume a paused run. Now cross-referenced.
- `tests/scenarios/board-empty-maintenance-transition/README.md` still said no tickets in `DOING`/`TODO`/`BLOCKED` -- stale against `done.md`'s new explicit "DONE or BLOCKED tickets remaining doesn't matter, only TODO" rule. Reworded.

A separate agent/session ran its own `saipen continue` somewhere mid-sequence (LOG shows `hunt -> clean @b935fc2`, STATE.md's `phase` is now `ADD`) -- left both untouched, that's real pending work, not this ship's to claim or overwrite. Its LOG line collided on `E-597` with one of this ship's own entries (both independently continued from the same `E-596`); renumbered it to the next free ID, kept its true original parent.

Both validators green.

## 7.39.0 -- 2026-07-23 -- second HUNT in a row: uninstall_hook.py couldn't tell "clean" from "wrong directory"
User asked for another `continue` right after v7.38.0 shipped. Board still empty -- HUNT again, this time aimed straight at the newest file in the repo: `tools/uninstall_hook.py` itself, written and shipped one cycle ago.

- `install_hook.py` explicitly checks `.git` shape before doing anything: a linked worktree (`.git` is a file) gets a clear message and a stop, no `.git` at all gets a clear `FAIL`. `uninstall_hook.py` had neither check -- it went straight to `Path(".git/hooks/pre-commit")` and reported the exact same "clean" message whether the repo was genuinely clean, had no `.git` at all, or was a linked worktree whose *shared* hook (in the main checkout) might still be very much active. "Clean" in the worktree case was actively misleading, not just incomplete.
- Added the same two guard clauses `install_hook.py` already has, worded for uninstall's non-destructive, always-exit-0 nature: a worktree gets pointed at the main checkout instead of a silent false "clean"; no `.git` at all gets its own distinct message instead of being indistinguishable from a real clean repo.
- Tested both new paths plus re-ran all 3 previously-passing scenarios (fresh install/uninstall, foreign-hook backup+restore, marker-absent no-touch) against a throwaway repo -- all 5 green after the edit.

Both validators green.

## 7.38.0 -- 2026-07-23 -- autonomous HUNT: install_hook.py had no uninstall
Bare `saipen` with an empty board -- zero-prompt auto-transition to HUNT per RFC § 2.1. Ran the six signal categories directly (sequential, no subagent dispatch). One real, verified finding; one hypothesis that didn't survive checking:

- Checked first whether `bootstrap/inject.ps1`'s global per-agent skill copies had an uninstall counterpart -- they do (`bootstrap/uninstall.ps1`/`.sh`), and a side-by-side read confirmed all 7 install targets (Claude Code, OpenCode, Codex, Gemini, ~/.agents, Antigravity plugins, Aider) are mirrored exactly. Not a finding -- verified clean, no fix needed.
- The real gap: `tools/install_hook.py` (per-project pre-commit hook installer, a completely different mechanism -- project-local, not global) had no uninstall counterpart at all. A user who installed it had no scripted way to remove it; a backed-up pre-existing foreign hook (`pre-commit.pre-saipen.bak`) had no scripted restore path either.
- Added `tools/uninstall_hook.py`: detects the marker `install_hook.py` writes, restores any backed-up prior hook if one exists, removes cleanly if not, and leaves a non-saipen hook completely untouched if the marker isn't present. Tested all three paths directly (fresh install/uninstall, foreign-hook backup+restore, marker-absent no-touch) against a throwaway repo before shipping.
- Documented next to every existing `install_hook.py` mention: its own docstring, `tools/validate.py`'s runtime manifest (11 -> 12 files), `SPEC.md`, `phases/validate.md`, `GUIDE.md`, and the 4 flagship guides (EN/RU/EE/DED) -- the other 29 translated guides are left for a future `saipen translate` drift pass, same precedent as prior small doc additions this segment.

Both validators green.

## 7.37.0 -- 2026-07-23 -- TRANSLATE's legacy-path handling brought up to the same bar as extensions'
Prompted by watching a real migration in the wild: a separate agent (Antigravity, on an unrelated project) was told to move root-level `.saitranslate/` to `.saipen/saitranslate/` and got the mechanics right on its own -- but the protocol itself had nothing telling it to. TRANSLATE's legacy clause was thinner than extensions' equivalent (§ 1.9), and `phases/translate.md` didn't mention the legacy path at all.

- RFC § 2.1's TRANSLATE bullet now mirrors § 1.9 exactly: never maintain both `.saitranslate/` and `.saipen/saitranslate/` at once, the migration command spelled out (`git mv .saitranslate .saipen/saitranslate`, one LOG line), and the same dual-location-conflict resolution (`.saipen/saitranslate/` authoritative, root copy stale, ticket its removal, never merge or guess which is newer).
- `phases/translate.md` now states the legacy path and precondition directly, instead of relying on an agent that only loads the phase doc -- not the full RFC -- to already know.
- A parallel TRANSLATE instance now carries the same `.saipen/` precondition `saipen sub spawn` already had since v7.36.0: no `.saipen/` yet, refuse and point at `saipen set`, never improvise a bootstrap.
- v7.36.0 shipped `saipen sub spawn`'s own precondition without conformance coverage -- backfilled. Scenario rows 24 (`translate-dual-location-conflict`) and 25 (`spawn-requires-init`) added, both behavioral/README-only, mirroring row 23's pattern.

Both validators green.

## 7.36.0 -- 2026-07-23 -- adversarial pass over yesterday's own consolidation, four real holes
User asked for another full logic-holes overview. Focused on the newest, least battle-tested surface: v7.35.0's `.saipen/` consolidation, since restructuring the file model is exactly the kind of change most likely to have introduced fresh ambiguity nobody stress-tested yet. Found four:

- **Nested STATE.md/BOARD.md/LOG.md ambiguity.** Before v7.35.0, a subSaipen's or parallel-TRANSLATE's own STATE.md lived under a totally separate tree (`extensions/`, `.saitranslate/`) -- no risk of confusing it with the project's own. After consolidation, real files named `STATE.md` now exist at multiple depths under the same `.saipen/` root. RFC § 1.1 hardened: "STATE.md" unqualified always means the exact `.saipen/STATE.md` at project root; a nested one is a different instance entirely, distinguished by full path -- never `find`/glob for a bare filename and act on whatever turns up.
- **Kitchen bullet didn't disambiguate subSaipen kitchens** the way it already did for TRANSLATE's. Added the same explicit callout: a crashed subSaipen's kitchen is that subSaipen's own resume concern (or the main agent's, via Handoff/OUTBOX), never something the main agent inspects hunting for its own crashed work.
- **Both extension locations existing at once** (partial/failed migration, two agents disagreeing) had no resolution rule -- RFC § 1.9 only said "don't maintain both," not what to do on discovering it already happened. Added: `.saipen/extensions/<name>/` is authoritative, root-level is stale, ticket the cleanup, never silently merge or guess which is newer. Scenario row 23 + `extension-dual-location-conflict` fixture.
- **`saipen sub spawn` had no precondition check** for a project with no `.saipen/` at all (never ran `saipen set`). A subSaipen attaches to a main project's continuation state -- it isn't one on its own. `extensions/subs/PROTOCOL.md` now requires `.saipen/` to already exist; tells the user to bootstrap first instead of silently triggering INIT as a side effect of an unrelated command.

Swept `phases/init.md` for the same class of issue -- confirmed clean, it only ever touches `.saipen/STATE.md`/`BOARD.md`/`LOG.md` directly, never auto-populates `extensions/`/`saitranslate/`, consistent with RFC's own no-auto-populate rule.

Both validators green.

## 7.35.1 -- 2026-07-23 -- TRANSLATE covers docs AND software together, actively tracks drift
User's follow-up clarified intent further: v7.34.1's "docs-first projects / UI-bearing projects" wording read as an either/or choice -- pick one. The real intent is additive: TRANSLATE's job is everything translatable in the repo, docs and real software UI strings together whenever both exist, never a choice between them. `phases/translate.md` § 2 reworded -- documentation and real UI strings are now explicitly "(a)" and "(b)", both in scope simultaneously; a project just gets whichever of the two it actually has (most SAIPEN-managed projects: (a) only, never fabricate (b) to compensate).

§ 3 ("Maintenance and Update") was also thin -- "if it already exists, compare" read as a passive, one-time check rather than an ongoing responsibility. Reworded to an active per-run drift scan: every `saipen translate` invocation re-scans both surfaces against the existing bundle, treats anything new or changed since the last run as drift to translate, and explicitly warns against two failure modes -- rebuilding everything from scratch every time (wasteful, loses nothing but resets nothing wrong either) and silently leaving stale translations next to updated source (worse than no translation, since nothing signals they've drifted). Added an explicit coverage-honesty requirement: a partial pass gets reported as partial in the completion LOG line, never rounded up to "done."

Both validators green.

## 7.35.0 -- 2026-07-23 -- everything protocol-shaped lives under one .saipen/ roof
User caught a real conformance bug in a different project (`FastPrompter`): another agent had spawned a subSaipen at root-level `subs/`, not `extensions/subs/` -- a deviation from spec. That surfaced the deeper question: why does a project carry `.saipen/`, `extensions/`, and `.saitranslate/` as three separate top-level entries at all? Weighed the tradeoff explicitly before touching anything this foundational (RFC's file model, referenced everywhere): consolidation cuts root-level clutter to one dot-folder; the cost is `.saipen/` (protocol-managed continuation state) absorbing `extensions/` (project-author-managed behavior hooks) into one bucket. Judged worth it -- confirmed with the user given the size of the change.

**New attachment point for a consuming project**: `.saipen/extensions/<name>/` (was root-level `extensions/<name>/`) and `.saipen/saitranslate/` (was root-level `.saitranslate/`). **Unchanged**: the SAIPEN home's own top-level `extensions/` -- that's the shipped library the injector distributes and `saipen sub spawn` bootstraps from, a different thing from where a consuming project attaches its copy. **Legacy**: a project bootstrapped before this version MAY still carry the old root-level locations -- agents MUST recognize them as equivalent and MAY migrate at a convenient checkpoint, never maintain both at once.

Every normative reference updated: RFC § 1.2 (secrets list, kitchen bullet), § 1.9 (extension discovery, with the legacy-recognition clause), § 2.1 (TRANSLATE). Phase docs: `verify.md`/`review.md` (security/performance hook lookup), `translate.md` (five `.saitranslate` mentions). The `extensions/subs/`, `extensions/security/`, `extensions/performance/` example docs themselves updated to describe the new attachment point for whoever copies them in. Found and fixed in passing: `extensions/subs/README.md` still name-checked `extensions/multi-agent/`, deleted back in v7.30.0 -- swapped for `extensions/performance/`.

This repo's own dogfooding: `.saitranslate/` (genuinely this project's own output, no library role) moved via `git mv` to `.saipen/saitranslate/`. The home's own `extensions/` folder deliberately NOT moved -- it plays the library role here, not a consuming-project attachment.

Both validators green.

## 7.34.1 -- 2026-07-22 -- TRANSLATE was fabricating content; scope fixed to the real surface
User's clarifying question ("so it translates the software AND README AND guides AND wiki, everything translatable in the repo?") led to checking what the phase actually produces -- and it isn't that. Read this repo's own `.saitranslate/` bundle (built by an earlier session, "23/23 locales" logged as a success): every locale file contains `app.title`, `action.continue`, `settings.language`, `status.hunting` -- fabricated UI strings for a settings screen and buttons that don't exist anywhere in SAIPEN. The phase doc's "translate the software strings" instruction assumed every project has real in-app UI copy to translate; for a protocol/CLI/docs-first project it does not, and the agent invented plausible-sounding placeholder keys instead of recognizing there was nothing real to translate.

Two real bugs, both fixed:
- **Fabrication risk**: `phases/translate.md` § 2 now requires determining the actual translatable surface before building anything -- grep the real source for genuine UI-string patterns first; if none exist (most SAIPEN-managed projects), the real surface is the project's own documentation (README, top-level docs), never invented UI copy. Docs-first mode explicitly skips anything already hand-maintained per language (this repo's own `guides/`) -- never duplicates or clobbers curated work.
- **Structural non-compliance**: the existing bundle sat directly in `.saitranslate/locales/` + `.saitranslate/manifest.json`, not inside `.saitranslate/kitchen/` as § 4's own completion rule already required. Moved via `git mv`, history preserved.

The existing bundle's *content* stays as-is for now -- moved to the correct location, not regenerated; it's fabricated and not integrated into anything (TRANSLATE's own completion rule never auto-integrates), so no real harm from it sitting there, but a real docs-scoped translate run is the honest next step whenever wanted.

Both validators green.

## 7.34.0 -- 2026-07-22 -- TRANSLATE gains an explicit parallel-agent mode
User's real ask, clarified after an initial wrong framing: not "make .saitranslate a subSaipen" (declined -- TRANSLATE writes extensively inside its own sandbox, subSaipen is permanently read-only toward everything; TRANSLATE is also Core, in RFC's closed 14-phase enum and command surface, not something that can move to an extension without a breaking change) -- the actual goal was parallelism: send a separate, dedicated full agent to build the whole translation bundle without getting in the main agent's way.

TRANSLATE already had almost everything needed for this (isolated `.saitranslate/`, main project treated read-only, its own `kitchen/`, completion sitting untouched until a later ADD/PLAN ticket integrates it) -- the one real gap: it assumed being run by the *same* agent phase-switching, so it wrote `phase: TRANSLATE` straight into the shared `.saipen/STATE.md`. A genuinely separate parallel agent doing that would stomp on whatever the main agent's own session has active -- exactly the one-writer concurrency boundary RFC § 1.4 already flags.

Fixed with an explicit parallel-instance rule, `phases/translate.md` § 1 + RFC § 2.1: a dedicated agent sent to run TRANSLATE in parallel keeps its own `.saitranslate/STATE.md` (same shape as Core's, scoped to the build) instead of touching the shared one, writes freely inside `.saitranslate/` (this is not read-only work -- don't confuse it with `extensions/subs/`'s subSaipen, which never writes anywhere real), and touches the *shared* `.saipen/LOG.md` exactly once, at completion, with the same line the single-agent case already produces. The existing single-agent phase-switch case (already field-tested -- an earlier session ran a real 23-locale translate) is untouched, still checkpoints normally.

Scenario row 22 + `parallel-translate-isolation` behavioral fixture. Both validators green.

## 7.33.4 -- 2026-07-22 -- full-project integrity pass: two real bugs found, both fixed
User asked for a fresh whole-project look. Both validators green going in; the new finds were things automation doesn't check:
- **`guides/GUIDE_EN.md` and `GUIDE_RU.md` still said "22 languages"** in their own command table's `saipen translate` row -- missed during the earlier 31-file batch fix because these two richer files phrase the sentence differently from the thin template the grep matched. Fixed to 32; swept the whole repo for any other live "22 language(s)" mention -- zero left outside history (LOG.md/CHANGELOG.md, correctly untouched).
- **Their command tables had no `saipen sub` row**, unlike `GUIDE_DED.md` which got one in v7.33.2 -- inconsistent treatment of the same fact across flagship guides. Added, same experimental framing.
- Caught and fixed a Russian grammar typo introduced in the same edit ("ко реальному" -> "к реальному").
- Verified clean otherwise: no dangling `extensions/multi-agent/` references anywhere, no dangling `](GUIDE_XX.md)` old-path links, `.saipen/BOARD.md` genuinely empty (matches every recent `next_action` claim), `CONFORMANCE.md` correctly has no scenario row for `extensions/subs/` (same precedent as every other extension -- opt-in layer, not Core-tested).
- Noted, not fixed (cosmetic/external, not a repo integrity issue): GitHub's latest Release is still `v7.22.0` while tags run to `v7.33.4` -- a release-cutting gap, not a correctness one.

Both validators green.

## 7.33.3 -- 2026-07-22 -- extensions/subs/README.md: one-line reminder, read-only is policy not a wall
Follow-up on a reviewer's comment about v7.33.0's design: `PROTOCOL.md` § 1 already says `mode: read-only` is procedural (no universal technical lock, same footing as RFC § 1.1's destructive-op rule) -- correct and already honest, nothing to fix there. What was missing: the Quick Start path (`README.md`, the file someone actually reads before spawning one) never said it. One line added where `saipen sub spawn` hands off to another agent -- if real isolation is wanted, run it in its own worktree or a directory-restricted session, not the same full-access agent on its honor. Single mention, not repeated elsewhere. Both validators green.

## 7.33.2 -- 2026-07-22 -- flagship guides mention subSaipen, clearly flagged experimental
User's call: update the four flagship guides (`guides/GUIDE_EN.md`, `GUIDE_RU.md`, `GUIDE_EE.md`, `GUIDE_DED.md`) for `extensions/subs/`. Distinct from *advertising* it (README section, GitHub topic -- still withheld, same v7.30.1 policy): a GUIDE is read by someone already using the product, not pitched to a new visitor, so a short, clearly-flagged "experimental, zero battle scars yet" mention belongs there even while the front door stays quiet about it. Each guide got one paragraph in its own established voice -- `saipen sub spawn saihunt` as the one-liner (self-bootstraps per v7.33.1), what it gets you (isolated read-only agent, findings via its own OUTBOX, never touches real code), the two built-in subSaipen (saiwiki, saihunt), and the explicit "don't bet the farm on it yet" caveat. `GUIDE_DED.md`'s command cheat-sheet table also gained the `saipen sub spawn` row. Both validators green.

## 7.33.1 -- 2026-07-22 -- saipen sub spawn bootstraps itself, no manual copy
User asked whether spawning a subSaipen in a new project requires manually copying `extensions/subs/` in first. It did -- real friction, easily closed: the agent already knows `saipen_home` (`STATE.md`, RFC § 1.7). `saipen sub spawn <name>` now bootstraps `extensions/subs/` from there on first use in a project (copies `PROTOCOL.md`/`README.md`/`TEMPLATE/`/`_shared/inbox.md`), then spawns the named subSaipen -- one command from a cold project, same command either way. Explicitly not a violation of RFC § 1.9's "don't auto-populate extensions/" rule -- that rule is about *silent* population `saipen set` never does; this is the *explicit* ask a user makes by typing `spawn` in the first place. No `saipen_home` recorded yet (pre-v7.25.0 state, or degraded bootstrap)? Ask once for the clone path, never guess.

## 7.33.0 -- 2026-07-22 -- extensions/subs/: read-only research subagents (design pass + build)
User handed over a same-day draft (`PLAN.md`/`PROTOCOL.md`/`README.md`/`TEMPLATE/`) for a new extension: isolated, read-only "subSaipen" agents that research the main project in parallel and hand back structured findings. Reviewed it like every other new-protocol-surface proposal this session -- verified against RFC before building, not transcribed:

- **RFC-command-surface violation, caught before it shipped.** The draft's SYS-005 planned to add `saipen sub *` commands directly into `saipen/RFC.md` -- exactly the Core/extension boundary this session has held all along (`extensions/multi-agent/` never touched RFC once). Fixed with a general, reusable escape valve instead of a subs-specific carve-out: RFC § 1.9 now states an extension MAY define its own bare-command vocabulary in its own docs, recognized only while its folder exists in the project, never registered in § 1.10's closed list.
- **Lifecycle state machine removed -- decorative complexity solving a problem that doesn't exist here.** The draft's 8-state machine (SPAWN/WORK/SIGNAL/WAIT_ACK/STALE/RECOVER/RETRY/CLEAN) with dual timeouts (3 collect-rounds OR 24h wall-clock) assumes a subSaipen is a background daemon that can silently die and needs liveness detection. It isn't -- it's a manually-invoked agent session, same as Core SAIPEN itself. Replaced with: a subSaipen IS a normal SAIPEN instance (same `phase` enum, same LOG skeleton), permanently `mode: read-only` -- RFC § 1.3 already defines exactly the wanted behavior ("advises, does not act"), reused deliberately as a policy application of the same value Core defines for a capability gap.
- **A broken, dangerous pre-commit hook deleted before it was ever installed.** The draft's read-only enforcement hook (`git diff --cached --name-only | grep -v "^extensions/subs/"`) would fire on every normal commit touching any file outside that one folder -- which is nearly every real commit in the project. As written it would have blocked all normal work, not enforced isolation. Removed; enforcement stays procedural (same footing as RFC § 1.1's destructive-op rule), stated honestly rather than claiming automation that doesn't exist.
- **STALE/RECOVER/RETRY and MANIFEST.md's lifecycle-tracking table removed.** A finished, folded-in subSaipen is stale kitchen content by definition -- `HUNT`'s existing kitchen-staleness check (v7.23.0) already covers it, no parallel machinery needed. `MANIFEST.md` is now just a name-to-folder list.
- **Kept**: the OUTBOX structured-handoff format (status/summary/critical/main_project_refs/details) and the ticket-ID namespace (`SYS-`/`WIKI-`/`HUNT-`/`<NAME>-`) -- both genuinely good ideas, unchanged. Command surface simplified from 6 to 4 (`list`/`spawn`/`collect`/`clean` -- dropped `ack` and `recover`, folded into `collect` / made moot).
- Built `saiwiki` (wiki/doc drafting) and `saihunt` (bug hunting) as the first two subSaipen, matching the draft's own ticket lists (`WIKI-001..005`, `HUNT-001..005`). `PLAN.md` deleted -- uncommitted build-plan doc, superseded by the simplified `PROTOCOL.md`/`README.md` it was executed into.
- `SPEC.md`'s extensions/ tree gained a `subs/` line, same style as `security/`/`performance/`.
- **Not advertised** -- same policy `extensions/multi-agent/` got in v7.30.1: usable, zero field runs behind it yet.

Both validators green.

## 7.32.1 -- 2026-07-22 -- GUIDE.md: Obsidian/PKM compatibility made explicit (Reddit feedback)
A user reported not seeing the "agent amnesia" problem at all -- they run a personal Obsidian vault with provenance logging and re-orient the agent from their own notes every session. Not a bug report, but a real signal: for engineers who already have PKM discipline, the unstated question is whether SAIPEN competes with that system or fits inside it.
- It already fits with zero code changes -- `.saipen/KNOWLEDGE/` is plain markdown, so opening the project root as an Obsidian vault makes it a normal part of the graph (wikilinks, backlinks, frontmatter properties all untouched by the protocol; KNOWLEDGE/'s only real rule is "durable truth, not an event log"). That fact was simply never stated anywhere. New GUIDE.md section spells it out, plus how to exclude `kitchen/`/`LOG.md` from a vault's index if the event-stream noise isn't wanted.
- Their "data provenance logging" is already covered by the existing `DEC` taxonomy (a decision entry is expected to carry its own "why") -- no new LOG taxonomy value added; RFC's RUN/DEC/H set stays closed, consistent with this session's standing bar for touching it.
- Both validators green.

## 7.32.0 -- 2026-07-22 -- all 33 language guides moved into guides/
- User's call: root directory had 33 `GUIDE_XX.md` files cluttering it alongside README/SPEC/LICENSE. Moved all of them (`GUIDE_AR.md` through `GUIDE_ZH.md`, plus `GUIDE_DED.md`) into a new `guides/` folder via `git mv`, preserving file history. `GUIDE.md` itself (the neutral hub, referenced directly by README and SPEC) stays at root.
- Updated every link: `GUIDE.md`'s 33-entry language table and `README.md`'s 5 badge links + language table now all point at `guides/GUIDE_XX.md`. Grepped for dangling `](GUIDE_XX.md)` references after the move -- none found.
- No content change to the guides themselves, no runtime/protocol impact (these files aren't in `tools/validate.py`'s manifest). Both validators green.

## 7.31.2 -- 2026-07-22 -- all 31 remaining language guides enriched
- User's follow-up after the EN/RU/neutral enrichment: enrich every other language guide too. Discovered all 31 (`GUIDE_EE.md` through `GUIDE_HR.md`, plus the standalone `GUIDE_DED.md` cheat sheet) share one much thinner template than GUIDE_EN/RU -- title, 1-2 line intro, 3-step quickstart, an 8-row bare command table -- and all still said "22 languages" despite the translate spec expanding to 32 (commit c6d5c2a). Scope kept proportional to what was asked and to each file's own format: added a compact translated "Good to know"-equivalent block (dirty-tree normalcy, KNOWLEDGE/ ADR pattern, capability degradation, install_hook) to all 31 files, in that file's own language, plus the 22->32 fix. Did not attempt a full rewrite to GUIDE_EN.md's complete depth (Steps 1-5 narrative, kitchen section, scenario-annotated command table) -- these 31 never had that content even before this session touched the guides, so bringing them to full parity is a materially larger, separate effort flagged back to the user rather than assumed.
- Both validators green.

## 7.31.1 -- 2026-07-22 -- GUIDE/GUIDE_EN/GUIDE_RU enriched, each in its own voice
User's call: guides were thin. Added four real, previously-undocumented behaviors to all three guides, each written in its own established voice (GUIDE.md neutral, GUIDE_EN.md/GUIDE_RU.md caveman-дед) rather than flattened to one tone:
- Dirty-tree-on-continuation (RFC § 1.5): uncommitted changes at cold-start are normal, not a red flag; agent attributes before touching, never auto-commits/reverts someone else's work.
- KNOWLEDGE/ ADR pattern spelled out: numbered `ADR-001.md` or running `decisions.md`, both legal (RFC § 1.2).
- Capability degradation made concrete: no git/shell means the agent says so plainly (`mode`, `WAIT:`) instead of guessing.
- `tools/install_hook.py` given a one-line setup callout as an optional safety net.

No new protocol behavior -- purely documenting what already shipped. Both validators green.

## 7.31.0 -- 2026-07-21 -- user cleared the pre-advertising checklist, project goes public
- `STATE.md` no longer lists pre-advertising to-dos (cold-run, goal-mode, multi-agent dry-run, fresh release). Plan was user's own reminder, they marked it done. Clean `next_action` now just says "Board empty -- bare saipen -> HUNT".

## 7.30.1 -- 2026-07-21 -- multi-agent pulled from the storefront until it's field-tested
- User's call after the honest pre-advertising assessment: the multi-agent extension has zero live runs behind it, so it does not get advertised. README's Multi-Agent Coordination section removed; the `multi-agent` GitHub topic removed. The extension itself stays fully in the repo (`extensions/multi-agent/`), and every normative reference stays intact -- RFC § 1.4's concurrency boundary, § 1.9's extension discovery, SPEC's architecture tree all still point at it, because the protocol's logic needs the pointer regardless of what the storefront says. Advertising returns after a real Planner/Worker/Integrator field run.

## 7.30.0 -- 2026-07-21 -- second adversarial pass: five holes, two of them self-inflicted last version
Asked what else the audit could catch, the honest answer included attacking my own v7.28.0 fixes:

- **Claim refresh starvation (self-inflicted v7.28.0).** The refresh duty was tied to checkpoints -- but § 1.5 checkpoints fire AFTER tickets, so a 40-minute ticket starved its own claim at minute 15 and made theft of a live, actively-worked ticket perfectly legal under the rules as written. Refresh is now a standing duty: every checkpoint AND a standalone BOARD-only touch at least every 10 minutes of continuous mid-ticket work.
- **The refresh's own side effect on Recovery (consequence of the same v7.28.0 change).** A standalone claim_time touch leaves BOARD.md newer than STATE.md with no STATE write after it -- exactly the mtime signature § 1.5's no-git Recovery heuristic reads as "crash between checkpoint steps 2 and 3." Recovery now checks whether BOARD's difference is claim fields only before rebuilding: live claim, not a crash.
- **"First write wins" was unverifiable as written.** Whole-file BOARD saves mean a concurrent second save silently clobbers the first -- wall-clock "first" can lose at the file level. Claiming now requires verify-after-write: re-read BOARD.md, confirm your claim survived; absent/overwritten = you lost regardless of timing, repick.
- **SHIP treated non-fast-forward as a blocker.** Step 9 sent "diverged history" straight to BLOCKED -- yet for a protocol whose whole pitch is multiple agents and surfaces on one project, "the remote moved while I worked" is routine, not an anomaly (it happened twice in this repo TODAY: a web-UI commit landed mid-ship and was correctly resolved by rebase, against the phase doc's own advice). Step 9 now has the real procedure: fetch, inspect what landed (protocol files or this ship's own files -> read before acting), rebase, re-validate, re-create the tag on the rebased HEAD with the tag==HEAD verification, push again; rebase conflicts -> BLOCKED with facts; force-push stays forbidden.
- **`install_hook.py` misreported inside linked worktrees.** `.git` is a pointer FILE in a worktree (where multi-agent Workers live, per our own extension), so the installer said "no .git here" -- false and confusing. It now detects the worktree case and says the true thing: run from the main checkout, worktrees share its hooks automatically.

## 7.29.0 -- 2026-07-21 -- dirty-tree-on-continuation rule (real cross-agent incident)
- User reported a real incident: agent A left work in the tree, a fresh session then warned "there are uncommitted changes, this is undesirable." The complaint is half-legitimate -- and the protocol had NOTHING on it: `git status` appeared only in Recovery's staleness detection, "uncommitted" only in verify.md's blocked-ticket revert. Nothing told a continuing agent whether a dirty tree is normal, whose changes those are, or what it may do with them.
- New RFC § 1.5 rule, placed before Recovery: uncommitted changes at cold-start are a NORMAL protocol state -- work commits at SHIP, not per checkpoint, so an in-flight ticket's edits are uncommitted BY DESIGN; warning the user about them is noise. The agent MUST attribute them first (`git diff --stat` vs the DOING ticket's scope, LOG tail, kitchen/): attributable -> continue/adopt silently, they fold into that ticket's eventual commit; unattributable (user's own manual edits, another tool) -> leave exactly as-is, MUST NOT commit/revert/stash/clean someone else's uncommitted work (silent revert = user-data deletion per § 1.1; committing = stamping authorship over unreviewed changes). Stop and ask ONLY when unattributed changes sit in the very files the next action must touch -- § 1.1's existing destructive-op gate, no new WAIT category.
- Scenario row 21 + `dirty-tree-continuation` behavioral fixture.

## 7.28.1 -- 2026-07-21 -- perfection sweep: zero warnings, zero dead references, docs caught up to reality
- **The last validator warning is gone.** LOG.md's one remaining `SYSTEM:` taxonomy line (v1-era `saipen clean` event) repaired the same sanctioned way as v7.24.0's 22 lines -- legal `RUN:` prefixed, every original byte kept. First fully clean validation run in the repo's history: zero FAILs, zero WARNs.
- **Three dead references to the deleted `SAIPEN_GAP_MATRIX.md` fixed** (deleted v7.26.0 by kitchen's own stale rule; its citations outlived it): CONFORMANCE row 11 now cites `KNOWLEDGE/decisions.md` + CHANGELOG for the goal_exit rejection; row 13 was stale AND wrong -- it still claimed parent-resolution/ID-uniqueness are "deliberately not validator-enforced" when v7.24.0 enforced both and the ledger repair killed the excuse; `invalid-phase-transition`'s README cites the CHANGELOG decision instead.
- **SPEC.md caught up to v7.24.0+ reality**: the architecture tree had zero mentions of `tools/` (the canonical validator formally didn't exist), still called schemas "not machine-enforced", and described the shell validators without their frozen-floor status. All three fixed.
- **Scenario coverage completed for the new normative rules**: rows 19-20 + behavioral README fixtures for unclaimed-DOING adoption (RFC § 1.4, v7.28.0) and the clean-tree-after-BLOCKED discipline (`phases/verify.md`, v7.27.0).
- `done.md`'s "no separate fix subcommand" note pointed at RFC § 2.4 (Goal Mode); free text is § 1.10's command surface. Citation fixed.

## 7.28.0 -- 2026-07-21 -- adversarial logic audit: the multi-agent core actually holds now
User asked for zero logical holes with the multi-agent amnesia promise as the target. Adversarial pass over RFC.md as a whole -- attacking the rules as written, not the wiring -- found six real holes, all in § 1.4/§ 1.6/§ 2.2:

- **The Pick Rule never referenced claims.** § 1.4 defined owner/claim_time since v1; § 1.6's Pick Rule said only "all needs: DONE" -- a rule-following agent could legally grab a ticket another agent claimed two minutes ago. The claim system existed and nothing consumed it. Pick Rule now excludes tickets under an active claim.
- **"Active owner: ... or actively writing to LOG.md" was undecidable AND contradicted the extension.** A shared file's mtime can't attribute activity to any particular owner -- and `extensions/multi-agent/`'s Workers never write LOG.md at all, so under the extension the test could never be true for exactly the agents it was supposed to protect. Replaced with a decidable refresh-based rule: active = claim_time under 15 minutes, owner (or Integrator) MUST refresh at every checkpoint; a recent `[agent: <owner>]` LOG line (v7.27.0's field, wired one version later) MAY support, never decide.
- **No concurrency boundary was ever stated.** Core now says plainly: claim-serialized tickets, ONE agent writing `.saipen/` at any instant; uncoordinated concurrent checkpoints are outside the envelope (E-### races, last-writer-wins STATE -- the validator catches wreckage, nothing prevents it, by design per SPEC); real parallelism = the multi-agent extension. An agent seeing a fresh STATE.md written by someone else MUST assume a live concurrent session and work only claimed tickets. (`.saipen/lock` stays rejected -- this states the boundary, it does not add coordination machinery.)
- **Zombie DOING tickets had no adoption rule.** A crashed session's `[/]` ticket with no owner fields was formally untouchable -- no rule said a successor may take it. Now: no owner/claim_time = unclaimed by definition; any agent MAY adopt after LOGging a DEC and checking kitchen/ for the predecessor's half-done work. Stale-claim takeover got the same explicit procedure.
- **"First successful filesystem commit wins" said nothing about the loser.** Now: the losing agent MUST re-read BOARD.md and pick a different ticket, never re-assert over the winner.
- **RFC § 2.2's ADD pseudocode still had the missing-ELSE bug T-105 fixed in `phases/add.md` (v7.22.0)** -- the phase doc was corrected, RFC's copy of the same pseudocode wasn't, leaving the spec contradicting its own authoritative phase doc for six versions. Synced.

`multi-agent-claim-conflict` fixture re-checked -- consistent with the 15-minute window and refresh semantics. Both validators green, fixture parity 9/9.

## 7.27.0 -- 2026-07-21 -- the last three proposals land: agent-ID in LOG, clean-tree rollback, pre-commit hook
User gave a blanket go-ahead on the remaining proposal queue. Each got a real design pass, not a transcription of the original suggestion:

- **`[agent: <id>]` in LOG.md (RFC § 1.2, MAY).** Placed after the ticket ref, same id convention as `STATE.md agent:`. Deliberately optional with a SHOULD-omit for single-agent sessions -- one agent repeating its own name 400 times is noise, not traceability. The real audience is `extensions/multi-agent/`: the Integrator stamps Worker ids when folding results into the ledger, so "who did what" lives in LOG itself instead of a kitchen-dir dig. `multi-agent.md` updated to say exactly that; STYLE.md's skeleton line and the validator's LOG grammar extended.
- **Rollback reframed: blocked tickets MUST leave a clean tree (`phases/verify.md`).** The original proposal (snapshot STATE before every BUILD, `restore E-XXX`) solved the smaller half -- STATE/BOARD are tiny and git-tracked; the thing that actually rots a session is the *working tree* keeping a failed ticket's half-broken edits while the next ticket builds on top of them. Nothing in the debug cap said otherwise, so contamination was the default. Now: before picking the next ticket, save the failed attempt (`git diff > .saipen/kitchen/failed/T-###.patch` -- re-appliable, auto-clears under kitchen's stale rule), then revert the uncommitted changes; pre-authorized + reversible, satisfying RFC § 1.1. No git -> copy files to kitchen and say plainly in `| blocker:` that the tree is dirty. No new command surface, no snapshot dirs, no append-only violations.
- **Pre-commit hook (`tools/install_hook.py`).** Stdlib, per-repo opt-in: writes `.git/hooks/pre-commit` running the canonical validator; corruption gets caught at commit time instead of at the next VALIDATE. Finds the validator via the home path baked at install time, falls back to STATE.md's `saipen_home` (v7.25.0 synergy -- the field earns its keep a version later), then the frozen shell floor; a machine with no validator reachable never blocks commits. Tested both directions: green pass-through in the home repo, exit-1 block from a corrupt fixture. Installed in the home repo itself -- every ship commit from now on validates by construction. Existing non-saipen hooks get backed up, not clobbered.
- Runtime manifest grew to 11 files (`install_hook.py` rides the existing `tools/` distribution); `phases/validate.md` documents the hook one line under the canonical-validator paragraph.

## 7.26.0 -- 2026-07-21 -- distribution integrity machine-checked; full HUNT sweep of the home repo
- **The v7.22.3/v7.25.0 bug class is now a validator FAIL, not archaeology.** Three new home-repo checks in `tools/validate.py`: (A) every phase named in RFC.md's phase enum must have its `saipen/phases/<name>.md` doc, both directions (orphan docs warn); (B) a 10-file runtime manifest (SKILL/UI/STYLE, validator scripts, schema, templates) must exist in the home; (C) both injector scripts must actually reference every runtime dir they're supposed to distribute (`phases`/`tools`/`tests`/`schemas`/`templates`). Negative-tested for real -- temporarily hid `done.md`, watched the FAIL fire with exit 1, restored, green again. A sixth phases-class bug now costs one validator run to find instead of a review cycle.
- **HUNT sweep of the home repo itself (all six hunt.md signal categories), findings fixed:**
  - *Silent failures (cat. 4):* both injectors' `Copy-Skill`/`copy_skill` reported "copied" even if every single copy failed -- `$ErrorActionPreference = "Continue"` / no `set -e` swallowed errors while the report claimed success. Both now report `copy FAILED (<dst>)` on any failure. Same hardening for `Remove-Skill`/`rm_skill` in the uninstallers ("skill removed" over a failed `rm -rf` was the same lie).
  - *Symmetry gaps (cat. 5):* the uninstallers' Aider cleanup still matched the OLD one-line conf format -- against v7.25.0's two-line block it would have stripped the `read:` key and RFC line but left the STYLE line orphaned as broken YAML. Worse, `uninstall.sh` ran `sed '/read:/d'` -- deleting EVERY line containing "read:" anywhere in the user's own conf. Both rewritten to remove exactly the injector's block (comment + read: + consecutive saipen items), nothing else, CRLF-tolerant on the PS side.
  - *Dead code/orphans (cat. 6), dogfooding v7.23.0's own kitchen rule:* `.saipen/kitchen/`'s two evidence docs (PART2_CANONICAL_MAP, SAIPEN_GAP_MATRIX) met the new stale definition exactly -- owning work DONE and off the board, content fully folded into CHANGELOG entries. Deleted per the rule HUNT now carries. First real exercise of that rule since it shipped.
  - Categories 1-3 (failing tests, unverified commits, stale TODOs) came back clean -- validators green, every ship logged, all TODO matches are protocol vocabulary, not stale markers.
- `export.ps1`/`.sh` reviewed, already correct (no file lists to drift, explicit failure paths) -- untouched.

## 7.25.0 -- 2026-07-21 -- promised-but-never-wired sweep: four more phases-class bugs
User asked whether more bugs of the v7.22.3 class exist ("the spec promises X, the wiring never delivers X"). Systematic sweep of every cross-file promise against what's actually distributed found four:

- **RFC § 1.7's bootloader was a dead letter since day one.** The section reads "saipen set... MUST write a bootloader to `.saipen/STATE.md` pointing to the canonical `saipen/` home path" -- and grep found zero implementation anywhere: no field in the STATE template, nothing in `phases/init.md`, nothing in the schema, nothing in this repo's own STATE.md. An agent cold-opening `.saipen/` on a machine without global injection had no path to the protocol at all -- the core continuation promise, unwired. Now concrete: `saipen_home` frontmatter field (MAY -- pre-v7.25.0 states legally lack it), defined in RFC § 1.2/§ 1.7, `state.schema.json`, the STATE template (ships empty, `init.md` says fill it), and this repo's own STATE.md. Dead path on a different machine -> clone the repo, update at next checkpoint.
- **`extensions/templates/` was never distributed.** `init.md` insists "Copy `extensions/templates/`... do NOT freehand the schema" -- but skill copies never received templates, so skill-only platforms ALWAYS hit the degraded freehand path. Injector now ships `extensions/templates/` (KNOWLEDGE/ starter included, recursively).
- **`tests/` was never distributed.** `validate.md`'s no-Python fallback ("run `tests/validate.sh`/`.ps1`") pointed at files skill-only platforms don't have. Injector now ships the two validator scripts into `tests/` (scenarios stay home -- they're development fixtures, not runtime).
- **Aider only ever got RFC.md.** Every other platform's boot promise is "RFC.md + STYLE.md"; Aider's conf got half of it. Both injector scripts now write/append/report both paths.

Verified live: injector re-run, skill copy now carries `phases/ tools/ tests/ extensions/{schemas,templates}`, python + bash validators both green with the new `saipen_home` field present.

## 7.24.0 -- 2026-07-21 -- canonical Python validator, LOG ledger repair, T-none ratified
- **`tools/validate.py` -- new canonical validator.** Python stdlib only, zero installs, run from a project root. Covers every check the shell pair performs plus what shell structurally can't do well: E-### uniqueness + monotonicity, parent-reference resolution, ticket-line grammar (malformed lines and unknown BOARD fields now caught instead of silently skipped), UTC enforcement on `updated`, `blocker` non-empty when `phase: BLOCKED`. Failures collect instead of dying on the first; repeated style-drift warnings aggregate by category instead of drowning the signal. `--strict` promotes warnings to failures. Verdict parity with the shell pair verified on all 9 structural test fixtures.
- **`extensions/schemas/state.schema.json` is now live, not reference.** The validator interprets its required/enum/type subset directly -- the schema file is the single source of truth for STATE's field list, ending schema-vs-validator drift by construction. `board/log.schema.json` stay descriptive (they model a parsed representation; the validator checks the raw Markdown grammar natively). `extensions/schemas/README.md` updated accordingly.
- **LOG.md ledger repair (user-approved).** The new uniqueness/monotonicity checks instantly exposed real corruption the shell validators never saw: E-numbering had restarted at least three times across the VAC-era history (E-001..E-016 duplicated wholesale, adjacent-line duplicate IDs scattered through the E-116..E-154 era), 22 lines had their taxonomy label eaten by the old encoding incident, and one parent pointed at E-095 -- an event that never existed (E-080..E-095 were lost at the v6.0.0 rebrand). Repaired per `phases/validate.md`'s shape-only rule: 487 events renumbered sequentially, 451 parent refs remapped to the nearest preceding instance, 1 parent reattached to its true predecessor, `RUN:` inserted on the 22 taxonomy-eaten lines. Verified byte-identical content outside the ID columns and those 22 insertions (mechanical diff, not eyeballing); the pre-repair file is permanently in git at `789e103`; the repair itself is recorded as a DEC event in the ledger. 97 structural failures -> 0.
- **`[T-none]` ratified (RFC § 1.2).** 339 historical lines used it; RFC's letter said "omit the field". Formalized as a legal explicit no-ticket marker -- it distinguishes "no ticket" from "forgot the field", same formalizing-working-practice reasoning as v7.22.0's fifth WAIT category. Any other non-numeric value in the position stays non-conformant.
- **`phases/validate.md`**: canonical order is now Python-first with the shell pair as § 1.3 capability degradation. Fixed the phase doc's own conformance bug while in there: it instructed logging `FAIL: no terminal...` -- `FAIL` isn't in RFC's closed RUN/DEC/H taxonomy; reworded to a legal `RUN:` line.
- **`tests/validate.sh` / `validate.ps1` frozen** as the portable floor for hosts without Python -- headers say so; new checks land only in `tools/validate.py`. One implementation grows instead of two staying in sync by hand.
- **Injector** now also distributes `tools/` + `extensions/schemas/` into every skill copy (validate.py resolves the schema relative to itself, so they travel together); verified the skill copy validates standalone.

## 7.23.0 -- 2026-07-21 -- user decisions on the external review: kill multilingual, merge version fields, auto-clean kitchen
User read the external review's 5 complaints, made three explicit calls, all implemented and verified:

- **STYLE.md multilingual sprinkle, removed.** "~25% English, ~10% eesti, ~5% 日本語" is gone -- decided it was noise, not style: an untranslated word in a language the reader doesn't know costs a lookup for zero payoff. One language per response now, the user's own, дед's attitude carried entirely by tone rather than code-switching. The canonical LOG.md example (which glossed an Estonian word inline, inconsistent with the rule only ever requiring that for Japanese) rewritten to pure Russian, matching the new rule instead of the old inconsistency.
- **`schema_version` + `saipen_version` merged into one field.** User's call: "premature optimization... when the protocol matures, split it again." Verified first this wasn't actually load-bearing anywhere: no `tests/validate.*` assertion reads either field, no `tests/scenarios/` fixture's actual test intent depends on the schema-migration mechanic (the one scenario with "stale" in its name, `stale-state-reconciliation`, tests STATE.md-older-than-LOG staleness, an unrelated concept). `saipen_version` now carries both roles -- informational provenance AND the version-guard mechanic `schema_version` used to own alone. Updated everywhere the field is defined or written: `RFC.md` § 1.2, `extensions/templates/STATE.md`, `phases/init.md`'s bootstrap instructions, `extensions/schemas/state.schema.json`, this repo's own `.saipen/STATE.md`, and all 7 `tests/scenarios/*/STATE.md` fixtures that carried the now-retired field.
- **`.saipen/kitchen/` auto-clean wired into HUNT, not an ignore-file.** User offered two options; ignore-file would have been wrong to take -- RFC § 1.2 requires a successor agent to inspect `kitchen/` to resume crashed work, which only works if kitchen/ is actually committed. Went with the other option: `phases/clean.md` now defines "stale" concretely (owning ticket `DONE` and off `BOARD.md`, or content fully superseded by `LOG.md`/`CHANGELOG.md`), and `phases/hunt.md` checks that same definition every autonomous pass -- kitchen/ no longer depends on a human remembering to type `saipen clean`.

Re-verified: bash + powershell `tests/validate.sh`/`.ps1` both PASS after all three changes.

The other two review complaints (rg/ripgrep absence, CONFORMANCE.md not shipped to consumer projects) were already confirmed non-issues in v7.22.3's evidence and needed no action. Five further "would add" proposals from the user's own follow-up (phase-docs-as-sole-authority, JSON-Schema-as-live-validator, rollback/snapshots, agent ID in LOG, pre-commit hook) are assessed, not yet built -- reported back for a scope decision, several touch normative, closed protocol surface (LOG's fixed line skeleton, the append-only invariant) or the project's stated zero-deps position and deserve a real go-ahead first.

## 7.22.3 -- 2026-07-21 -- injector: phases/ was never actually distributed (real bug, external review)
- fix: `SKILL.md` promises "phase modules in `phases/` -- loaded by boot per STATE.md phase," and RFC.md instructs the agent to load specific `phases/*.md` files as a normal, constant part of every phase transition -- but `Copy-Skill`/`copy_skill` in both injector scripts only ever copied `SKILL.md`/`RFC.md`/`UI.md`/`STYLE.md`, never the `phases/` directory itself. For the two platforms with zero absolute-path fallback (`~/.agents/skills`, Antigravity plugins), this meant phase docs were unreachable 100% of the time -- RFC.md's own referenced files simply didn't exist anywhere on disk. For Claude Code/OpenCode/Codex, the CLAUDE.md/AGENTS.md global block happened to mask it by separately pointing at the original clone's absolute path -- masking, not a fix, and fragile the moment that original clone moves or a teammate's machine never had it.
- An external review caught this precisely: "протокол обещает машину состояний -- а реально `next_action` строка и вся логика во мне, а не в phase-документах." Verified by reading the injector scripts directly rather than taking the claim on faith; confirmed by re-running the injector and inspecting `~/.agents/skills/saipen/` before and after -- `phases/*.md` was absent, now present.
- Fix: both `Copy-Skill` (inject.ps1) and `copy_skill` (inject.sh) now also copy the `phases/` directory into every destination. `CONFORMANCE.md` deliberately NOT added to the copy set -- it's a framework-builder conformance-test doc (same tier as SPEC.md), cited by RFC.md for attribution only, never something a working agent must load at runtime to act (verified: every RFC.md citation of it is a parenthetical reference, and `phases/validate.md` restates all three vectors inline rather than deferring to it).
- Re-verified: bash + powershell `tests/validate.sh`/`.ps1` both PASS after the fix.

## 7.22.2 -- 2026-07-21 -- README: multi-agent section points at the setup doc
- docs: README's Multi-Agent Coordination bullet named the mechanics but gave no link to actually start -- user asked "what command do I run", answer is "none, it's copy-in + manual roles", so the bullet now says that explicitly and links straight to `extensions/multi-agent/README.md` (setup, roles, starter prompts). No behavior change.

## 7.22.1 -- 2026-07-21 -- STYLE.md language-inference fix (real incident)
- fix: `STYLE.md`'s "Base language = user's session language" rule never specified what "session language" means when the user's actual FIRST message carries zero language signal at all -- a bare command like `saipen hunt`, no prose. A real, observed incident: a session responded fully in German off exactly that kind of bare command, with no German anywhere in what the user had actually typed -- the agent evidently inferred language from some ambient signal (IDE/OS locale, platform UI, unrelated context) instead of the user's own words. Clarified: "user's session language" means language evident in what the user actually typed, never inferred from ambient signals; a bare first message with no language signal defaults to English until the user's own words say otherwise.
- Docs-only clarification of existing behavior's intent, not new normative rule -- hence patch tier.

## 7.22.0 -- 2026-07-21 -- PHASE_DOCS_FIX_DIRECTIVE_PART2 (T-100 through T-114)
A user-supplied ticket-by-ticket directive, executed one ticket at a time with an evidence package per ticket, local-commit-only until this final ship (Prime Rule 7: no tag/release without operator confirmation). Every ticket was cross-checked against what earlier rounds this session (through v7.21.0) had already fixed before touching anything -- several tickets turned out fully or partially already satisfied, and are reported as such below rather than re-done.

**Canonicalization (T-100):** No duplicate or conflicting variants of any canonical file (RFC.md, SPEC.md, CONFORMANCE.md, GUIDE*.md, README.md, ship.md) exist anywhere in the working tree -- confirmed by direct search, not assumed. `.saipen/kitchen/PART2_CANONICAL_MAP.md` records the full checklist-vs-grep evidence per file.

**Real bugs found and fixed, not just wording:**
- `add.md`'s evaluation pseudocode had no `ELSE` on the minimal-delta/design-language check -- a genuine, non-minimal improvement opportunity silently fell through the loop to `RETURN DONE`, falsely declaring the product mature even though the phase's own "Act" prose already assumed a ticket-it-and-PLAN path existed. Added the missing branch (T-105).
- `plan.md`'s size gate literally read "skip PLAN, edit, verify, LOG, done" -- going straight from verify to done in the text, contradicting `review.md`'s own "SHIP is mandatory before DONE" rule. Reworded so the gate only ever skips PLAN's detailed analysis, never a correctness gate (T-103).
- `add.md`'s mature-exit branch never explicitly cleared `goal_mode`/`goal_waves`/`goal_tickets` -- RFC § 2.4's Exit rule for this exact case lived only in RFC.md, never operationalized at the point in `add.md` where an agent actually needs to act on it (T-105).

**Normative additions:**
- RFC § 1.2's `WAIT:` enum grows from 4 to 5 legal categories: manual-verify gate, destructive-op confirmation, first-publish confirmation, user's own explicit brake, and now -- narrowly -- `INIT` bootstrap when `BOARD.md` is empty and no project goal exists anywhere yet, asking for the first goal/backlog only. Weighed deliberately since this enum has been closed and tested all session; judged as formalizing already-working `INIT` behavior into the protocol's existing mechanism, not a new behavior or a reversal of any settled decision (T-104).
- `hunt.md`'s 5-file delete-free cap gained an explicit "never user data" floor, matching `clean.md`'s own explicit floor (T-107).
- RFC § 1.2 gained a general clarification: "LOG exactly `RUN: X`" fixed-format instructions mean the `TAXONOMY:text` portion only, the full line skeleton always still applies -- `ship.md`'s two LOG lines (the one file this hadn't reached yet) reworded to match (T-102).

**Docs/clarity sync:**
- `ship.md`: explicit pre-push version-consistency checklist (badge/CHANGELOG head/tag must all agree, new step 3); "PUBLISH is the action inside SHIP, not a separate phase" (the heading's `->` could otherwise misread like a transition-table row); an accurate no-publish note (RFC § 1.3 already blocks entering `SHIP` entirely under no-publish, not just the push step -- the ticket's proposed wording would have implied a scenario RFC's own rule prevents from occurring, written an accurate version instead) (T-101, T-106).
- `translate.md`'s integration boundary strengthened to an explicit negative statement naming the `VERIFY`/`REVIEW`/`SHIP` gates directly (T-108).
- `SPEC.md`'s "SAIPEN MUST remain immutable" (ambiguous enough to read as "project state must never change," the opposite of what a continuation protocol does) replaced with an accurate statement distinguishing the stable protocol contract from constantly-mutating project state (T-111).
- `CONFORMANCE.md`'s TEST-001 reconciled with T-104's new bootstrap `WAIT:` category: a bootstrap `WAIT:` is the same specific-question pattern as the other four, doesn't fail the Continuation Test (T-112).
- `GUIDE_EN.md`/`GUIDE_RU.md` gained the `saipen init` alias mention `GUIDE.md` already had; all 3 guides now list all 10 real commands (T-113).
- `GUIDE.md`, `GUIDE_EN.md`, `GUIDE_RU.md`, and `README.md` all shared the same subtle inaccuracy describing `saipen goal` as running "to completion" with only the wave/ticket cap ever mentioned as a stopping condition -- none of them said what actually happens: shipping the objective isn't a stopping point, it falls into autonomous `HUNT`/`ADD` maintenance until mature, blocked, or capped. This is exactly the misconception the thrice-rejected `goal_exit` proposal was implicitly about; the behavior was always correct, the docs just never said so (T-113).

**Confirmed already correct, explicitly not re-done:** RFC's no-git Recovery fallback, `schema_version` status documentation, "run-scoped" goal_mode wording, VERIFY's transition table row, and the stale hunt-transition note were all already fixed in v7.21.0 (T-110, full no-op). Six of the Core/Maintenance phase docs (`scout.md`, `build.md`, `verify.md`, `review.md`, `blocked.md`, `clean.md`) were swept against 28 checklist items with zero misalignment found (T-109, full no-op).

**Declined sub-proposals, with reasoning, not silently dropped:**
- `blocker: none -> ""` in the STATE.md templates -- would have contradicted this repo's own established convention (`none`, the same pattern RFC sanctions for `task: none`) without real justification (T-104).
- "not tracked content" as an exclusion on `hunt.md`'s delete-free rule -- would have neutered the exact dead-code capability signal #6 exists for, and gets the safety direction backwards (a tracked file's deletion is more reversible than an untracked one's, not less) (T-107).

**Scenario sweep (T-114):** All 16 `tests/scenarios/` fixture directories re-verified. 6 complete-structural fixtures (full `.saipen/`, meant to run through `tests/validate.sh`/`.ps1` directly) all produced their correct expected PASS or FAIL. 3 fixtures (`dependency-cycle`, `multi-agent-claim-conflict`, `resume-after-crash`) are deliberately partial single-file fixtures for a narrow behavioral assertion, confirmed via their own READMEs -- running the full validator against them fails for an unrelated missing-file reason, which is a limitation of a blanket full-pipeline sweep, not a fixture defect. 7 fixtures are behavioral-only by design, no `.saipen/` to run.

**No settled decision reopened:** `goal_exit` remains rejected (referenced again in T-113's wording fix, not reconsidered). `.saipen/lock` for Core concurrency remains rejected -- multi-agent coordination stays the external `extensions/multi-agent/` layer, matching what v7.20.0 already shipped independently of this directive. Full machine-parseable LOG marker grammar remains rejected -- LOG text stays prose around the fixed skeleton.

Minor version: T-104's new WAIT category and T-105's real bug fix plus newly-operationalized goal_mode behavior are normative additions, not just docs clarity.

## 7.21.0 -- 2026-07-20 -- external review round: stale HUNT note, unbounded free-delete, no-git recovery
- fix: RFC.md § 1.6's transition table note still said "`hunt.md` itself does not state this transition explicitly today" -- true when written, but `hunt.md` gained that exact statement in v7.18.0 and nobody went back to update the note pointing at the gap it closed. Same two-source-drift class this protocol fights everywhere else, self-inflicted this time by fixing one side of a cross-reference and not the other.
- feat: `hunt.md`'s "obvious junk -> delete free" had no cap -- a sweep finding many individually-obvious dead files could delete all of them at once with zero confirmation, arguably crossing into "mass file deletion" (RFC § 1.1's own destructive-ops category) without ever technically violating the letter of the rule. Capped at 5 files per sweep, matching the existing ambiguous-ticket cap; more than that gets ticketed for confirmation regardless of how obvious each individual file looks.
- fix: `hunt.md`/`translate.md`'s "LOG exactly `RUN: X -> Y @HASH`" phrasing showed only the taxonomy:text portion, which reads as "write just this string" to a careless agent -- missing the date/`[E-###]`/skeleton RFC § 1.2 actually requires around it. Reworded both to show the full skeleton in the example, matching the clearer pattern `clean.md` already used ("LOG one normal Event Graph line per RFC § 1.2 -- `- DATE [E-###]...`").
- feat: RFC § 1.5 Recovery said flatly "`git status` is ground truth" with no fallback for a `mode: no-publish` or no-git project -- meaning a git-less project hitting STATE staleness had zero defined recovery path. Added a fallback using filesystem modification timestamps across `LOG.md`/`BOARD.md`/`STATE.md`, cross-referenced against the Checkpointing write order the same section already states -- no new mechanism invented, just applying information already there.
- fix: `schema_version` is discussed in RFC § 1.2's Schema migration paragraph but was never actually named in the preceding MUST-frontmatter enumeration, so reading that sentence alone gives no hint the field exists at all. Added a one-clause cross-reference.
- feat: `saipen validate` (RFC § 1.10 and `phases/validate.md`) said "fix structural corruption" with no stated boundary -- this session has drawn a hard line all along (fix shape, never rewrite what actually happened) but it lived only in working practice, never in the protocol text VALIDATE itself is supposed to follow. Made explicit: shape-only, `LOG.md`'s historical event content is never rewritten to make a check pass.
- fix: RFC § 2.4 called Goal Mode "session-scoped," but the persisted `goal_waves`/`goal_tickets` counters exist specifically so a `saipen goal` run survives a crash or a fresh chat session mid-run -- "session-scoped" reads as "dies when the chat does," the opposite of what was built. Renamed to "run-scoped" with a one-sentence clarification.
- Confirmed already correct, no action: CONFORMANCE.md's transition-legality gap (STATE.md doesn't track phase history, so this can't be automated) is already honestly documented in its own Scenario Coverage table as concept #14, not a silent gap -- flagged by the reviewer as "worth remembering, not urgent," which matches what's already there. README/CHANGELOG/GUIDE version currency (the reviewer had no visibility into these files) -- already current, self-checked by the validator since 7.17.0.
- This round came from an external review pasted with corrupted code-block quotes (the actual quoted text was stripped, only placeholder line-count blocks survived) -- every claim was re-derived from the actual current file content before acting rather than trusted from the prose description alone; all 7 acted-on findings confirmed real, 2 confirmed already handled.

## 7.20.0 -- 2026-07-20 -- extensions/multi-agent/ (Coordinator layer, made concrete)
- feat: new `extensions/multi-agent/` reference, the same copy-into-your-project pattern as `extensions/security/`/`extensions/performance/`, but scoped to a whole session instead of one phase. Implements the Coordinator/Server Layer `SPEC.md`'s own Concurrency & Distribution Boundaries section has predicted since it was written -- "SAIPEN is a state protocol, not a distributed consensus algorithm... a thin Coordinator/Server Layer SHOULD be built on top." This gives that layer an actual shape: `README.md` (roles, the one rule that matters -- agents never share live space, only verified results enter it), `lanes.md` (file-glob-to-lane map so the Planner can tell which tickets would collide), `multi-agent.md` (the working agreement -- `.saipen/STATE.md`/`BOARD.md`/`LOG.md` written only by the Integrator, Workers isolated to one `git worktree` + branch each, evidence-package-or-it-didn't-happen), and `prompts/planner.md`/`worker.md`/`integrator.md`.
- Deliberately does NOT touch `RFC.md`'s Core or Maintenance layers beyond one clarifying sentence in § 1.9's existing extensions-are-examples note -- this stays fully additive and opt-in, same as security/performance. No new `BOARD.md` ticket field: `lane:` was considered and rejected -- RFC § 1.2's ticket shape is a closed enum, extending it for one opt-in extension isn't worth the conformance surface. Lane assignment lives entirely in `lanes.md`, cross-referenced against each ticket's already-predicted "files touched" instead.
- Workers don't go silent in `LOG.md` either -- they write to `.saipen/kitchen/agents/<worker-id>/`, and the Integrator folds the meaningful parts into real `LOG.md` entries at merge time, preserving the event-graph granularity this protocol has leaned on all its life instead of collapsing to one "merged T-004" line per ticket.
- `SPEC.md`'s architecture tree and Concurrency section, and `README.md`'s feature list, all updated to reference the new extension so it isn't another `extensions/adapters/`-style orphan from day one.
- This round came from evaluating a detailed multi-agent architecture proposal the user brought in, critically rather than adopting it wholesale -- agreed with its core principle (isolated sandboxes, single ledger writer, evidence over claims) and its own instinct that the Integrator shouldn't be a third autonomous LLM agent yet, while pushing back on the two places it would have added real conformance debt (the `lane:` field, LOG.md going fully silent for Workers).

## 7.19.1 -- 2026-07-20 -- GUIDE Cursor correction, goal_exit ADR
- fix: `GUIDE_EN.md` and `GUIDE_RU.md` both named "Cursor" as an example agent SAIPEN configures -- it isn't one of the actual injector targets (Claude Code, OpenCode, Codex, Gemini, ~/.agents, Aider, Antigravity; confirmed zero mentions of Cursor anywhere in `inject.ps1`/`inject.sh`). `GUIDE.md` already had this right ("Claude, Gemini, Aider, and Antigravity"); its two sibling guides didn't. Swapped the example to Aider, a real target, in both.
- feat: `.saipen/KNOWLEDGE/decisions.md` never recorded the `goal_exit: objective | mature` rejection -- a decision the user was asked to reconfirm three separate times this session, with CHANGELOG 7.13.1 explicitly saying "don't re-propose without new evidence." That instruction was only findable by scrolling CHANGELOG/LOG history, not in the one file whose entire purpose is durable settled-decision record. Added an entry, matching the file's own existing style.
- Both confirmed via a narrowly-scoped audit pass (GUIDE accuracy against the session's latest changes, image asset existence, CHANGELOG version-sequence sanity, decisions.md completeness, this repo's own BOARD.md state) -- everything else checked came back clean: all referenced image assets exist, the 76-entry CHANGELOG version sequence is strictly descending with no dupes or unexplained gaps, this repo's own BOARD.md is genuinely empty with all 4 required headings.
- No RFC or behavioral changes -- documentation accuracy only, hence patch tier.

## 7.19.0 -- 2026-07-20 -- Antigravity install/uninstall parity, export silent-failure fix, remaining audit surface
- feat: **`inject.sh` never wired up Antigravity at all** -- `inject.ps1` has copied the SAIPEN skill into every detected `~/.gemini/config/plugins/*/skills/` directory since v1.2.0, but bash/macOS/Linux users running `inject.sh` never got it, despite README/GUIDE both advertising Antigravity as a taught platform regardless of OS. Ported the same logic to `inject.sh`.
- feat: **neither `uninstall.ps1` nor `uninstall.sh` reversed the Antigravity install at all** -- every other target inject.ps1 touches (Claude Code, OpenCode, Codex, Gemini, ~/.agents, Aider) had a matching uninstall step; Antigravity copies were permanently orphaned by "uninstall." Added to both, in the same plugin-loop shape as the new inject.sh block. All three changes verified in a fully isolated sandbox (fake `$HOME`/`$env:USERPROFILE` pointing at synthetic plugin directories, never the real ones on this machine) -- confirmed inject finds and copies into real-shaped plugin dirs while skipping ones without a `skills/` subdirectory, and uninstall removes exactly the `saipen/` copy without touching the plugin directory itself.
- fix: `bootstrap/export.ps1` and `export.sh` reported "Done" unconditionally after `Compress-Archive`/`tar`, with zero error checking -- a failed archive (bad path, no space, permissions) would still print success. Same silent-false-success class this protocol has hunted down repeatedly elsewhere (ship.md's own "never claim success on a failed push" rule). Added real error handling to both; verified against both a genuine success and a genuine induced failure (invalid destination path) on each platform.
- fix: `phases/build.md`'s `` `ui` flag `` and `phases/hunt.md`'s `## Perf (perf flag)` both referenced an undefined "flag" mechanism -- RFC § 1.10's Command Surface has no notion of flags at all, and these were the only two places the word appeared. Same non-conformance class as done.md's fake commands fixed in 7.18.0. Reworded both to state the actual trigger condition in plain language instead of an undefined mechanism.
- fix: `SPEC.md`'s architecture tree was missing 4 real files directly under `saipen/` (`CONFORMANCE.md`, `SKILL.md`, `STYLE.md`, `UI.md`) and omitted `bootstrap/` entirely despite it being a top-level, README-documented directory.
- feat: `extensions/adapters/` (9 per-platform quick-install files -- read and confirmed current/accurate, not stale) had zero inbound references from README, GUIDE*, RFC.md, or SKILL.md, and isn't copied by the injector -- genuinely unreachable despite being real, valuable content. Not deleted (HUNT's own rule: ambiguous content is ticketed for review, not removed) -- added a one-line pointer from `README.md`'s Quick Start for platforms the injector doesn't auto-detect.
- Confirmed clean, no changes needed: `extensions/security/README.md` and `performance/README.md` match RFC § 1.9 and their attached phase docs exactly; `extensions/templates/BOARD.md` has RFC's exact 4 section headings; `extensions/templates/LOG.md`'s lack of example content is correct per `phases/init.md`'s own explicit "no placeholder line in a fresh project" rule, not a gap; UI.md's px-vs-pt sizing across its web/non-web sections is intentional domain-appropriate units, not a contradiction; all 17 `tests/scenarios/` fixtures re-checked against this session's RFC changes, none depend on stale behavior.
- This round came from a subagent audit of everything not yet deeply checked this session (UI.md, all of `extensions/`, the four bootstrap scripts beyond grep-level, a HUNT-style dead-code self-scan, fixture accuracy, SPEC.md) followed by direct verification before acting -- as usual, some raised items turned out already correct and were left alone rather than "fixed" into noise.

## 7.18.1 -- 2026-07-20 -- caveman-дед named as the one fused chat style
- fix: `STYLE.md` described the chat persona ("дед с района 90-х") and the caveman-compression rule as two loosely-related ideas mentioned in passing near each other. Made explicit what was already true in practice: chat has exactly ONE style, **caveman-дед**, fused not chosen-between -- caveman is the structural half (cut articles/filler/hedging/pleasantries, fewer tokens, cheaper and faster), дед is the tonal half (blunt, sharp, mocks bad code). Retitled the file and the Chat section heading to name it directly instead of leaving the connection implicit.
- feat: the injected `<!-- SAIPEN:BEGIN -->` block (`bootstrap/inject.ps1` + `inject.sh`) now states the chat tone directly -- `Chat tone: caveman-ded (STYLE.md) - compressed + blunt, on by default, off only on "stop caveman"/"normal mode".` -- instead of relying on whoever reads the block to separately discover it inside `STYLE.md`. Kept in plain ASCII deliberately, not `caveman-дед` -- this specific block has stayed ASCII-only its whole life for a reason: Cyrillic inside a PowerShell here-string literal is exactly the class of bug (`Write-NoBom`-bypassing double-encoding) this protocol hit and fixed earlier this session, and there's no need to reopen that risk in the one piece of infrastructure proven not to have it. `STYLE.md`'s own prose, copied via `Copy-Item` rather than typed inline, was never at that risk and keeps the Cyrillic name.
- Both scripts re-tested end to end (two runs each, both platforms): first run `block refreshed` everywhere (content changed), second run `already` everywhere -- idempotency holds.
- No RFC or behavioral rule changes -- this is a naming/clarity pass on an already-active style plus a shorter discovery path for it, hence patch tier.

## 7.18.0 -- 2026-07-20 -- phases-vs-RFC drift audit (goal-mode counters, manual-verify, stale VERIFY loop-back)
- fix: RFC.md's own **VERIFY** section (§ 1.6 prose + the transition table) still described failure "looping back to `BUILD` (max 2 loops) or `SCOUT`" -- an older design `phases/verify.md` has since replaced with something better: a fixed retry cap (3 dead hypotheses or 2 failed fix cycles) that moves the ticket to `## BLOCKED` and lets the agent pick up other workable tickets instead, never a phase transition back to `BUILD`/`SCOUT` at all. Per RFC's own tie-break rule ("phase doc wins"), RFC was the stale one -- both the prose and the transition table row (`VERIFY -> REVIEW | BUILD | SCOUT | BLOCKED` -> `VERIFY -> REVIEW | BLOCKED`) now match what `verify.md` actually does.
- feat: `mode: manual-verify` (RFC § 1.3 -- no shell on the host) was never once checked in `phases/verify.md`, despite RFC § 1.6 explicitly requiring VERIFY to "block and await human confirmation" in that mode. An agent reading only the phase doc had no instruction to do this at all. Added, using the `WAIT:` form RFC § 1.2 already defines for exactly this gate.
- feat: **goal-mode's safety-valve counters were specified but never actually incremented anywhere.** RFC § 2.4 says `goal_waves` bumps "each time `PLAN` runs for a new wave, and each time a `HUNT`→`ADD` cycle completes," and `goal_tickets` bumps "each time a ticket passes `VERIFY`" -- but no phase doc contained an increment step, meaning an agent following only the phase docs during a `goal_mode` run would never learn to touch either counter, silently defeating the whole persisted-counter fix from earlier this protocol's life. Added the increment + the 3-wave/20-ticket cap-check (stop and checkpoint on hit) at all three specified points: `plan.md` (new wave), `add.md` (cycle completion), `verify.md` (ticket passes).
- fix: `phases/hunt.md`'s findings-case transition has been a known, explicitly-flagged gap since the transition table was first built (RFC's own text: "`hunt.md` itself does not state this transition explicitly today") -- only the clean-board-to-`ADD` case was ever explicit. Closed: findings that get ticketed now transition to `PLAN` or `SCOUT` per the same size-gate judgment call as any other ticket.
- fix: **`extensions/templates/STATE.md` -- the canonical template copied by the normal `INIT` path, not just the degraded hand-fallback -- was missing the `mode:` field entirely**, despite RFC § 1.2 listing it as MUST frontmatter. Added (`mode: full`, the same placeholder-then-overwrite pattern as the template's existing `updated:` epoch stub). `phases/init.md`'s hand-fallback field list gained the same field.
- fix: `phases/blocked.md` step 3 ("ask the user for clarification, credentials, or manual intervention") never specified the actual `STATE.md` mechanism for doing so. Now names the `WAIT:` form explicitly, and step 1 now states that arriving in `BLOCKED` with an empty `blocker:` is itself non-conformant (RFC § 1.2) rather than leaving that rule live only in RFC and never checked.
- fix: `phases/ship.md`'s first-publish confirmation (step 6) is exactly RFC § 1.2's "first-publish confirmation" `WAIT:` category, but never used the token. Added a concrete example.
- fix: `phases/done.md` instructed running `saipen (hunt)` and `saipen (add)` -- neither is a real command RFC § 1.10's Command Surface defines, exactly the "undefined command in a phase doc" bug that section's own text calls non-conformant. Both were just informal internal shorthand for "bare `saipen` auto-transitions here" that had drifted into looking like literal command syntax. Rewritten to describe the actual mechanism (bare `saipen`'s § 2.1 auto-transition, `saipen goal <text>` free text, or a normal `PLAN` ticket) instead of inventing commands. This repo's own `STATE.md` had been using the same "(hunt)" shorthand in `next_action` all session -- fixed there too, this entry included.
- This round came from a full phases-vs-RFC drift audit (a subagent checking destructive-ops/secrets-rule references, `WAIT:` propagation, extension present-but-broken handling, the full 14-phase transition table, `blocker` non-emptiness, goal-mode counters, and a general sweep) followed by direct verification of every claim against the actual current file text before acting -- several raised items turned out to already be correctly, deliberately scoped from earlier fixes this session (the CLEAN/HUNT "obvious junk" delete carve-out, the secrets-rule not being restated in `clean.md`/`translate.md`, REVIEW/TRANSLATE's `BLOCKED` transition row) and were left alone rather than "fixed" into duplication.

## 7.17.0 -- 2026-07-20 -- fresh post-directive audit round (validator parity, schema/RFC consistency, conformance completeness)
- feat: `tests/validate.sh` gained real cycle detection. It previously just printed a skip-note ("acyclic check requires powershell/python currently") -- meaning any agent validating on bash (the default on macOS/Linux) got **zero** protection against cyclic `needs:` references, the exact bug class this protocol already fixed once for goal-mode counters. Implemented via Kahn's algorithm (repeatedly resolve tickets whose `needs:` are already satisfied; anything left over after a no-progress pass is a cycle) using plain indexed arrays, not `declare -A` -- macOS ships bash 3.2 as `/bin/bash` by default and associative arrays need bash 4+. Verified on both a synthetic 2-ticket cycle (correctly isolates just the cyclic pair, doesn't false-flag an unrelated third ticket) and a 3-ticket acyclic chain, plus a clean regression run against this repo's own real `BOARD.md`.
- fix: `tests/validate.ps1` had three real gaps against `validate.sh`, not just style differences. (1) No `Test-Path` guard before reading `STATE.md`/`BOARD.md` -- missing either would throw a raw PowerShell exception instead of a clean `FAIL:` message; `LOG.md` had the opposite problem, an unconditional read that would throw if the file didn't exist at all, where bash already skips gracefully. (2) The `KNOWLEDGE/` leak scan was `-Include *.md` with no `-Recurse` -- a leaked event-journal line in a nested subdirectory, or in any non-`.md` file, silently passed. Now recurses the whole tree and checks every file, matching bash's `grep -rE`. (3) The date-separator character class was missing `/` (`[-\.]` vs bash's `[-/.]`) -- a `/`-separated date in a leaked line would silently pass. All three fixed and each verified with a case that would have silently passed under the old code and now correctly fails.
- fix: `extensions/schemas/state.schema.json` contradicted RFC.md outright -- `schema_version` was in the schema's `required` array, but RFC § 1.2 explicitly says it "MAY be absent" (treated as `0` and upgraded at the next checkpoint, the whole point of the migration rule added earlier this protocol's life). A perfectly conformant `STATE.md` could fail schema validation. Fixed: `schema_version` is no longer required (kept as a documented optional property), and `mode` -- genuinely RFC-required but missing from the schema's `required` array -- was added.
- fix: `saipen_version` is written by every real `STATE.md` this protocol has ever produced (`phases/init.md`'s own bootstrap example includes it) and the schema already required it, but RFC.md never actually documented it as a field -- an undocumented-but-load-bearing field, the same bug class as the missing `VALIDATE` entry trigger fixed earlier. Added to RFC § 1.2's STATE.md field list with a one-line description of its purpose (protocol-version provenance, distinct from `schema_version`'s shape-migration role).
- fix: `extensions/schemas/board.schema.json` had a `files` property on ticket objects that RFC's ticket field list (`needs`/`owner`/`claim_time`/`blocker`/`verify`) never defines and no phase doc or template ever writes -- a schema-only orphan. Removed rather than retroactively justified; nothing in the actual protocol produces or consumes it.
- feat: `CONFORMANCE.md`'s Scenario Coverage table was missing 3 of the fixtures actually present in `tests/scenarios/` -- `blocked-ticket` and `fresh-init` existed on disk but were never mapped to a table row (added as concepts 16 and 17). A third fixture, `tests/scenarios/005-add-evolution.md`, predated the current fixture-directory convention (a loose file instead of a `README.md`-in-its-own-directory) and was itself never in the table -- migrated to `tests/scenarios/add-feature-symmetry/` matching every sibling fixture's shape, old file removed, added as concept 18.
- fix: `README.md`'s version badge had drifted stale again (`v7.15.0`, real version two releases ahead) -- the *third* time this exact drift has happened. Fixed, and this time backed by prevention instead of another manual patch: both validators gained a self-check comparing the badge against `VERSION`, gated on `saipen/RFC.md` existing in the working directory so it only fires when run from this repo's own clone root, never against a consuming project's unrelated `README.md`. Verified it correctly skips on a fixture with no such fingerprint, and correctly fails against a deliberately stale badge, on both platforms.
- fix (bookkeeping): `.saipen/kitchen/SAIPEN_GAP_MATRIX.md`'s G-10/G-11/G-12 rows were still listed under "Newly confirmed OPEN items" despite being closed by T-013 (G-12) and T-014 (G-10/G-11) -- the matrix had drifted from the work it was tracking. Updated in place with CLOSED status and the citation that closed each one, re-verified against the actual current RFC.md text before writing.
- Everything in this round came from one fresh audit pass (a subagent tasked with re-checking version consistency, command-surface parity, scenario coverage, validator parity, schema/RFC field consistency, gap-matrix staleness, dead links, and phase-enum coverage against the current repo state) rather than re-litigating anything already settled -- command surface, dead links, and phase-enum coverage all came back clean and needed no changes.

## 7.16.1 -- 2026-07-20 -- legacy ASP/VAC/vacskill removal (user directive: SAIPEN-only, no migrations)
- fix: `bootstrap/inject.ps1` and `inject.sh` had legacy ASP/VACSKILL/VAC migration support baked in from the protocol's earlier names -- block-stripping functions for the old marker format (`Remove-LegacyBlock`/`strip_legacy_block`), a legacy-named skill-directory cleanup function (`Remove-LegacySkill`/`rm_legacy`), a `$legacy`/`$2` parameter threaded through `Copy-Skill`/`copy_skill` and every platform call site, an Aider `.aider.conf.yml` path-migration branch rewriting old `vac`/`vacskill` paths to the new one, and the orphaned `(short alias "vac ...")` mention in the injected block text (never actually defined in RFC § 1.10's own Command Surface -- a dead promise). Per explicit user instruction, none of this is needed anymore: SAIPEN is the only name going forward, not a migration target. All of it removed from both scripts.
- Both scripts re-tested end to end after the rewrite: two full runs each (PowerShell and bash). First run shows `block refreshed` (block text changed -- the `vac` alias line is gone from every already-installed target), second run shows `already` across every target -- idempotency holds after the simplification, same discipline applied to every other change to these scripts this protocol's life.
- Deliberately NOT touched, consistent with this repo's own "don't rewrite history" rule: `.saipen/KNOWLEDGE/decisions.md`'s ADR mentioning `.vac/metrics.md` as a rejected v2.1.0-era idea, and `CONFORMANCE.md`'s footnote citing the real vac -> vacskill -> SAIPEN rename as context for why LOG parent-resolution isn't validator-enforced. Both are historical record of what actually happened, not active migration code -- removing them would falsify the project's own history, not clean it up.
- No RFC or behavioral changes beyond the injected block's own text -- this is bootstrap-script cleanup, hence patch tier.

## 7.16.0 -- 2026-07-20 -- T-014 (security, destructive ops, docs sweep) -- SAIPEN_SPEC_DIRECTIVE.md complete
- feat: RFC.md § 1.1 gained a destructive-operations rule -- force-push, branch deletion, history rewrite, schema drop, mass file deletion, user data deletion, and irreversible migration all require explicit user confirmation unless the active ticket pre-authorizes them AND the operation is reversible. This is SAIPEN's own portable floor, independent of whatever safety discipline any given vendor's agent already has -- the whole point of a vendor-neutral protocol is not depending on that.
- feat: the secrets-hygiene rule (§ 1.1) now names `.saipen/kitchen/` and `.saitranslate/kitchen/` explicitly -- scratch files are exactly as committable as the files already named.
- feat (the docs sweep actually done, not assumed clean): `GUIDE.md`, `GUIDE_EN.md`, and `GUIDE_RU.md` were all missing `saipen translate`, `saipen ship`, and `saipen validate` from their command tables -- 3 of RFC § 1.10's 9 real commands absent from every one of the three guide variants, the same gap in all three independently. Added to all three, matching each file's own existing tone (terse 2-column for `GUIDE.md`, persona-rich 3-column for the EN/RU ELI5 guides).
- fix: `README.md`'s version badge had drifted stale to `v7.6.0` again -- the *second* time this exact drift has happened this protocol's life (first caught at v7.6.1). `ship.md` already says to keep it current; this has been an execution-discipline gap across several rapid narrowly-scoped ships in this directive-execution arc, not a spec gap.
- fix: `SPEC.md`'s `requires:` example was missing `shell` relative to RFC's own actual example.
- **`SAIPEN_SPEC_DIRECTIVE.md` is now fully resolved.** All 15 tickets (T-000 through T-014) have either shipped or been rejected with documented, evidenced reasoning in `.saipen/kitchen/SAIPEN_GAP_MATRIX.md` -- nothing left silently unaddressed. Per the directive's own "Global Definition of Done": every ticket has an evidence trail, both validators pass, positive/negative tests exist for every enforced rule, no known contradictions remain across RFC/CONFORMANCE/SPEC/GUIDE*/README, TEST-001 still passes, and Core still works with Maintenance/Goal Mode/Subagents/extensions all disabled.

## 7.15.0 -- 2026-07-20 -- T-013 (CLEAN/TRANSLATE/extensions safety)
- feat: RFC.md § 1.9 now covers the case it was missing -- an extension *present* but its own requirements (a scanner binary, an API key) aren't met on this host. Degrade and continue if Core's own safety/correctness isn't at stake; go `BLOCKED` if proceeding without it would be genuinely unsafe, rather than silently skipping a check the project explicitly wanted. Also states plainly that an extension can only add checks on top of Core, never weaken what Core already requires.
- feat: `phases/clean.md` gained an explicit safety floor: CLEAN MUST NOT delete user data without confirmation (the existing "clearly unconnected -> delete free, ambiguous -> ticket" rule already implied this, now stated directly), and MUST go `BLOCKED` rather than push through something it can't safely finish auditing -- `DONE` is earned by actually finishing safely, not a default. Also clarified that pruning `[x]` DONE tickets off `BOARD.md` doesn't lose their history -- `LOG.md`'s append-only graph already has every real event for each of them permanently; no new archive/ directory needed, existing infrastructure already serves that role.
- Confirmed, not changed: `phases/translate.md`'s isolation-vs-checkpointing text (fixed two versions ago) already satisfies every one of the directive's proposed TRANSLATE reconciliation points verbatim -- checked line by line, nothing to add.
- Stayed in this ticket's own file scope (RFC.md § 2.1/§ 1.9, `phases/translate.md`) -- no new test fixtures added for the extension present-but-broken behavior even though it's now testable; that's `tests/scenarios/` territory, T-011's domain, not this ticket's.

## 7.14.0 -- 2026-07-20 -- T-011 (conformance scenario coverage)
- feat: closed all 15 of the directive's proposed test concepts, not just the ones with an obvious fixture. 3 new structural fixtures (`dangling-needs-reference`, `read-only-restriction`, `invalid-mode-phase-combination`), each verified to actually fail on both `validate.sh` and `validate.ps1`, not just assumed from the check existing. 2 new behavioral/conceptual scenarios where no structural check is possible (`board-empty-maintenance-transition` -- agent decision-making, nothing to validate mechanically; `invalid-phase-transition` -- `STATE.md` doesn't track phase history, so this can't be automated without new scope, documented honestly rather than faked). The remaining concepts were already covered by existing infra or explicitly N/A (goal objective exit -- moot since `goal_exit` is rejected; unresolved LOG parent -- deliberately not validator-enforced, same reasoning as Event ID uniqueness).
- feat: `CONFORMANCE.md` gained a full Scenario Coverage table -- all 15 concepts mapped to their actual fixture or reasoning for having none, so nothing is a silent gap.
- Full regression sweep across every fixture in `tests/scenarios/` (old and new, 13 directories total): zero unexpected failures. The 3 new invalid fixtures correctly fail with the expected message; the 2 new behavioral ones have nothing to validate and correctly aren't run against the validator.

## 7.13.1 -- 2026-07-20 -- goal_exit closed, second confirmation
- fix (housekeeping, no behavior change): asked the operator directly a second time whether `goal_mode` should gain a `goal_exit: objective` option that stops once the user's literal ask is done -- same question as after T-000/T-001, now specifically re-raised inside T-003. Answer both times: keep current behavior. `.saipen/kitchen/SAIPEN_GAP_MATRIX.md` now marks this CLOSED/REJECTED rather than open -- don't re-propose without new evidence (a real trace showing current behavior actually causing a problem, the bar the original fix cleared). This repo's own `STATE.md next_action` updated accordingly -- the `WAIT:` is now about which `SAIPEN_SPEC_DIRECTIVE.md` ticket comes next, not this settled question.

## 7.13.0 -- 2026-07-20 -- T-003 partial (STATE hardening, goal_exit split out)
- feat: `next_action` now formally supports `WAIT: <specific question>` as a legal executable form -- scoped explicitly to manual-verify gates, destructive-op confirmation, first-publish confirmation, or the user's own explicit brake. Never a stand-in for "figure out project context", which the agent already gets from STATE/BOARD/LOG. `CONFORMANCE.md` TEST-001 clarified so this doesn't read as contradicting "never ask 'what should I do?'" -- asking one exact, pre-determined question instantly is the executable action; the failure mode is vague context-seeking, not a specific authorization gate.
- feat: `blocker` MUST be non-empty when `phase: BLOCKED` -- a blocked state with no stated reason was never actually forbidden before this.
- feat: `updated` MUST be ISO-8601 **UTC** specifically, not just any offset -- Recovery's "is STATE stale relative to LOG/BOARD" comparison (§ 1.5) silently miscompares across agents in different timezones otherwise. This repo's own `.saipen/STATE.md` was already conformant (`Z` suffix throughout).
- feat: schema-version migration rule, using the *existing* `saipen_version`/`schema_version` fields rather than adding a new redundant one -- missing `schema_version` on old state is treated as `0` and upgraded at the next checkpoint; a `schema_version` *higher* than what the running agent's own RFC copy understands degrades to `read-only` or `BLOCKED` rather than silently rewriting state a newer protocol version wrote.
- Declined again, no new argument presented this ticket: a new `schema: "7.7"` field (redundant with the version fields the migration rule above actually uses) and `goal_anchor: T-### | none` (RFC § 2.4's Final Report requirement already covers the same need without a persisted field).
- NOT implemented, split out from this ticket rather than silently reversed a second time: `goal_exit: objective | mature` defaulting to `objective`. Same conflict as before -- would reverse the explicit decision made earlier this session (kept `goal_mode` never exiting on board-empty). Asked the operator directly again rather than letting a second pass through the same ticket text quietly flip it.

## 7.12.0 -- 2026-07-20 -- T-001 (phase enum + transition table)
- feat: RFC.md § 1.6 now states the full 14-value phase enum and a complete transition table, cross-checked line by line against every phase's own `phases/*.md` text before shipping, not copied from the directive's own proposal. Several of the directive's proposed rows were wrong and got corrected: `REVIEW -> SCOUT` isn't stated anywhere in `review.md` (removed); `BLOCKED` only ever transitions to `PLAN`/`SCOUT` per `blocked.md`, not the wide `BUILD|VERIFY|REVIEW|HUNT|DONE` list proposed (narrowed); `ADD` actually transitions to `PLAN`/`SCOUT`/`HUNT` in addition to `VERIFY`/`DONE`, which the proposed table missed entirely (widened). The table states plainly that each phase doc is authoritative and the table is the one that's wrong if they ever disagree.
- feat (found while building the table, not proposed by the directive): `VALIDATE` had no defined entry trigger anywhere in the protocol -- same bug class as the missing `saipen ship` command fixed two versions ago. `saipen validate` added to § 1.10 Command Surface.
- feat: `CONFORMANCE.md`'s Phase Contract Validation vector now references the phase enum and transition table explicitly, not just mode legality.
- Verified: positive test (`PLAN -> SCOUT` appears in the table) and negative test (`INIT`'s row is `PLAN | BLOCKED` only, `SHIP` does not appear) both confirmed by direct grep against the shipped text. This remains a conceptual check, not a live automated transition-legality validator -- `STATE.md` doesn't track phase history (only current phase), and building that tracking is new scope beyond this ticket's stated files (RFC.md § 1.6, CONFORMANCE.md only).
- Logged, not fixed (out of this ticket's file scope, added to the gap matrix instead): `phases/hunt.md` never explicitly states HUNT's transition when findings exist and get ticketed -- only the clean-board-to-ADD case is explicit. The table documents `HUNT -> PLAN | SCOUT` for the findings case as a reasonable inference, flagged as inferred rather than sourced.

## 7.11.2 -- 2026-07-20 -- T-000 (audit + validation harness)
- feat: `SAIPEN_SPEC_DIRECTIVE.md` appeared at the repo root -- a formalized, stricter re-packaging of the earlier external audit, with a strict one-ticket-at-a-time execution protocol (EVIDENCE PACKAGE format, no self-certified done). Executed T-000 only, as instructed: audit + validator hardening, explicitly no normative file changes.
- feat: `tests/validate.sh`/`.ps1` now verify `BOARD.md` actually contains all four required section headings (`## DOING`/`## TODO`/`## DONE`/`## BLOCKED`) -- every other BOARD check (ticket shape, duplicates, dangling refs) scanned content under these headings without ever confirming the headings themselves exist. Verified empirically: a board missing `## BLOCKED` now fails on both platforms.
- feat: added a minimal mode/phase compatibility check -- not the full matrix (still rejected as unnecessary bulk), just the two restrictions already stated in RFC § 1.3 prose: `mode: no-publish` blocks `phase: SHIP`, `mode: read-only` blocks `BUILD`/`SHIP`/`CLEAN`/`TRANSLATE`. Verified in both directions on both platforms (negative: both violations correctly fail; positive: `no-publish` + `DONE` correctly passes).
- feat: produced `.saipen/kitchen/SAIPEN_GAP_MATRIX.md` -- every claim in it backed by an actual grep/validator command and its real output, re-verified before finalizing (one evidence citation was wrong on first draft -- a grep pattern that didn't actually match -- caught and corrected before shipping, not after). Confirmed 3 genuinely new open items in the process: no destructive-ops-confirmation rule exists anywhere in RFC.md (relies entirely on the operating agent's own general safety training, not portable protocol text); the secrets-hygiene rule names STATE/BOARD/LOG/KNOWLEDGE but not `.saipen/kitchen/`/`.saitranslate/kitchen/`; extensions have no defined behavior for "present but its own requirements aren't met" (only "absent" is covered). None fixed this ticket -- logged per the ticket's own scope boundary, not touched silently.
- Not committed: `SAIPEN_SPEC_DIRECTIVE.md` itself. Several of its later tickets (T-001 full transition table, T-002 full mode matrix, T-004 resolver, T-006 marker lexicon, T-012 doctor command) re-assert items already evaluated and rejected with documented reasoning across v7.10.0/v7.11.0/v7.11.1. T-007 defaults `goal_exit: objective`, which would reverse the explicit decision made earlier this session via a direct question to the operator (kept current behavior, grounded in a real stall trace). Flagged to the operator rather than executed past T-000.

## 7.11.1 -- 2026-07-20 -- re-audit found one more real gap
- feat (found on a genuine re-check against the original audit text, not against my own prior summary of it): a dangling `needs:` reference -- a ticket declaring `needs: T-999` where `T-999` doesn't exist anywhere on the board -- was completely undetected. Worse than a cycle: the existing cycle-detector only tracks cycles among tickets that themselves declare `needs:`, so a reference to a ticket that was simply never real gets silently treated as a dependency-free leaf. The Pick Rule becomes permanently unsatisfiable for that ticket with zero diagnostic signal anywhere -- no error, no cycle, nothing, just a ticket that never gets picked, forever.
- RFC § 1.2 now covers it explicitly, same remedy as cycles: move the ticket to `## BLOCKED` with `| blocker: needs nonexistent T-###`, log a `DEC`, keep working other tickets. Both validators detect it now -- verified empirically: a fixture where one ticket needs a real sibling and another needs a ghost ticket correctly flags only the ghost reference, not the real one. `CONFORMANCE.md`'s Session Validation vector tightened to name this explicitly instead of just "acyclic", which doesn't by itself imply references resolve.
- Full regression sweep across every existing scenario fixture confirmed zero new failures from this addition.

## 7.11.0 -- 2026-07-20 -- closing every open item from the audit triage
- feat: `.saipen/` root location stated once, explicitly, in § 1.1 -- individual mentions elsewhere in the document may drop the prefix for brevity without it reading as a different location.
- feat (security baseline, genuinely missing before this): § 1.1 now states agents MUST NOT write secrets (API keys, tokens, passwords, credentials) into `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/` -- these files are meant to be committed and shared across agents. A secret found mid-task gets redacted in whatever gets written, user gets told to rotate it.
- fix: `| verify: <command>` was already a real field -- typed in `board.schema.json` since early in this protocol's life, actively used in the `blocked-ticket` test fixture -- but never made it into § 1.2's RFC prose skeleton when the exact ticket-line format was formalized in v7.8.0. Added, cross-referenced to `phases/plan.md`'s existing "independently verifiable" ticket-shape requirement.
- feat: closed the `goal_anchor` question left open in the audit triage. Concluded a new persisted field isn't warranted -- board order at Entry already carries which tickets are the goal's own vs. demoted backlog, and nothing in current behavior needs to query that distinction to function correctly. What was actually missing is narrower: § 2.4's Final Report line now says to distinguish "the user's original ask" from "picked up along the way" in what gets reported, so the user doesn't have to re-derive it from `LOG.md` -- no schema change required.
- feat: `tests/validate.sh`/`.ps1` now enforce two rules that were normative text with no enforcement: `STATE.md`'s `mode` must be present and one of the four legal values, and `goal_mode: true` requires `goal_waves`/`goal_tickets` to actually be present (not just documented as required). Verified empirically in both directions on both platforms: a fixture missing the counters fails, one with them passes; a fixture missing `mode` entirely fails. The three existing test fixtures that predated `mode` becoming required (`blocked-ticket`, `resume-after-crash`, `stale-state-reconciliation`) got `mode: full` added so they don't newly fail under the tightened check.
- feat: added `tests/scenarios/goal-counter-recovery` (STATE.md stale/pre-dating a goal pivot, LOG.md showing the pivot plus two waves' worth of ticket completions -- the counters must be reconstructed from LOG, not assumed `0`) and `tests/scenarios/extension-absence` (the common case: no project `extensions/` at all, phase must proceed with zero overhead) -- both were proposed in the audit and directly exercise fixes shipped in v7.9.0/v7.10.0 that had no fixture yet.
- Explicitly decided NOT to add a LOG `[E-###]` uniqueness/monotonicity *validator* check (the RFC rule itself, added in v7.10.0, stays as guidance): checked this repo's own `.saipen/LOG.md` before implementing and found real, legitimate numbering resets from the vac -> vacskill -> SAIPEN rename lineage, plus prose that quotes `[E-001]` as text without meaning a duplicate event. A naive enforcing check would immediately and permanently fail against real history that's too risky to renumber (parent: links reference exact IDs; renumbering risks silently breaking the graph). Better to catch this before shipping a check that lies about failing, matching this session's own "verify by running it" discipline turned on itself.
- Everything else from the triage that had no further action needed, made explicit rather than left implicit: ADD's `bugfix -> RETURN HUNT` pseudocode branch is deliberate phase-boundary discipline (ADD hands a stray bug back to HUNT's own signal-driven process rather than improvising a fix outside it), not a defect. CLEAN's authority to touch `.saipen/` structurally is its actual job, not a boundary violation. HUNT's 6 signal categories living only in `phases/hunt.md` (not duplicated into RFC.md) is the 2-tier architecture working as intended. § 2.4's counter-authority split (`STATE.md` primary during normal operation, `LOG.md` fallback only when `STATE.md` itself is being rebuilt) is a coherent primary/fallback design, not competing sources of truth. Slash-command (`/saipen continue`) vs bare (`saipen continue`) framing was never actually ambiguous to a reasonable reader.

## 7.10.0 -- 2026-07-20 -- external audit, evaluated and triaged
- feat (the big one -- a self-inconsistency in this repo's own v7.6.0 work): § 1.9 Extension Discovery told agents to check `extensions/<name>/` "at the project root", but nothing in `init.md` or the injector has ever copied `extensions/security/` or `extensions/performance/` into a consuming project -- the only real copies of those folders live inside the SAIPEN home itself, a completely different location from "project root". The discovery mechanism pointed at a location nothing populates. Fixed: § 1.9 now explicitly distinguishes the SAIPEN home's copies (reference *examples* to copy, same role as `extensions/templates/`) from a project's own `extensions/<name>/` (which a project author creates, the same way they'd add their own `tests/`). Both example READMEs and `SPEC.md`'s architecture tree relabeled to match.
- feat: `mode` was missing from § 1.2's STATE.md required-field list even though § 1.3 requires writing it -- added. `read-only` mode never had its own explicit phase-restriction list (unlike `no-publish`/`manual-verify`, which do) -- added: no `BUILD`/`SHIP`/`CLEAN`/`TRANSLATE`/mutating `ADD`/`HUNT`, advise-only.
- feat: cyclic `needs:` dependencies had a MUST-be-acyclic rule but no agent-facing procedure for when one is actually found. § 1.2 now says move every ticket in the cycle to `## BLOCKED` with the cycle noted, log a `DEC`, keep working other tickets -- reusing the `## BLOCKED` mechanism already built for exactly this kind of "can't proceed on this one, don't stall the session" case. Added a matching `tests/scenarios/dependency-cycle` fixture; verified the existing cycle-detection logic actually flags it and correctly leaves the unrelated third ticket alone.
- feat: LOG `[E-###]` uniqueness/monotonicity and `[parent:]` must-reference-an-existing-event were implied by the graph design but never stated as MUST -- stated explicitly, since Recovery depends on both holding.
- feat: BOARD `T-###` ID uniqueness/no-reuse wasn't stated; an unescaped `|` inside a ticket description is indistinguishable from a field separator in the v7.8.0 pipe-field format -- both fixed (escape as `\|`).
- feat: checkpointing said "on-disk state MUST be atomic" across three separate files, which plain file writes can't actually guarantee without a real transaction. Replaced the unenforceable claim with an enforceable one: a specific write order (LOG append, then BOARD, then STATE.md *last* as the commit pointer) that makes any crash mid-checkpoint land in a state Recovery already knows how to fix, rather than one where STATE.md could claim something BOARD.md doesn't yet reflect.
- feat: Recovery now backs up a corrupt/stale `STATE.md` to `.saipen/recovery/<timestamp>-STATE.md` before overwriting it, instead of destroying the only evidence of what went wrong.
- feat: `saipen ship` was used throughout `phases/ship.md` and § 2.4 but was missing from § 1.10's own Command Surface registry -- ironic, given that section's own closing rule flags exactly this as non-conformant. Added, plus an explicit "unrecognized `saipen <word>` -> list valid commands, don't invent behavior" closing rule.
- feat: `phases/ship.md` never said what to do if `git push` fails -- added: log the failure honestly, retry once if transient, `BLOCKED` if not -- never claim success on a failed push.
- fix: `phases/translate.md`'s "operate EXCLUSIVELY inside `.saitranslate/`" could be misread as suspending normal `.saipen/` checkpointing too. Clarified: isolation scopes the translation work itself, not protocol bookkeeping.
- Triage note: this batch came from a detailed external audit pasted in by the user (a separate agent's pass over the public repo). About half its findings were real and are captured above. Rejected as scope creep against already-established design: a `.saipen/lock` file (SPEC.md already explicitly punts multi-agent coordination to an external layer), a full machine-parseable LOG marker grammar (fights the "text is prose, not code" design), moving VERIFY/REVIEW's caps into Core (they already live correctly in their phase docs -- the reviewer hadn't cross-referenced those), an exhaustive phase-transition table and `saipen doctor` (both already covered by the existing 2-tier phase docs and `status`/VALIDATE respectively). One real design question -- whether `goal_mode` should offer an "exit once the user's literal objective is done" option instead of always falling through to autonomous HUNT/ADD -- was surfaced to the user rather than silently decided either way; kept the current behavior, confirmed by them, since it's what a real WildRiftAssistant stall trace earlier this session already validated.

## 7.9.0 -- 2026-07-20 -- reliability pass before extended live test
- feat (critical for long autonomous runs): Goal Mode's safety valve -- "MUST NOT process more than 3 waves or 20 tickets" -- had no persisted counter anywhere. The cap could only be enforced by an agent counting purely within its own current context window. SAIPEN's entire premise is that any agent, after any restart, continues correctly from disk state -- but this specific mechanism silently reset to zero on every crash, machine restart, or agent handoff, exactly the scenarios a long-running goal_mode invocation is expected to encounter. A genuinely long run could in principle never hit the cap at all if it spanned more than one process. Fixed: `STATE.md` now carries `goal_waves`/`goal_tickets` (RFC § 1.2, § 2.4), bumped and checkpointed the moment they change, so any agent resuming mid-run reads the true count directly from disk instead of losing it. Both fields added to `state.schema.json`. § 1.5 Recovery also covers the edge case where `STATE.md` itself needs rebuilding: reconstruct the counters by counting completion events in `LOG.md` since the goal's pivot line, never assume `0`.
- Reliability pass also checked and confirmed sound (no fix needed): VERIFY's 3-hypotheses/2-fix-cycle cap and REVIEW's 2-pass cap are both scoped to a single ticket/finding and naturally recoverable from that ticket's own `LOG.md` entries on restart -- unlike the goal-wide safety valve, a restart re-approaching with a reset counter is tolerable there, not a silent defeat of the mechanism. The default (non-goal_mode) HUNT<->ADD Maintenance loop is intentionally uncapped by a number -- its stopping condition is ADD's own qualitative "product is mature" judgment, not a quantitative ceiling, which is by design, not a gap.

## 7.8.2 -- 2026-07-20
- fix: `saipen/UI.md` -- the mandatory Win95 dark-golden UI spec, copied to every agent install via the injector and referenced by a standing global instruction for all UI work -- had never been read or audited this entire session despite being touched constantly by reference. Found the same PowerShell double-encoding mojibake as everywhere else this cycle: em-dashes, the `x` in `640x480`, and the `<=`/`>=` comparison symbols in the accessibility floor were all corrupted. The actual CSS token block was already clean (corruption was confined to prose bullets, never in executable values), but fixed throughout for consistency with the rest of the now-clean repo. Verified: zero non-ASCII bytes remain, no BOM.
- Checked in passing: GUIDE.md's `status`/`stop` command descriptions are consistent with RFC § 1.10's fuller normative definitions (simpler wording, same behavior, no conflict) -- no fix needed. All image assets referenced by README/GUIDE/SPEC exist on disk -- no broken links.

## 7.8.1 -- 2026-07-20
- fix: regression-tested the new BOARD.md duplicate-ticket check (v7.8.0) against every `tests/scenarios/*` fixture to make sure it didn't false-positive on existing test data. It didn't -- but the sweep surfaced a real pre-existing issue unrelated to the new check: `stale-state-reconciliation/.saipen/LOG.md`'s one line was missing `[E-###]` entirely (`- 26.07.17 00:00 [T-001] DEC: ...`), non-conformant to the § 1.2 skeleton. Fixed. The other apparent "failures" during the sweep (`multi-agent-claim-conflict` missing STATE.md, `resume-after-crash` missing BOARD.md) were false alarms on my part -- those fixtures are deliberately minimal, illustrating one specific mechanic each, not meant to be complete bootable `.saipen/` dirs; running the full validator against a partial-by-design fixture isn't a fair test. Confirmed via direct inspection that both fixtures' existing files already conform to the current schemas.
- fix: RFC.md's KNOWLEDGE/ line said "Uses ADR pattern (`ADR-001.md`)" but checked the real evidence -- of the three live projects plus this repo's own `.saipen/KNOWLEDGE/`, three of four use descriptive filenames (`architecture.md`, `minimap-arch.md`, and this repo's own `decisions.md`/`traps.md`); only one uses literal `ADR-001.md` numbering. The actual constraint that matters (and that both validators already enforce) is "no event-history syntax leaking in" -- the filename was never the real rule. Reworded to explicitly name both as valid: a living descriptively-named reference doc, or a numbered immutable ADR for a single formal decision -- matching what agents already do successfully instead of a convention almost nobody, including this repo, was actually following. `extensions/templates/KNOWLEDGE/ADR-001.md` is unaffected -- it's a genuinely well-structured template for the formal-ADR case, kept as one of the two options, not the only one.
- Content check (not a fix, a finding): all three live projects' `KNOWLEDGE/` files were read in full and are completely clean -- zero event-history leakage, genuinely useful durable notes. This was the smaller of two field-audit rounds; noting it honestly rather than padding the finding to match the last one's size.

## 7.8.0 -- 2026-07-20 -- field audit round 2
- feat (found via live field evidence, not text auditing): re-checked the three real projects using SAIPEN (FastPrompter, Wintage, WildRiftAssistant) now that the LOG skeleton fix has had a day to land. Found BOARD.md has the exact same "structure named but no exact skeleton" gap LOG.md had before v7.5.0 -- and it's producing the same kind of real divergence: FastPrompter's BOARD.md has all 6 tickets listed twice, verbatim; Wintage's BOARD.md isn't headings at all, it's a markdown table -- a third schema; WildRiftAssistant's BOARD.md has duplicate `## DONE`/`## BLOCKED` headings with the same four tickets listed simultaneously `[x]` done under one and `[ ]` blocked under the other, self-contradictory, and it independently invented a `## BLOCKED`-style heading *before* this repo's own v7.6.0 shipped it -- strong convergent evidence the gap was real. `tests/validate.ps1`'s own cycle-detector already implicitly assumed a `- [ ] T-### ... needs: ...` shape that RFC.md never actually wrote down as MUST.
- feat: RFC.md § 1.2 now states the exact BOARD.md ticket-line skeleton: `- [ ] T-### description` plus optional ` | needs:` / ` | owner:` / ` | claim_time:` / ` | blocker:` fields, and states explicitly that a status change MUST move the line (cut from old heading, paste under new) and MUST NOT leave a duplicate behind -- the precise rule the field evidence shows agents violate without it.
- feat: `phases/clean.md`'s Board Scrub gained a structural-repair step matching the corruption patterns actually found in the wild: any ticket ID appearing more than once (within a section or across two) gets reconciled against `LOG.md`'s record of its true final state, keeping exactly one line under the correct heading; duplicate section headings get merged.
- feat: both `tests/validate.sh` and `validate.ps1` now detect duplicate ticket IDs across `BOARD.md` and fail loudly instead of staying silent -- this exact class of corruption was invisible to both validators before today. Verified empirically both directions: a deliberately corrupted fixture (mirroring WildRiftAssistant's real duplicate) fails both validators as expected; this repo's own clean `BOARD.md` still passes both.
- Positive finding worth noting: WildRiftAssistant's LOG.md shows real self-correction in the wild -- older entries used phase names (`[HUNT]`, `[FIX]`, `[GOAL]`) as the taxonomy, exactly the mistake RFC § 1.2 names and forbids, but entries from today's session correctly use `RUN`/`DEC`/`H` throughout. The root-cause fix (moving the skeleton into always-loaded RFC.md instead of leaving it only in STYLE.md) demonstrably works once an agent picks up the updated protocol, not just in theory.
- Note: as with the LOG audit, none of the three live projects' own `.saipen/` files were touched -- that's the user's active work under other agents' hands. This fix is forward-looking; existing corruption in those boards will only clear once each project's own agent runs `saipen clean` under the updated protocol.

## 7.7.2 -- 2026-07-20
- fix (real, same class as the original VERIFY-loop bug this whole audit arc started from, this time on REVIEW): swept every numeric cap RFC.md cites against the phase doc that's supposed to implement it. Found `§ 2.4`'s "Unchanged under Goal Mode" bullet claims REVIEW has a "2 review passes per finding" cap, but `phases/review.md`'s actual cap -- "LOG has a verdict on this finding -> NO + ticket, stop cycling" -- is circular: a verdict gets logged every single pass regardless, so nothing ever forced it to *become* `NO -- BLOCKER` after repeated failures on the same finding. Unlike VERIFY's explicit "3 dead hypotheses OR 2 failed fix cycles", REVIEW had no real numeric ceiling -- a finding that kept coming back almost-fixed could cycle BUILD -> REVIEW -> BUILD indefinitely, never tripping the stop condition. `review.md` now states the 2-pass cap explicitly: pass 1 finds it, BUILD fixes it, pass 2 re-checks; still broken -> verdict MUST become `NO -- BLOCKER`. Findings are identified by `file:line`, so a new finding surfaced by the fix itself gets its own fresh count rather than being silently absorbed into the old one's tally.
- Every other numeric cap RFC.md cites was cross-checked and already matches its phase doc exactly (VERIFY's 3/2 cap, the 3-wave/20-ticket Goal Mode safety valve, the 15-minute claim window) -- this was the one gap in an otherwise consistent set.

## 7.7.1 -- 2026-07-20 -- final control review
- fix (real RFC-2119 self-contradiction): § 2.3 The Industrial Completion Rule said "the agent SHOULD implement the minimal coherent set" in its opening paragraph, then two lines later said "The agent MUST complete the minimal coherent set" for the exact same obligation -- SHOULD and MUST have meaningfully different force under the RFC 2119 keywords this document itself invokes (§ 1.1). Resolved by splitting what was actually two distinct obligations conflated into one: whether the rule applies is a judgment call (stays SHOULD), but once triggered, implementing it is a discipline requirement (now MUST, matching the smallest-complete-solution bullet). `phases/add.md`'s parallel wording had the same clauses inverted (MUST evaluate, MUST implement) -- aligned to match: SHOULD evaluate, MUST implement.
- fix: § 1.2's `## BLOCKED` bullet cited "§ VERIFY debug cap" -- malformed, `§` denotes a numbered RFC section and VERIFY's debug cap isn't one (it lives in `phases/verify.md`). Fixed to cite the file directly, no more phantom section number.
- fix: "the Pick Rule" was cited by name in § 1.2 (`## BLOCKED` bullet) and has been used in chat throughout this session, but § 1.6 -- the section actually being cited -- never named it; it only described the behavior inline. Formally bolded as **Pick Rule** at its point of definition in § 1.6 so the cross-reference resolves to a real term instead of an inference.
- fix: § 1.10's citation for `saipen continue` / bare `saipen` pointed only at § 1.1 (general read requirement) and missed § 2.1's DEFAULT BEHAVIOR bullet, which is the actual normative definition of what the bare command does. Added.
- fix: `.gitattributes` had only a bare `* text=auto` with no per-type override. Added `*.sh text eol=lf` as defensive hardening for the bash scripts this project ships and depends on running correctly on macOS/Linux -- verified against the actual git blobs that current line endings were already clean LF (no corruption existed; this is prevention, not a fix for existing damage).
- fix: `.gitignore` still carried `.asp/tmp/`, `.asp/history/`, `.vac/tmp/` -- dead patterns for directory names nothing in the current SAIPEN naming scheme has created since the vacskill/ASP-era rename. Removed; only `.saipen/` and its `kitchen/` subdirectory exist today, and `kitchen/` is intentionally NOT gitignored (RFC § 1.2: a successor agent MUST be able to inspect it after a clone, so it needs to stay tracked).
- removed: `style/` (`default.md`, `grandpa.md`, `concise.md`, `corporate.md`) -- a designed-but-orphaned mechanism for switching the chat voice mid-session (`style corporate`, `style concise`, etc.). Zero references anywhere in the live protocol tree (RFC.md, STYLE.md, SKILL.md) -- an agent had no way to discover it existed, and two of the four files carried the same mojibake corruption fixed elsewhere this cycle. STYLE.md has since consolidated on a single caveman+dedy voice as SAIPEN's identity, not a menu of swappable personas, so this wasn't a gap to wire up -- confirmed dead code (HUNT signal #6) and removed with the user's explicit sign-off rather than assumed unilaterally.
- Verified: both validators pass, full repo-wide BOM sweep (every tracked file, not just ones touched this session) found zero BOM anywhere, git tags/VERSION/CHANGELOG head all agree at every step.

## 7.7.0 -- 2026-07-20
- feat: found the same phantom-command bug class as the `saipen fix` fix, except worse -- `saipen status` and `saipen stop` are two of the six commands in GUIDE.md/GUIDE_EN.md/GUIDE_RU.md's primary user-facing command table, each with clear, specific promised behavior ("read-only report", "checkpoint and hand control back"), and neither has ever had a single line of backing definition in RFC.md or any `phases/*.md`. An agent reading only the actual protocol tree (not GUIDE.md, which it has no obligation to load) would have nothing to go on if a user typed either.
- feat: new RFC.md § 1.10 Command Surface. Formalizes `status` (read-only, MUST NOT write or perform work, even under `goal_mode`) and `stop` (immediate § 1.5 checkpoint, then halt -- overrides `goal_mode`, the user's manual brake always wins) as normative MUST behavior matching what GUIDE.md already promised. Also lists every other recognized command with a cross-reference to where it's actually defined, turning this into a registry -- closes the whole bug class, not just these two instances, since any future `phases/*.md` doc inventing an undefined command now has an explicit place it should have been declared and wasn't.
- Verified: both validators still pass, RFC.md non-ASCII sweep confirmed clean (only legitimate UTF-8 `§`, no mojibake), no BOM.

## 7.6.1 -- 2026-07-20
- fix: `phases/done.md` item 3 told agents to run `saipen fix SYMPTOM` -- a command that doesn't exist anywhere else in the protocol. Not in RFC.md, not in GUIDE.md's command table, not in SKILL.md. The correct entry point per RFC § 2.4 is bare `saipen <text>`; done.md now says that instead of a phantom subcommand.
- fix: `phases/validate.md`'s own summary of the "three conformance vectors" had drifted from `CONFORMANCE.md`'s wording (itself just fixed in v7.6.0) and used the ambiguous word "schema" again -- exactly the term v7.6.0 had to disambiguate. Also neither doc previously listed `KNOWLEDGE/` as part of Repo Validation despite both validators actually checking it as a fourth vector. Both docs now say the same thing, matching what the scripts do.
- fix: `phases/clean.md`'s Board Scrub step never mentioned the `## BLOCKED` section added in v7.6.0 -- a gap CLEAN itself created a precondition for. CLEAN now re-checks every `## BLOCKED` ticket: blocker resolved elsewhere -> back to `## TODO`; still stuck and abandoned -> pruned like a stale `TODO`. `## BLOCKED` was at risk of becoming a graveyard nothing ever revisits.
- fix: `SPEC.md`'s architecture tree listed `verify.md` under "Maintenance Phases" -- wrong, VERIFY sits directly in the Core ticket DAG (RFC § 1.6: `BUILD -> VERIFY -> REVIEW`), every ticket passes through it, it has nothing to do with autonomous HUNT/ADD/CLEAN evolution. Moved to Core Phases where build.md/review.md already are. Also reworded the `schemas/` tree entry from "canonical file schemas" to "reference file schemas (not machine-enforced)" to stop contradicting the v7.6.0 CONFORMANCE.md fix, and noted RFC § 1.9 on the `security/`/`performance/` entries now that they're actually discoverable.
- fix: `README.md`'s version badge had drifted to `v7.4.2` (real version several ships ahead at time of fix: `v7.6.0`) -- `phases/ship.md` step 1 already says the README's version must be current, this was pure execution drift across several ships, not a spec gap. Corrected; watch this going forward, it has now drifted twice.

## 7.6.0 -- 2026-07-20
- feat: new RFC.md § 1.9 Extension Discovery. `extensions/security/` and `extensions/performance/` both said "MUST read this directory" for VERIFY/REVIEW respectively, but nothing in the always/on-demand-loaded protocol tree (RFC.md, `phases/verify.md`, `phases/review.md`) ever told an agent these hook points existed -- a completely undiscoverable "MUST". § 1.9 now states the general extension-discovery rule (check `extensions/<name>/` on entering its stated phase; absent = zero overhead, never gates a transition), and `verify.md`/`review.md` each gained one concrete line pointing at their respective extension. `extensions/schemas/` is carved out explicitly as the one non-behavioral exception (see below).
- feat: resolved the long-standing "how exactly is a blocked ticket marked" gap. `BOARD.md` gains a fourth section, `## BLOCKED`, alongside `## DOING`/`## TODO`/`## DONE` -- distinct from session-level `STATE.phase: BLOCKED`. `phases/verify.md`'s debug cap now says concretely "move THIS ticket to the `## BLOCKED` section" instead of the previously vague "mark THIS ticket blocked". The Pick Rule already only ever selects from `## TODO`, so a blocked ticket is excluded automatically, no extra filtering logic needed anywhere. Applied to `extensions/templates/BOARD.md`, this repo's own `.saipen/BOARD.md`, `phases/init.md`'s bootstrap skeleton, and `board.schema.json` (new `BLOCKED` enum value + `blocker` field). Also fixed three `tests/scenarios/*/.saipen/BOARD.md` fixtures (blocked-ticket, stale-state-reconciliation, multi-agent-claim-conflict) that had bare checkbox lines with no section headings at all -- didn't match the canonical format they were supposed to demonstrate.
- fix: `CONFORMANCE.md` flatly contradicted `extensions/schemas/README.md`. CONFORMANCE claimed "STATE/BOARD/LOG MUST conform to extensions/schemas/" as a normative MUST; the schemas' own README says "no agent reads these... frozen until an orchestrator exists" -- confirmed true by grepping `tests/validate.sh`/`validate.ps1`, which check shapes via plain regex against the Markdown files directly and never touch the JSON schemas at all. CONFORMANCE.md now correctly points at RFC.md § 1.2 (enforced by the validators) and describes the schemas as a forward-looking, not-yet-enforced reference.
- fix: all three `extensions/schemas/*.json` files still had `"title": "VAC ... Schema"` (pre-rename leftover). `state.schema.json`'s `phase` enum was missing `INIT`/`HUNT`/`ADD`/`CLEAN`/`TRANSLATE`/`VALIDATE` and had no `goal_mode` property at all despite it being a documented RFC field. All synced to current reality -- title, phase enum, `goal_mode`, and (see above) the new `BLOCKED` board status. Verified all three still parse as valid JSON after editing.
- fix: mojibake em-dash in `extensions/schemas/README.md` (same corruption class as v7.5.1/7.5.2), cleaned in place.
- Both `tests/validate.sh` and `validate.ps1` re-run against this repo's own `.saipen/` after every edit in this batch -- still pass throughout, including after the `## BLOCKED` heading addition (the cycle-detection regex is heading-agnostic, confirmed rather than assumed).

## 7.5.2 -- 2026-07-20
- fix (real bug, not cosmetic): `bootstrap/inject.ps1` and `inject.sh` were never actually idempotent despite both claiming it in their own header comments. `Remove-LegacyBlock`/`strip_legacy_block` unconditionally stripped ANY `<!-- SAIPEN:BEGIN -->` block -- including a perfectly current, already-installed one -- before `Add-Block`/`add_block` ever got a chance to check "is this already installed". That made the "already"/"upgraded" branch permanently dead code: every single re-run silently stripped and rewrote every target file (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.config/opencode/AGENTS.md`, `~/.gemini/GEMINI.md`) and reported it as `"migrated from VAC"`, forever, even on a machine that has never seen VAC. The bash version had a second, independent instance of the same root problem: `strip_legacy_block` always returned success regardless of whether it matched anything, so even a brand-new file being created for the first time got mislabeled `"migrated from VAC"` too.
- fix: both scripts now compare the existing `SAIPEN:BEGIN...END` block's content against the canonical block before touching the file at all -- identical content returns `"already"` untouched; different content (stale path, old wording, a real pre-refresh block) returns `"block refreshed"`. Legacy `ASP:BEGIN`/`VACSKILL:BEGIN` stripping is unaffected and still works exactly as before -- only the case that was never actually "legacy" (a current SAIPEN block) stopped being needlessly destroyed. Verified empirically by running each script twice in a row: first run legitimately refreshed stale blocks (leftover from before this fix), second run reported `"already"` across every target with zero file writes -- true idempotency, not assumed.
- fix: mojibake in both scripts' own header comments (PowerShell double-encoding artifact, same corruption class as the v7.5.1 adapters bug) -- `sed`/`Edit` couldn't match the corrupted bytes for either file, so both were rewritten clean via full-file `Write` in plain ASCII, same fix strategy as v7.5.1. Full BOM/non-ASCII sweep on both confirmed clean.

## 7.5.1 -- 2026-07-20
- fix: all 9 `extensions/adapters/*.md` platform files (aider, claude, codex, deepseek, gemini, generic, openai, opencode, qwen) pointed at `saipen/PROTOCOL.md` -- a file that has never existed under that name since the vacskill->SAIPEN rename; the real file is `saipen/RFC.md`. Every one of these short pointer docs was sending a fresh agent on a platform-specific onboarding path straight into a dead link. Fixed across all 9.
- fix: `claude.md`, `codex.md`, `generic.md`, `opencode.md` also carried mojibake from an earlier PowerShell write (double-encoded arrow `->`, byte sequence unrenderable/corrupt in terminals) -- `sed` and even targeted `Edit` calls failed against the corrupted bytes (exact-string match failed at the byte level), so all four were rewritten clean via full-file replacement using plain ASCII (`->`, `--`) instead of Unicode arrows/em-dashes, permanently sidestepping the PowerShell encoding trap for these files. The other 5 adapters were re-verified byte-by-byte: their only non-ASCII bytes are correctly-encoded UTF-8 em-dashes (`E2 80 94`), not corruption -- left untouched. Full BOM sweep across all 9 files confirmed clean.

## 7.5.0 -- 2026-07-19
- feat (field audit, three live projects): checked how real agents actually use SAIPEN in practice (FastPrompter, Wintage, WildRiftAssistant) instead of only auditing the protocol in isolation. Found the LOG.md line format has zero real-world consensus -- three projects, three different formats, none matching STYLE.md's own example: FastPrompter uses `[E-001] DATE — LABEL:` (ID before date, no leading dash); Wintage uses phase names (`SCOUT:`/`BUILD:`) instead of a taxonomy; WildRiftAssistant has ZERO numeric Event IDs across all 85 LOG lines (uses `[HUNT]`/`[FIX]`/`[GOAL]` instead) and a literal `XX` placeholder for minutes in 57 separate entries. Root cause: the LOG line's structural skeleton lived only in STYLE.md (a voice/personality doc agents can reasonably deprioritize), not in RFC.md (always-loaded, strictly normative) -- and STYLE.md's own example didn't even include the `[E-###]` RFC already requires. RFC.md § 1.2 now states the exact skeleton (`- DATE [E-###] [parent: E-###] [T-###] TAXONOMY: text`) as MUST, with `RUN`/`DEC`/`H` as the closed, explicitly-named taxonomy (never declared as a closed set anywhere before this). STYLE.md's example fixed to match instead of contradict.
- fix: `phases/init.md` pointed at a `templates/` path that has never existed (the real path is `extensions/templates/`) and its own inline LOG example (`[E-001] DEC: Initialize SAIPEN`) violated the format it was teaching -- every fresh project's first log line was non-conformant by instruction. Also `extensions/templates/STATE.md` itself was missing `saipen_version`, `schema_version`, and `goal_mode` despite `init.md` listing them as MUST. All three reconciled; "or write manually" softened to a genuine fallback (degraded capability only), not an equally-valid default.
- Note: the three live projects' own existing `.saipen/LOG.md` history was NOT touched -- that's the user's active work under other agents' hands, not this repo's to rewrite. The fix is forward-looking: once each project's agent re-reads the refreshed protocol, new entries should conform.

## 7.4.6 -- 2026-07-19
- fix (the conformance suite was silently lying): explored `CONFORMANCE.md`, `extensions/`, and `tests/` for the first time this session and found `tests/validate.sh`/`validate.ps1` badly out of sync with the live protocol. (1) The `phase:` whitelist was missing `HUNT`, `ADD`, `CLEAN`, `TRANSLATE` entirely -- a validate run during any Maintenance phase would false-fail. (2) The LOG.md regex required `[E-###]` immediately after the dash with zero tolerance for the date prefix STYLE.md has mandated all along -- empirically, 0 of 34 correctly-dated lines in this repo's own `.saipen/LOG.md` matched it. (3) `validate.sh`'s check used `grep -q` (succeeds on ANY matching line) instead of verifying no line violates -- it was passing only because 124 leftover lines from an old un-dated import happened to satisfy the stale pattern, masking that literally none of today's real entries would. Fixed both scripts: phase whitelist completed, date prefix made optional-but-recognized, bash's any-match logic replaced with a real all-lines check (and its own `set -e` trap on a legitimately-empty `grep -v` result fixed along the way). Verified empirically -- both scripts now genuinely pass against this repo's real `.saipen/`, not by accident.
- fix: traced the false-pass to its root -- `phases/clean.md` never specified an exact LOG line format (same class of gap already fixed in `hunt.md`/`translate.md`), so a past agent invented a non-conformant `[E-CLEAN]` marker instead of a normal numbered Event ID. `clean.md` now specifies the exact format. The one historical `[E-CLEAN]` line was reformatted to a real `[E-115]` entry -- content and timestamp preserved, only the broken format corrected (not a content rewrite).
- fix: three `tests/scenarios/*/STATE.md` fixtures opened frontmatter with `--` instead of `---`. Harmless to the validators (they don't check delimiters) but objectively wrong YAML syntax; corrected for consistency.

## 7.4.5 -- 2026-07-19
- fix (the significant one): `phases/verify.md`'s cap said only "-> BLOCKED + facts" with no instruction to try other tickets first, and `phases/blocked.md` went straight to "ask the user, wait" with no check for remaining work -- combined with §2.4 treating any BLOCKED as a goal_mode-exit condition, one stuck ticket could halt an entire autonomous run even with five perfectly workable tickets still on the board. `verify.md` now marks only the stuck ticket blocked and moves to the next unblocked one; `blocked.md` (session-level, last resort) now re-checks the board before ever asking the user. `review.md`'s own "NO -- BLOCKER" cap was checked and is unaffected -- it already tickets the stubborn finding and continues, no fix needed there.
- fix: `phases/init.md` still wrote `asp_version: 7` into fresh `STATE.md` -- the one surviving leftover of the pre-rename protocol name, everywhere else (including this repo's own `.saipen/STATE.md`) uses `saipen_version`. Every newly bootstrapped project was getting an inconsistent schema from day one.
- fix: RFC.md §1.8's "strictly one by one" was ambiguous between BUILD scope (intended: don't mix tickets in one edit) and cadence (misreadable as: pause after each ticket) -- the latter reading directly contradicts `goal_mode`'s continuous-flow guarantee. Clarified explicitly.

## 7.4.4 -- 2026-07-19
- fix: Audited another agent's unreviewed commits to this repo (§1.8 Batch Input Parsing, Zero-Prompt Auto-Transition, TRANSLATE phase, ADD baseline constraints -- f709eed/57cb87f/a463be2, all confirmed sound). Found and fixed three real gaps in the new `phases/translate.md`: (1) "the kitchen" was ambiguous against §1.2's single `kitchen/` definition and contradicted the phase's own isolation rule -- `.saitranslate/kitchen/` is now explicit and cross-referenced from RFC.md §1.2; (2) "drawn flag icon" assumed image-generation tooling most text agents don't have -- Unicode flag emoji is now the stated universal baseline; (3) completion LOG line was free-text, tightened to the same exact-format convention as `hunt.md`. Also restructured `add.md`: Baseline Architectural Constraints (session persistence, no hardcoding) were nested inside the Industrial Completion Rule's bullet list despite being a distinct, always-applicable concern -- now its own numbered item.

## 7.4.3 -- 2026-07-19
- docs: README trimmed 79 -> 65 lines -- cut redundant/flavor prose (two intro paragraphs saying the same thing twice, decorative asides in the Evolution section), kept every fact intact (GOAL Mode safety valve, auto-push scope, VERIFY/REVIEW guarantee, install commands). Also fixed a stale version badge (was still showing v7.2.0).

## 7.4.2 -- 2026-07-19
- docs: Renamed "Optional acceleration" to "Optional Parallel Execution" in RFC.md §1.3 -- independence of the 6 HUNT categories is the trigger, speed is only the consequence. SPEC.md's Architecture section now states the verified layer independence explicitly: Core (correctness/continuation) works with zero Maintenance; Maintenance (unattended evolution) works identically with or without Goal Mode; Goal Mode and Subagents are both confirmed opt-in with no downstream dependency pointing back at them.

## 7.4.1 -- 2026-07-19
- fix: `phases/ship.md`'s terminal line ("After SHIP: STATE -> DONE") had zero mention of `goal_mode`, the same class of gap fixed in `done.md`/`review.md` a version ago -- a model landing here in one continuous turn could write `phase: DONE` without ever loading `done.md`'s goal_mode check in the same pass. Now checks explicitly. Full sweep of every other `DONE` transition in `phases/*.md` confirmed clean: `add.md`'s is the one legitimate exit condition (product mature) RFC §2.4 already defers to, and `clean.md` is purely human-triggered, already covered by `done.md`'s landing check.

## 7.4.0 -- 2026-07-19
- feat: `HUNT` fans its 6 independent signal categories out to parallel subagents when the platform supports spawning them (RFC.md §1.3, new optional `subagents` capability -- never required, never gates a phase). Subagents are read-only investigators; only the orchestrating agent writes BOARD/LOG, once, after merging results, avoiding write races by construction. No subagent support falls back silently to the existing sequential sweep -- identical cap, identical output, just slower.

## 7.3.3 -- 2026-07-19
- fix (root cause, found via a second WildRiftAssistant trace on the SAME bug after 7.3.2): `phases/done.md` item 3's HUNT-trigger condition was "the user simply typed `/saipen`" -- literally false when an agent arrives at DONE autonomously mid-`goal_mode` run, since the user typed nothing. A model reading `done.md` correctly would NOT transition to HUNT under that wording, no matter how clearly RFC.md §2.4 said to elsewhere. `done.md` now checks `goal_mode` FIRST, before any other branch, and forbids writing `next_action: wait for user command` while it's true.
- fix: `phases/review.md` had no "STATE -> DONE" branch at all, yet the observed trace jumped straight to DONE past the mandatory SHIP step. Added an explicit line: SHIP is mandatory before DONE, no exceptions, even under `goal_mode`.

## 7.3.2 -- 2026-07-19
- fix: Lowercased every command everywhere -- `saipen set`, `saipen goal`, `saipen init` (was inconsistently ALL-CAPS in RFC/README/guides/skill/injector). No functional change from casing.
- fix (real bug, found via a live WildRiftAssistant trace): Goal Mode's Exit clause let a momentarily empty `BOARD.md` count as "reached DONE," short-circuiting the mandatory HUNT->ADD Autonomous Transition (RFC.md §2.1) and stranding the agent at `next_action: wait for user command` instead of looping. RFC.md §2.4 now states explicitly: board-empty is a waypoint, not an exit; `goal_mode` persists through HUNT->ADD->HUNT->ADD until ADD itself gracefully concludes (product mature), BLOCKED, or the safety valve (3 waves/20 tickets) triggers. `phases/hunt.md` reinforced: the clean-hunt-to-ADD transition is unconditional and the LOG line format is exact, not free text.

## 7.3.1 -- 2026-07-18
- fix: Merged `saipen GOAL <text>` with the pre-existing (undocumented-in-RFC) "pivot" semantics already promised in the guides -- entering GOAL mode now demotes (never deletes) the current board and inserts the new objective's tickets on top, before running them to completion. Normalized casing to `saipen GOAL` everywhere (was inconsistently `goal` in RFC/phases/README, matching the pre-existing `saipen SET` convention). Updated README, GUIDE.md, GUIDE_EN.md, GUIDE_RU.md to describe the full merged behavior.

## 7.3.0 -- 2026-07-18
- feat: Introduced `saipen goal <text>` (RFC.md §2.4) -- an explicit, session-scoped autonomous mode that runs SCOUT->BUILD->VERIFY->REVIEW across successive tickets and waves without pausing to ask "shall I continue?". SHIP auto-pushes to an existing `origin` under `goal_mode`; first publish of a brand-new repository still requires explicit confirmation. VERIFY and REVIEW gates, and all existing caps (3 dead hypotheses / 2 fix cycles / 2 review passes), are never skipped. New safety valve: max 3 waves / 20 tickets per invocation before a mandatory checkpoint-and-report.

## 7.2.1 -- 2026-07-18
- docs: Refined the Industrial Completion Rule (`RFC.md` §2.3, `phases/add.md`). Replaced "functional cluster" with "user workflow" throughout for a clearer mental model. Added the "Complete before you extend" maxim: finish the requested workflow before proposing a different one, because agents should preserve user expectations before introducing new capabilities.

## 7.2.0 -- 2026-07-18
- feat: Introduced the `ADD` phase. The agent now acts as a product manager and lead engineer to systematically brainstorm and implement new features based on core UX rules (persistence, industry standards, maximum user control, safe step-by-step evolution).
- feat: Automated Continuous Evolution. When `BOARD.md` is empty, `/saipen` defaults to the `HUNT` phase to fix bugs. If `HUNT` finds a clean codebase, it automatically transitions to the `ADD` phase to safely evolve the software.
- doc: Added ELI5 "Grandpa Style" guides (`GUIDE_RU.md`, `GUIDE_EN.md`) and linked them with prominent shields.io badges in the `README.md`.
- fix: Replaced `inject.ps1` and `inject.sh` symlink (junction) creation with direct file copies to ensure maximum reliability across all agent platforms.
- fix: Restored Cyrillic UTF-8 encoding in `STYLE.md` to ensure correct persona injection for future agents.

## 7.1.2 -- 2026-07-17
- refactor: Renamed GitHub repository from `vacskill` to `saipen`. Updated all absolute URLs and git clone instructions.

## 7.1.1 -- 2026-07-17
- doc: Formally defined the boundary of SAIPEN regarding distributed consensus. SAIPEN explicitly states it is a local state protocol relying on atomic filesystem commits; true multi-machine network distribution requires an external "Coordinator" built on top of SAIPEN.

## 7.1.0 -- 2026-07-17
- refactor: Total Bootstrap Decoupling. Stripped all remaining platform-specific instructions (`CLAUDE.md`, `GEMINI.md`, `VACSKILL:BEGIN`) from the `init.md` core phase. The core is now perfectly sterile and only initializes the `.saipen/` directory.
- chore: Replaced all legacy `VACSKILL:BEGIN` hooks with `SAIPEN:BEGIN` inside the bootstrap scripts.

## 7.0.0 -- 2026-07-17
- BREAKING / REWRITE: `PROTOCOL.md` has been brutally minimized (< 60 lines). 
- doc: Removed Abstract, Scope, Adapter Contract, and CLI commands from the core protocol machine document. These have been migrated to `SPEC.md` and `GUIDE.md` to prevent any context distraction.
- feat: `DONE` phase formally forbidden without successful `VERIFY` (or `MANUAL-VERIFY`), `needs` formalized as strict DAG, and `HUNT` signal dependency rigidly enforced.

## 6.3.0 -- 2026-07-17
- BREAKING / REWRITE: `PROTOCOL.md` has been brutally minimized (< 60 lines). 
- doc: Removed Abstract, Scope, Adapter Contract, and CLI commands from the core protocol machine document. These have been migrated to `SPEC.md` and `GUIDE.md` to prevent any context distraction.
- feat: `DONE` phase formally forbidden without successful `VERIFY` (or `MANUAL-VERIFY`), `needs` formalized as strict DAG, and `HUNT` signal dependency rigidly enforced.

## 6.2.0 -- 2026-07-17
- refactor: Ruthlessly purged all conversational/literary explanations from `PROTOCOL.md` to ensure the machine document remains absolutely cold and unambiguous.
- feat: Formalized Conformance into three strict vectors: Repo Validation, Session Validation, and Phase Contract Validation. `saipen validate` is now structurally mandated to enforce these vectors.

## 6.1.0 -- 2026-07-17
- doc: Reframed SAIPEN completely around the **"Continuation Test"**. Memory is a means to an end; instant action is the goal. Tagline changed to "One command. Zero amnesia."
- feat: Added `TEST-001: The Continuation Test` to the Conformance section as the gold standard for release validation.
- feat: `next_action` in `STATE.md` MUST now be an explicitly executable command (e.g. `pytest tests/`), not a vague intent, to ensure zero-context resumption.

## 6.0.0 -- 2026-07-17
- BREAKING / REBRAND: Renamed "Cross-Agent Project Memory Protocol" to **SAIPEN**.
- BREAKING: `LOG.md` events are no longer linear lists. They are now graph nodes identified by `[E-XXX]` and `[parent: E-XXX]`, enabling safe multi-agent branching and merges.
- feat: Implemented Two-Way Capability Negotiation. The protocol now dictates `requires:` in `STATE.md`, and the agent locks its `mode:` based on local capabilities.
- feat: Formalized Architecture Decision Records (ADR). Long-term truths live in `KNOWLEDGE/ADR-XXX.md` to prevent log bloat.
- feat: Expanded `extensions/` architecture with `security/` and `performance/` hook documentation.
- doc: Radically split documentation. `README.md` is now just a 5-minute pitch. `SPEC.md` is the human-readable RFC. `PROTOCOL.md` is strictly machine instructions. `GUIDE.md` is the human tutorial.

## 5.3.0 -- 2026-07-17
- feat: Added dedicated `validate` phase and `saipen validate` command.
- feat: Added `tests/validate.ps1` and `tests/validate.sh` conformance checker scripts.
- test: Added `tests/scenarios/` with 7 mock `.saipen` states for protocol compliance testing (crash-recovery, staleness, claim conflicts).
- struct: Explicitly separated Core (`saipen/`) from Adaptive Extensions (`extensions/` schemas, adapters, templates) to prevent protocol pollution.

## 5.2.0 -- 2026-07-17
- BREAKING / REWRITE: Converted the core `PROTOCOL.md` from a conversational guide into a strict, RFC-style normative specification.
- feat: Formalized the State Machine (`INIT РІвЂ ’ PLAN РІвЂ ’ SCOUT РІвЂ ’ BUILD РІвЂ ’ VERIFY РІвЂ ’ REVIEW РІвЂ ’ SHIP РІвЂ ’ DONE | BLOCKED`).
- feat: Formalized Claim/Ownership logic (`owner` and `claim_time` added to `board.schema.json`) to prevent multi-agent race conditions.
- feat: Added Capability Negotiation handshake (agents MUST check capabilities like git/shell before engaging).
- feat: Added formal Recovery doctrine.
- doc: Stripped all "marketing copy" and persona out of `PROTOCOL.md` into non-normative abstracts, reinforcing that voice (`STYLE.md`) never overrides logic.

## 5.1.0 -- 2026-07-17
- feat: unified "Р Т‘Р ВµР Т‘ РЎРѓ РЎР‚Р В°Р в„–Р С•Р Р…Р В°" persona. Removed haiku requirement completely. The direct, witty, tough-love "grandpa" style is now the default for both chat responses and LOG entries (while maintaining strict caveman token compression and preserving facts verbatim).

## 5.0.1 -- 2026-07-17
- fix: extract missing `verify.md`, `review.md`, `done.md`, and `blocked.md` phases that were unintentionally merged or omitted in 5.0.0, which broke lazy loading when STATE entered these phases

## 5.0.0 -- 2026-07-17
- BREAKING: 2-tier protocol architecture. PROTOCOL.md is now a dense boot loader (~110 lines, ~1,200 tokens cold start). Phase-specific rules moved to lazy-loaded saipen/phases/ modules (init, plan, scout, build, ship, hunt). Agent loads only the phase it needs -- 60% fewer tokens per session vs monolithic v4. All rules preserved, zero lost. README rewritten for SAIPEN positioning
## 4.1.0 -- 2026-07-17
- Public launch edition: fix encoding corruption throughout (control chars -> clean ASCII, no BOM anywhere); README rewritten for public consumption with clean ASCII art; PROTOCOL.md audited and rebuilt clean

## 4.0.0 -- 2026-07-17
- BREAKING: skill -> protocol. saipen/PROTOCOL.md is the single vendor-neutral canon (240 lines, capability degradation table included); SKILL.md shrunk to a thin skill-reader adapter. New: adapters/ (9 platforms), templates/ (init boilerplate), style/ (opt-in voices), schemas/ frozen for a future orchestrator. Injectors point everything at PROTOCOL.md, upgrade stale 3.x blocks, and write UTF-8 without BOM. Positioning: vendor-neutral project execution protocol for LLM agents

## 3.1.2 -- 2026-07-16
- hotfix: ensure FreeBuff and Antigravity plugins receive copy, not junction, as their scanners ignore symlinks

## 3.1.1 -- 2026-07-15
- core reliability audit: HUNT skip was a phantom rule since 2.0.0 (no clean-line format, no anchor) -- now `hunt -> clean @<hash>` vs HEAD; legacy rename no longer assumes git; STYLE.md-missing fallback; REVIEW pass counter lives in LOG not memory; graph-mode claim race resolved by re-read; history prune made explicit. Net zero lines -- fixes paid for by compression

## 3.1.0a -- 2026-07-15
- drop _archive_versions/ -- identical twins of v1.2.2, already served by tags (`git show v1.2.2:VAC/SKILL.md`)

## 3.1.0 -- 2026-07-15
- anti-drift: STYLE.md Persistence section (voice holds every response, no revert after many turns) + protocol loads it upfront; git tags as release archive (all 17 past versions tagged retroactively); memory backup rule for non-git projects; self-imposed ~250-line cap -- SKILL.md compressed 281 -> 249 with zero rules lost

## 3.0.0 -- 2026-07-15
- BREAKING: renamed VAC -> saipen everywhere -- skill name, folder, memory dir (.vac/ -> .saipen/), pointer blocks (VACSKILL:BEGIN), repo (github.com/vacterro/saipen). Short alias `vac` still works for every command. Injector migrates pre-3.0 installs automatically; in projects run `git mv .vac .saipen`

## 2.1.0a -- 2026-07-15
- README rewritten for v2.x: angrier grandpa, phases/confidence/graph/KNOWLEDGE covered

## 2.1.0 -- 2026-07-15
- verify confidence (high/med/low) on DONE tickets; graph mode: parallel agents claim [P] tickets over needs: DAG; KNOWLEDGE index.md rule; vac status quick metrics

## 2.0.0 -- 2026-07-15
- protocol/personality split: SKILL.md cold protocol + new STYLE.md (voices); SCOUT and REVIEW promoted to phases (PLAN->SCOUT->BUILD->VERIFY->REVIEW->SHIP); KNOWLEDGE/ base (architecture/conventions/decisions/traps) -- LOG is journal only; BOARD needs: dependencies + no-free-will pick rule; minimal STATE

## 1.2.2 -- 2026-07-15
- injectors detect generic ~/.agents/skills (FreeBuff etc.); fixed broken-encoding stale copy there

## 1.2.1 -- 2026-07-15
- README rewritten: caveman English voice, ELI5 usage guide, half the size, twice the punch

## 1.2.0 -- 2026-07-15
- one-shot injectors inject.ps1 + inject.sh: auto-detect and wire all agentic systems (Claude Code, OpenCode, Codex, Gemini, Antigravity plugins, Aider), idempotent re-runs

## 1.1.5 -- 2026-07-15
- chat voice: compressed, direct, no filler; LOG persona unchanged

## 1.1.4a -- 2026-07-15
- voice boundaries hardened: LOG voice confined to .vac/ files only; chat strictly direct

## 1.1.4 -- 2026-07-15
- human dates DD.MM.YY HH:mm in LOG, wise-angry-grandpa commentary voice (facts stay exact), closing haiku on stop/ship; chat voice unchanged

## 1.1.3 -- 2026-07-15
- self-cleaning: scratch confined to .vac/tmp/ (deleted at stop/ship), orphan-file hunting with proven-unreferenced guard, no-litter iron rule

## 1.1.2 -- 2026-07-15
- publish target now user-agnostic: repo's own origin / logged-in gh account -- no hardcoded owner

## 1.1.1 -- 2026-07-15
- concurrent-agent takeover guard; new-machine bootstrap fallback in pointer block; .gitignore/.env guard before publish commits

## 1.1.0a -- 2026-07-15
- add "vac set" as official resume alias

## 1.1.0 -- 2026-07-15
- loop caps (3 hypotheses / 2 fix cycles -> BLOCKED, never spin); PUBLISH opt-in only (no auto-push of user projects); HUNT skips unchanged-clean repos; runtime token discipline section; unified checkpoint doctrine

## 1.0.1 -- 2026-07-15
- portable install: clone-anywhere paths, macOS/Linux symlinks; MIT LICENSE; SKILL.md init block uses <VAC_HOME> instead of hardcoded path

## 1.0.0 -- 2026-07-15
- first release: single VAC skill (PLAN/BUILD/CHECK/SHIP/HUNT loop), .vac/ cross-agent memory, ship-to-GitHub flow

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

## 7.211.0 -- 2026-08-07 -- the clean-HUNT destination and the valve resume key follow the execution intent

T-539: the HUNT-to-ADD routing was one unconditional line ("immediately transition to `ADD`") that also bound `execution_intent: converge` -- while CONVERGE.md stage C forbids `ADD` entirely under converge as the invention that can never terminate. A converge run that exhausted the board was ordered into the very phase the contract forbids. The destination is now intent-aware: under converge a clean HUNT is stage F or stage I of CONVERGE.md (F routes to `CLEAN`, I into the closure sequence -- sync, fresh factories, finalize), under normal/goal it keeps the `ADD` destination of MAINTENANCE § 2.1. The clause lives once in § 2.1; `hunt.md`, `done.md` and `add.md` name it without restating it.

The safety-valve pause's resume key is intent-aware too. Under goal intent the fixed § 1.2 form stands (`run 'saipen goal' to continue`); under converge the pause MUST read `run 'cc' to continue`, never `run 'saipen goal'` -- there `saipen goal` is a NEW objective, a substitution, while bare `cc` is the only legal resume. The pending "resume key moves to cc when the intent model lands" note was landed, since T-536 made the intent model real.

`validate.py` gains two checks: a converge state carrying a clean-HUNT LOG marker whose `next_action` names `ADD` FAILs (the normal intent naming `ADD` passes untouched -- scenario 8), and a converge safety-valve `WAIT:` whose body names `run 'saipen goal'` FAILs. Two new red controls in `audit_checks.py` (168 -> 170) and `run_converge_routing_probes` in `run_scenarios.py` (5 behaviors) cover red and green on both intents plus the wording half. CONFORMANCE rows 243/244.

## 7.210.0 -- 2026-08-07 -- the convergence order gets one owner

T-538: `saipen/CONVERGE.md` is now the only place the `cc` lifecycle is defined -- stages A through M from recovery to fresh producer packages, the rule that no main-source mutation may follow the producer preparation, and the closure bar that decides when a converge run may clear the intent and stop. The order was previously implied by five documents that each knew one hop, so no single reader could answer "what comes after CLEAN" without assembling it, and assembling it is where two conformant agents diverge. `hunt.md`, `clean.md`, `prepare.md` and `done.md` each name their own stage and defer; none restates the sequence.

`validate.py` gains `[converge-contract]`, which checks the 13 stages BY POSITION: a reordering FAILs while every stage is still present, because the way this contract actually breaks is two stages swapping and putting the factories before the cleanup that invalidates them -- not a deleted file. Two red controls cover exactly that (one renames a stage heading to another's, one deletes the ordering rule); audit_checks 168 of 168. The doc is registered in INDEX.md, `saipen/MANIFEST.json` and BOTH bootstrap injectors, whose copy lists are still hand-written beside the manifest.

## 7.209.0 -- 2026-08-07 -- a callout can no longer name the wrong destination

T-537: the shortcut-callout check counted keys, tokens, order and the link and never read what the sentence claimed, so a document could tell the reader `cc` is the Goal Mode key while §1.10 routed that key to `saipen continue`. Three Core-owned files shipped in v7.208.0 doing exactly that -- the RU locale source, the EN guide and the JA guide, each one's sibling already moved. Fixed, and the blind spot closed: a Core-owned callout still describing `cc` as the Goal Mode key now FAILs `[shortcut-callouts]`, derived from the route the way the `[shortcut-notes]` check is. Scoped to the 15 files Core owns -- `phases/translate.md` gives the other 28 languages to saitranslate, so their remaining semantic drift clears through an `ee` run rather than reddening every Core commit. One new red control; audit_checks 166 of 166.

## 7.208.0 -- 2026-08-07 -- `cc` and `gg` get separate destinations

T-550: the Core half of the `gg`/`cc` split lands. `cc` routes to `saipen continue` (continue context / converge: it resumes an active `execution_intent: goal`, resumes convergence, or enters convergence from `normal`, and never asks for an objective -- `cc <args>` replies `Use: gg <objective>` and stops); `gg` is the sole short route for a NEW goal and its bare form is a usage line, never a continuation alias; `ccc` becomes converge, SHIP, then refresh EE and QQ against the shipped revision. `EXPECTED_SHORTCUT_ROUTES`, CONFORMANCE rows 207/218/224 and MAINTENANCE's safety-valve wording follow the new mapping, along with the `cc` callout in five languages.

Two red controls had gone silently dead in the process: the `cc`-row and `gg`-row cases in `tools/audit_checks.py` quoted §1.10 row text this split rewrote, so both mutations were no-ops and the harness scored them SKIP -- the third occurrence of the split-anchor class T-496 and T-532 name. Repointed: the `cc` case now maps the route cell back to `saipen goal` and must FAIL `[shortcut-routes]`, which is the separation's own regression control, and the `gg` case strips the "pivot needs text" clause the `[shortcut-notes]` check reads. audit_checks is back to 165 of 165 with zero not-evidence lines. The 28 non-Core locale callouts still describe the old `cc` semantics and remain T-537's remainder -- `phases/translate.md` gives those languages to saitranslate.

## 7.207.0 -- 2026-08-07 -- execution_intent replaces goal_mode

T-536: the persisted execution-intent moved from the boolean `goal_mode` to ONE canonical enum `execution_intent: normal | goal | converge` in STATE. `goal_mode` remains READ-compatible only during migration (maps `true` -> goal, `false` -> normal) and a state carrying both fields FAILs validation -- one source of truth after the first canonical checkpoint. The safety-valve counters `goal_waves`/`goal_tickets` re-bind to `execution_intent: goal`; Recovery rebuilds the intent from the `DEC: goal pivot` line; the live state, template, scenario fixtures, portable floors, and the audit harnesses all migrated. The `cc`-semantics and safety-valve-wording changes follow in the next tickets.

## 7.206.9 -- 2026-08-07 -- uninstaller survives non-Windows

T-535: uninstall.ps1's Remove-Task (from T-531) called `Get-ScheduledTask`, a Windows-only cmdlet -- on pwsh/Linux it throws and kills the uninstaller, which the first fully-reaching CI run exposed at the run_scenarios step. Remove-Task/rm_task now return "clean" when the cmdlet is unavailable or SAIPEN_UNINSTALL_SKIP_TASK is set, and both injector probes set that var because the scheduled task is machine-global -- a sandboxed test must never delete a real scheduler entry.

## 7.206.8 -- 2026-08-07 -- parity restore survives MULTI cases

T-534 (third pass): the v7.206.7 CI run got audit_checks green and then failed the next previously-masked step -- `tools/audit_parity.py` reported "the copy did not survive the run". audit_parity imports audit_checks' CASES but ran its own restore loop that saved/restored only the case target, so the new two-file MULTI cases left the second file mutated and the pristine drifted. The parity loop now uses the same `mutation_files` save/restore as the audit_checks main loop.

## 7.206.7 -- 2026-08-07 -- audit_checks pick control claim-independent

T-534 (second pass): the v7.206.6 CI run exposed a third board-state dependence in `tools/audit_checks.py` -- the next_action-topmost red control fires locally on a claim-free board, but the pick check only runs when nothing is claimed, and a ship commit's own ticket sits in `## DOING`. `demote_the_pick` now empties `## DOING` (drops the claimed ticket line) before arranging the `## TODO` mismatch, so it goes red from a board WITH a claimed ticket and a zero-workable `## TODO` -- the exact CI composition. Verified 165/165 under both compositions.

## 7.206.6 -- 2026-08-07 -- audit_checks controls board-state independent

T-534: two of the 165 audit_checks controls stayed dependent on the live board/STATE composition after T-532, so CI came back red on the v7.206.4/v7.206.5 ships even though local runs reported 165/165: the session-BLOCKED control cannot fire when the ship commit's board holds no workable `## TODO`, and next_action-topmost cannot fire when STATE sits at DONE with a non-ticket next_action. Both are now fully self-contained through a new MULTI mutation form (a case may edit two files, with save/restore): session-BLOCKED injects a synthetic workable ticket alongside `phase: BLOCKED`; next_action-topmost injects synthetic tickets at the top and bottom of `## TODO` and names the bottom one in STATE.next_action.

## 7.206.5 -- 2026-08-07 -- safe LOG-append prescribed

T-533: the LOG-append guidance named no safe command, so a Windows agent reached for PowerShell `Add-Content` and corrupted `.saipen/LOG.md` through the console codepage (Cyrillic came back as invalid UTF-8, "recovered" by a byte-patch that quietly transliterated it). CORE.md § 1.5 now states the LOG append is a UTF-8 write and names three byte-safe forms (PowerShell `AppendAllText` with BOM-less UTF8Encoding, bash `printf >>`, Python `open(..., 'a', encoding='utf-8')`); KNOWLEDGE/traps.md's Set-Content/Add-Content trap entry carries the same one-liners. The active LOG also crossed the 64 KB soft cap and was sealed to LOG-009.md (the `log-soft-cap` ownership check FAILs when the slug returns with no owner -- sealing is the fix, as E-2046 recorded).

## 7.206.4 -- 2026-08-07 -- audit_checks 165/165 evidence again

T-532: 14 of 165 red controls in `tools/audit_checks.py` had stopped being evidence. Split-anchor drift (T-496 class) after the BOOT.md shrink and CHANGELOG archiving; control mutations that removed one occurrence of a string the validator counts anywhere (so survivors satisfied the checks); a harness that copies the repo's live STATE.md, which no longer carries goal-mode counters; and a board with a single workable ticket that `demote_the_pick` could not demote into being not-topmost. Every case repaired to fire on its own condition -- including injecting a synthetic workable ticket, making the goal-mode mutations self-contained, and tightening one genuinely weak validator check (the PROTOCOL.md charter-loading test was satisfied by any occurrence of the words "load"/"charter"). This ship should produce the first fully green validate run since 2026-08-03.

## 7.206.3 -- 2026-08-07 -- CI push-loop: portable-floor red harness + tag ledger

Two more pre-existing conformance-step failures surfaced once the validator and lint steps passed. `tools/audit_floor.py` read `saipen/RFC.md` alone -- a 144-byte redirect stub since the v7.190.0 split -- so every red-control anchor was unresolvable (the T-496 split-layout class in the portable-floor harness); it now reads CORE.md + MAINTENANCE.md with an RFC.md fallback. `tools/audit_tags.py` flagged v7.199.0/v7.200.0, both pointing at a commit carrying VERSION 7.201.0 because their true release commits were orphaned by a history rewrite and no longer exist on origin/main; both are now acknowledged in KNOWN_MISMATCHES per user decision rather than re-pointed.

## 7.206.2 -- 2026-08-07 -- ruff-clean validator

Two legacy `tools/validate.py` errors kept the conformance job's Lint step red after the T-528 fix: E402 (the `pathlib` import sat below the Windows stdout wrapper instead of the top import block) and FURB192 (`sorted(...)[0]` -> `min(...)`). Both pre-dated the CI-red diagnosis; fixing them is what "the next push produces a green run" actually requires.

## 7.206.1 -- 2026-08-07 -- hunt mark must reach the remote

T-528: CI had been red for two runs because a clean-hunt mark named a commit that existed on one machine and on no remote branch -- `@db9d775` in LOG.md:116, an orphan local commit, so the validator passed locally and FAILed on a fresh clone against the identical tree. The check now has a second rung: after the commit exists, it must sit on a remote-tracking branch (`git branch -r --contains`, output-based), active misses FAIL and sealed misses WARN; a project with no remote keeps the old behavior. The mark was repaired by declared amendment to its remote-backed parent `@594a1da` (DEC E-2233). run_scenarios hunt-mark probes 2 -> 4, adding a local bare remote with an unpushed commit that must FAIL.

## 7.206.0 -- 2026-08-07 -- RFC stub trap out of the injectors + auto-scheduled inject

T-529: the RFC stub trap was live in the injected block on every installed agent home -- both shell injectors wrote "read RFC.md + STYLE.md and follow them" into CLAUDE.md/AGENTS.md/GEMINI.md, and RFC.md is 144 bytes of redirect since the v7.190.0 split. Both injectors now name BOOT.md as the cold-start kernel and route BOOT -> INDEX -> CORE, sanity-check saipen/BOOT.md (not the stub), and give Aider the BOOT.md + STYLE.md boot set; the four root README entry lines match. The validator's RFC-stub-trap check was blind two ways -- its file set globbed only `adapters/*.md` + saipen/SKILL.md (the shell injectors reach every agent's global config) and its regex wanted `follow.*RFC\.md` while the live sentence has `follow` trailing RFC.md. Both layers closed: inject.sh + inject.ps1 are in the set, and `RFC\.md\s*\+` / `read[^.\n]*RFC\.md` catch the boot-SET shape; red-tested.

T-531: `bootstrap/schedule.ps1` + `schedule-run.ps1` register a `saipen-inject` Windows Task Scheduler task (schtasks /SC MINUTE /MO 15 -- the indefinite form, since New-ScheduledTaskTrigger -RepetitionDuration cannot express "forever") that git-pulls the clone and re-injects every agent config every 15 minutes, logging to %LOCALAPPDATA%\saipen\inject.log. The runner pulls best-effort with GIT_TERMINAL_PROMPT=0 so a dirty tree or offline box never blocks the inject; uninstallers (ps1 + sh) remove the task when present.

## 7.205.2 -- 2026-08-07 -- pre-commit hook generation 7

T-517: the validation path is read-only, proven rather than asserted — `git status --porcelain=v1 -uall` byte-identical across `validate.py`, and `ci_status.py` writes only inside `.git/` or the system tempdir.

T-527: the hook told every successful commit it had not been validated. Generation 6 removed `validate.py && exit 0` so the purity guard could no longer be skipped, and put no success exit in its place, so control fell past the failure check into the fall-through `saipen: NOT VALIDATED` diagnostic. Generation 7 restores a success exit gated on the validator rc being set, placed *after* the purity guard so generation 6's reason for deleting it does not return. Two red controls added (installed-hook probes 4 → 6): the healthy path must stay silent, and a genuinely unreachable validator must still say so out loud and still exit 0.

## 7.205.1 -- 2026-08-07 -- validation blind spots closed

T-526: pre-commit purity probe (read-only gate proven, mutating validator trips gen-6 guard) + validator checks for STATE final-newline, nested saipen/VERSION duplicate, INDEX phase parity, and adapter RFC-stub-trap. Gen-6 hook fix: the gen-5 `&& exit 0` short-circuited before the purity guard, making it dead; now captures validator rc, runs purity comparison, then exits. All 11 validation blind spots now covered by a named check or probe.

## 7.205.0 -- 2026-08-07 -- cold-start + execution chain hardening

Goal wave "Harden cold-start and execution chain" (9 tickets, 8 shipped):
- **T-518** (P0): validation + pre-commit are now provably read-only. install_hook.py generation 5 captures `git status --porcelain=v1 -uall` before/after the gate; any project-file write from the validation path FAILs the commit.
- **T-519** (P0): one deterministic `protocol_dir` resolver for both source-clone and flattened-install layouts (BOOT + CORE).
- **T-520** (P1): one canonical runtime manifest (`saipen/MANIFEST.json`) replaces the divergent inject.sh/ps1/autoinject.py/validate.py file lists.
- **T-521** (P1): RFC stub trap removed — adapters/SKILL.md route to BOOT→INDEX→exact CORE, never to RFC.md as constitution.
- **T-522** (P2): INDEX.md exact — 16 phases synced with files on disk.
- **T-523** (P2): one version source — saipen/VERSION deleted, root VERSION only.
- **T-524** (P1): transition authority removed from conflict — CORE matrix is the single canonical source.
- **T-525** (P1): cold path shrunk — BOOT.md 13.9KB→5.2KB, v8 backlog moved off the cold-start surface.

## 7.204.1 -- 2026-08-07 -- guide opening drift fix + protocol hygiene

13 locale guides (AR/DA/FI/HE/IT/KO/NL/NO/PL/PT/SV/TH/VI) fixed: opening prose contract restored. Guides previously started with HTML image tags instead of prose, violating STYLE.md's guide contract. saipen/VERSION now git-tracked. BOOT.md duplicate STYLE.md contract removed. audit_checks.py release_ledger_probe hunt-mark sanitized.

## 7.204.0 -- 2026-08-07 -- protocol polish

CHANGELOG archiving: sealed entries 7.197.0 through 7.186.0 into CHANGELOG_ARCHIVE.md. CHANGELOG.md now carries exactly 10 newest releases per its own stated contract. MAINTENANCE.md self-references already bare (§ 2.x) — no change needed.

## 7.203.0 -- 2026-08-07 -- RFC→CORE.md/MAINTENANCE.md reference sweep

T-512: Mechanical sweep of all shipped docs (23 files). Every "RFC § X.Y" reference replaced with "CORE.md § X.Y" (for §1.x) or "MAINTENANCE.md § X.Y" (for §2.x). "RFC.md" → "CORE.md". Zero remaining numeric RFC references. STYLE.md boot marker updated to reflect text change. Cross-doc checks and scenario fixtures pass.

## 7.202.0 -- 2026-08-07 -- expert skill injection routing at boot

T-502: BOOT.md step 3a — skill injection. When `.saipen/extensions/skill_injection/SPEC.md` exists, the agent detects the problem class from the active ticket, matches the smallest domain skill from the platform registry, injects its context, and ejects when the problem class shifts. The contract (T-501) governs; the step defers to it. Absent contract -> zero overhead.

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

# Changelog

> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

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

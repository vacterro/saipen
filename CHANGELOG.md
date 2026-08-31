# Changelog
> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

## 7.234.2 -- 2026-09-01 -- A Freshness Digest That Can Actually Match (T-1253)

- The stamp was finally being written (7.234.1) and still could not match. `autoinject._digest` hashed raw bytes, but the two sides of the comparison arrive through different transports: the clone holds LF and the snapshot git hands the scheduled injector holds CRLF. `saipen/BOOT.md` is 4972 bytes in the clone and 5063 bytes in the snapshot with not one character of difference, so a home refreshed seconds earlier reported STALE -- and a witness that always says stale is the same as no witness.
- `_content_bytes` normalises CRLF and lone CR to LF for anything that decodes as UTF-8, and hashes a non-text file byte-for-byte: it has no line endings to normalise and guessing would corrupt the comparison. The docstring already claimed the digest covered file CONTENT; now it does.
- `tools/test_inject_digest.py` pins both halves rather than observing them once: the two transports agree on an identical surface, a real edit still moves the digest, a mixed-ending file collapses cleanly, and binary content is left alone.
- This closes the fourth and last layer of one hole. The task was never installed; then it was installed and skipped every run on a too-broad cleanliness rule; then it injected and wrote no witness; then it wrote a witness that could never match. Each layer hid the next, and only running the thing end to end on a real machine surfaced them.

## 7.234.1 -- 2026-09-01 -- The Freshness Witness Gets Written (T-1252)

- `tools/autoinject.py` owns the `.saipen_injected` stamp and compares it to decide whether a consumer copy is current. `bootstrap/inject.ps1` -- the injector the 15-minute task actually invokes -- copied the protocol and wrote no stamp at all. So the design's entire staleness signal had no witness: a freshly refreshed home and a home several releases behind both read as `installed unstamped`, forever.
- Proven live, in the worst possible way: the scheduled inject at 02:02 succeeded and genuinely refreshed every consumer home (the `.claude` copy went from the pre-W4 13 KB router to the current 5063-byte one), and `autoinject.py --check` still reported all four targets stale immediately afterwards.
- `--stamp-only` was added to `autoinject.py` -- compute the surface digest, write it into every installed target, copy nothing -- and `schedule-run.ps1` calls it after a successful inject. The digest keeps exactly ONE owner: a PowerShell reimplementation would drift from the Python one and the drift would be invisible, which is the failure this repository keeps closing everywhere else.
- A missing interpreter or a missing `autoinject.py` is logged and left visible rather than pretending a stamp was written. The copies are current; only the witness is absent, and `--check` says so out loud.
- Scheduler probes 60 of 60: the fixture gained a stand-in stamper and asserts the callback fires with `--stamp-only` on a clean inject.

## 7.234.0 -- 2026-09-01 -- The Scheduled Injector Actually Injects (T-1251)

- The 15-minute `saipen-inject` task was healthy, fired on time, and refreshed nothing. `schedule-run.ps1` rejected the source whenever `git status --porcelain -uall` printed a single line, and a live project permanently prints thousands: 1926 translation-cache files, 1562 subSaipen kitchen files, `.prepare-staging`, improve cycles, unshipped release-scope records and the user's own `.workbuddy-ai/memory`. None of them affect a single byte the injector copies. The feature shipped inert and stayed that way: observed live at 01:01 and 01:31, both runs `SKIP: DIRTY_SOURCE`.
- The guard now asks the question it meant to ask: does anything in the INJECTED SURFACE differ from HEAD? The surface is read from `saipen/MANIFEST.json` -- the one owner of that list, so it cannot drift -- and handed to git as a pathspec. An edited `saipen/CORE.md`, a modified `tools/` file or an unreviewed script dropped into `bootstrap/` still blocks, which is the property the guard exists for. A source whose manifest is missing or unreadable refuses rather than guessing what it ships.
- `inject.log` now records the deciding surface and, on a clean run, how many paths were checked.
- Scheduler probes 59 of 59, with both halves pinned: an untracked file outside the surface no longer blocks, an untracked file inside it still skips, and a manifest-less source refuses.
- Operational note for anyone whose consumer copies drifted: this is what made the drift possible. The task existed, the machinery existed, and the one rule between them was too broad to ever let it run.

## 7.233.4 -- 2026-09-01 -- Scheduler Status Stops Failing Its Own Install (T-1250)

- `bootstrap/schedule.ps1 status` reported DEGRADED for a task `install` had just created correctly. It required the stored `Arguments` to equal the bare VBS path on the reasoning that "schtasks strips the surrounding quotes"; Windows 10 Pro 19045 keeps them, so the installer produced a state its own health check called broken.
- Quoting is a host detail, not a contract. Status now strips exactly one layer of surrounding double quotes and then demands an exact match against the canonical wrapper path. The anti-laundering property that motivated the strict form is unchanged and finally has its own case: an extra argument smuggled after the wrapper still reports DEGRADED, which is the form that actually changes what runs.
- The scheduler probe flipped with it -- it asserted the quoted form was DEGRADED, encoding the same wrong premise -- and the smuggled-argument case was added beside it. 57 of 57.
- The `saipen-inject` task is live on the maintainer's machine and reports HEALTHY with its 15-minute repetition. It still exits `SKIP: DIRTY_SOURCE` every run: T-1251 owns that rule, which treats any untracked file -- translation caches, subSaipen kitchens, the user's own notes -- as a reason not to refresh a protocol none of them affect.

## 7.233.3 -- 2026-09-01 -- Fault Injection That Actually Injects (T-1248)

- Release-executor probe 7 wrote `.git/hooks/pre-commit` with `write_text` and never set the executable bit. POSIX git runs a hook only when it is executable and skips it silently otherwise, so on Linux the injected commit rejection never happened: the ship genuinely succeeded and the probe reported that real release as a missing refusal (`ok=True code='RELEASED' not in errors.CODES`) plus a push it expected not to see. Windows ignores the bit, which is why it passed there for as long as it existed.
- The hook is now `chmod 0755`. A probe whose fault injection is a no-op tests nothing, so the same class was swept across the suite: every other shebang write already chmods, and the symlink/junction probes measure the capability instead of assuming it from `os.name`. This was the only silent no-op.
- Operational: the `saipen-inject` scheduled task was never installed on the maintainer's machine, so all four consumer copies (`.claude`, `.config/opencode`, `.codex`, `.agents`) were stale and unstamped -- an opencode agent stranded mid-session looking for the `gg` shortcut in CORE.md, where W4 no longer keeps it. The task is installed now (every 15 minutes, hidden wscript wrapper). Follow-ups filed: T-1249 (staleness detection must name a stale consumer copy rather than let it be used silently) and T-1250 (`schedule.ps1 status` reports DEGRADED for a correctly installed task because it expects the bare argument form this Windows build does not store).

## 7.233.2 -- 2026-08-31 -- Release Fixture Stops Inheriting the Authoring Host (T-1246)

- `run_scenarios.build_fixture` copied the live `.saipen/STATE.md` and rewrote phase/task/mode but left `saipen_home` pointing at the absolute path of the machine that wrote it. That path exists on exactly one host, so every other one -- a Linux CI runner above all -- refused the fixture's first command with `REFUSE [HOME_REQUIRED]` and aborted the whole conformance run. The defect was always there; it only became reachable once v7.233.0 fixed the scheduler probe that used to crash the suite earlier.
- The fixture is self-hosting, so it now rebinds `saipen_home` to its own project root. Proven by breaking it on purpose: with the live `saipen_home` pointed at a nonexistent path the release-executor probes still report 96 of 96, and the live STATE was restored byte-identical.
- Known follow-up: T-1247, the warn-slug ownership probe reports a false break whenever BOARD.md sits within ~1 KB of the soft cap, because the ticket it adds is enough to introduce the `board-soft-cap` slug.

## 7.233.1 -- 2026-08-31 -- Red-Control Anchor Derived, Not Named (T-1245)

- CI went red on main at b62e2313: the `audit_checks` red-control "CHANGELOG entries fall out of descending order" anchored on the literal `## 7.230.0`, and v7.233.0 archived that entry out of `CHANGELOG.md` in the same release. The mutation became a silent no-op and the control stopped being evidence without anyone touching it -- the second time a hardcoded CHANGELOG anchor has died exactly this way.
- `bump_second_changelog_entry` now derives the target at run time: it finds the second `## X.Y.Z` heading and raises it above the head. Archiving can no longer orphan it. The SECOND entry is used, not the first, so only the descending-order rung fires and the case still isolates the rule it names.
- audit_checks reports 227 of 227 again.

## 7.233.0 -- 2026-08-31 -- Audit Ecosystem Closure: Producer API, HUSH Runtime, Backlog Re-entry (T-1229..T-1244)

Folds the never-tagged 7.232.1 metadata into one release; the ledger carries no phantom version.

- **Shared audit producer API (T-1230, `SOURCE-AUDIT-ENQUEUE-01`).** `tools/saipen_engine/audit_enqueue.py` is the one constrained writer for every producer. Layer numbers come from a monotonic allocator (`.saipen/intake/audit_allocator.json`) and are never reused -- the floor steps over files on disk, this allocator's own records, AND the audit-inbox binding, so a number consumed before the allocator existed cannot be reissued. Placement is reserve-then-place under a narrow writer lock plus a same-process guard: a crash costs at most one spent id, a retry with the same `producer_operation_id` finishes the SAME layer, a retry with different bytes is refused, and a refused placement frees the operation while keeping the id spent. A producer names no path, picks no number, and cannot overwrite a layer or write BOARD/STATE/LOG. `saipen audit enqueue` with full PLAN parity under `--dry-run`.
- **Producer-neutral envelope (T-1231).** An optional leading `<!-- saipen-audit-envelope` block carries `producer`, `producer_item_id`, severity, confidence and related-audit claims. Plain Markdown stays valid, parsing is pure so the generation digest is unaffected, a malformed envelope degrades to "no usable metadata" instead of blocking capture, and every field is a Source CLAIM: nothing routes on it and `maintainer_verdict` is PENDING on intake, so a producer cannot approve its own finding.
- **Maintainer disposition loop (T-1232).** Provenance is written once at capture into the layer binding and outlives the file: after the bytes are journaled away, `saipen audit trace [N]` still answers audit -> receipt -> Work -> disposition, read-only, with no audit body text. A later binding cannot rewrite recorded claims. Rejection is a valid closure.
- **Concurrency hardening and operator surface (T-1233, T-1234).** Concurrent producers take distinct ids with no partial layer ever visible to a scanner (the temp file cannot match the canonical regex). `saipen status` carries a compact `audit_inbox` block -- pending, active layer, bound receipt, bound Work, closed-pending-delete, invalid, last allocated id -- and renders nothing at all when `audit/` is absent.
- **Real HUSH runtime (T-1236, `EXEC-HUSH-01`).** `tools/saipen_engine/hush.py` implements `hush <task>` as a task-local execution-policy modifier: only a leading whole token counts, `<task>` reaches the normal resolver unchanged, and the policy is never persisted to `STATE.md`, so it cannot leak into the next task. The mandatory output set is closed and an unrecognized output kind falls into it, so safety refusals, destructive confirmations, missing authority, terminal failure, protocol corruption, side-effect acknowledgement, evidence and the final report can never be suppressed. `hush cc` routes exactly where `cc` routes, proven across the whole shortcut table. REGISTRY `hush_precedence.status` moved from `planned` to `active` only after that proof.
- **SAIPAL bridge readiness (T-1235).** SAIPAL needs no new surface: the constrained enqueue plus the read-only trace. An AST sweep asserts no engine module carries a producer name outside a docstring, and a hand-dropped file, an AUDAPACK-shaped enqueue and a SAIPAL-shaped enqueue reach a byte-identical transport state.
- **Transport dogfood (T-1237).** All three producer shapes walk discover -> capture through the real Source intake -> bound -> journaled delete. A generation changed after closure is preserved, not deleted; concurrent enqueue is safe; a rejected finding still closes with its item id intact; a cold reader reconstructs provenance and the allocator floor from disk alone.
- **Scenario sandbox no longer manufactures the defect it reports (T-1240).** `run_scenarios.neutralize_sandbox_work_surface` unlinks ONLY receipts whose Work the probe itself deleted from the copied board. A receipt naming Work that exists nowhere stays dangling and still fails, so the check keeps its ability to go red.
- **Verification evidence grammar (T-1241).** `verification_evidence` tested `"FAIL" in txt`, so the canonical zero-failure summary every gate here prints -- `validate.py --gate core 0 FAIL` -- read as negative evidence and VERIFY could not reach REVIEW without a second, weaker event. `_claims_failure` now counts FAIL tokens against zero-count forms: `0 FAIL` and `no failures` pass, while `1 FAIL`, `FAILED`, a bare `FAIL:` prefix and a mixed `core 0 FAIL, ship 3 FAIL` line all still fail. The single-ticket and bulk classifiers share the predicate.
- **Source truth repair.** SRC-011 linked to T-1211 through the journaled duplicate-capture path and given a 20-clause W4 acceptance contract, all VERIFIED against measured tree facts. SRC-007 gained a 14-clause ledger (13 SUPERSEDED by the SRC-008 re-audit, CORE-004 VERIFIED). SRC-008 gained a 13-clause ledger, all VERIFIED against the live engine. All three closed and archived; SRC-015 closes 9 of 9.
- **Backlog re-entry (T-1238).** BOARD 51941 -> 14928 bytes with zero closed-ticket text; 53 DONE entries and 33 tickets whose work is verifiably shipped pruned with cited evidence, no unresolved Work removed, no `needs:` reference broken. `.saipen/LOG.md` 121965 -> 10944 bytes sealed verbatim into `.saipen/logs/LOG-016.md` at E-4977, sequence continuing, no line rewritten. Seven stale producer packages marked `status: stale` by PROTOCOL.md's own contract rather than collected, and the saiwiki OUTBOX repaired by removing a 56-line pasted validator transcript that made the package unparseable.
- **Audit directory hygiene.** `audit/` is a clean inbox again, holding one canonical layer placed through the new enqueue API. The 31 Aug roadmap pack moved to `.saipen/KNOWLEDGE/roadmaps/next-2026-08-31/` as acceptance-bar evidence; the two superseded packs were deleted, their bodies preserved verbatim inside the SRC-015 receipt.
- Scheduler lifecycle probes require a Windows host, not merely a discoverable PowerShell executable. Linux CI runners carrying `pwsh` keep the platform-independent scheduler contract checks and skip only the Windows Task Scheduler lifecycle harness.
- CORE command semantics again state persisted converge-intent continuation plus the USERPERSON precedence and completion-report contracts; hardening control 27 once again has a live validator anchor.
- Known follow-ups filed rather than fixed here: T-1242 (the installed skill copy of the protocol is a stale pre-W4 fork), T-1243 (Conformance read UNKNOWN for every real validator record), T-1244 (the enqueue process guard is held across an unbounded wait on the OS file lock).

## 7.232.0 -- 2026-08-31 -- Native Audit Inbox + Audit Queue Closure (T-1223..T-1227, T-1229)

- T-1227: native Audit Inbox (`SOURCE-AUDIT-INBOX-01`). `tools/saipen_engine/audit_inbox.py` is a transport adapter into the existing Source Receipt lifecycle: canonical `audit/^[1-9][0-9]*\.md$` layers only, non-recursive, generation identity is `relative path + exact-byte SHA-256` (never mtime), foreign files ignored and never deleted.
- `saipen continue` routing gains an Audit Inbox stage AFTER recovery/WAIT/active continuation and BEFORE the ordinary BOARD Pick Rule: a workable unconsumed audit outranks queued TODO and forbids the Improve fallback, but never preempts a live ticket. An audit whose Work is blocked falls through to the Pick Rule.
- `saipen audit status|inspect <N>|ingest`; `saipen next` and `--dry-run` stay read-only. Deletion runs as the journaled `audit_inbox.consume` operation and only after the source closure contract passes AND the bytes still match the captured generation; a changed same-path file becomes a new generation instead. EOL-only `legacy_transport_equivalent` migration binding records both digests and never rewrites a receipt digest.
- T-1223/T-1224: SRC-013 (17/17) and SRC-014 (17/17) closed with evidence; `audit/1.md`, `audit/2.md` and `audit/3.md` consumed by the new journaled path, not by manual unlink -- including audit/3.md self-consumed by the feature it specified.
- T-1226: phase delta compression -- corpus 109077 -> 100304 bytes (ship 17142->12811, translate 13713->10907, markhunt 10888->10160, clean 10696->9788). 16/16 phases and every audit_checks red-control anchor intact; the residual gap to the ~70 KB target is recorded as a justified variance on SRC-013 R008 and carried by T-1229.
- SRC-015 captures the remaining audit-ecosystem roadmap (producer enqueue API, envelope, disposition projection, concurrency hardening, operator surface, SAIPAL bridge, HUSH runtime, dogfood, backlog re-entry) as T-1230..T-1238; the roadmap reference packs moved out of the live inbox to `.saipen/KNOWLEDGE/roadmaps/`.

## 7.231.11 -- 2026-08-31 -- W4/W5 Audit Implementation + PERF-006 (T-1208)

- T-1208: PERF-006 one release authority inventory per PLAN; W4/W5 audit implementation follow-up shipped on top of 7.231.10 (entry backfilled at 7.232.0: the release was tagged without one)

## 7.231.10 -- 2026-08-31 -- Audit Closure SHIP (T-1222..T-1228)

- T-1222/T-1223/T-1224: audit/1,2,3 captured as SRC-012/013/014 with 54 acceptance criteria dispositioned (36 VERIFIED, 18 deferred)
- T-1225: umbrella verification + subtickets T-1226 (W5 phase compression), T-1227 (Audit Inbox), T-1228 (SHIP pre-staging fix)
- T-1228: SHIP blocking resolved (staged SRC-009/SRC-010 coverage + index.json refreshed to working-tree bytes; all SRC-011..SRC-014 intake files staged)

## 7.231.9 -- 2026-08-27 -- SRC-003 Audit All-3 Repair Wave (T-1171)

- T-1171: 28/28 SRC-003 audit clauses VERIFIED. Wave 1 (CORE-001..004): journaled stop/ss, claim-safe stop_checkpoint, non-recursive tt test orchestrator, atomic ccc entry marker. Wave 2 (W2-001..017): journal intermediate file ownership (no-follow/O_CREAT|O_EXCL), liveness cache ownership + concurrency-safe read-modify-write, producer descendant ownership, crash-recoverable source close/archive/purge with idempotent settle, lock acquisition failure unwind, final lock-file no-follow ownership, coherent STATE/BOARD before targeted producer integration, Git-compatible exclusive index rollback lock, canonical chronology for convergence predecessor selection, one coherent ProjectSnapshot for status/next/explain, structured chronological project-bound attribution claims, portable lineage binding for crew defer scope, non-fatal post-COMMITTED settlement, consistent structured SubSaipen receipt corruption handling, source-identity APPLY CAS, truthful producer cleanup_pending. Wave 3 (PERF-001..007): call-scoped linear intake validation, bounded indexed source duplicate lookup, disposable scenario validation, bounded semantic receipt decoding, purpose-specific LOG history retention, owned cross-platform child process-tree cancellation, suite-owned temporary directory cleanup.

## 7.231.8 -- 2026-08-27 -- Repeated CC False-Loop Hardening (T-1170)

- T-1170: repeated cc remains command, same next_action not same state, RUN_ROLE executed, validator not continue, exact no-op only by command

## 7.231.7 -- 2026-08-27 -- CCC Ship Control + FF Analytic Lens (T-1169)

- T-1169: CCC vs SC distinct targets, CONTROLS in runtime, FF performance zero-match analytic brief

## 7.231.6 -- 2026-08-27 -- Runtime Manifest Completeness (T-1168)

- T-1168: add CONTROLS.md to runtime MANIFEST (188 files), install via inject.ps1/sh, autoinject stale detection, CCC vs SC distinct targets

## 7.231.5 -- 2026-08-27 -- Shortcut Payload Routing (T-1167)

- T-1167: `gg <payload>` now routes mechanically via shared resolver; leading shortcut owns payload, destination validates; bare `gg` usage preserved; `cc`/`sss` surplus recognized then refused; unknown tokens still fail closed.

## 7.231.4 -- 2026-08-27 -- Bootstrap Activation Parity + Crew Bootstrap Liveness (T-1166 wave)

- T-1166 + 3-wave hardening: bootstrap shortcut activation now advertises full 19-key canonical set (ff,xx,vv,zz) via `bootstrap/inject.*`, generic `~/.agents/skills` positive detection, Gemini/CodeBuddy skills, FreeBuff always-on knowledge gate; crew SC-0 distinguishes missing MANIFEST bootstrap from malformed corruption (SYNC_SHARED → SPAWN_ROLE); OBEY>UNBLOCK cc over WAIT verified with 11 hostile regressions.

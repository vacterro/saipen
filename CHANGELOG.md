# Changelog
> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

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

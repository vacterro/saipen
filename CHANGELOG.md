# Changelog
> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

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

## 7.231.3 -- 2026-08-26 -- Changelog Active-Set Compaction (T-1165)

- T-1165: retain the 10 newest release entries in `CHANGELOG.md`; move all
  older entries verbatim to the newest-top append-only archive.

## 7.231.2 -- 2026-08-26 -- Canonical Ruff Gate Repair (T-1164)

- T-1164: remove two unused audit-test imports and wrap nine overlong audit/
  continuity lines; behavior is unchanged, canonical Ruff is clean, 307 tests
  pass, 271/271 validator controls go red, and all executable scenarios pass.

## 7.231.1 -- 2026-08-26 -- USERPERSON Legacy Markdown Compatibility (T-1163)

- T-1163: global and project USERPERSON readers accept established Markdown
  `* [Category] preference` bullets alongside the canonical `- ` form.
  Validation remains strict for headers, categories and preference text; the
  next explicit mutation rewrites legacy input to the single canonical `- `
  representation. The real 241-entry global profile now loads byte-unchanged.

## 7.231.0 -- 2026-08-26 -- Lossless Intake, Global USERPERSON, Runtime Identity (T-1162)

- T-1162: immutable source receipts now preserve substantial source input
  verbatim before interpretation, bind derived Work Contracts and clause
  coverage, enforce reread/integrity gates at BUILD/REVIEW/DONE/SHIP, dedupe
  exact bytes, and archive closed bodies without losing tombstone authority.
- T-1162: USERPERSON now composes deterministic global and project profiles
  with explicit provenance and project precedence. Global writes use a
  contained lock plus atomic replacement; boot/context/subSaipen surfaces stay
  silent when inactive and expose only bounded role projections when active.
- T-1162: Adaptive Runtime Wave 1 adds a read-only runtime identity and
  tri-state capability projection. Runtime telemetry cannot override the
  acting agent seat, is never persisted, and missing facts remain UNKNOWN.
- Combined-release audit hardened strict USERPERSON loading: empty category or
  preference fields now fail closed with a regression test.

## 7.230.0 -- 2026-08-25 -- Self-Resolving Gates (T-1161)

- T-1161: INC-MUSE-SHIP-INTERNAL-CHOICE-001 hardened -- MULTIPLE POSSIBLE
  INTERNAL ACTIONS DO NOT CREATE A HUMAN DECISION; no-human-courier law,
  operational-vs-product choice separation, and the user-wait proof
  obligation (missing_authority / evidence_insufficient / consequence) are
  normative in CORE §1.10.
- T-1161: closed disposition vocabulary + classifier
  (`saipen_engine/disposition.py`): EXECUTE_SELF / RECONCILE_SELF /
  WAIT_USER / WAIT_EXTERNAL / BLOCKED / COMPLETE / INVALID, derived from
  carrier fields SAIPEN already emits; stale+refreshable is EXECUTE_SELF,
  never BLOCKED; `blocked`/`safety valve` WAIT categories are not user
  questions.
- T-1161: validator-is-a-sensor law with failure classification and repair
  precedence; semantic laundering (relabeling actionable state as blocked to
  pass syntax) named as a regression class; traceability reconstruction with
  per-finding disposition/evidence/verification mapping -- umbrella tickets
  without durable mapping fail.
- T-1161: `saipen explain-next` READ_ONLY decision-trace diagnostic;
  OPS §10 owns the mechanics.

## 7.229.0 -- 2026-08-25 -- Effect-Based Authorization (T-1160)

- T-1160: INC-PERMISSION-EFFECT-BYPASS-001 hardened permanently --
  authorization now follows the EFFECT exercised (fs.write, repo.mutate,
  process.execute, ...), never the tool name that reached it; indirect
  mutation through shell/interpreter/generator/git is still mutation.
- T-1160: closed effect vocabulary + coverage evaluator
  (`saipen_engine/effects.py`): DENY fails closed, MANUAL needs a scope-bound
  Approval naming the exact effect (paths/Work/Attempt), fs.write implies
  only same-path repo.mutate, process.execute promotes to nothing;
  expected-vs-observed divergence is EFFECT_DRIFT.
- T-1160: policy != enforcement != audit. Enforcement is UNAVAILABLE unless
  the host declares it (`SAIPEN_HOST_ENFORCEMENT`); a MANUAL/DENY policy over
  a non-sandboxed host surfaces as an explicit ENFORCEMENT_GAP, and negative
  safety claims ("no files modified") require evidence -- tool name alone is
  never evidence.
- T-1160: cheap read-only Git worktree delta audit (`tree_snapshot`/
  `tree_delta`, porcelain only); provenance uses KNOWN/UNKNOWN/UNAVAILABLE,
  never inference or intent labels; optional project `.saipen/policy.json`
  may tighten (never loosen) the derived capability policy.
- T-1160: `saipen permissions` READ_ONLY diagnostic (policy, enforcement
  truth, gaps, tool contracts, worktree delta); CORE §1.10 carries the law,
  OPS §9 owns the mechanics.

## 7.228.0 -- 2026-08-25 -- Crew Liveness + Runtime Drift (T-1159)

- T-1159: every actionable crew carrier (CREW_BLOCKED routing carrier,
  RUN_ROLE-style CREW_ACTION) now carries a deterministic
  `action_fingerprint`; the SAME fingerprint twice in a row is surfaced as
  `CREW_STALLED` -- an execution/conformance failure -- instead of silent
  polling. Engine progress clears it; `--dry-run`/read-only never write.
- T-1159: unknown commands in a project whose `saipen_home` names a different
  install than the executing runtime are diagnosed as `RUNTIME_DRIFT` with
  both versions and the safe rebind action, never a bare `unknown command`.
- T-1159: normative CORE §1.10 "No Silent Polling, No Silent Drift" rule;
  stale evidence with a refresh path stays ACTIONABLE.

## 7.227.2 -- 2026-08-24 -- Portable Undo Ownership (T-1158)

- T-1158: binds post-milestone release-scope ownership to the existing
  portable project lineage, so a cold agent in a fresh clone can preview
  published undo without weakening exact-path/hash or foreign-edit checks.
- T-1158: keeps runtime-path identity only for genuinely legacy scope records
  and refuses malformed lineage-bearing records instead of falling back.

## 7.227.1 -- 2026-08-24 -- Published Undo Proof Hardening (T-1157)

- T-1157: proves remote-published post-milestone Work from append-only
  machine-owned release evidence, so `zz` creates forward Revert Work instead
  of restoring published content directly.
- T-1157: adds a hostile regression covering a dirty-since-milestone release,
  fresh-clone-safe publication evidence and preservation of published bytes.

## 7.227.0 -- 2026-08-24 -- Focus, Build, Cut and Undo Controls (T-1156)

- T-1156: adds `ff` read-only semantic focus, `vv` native foreground Work
  intake, two-stage content-bound `xx`, and one-step reasoned `zz` without
  adding phases or bypassing Work/Attempt and Core gates.
- T-1156: adds sparse exact-byte Restore Milestones with explicit lineage,
  crash-safe journals, content deduplication, Git/non-Git baselines, foreign
  edit protection, append-only rollback history and compact status projection.
- T-1156: adds hostile routing, stale-plan, path, binary, crash, published
  history, cold-agent and integrated acceptance coverage; full verification
  evidence is recorded in the ticket closure.

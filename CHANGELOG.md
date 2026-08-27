# Changelog
> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

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

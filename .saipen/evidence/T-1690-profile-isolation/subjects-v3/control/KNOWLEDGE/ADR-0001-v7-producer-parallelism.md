# ADR-0001 — V7 Producer Parallelism Hardening

- **Status:** ACCEPTED
- **Date:** 2026-08-20
- **Ticket:** T-1100
- **Version:** 7.226.0
- **Supersedes:** none
- **Superseded by:** none

## Context

SAIPEN already separated *prepare* (a SubSaipen PRODUCER such as `saitranslate` /
`saiwiki` builds a handoff package) from *collect* (Core consumes exactly one
already-prepared package). But the separation was held together by prose, not by
mechanics: a producer could in principle corrupt another producer's package,
forge readiness, publish from a stale worker after a takeover, mutate Core
STATE/BOARD/LOG, or — worst of all — two independently-prepared packages could
be flagged whole-tree STALE the moment either's source moved, even when their
dependencies did not actually conflict.

The goal is **safe parallel execution of isolated PRODUCER roles without
Concurrent Mode and without a second canonical Core writer**. Core stays the
sole main-tree writer; `saipen crew` stays serial; producer prepare stays
read-only to the main tree; integration/collect/disposition/ship stay
serialized through Core.

## Decision

Eight load-bearing mechanics, each named after the defect class it eliminates:

### 1. Dependency-aware READY packages
A producer package carries `base_source_head`, `base_source_tree_fingerprint`,
`role_revision`, a `read_set` (path → content hash), a `write_set` (target →
before-hash), a deterministic `package_identity`, and the whole-tree fingerprint
for provenance. Classification revalidates `read_set` + `write_set` by **content
hash, never mtime**.

### 2. Explicit conflict model
For any two packages A and B, derive `A.write ∩ B.write`, `A.write ∩ B.read`,
`B.write ∩ A.read` and expose the exact reason. Conflicts are computed, never
guessed.

### 3. Atomic prepare publication
Payloads, manifests, and metadata land in a non-READY staging generation. A
READY record appears only via a final `os.replace` switch. A crash leaves only
incomplete staging — **never a false READY**.

### 4. Producer-local writer exclusion
A `ProducerLock` serializes same-producer writers and grants **no** authority
over the canonical main tree. Cross-producer (`saitranslate` + `saiwiki`) runs
concurrently. Core integration still requires the canonical `project_writer_lock`.

### 5. Producer epoch / stale-worker rejection
Each producer namespace carries a monotonic `ProducerEpoch`. A worker whose
epoch was superseded by a takeover **cannot** publish READY.

### 6. Idempotent package identity
`package_identity` is deterministic over `base_source_head +
base_source_tree_fingerprint + role_revision + read_set + write_set +
requested_scope`. An identical prepare reuses the READY record instead of
duplicating OUTBOX/package records.

### 7. Hard capability boundary
A producer MAY NOT mutate Core STATE/BOARD/LOG, integrate, collect/disposition,
commit/tag/push, or ship. `assert_producer_capability` /
`guard_core_mutation` refuse with `CAPABILITY_DENIED` and perform **zero
writes**.

### 8. Multi-package integration plan
`plan_integration` shows READY packages, base identities,
CURRENT / COMPATIBLE_DRIFT / STALE, read/write conflicts, deterministic order,
and which package must regenerate. No auto-rebase of stale packages.

## Integration classification

- **CURRENT** — identical global source identity (`source_head`,
  `source_tree_fingerprint`, `role_revision`). Fast path: integrate as-is.
- **COMPATIBLE_DRIFT** — source identity changed but the package's `read_set`
  and `write_set` still match live content hashes. Usable; no gratuitous
  whole-tree staleness.
- **STALE** — a `read_set` entry changed, or a `write_set` before-hash
  diverged. Requires reprepare by the owning producer. Never integrated.

## Conformance matrix (tools/test_v7_producer_parallelism.py, A–N, 14/14)

| Test | Covers |
|------|--------|
| A | concurrent `ee` + `qq` allowed |
| B | same-producer `ee` + `ee` serialized, no corruption |
| C | same-producer `qq` + `qq` serialized, no corruption |
| D | crash mid-prepare leaves no READY |
| E | stale epoch cannot publish |
| F | idempotent duplicate prepare reuses READY |
| G | translate-first → wiki is COMPATIBLE_DRIFT |
| H | translate changes wiki read-dep → STALE |
| I | same output from second producer → second refused |
| J | Core unrelated change → package usable (CURRENT/COMPATIBLE_DRIFT) |
| K | Core changes a declared input → STALE |
| L | producer Core mutation / ship → CAPABILITY_DENIED, zero writes |
| M | restart recovery produces no false READY |
| N | integration serialized through Core writer lock |

## Non-goals (preserved)

- No `saipen concurrent` command.
- No distributed STATE/BOARD/LOG or canonical STATE outside Core.
- No Core worktrees.
- No release-captain / takeover / deadlock machinery.
- No change to `saipen crew` semantics.
- No DB, daemon, background service, or background canonical STATE.

## References

- Implementation: `tools/saipen_engine/producer.py`
  (`ProducerPackage`, `classify_integration`, `derive_conflicts`,
  `ProducerEpoch`, `StagingGeneration`, `producer_namespace`,
  `plan_integration`, `integrate_packages_core`, `_live_source_identity`,
  `_live_hashes`).
- Capability boundary: `tools/saipen_engine/capability.py`
  (`assert_producer_capability`, `guard_core_mutation`,
  `PRODUCER_ALLOWED_ACTIONS`, `PRODUCER_FORBIDDEN_ACTIONS`,
  `CAPABILITY_DENIED`).
- Lock: `tools/saipen_engine/lock.py`
  (`ProducerLock`, `producer_writer_lock`).
- Conformance: `tools/test_v7_producer_parallelism.py` (matrix A–N).
- Normative rule: `saipen/CORE.md` § 1.4 Concurrency boundary (V7 producer
  parallelism bullet).
- Changelog: `CHANGELOG.md` `## 7.226.0`.

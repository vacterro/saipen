# T-392: Architectural Reorganization Plan

## 1. Problem Statement & Invariants
**Load:** `saipen/RFC.md` (146KB) and `saipen/CONFORMANCE.md` (181KB) impose extreme context bloat, slowing down operations, increasing API costs, and triggering the "truncation" or "summarization" statistical habits in weaker models.
**Duplication:** Rule definitions often exist in both `RFC.md` and the corresponding `saipen/phases/*.md` files, risking drift.
**Model-Strength Sensitivity:** Small or weak models fail to uphold rules located at the end of a 150KB file.

**Invariants to Preserve:**
- The SAIPEN Litmus Test: The state must be unambiguously defined by file shapes.
- Cold Start: `saipen continue` must remain a 1-minute bootstrap without prior memory.
- Conformance: The validator (`tools/validate.py`) must still trace every normative MUST to an explicit row ID.

## 2. Target Architecture
- **RFC Split:** `RFC.md` will be partitioned. 
  - `saipen/CORE.md`: State graph, file constraints, capability negotiation, and baseline Litmus tests.
  - `saipen/MAINTENANCE.md`: Subagents, goal mode, maintenance cycles (Hunt, Add, Clean).
- **Phase Single Source of Truth:** `saipen/phases/*.md` will become the *only* normative text for phase transition requirements. `CORE.md` will merely enumerate the phases.
- **Conformance Segregation:** `CONFORMANCE.md` will be formally segregated so that only the verification scripts or a `VERIFY` phase agent reads it. Cold-start agents will explicitly ignore it.

## 3. Failure Modes & Compatibility Gates
- **Failure:** Validator breaks due to missing RFC anchor.
  - *Gate:* Validator must be updated to parse `CORE.md` and `MAINTENANCE.md` concurrently.
- **Failure:** Legacy adapters (extensions/adapters/) break because they hardcode a path to `RFC.md`.
  - *Gate:* Provide a backwards-compatible `RFC.md` shim that `includes` or points to the new files until v8.
- **Failure:** Split-brain between CORE and phases.
  - *Gate:* Zero duplication rule enforced by text linting.

## 4. Rollback
- All migrations will be done via standard SAIPEN tickets with Git checkpoints. If `validate.py` fails on CI after any stage, the branch is rolled back.

## 5. Ordered Execution Tickets (Measurable Acceptance Criteria)

- **T-488 [P1] Architecture Partition**: Split `RFC.md` into `CORE.md` and `MAINTENANCE.md`. Update `validate.py` to parse both. Leave a stub `RFC.md` for backwards compatibility. | verify: `validate.py` passes with no dropped conformance row IDs; total byte size remains identical.
- **T-489 [P1] Phase Deduplication**: Remove all phase-specific normative rules from `CORE.md` and `MAINTENANCE.md`. Consolidate them strictly into `saipen/phases/*.md`. | verify: grep for duplicate rule phrasing returns zero; validator text lint is updated.
- **T-490 [P1] Conformance Segregation**: Instruct `BOOT.md` and `STYLE.md` that standard agents must NEVER read `CONFORMANCE.md` unless explicitly debugging a validator failure. | verify: `BOOT.md` contains the exclusion directive.
- **T-491 [P2] Lazy Load Index**: Introduce `saipen/INDEX.md` as the table of contents. Agents read `BOOT.md`, then `INDEX.md`, then fetch only what they need. | verify: A cold agent can complete a ticket reading < 50KB of rules total.

# FUTURE GATE PROPOSAL — SAIGPU LIBRARIAN

STATUS: PROPOSAL / NOT ACTIVE  
IMPLEMENTATION: NOT STARTED  
CANONICAL WORK: NONE  
AUTO-INGEST AS WORK: NO  
MAY SPAWN FUTURE GATE: YES

## Purpose

Preserve for architecture review the concept of a bounded, continuously available local-GPU maintenance worker, tentatively named `SAIGPU_LIBRARIAN`.

The role may reduce project entropy while primary agents are inactive and prepare useful derived artifacts for a later active session. It is not a product coder, protocol owner, or autonomous product maintainer.

> Primary agents advance Work. SAIGPU Librarian reduces entropy around Work.

This is a future design proposal, not permission to start implementation. It must not change current priority, `next_action`, BOARD / STATE / LOG truth, ticket or seat ownership, or operator authority. Promotion must follow the existing architecture-seed-to-bounded-gate path described by [the SAIPEN future architecture index](SAIPEN_FUTURE_ARCHITECTURE_20260918/future_architecture/README.md). The concepts of continuous scheduling and authority separation in [Continuous Worker Mode](SAIPEN_FUTURE_ARCHITECTURE_20260918/future_architecture/05_CONTINUOUS_WORKER_MODE.md) and [Security and Authority](SAIPEN_FUTURE_ARCHITECTURE_20260918/future_architecture/11_SECURITY_AND_AUTHORITY.md) are related constraints, not implementation authorization.

## Candidate role and work

Candidate role name: `SAIGPU_LIBRARIAN`.

Possible bounded maintenance tasks include:

- semantic/search indexing, embedding refresh, and historical recall indexes;
- duplicate, stale-reference, orphaned-artifact, abandoned-worktree, and stale-cache detection;
- documentation classification, organization, consistency checks, and architecture/documentation maps;
- generated wiki, glossary, FAQ, translation, and other derived documentation projections;
- log digestion into indexes, ticket timelines, incident and recurring-failure summaries, and compact digests;
- generated-artifact inventories and candidate cleanup reports;
- preparation of bounded maintenance tickets or proposed documentation changes in an isolated workspace.

These outputs are advisory or derived. They must not reinterpret source-of-truth documents or turn a detected issue into an unapproved canonical edit.

## Authority levels to evaluate

1. `READ_ONLY` — scan, index, embed, classify, compare, and report; no project mutation.
2. `DERIVED_WRITE` — write only explicitly authorized, regenerable projections such as indexes, search databases, summaries, generated wiki/translation projections, manifests, and caches. Keep them visibly distinct from canonical truth and record their inputs/provenance.
3. `MAINTENANCE_CANDIDATE` — prepare proposed documentation or organizational changes only in an isolated maintenance workspace/worktree. No automatic merge into canonical main unless a separate policy explicitly authorizes that exact class of change.

The role must never modify product source code; take ownership of active product Work; change canonical lifecycle meaning; rewrite historical evidence or reorder canonical LOG history; fabricate provenance; close tickets; make SHIP decisions; change active ownership; silently merge candidates; or delete ambiguous artifacts.

## Eligibility and execution shape

Consider work only when exact SAIPEN machine truth says there is no conflicting active primary owner or lease. Candidate eligible states include `DONE`, `STOPPED`, `WAITING_OPERATOR`, `WAITING_EXTERNAL`, `WAITING_SOAK`, or an equivalent explicitly parked state. Avoid active phases such as `BUILD`, `VERIFY`, `REVIEW`, and `SHIP`. UI appearance and elapsed time alone are not eligibility evidence.

Proposed bounded flow:

1. Check machine-state eligibility, active ownership, leases, and conflicting field gates.
2. Acquire a scoped, expiring maintenance lease; fail closed if ownership is unclear.
3. Inventory read-only and classify work by allowed authority level.
4. Run eligible local-GPU maintenance within per-project and global resource budgets.
5. Validate outputs and provenance; publish only derived writes explicitly authorized by policy, and keep candidates isolated.
6. Produce one bounded maintenance digest, record actions and non-actions, then release the lease.

Prefer an isolated workspace over the canonical working tree. Do not establish a new workspace path convention until existing path ownership, lease, and cleanup rules have been reviewed. If the project becomes active or a conflicting lease appears, stop mutation and release/expire the maintenance lease safely.

## Provenance, logs, and staleness

Detect stale or inconsistent documentation and report structured findings or candidate fixes rather than silently rewriting canonical files. For example, a README that marks a ticket `TODO` while machine truth says `DONE` is a finding, not authority to edit the README.

Treat translations as derived projections where practical. Bind each projection to source path and digest, generation timestamp, translation schema/version, and translator/runtime provenance when available. If its source digest changes, mark it `STALE`; do not present it as current.

Never rewrite canonical logs for neatness. Build derived log indexes, timelines, incident summaries, recurring-failure reports, searchable semantic indexes, or compact human-readable digests while leaving canonical evidence untouched.

## Cleanup and resource governance

Automatic deletion, if ever considered, must be narrow, deterministic, and backed by an explicit garbage/retention policy. Prefer detection, classification, quarantine candidates, and operator/reviewer confirmation for ambiguous artifacts. Ambiguity means retain and report.

Consider opportunistic scheduling based on GPU idle time, CPU load, absence of an active primary agent, absence of conflicting field gates, maintenance windows, and per-project budgets. Candidate workload tiers:

- `LOW`: embeddings, indexing, metadata refresh;
- `MEDIUM`: classification, summaries, duplicate/staleness analysis;
- `HIGH`: local-LLM translation, wiki generation, larger documentation synthesis.

Future policy should bound GPU minutes, generated tokens, files touched, candidate count, and disk growth per project. Resource availability never grants semantic or lifecycle authority.

## Reporting

If SAIMAIL is available, prefer one bounded maintenance digest over many small notifications. Report counts/findings for indexed items, stale references, duplicates, orphaned artifacts, stale translations, candidates prepared, and actions explicitly not taken. State clearly when no canonical lifecycle truth or protected source was modified. Do not notify or wake a primary agent repeatedly for routine progress.

## Review questions before promotion

Any later architecture review should define the machine-truth eligibility contract, lease ownership and interruption behavior, exact derived-write allowlist, provenance schema, workspace/path ownership, publication rules, cleanup/retention policy, resource ceilings, report delivery policy, and how a human or primary agent accepts/rejects candidates. It should also test cold recovery and prove that generated projections cannot outrank canonical sources.

Only after those decisions should a bounded future gate be proposed with explicit acceptance criteria and activation conditions. This proposal itself creates no ticket, lease, active Work, path convention, or implementation task.

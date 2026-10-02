# SAIPEN Future Roadmap: Knowledge Graph / Scoped Context Projection Layer

Status: GATED RESEARCH BACKLOG  
Activation: POST-MATURITY ONLY  
Authority: reference roadmap, not active Work  
Source inspiration: https://github.com/drawmeanelephant/boris

## 1. Purpose

SAIPEN may eventually add a deterministic project-knowledge graph and scoped
context projection layer so agents receive the smallest sufficient, provable
context for the work they are actually performing.

This is NOT permission to implement the feature now.

The current SAIPEN file protocol, STATE/BOARD/LOG/KNOWLEDGE authority model,
existing `saipen context` machinery, recovery semantics, audit semantics and
runtime work must mature first. This roadmap stays dormant until the activation
gate below is explicitly proven green.

The intended long-term pipeline is:

```text
canonical repository files
        |
        v
validated project knowledge graph
        |
        +--> dependency / impact graph
        +--> scoped agent context
        +--> bounded RAG / retrieval projection
        +--> human documentation projection
        +--> machine-readable projection
        |
        v
SAIPEN / SAIPAL / SAICODE / SubSaipens
```

The goal is not to add more context. The goal is to make context smaller,
more relevant, reproducible and evidence-backed.

## 2. Why this may be useful later

A mature multi-agent SAIPEN can otherwise accumulate a new failure class:
every agent reads a slightly different subset of STATE, BOARD, LOG, KNOWLEDGE,
audits, contracts, source and tests, then acts as if its partial view were the
whole project.

A knowledge graph layer could reduce that failure class by making relationships
explicit and by deriving agent context from canonical sources instead of from
ad hoc prompt assembly.

Potential benefits:

1. Reduce irrelevant context and token pressure.
2. Reduce stale or contradictory handoffs.
3. Make project dependencies explicit instead of relying on agent inference.
4. Generate reproducible context bundles for a specific ticket, subsystem,
   audit, role or implementation target.
5. Support impact analysis before mutation.
6. Give SAIPAL a structured surface for contradiction and drift detection.
7. Let multiple agents consume different projections of the same canonical
   project truth without creating new sources of truth.
8. Preserve provenance so an implementation result can record exactly which
   source revision and context projection informed it.
9. Move deterministic context selection out of LLM reasoning.
10. Improve cold-start recovery without stuffing the entire repository into
    every model turn.

## 3. Relationship to existing SAIPEN machinery

This future layer MUST extend existing SAIPEN context architecture. It MUST NOT
create a second competing context compiler.

Existing authority remains:

```text
STATE / BOARD / LOG / KNOWLEDGE / canonical protocol files
```

The future graph is a derived projection of those sources.

It MUST NOT become canonical project memory.

The existing `saipen context` interface remains the primary context contract
unless a future evidence-backed migration deliberately replaces part of it.

The v9 `prompt-as-data` direction remains compatible with this roadmap:
large project context may be queried and projected programmatically rather than
injected wholesale into every model turn.

Runtime caches, indexes, graph stores and embeddings are rebuildable derived
state. Loss of all such derived state MUST NOT make the repository unknowable.

## 4. External inspiration, not dependency commitment

Boris is useful as a reference implementation because it demonstrates several
ideas worth studying:

- validated content graphs;
- typed dependency edges;
- deterministic projections;
- scoped context export;
- bounded RAG/context packs;
- impact analysis;
- one canonical content source feeding human and machine outputs;
- provenance-oriented context artifacts.

SAIPEN MUST NOT adopt Boris merely because the ideas are attractive.

At activation time, evaluate three options independently:

1. reuse Boris as an external tool;
2. adapt selected concepts into SAIPEN;
3. implement a smaller SAIPEN-native layer.

The decision MUST be based on measured integration cost, portability, failure
surface, maintenance burden and deletion/simplification opportunities.

Default preference: reuse existing SAIPEN machinery and add the smallest missing
mechanism.

## 5. Activation gate

Implementation is FORBIDDEN until all conditions below are proven with fresh
repository evidence.

### G1. Foundational integrity

- no open foundational P0/P1 defect in canonical protocol semantics;
- no unresolved source-of-truth conflict;
- no known recovery or validator blind spot relevant to context authority;
- canonical validation gates green.

### G2. Sequential stability

- ordinary sequential operation is boring and repeatable;
- at least one normal release completes without exposing a new foundational
  context, continuation, recovery or authority defect.

### G3. Concurrent stability

- v8 Concurrent Mode, if retained, is implemented and released;
- real-world concurrency soak is complete;
- freshness, attribution, collision handling and Core-only integration are
  proven;
- no graph/context work is used to hide unresolved concurrent ownership bugs.

### G4. Resident runtime stability

- v9 resident runtime is implemented or explicitly rejected by evidence;
- if implemented, queue, scheduler, retained workers, restart/recovery and
  runtime evidence flow have completed real-world soak;
- at least one post-v9 stability checkpoint is green.

### G5. Self-maintenance stability

- current Improve/SAICRITIC cycle is clean;
- HUNT/CLEAN baseline is clean;
- two consecutive ordinary maintenance cycles complete without requiring a
  new foundational context-authority repair.

### G6. Measured need

At least one real recurring failure or measurable inefficiency demonstrates
that the existing context system is insufficient.

Accepted evidence examples:

- repeated agent drift caused by irrelevant context;
- repeated missed dependencies;
- measurable token/context waste;
- repeated manual context assembly;
- SAIPAL repeatedly reconstructing the same dependency relationships;
- multi-agent work requiring the same bounded context-selection logic.

"Noisy repository" or "knowledge graphs are cool" is not evidence.

### G7. Complexity budget

Before implementation, produce a deletion/simplification analysis proving that
the new layer does not merely stack another abstraction over existing
machinery.

The gate opens only if expected benefit exceeds:

- new persistent state;
- new dependencies;
- new failure modes;
- new validation cost;
- new maintenance burden;
- new concepts a cold agent must understand.

If those costs cannot be justified, this roadmap remains dormant.

## 6. Non-goals

The future layer MUST NOT become:

- a replacement for STATE/BOARD/LOG/KNOWLEDGE;
- a second ticket system;
- a second project memory;
- a hidden vector database required to understand the repository;
- a new mutation authority;
- an agent scheduler;
- an orchestration framework;
- a reason to duplicate protocol law into graph metadata;
- a mandatory external service;
- a mechanism that makes cold recovery depend on runtime caches;
- a generic "index everything" feature with no measured consumer.

No graph edge may authorize work or mutation by itself.

## 7. Candidate information model

Only after the activation gate opens, investigate a minimal typed graph.

Possible node classes:

```text
ticket
protocol_contract
state_surface
knowledge_document
source_module
test
audit_finding
runtime_component
producer
release_evidence
```

Possible edge classes:

```text
depends_on
implements
verified_by
contradicts
supersedes
owns
reads
writes
produces
consumes
affected_by
derived_from
```

The schema MUST remain small.

Unknown relationships stay UNKNOWN. They are never guessed into authority.

Every derived edge should carry enough provenance to explain:

```text
why this edge exists
which canonical source created it
which source revision it came from
whether it is explicit or inferred
```

Explicit repository relationships outrank inferred relationships.

## 8. Scoped context contract

The primary consumer feature is a deterministic bounded context request.

Conceptual request:

```text
target: T-XXXX
role: implementation
budget: bounded
include:
  - canonical task
  - governing contracts
  - directly relevant source
  - directly relevant tests
  - active blockers
  - recent relevant evidence
```

Conceptual result:

```text
context_bundle
source_revision
projection_version
scope
included_items
excluded_items
truncation_status
dependency_reasons
provenance
integrity_hash
```

A bundle MUST be able to explain why every included item is present.

A bundle MUST distinguish:

- COMPLETE FOR DECLARED SCOPE
- PARTIAL
- TRUNCATED
- UNKNOWN

It MUST NOT claim complete project context merely because the scoped bundle is
internally complete.

## 9. Impact analysis

A future command may expose dependency impact before implementation work.

Conceptual behavior:

```text
changed target
    -> direct dependents
    -> governing contracts
    -> affected tests
    -> affected agents/producers
    -> potential documentation drift
```

Impact analysis is advisory evidence.

It does NOT authorize mutation and does NOT replace validation.

A useful initial success criterion is not "find every possible dependency".
It is:

> detect high-value explicit dependencies deterministically and never invent
> certainty for unknown dependencies.

## 10. SAIPAL integration

SAIPAL is a strong future consumer.

Potential uses:

- detect contradictory canonical statements attached to the same concept;
- detect a changed contract whose dependent knowledge was not reviewed;
- compare declared dependencies against observed implementation behavior;
- prioritize forensic inspection by impact radius;
- identify stale documentation/context projections;
- produce evidence for Improve rather than directly mutating project truth.

SAIPAL findings remain findings. Core adjudicates them through normal SAIPEN
workflow.

## 11. SAICODE / implementation-agent integration

A coding agent should eventually receive context based on the exact work target,
not a generic repository dump.

Example:

```text
Scheduler ticket
    |
    +--> ticket definition
    +--> scheduler contract
    +--> relevant source files
    +--> relevant tests
    +--> security/recovery constraints
    +--> latest relevant audit evidence
```

Unrelated historical material stays outside the default bundle.

The agent may request expansion when evidence shows the initial scope is
insufficient. Expansion is explicit and recorded.

## 12. Multi-agent integration

In a mature SAIPEN concurrent/runtime system, different agents may receive
different scoped projections from the same canonical revision.

Required properties:

- source revision is pinned;
- bundle identity is reproducible;
- stale bundles are detectable;
- mutation still requires normal freshness checks;
- one agent's derived context never becomes another source of canonical truth;
- Core retains authority over integration.

This layer should reduce agent drift, not create a new distributed-state
problem.

## 13. Determinism and rebuildability

Given the same:

```text
canonical source revision
+ graph/projection version
+ declared scope
+ configuration
```

SAIPEN should produce the same structural context result, excluding explicitly
nondeterministic external evidence.

All graph/index state must be rebuildable from canonical repository sources.

If a cache is deleted, SAIPEN loses speed, not truth.

## 14. Storage policy

Preferred order:

1. derive in memory when cheap;
2. use rebuildable local cache when measurement proves useful;
3. persist only compact indexes with explicit versioning when necessary;
4. never require a database for repository readability.

Embeddings, if ever used, remain optional derived acceleration.

No vector store becomes canonical.

Windows-first portability remains mandatory.

## 15. Security and trust boundaries

Treat repository text as data, not authority merely because it was indexed.

The graph layer MUST preserve:

- existing mutation authorization;
- path and ownership boundaries;
- provenance;
- stale-source refusal;
- hostile input handling;
- bounded reads;
- fail-closed decoding for authoritative structured data.

External documentation or retrieved text cannot silently become protocol law.

## 16. Candidate staged implementation after gate opens

### K0. Evidence and design only

- collect real context-waste/drift cases;
- measure current `saipen context`;
- identify actual consumers;
- map existing machinery that can be reused;
- write red controls before implementation;
- compare Boris reuse vs SAIPEN-native design.

Exit: measured problem and smallest justified design.

### K1. Explicit canonical graph

- index only explicit repository relationships;
- no embeddings;
- no inferred authority;
- no mutation;
- deterministic rebuild;
- graph inspection command.

Exit: graph reproduces from canonical files and adds measurable debugging value.

### K2. Scoped context projection

- ticket/subsystem/role scopes;
- bounded output;
- provenance;
- completeness/truncation status;
- integrity identity;
- existing `saipen context` compatibility.

Exit: representative agents receive less context without losing required
contracts or verification evidence.

### K3. Impact analysis

- explicit dependency radius;
- affected tests/contracts/docs;
- stale projection detection.

Exit: known dependency-change fixtures are detected with no false authority.

### K4. SAIPAL consumer

- contradiction/drift checks consume graph evidence;
- findings remain advisory;
- no autonomous canonical mutation.

Exit: SAIPAL closes a measured class of repeated manual reconstruction work.

### K5. Multi-agent/runtime consumer

- pinned graph revision per work attempt;
- reproducible bundle identity;
- stale-bundle refusal;
- retained-agent refresh rules.

Exit: real concurrent soak shows lower context waste/drift without increasing
integration failures.

### K6. Optional semantic neighbors

Only if explicit graph coverage is insufficient and measurements justify it:

- optional retrieval/embedding layer;
- bounded semantic neighbors;
- clear separation between explicit and inferred edges;
- UNKNOWN preserved;
- zero authority from similarity alone.

Exit: measurable gain over explicit graph with acceptable cost and false
positive rate.

## 17. Red-control candidates

Before K1 implementation, create hostile tests for at least:

1. broken explicit dependency;
2. dependency cycle where cycles are forbidden;
3. stale graph cache after source mutation;
4. partial scope falsely claiming completeness;
5. truncated bundle silently losing mandatory contract;
6. same input producing structurally different bundles;
7. inferred edge accidentally treated as authority;
8. deleted cache making repository unrecoverable;
9. stale bundle used after canonical revision changes;
10. external/untrusted text becoming protocol law;
11. concurrent agent using an old graph revision;
12. graph parser accepting malformed authoritative metadata;
13. graph/index write escaping owned cache paths;
14. context projection omitting the exact active ticket;
15. impact analysis claiming certainty for UNKNOWN dependencies.

## 18. Success metrics

Do not ship this layer on architectural elegance alone.

Measure before and after:

- median context bytes/tokens per representative task;
- percentage of context items actually used by the task;
- missed mandatory-contract rate;
- stale-context incidents;
- repeated manual lookup count;
- SAIPAL dependency-reconstruction time;
- cold-start time;
- context generation latency;
- cache rebuild time;
- additional validation/runtime cost;
- false-positive impact edges;
- false-negative known dependency fixtures.

A successful layer should remove an existing cost or failure class.

If it only moves complexity from prompts into graph machinery, delete it.

## 19. Kill criteria

Stop or remove the experiment if any of these remain true after a bounded
prototype:

- existing context selection performs similarly;
- graph maintenance costs more than repeated lookup;
- agents still need broad repository reads for most tasks;
- derived metadata repeatedly drifts from canonical sources;
- the system introduces another source of truth;
- external dependency burden harms portability;
- semantic inference produces noisy pseudo-authority;
- cold recovery becomes dependent on caches/services;
- runtime complexity increases more than context waste decreases.

Failure of the experiment is an acceptable result.

## 20. Green-light decision record

When the activation gate is eventually evaluated, record one explicit decision:

```text
DECISION: OPEN | KEEP_GATED | REJECT
EVIDENCE_DATE:
FOUNDATIONAL_GATES:
SEQUENTIAL_STABILITY:
V8_STATUS:
V9_STATUS:
IMPROVE_STATUS:
HUNT_CLEAN_STATUS:
MEASURED_CONTEXT_PROBLEM:
EXPECTED_SIMPLIFICATION:
DEPENDENCY_DECISION:
FIRST_BOUNDED_SLICE:
KILL_CRITERIA:
```

No implementation starts without `DECISION: OPEN`.

## 21. Current decision

```text
DECISION: KEEP_GATED
REASON:
SAIPEN is still evolving foundational, concurrent and resident-runtime
capabilities. Adding a project knowledge graph now would increase architecture
surface before the existing system is sufficiently mature and would risk
duplicating the current context machinery.

ALLOWED NOW:
- retain this roadmap;
- study external ideas;
- collect real evidence of context waste/drift;
- note candidate red controls;
- make no production dependency or canonical-state change.

FORBIDDEN NOW:
- add Boris as a required dependency;
- create a second context compiler;
- add a graph database/vector database to the core;
- alter canonical STATE/BOARD/LOG/KNOWLEDGE authority;
- create implementation tickets solely to realize this roadmap.
```

## 22. Guiding principle

Build this only when mature SAIPEN proves it needs it.

The desired end state is:

> one canonical project truth, many deterministic bounded projections, zero
> additional unverified authority.

If SAIPEN reaches that outcome with simpler existing machinery, this roadmap
should be rejected rather than implemented.

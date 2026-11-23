SAIPEN
FUTURE GATE — EXTERNAL ARCHITECTURE MINING / PROTOCOLIST BENCH

STATUS: FUTURE_ARCHITECTURE / KEEP_GATED / NOT AUTHORIZED FOR RUNTIME IMPLEMENTATION
ROLE: SAIPEN PROTOCOLIST
MODE: RESEARCH -> COMPARE -> ADJUDICATE -> RECORD
PRIORITY: PRESERVE SAIPEN AUTHORITY > EXTRACT USEFUL MECHANISMS > NOVELTY
IMPLEMENTATION AUTHORITY: NONE

MISSION

Evaluate a bounded set of external agent/process/context systems as architecture references for future SAIPEN evolution.

The purpose is NOT to install these systems, wrap SAIPEN around them, or create a second control plane.

The purpose is to identify specific mechanisms that may improve SAIPEN while preserving SAIPEN's existing authority, lifecycle, evidence, recovery, and ownership contracts.

The external project is never the unit of adoption.
The unit of adoption is one proven mechanism with explicit ownership and failure semantics.

CANDIDATE BENCH

P1 — GitHub Spec Kit
Repository:
https://github.com/github/spec-kit

Inspect:
- resumable workflow model
- persisted workflow state
- human review gates
- extensions
- presets and precedence
- bundles and version pinning
- provenance and conflict handling
- artifact introspection
- process packaging
- idea-assessment and bug-fix processes

Primary question:
Can SAIPEN gain composable protocol capabilities without creating a second workflow authority?

P2 — OpenSpec
Repository:
https://github.com/Fission-AI/OpenSpec

Inspect:
- artifact dependency graph
- delta specifications
- ADDED / MODIFIED / REMOVED / RENAMED semantics
- change folders
- validation
- sync/archive lifecycle
- transactional archive behavior
- preserved history
- brownfield change representation

Primary question:
Can future SAIPEN protocol/spec changes use explicit deltas and atomic promotion instead of broad canonical rewrites?

P3 — OpenMontage
Repository:
https://github.com/Calesthio/OpenMontage

Inspect only architecture/protocol mechanisms:
- pipeline manifest authority
- canonical machine-readable artifacts
- checkpoint states
- awaiting_human semantics
- decision_log
- approval scope
- pre-authorization policy
- agent END-TURN behavior at gates
- tool registry boundaries

Do not import video-production concerns.

Primary question:
Can SAIPEN strengthen checkpoint, approval-scope, and decision-provenance semantics?

P4 — Caveman
Repository:
https://github.com/JuliusBrussee/caveman

Inspect:
- recoverable context compression
- original-byte preservation
- exact recovery path
- shape-aware compression
- token measurement
- passthrough when compression is unsafe or useless
- agent integration boundaries

Primary question:
Can SAIPEN introduce a derived context representation that reduces context cost while preserving exact canonical source recovery?

P5 — Headroom
Repository:
https://github.com/headroomlabs-ai/headroom

Inspect:
- live-zone-only compression
- cache-hot-zone preservation
- type-aware transforms
- recent-code protection
- analysis-context protection
- reversible context handling
- proxy vs library integration boundaries
- metrics and budget surfaces

Primary question:
Can SAIPEN optimize agent-visible context without mutating canonical history or weakening auditability?

P6 — Hermes Agent
Repository:
https://github.com/NousResearch/hermes-agent

Inspect:
- isolated profiles
- agent capability/tool manifests
- memory boundaries
- skills lifecycle
- reusable procedural knowledge
- MCP filtering
- routines
- multi-agent isolation
- provider independence
- session recall

Primary question:
Which isolation and capability-management mechanisms are useful without allowing learned agent state to become protocol truth?

P7 — Docling
Repository:
https://github.com/docling-project/docling

Inspect:
- source-preserving document normalization
- unified document representation
- layout/table/code/formula preservation
- deterministic export surfaces
- local processing boundaries

Primary question:
Can Docling-like normalization improve SAIPEN evidence intake while remaining strictly derived from original evidence?

P8 — PageIndex
Repository:
https://github.com/VectifyAI/PageIndex

Inspect:
- hierarchical document indexing
- vectorless reasoning retrieval
- corpus-level indexing
- local-mode operation
- source localization
- index rebuild/invalidation semantics

Primary question:
Can a derived index reduce retrieval cost without becoming an authority source?

P9 — mem0
Repository:
https://github.com/mem0ai/mem0

Inspect:
- memory lifecycle
- memory history
- semantic retrieval
- deduplication/conflict concepts
- graph-style cross-memory relations
- persistence boundaries

Hard constraint:
Memory MUST NOT own canonical ticket state, lease state, verification state, next_action, or protocol rules.

Primary question:
Is there any useful non-authoritative memory mechanism that improves recall without creating truth drift?

P10 — Daytona
Repository:
https://github.com/daytonaio/daytona

Important:
The public repository states that it is no longer maintained as of June 2026.

Inspect architecture only:
- execution isolation
- sandbox lifecycle
- filesystem/network/process separation
- executor abstraction
- resource boundaries

Do not propose Daytona OSS as a required SAIPEN dependency.

Primary question:
What generic executor/sandbox contract should SAIPEN expose without coupling protocol semantics to one runtime?

P11 — Fabric
Repository:
https://github.com/danielmiessler/Fabric

Inspect:
- reusable named procedural patterns
- provider-independent instruction assets
- pattern versioning/organization
- testability across providers

Primary question:
Should some SAIPEN procedural roles become explicit versioned assets rather than duplicated prompt prose?

P12 — TrendRadar
Repository:
https://github.com/sansan0/TrendRadar

Inspect as optional future intelligence plugin only:
- source aggregation
- filtering
- scheduled collection
- local evidence storage
- MCP-facing analysis
- notification boundaries

Primary question:
Can an optional radar feed external changes into SAIPEN intake without gaining mutation authority?

P13 — Scrapling
Repository:
https://github.com/D4Vinci/Scrapling

Inspect as optional research/intake adapter only:
- adaptive extraction
- crawl pause/resume
- source change tolerance
- structured extraction

Primary question:
Can public-web research adapters provide candidate evidence with explicit provenance and no authority?

P14 — AI Engineering Hub
Repository:
https://github.com/patchy631/ai-engineering-hub

Inspect only as a reference corpus for implementation patterns.

Primary question:
Are there reusable implementation patterns worth recording as references?

P15 — HyperFrames
Repository:
https://github.com/heygen-com/hyperframes

Inspect only the generic deterministic-build concepts:
- same input -> same output
- non-interactive agent-friendly generation
- CI/regression verification
- deterministic artifact pipelines

Do not import video-specific runtime concerns.

Primary question:
Are there useful deterministic-artifact invariants applicable to SAIPEN generators?

CANONICAL AUTHORITY INVARIANT

SAIPEN remains the sole protocol authority.

External systems or derived layers MUST NOT independently own or mutate:

- canonical Work state
- BOARD truth
- lifecycle truth
- ticket completion
- verification status
- lease ownership
- next_action
- protocol invariants
- canonical evidence disposition

Optional components may:
- derive
- index
- compress
- search
- summarize
- suggest
- propose
- execute explicitly authorized work

Optional components may NOT silently promote derived information into canonical truth.

NO SECOND CONTROL PLANE

Reject any design that requires SAIPEN and another framework to independently coordinate the same work lifecycle.

Bad:
SAIPEN state machine + external state machine both deciding what happens next.

Allowed:
SAIPEN owns the lifecycle.
An external/derived component provides a bounded capability through an explicit adapter.

PLUGIN PRINCIPLE

Absence of an optional project or plugin MUST degrade capability, not SAIPEN availability.

Example:
SAIPAL unavailable -> forensic capability unavailable.
AUDAPACK unavailable -> packaging capability unavailable.
External index unavailable -> canonical direct-read path remains valid.

Never:
optional component unavailable -> SAIPEN refuses unrelated protocol work.

DERIVED CONTEXT CONTRACT CANDIDATE

Investigate a future contract with these properties:

1. Canonical bytes remain unchanged.
2. Compressed/normalized/indexed representations are explicitly DERIVED.
3. Every derived segment can identify its canonical source.
4. Lossy transformation never destroys the recoverable original.
5. Unsafe or failed transformation falls back to canonical/original data.
6. Security, irreversible actions, protocol invariants, errors, commands, evidence hashes, and exact machine contracts receive stronger preservation rules.
7. Derived representation can be discarded and rebuilt.
8. Derived representation cannot complete, verify, claim, close, or mutate canonical work.

PROTOCOL DELTA CONTRACT CANDIDATE

Investigate whether future SAIPEN protocol evolution should support:

PROPOSAL
  ->
EXPLICIT DELTA
  ->
VALIDATION
  ->
REVIEW
  ->
ATOMIC PROMOTION
  ->
PRESERVED HISTORY

A delta may describe:
- ADD
- MODIFY
- REMOVE
- RENAME

The current canonical protocol remains authoritative until promotion succeeds.

Partial promotion is forbidden.

Failure must leave or restore the previous canonical state.

Do not implement this contract in this gate.

CAPABILITY / EXTENSION CONTRACT CANDIDATE

Investigate whether SAIPEN should eventually expose an introspectable capability stack.

Desired properties:
- explicit capability ID
- owner
- source
- version
- dependencies
- optional/required classification
- precedence
- activation state
- provenance
- health
- conflict detection
- read-only "why is this active?" introspection

Optional extensions must not silently replace kernel invariants.

AGENT LEARNING CONTRACT CANDIDATE

Agent experience may create:
- hypotheses
- proposed skills
- suggested procedures
- reusable hints

It may NOT autonomously create or modify:
- protocol invariants
- canonical state rules
- verification requirements
- authority rules

Promotion of learned behavior must remain proposal-first and reviewable.

EXECUTOR CONTRACT CANDIDATE

Separate:

SAIPEN:
- what work is legal
- who owns authority
- what state transition is valid

EXECUTOR:
- where/how work runs

Future executors may include:
- local process
- isolated process
- VM
- container
- remote sandbox
- other adapters

Executor failure must not redefine protocol truth.

REQUIRED RESEARCH OUTPUT

For every candidate produce a compact dossier containing:

1. Exact project and inspected revision/date.
2. Mechanism being evaluated.
3. Authority model.
4. Persistence model.
5. Recovery/failure semantics.
6. Resumability semantics.
7. Provenance/auditability.
8. Mutation rights.
9. Human-gate behavior.
10. Optionality/coupling.
11. Maintenance/license/dependency risk where relevant.
12. Existing SAIPEN equivalent, if any.
13. Gap actually solved.
14. New failure modes introduced.
15. Verdict.

VERDICT VALUES

ADAPT_CONCEPT
A useful mechanism exists, but SAIPEN must own its implementation/contracts.

REFERENCE_ONLY
Useful architectural evidence; no implementation is currently justified.

KEEP_GATED
Potentially valuable but requires later maturity or measured pain.

REJECT
Conflicts with SAIPEN authority, adds a second control plane, creates unacceptable coupling, or does not solve a demonstrated problem.

DIRECT_ADOPTION must NOT be used by this gate.

EFFICIENCY FRAMEWORK

For each candidate mechanism normalize:

B = Benefit
A = Relevance
N = Reliability
C = Cost
R = Risk
L = Side Losses

Use:
Value = B * A * N
Penalty = wC*C + wR*R + wL*L

Report:
- heuristic Scenario Efficiency
- confidence
- important assumptions
- strongest positive driver
- strongest negative driver
- sensitivity
- implementation horizon

Do not create false precision.
Prefer ranges when evidence is weak.

MANDATORY CONFLICT MATRIX

For every mechanism explicitly compare against:

- existing canonical authority
- state ownership
- BOARD/Work lifecycle
- guard behavior
- lease ownership
- continuation/next_action semantics
- evidence model
- recovery semantics
- audit trail
- optional capability behavior
- existing future architecture gates

Deduplicate by root cause/mechanism, not project name.

If OpenSpec, Spec Kit, and OpenMontage all expose variants of the same useful mechanism, produce ONE SAIPEN concept dossier with comparative evidence, not three duplicate future features.

HIGH-VALUE CONCEPT FAMILIES TO TEST

A. Composable protocol capabilities with provenance.
B. Explicit protocol/spec deltas with atomic promotion.
C. Resumable workflow/checkpoint semantics.
D. Scoped human approval and pre-authorization.
E. Reversible derived-context compression.
F. Derived knowledge/index layers with source traceability.
G. Agent/profile/capability isolation.
H. Proposal-first learned procedural skills.
I. Runtime-independent executor/sandbox adapters.
J. Optional external intelligence intake.

These are hypotheses, not approved features.

RED FLAGS / VETO

A mechanism is vetoed for future adoption if it requires:

- duplicate canonical state ownership
- silent protocol mutation
- opaque lossy evidence transformation
- unrecoverable source replacement
- derived memory becoming truth
- optional plugin becoming bootstrap-critical without explicit justification
- executor vendor semantics leaking into protocol authority
- autonomous learned rules without promotion/review
- hidden precedence
- unbounded autonomous workflow loops
- inability to explain why a rule/capability is active
- inability to reconstruct canonical evidence from a derived representation where exact recovery is required

CURRENT DECISION

KEEP_GATED.

This gate authorizes architecture research and adjudication only when explicitly activated.
It does not authorize runtime integration or production code changes.

ENTRY CONDITIONS FOR ACTIVATION

Prefer activation after:
- current authority/liveness/recovery defects are stable enough that external concepts can be evaluated against trustworthy baseline behavior
- canonical ownership contracts are documented and testable
- optional capability semantics are understood
- measured context/retrieval/process pain exists for the mechanism being considered
- the user explicitly activates this FUTURE GATE

FIRST ACTIVATED SLICE

Research only.

Do not prototype all candidates.

Produce:
1. one deduplicated concept map
2. one conflict matrix
3. one verdict matrix
4. at most three proposed future implementation slices

Each proposed slice must state:
- exact problem
- measured or evidenced pain
- existing SAIPEN behavior
- proposed invariant
- expected benefit
- new risks
- rollback path
- acceptance criteria
- why existing SAIPEN primitives cannot already solve it

STOP CONDITION

STOP after the research/verdict artifacts are complete.

Do not implement any shortlisted mechanism in the same wave.

Implementation requires a separate explicit FUTURE GATE activation for one selected mechanism.

FINAL REPORT FORMAT

CONCEPT | SOURCE PROJECTS | SAIPEN GAP | VERDICT | SCENARIO EFFICIENCY | CONFIDENCE | MAIN RISK | NEXT GATE

Then provide:

ADAPT_CONCEPT:
<deduplicated concepts>

REFERENCE_ONLY:
<references>

KEEP_GATED:
<future candidates>

REJECT:
<rejected mechanisms and exact conflict>

TOP 3 FUTURE SLICES:
<no more than three>

RUNTIME CHANGES:
NONE

CANONICAL STATE MUTATION:
NONE

FINAL DECISION:
KEEP_GATED | READY_FOR_SINGLE_SLICE_GATE | REJECT_ALL
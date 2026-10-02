# FUTURE GATE — VERIFIED SHARED KNOWLEDGE LAYER

Status: REFERENCE ONLY / NOT AUTHORIZED FOR IMPLEMENTATION

## IDEA

Introduce a durable, project-scoped knowledge layer shared across SAIPEN-compatible agents and tools.

The layer would compile useful historical evidence from sessions, audits, project state, decisions, lessons, rules, and documentation into small maintained knowledge pages with explicit provenance and revision history.

Its purpose is not to preserve entire conversations or recreate live sessions.

Its purpose is to answer:

> What has this project already learned, why do we believe it, and is it still true?

## TARGET ARCHITECTURE

Conceptual flow:

Source history
→ discovery
→ evidence extraction
→ provenance
→ candidate knowledge
→ verification
→ canonical project knowledge
→ indexed retrieval
→ agent context

Possible project-local shape:

```text
.saipen/
  STATE.md
  BOARD.md
  LOG.md

  knowledge/
    index.md
    decisions/
    workflows/
    lessons/
    concepts/
    architecture/
    sources/

  provenance/
    sources.jsonl
    pages.jsonl

  staging/
    candidates/
    conflicts/
```

Exact structure is intentionally undefined until implementation is authorized.

## CORE PRINCIPLES

### 1. KNOWLEDGE IS NOT AUTHORITY

Historical conversations, audits, rules, skills, and knowledge pages are reference material.

They must never override:

* the current user request;
* active system or tool instructions;
* current project state;
* newer verified decisions.

Retrieval provides context, not command authority.

### 2. SOURCES REMAIN SEPARATE FROM COMPILED KNOWLEDGE

Original evidence must remain distinguishable from derived summaries.

Agents should be able to move from:

```text
knowledge claim
→ provenance record
→ original evidence
```

without treating generated summaries as primary evidence.

### 3. PROJECT-SCOPED RETRIEVAL

Do not inject the complete knowledge store into every session.

Resolve the active project and task first, then retrieve only a small relevant subset.

Preferred retrieval order:

```text
current project state
→ relevant maintained knowledge
→ original evidence when needed
```

### 4. PROVENANCE FOR CONSEQUENTIAL KNOWLEDGE

Important claims should retain enough provenance to determine:

* source identity;
* source type;
* source date;
* capture date;
* relevant range or locator;
* source revision;
* verification status;
* supersession relationships.

Missing provenance must remain explicitly missing.

### 5. REVISION INSTEAD OF SILENT REPLACEMENT

Knowledge must support:

```text
ACTIVE
SUPERSEDED
DISPUTED
STALE
UNVERIFIED
```

A later decision should supersede an earlier decision rather than silently erase it.

Historical reasoning remains available while retrieval prefers the active revision.

### 6. CURRENT FACTS REQUIRE CURRENT VERIFICATION

Historical knowledge must not automatically be treated as current truth.

Examples:

* installed versions;
* active branch;
* open issues;
* runtime behavior;
* deployment state;
* provider capabilities;
* model availability.

Agents should verify mutable facts against live project state before relying on them.

## POSSIBLE SAIPAL ROLE

SAIPAL may eventually act as the discovery and verification layer.

Potential flow:

```text
inspect sessions and project history
→ detect reusable knowledge candidate
→ locate supporting evidence
→ compare with existing knowledge
→ detect contradiction or supersession
→ propose knowledge change
```

SAIPAL should not silently promote discovered material into canonical knowledge.

Default behavior should be proposal-first.

## KNOWLEDGE CANDIDATES

Good candidates include:

* architectural decisions;
* verified failure modes;
* recurring debugging lessons;
* tested operational workflows;
* important project conventions;
* rejected approaches and their rationale;
* compatibility constraints;
* verified integration behavior;
* stable terminology;
* important historical migrations.

Bad candidates include:

* temporary task chatter;
* speculative ideas presented as facts;
* raw chain-of-thought;
* duplicated summaries;
* transient runtime output;
* credentials or secrets;
* information unrelated to the project;
* facts that can be cheaply obtained from authoritative live state.

## CONFLICT HANDLING

Contradictory evidence must remain visible.

Example:

```text
DEC-0042
Queue dispatch occurs immediately.

Status: SUPERSEDED

Superseded by: DEC-0067
Reason: turn barrier introduced after verified race condition.
```

Conflicting evidence without a confirmed resolution should remain:

```text
Status: DISPUTED
```

The system must not manufacture consensus.

## RETRIEVAL CONTRACT

A future agent requesting project context should ideally receive:

```text
1. Current operational state
2. Relevant active decisions
3. Relevant verified lessons/workflows
4. Known contradictions or stale claims
5. Provenance pointers
```

Original conversation retrieval should remain available for exact wording, chronology, and deeper investigation.

The maintained knowledge layer should optimize for compressed reusable understanding.

## SAFETY / CONSISTENCY REQUIREMENTS

Any implementation must provide protection against:

* simultaneous writers;
* duplicate compilation;
* stale retrieval indexes;
* circular or broken provenance;
* project-scope leakage;
* accidental global promotion of local rules;
* silent supersession;
* generated knowledge citing generated knowledge recursively;
* deletion of historical evidence when only the visible page was removed.

Canonical writes should use a single-writer, lock, compare-and-swap, revision, or equivalent consistency mechanism.

## NON-GOALS

This gate does NOT authorize:

* a general-purpose personal memory system;
* automatic import of every historical conversation;
* cloud synchronization;
* replacement of STATE / BOARD / LOG;
* autonomous modification of project rules;
* loading the entire knowledge base into every agent;
* direct editing of external tools' internal databases;
* implementation of a graph database merely because graph databases exist.

Markdown plus structured metadata should remain the default until scale proves it inadequate.

## ENTRY CONDITIONS

Do not activate this gate until most of the following are true:

* SAIPEN operational state contracts are stable;
* SAIPAL session inspection is reliable;
* project identity is consistently resolvable;
* source/session identity can be referenced reliably;
* current-state retrieval is trustworthy;
* concurrency and write ownership are understood;
* there is measurable repeated context loss across agents;
* maintaining compiled knowledge provides more value than reading source history directly.

## FIRST IMPLEMENTATION SLICE

If this gate is activated, begin narrowly.

Recommended first slice:

```text
ONE PROJECT
ONE KNOWLEDGE TYPE: decisions
ONE SOURCE TYPE
ONE WRITER
MANUAL APPROVAL
NO BACKGROUND AUTOMATION
```

Demonstrate:

1. Discover one historical decision.
2. Preserve its original evidence.
3. Compile one canonical decision page.
4. Retrieve it from a fresh agent session.
5. Supersede it with a newer verified decision.
6. Confirm retrieval prefers the new decision while preserving the old one.
7. Confirm deletion or failure does not corrupt original evidence.

Do not expand scope until this vertical slice is proven.

## SUCCESS CRITERION

The feature is valuable only if a fresh agent can enter an established project and recover important verified context faster and more accurately than by searching raw history manually.

The target is not:

> "The agent remembers everything."

The target is:

> "The agent can reliably recover the small amount of historical knowledge that matters now."

## FUTURE DESIGN QUESTION

If this gate is eventually activated, evaluate whether the canonical owner should be:

* SAIPEN Core;
* SAIPAL;
* a dedicated knowledge subsystem;
* or a separate future agent.

Do not decide this prematurely.

Keep the knowledge format portable enough that ownership can change without rewriting the knowledge itself.

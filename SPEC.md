# Agent Session Protocol (ASP) Specification

## Abstract
**Design Goal #1: A cold agent with zero chat history must be able to execute `/asp continue` and resume productive work within one minute, without asking the user to repeat context.**

ASP is a portable, file-backed continuation protocol for LLM agents. Implementations MAY vary. The on-disk contract MUST remain stable. Everything in this protocol exists to serve the Continuation Test.

- **`STATE`**: Exists to answer *"What do I do right now?"*
- **`BOARD`**: Exists to answer *"What task am I picking up?"*
- **`LOG`**: Exists to answer *"Why did we come to this point?"*
- **`KNOWLEDGE`**: Exists to answer *"What is the durable truth of this project?"*
- **`next_action`**: The heart of ASP. It answers *"What exact command do I execute right this second to resume work?"*

## Architecture

The protocol is strictly normative. We explicitly separate the **Core Protocol** from **Adaptive Extensions**.

```text
asp/                   <- THE CORE (distributable unit)
  PROTOCOL.md               normative core specification (MUST/SHOULD/MAY)
  phases/                   strict state machine logic
    validate.md             conformance testing
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md
    hunt.md / done.md / blocked.md

extensions/                 <- THE ADAPTIVE LAYER
  adapters/                 per-model instruction bridges
  schemas/                  canonical file schemas
  templates/                fresh .asp/ boilerplate
  security/                 security scanning hooks
  performance/              performance benchmark hooks

tests/                      <- CONFORMANCE LAYER
  validate.ps1 / .sh        protocol self-check validator
  scenarios/                mock states (crash-recovery, claim-conflicts, etc.)
```

## Two-Way Capability Negotiation
Agents do not simply declare what they can do; the protocol demands what is required.
The project defines `requires: [filesystem, git, python]` in its state. The agent cross-references its host capabilities and locks into a `mode` (e.g., `full`, `read-only`).

## Graph-Based Event Logging
Logs in ASP are not linear strings. They form an acyclic graph of decisions using Event IDs (`E-001`). This permits complex branching, agent merging, and precise audit trails.

## Architecture Decision Records (ADR)
Transient event logs do not house permanent knowledge. ASP mandates that structural architectural decisions are persisted as ADRs (e.g., `KNOWLEDGE/ADR-001-use-sqlite.md`).

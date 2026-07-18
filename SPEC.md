# SAIPEN Specification

## Abstract
**Design Goal #1: A cold agent with zero chat history must be able to execute `/saipen continue` and resume productive work within one minute, without asking the user to repeat context.**

SAIPEN is an engineering operating model for autonomous software maintenance. At its core, it uses a portable, file-backed continuation protocol for LLM agents. Implementations MAY vary. The on-disk contract MUST remain stable. Everything in this protocol exists to serve the Continuation Test.

SAIPEN is evolutionary, not creative. Its purpose is to complete software, not reinvent it. ADD extends existing design patterns, industry conventions, and obvious feature symmetry.

- **`STATE`**: Exists to answer *"What do I do right now?"*
- **`BOARD`**: Exists to answer *"What task am I picking up?"*
- **`LOG`**: Exists to answer *"Why did we come to this point?"*
- **`KNOWLEDGE`**: Exists to answer *"What is the durable truth of this project?"*
- **`next_action`**: The heart of SAIPEN. It answers *"What exact command do I execute right this second to resume work?"*

## Architecture

The protocol is strictly normative. We explicitly separate the **Core Protocol** from **Adaptive Extensions**.

```text
saipen/                   <- THE CORE (distributable unit)
  RFC.md                    normative core specification (MUST/SHOULD/MAY)
  phases/                   strict state machine logic
    validate.md             conformance testing
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md
    hunt.md / done.md / blocked.md

extensions/                 <- THE ADAPTIVE LAYER
  adapters/                 per-model instruction bridges
  schemas/                  canonical file schemas
  templates/                fresh .saipen/ boilerplate
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
Logs in SAIPEN are not linear strings. They form an acyclic graph of decisions using Event IDs (`E-001`). This permits complex branching, agent merging, and precise audit trails.

## Architecture Decision Records (ADR)
Transient event logs do not house permanent knowledge. SAIPEN mandates that structural architectural decisions are persisted as ADRs (e.g., `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Concurrency & Distribution Boundaries
SAIPEN ensures state integrity via file-based claims (`owner`, `claim_time`) and sequential graphs (`LOG.md`). However, **SAIPEN is a state protocol, not a distributed consensus algorithm.**
- **Local/Shared Filesystem**: Conflict resolution relies on atomic filesystem writes ("first commit wins").
- **Networked/Distributed Environments**: If agents operate across disconnected machines without real-time file syncing, race conditions on `BOARD.md` claims will occur. In highly distributed setups, SAIPEN MUST remain immutable, but a thin **Coordinator/Server Layer** SHOULD be built *on top* of SAIPEN to broker atomic locks before pushing state to the agents.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

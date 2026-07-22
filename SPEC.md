# SAIPEN Specification

## Abstract
**Design Goal #1: A cold agent with zero chat history must be able to execute `/saipen continue` and resume productive work within one minute, without asking the user to repeat context.**

SAIPEN guarantees that any compatible AI agent can safely continue any project without being rebriefed. It is an ABI (Application Binary Interface) for engineering AI agents—a compatibility layer that solves the amnesia problem. Whether you use Claude today, Gemini tomorrow, and GPT the day after, they will all operate against the same project state without requiring you to restate context.

### Core Philosophy: Project State > Model Memory
Memory should live next to the code, not inside the head of another model. SAIPEN shifts the paradigm from `Project -> Memory -> LLM` to `Project -> SAIPEN State -> LLM`. The memory belongs to the project.

At its core, SAIPEN uses a portable, file-backed continuation protocol for LLM agents. Implementations MAY vary. The on-disk contract MUST remain stable. Everything in this protocol exists to serve the Continuation Test.

SAIPEN is evolutionary, not creative. Its purpose is to complete software, not reinvent it. ADD extends existing design patterns, industry conventions, and obvious feature symmetry.

- **`STATE`**: Exists to answer *"What do I do right now?"*
- **`BOARD`**: Exists to answer *"What task am I picking up?"*
- **`LOG`**: Exists to answer *"Why did we come to this point?"*
- **`KNOWLEDGE`**: Exists to answer *"What is the durable truth of this project?"*
- **`next_action`**: The heart of SAIPEN. It answers *"What exact command do I execute right this second to resume work?"*

## The SAIPEN Litmus Test

Any proposed change or new idea for the protocol MUST pass the following three questions:
1. Does it make the transition between agents more reliable?
2. Does it make the behavior of different models more uniform?
3. Does it reduce the probability of context loss?

If the answer is "no" to at least two of these questions, the idea is rejected. SAIPEN prioritizes discipline, reproducibility, and reliability over novelty.

## Architecture

The protocol is strictly normative. SAIPEN conceptually divides into two layers: **Core** and **Maintenance**. 
- **The Core layer** guarantees safe, vendor-neutral task continuation. 
- **The Maintenance layer** is an autonomous software evolution model built on top of Core.

Underneath the two layers, SAIPEN separates three concerns that never entangle:
**correctness and continuation** (Core -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, capability
negotiation, checkpointing), **unattended evolution** (Maintenance -- `HUNT`/`ADD`/`CLEAN`,
fully functional under the plain `saipen`/`saipen continue` default), and **throughput**
(Goal Mode, Subagents -- both explicitly opt-in, §1.3/§2.4). Disable Goal Mode: the
protocol is unchanged, one ticket at a time. Disable Subagents: `HUNT` runs the same
six categories sequentially, same result. Use Core alone, with no Maintenance layer at
all: it still holds -- a cold agent still resumes correctly. Each layer builds on the
one beneath without the reverse ever being true; nothing upstream depends on a
downstream feature existing.

```text
saipen/
  RFC.md                    normative specification (divided into Core and Maintenance)
  CONFORMANCE.md             self-check vectors + scenario coverage table
  SKILL.md                  thin entry point for skill-reading platforms
  STYLE.md                  voices: chat, LOG.md, artifacts
  UI.md                     Dark Golden Win95 UI spec (mandatory for UI work)
  phases/                   strict state machine logic
    [Core Phases]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Maintenance Phases]
    hunt.md / add.md / clean.md / translate.md
    
    validate.md             conformance testing

extensions/                 <- THE ADAPTIVE LAYER
  adapters/                 per-model instruction bridges, for platforms the
                             injector doesn't auto-detect (README.md points here)
  schemas/                  state.schema.json is machine-read by tools/validate.py
                             (single source of truth for STATE's shape); board/log
                             schemas stay reference-only (see schemas/README.md)
  templates/                fresh .saipen/ boilerplate
  security/                 EXAMPLE hook to copy into a project (RFC § 1.9, attaches to VERIFY)
  performance/              EXAMPLE hook to copy into a project (RFC § 1.9, attaches to REVIEW)
  subs/                     EXAMPLE read-only research subagents (RFC § 1.9) -- own
                             STATE/BOARD/LOG per subagent, findings only via OUTBOX,
                             never a second write-path into the project

bootstrap/                  <- INSTALL/EXPORT/UNINSTALL, one machine at a time
  inject.ps1 / .sh          installs the SAIPEN block + skill copies (README Quick Start)
  uninstall.ps1 / .sh       reverses inject -- removes blocks + skill copies
  export.ps1 / .sh          archives a project's .saipen/ for backup

tools/                      <- CANONICAL VALIDATOR & REPO UTILITIES
  validate.py               canonical conformance validator (stdlib Python, zero
                             installs; validates STATE against state.schema.json
                             directly, plus graph checks the shell pair can't do)
  install_hook.py           installs a pre-commit hook running validate.py
  uninstall_hook.py         removes exactly that hook (restores any prior one)

tests/                      <- CONFORMANCE LAYER
  validate.ps1 / .sh        frozen portable floor for hosts without Python --
                             new checks land only in tools/validate.py
  scenarios/                mock states (crash-recovery, claim-conflicts, etc.)
```

## Two-Way Capability Negotiation
Agents do not simply declare what they can do; the protocol demands what is required.
The project defines `requires: [filesystem, git, shell, python]` in its state. The agent cross-references its host capabilities and locks into a `mode` (e.g., `full`, `read-only`).

## Graph-Based Event Logging
Logs in SAIPEN are not linear strings. They form an acyclic graph of decisions using Event IDs (`E-001`). This permits complex branching, agent merging, and precise audit trails.

## Architecture Decision Records (ADR)
Transient event logs do not house permanent knowledge. SAIPEN mandates that structural architectural decisions are persisted as ADRs (e.g., `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Concurrency & Distribution Boundaries
SAIPEN ensures state integrity via file-based claims (`owner`, `claim_time`) and sequential graphs (`LOG.md`). However, **SAIPEN is a state protocol, not a distributed consensus algorithm.**
- **Local/Shared Filesystem**: Conflict resolution relies on atomic filesystem writes ("first commit wins").
- **Networked/Distributed Environments**: If agents operate across disconnected machines without real-time file syncing, race conditions on `BOARD.md` claims will occur. In highly distributed setups, the SAIPEN on-disk protocol contract MUST remain stable -- project state itself still mutates constantly, through SAIPEN's own rules (§ 1.5 checkpointing), never the protocol shape those rules follow.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

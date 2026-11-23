# SAIPEN FUTURE ARCHITECTURE

STATUS: ARCHITECTURE SEED  
IMPLEMENTATION: NOT STARTED  
CANONICAL WORK: NONE  
AUTO-INGEST AS WORK: NO  
MAY SPAWN FUTURE GATES: YES

## Purpose

This directory preserves architecture-level ideas that are too large to be one ticket or one FUTURE GATE.

A document here is NOT an instruction to start implementation.

A document here must not alter:

- current project priority,
- current `next_action`,
- BOARD / STATE / LOG truth,
- ticket ownership,
- seat ownership,
- operator authority.

Architecture seeds exist to preserve design intent until SAIPEN is ready to convert a bounded slice into an explicit FUTURE GATE.

## Separation

Use:

- `future_architecture/` for cross-cutting architecture directions,
- `future_gate/` for bounded future capabilities with acceptance criteria,
- `.saipen/` for current canonical project truth and executable work.

Do not promote an architecture seed directly into active Work.

Preferred promotion path:

    ARCHITECTURE SEED
        -> bounded design decision
        -> FUTURE GATE
        -> accepted activation conditions
        -> Source / Work
        -> implementation

## Current architecture family

Primary seed:

    Global Project Dispatcher / Multi-Project Agent Slot Broker

It connects five concepts without collapsing them into one subsystem:

    Portfolio Context
        what deserves attention

    Project Registry
        where projects exist

    Local SAIPEN
        what is legally actionable inside each project

    Global Lease Broker
        who may mutate which project now

    Dispatcher
        which free worker gets which eligible project

OpenCode / model runtimes then become generic workers instead of manually assigned project windows.

## First safety rule

Initial implementation should assume:

    ONE LIVE MUTATING LEASE PER PROJECT

Multi-worker mutation inside the same repository is deliberately deferred.

## Related future capability

Expected related gate:

    ../future_gate/FUTURE GATE — OPTIONAL PORTFOLIO CONTEXT PROVIDER_20260918.md

That gate supplies advisory portfolio priority.

It is not the dispatcher itself.

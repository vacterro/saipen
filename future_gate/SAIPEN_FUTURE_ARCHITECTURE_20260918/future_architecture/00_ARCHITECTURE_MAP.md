# ARCHITECTURE MAP

STATUS: ARCHITECTURE SEED

## System view

    Human / Operator
            |
            v
    Portfolio Intent Provider
    (optional, e.g. AUDAPACK)
            |
            v
    +----------------------+
    | Global Dispatcher    |
    +----------------------+
       |       |       |
       v       v       v
    Worker A Worker B Worker C ...
       |       |       |
       +-------+-------+
               |
               v
        Global Lease Broker
               |
               v
        Project Registry
               |
               v
      Per-project SAIPEN Core
               |
               v
        STATE / BOARD / LOG /
        intake / lifecycle /
        local next action

## Responsibility boundaries

### Portfolio provider

Answers:

    Which projects currently deserve more or less attention?

Must not grant execution authority.

### Project registry

Answers:

    Which project IDs exist?
    Where is each root?
    What lineage identifies it?
    Is the registration current?

Must not decide local lifecycle truth.

### Local SAIPEN

Answers:

    What is true inside this project?
    What is the legal local next action?
    Is Work blocked?
    Does this session hold valid authority?

Must remain usable without a global dispatcher.

### Global lease broker

Answers:

    Which worker currently owns the right to mutate this project?

Must make acquisition atomic.

### Dispatcher

Answers:

    Given free worker capacity, which eligible unleased project should be assigned now?

Must not silently reinterpret an explicit project request.

### Worker runtime

Examples:

    OpenCode
    Codex
    other supported agent host

Worker executes the assignment. It is not the owner of portfolio policy.

## Core equation

    GLOBAL ELIGIBILITY
        =
    LOCAL ACTIONABILITY
        AND
    GLOBAL LEASE AVAILABILITY
        AND
    SCHEDULER POLICY

Optional portfolio priority may influence ordering.

It must not create local actionability.

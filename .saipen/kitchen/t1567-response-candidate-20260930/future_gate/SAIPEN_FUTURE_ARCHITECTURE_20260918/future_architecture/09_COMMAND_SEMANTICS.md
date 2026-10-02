# FUTURE COMMAND SEMANTICS

STATUS: DESIGN SEED ONLY  
COMMANDS ARE NOT IMPLEMENTED

## Explicit project request

    saipen start AUDAPACK

Meaning:

    locate registered AUDAPACK
    validate identity
    attempt lease
    enter that project
    execute its legal local start/continue route

If occupied:

    return conflict

Do not substitute another project.

## Generic dispatcher

    saipen dispatch

Meaning:

    find eligible candidate set
    rank according to policy
    atomically acquire one
    return assignment

## Pool-constrained dispatch

    saipen dispatch --pool MAIN0

Meaning:

    same as generic dispatch
    but filter to the named external scheduling pool/policy class

The command must not require literal AUDAPACK lane names in Core.

## Continuous mode

    saipen dispatch --continuous

Meaning:

    dispatch
    work until real local stop
    release
    dispatch again

## Read-only inspection

Possible future commands:

    saipen projects
    saipen workers
    saipen leases
    saipen dispatch status

These names are placeholders.

Do not reserve CLI syntax until the relevant FUTURE GATE is activated.

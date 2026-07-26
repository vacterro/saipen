Test: Agent should detect a cyclic `needs:` dependency, move every ticket in the cycle to `## BLOCKED` with a `dependency cycle` blocker note, and keep working other unblocked tickets instead of stalling.

expect: fail

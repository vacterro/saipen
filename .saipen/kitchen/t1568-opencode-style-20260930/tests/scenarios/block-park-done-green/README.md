Test: canonical `ticket block` on the ACTIVE ticket moves the line to
`## BLOCKED` and parks the execution state at DONE/task none with
transition_from = the actual mid-flight phase (BUILD here). The DFA has no
DONE edge from BUILD and session-level BLOCKED would be a lie whenever other
work is workable, so the block is the one documented transitional shape that
produces this state. The active LOG's most recent ticket event is the
canonical SAIOPS `ticket block via SAIOPS (active)` line -- the `(active)`
marker proves this was a DOING-ticket block, the event is structurally valid
and `[op:]` provenanced, it names T-001 which sits in `## BLOCKED`, and that
evidence is what legitimizes the edge.


expect: pass

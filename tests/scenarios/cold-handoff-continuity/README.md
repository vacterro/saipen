# SC-CONTINUITY-001 -- canonical cold-handoff recovery scenario

Test: The Work survives the death of the Attempt that was executing it.
Agent A claims T-001, opens attempt A-001, then stops (simulated context
limit). Agent B -- a COLD process with zero chat history from A -- resumes
from repository state alone via `saipen brief`, opens A-002 on the SAME
Work, drives it through VERIFY/REVIEW/SHIP to a verified completion.
Agent C independently re-checks the finished Work with the validator.

Deterministic: both agents are mock identities driving the real engine
CLI; no model, network, or provider participates.

expect: pass

expect: fail
expect_fail_contains: STATE is behind BOARD

Test: the opposite checkpoint interruption -- BOARD moved a self-claimed
ticket (T-100, owner probe) into ## DOING while STATE still reads task: none.
This is the "BOARD ahead of STATE" crash from RFC section 1.5; Recovery adopts
the BOARD claim, and until it does the state is a contradiction. A stranger's
## DOING claim with task: none stays valid (multi-agent-claim-conflict) --
only a claim by this agent or an unclaimed one must be mirrored in STATE.

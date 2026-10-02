<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: recovery repairs, downstream project reports, reconcile, regression fixtures
trigger: fixing a recovery or reconcile defect from a report that describes a stranded downstream project
status: active
evidence: T-1574, SRC-149, tools/test_t1572_ticket_scoped_recovery.py RealDownstreamShapeTests, .saipen/evidence/T-1574-three-reports/audapack-real-copy.txt
supersedes: none

# A reported downstream shape is a hypothesis about bytes

Prove a recovery fix against a scratch copy of the real project's `.saipen/`, not only against the fixture the report describes; the bytes, not the report, decide the shape.

Why:
SRC-149 described AUDAPACK T-261 as canonical SCOUT/BUILD/VERIFY transitions with no SHIP. The real journal held only a canonical claim followed by hand-written `RUN:` lines under invented op ids, plus an unknown `evidence:` BOARD field. The fixture-based repair passed every test and still left the real project RECOVERY_BLOCKED twice: once because no tagged transition existed (a claim alone proves SCOUT), once because the reopened row kept a field outside the closed grammar. Copying the real `.saipen/` into a scratch git repo and running `recover`, the named route, `validate`, `recover` and `continue` found both in minutes without touching the real project.

How to apply:
- Copy the downstream `.saipen/` into the scratchpad, `git init`, commit, and run the canonical verbs there.
- Turn the real shape into a regression beside the report's fixture; keep both.
- Never apply the repair to the real project unless its operator asks.

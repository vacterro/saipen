<!-- SAIPEN FUTURE GATE v1 -->
id: FG-0052
title: Architectural Simplification and Causal Self-Recovery
state: DEFERRED
priority: P1
basis: measured
estimate: 1
slice: TODO -- name the ONE bounded unit this gate may promote
needs: none
evidence: future_gate/SAIHANDOFF — SAIPEN_20261024_1647.md

# Architectural Simplification and Causal Self-Recovery

Operator handoff 2026-10-24 (future_gate/SAIHANDOFF — SAIPEN_20261024_1647.md, 18613 bytes) recorded as a deferred target and NOT as Work. Registration only; the proposal is preserved in that document and is not duplicated here.

CORE OBJECTIVE. Replace the growing collection of incident-specific refusal rules, fallback loops and manual recovery requirements with a smaller set of enforceable system invariants, causal ownership relations, typed lifecycle facts and mechanically provable recovery operations. SAIPEN should detect unfamiliar but structurally recognizable failures, reason over canonical evidence, and recover automatically when safety can be proven -- without a new hardcoded workaround per agent mistake, and without remaining secure only because the model happens to behave.

PROPOSED SHAPE (from the handoff, unratified). Typed blocker records carrying owner, scope and causality instead of free-text heads; a causal ownership graph so an unrelated blocked ticket cannot veto recovery; transactional STATE mutation with a journal-derived projection so crash recovery cannot recreate a stale field; recovery plans expressed as provable pre/post conditions rather than prose refusals.

WHY IT IS DEFERRED. The two incidents that motivated it were repaired narrowly and verifiably instead: T-1883 (reconcile causal classification) and T-1884 (transition must not inherit an unowned blocker). Those fixes are measured, regression-covered and stay authoritative. A whole-system redesign on top of them, before the current publication and verification-identity defects are settled, would trade proven behaviour for unproven behaviour. INV-16 forbids promoting this gate as a side effect of anything else.

NOT AUTHORIZED BY REGISTRATION: implementation, promotion, a new ticket, or any change to the active execution objective.

Deferred authority candidate. Not Work, not a rule source, not
implementation authority until `saipen future promote`.

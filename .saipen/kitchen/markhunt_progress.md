# MARKHUNT progress cursor (overwrite-only, not history)

run: 2026-07-23T20:35Z | agent: opus (this session)
input: user-supplied 12-gap + 5-contradiction audit, cross-checked against live canonical files (saipen/RFC.md + all 16 phases + extensions/subs/PROTOCOL.md + VERSION)

## Scope covered (exhausted)
- RFC.md §1.1-§2.4: read whole
- phases/: done, hunt, verify, review, markhunt, blocked, prepare, translate, clean, plan, validate -- read whole
- extensions/subs/PROTOCOL.md -- OUTBOX/collect path confirmed
- VERSION = 7.50.0 present
- skill-copy vs canonical: diff-clean (RFC + 12 phases identical)

## Verdict: 4 real (recorded T-149..T-152), 8 false/already-fixed (rejected, not boarded)

REAL:
- T-149 P2 goal_tickets = verify-passes not tickets (verify.md:63 vs RFC §2.4:222)
- T-150 P3 saitranslate/STATE.md reaped by no phase
- T-151 P3 kitchen not atomic + no crash-integrity check
- T-152 P3 doc-explicitness cluster x6

REJECTED (evidence):
- #3 claim theft: already fixed v7.30.0, RFC §1.4 mandates 10-min standalone BOARD refresh
- #6 BLOCKED timeout: blocked.md:9 re-scans every entry; clean.md re-checks BLOCKED; command-driven not daemon
- #8 subSaipen OUTBOX orphan: extensions/subs/PROTOCOL.md:114 defines collect at HUNT/continue/`sub collect`
- #11 ext command collision: RFC §1.9:137 already "MUST NOT collide with a §1.10 name"
- #12 PREPARE orphan: external-handoff by design, user-invoked, out-of-band consumer
- #14 bare `saipen goal` resume/pivot: §2.4/§1.10 unambiguous (bare = resume only)
- #15 HUNT->ADD->DONE one tick: documented intended behavior
- #16 WAIT: in plan.md: plan.md:11 scopes the ban to proposal-halt, which is NOT one of §1.2's legal WAIT: gates -- consistent, not contradictory

## Remaining: none -- surface exhausted for this audit's claims

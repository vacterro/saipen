# 03 — WAVE 1: SRC-013 COVERAGE TRUTH REPAIR

## Goal

Make `audit/2.md` Source Coverage truthful before final phase compression.

The native Audit Inbox must never delete an audit merely because old generic evidence claims it is complete.

## Rule

Coverage disposition is a claim that requires clause-specific evidence.

Do not inherit one generic checkpoint sentence across unrelated acceptance criteria.

## W1.1 — Re-audit all 17 clauses

For each `SRC-013:R001..R017`:

classify as:

- VERIFIED with direct evidence;
- IMPLEMENTED with direct evidence;
- DEFERRED with exact Work;
- BLOCKED with exact missing fact;
- or other existing truthful disposition.

If current evidence does not prove a VERIFIED clause, reopen it.

## W1.2 — Mandatory re-open candidates

At minimum re-evaluate:

### R003 — consistent phase structure

Current tree does not satisfy this visibly across all 16 phase docs.

Reopen unless concrete structural validation proves otherwise.

### R010 — narration independence

Add the actual requested regression:

`test_phase_lifecycle_does_not_depend_on_narration`

or equivalent.

Do not use the continue-fallback no-narration test as proof for all phase lifecycles.

### R016 — gates green

Cannot be VERIFIED while core validator is red.

Only close after Wave 0.

### R017 — clean checkout

Only close after actual clean-checkout reproduction.

## W1.3 — Check remaining clauses individually

Particularly inspect:

- R005 universal duplication removed;
- R006 SHIP/VERIFY/REVIEW regression proof;
- R007 maintenance phase boundaries;
- R013 MAINTENANCE duplicated procedure removal;
- R014 stale cross-reference removal;
- R015 active-phase load profiles.

Do not assume they are true because one prior harness was green.

## W1.4 — Bind final compression Work

R008 is the outstanding size criterion.

Do not point it to an impossible single four-file ticket.

Use a parent/child Work structure or final aggregator whose verification matches the source text:

`phase corpus <= approximately 70 KB OR justified variance`.

## Completion bar

1. no unsupported VERIFIED disposition remains;
2. every open clause names exact Work;
3. generic E-4799 evidence is not used as universal proof;
4. Source closure is impossible until the genuinely open clauses close;
5. Audit Inbox sees audit/2 as ACTIVE, not falsely cleanup-eligible.

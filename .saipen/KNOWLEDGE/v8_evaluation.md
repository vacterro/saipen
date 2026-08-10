# v8 evaluation after the repaired foundation (T-613, 2026-08-10)

Decision made ONLY from the repaired foundation (after NITRO dogfood I-IV +
DOGFOOD V provenance integrity), never from historical green claims.

## Fresh evidence (this session, after the dogfood V wave shipped 08d7fee)

- `tools/validate.py --gate core`: PASS, 7 warnings, all owned (goal-reauth-
  untripped T-407, subsaipen-never-ran T-406, log-missing-date immutable,
  producer-package-stale T-609, subsaipen-uncollected, producer-package-stale
  saitranslate/EE).
- `tools/run_scenarios.py`: ALL executable scenarios + injector probes pass.
- `tools/audit_checks.py`: 243/243 checks still go red on their own condition.
- `tools/audit_floor.py`, `audit_order.py`, `audit_tags.py`, `audit_parity.py`
  (243/243 cases): PASS.
- `tools/nitro_integrity_repro.py`: R1..R13 all NOT REPRODUCED -- every claimed
  NITRO defect flipped (fixed); the harness reports "audit claims need
  re-checking", which is the honest fixed state.
- `git diff --check`: clean. Working tree clean, remote synchronized.

## Foundational defect classes closed

- NITRO I: lying mechanical operations (journal/transactions) -- R1..R8.
- NITRO II: composing operations into lies (CAS, claims, recovery) -- R9..R12.
- NITRO III: correct operations composing into a lie (finish laundering the
  transition_from) -- R13.
- NITRO IV: valid final state faking required gates (finish-requires-SHIP).
- DOGFOOD V: valid-looking evidence pointing at the WRONG source/finding/run
  (provenance) -- composite finding identity, exact source_reports, sweep
  pre-write authorization, strict report lifecycle, mechanical manifest,
  real fingerprints, freshness gates, mechanical abort. T-615..T-621 DONE.

## Sequential stability checkpoint

The ordinary sequential release used as the stability checkpoint is the
DOGFOOD V wave itself (08d7fee, 489af86): it completed the full lifecycle
(ADD -> claim -> build -> verify -> review -> ship -> push) without exposing a
new foundational defect. The single self-audit finding (the resolver-race
assertion not recognizing the "already RESOLVED" refusal) was a test bug, not
a protocol defect, and was fixed in-wave.

## Crew/Concurrent backlog (T-442..T-451)

Design lives in KNOWLEDGE/crew-v8-backlog.md. The gate T-442's conditions are
now satisfiable on the repaired foundation: no open foundational P0/P1;
canonical gates green; one ordinary sequential release completed without a new
foundational defect. v8 Concurrent Mode DESIGN/implementation may proceed per
the Crew backlog. T-473 (Rosary collision guard) stays gated on T-442. No Crew
implementation exists yet.

## Open SAICRITIC findings with disposition

- T-609 (producer-boundary): remains honestly BLOCKED on external saiwiki
  producer evidence; Core may trigger the producer but never fabricate it.
- T-473 (held): disposition = held for the Crew concurrency design.
- T-407/T-406 (permanent warning owners): stay live while their slugs warn.

## Next real wave

v8 Concurrent Mode design + implementation per KNOWLEDGE/crew-v8-backlog.md,
gated on T-442. The Improve layer is now mechanically trustworthy enough to
audit that work: a finding that creates canonical work is traceable without
ambiguity through project -> cycle -> seat -> source revision/tree -> run ->
finding -> Core disposition -> reproduction evidence -> canonical ticket ->
fix -> verification, and no unrelated finding with the same local IMP number
can satisfy any link in that chain.

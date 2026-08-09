# SAIPEN Evolution Queue (queued directive)

This is the repository-backed record of the queued evolutionary directive.
It becomes ACTIVE only after two predecessors reach their own DONE contracts:

- A. NITRO / SAIOPS foundation (saipen/OPS.md, KNOWLEDGE/NITRO.md, the
      saipen_engine package, claim/transition/checkpoint operations);
- B. SAICRITIC / self-maintaining `saipen improve` (adversarial
      self-auditor whose findings Core adjudicates and SAIOPS commits).

Until then, DO NOT execute this directive early. The macro order (subject to
fresh evidence, which outranks the roadmap):

1. NITRO / SAIOPS foundation.
2. SAICRITIC / self-maintaining Improve.
3. Real `saipen improve` cycle #1 -> execute its accepted findings.
4. Real cycle #2 -> verify root-cause closure (PREVIOUS_IMPROVEMENT_REGRESSION
   check).
5. One boring sequential stability release (no foundational P0/P1, all gates
   green, no unresolved journals, cold-recoverable).
6. v8 Concurrent Mode foundation ON SAIOPS (reuse ProjectSnapshot, op IDs,
   plan/apply, stale-precondition refusal, journals, recovery, typed results,
   Core writer ownership; no second transaction system).
   - v8-M1: isolation, not speed (workers in isolated workspaces -> proposal /
     OUTBOX -> Core integrates through SAIOPS; no shared main-tree editing).
   - v8-M2: claims / epochs / freshness (stale worker results are STALE, never
     "probably okay").
   - v8-M3: failure containment (worker death, simultaneous completion, Core
     death mid-integration, stale late returns, duplicates, out-of-scope
     writes, restart).
   - v8 real-world soak on actual SAIPEN maintenance; simplify if concurrency
     costs more than it saves.
   - SAICRITIC against v8; fix findings; stable v8 release.
7. v9 resident execution, NOT new governance (SAIPEN stays canonical; runtime
   calls SAIOPS).
   - v9-M1 resident continue (client crash != worker death; worker death !=
     state loss; supervisor restart != duplicate execution).
   - v9-M2 durable queue + scheduler + provider limit-reset resume.
   - v9-M3 retained SubSaipens (retained context != fresh evidence).
   - v9-M4 persistent disposable computational scratch (never canonical).
   - v9-M5 runtime -> Improve evidence bridge.
   - SAICRITIC against complete v9; simplify / delete obsolete machinery.
8. Maintain portability (files canonical, zero/minimal deps, Windows-first,
   no mandatory database/service/runtime for reading a repository).
9. SAIPENVIEW only after engine contracts are stable (UI is a client; never
   duplicates parsers/mutation logic; closing it never owns work).
10. USERPERSON remains advisory (never authorizes new scope / unsafe action /
    protocol override).
11. Version evolution follows proven capability, not roadmap labels.

## Standing rules

- AUTO-QUEUE: when one eligible ticket finishes, checkpoint, select the next
  canonical eligible ticket, continue -- do not ask "should I continue?" when
  protocol state already answers yes. Stop only for human decision gates,
  destructive confirmation, unavailable external resources, architectural
  ambiguity with materially different outcomes, exhausted budget, or an
  undecidable safe next action.
- Before a session limit: checkpoint EARLY (no half operation, no uncommitted
  journal, no ambiguous DOING, exact next_action, evidence in LOG).
- Chat is transport; repository state is continuity. This queue is recorded
  here, not in a chat scrollback.
- Keep foundational protocol-law work serial even after v8; use concurrency
  only for genuinely separable work.
- Keep DELETE/SIMPLIFY first-class at every Improve cycle.
- GLOBAL ANTI-DRIFT: for every proposed architecture change ask what observed
  failure it removes, what work it mechanizes, what dependency it unlocks,
  whether existing machinery solves it, and whether something can be deleted.
- GLOBAL PRIORITY (when uncertain between two eligible improvements): one that
  removes an entire failure class > moves deterministic work out of LLM
  reasoning > reduces sources of truth > improves crash/recovery > strengthens
  evidence > enables later architecture safely > reduces recurring human work >
  simplifies rather than expands.
- OVERRIDE: evidence outranks roadmap. If SAICRITIC or executable evidence
  finds a foundational defect, stop expansion, ticket the root cause, fix it,
  prove it, resume from the nearest valid gate.
- End state: MAXIMUM USEFUL AUTONOMY WITH MINIMUM UNVERIFIED AUTHORITY. If
  normal maintenance still needs a human courier between repository, external
  reviewer, instruction and maintainer -- or a repeated "continue" after
  mechanically obvious checkpoints -- that is remaining automation debt.

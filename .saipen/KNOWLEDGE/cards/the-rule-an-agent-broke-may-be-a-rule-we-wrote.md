<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: incidents where an executor did something the protocol forbids and said so, activation block edits, fallback and degraded-mode clauses in OPS and BOOT, host-facing fixes
trigger: an incident report quoting an agent that "knew" a limitation and worked around it, writing a guard against an agent behaviour, or calling a host-facing fix done
status: active
evidence: T-1672, SRC-193, .saipen/evidence/T-1671-lifecycle-authority/regression_pair.out.txt, .saipen/evidence/T-1671-lifecycle-authority/live_copies.out.txt, saipen/OPS.md, saipen/ACTIVATION_BLOCK.md
supersedes: none

# The rule an agent broke may be a rule we wrote

Before building a guard against something an executor did, search the protocol for the sentence that told it to, and check that the fix it already has reached the host it runs on.

Why:
An executor that could not find `saipen` wrote STATE, BOARD and LOG by hand and reported it plainly. That read as a model rationalising. It was compliance: OPS 8 said that with the engine unavailable an agent uses "the documented manual protocol as compatibility fallback" and states that enforcement was unavailable, OPS 4a called manual structural editing "FALLBACK / RECOVERY ONLY", and the activation block every host receives ordered "checkpoint BOARD + STATE after every ticket, LOG line after every run". A guard added beside those sentences would have left the law and the engine disagreeing. The second half was deployment: the launcher line that would have let that executor reach the engine had been in the tree for two days, and no host had it, because the injector refuses a tree that differs from HEAD (`status` reports `distribution ... BLOCKED DIRTY_SOURCE`) and nothing had been committed since 2026-10-05.

How to apply:
Grep `saipen/*.md` for fallback, degraded and "unavailable" clauses and for imperative lines in ACTIVATION_BLOCK.md that an agent can satisfy by hand; rewrite the licence in place (the protocol markdown has a total byte cap, so a rewrite replaces, it does not append). Then read `saipen status --json` `distribution`: `stale` homes or a `blocker` mean the host still runs the old generation, and a fix that is built and green is not a fix the reported host has. Say which of the two is true when reporting.

## 10. Maturation of a reviewed deferred gate

Refinement answers *"What is this historical record?"*. **Maturation** answers
a different question: *"Can one concrete bounded executable slice be derived
from this already-known deferred intent now?"*. They are separate bounded
Future-layer operations and are never conflated: refinement normalizes an
ambiguous record, maturation prepares ONE reviewed `DEFERRED` gate for the
normal readiness check. Neither is implementation. Neither edits
implementation code. Neither creates authority — `§ 7` promotion stays the
only path into ordinary Work, and readiness is re-evaluated after every
maturation exactly as `§ 4` demands.

### 10.1 Activation policy

`DEFERRED` covers semantically different cases, so every projected gate
carries one machine fact — `activation_policy` — from this closed vocabulary:

| policy | meaning |
| --- | --- |
| `AUTO_WHEN_IDLE` | deferred while ordinary Work exists; may mature automatically once the Future layer owns the seat |
| `CONDITION_BOUND` | may mature only after its named, machine-checkable prerequisites hold |
| `OPERATOR_ONLY` | the record carries an explicit external/manual activation gate that cannot be read as merely "not now" |
| `ARCHITECTURE_SEED` | too broad for direct maturation; at most one bounded child Future Gate (or a bounded planning result) may be derived first |

The policy is derived mechanically from the reviewed record, never guessed:
broad architecture/planning status yields `ARCHITECTURE_SEED`; an explicit
prohibition such as "do not activate this gate until ..." yields
`OPERATOR_ONLY`; machine-checkable prerequisites yield `CONDITION_BOUND`;
everything else — including the historical "RECORDED FOLLOW-UP WORK / NOT
AUTHORIZED FOR IMPLEMENTATION" — yields `AUTO_WHEN_IDLE`, because that phrase
recorded *deferred implementation authority*, not a permanent prohibition. A
reviewed record may pin `facts.activation_policy` explicitly, and an explicit
fact outranks the derivation. Ambiguity stays conservative: a phrase that
cannot be interpreted mechanically classifies to the stronger hold, never to
`AUTO_WHEN_IDLE`.

### 10.2 The maturation rung

When the Future layer owns the seat, no gate is `ELIGIBLE` and no record is
awaiting refinement, continuation classifies the route as
`FUTURE_GATE_MATURATION` (`executable_behavior: MATURE_AND_REROUTE`) and names
ONE deterministic candidate. The route requires **no human**: the host/agent
executes it autonomously by deriving the bounded candidate itself and
persisting it through the canonical command — never by asking the operator to
invent `--slice` / `--evidence`:

    saipen future mature FG-#### [--slice TEXT --evidence PATH[,PATH]]
    saipen future mature FG-#### --reason TEXT        # deterministic no-progress

The machine validates every submitted fact: the gate must be present,
`DEFERRED`, reviewed and allowed by its activation policy, its hard
prerequisites must hold, and evidence paths must exist. A successful
maturation writes machine-owned metadata only (the reviewed record's `facts`
plus the maturation witness), re-runs readiness, and reroutes — the gate
becomes `ELIGIBLE` only if `§ 4` then proves it, and promotion stays ordinary.

Excluded from selection: terminal and promoted gates, `OPERATOR_ONLY` gates,
`CONDITION_BOUND` gates whose prerequisites are still false, gates with an
unresolved promoted slice, and gates whose current document digest and
prerequisite state already carry an unchanged no-progress maturation
witness. Ordering inside the rung is deterministic: explicit `priority:`,
then measured/reproduced basis before speculative, prerequisite-unblocked
records, narrower `estimate:`, older `recorded_at:`, ties on ascending
`FG-####`.

### 10.3 One gate per bounded step, and no spin

Maturation is a queue, not a feature avalanche: ONE gate (or one child slice)
per bounded step. When no truthful bounded slice can be derived, the attempt
records a deterministic no-progress result — gate id, document digest,
prerequisite state, reason — and continuation moves to another candidate or
HUNT. An unchanged no-progress witness suppresses reselection of that exact
gate; any document edit or prerequisite change invalidates the witness and
makes the gate maturable again. A corpus of deferred intent therefore
advances without operator babysitting and without ever looping on one record.

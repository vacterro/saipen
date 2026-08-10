# SAICRITIC -- the self-critique process (T-603)

SAICRITIC is the periodic full self-critique of SAIPEN against the four proof
levels. It is not a separate phase -- it is a real Improve cycle whose seat
role is `critic` and whose subject is the protocol's own mechanical layer.

## What it does

For every claim a wave made (its tickets' `verify:` clauses and the checks
that implement them), classify the proof as:

| Level | Question |
|---|---|
| UNIT | is the operation locally correct? |
| COMPOSITION | does the predecessor/successor chain work? |
| CANONICAL | do the repository invariants validate? |
| GATE | did the REQUIRED semantic/protocol gates actually occur? |

A claim with a missing layer is NOT PROVEN -- record it as such, never PASS.
The permanent invariant: VALID END STATE != PROOF OF REQUIRED PROCESS.

## How it runs

1. Register a real Improve cycle (`cycle_status: active`) with a `critic`
   seat; the report is written like any seat report under
   `.saipen/improve/<cycle>/<seat>/`.
2. The audit targets the wave's mechanical layer: the finish gate, the
   sweep-ticket linkage, the report schema, the reasoning gates, the
   target-aware verifier, the context projection, the command surface.
3. Every finding carries the four-level classification in its `expected/
   actual/evidence` block; a `PROTOCOL_VIOLATION` finding records the
   cross-project recurrence reasoning and the weak-model answer on its
   canonical ticket (IMP-003 spec, T-558).
4. Findings are swept with the normal Core sweep; root-cause dedup produces
   one canonical ticket per root cause.
5. A finding whose subject was ACCIDENTAL_SUCCESS (a wave claim met by luck,
   not by verification) is recorded honestly: either reclassify the gap as a
   real defect (LOGIC_ERROR) or dispose it as unverified -- never flip it to
   PASS in the sweep.
6. The cycle completes (full sweep coverage) and is archived with provenance.

The first SAICRITIC run (T-603) found the register-without-executor defect:
`saipen improve` was registered in the command surface but the CLI had no
executor (IMP-001/IMP-003 -> T-606), and the SubSaipen write boundary was
admission-only, not continuously checked (IMP-002 -> T-607).

# SAICRITIC -- self-critique (T-603)

SAICRITIC periodically audits all SAIPEN mechanical claims through a `critic` Improve seat; it is not a phase.

## What it does

Classify each Work claim and its checks at five ordered levels:

| Level | Question |
|---|---|
| UNIT | Is the operation locally correct? |
| COMPOSITION | Does the predecessor/successor chain work? |
| CANONICAL | Do repository invariants validate? |
| GATE | Did required semantic and protocol gates actually run? |
| PROVENANCE | Does evidence bind the exact source, session, run, finding and result? |

Missing proof is NOT PROVEN, never PASS.
VALID END STATE != PROOF OF REQUIRED PROCESS.
VALID RESULT + VALID PROCESS != VALID EVIDENCE LINK.

## How it runs

1. `saipen improve --role critic --new-seat` registers a real cycle and critic seat, with a report under `.saipen/improve/<cycle>/<seat>/`.
2. Audit the wave's mechanical layer: finish gate, sweep linkage, report schema, reasoning gates, verifier, context projection and command surface.
3. Give each finding the five-level classification in `expected/actual/evidence`. A `PROTOCOL_VIOLATION` records cross-project recurrence reasoning and the weak-model answer on its canonical ticket.
4. Core sweeps findings and deduplicates by root cause, yielding one ticket per cause.
5. ACCIDENTAL_SUCCESS is reclassified as LOGIC_ERROR or disposed as unverified; it is never promoted to PASS.
6. Complete the cycle only with full sweep coverage, then archive it with provenance.

## Permanent lenses

Lenses, not new enums:

- `COMMAND_SURFACE_SPLIT`: declared and executable actions differ.
- `ROLE_LAUNDERING`: critic evidence lacks a critic roster/report role.
- `SESSION_COLLAPSE`: independent workers share one logical seat or report.
- `PROVENANCE_FABRICATION`: runtime or protocol identity is asserted, not captured.
- `ERROR_NORMALIZATION_GAP`: expected contention is structured in one domain but escapes as a traceback in another.
- `EVIDENCE_ADVERSARY`: falsify only a recent green claim's proof linkage while leaving its end state apparently valid. A gate that stays green after a stale fingerprint, wrong seat/source, duplicate identity, missing gate receipt or malformed-but-parseable ledger is a finding, never PASS.

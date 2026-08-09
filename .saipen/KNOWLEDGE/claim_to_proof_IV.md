# Claim-to-proof IV -- GATE INTEGRITY (NITRO dogfood IV, T-602..T-596)

The fourth proof level. The learned hierarchy was UNIT / COMPOSITION /
CANONICAL. Dogfood IV exposes a defect that hierarchy cannot name:

> A mechanically valid final state can still be invalid evidence of the work
> that supposedly produced it.

`finish_ticket` previously wrote `transition_from: SHIP` regardless of the
actual phase, so finishing a ticket from SCOUT/BUILD/VERIFY/REVIEW produced a
syntactically legal `DONE` state whose phase history was fabricated. Final
bytes validated; the gates never ran.

## The four proof levels

| Level | Question | Evidence |
|---|---|---|
| UNIT | is the operation locally correct? | the operation's own red controls |
| COMPOSITION | does the predecessor/successor chain work? | scenario composition controls |
| CANONICAL | do the repository invariants validate? | tools/validate.py on the resulting state |
| GATE | did the REQUIRED semantic/protocol gates actually occur? | journaled transition chain + the finish gate (phase==SHIP) + `[gate-closure]` validator check |

The permanent invariant (T-602):

    VALID END STATE != PROOF OF REQUIRED PROCESS.

Final-state validity alone never proves that a required historical gate ran.
Gate proof needs event/provenance evidence from the append-only LOG, and the
mutator must make skipping the gate mechanically impossible (the engine
refusal), never rely on the validator to spot the omission after the fact.

## Historical skipped-gate closures -- ACCIDENTAL_SUCCESS

The pre-fix finish defect let a ticket be closed from VERIFY without running
REVIEW/SHIP. These closures are recorded as ACCIDENTAL_SUCCESS: their result
may be correct, but their historical closure evidence is incomplete.

| Ticket | Closure event | Phase named | Review/SHIP ran? | Status |
|---|---|---|---|---|
| T-591 | E-2585 `ticket finished via SAIOPS -- completion (from VERIFY)` | VERIFY | no | ACCIDENTAL_SUCCESS -- gate proof incomplete |
| T-594 | E-2594 `ticket finished via SAIOPS -- completion (from VERIFY)` | VERIFY | no | ACCIDENTAL_SUCCESS -- gate proof incomplete |
| T-595 | E-2603 `ticket finished via SAIOPS -- completion (from VERIFY)` | VERIFY | no | ACCIDENTAL_SUCCESS -- gate proof incomplete |

Their historical DONE state is NOT rewritten (append-only). Their diffs and
relevant verification are re-audited with current evidence below; the skipped
lifecycle is never called retrospectively executed.

## Fresh re-verification by current evidence (FINAL, T-596 closure, 2026-08-09)

Independent re-review of the actual diffs + exact relevant verification, run
fresh on the current HEAD (T-602..T-596 wave). The lifecycle column records
the GATE proof that the historical ticket lacked; it does not backdate it.

| Ticket | Diffs reviewed | Relevant verification rerun (fresh) | Result | Gate proof |
|---|---|---|---|---|
| T-591 | closure + router/BOOT wave (6393345, 55f6a84, 541b617, 7b863f2, f12d3b0) | run_scenarios.py fresh: closure controls A-F + public closure probes + router WAIT/BLOCKED precedence probes + `saipen next` action/load pairing | RESULT CORRECT | gate now mechanical: finish requires SHIP; `[gate-closure]` validator check; T-602 gate controls |
| T-594 | conflict resolution + verification-policy wave (2fbd49f, ee9dde1) | run_scenarios.py fresh: conflict inspect/resolve (accept_live/replan) probes + verification-policy registry probes + IMP-IMP-001 sweep writer probes | RESULT CORRECT | gate now mechanical: `verify_improve(root, targets)` shared by APPLY + Recovery; resolver lock (T-601) |
| T-595 | improve writer/parser/lifecycle wave (dc08713, 1c7077f) | run_scenarios.py fresh: improve writer->parser->derive_status end-to-end probes + cycle lifecycle probes + completion-prerequisite probes | RESULT CORRECT | gate now mechanical: complete_cycle sweep-coverage requirement (T-601) |

The three historical closures remain ACCIDENTAL_SUCCESS for GATE proof (their
REVIEW/SHIP lifecycle was bypassed); the RESULT layer is re-proven correct by
the fresh suite above, and the GATE layer is now mechanically enforced for all
new closures.

## Dogfood IV wave proof (T-602 / T-601 / T-600)

Every claim below was produced fresh THIS wave; no result was reused from
historical evidence.

| Ticket | Claim | Direct (UNIT) | Composition | Canonical | Gate |
|---|---|---|---|---|---|
| T-602 | finish refuses every non-SHIP closure; transition_from is actual | gate controls A/B/C zero-bytes + ILLEGAL_PHASE; mutation red-control | full-chain control D validator-green; valve-mid-ticket control | validate.py PASS | finish-requires-SHIP + `[gate-closure]` validator check |
| T-601 | complete_cycle requires sweep coverage; target-aware verifier; resolver serialized | lifecycle REFUSE/COMMITTED controls; malformed-SWEEP verifier red control; recovery same-verifier control | next-cycle-admitted control; resolver two-process race | validate.py PASS | complete_cycle sweep-coverage gate; APPLY/Recovery one verifier class |
| T-600 | context metrics describe the emitted surface; mandatory sections never cut | byte identity (Cyrillic+Japanese) exact; truthful board-map cap | real-shape small-budget fixture keeps routed action/ticket/needs/verify/phase-doc/recovery | validate.py PASS | n/a (read-only projection; no workflow gate) |

Full wave gates: run_scenarios.py green (168 nitro-integrity + 49 improve +
all fixtures), tools/validate.py PASS, tools/audit_checks.py 231/231,
audit_floor + audit_order + audit_tags green, R1..R13 repro all NOT
REPRODUCED.

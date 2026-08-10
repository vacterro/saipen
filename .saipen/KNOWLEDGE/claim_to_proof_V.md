# Claim-to-proof V -- PROVENANCE INTEGRITY (NITRO DOGFOOD V, T-615..T-618)

The fifth proof level. The learned hierarchy was UNIT / COMPOSITION /
CANONICAL / GATE. Dogfood V exposes a defect that hierarchy cannot name:

> Valid-looking evidence can point at the WRONG source/finding/run and still
> authorize canonical work.

A ticket can inherit truth from a vaguely matching finding: the validator
resolved `source_reports: IMP-001` by substring search, so any IMP-001 in any
archived cycle satisfied provenance; `derive_status` counted one bare sweep
disposition as coverage for every finding sharing a local IMP number; and
`write_sweep_entry` committed a disposition naming a report, run and finding
that did not exist.

## The five proof levels

| Level | Question | Evidence |
|---|---|---|
| UNIT | is the operation locally correct? | the operation's own red controls |
| COMPOSITION | does the predecessor/successor chain work? | scenario composition controls |
| CANONICAL | do the repository invariants validate? | tools/validate.py on the resulting state |
| GATE | did the REQUIRED semantic/protocol gates actually occur? | journaled transition chain + finish gate + `[gate-closure]` check |
| PROVENANCE | does the evidence unambiguously identify the exact source/run/finding/result it claims? | exact composite finding refs, no substring resolution |

PROVENANCE is distinct from GATE: a process may have run every required gate
and still cite the wrong IMP-001.

The permanent invariant (T-615):

    VALID RESULT + VALID PROCESS != VALID EVIDENCE LINK.

Exact provenance is part of correctness.

## The canonical composite finding reference

`<cycle_id>/<seat_id>/<report_path>#<RUN-N>/<IMP-NNN>`.

One representation everywhere: report parser, SWEEP writer, SWEEP parser,
`derive_status`, `complete_cycle`, the validator and BOARD `source_reports`
resolution. Two RUNs may both carry IMP-001; they are different findings. One
cycle's IMP-001 never satisfies another cycle's ticket provenance. No bare
IMP-### substring is ever canonical cross-artifact provenance.

## The one structured sweep record

`SweepRecord(finding_ref, disposition, reproduced, ticket, fixed_by,
verification)` is the single grammar owner for SWEEP.md. The writer, parser,
`derive_status`, the validator and ticket provenance consume the same record;
nobody reconstructs ledger semantics with unrelated regexes.

## The write-time authorization gate

`write_sweep_entry` validates BEFORE write: cycle active, report registered
and complete, run exists, finding exists in that exact run, disposition and
reproduced values legal, disposition/ticket relation legal, and a CONFIRMED
disposition names a canonical ticket that exists on the board or in the LOG.
Fictional reports/runs/findings/tickets can never COMMIT.

## The completion bar

`complete_report` and `complete_cycle` run the FULL report validation first:
valid header, at least one explicit `## RUN N` (or an explicit `NO_FINDINGS`
run) for strict cycles, every finding with its composite identity and its
expected/actual/evidence triple, and exact composite sweep coverage. A report
containing only `report_status: complete` refuses.

## Legacy evidence boundary (2026-08-10)

The three historical cycles `imp-saipen-20260810-1/2/3` are immutable
historical evidence, byte-stable. Their evidence schema is recorded as LEGACY
/ weaker than the strict boundary:

- duplicate roster header (`# IMPROVE CYCLE ROSTER` twice);
- no strict cycle identity metadata (cycle_id / created_at / project_identity);
- zero explicit `## RUN` sections;
- symbolic `source_tree_fingerprint` values (`saicritic-cycle-1`,
  `improve-cycle-2`, `improve-cycle-3`);
- bare IMP cross-artifact identity.

Their semantic findings are not wrong; their EVIDENCE SCHEMA is legacy. Bare
`source_reports: IMP-###` refs may resolve against legacy (run-less) sweep
records in legacy cycles under historical compatibility; a bare ref FAILs once
the only matching records live in strict cycles. All newly created cycles use
the strict schema; the new writers never emit the legacy form.

## Cold SAICRITIC dogfood (cycle imp-vacterro-saipen-20260810-1, archived)

A NEW SAICRITIC cycle ran AFTER the strict evidence boundary through ONLY the
public/mechanical path, with no seeded expectations:

`saipen improve` (audit assignment, strict cycle + draft report + real
`git-delta-v1` fingerprint) -> `saipen improve submit` (RUN-1, journaled) ->
`saipen improve complete` (full validation bar) -> `saipen improve sweep-queue`
(4 exact composite findings) -> tickets created via SAIOPS with exact composite
`source_reports` -> `saipen improve sweep` (4 dispositions) -> `saipen improve
verify` PASS -> `saipen improve cycle-complete` -> `saipen improve clean`
(archived). Zero raw MANIFEST/report/SWEEP writes.

The critic independently detected real remaining gaps:

| Finding | Lens | Ticket | Fixed |
|---|---|---|---|
| IMP-001 | source freshness not enforced at sweep/verify gates | T-619 | write_sweep_entry refuses CONFIRMED on stale evidence; verify_cycle refuses a stale fully-swept cycle |
| IMP-002 | status derives a healthy lifecycle from fabricated fingerprints | T-620 | status applies the validator's report-validation depth (INVALID_REPORT) |
| IMP-003 | raw-writer bypass is normative only | note | recorded as an accepted boundary limit |
| IMP-004 | a stuck draft cycle has no mechanical exit (demonstrated live) | T-621 | `saipen improve abort` -- journaled, disposition-guarded, byte-preserving |

The dogfood also demonstrated the stuck-cycle defect live: a submitted RUN with
a missing `evidence:` field was correctly refused by the completion bar, and the
only old escape was a raw directory delete.

## Fresh re-verification by current evidence

| Ticket | Claim | UNIT | COMPOSITION | CANONICAL | GATE | PROVENANCE |
|---|---|---|---|---|---|---|
| T-615 | composite finding identity + sweep authorization | multi-RUN collision control; fiction-refusal controls (nonexistent report/run/finding/ticket); SweepRecord round-trip | writer->parser->derive_status end-to-end; exact-composite source_reports green/red | validate.py PASS | write_sweep_entry pre-write gate | composite refs only; bare ref into a strict cycle FAILs |
| T-616 | report lifecycle + completion/verify integrity | bare report_status skeleton refuses; NO_FINDINGS controls; parser-derived immutability | complete_report -> complete_cycle chain; verify rejects incomplete completed report | validate.py PASS | full validation before completion | lifecycle state parser-derived, never substring |
| T-617 | high-level command semantics + no-manual-courier path | bare improve returns AUDIT_ASSIGNMENT, never status; submit/complete/sweep-queue routes | public end-to-end cycle (improve -> submit -> complete -> sweep -> verify) with zero raw writes | validate.py PASS | verify delta-only, never recurses | exact unswept composite queue |
| T-618 | strict manifest + freshness + proof | strict manifest round-trips; fake fingerprint fails; stale-tree detected | legacy + strict cycles coexist | validate.py PASS | manifest = writer = parser = validator | portable project identity; real mechanical fingerprints |

Full wave gates: run_scenarios.py green (81 improve + 171 nitro-integrity),
tools/validate.py PASS, R1..R13 repro all NOT REPRODUCED (every claimed defect
flipped).

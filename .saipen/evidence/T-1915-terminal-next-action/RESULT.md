# T-1915 — SRC-325: terminal-checkpoint deadlock (reproduced, partly repaired)

## PRE_FIX_REPRODUCTION

Measured on the current revision with a Freebuff-shaped fixture (phase DONE,
task none, descriptive `next_action`, `[x]` row in `## DOING`, STATE.last_event
three events behind the LOG tail, a queued request):

    next_action -> refuse  "cannot be projected: phase 'DONE' is not
                            ticket-bearing or task is not a work ticket"
    operator_decision_available: true
    canonical_next_command: saipen recover resolve-next-action <SRC-###>

Refusal therefore fired before the shared router was ever consulted. In the
same run the other two defects were already diagnosed (`last_event` repair and
the `[x]` -> `[/]` presentation repair), which is the second half of the report:
one advisory field held the whole transaction.

Red control: `tools/test_t1915_terminal_next_action.py::
test_the_pre_fix_contract_refuses_the_terminal_checkpoint` disables the new
projection predicate and lands on exactly that refusal.

## ROOT_CAUSE

`reconcile._state_next_action_repairs` treated a non-ticket-bearing phase as an
unprovable route. That is a category error: `next_action` is a ROUTING
PROJECTION derived from STATE/BOARD/queue, not a decision record. Decisions live
in the journal and in operator gates. When the shared router uniquely projects
an executable action from the same bytes, the replacement is deterministic.

## FILES_CHANGED

- `tools/saipen_engine/reconcile.py`
  - `_state_next_action_repairs`: a non-ticket-bearing checkpoint is projected
    from `router.route_next` when the phase is a declared DFA phase, the action
    is legal `next_action` grammar, and the router reason is not a gate.
  - `_terminal_projection_allowed(phase)` — the explicit predicate (red control
    surface).
  - `_NON_PROJECTABLE_REASONS` — router reasons that are NOT projections
    (`foreign-live`, `binding-mismatch`, `wait`, `operator-gate-due`, recovery
    and malformed-state reasons). Projecting one of them would launder a gate
    into an executable command.
- `tools/test_t1915_terminal_next_action.py` (new)
- `tools/test_next_action_deadlock.py` (two assertions moved to the new
  contract; the refusal contract moved to the new module's unprovable fixture)

## POST_FIX_REPRODUCTION

Same fixture, original bytes, `saipen recover` (in-process dry run):

    changed.state: last_event 91 -> 93
    changed.state: next_action -> "PHASE SCOUT T-70" (reason 'start')
    changed.board: T-69 checkbox 'x' -> '/'   (presentation only, stays DOING)
    operator_decisions: []                    (none for next_action)

## SAFE_RECOVERY_RESULTS

- A projectable terminal checkpoint repairs in ONE journaled transaction: state
  marker, next_action and BOARD presentation together; `recover` answers
  `REPAIRED`, the marker binds to the LOG tail the repair writes (L08/L09).
- Repeating `recover` writes nothing and returns no next_action repair
  (idempotent, AC-24).
- The legacy prose survives in the archived pre-repair STATE under
  `.saipen/recovery/state-legacy-output/` and in the repair DEC (N11).

## AMBIGUOUS_GATE_RESULTS

- A live FOREIGN seat: the router answers `foreign-live`, the repair refuses,
  and the gate still names `saipen recover resolve-next-action <SRC-###>`
  (AC-08, N20).
- The compound field shape keeps exactly ONE operator decision (the BOARD
  section move of an unclaimed DOING ticket), not two, and that decision names
  `saipen recover --apply-approved-repair <id>`.

## URGENT_WORK_ROUTING

Not implemented in this slice. Unchanged behaviour: a fresh request is captured
durably and queued (proven twice this session: SRC-324/T-1911, SRC-325/T-1915),
but it cannot take a seat that a malformed checkpoint refuses to release. With
the next_action gate gone, the remaining blocker is the single BOARD gate above.

## EXTERNAL_WORK_PROVENANCE

Not implemented (SRC-325 §10). No mechanism in this revision re-admits work
performed outside the lifecycle; the existing Source/Work admission is untouched.

## TESTS

- `tools/test_t1915_terminal_next_action.py` — 5 passed (incl. red control).
- Mandated families: `test_next_action_deadlock`, `test_recovery_reachability`,
  `test_reconcile_legacy_output_field`, `test_reconcile_history_ledger_blocked`,
  `test_reconcile_valve`, `test_recover_approved_repair`,
  `test_recovery_noop_targets`, `test_t1316_recovery_already_applied`,
  `test_t1327_zero_manual_recovery`, `test_t1751_reconcile_surfaces`,
  `test_t1883_reconcile_causality` — 261 passed, 205 subtests.
- Routing/continuation families: `test_continue_entry`,
  `test_t1669_clean_done_projection`, `test_cold_recovery`,
  `test_t1572_ticket_scoped_recovery`, `test_t1609_unproven_done_recovery` —
  63 passed, 34 subtests; `test_router_closure_readiness`,
  `test_t1598_stale_claim_next_action`, `test_t1757_claim_follows_route`,
  `test_foreign_owner_terminal_route`, `test_refusal_routes` — 47 passed.
- `ruff check` clean on every edited file.

## DIAGNOSTIC_CLASSIFICATION (§12)

The next_action atom now names its own class using existing result types:
`NEXT_ACTION_CANONICALLY_PROJECTABLE` on a repair,
`NEXT_ACTION_SEMANTICALLY_AMBIGUOUS` on a refusal. Held by two assertions in the
new module. The compound field shape keeps its existing report
(`changed.state` / `changed.board` / `refused[]` with field, surface, exact
command), so every diagnosed defect stays visible in one answer.

## WRITE_PREVENTION (§11 P01/P07/P09) — verified, not changed

Probe on the current revision (`state.patch_state` + `fast_check.validate_texts`):
the low-level patcher accepts a free-text `next_action`, and the validator
refuses the SAME proposed bytes ("does not start with
WAIT:/saipen /PHASE /RUN:/RESUME:"). Canonical operations run
`validate_texts` before their write (`operations.py`, `controls.py`), so a
canonical writer cannot persist prose routing state; the T-1669 family holds the
producer side of that rule. What Python validation cannot do is stop a foreign
process from editing STATE directly — that stays a detection fact, never a
prevention claim (P12/P13).

## INSTALLED_RUNTIME_ACCEPTANCE

Not proven. No installed host ran this revision; nothing here is reported as
live acceptance (AC-25 remains open).

## P0-003 / §6 — measured answer: no defect at this revision

Re-measured after the next_action repair, on the exact field compound (stale
marker + advisory next_action + `[x]` in DOING + unclaimed ticket):

- the answer carries ONE operator decision, and it is a BOARD lifecycle
  mutation (`## DOING` -> `## TODO` for work that was never started, SRC-043);
- an unapproved `recover` writes NOTHING (STATE and BOARD bytes unchanged);
- one `--apply-approved-repair <id>` commits the entire set atomically --
  marker, next_action projection, checkbox presentation and the section move;
- the plan id is content-addressed, so a stale approval refuses
  (`STALE_APPROVED_REPAIR`, already held by `test_recover_approved_repair`).

Committing the state repairs BEFORE the approval was considered and rejected:
the repair id binds the bytes, so a partial commit invalidates the plan the
operator is about to approve and turns one decision into two -- the
repair-one-field-then-rerun loop SRC-043 removed. R05-R08 are satisfied by the
current atomic approved plan; no code change is warranted.

## REMAINING_BLOCKERS

1. None for P0-003 (see above). The BOARD lifecycle set stays approval-gated by
   design.
2. SRC-325 §9 urgent-work lane: not implemented.
3. SRC-325 §10 external-work provenance: not implemented.
4. SRC-325 §11 write prevention: `next_action` writers are unchanged; the
   repair only removes the deadlock, it does not prevent a malformed write.

## NEXT_EXACT_ACTION

`saipen continue`

---

# SRC-325 §10 — EXTERNAL IMPLEMENTATION PROVENANCE (implemented)

## The gap, measured

The field incident: a reconciliation deadlock blocked the lifecycle, and the
application files were repaired through workspace tools anyway. Nothing in the
engine could describe that work truthfully — `analyze_handoff_delta` only runs
AT admission, on a request text it is handed. A worktree delta with no Source
and no Work was simply invisible: neither evidence nor a refusal, and certainly
never DONE.

## What exists now

`saipen source delta <SRC-###>` → `handoff_reconciliation.classify_external_delta`

Read-only, five dispositions, and no path from a dirty tree to a canonical
event:

| Disposition | Meaning |
|---|---|
| `NO_DELTA` | the worktree carries nothing unadmitted |
| `ACCEPTED_FOR_ADMISSION` | every clause is covered by bytes already on disk — admit through Source/Work, then verify |
| `PARTIAL_DELTA` | some clauses covered; the rest is real work, not re-implementation |
| `QUARANTINED` | a delta nothing can attribute to this objective: not credited, not deleted, not DONE |
| `UNAVAILABLE` | no worktree to observe — absence of evidence, never a clean bill |

Contract, clause by clause:

- **E01/E02/E13** — `paths[]` carries the exact changed-file identity: relative
  path, sha256, observed mtime (UTC `Z`), presence, and `PROJECT` vs
  `PROTOCOL_MEMORY` class. Untracked directories are expanded to files, and a
  project nested in a larger repository is measured in ITS OWN frame, so a
  parent repo can neither hide nor mislabel the delta.
- **E03** — a clause is covered only when the CHANGED BYTES carry it (token
  overlap ≥ 2 against the file's content and path), never by the ticket title.
- **E04** — provenance is what is observed now: mtimes and digests. Nothing is
  backdated.
- **E05/E06** — `history_written: false` in every record. No Source minted, no
  LOG event, no claim that SAIPEN executed the work.
- **E07** — the only offered next step is ordinary admission
  (`ADMISSION_REQUIRED` → `ADMIT_THEN_VERIFY`).
- **E08/E09/E14** — `verification: "NOT_EXECUTED"` is a constant of this
  classifier. A dirty tree is presence, never a passing run, and never DONE.
- **E10** — a covered clause is reported as covered so the work is not
  implemented twice.
- **E11** — `publication_authority: "CLOSED"` unconditionally.
- **E12** — the disposition IS the report: accepted-for-admission, partial,
  quarantined or unobservable.

## Verification

- `test_t1916_external_delta.py` — 12 tests: clean tree, covering delta
  (accepted, still `NOT_EXECUTED`), provenance identity, protocol-memory class,
  unattributable delta quarantined, no-objective delta never credited, partial
  coverage naming the remainder, no-worktree honesty, and the write-freedom
  invariant (a full tree digest before/after classification is identical), plus
  the CLI verb's reachability, argument refusal and read-only behaviour.
- Source/duplicate-handoff families: 246 passed, 45 subtests.
- `test_protocol_registry.py`: 20 passed (after the documented `ship_improve`
  re-derivation in `.saipen/evidence/T-1915-external-delta/BUDGET.md`, needed
  because the new verb's reference row added 313 bytes to a surface that had 4
  bytes of headroom).
- ruff: clean on the three changed Python files (the three pre-existing E501s
  in `saipen.py` lines 3581/3625/3629 are untouched by this slice).

## Honest residuals

1. §9 urgent-work lane: still not implemented.
2. §11 write prevention: unchanged — canonical writers validate before commit,
   an external editor does not.
3. Installed-runtime parity (§14 / E-series live acceptance): NOT measured.
   Every disposition above is proven on source and in hermetic fixtures only.

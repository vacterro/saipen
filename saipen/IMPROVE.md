# SAIPEN Improve — the meta-control that audits SAIPEN

Improve is a META-CONTROL, not a project phase (T-552). It audits SAIPEN and
the project under it; it does not run project execution. This file is the
single canonical owner of the Improve lifecycle: cycle admission, the seat and
report contract, the finding schema, sweep, verify, and archive semantics.
CORE.md section 1.10 owns command routing only. STATE owns no Improve
semantics. SubSaipen boundaries stay in `extensions/subs/PROTOCOL.md`. There is
no improve phase document under the phases directory, and the phase count
remains 16.

## 0. Why a meta-control

Improve is invoked on top of whatever the project is doing. Several seats may
audit independently and concurrently; reports are read-only evidence, never
canonical state; invoking improve during BUILD or VERIFY must not orphan the
DOING ticket; and one global `STATE.phase: IMPROVE` cannot represent several
independent audit seats at once. Adding Improve routing fields to STATE turns
retrospective evidence collection into project execution state — the category
error this file exists to prevent.

## 1. Command surface (routing lives in CORE.md 1.10)

- `saipen improve` — checkpoint current work if necessary (never orphaning a
  DOING ticket), reload the current protocol, audit this seat's observable
  context, write only this seat's report. Does NOT change phase/task/
  next_action merely to run an audit.
- `saipen improve status` — read-only; derives each registered seat's visible
  status from the roster, the report's `report_status`, and the sweep ledger.
- `saipen improve sweep` — Core-only. Reads reports in deterministic order,
  verifies findings, deduplicates root causes, writes dispositions into the
  Core-owned sweep ledger, creates normal T-### TODO tickets for confirmed
  defects. Never silently pre-empts an existing DOING ticket.
- `saipen improve verify` — a bounded DELTA audit of the current cycle's own
  output (fixes, new rules, new tests, final state). It MUST NOT re-enter a
  full improve cycle and MUST NOT recurse.
- `saipen improve clean` — archive/retention meta-operation. Never means phase
  CLEAN, never enters the CLEAN phase.

No repeated-letter shortcut is assigned; the shortcut key count stays
byte-unchanged.

## 2. Cycle lifecycle

- Core is the sole creator of an Improve cycle.
- `cycle_id` is unique WITHOUT relying on chat history: derived from the
  canonical project identity plus a deterministic token (e.g.
  `imp-<projectkey>-<YYYYMMDD>-<NN>`, the counter taken from the cycle
  directory's existing entries read to end-of-file).
- Creation is atomic: a cycle directory becomes visible only after its roster
  is written.
- Two simultaneous attempts cannot silently create two "current" cycles: the
  second admission REFUSES with the existing cycle named.
- One project has at most one active Improve cycle unless an explicit
  separate-cycle operation exists.
- A completed cycle is immutable.

Improve routing/status is DERIVED, never carried in `STATE.md` (T-553): the
visible status per seat (expected / draft / complete / swept / unavailable)
is computed from the cycle roster + the seat report + the SWEEP ledger, and a
manifest/sweep edit changes it with ZERO STATE writes. No independent
`improve_*` counter may live in STATE -- the validator's
`[improve-state-purity]` check FAILs such a field and FAILs finding text in
STATE (findings live in seat reports, judgment lives in SWEEP.md).

One real lifecycle order (NITRO dogfood IV, T-601):

```
ACTIVE
    seat reports written / completed (per-seat, parallel)
    ↓
    Core sweep dispositions written to SWEEP.md (judgment is Core-owned)
    ↓
    complete_cycle
    ↓
COMPLETE
    immutable historical evidence (every ordinary mutator refuses)
    ↓
ARCHIVED
    retention state only (saipen improve clean)
```

- COMPLETE means the cycle's mutation-producing work is over: before marking
  complete, every expected seat's report MUST have `report_status: complete`
  AND every finding in it MUST carry a final Core SWEEP disposition for its
  exact composite identity (cycle + seat/report + run + IMP id). A partial
  sweep REFUSES `complete_cycle` -- Core can never freeze the artifact before
  its own sweep finished. One seat's disposition never satisfies another's
  finding (composite identity).
- After COMPLETE every ordinary mutator (register_seat, append_run,
  write_sweep_entry) refuses; only permitted archive metadata may change the
  cycle, and a new cycle may then be admitted without deleting history.

Cycle directory:

```
.saipen/improve/<cycle_id>/
    MANIFEST.md      Core-owned roster (stable routing/identity only)
    SWEEP.md         Core-owned sweep ledger (dispositions, judgments)
    <seat_id>/saipen_improve_<PROJECTNAME>.md     seat report (immutable once complete)
```

## 3. Seat roster (MANIFEST.md)

Core registers the expected seat roster before fan-out. `seat_id` identifies
ONE concrete audit seat or session, never a model family:
`opencode-01`, `claude-01`, `codex-01`, `saiui`, `saihunt`. Two sessions both
running `agent: opencode` MUST NOT resolve to one report unless deliberately
the same registered seat.

Roster fields (stable routing/identity only):

```
cycle_id
created_at
project_identity
seat_id
role
report_path
availability        (expected | unavailable)
```

- `seat_id` is path-safe.
- Duplicate seat registration fails.
- A seat cannot silently attach itself to another project's cycle.
- Unavailable historical seats are explicitly `availability: unavailable`.
- Seat identity is NEVER inferred from `STATE.agent` (latest actor only) or
  from LOG agent tags (optional field).

The roster is NOT a second report: it carries no `draft`/`complete`/`swept`
status. Those are derived (section 5).

## 4. Seat report

Canonical paths:

```
Core seat:      <project_root>/.saipen/improve/<cycle_id>/<seat_id>/
                    saipen_improve_<PROJECTNAME>.md
SubSaipen seat: <sub_home>/improve/<cycle_id>/
                    saipen_improve_<PROJECTNAME>.md
```

- The exact requested basename is preserved; everything above it is the
  canonical path.
- Nothing is ever written under the shared protocol install (`saipen_home`).
- One seat owns one report path. A different seat gets a different directory;
  a different cycle gets a different directory.
- A second run from the SAME seat in the SAME cycle APPENDS an immutable RUN
  section; an earlier RUN is never overwritten.

Report header identity — NO absolute machine-local path. Report identity uses:

```
saipen_version
protocol_fingerprint
```

A logical protocol-source classification MAY appear; the absolute local
installation path (e.g. `V:\...\_SAIPEN`) must never be persisted as report
identity: it is machine-local, non-portable, unnecessary for reproduction, and
potentially user-specific filesystem leakage.

`report_status: draft | complete`. A seat marks a RUN complete; from that
moment the original report content is immutable (byte-stable).

## 5. Derived status (one fact, one owner)

`saipen improve status` DERIVES the visible status:

| Visible | Derivation |
|---|---|
| expected | roster entry exists, no report |
| draft | report exists, `report_status: draft` |
| complete | `report_status: complete`, no Core disposition yet |
| swept | sweep ledger contains final disposition coverage for that report |
| unavailable | roster explicitly records `availability: unavailable` |

MANIFEST never mirrors report status. SWEEP owns dispositions.

## 6. Finding schema

A finding is `IMP-###`, numeric order inside a report. Required header block:

```
agent, role, model_or_runtime, project,
saipen_version, protocol_fingerprint, source_head, source_tree_fingerprint,
context_scope, context_available, report_status
```

No `saipen_home` absolute path. Every finding MUST carry an observable
expected/actual/evidence triple — a finding without it is rejected, not
softened. Closed vocabularies:

- severity: `P0 | P1 | P2 | P3`
- class: `PROTOCOL_VIOLATION | PROJECT_VIOLATION | LOGIC_ERROR |
  ACCIDENTAL_SUCCESS | USERPERSON_MISS | VAGUE | OTHER`
- confidence: `observed | reproduced | proven | suspected`
- action: `fix | ticket | note | reject`

`context_available: complete` is refused when the stated scope is partial.
`NO_FINDINGS` with a stated scope is legal. `LATER_RULE` is distinct from a
historical violation. `ACCIDENTAL_SUCCESS` is first-class: a correct result
reached without the required verification is never PASS.

`USERPERSON_MISS` is a preference class, not automatically a protocol
violation. A seat may only be classified `USERPERSON_MISS` for a preference it
was legitimately given via a projection (section 8).

## 7. Core sweep (judgment is Core-owned)

Core sweep is the only path from report to canonical work:

1. deterministic report order; numeric IMP order inside a report;
2. reproduce; reject invalid findings;
3. root-cause deduplication: several reports naming one root cause produce ONE
   ticket with every `source_reports:` reference;
4. dispositions are written to the Core-owned ledger `.saipen/improve/
   <cycle_id>/SWEEP.md`, NEVER into the seat report;

SWEEP.md records per finding: `report_path, run_id, IMP-id, disposition,
reproduced, canonical ticket, fixed_by, verification`.

Disposition set (closed): `CONFIRMED | DUPLICATE | ALREADY_FIXED |
SUPERSEDED | LATER_RULE | NOT_REPRODUCED | INVALID | NEEDS_EXTERNAL_EVIDENCE`.

A report's own `confidence: proven` is evidence to inspect, never a ticket
authorization. Canonical tickets carry: `source_reports, reproduced,
invariant, defect, impact, exact_fix_scope, red_control, done_condition`.

Chain of custody:

```
SEAT REPORT      immutable observation
        |
        v
CORE SWEEP       canonical judgment (SWEEP.md)
        |
        v
BOARD TICKET     actionable work
```

Observation and judgment never live in one writable file. A completed seat
report is hash-verified unchanged after sweep/fix/verify.

## 8. USERPERSON projections

SubSaipen handoffs project a relevant preference subset, never the whole
profile, and record what was projected so Core can audit it:

```
projection_policy(role) -> allowed preference categories
project_profile(profile, role) -> the bounded projection
```

A projection handoff includes: the source profile fingerprint, which
preference IDs/categories were selected, and the scope statement. If the
semantic category selection is performed by the model rather than Python, that
is stated explicitly and the mechanical layer only validates/writes the
already-distilled representation. USERPERSON preference identity is structured
(category-keyed), never pretended to be solved by string splitting.

## 9. Verify (delta-only)

`saipen improve verify` audits ONLY the delta produced by this cycle. It MUST
NOT reopen unrelated history and MUST NOT recurse into a full improve cycle.
If it starts another historical self-audit, it fails.

## 10. Archive / clean semantics

`saipen improve clean` is archive-with-provenance and NOTHING else: it
refuses while any finding is unswept or any disposition is missing (naming
the finding, red control 23), it preserves the original findings verbatim,
and every archived report keeps the canonical ticket references that point
back at it (the `[sweep-ticket-link]` check must still resolve an archived
report's `source_reports` -- deleting SWEEP.md or the report to "clean up"
breaks provenance, red control 24). Partial or timed-out test evidence can
never mark an IMP fixed (a CONFIRMED disposition with `reproduced` other
than `y` fails, red control 25).

Prefer immutable cycle directories plus a compact index/archive marker over
renaming paths that tickets reference. Do not create link rot as a cleanup
feature: canonical ticket provenance must still resolve through a stable
cycle/report identity after archiving.

## 11. Meta-control proof

Improve being a meta-control means:

- no phase enum row is added (phase count stays 16);
- no improve document exists under the phases directory;
- INDEX does not list IMPROVE as a phase;
- no transition table contains IMPROVE;
- `saipen improve` may checkpoint current work before an audit but never
  changes phase/task/next_action merely to run the audit;
- `saipen improve` never silently enters ADD -- an audit run never routes
  into the ADD phase (T-557).

## 12. Writer boundary and recursion stop (T-557)

During SELF-AUDIT/REPORT no seat may touch Core protocol, main source, or the
canonical BOARD/LOG/STATE except the bookkeeping that registers the audit. A
SubSaipen writes only inside its own home (`extensions/subs/PROTOCOL.md`);
an auditing sub that writes a main-project file violates the boundary. A seat
report is evidence, never canonical BOARD state: a report that carries BOARD
section headings (`## DOING` / `## TODO` / `## DONE` / `## BLOCKED`) is
rejected (red control 22). `saipen improve verify` is delta-only (section 9)
and NEVER re-enters a full improve cycle -- a verify pass that reopens
unrelated history or starts a fresh cycle fails (red controls 17/18).

## 13. Reasoning gates are checked artifacts (T-558)

A protocol-level improve ticket (a `PROTOCOL_VIOLATION` finding that produced
a canonical ticket) MUST record two checked artifacts on the ticket itself:

- `recurrence:` -- the META-IMPROVEMENT rule. The cross-project recurrence
  analysis: does this defect recur across projects, or is it local? A
  protocol-level fix records the reasoning; a local bug stays local.
- `weak_model:` -- the WEAK-MODEL PRECEDENT test. The answer to "could a weak
  but compliant model still choose wrong while honestly believing it followed
  SAIPEN?", strengthened in the fixed preference order: state field,
  transition rule, validator, red scenario, canonical example, prose last.

The `[sweep-ticket-link]` check FAILs a `PROTOCOL_VIOLATION` finding that
produced a ticket without both fields (red controls 15/16). A fix answered
only with prose where a state field or validator was available is flagged.
`ACCIDENTAL_SUCCESS` is first-class: a finding whose result was correct but
whose verification never ran is classified `ACCIDENTAL_SUCCESS`, never PASS
-- a sweep disposition recording it as verified (`reproduced=y`) fails (red
control 5).

A real IMPROVE phase may still be proposed only by first proving a failure the
meta-control design cannot solve.

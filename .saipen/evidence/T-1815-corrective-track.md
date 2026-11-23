# T-1815 — SRC-274 corrective track (F-01, F-03)

Scope: the two SAIPEN-owned correctives of `SRC-274` that this ticket delivered,
with the honest red-before-green controls the receipt's acceptance gate demands.
The remaining SRC-274 SAIPEN items (R003–R005) are projected as their own
tickets T-1853/T-1854/T-1855; R006 is the ownership boundary and was not acted
on.

## What was measured before any edit

`SRC-274` is a **second** audit receipt, distinct from `SRC-275` (33,461 vs
34,631 bytes; different sha256). Its contract carried `"clauses": {}` and its
coverage `"requirements": {}`, so T-1815 began with **no derived scope at all**.
The canonical derivation path exists (`intake.ensure_request_clause`), but its
heuristic extractor reads 17 paragraphs of the receipt, of which seven are
explicitly *non-findings* ("correctly handled boundaries") and one spans the
ZAICODE/AUDAPACK tracks. Accepting that shape would have bound this ticket to
claims the audit did not make, so the clauses were derived **explicitly** from
the receipt's own "Corrective ownership and execution order" section, one batch
under one contract revision (`REQUIREMENT_ADDED`, revision 1).

Seven clauses result, and the ownership boundary is one of them (R006), so the
scope cannot silently grow into another product's repo.

## F-03 — a late checkpoint may not become live lifecycle history

**Defect, reproduced live.** The receipt records a checkpoint for already-DONE
T-1745 accepted at 02:11 while T-1744 owned the active phase. Reproduced against
this tree before the fix:

    python tools/saipen.py checkpoint DEC T-1851 "SHIP -- probe" --dry-run --json
    -> {"ok": true, "code": "CHECKPOINTED", "event_id": "E-17311", "dry_run": true}

with `STATE.phase=DONE`. The whole ticket-bearing guard in
`operations._plan_checkpoint` was two shape tests: `T-\d+`, and "is the row on
the board". A finished ticket therefore stayed writable forever, and a bystander
could mint durable `[T-###]` lifecycle history for work it did not own.

**Fix.** `operations._stale_work_context_refusal` binds a ticket-bearing
checkpoint to the project's own statement of current work: `STATE.task` must
equal the named ticket, that ticket must still be the one `## DOING` row, and a
project with no active task refuses rather than guessing a subject. Refusal is
`STALE_WORK_CONTEXT` (registered in `saipen/REGISTRY.json`) and writes zero
canonical bytes. Ticket-less session checkpoints stay legal — budget and idle
notes carry no ticket by construction, and blocking them would break ordinary
operation. Retrospective evidence keeps its own journal class
(`improve_retrospective_v1`), so it never needs this verb.

**After the fix, the same probe:**

    -> {"ok": false, "code": "STALE_WORK_CONTEXT", "changed_files": []}

**Red-before-green control.** `test_without_the_guard_the_same_checkpoint_would_forge_history`
patches the guard away and asserts the very same checkpoint is ACCEPTED and the
canonical bytes move. It fails if the green ever stops depending on the guard.

Tests: `tools/test_t1815_stale_work_context.py`, 9 cases — finished ticket,
merely-inactive ticket, no active task, current ticket still writes, ticket-less
checkpoint still legal, the two-writer race, the code is registered, the guard
is the single authority the planner consults, and the red control.

## F-01 — a restamped improve header is not fresh evidence

**Defect.** `improve._freshness_errors` compared the report's `source_head` and
`source_tree_fingerprint` to the current tree — the report **header**, which a
writer can edit. The measured AUDAPACK sequence was: report goes stale, engine
refuses, header is rewritten in place with `re.sub`, `improve complete` then
accepts. Fresh authority was bound to bytes no audit examined.

**Fix.** `improve._header_repair_errors` anchors the header to the
producer-attested RUN provenance T-1816 already writes
(`run_source_head`/`run_source_tree_fingerprint`, emitted by `append_run`, never
choosable by a model). A header that names an identity **no RUN recorded** is a
header-only freshness repair and is refused; completing it would seal a
fabricated attestation. The check runs inside `_freshness_errors`, so every
existing consumer inherits it.

The rule is deliberately one-directional:

- header names an identity some RUN recorded → admissible (even if a newer RUN
  measured a newer tree: that is ordinary history, and currency is decided
  separately by the existing comparison);
- header names an identity no RUN recorded → refused as a repair;
- legacy report with no RUN provenance, or `UNAVAILABLE` provenance → no bar
  invented (an honest hole is not a contradiction).

**Red-before-green control.** `test_without_the_bar_the_same_restamp_looks_clean`
disables the bar, shows the restamped bytes pass, then asserts the real bar still
refuses once the patch is lifted.

Tests: `tools/test_t1815_header_repair.py`, 10 cases — clean header, restamped
header, genuine new RUN moves the bar, header naming no RUN, older header with a
newer RUN, legacy report untouched, `UNAVAILABLE` not manufactured into a
verdict, a completed report really carries per-RUN provenance, the end-to-end
restamp refusal, and the red control.

## Verification

| Check | Result |
|---|---|
| focused gate, six patterns, current tree | PASS, 64 tests, record `ee1a8bbd8d49eda5-20261022T160119496857Z` |
| the audited F-03 probe, after the fix | `STALE_WORK_CONTEXT`, zero writes |
| the active ticket's own checkpoint | still `CHECKPOINTED` (E-17319) |
| checkpoint-dependent cluster (9 modules) | 120 tests OK |
| related improve/provenance cluster (5 modules) | 48 tests OK |
| `ruff` on all four changed files | All checks passed |

## Coverage disposition

| Clause | Disposition | Route |
|---|---|---|
| R001 F-01 report authority | VERIFIED | this ticket, record `ee1a8bbd8d49` |
| R002 F-03 checkpoint CAS | VERIFIED | this ticket, record `ee1a8bbd8d49` |
| R003 F-02 fresh handoff admission | DEFERRED | T-1853 |
| R004 F-04/F-05 ingress + runtime home | DEFERRED | T-1854 |
| R005 F-06/F-09 compound resolver policy | DEFERRED | T-1855 |
| R006 ownership boundary | NOT_APPLICABLE | non-goal, nothing mutated outside SAIPEN |
| R007 acceptance gate | VERIFIED | red controls above |

R003–R005 remain `unresolved` by the engine's own arithmetic (`DEFERRED` is not
a terminal disposition). That is the truthful state: those correctives are open
work owned by named tickets, not deliverable claimed by this one.

## Deliberately not done

- The seven refusal codes missing from `REGISTRY.json` (reported by
  `test_refusal_registry`) are **pre-existing** and belong to in-flight intake
  work. Registering another ticket's in-flight verbs here would be exactly the
  convenient green this audit condemns.
- No ZAICODE or AUDAPACK project was read, edited, or committed. R006 records
  that boundary rather than assuming it.

## Superseded evidence and the reason

The focused record cited above (`ee1a8bbd8d49eda5-…`) was valid when written. It
stopped matching the tree when T-1856's fix changed
`tools/saipen_engine/test_runner.py`, which is inside the focused fingerprint
subject, so the record's own rule correctly refuses it now as "tested a different
tree". It stays as history and is not re-cited.

This ticket's gate obligation was already satisfied before that change: the SHIP
transition was accepted (op `transition-8ef30f3361f84ad0a3739421d5470b5e`), and
the ticket is held in `## BLOCKED` on the operator's 206 staged paths, not on
verification. Re-citing a fresh record would prove the tree T-1856 touched rather
than the tree this ticket delivered, so no new citation is manufactured.


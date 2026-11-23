# T-1746 / SRC-240 -- terminal crew convergence for a versionless, ticketless-epoch project

Delivery report in the order SRC-240 section 11 asks for.

## 1. Live SAIPEN root, HEAD, admission, ownership

- Root `V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN`, branch `main`, HEAD `025bf596`,
  protocol 8.1.0, tree dirty (nothing committed since 2026-10-05, T-1644 open).
- Work T-1746 claimed by seat `saipen-cli` (E-15049); no pending recovery, no
  other Claude or Codex process bound to this tree at session start (measured).
- Wintage admission checked separately and read-only: phase DONE, task none,
  intent converge/crew, STATE.mode `full`, no VERSION, HEAD `b5fb1d6`,
  fingerprint `git-delta-v1:91488298...`, epoch
  `converge_intent-967059ce454a40fbb0a13bd4e3835ee8` without `ticket_id`.

## 2. Confirmed defect chain

The four locations SRC-240 names were confirmed in the live tree. Three more
were found only by running the route on a copy of the real bytes, each hidden
behind the previous one.

| # | Where (pre-fix) | Defect |
|---|-----------------|--------|
| D1 | `release.py:702` | VERSION read before the mode is known: a no-publish crew closure of a versionless project refused as if it published |
| D2 | `release.py:799`, `:1143`, `:4583` | empty epoch `ticket_id` refused at plan and inadmissible as a receipt, although `crew.py:401` keeps it optional; the refusal sentence blamed an empty scope |
| D3 | `release.py:1262`, `:2069`, `:2199` | deferred scope compared with the 16-hex journal token while `crew_defer` records a full sha256: every crew scope deferred since the full identity read as changed (not in the audit) |
| D4 | `crew.py:1311` | local or published completion chosen from persisted STATE.mode |
| D5 | `crew.py` `_producer_package_records` | producer pre-ship evidence read from OUTBOX.md alone; one malformed historical entry voided it while SC-8/SC-9 called the producer integrated, so the plan advertised SHIP and the release context refused (not in the audit) |
| D6 | `release.py` `_run_gate` | the gate ran `<project>/tools/validate.py`; a managed project has none, so every release body there died on a missing file (not in the audit) |
| D7 | `release.py` `release_verdict` | an ABORTED attempt (refused local validation, crash before the body) counted as a malformed sibling: the epoch's lineage stayed unclean for good (not in the audit) |

## 3. Terminal outcome contract

See `CONTRACT.md`: PUBLISHED, LOCAL_NO_PUBLISH, or no admissible receipt;
derived from the mode the receipt itself records; no stored field added.

## 4. Files and symbols changed

- `tools/saipen_engine/release.py`: `plan_release`, `_plan_crew_release`,
  `_preflight_plan`, `_apply_no_publish_locked`, `_no_publish_body`,
  `_finish_targets`, `_run_gate`, `_is_admissible_terminal_receipt`,
  `_receipt_evidence`, `release_verdict`; new `_crew_terminal_route`,
  `_crew_carrier_problem`, `_scope_identity_holds`, `_source_identity_drift`,
  `_gate_command`, `_ship_label`, `TERMINAL_*`, `PUBLICATION_*`.
- `tools/saipen_engine/crew.py`: `ReleaseEvidence.mode`, `_release_evidence`,
  `_release_current`, `derive_crew_scope`, `_producer_package_records`; new
  `_outbox_package_records`, `_producer_integration_edge`
  (`_producer_integrated` is now its predicate); SC-11 action wording.
- `tools/saipen_engine/operations.py`: `_plan_crew_closure(published=...)`.
- `extensions/subs/crew.md`: SC-11 row names both terminal outcomes.
- `tools/test_t1746_crew_terminal_outcome.py`: 45 cases, new.

## 5. Red controls before and after

- Engine-measured pair, same verifier, evidence class executed:
  `.saipen/evidence/regression/regression-execution-c7e647fdd0134398bc911dbb541ef96a.json`
  (pre-fix subject red, post-fix subject green).
- Pre-fix subject: 39 of the 45 cases red. The six green ones are the guards
  that must not move (missing VERSION never reaches a publication, an ordinary
  versionless ticket keeps `ticket done`, a cohort keeps its version and
  ticket, a producer without an edge stays without evidence, a superseded tie
  keeps one owner) and the known-good control (ticketed, versioned,
  short-identity closure).
- Mutation controls, each run twice in a disposable copy: 18 mutations, every
  one turns its named test red, none unstable (`mutations.json`,
  `mutate1746.py`). The control run is green twice.
- All twenty cases of SRC-240 section 7 are named tests; the refusing ones
  refuse on the post-fix subject.

## 6. Regression totals

- `test_t1746_crew_terminal_outcome`: 45 ran, all green.
- Contract modules plus the release and crew neighbours (14 modules): 332 ran,
  all green, 4 skipped.
- `ruff 0.16.0 check tools tests`: clean. `git diff --check`: clean.
- Declared core-unit family: see section 12.

## 7. Journal and recovery

- Interrupted closure (death after the first target): `recover` answers
  COMMITTED, a second `recover` answers ALREADY_APPLIED and changes no byte,
  the verdict is ok afterwards.
- Death before the body: `recover` answers ABORTED, STATE/BOARD/LOG unchanged.
- Refused local validation: the attempt stays pending until `recover` aborts
  it; the next closure verifies (D7).
- An unrecovered PREPARED sibling still blocks a new release and still keeps
  the verdict away from ok.

## 8. Was live Wintage touched

No. Every command ran on a robocopy of the tree under the session scratchpad
with `FORBID_SAIPEN_PROJECT_WRITE` naming the real root. After the proof the
real project still reads HEAD `b5fb1d64`, 32 tags, refs digest `442ae4f9e7ce`,
index digest `c7400483be64`, 942 dirty paths, LOG tail E-4128.

## 9. Wintage SC-11..SC-13, measured on the copy

Outputs: `wintage-copy-*.json` beside this file, in order.

1. Before the closure: SC-0..SC-10 and WAIT-ROLE SATISFIED, SC-11 UNSATISFIED
   ("no canonical terminal release receipt"), next action SHIP -- the state
   the audit describes, reproduced byte for byte.
2. Release context after D5: ok, epoch bound, ticket empty, seven scope paths.
3. Plan: mode no-publish, version empty, tag empty, ticket empty.
4. The source gate refuses: ACTIVE receipts SRC-002 and SRC-069 are projected
   by no BOARD Work. This refusal is correct and is that project's own Work.
5. COUNTERFACTUAL, copy only: both receipts discharged with a probe clause
   (`wintage_copy_counterfactual.py`) to look for engine obstacles behind the
   gate. D6 and D7 were found this way.
6. Closure COMMITTED: `release-3470a48652b1488cbd5596589c0d1ae0`,
   terminal_outcome LOCAL_NO_PUBLISH, publication NOT_PERFORMED, LOG
   `ship (no version) -> skipped publish (no-publish: policy)`.
7. Verdict ok; `_release_current` true under STATE.mode `full`; all six roles
   carry pre-ship evidence, saitranslate by its integration edge.
8. SC-11 SATISFIED. SC-12 UNSATISFIED: "final EE is not READY/current", next
   action PREPARE_TRANSLATE_FINAL. SC-13 waits on SC-12. Both need real role
   runs in the project; nothing here claims them.
9. Git in the copy after the closure: same HEAD, same refs, same index, no
   new tag.

This is a copy. It is not a claim that live Wintage converged.

## 10. Publication status

NOT_PERFORMED, in the fixture, in the copy and in this repository
(no-publish ship, T-1644 open).

## 11. Remaining operator-only actions

For the Wintage project, by its operator or an agent it authorizes:

1. Dispose the two unprojected receipts: project SRC-002 and SRC-069 to Work,
   or resolve their clauses. The refusal names the first command.
2. Run the crew circuit in a session that declares `SAIPEN_CAPABILITY=no-publish`.
   Wintage binds this source checkout as its `saipen_home`, so the fixed
   engine is already the one it runs.
3. Do the post-ship role runs SC-12 asks for, then FINALIZE.
4. T-376 stays where it is; nothing here depends on it.

## 12. Declared core-unit family

Two runs of one tree (fingerprint `bc05674d95f643aa`):

- Run 1, started while this session measured the regression pair and derived
  the source clauses beside it: 6430 ran, one member outside the baseline red,
  `test_t1446_supervise.QualityOverTimeTests.test_the_host_bound_ends_a_progressing_slice_without_failure`
  (expected two worker generations inside the host bound, counted one). Its
  text is kept in `family-run-1-red.json`. The member is green three times in
  a row alone, and nothing this Work changed is on its path.
- Run 2, same bytes, quiet machine: verdict PASS, 6430 ran, nothing red.
  Record `.saipen/evidence/core-unit/bc05674d95f643aa-20261013T155047Z.json`.

The member is timing-bound; it is filed as a follow-up instead of being
explained away.

## 13. Follow-ups filed from this Work

Named in the ticket's SHIP line: the timing-bound family member, the pending
attempt a refused local validation leaves behind, home-level validator checks
that fail a managed project on a stray file in the SAIPEN checkout, and the
Wintage-side actions of section 11.

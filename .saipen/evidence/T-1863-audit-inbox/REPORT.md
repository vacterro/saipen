# T-1863 (SRC-295) — SAIHANDOFF_AGENT_DRIFT: clause dispositions

Read-only audit, consumed per `SOURCE-AUDIT-INBOX-01`. This file records what
each derived clause of SRC-295 maps to in the CURRENT tree. It is written
after the mapping was verified in the tree, not from the audit's own prose.

Scope note, stated first because it decides half the ledger: SRC-295 is a
forensic report about ONE captured ZAICODE session in ANOTHER project
(`_BZDECOMP`). Its findings split cleanly into three kinds, and only the
second can be closed by work in this repository:

1. **ZAICODE host/transport findings** (F-01 ingress rewriting, F-02 host
   authority bridge, F-05/F-06 host-side output gates, F-07 push UI). The
   report itself assigns these to "ZAICODE implementation owner". SAIPEN
   cannot implement an OS-bound broker inside a host it does not own, and
   claiming otherwise would be the exact drift class the audit describes.
2. **SAIPEN engine findings** (F-03 own_patch publication binding, F-08
   runtime provenance surface, F-09 continuation-vs-new-scope classifier).
   These are actionable here.
3. **Correct refusals** (F-10). Explicitly not drift; nothing to change.

## The eleven derived clauses

`source_append.derive_normative_clauses` produced 11 clauses from the report
body. Their dispositions follow the verified mechanism, not the finding
headline.

### SRC-295:R001 — requirement: `/goal cc all` vs the registered `cc` shortcut

**DUPLICATE.** The clause is the audit's own *defense* text: it states that
`/goal cc all` is not automatically the registered `cc` shortcut and that
mixed prose+command semantics must be resolved by a parser, not guessed. That
resolver is SRC-274:R005, already carried by open Work **T-1855**
(`needs: T-1815`), whose verify clause names exactly this case: "a mixed
command such as a cleanup command plus /goal cc all preserves ordering, STOP
and provenance". Filing a second ticket for one requirement is the
duplication the audit itself warns about.

### SRC-295:R002 — requirement: provenance must be demonstrated independently of session labels

**DUPLICATE.** Same requirement as SRC-274:R004 (`operator provenance is
carried as a machine-readable witness instead of being downgraded/upgraded by
a label`), carried by open Work **T-1854** (`needs: T-1815`). The
in-repo mechanism exists and is tested: `operator_task.py` defines the
`model_supplied` witness, and `test_operator_task_witness.py`,
`test_ingress_authority.py` (13 tests) and `test_operator_ingress_matrix.py`
(19 tests) prove that identical bytes carry different authority depending on
witness. What those tests cannot do is manufacture a trusted host event —
which is why T-1854 remains open rather than closed.

### SRC-295:R003 — requirement: `own_patch` closure must bind publication

**BLOCKED, and this is the audit's one substantive engine finding.** Verified
directly in the tree: `operations._plan_finish_ticket` refuses `own_patch`
only when `latest_build_declares_no_delta` is true (operations.py:3852). It
never reads Git. A ticket whose BUILD declared `implementation_delta patch`
closes FINISHED while its files are still uncommitted — precisely F-03.

The engine *does* have the downstream half: `closure.resolve_implementation_source`
refuses to treat a DONE `own_patch` ticket as publication authority without
committed release evidence ("DONE is an evidence claim, never proof of
publication", closure.py:724), and `test_closure_provenance.py:124`
(`test_done_alone_is_never_publication`) pins it. So inheritance is protected;
the *closure itself* is not.

**Bound to T-1866, filed for this finding.** REVIEW corrected an earlier
attribution in this very section: the clause was first mapped to T-1675, and
T-1675 is not its owner. T-1675 decides whether managed projects get a
validating Git hook by default — a boundary for an executor that never calls
SAIPEN at all. F-03 is the opposite case: the ticket went *through*
`saipen ticket done` and SAIPEN's own finish gate accepted it, because the gate
distinguishes "BUILD declared no delta" from "BUILD declared a patch" and never
asks whether that patch is published. A Git hook cannot repair a gate that
already answered FINISHED. The audit names SAIPEN as owner of exactly this
repair ("require immutable commit/diff and source identity for `own_patch`
before DONE, with a separate pending-publication state or explicit cohort
binding"), so it is engine work with no operator decision in it. T-1866 now
owns it, and R003 states the mechanism while R007 states the executable
acceptance test.

### SRC-295:R004 — AC: byte-identical receipt for a real GUI multi-clause message

**BLOCKED.** Needs a genuine host event. The in-repo half is proven:
`test_operator_ingress_matrix.py::test_clause_a`/`_b`/`_c` show a new
handoff routes to `start`, a standalone `cc` routes to `continue`, and host
prompts reach canonical admission. `intake._exact_authority_record` records
`redaction.applied: false` with `source_authority.mode: exact`. The
acceptance criterion as written asks for a REAL GUI message — the audit's own
standard, which `test_operator_ingress_matrix.py::test_live_acceptance_disposable_project`
documents as not satisfiable by a disposable fixture. Carried by T-1859
AC-01 [LIVE] and T-1858 AC-03 [LIVE].

### SRC-295:R005 — AC: model-repeated text cannot reset bounded authority

**VERIFIED.** This is enforced today and adversarially tested.
`test_ingress_authority.py::test_identical_trusted_bytes_have_different_authority`,
`::test_real_looking_model_request_has_no_operator_preemption` and
`::test_duplicate_captured_model_bytes_cannot_gain_carrier_authority`;
`test_operator_ingress_matrix.py::test_clause_d_agent_authored_text_cannot_impersonate`
and `::test_clause_l_tripped_bounded_valve_remains_effective`.
`test_t1864_autonomous_valve.py::test_a_consumer_bounded_grant_still_waits_for_its_operator`
(adds the goal-budget path: a consumer's bounded grant still writes the WAIT
and binds a brake). Verification command and result are in the coverage
ledger.

### SRC-295:R006 — AC: a genuine native `cc` passes the OS-bound broker

**BLOCKED.** `host_authority_broker.py` exists and is a real separated
authority (in-memory key, OS-derived process identity, fail-closed). But the
criterion requires a live native GUI `cc`, and broker installation into this
ZAICODE session is exactly what T-1859 AC-01 [LIVE] and T-1858 AC-03 [LIVE]
track. Disposable broker doubles are explicitly excluded by T-1858's own
verify clause ("Disposable broker doubles do not satisfy AC-03").

### SRC-295:R007 — AC: a T-251-like dirty ticket cannot enter `own_patch` DONE

**BLOCKED.** Same defect as R003 and the same owner, **T-1866** (not T-1675 —
that correction is explained under R003): the finish gate does not read Git, so
a dirty T-251-shaped ticket still enters `own_patch` DONE. Recorded separately
rather than folded into R003 because it is the *executable acceptance test* the
repair must satisfy: the T-251 shape denied FINISHED with the exact
remediation named.

### SRC-295:R008 — AC: fixtures-only MPI must report `LOCAL_PASS / LIVE_MPI_UNVERIFIED`

**VERIFIED, in this repository's own vocabulary.** SAIPEN does not have an MPI
acceptance profile (it has no MPI subsystem), but the general mechanism the
criterion asks for exists and is the one this ticket's own closure used:
`acceptance.py` binds every `AC-NN` criterion to a `minimum_witness` level
(`UNIT < INTEGRATION < EFFECT_PATH < LIVE`), defaults conservatively to
`UNIT` when unstated, and `acceptance.witness_satisfies` refuses a weaker
witness. `acceptance_contract.gate` consumes it at REVIEW and finish.
Demonstrated directly: `parse_criterion_specs("AC-01 [LIVE] two-client parity")
-> {'AC-01': {'minimum_witness': 'LIVE', ...}}`. So a ticket declaring a LIVE
criterion cannot close on unit fixtures — the distinction the audit asks for
is already machine-enforced, per criterion instead of per project.
(`test_cold_agent_truth.py::test_effect_path_witness_satisfies_broader_criterion`.)

### SRC-295:R009 — AC: 200-step run with no chatter and a canonical final digest

**BLOCKED as stated** (it asks for a 200-step host run), **with the in-repo
half verified.** `hush.py` implements EXEC-HUSH-01 as an execution-policy
modifier with a CLOSED discretionary set and treats every unknown kind as
mandatory, so a policy cannot silence a safety confirmation; `response_surface.py`
implements EXEC-RESPONSE-01 and `test_response_digest.py` (10 tests) pins the
digest contract. What is missing is the host-side mechanical gate that would
prevent a ZAICODE session from narrating anyway — F-05's ZAICODE-owner item,
tracked by T-1548 (`EXEC_RESPONSE_HOST_GAP`, needs T-1551).

### SRC-295:R010 — AC: "continue, and now I authorize X" creates a new receipt

**DUPLICATE.** This is SRC-274:R003 (fresh SAIHANDOFF admission — `continue`
must not silently substitute persisted Work for a fresh substantial handoff),
carried by open Work **T-1853** (`needs: T-1815`). Its verify clause is a
near-verbatim restatement: "a receipt for a new objective is admitted, queued
or refused mechanically with that decision shown".

### SRC-295:R011 — AC: correct refusals must be preserved

**VERIFIED.** This is the audit's own F-10, and it agrees with the current
tree. The tests that own those refusals are green and were rerun for this
ticket: `test_closure_provenance.py` (unfinished Work cannot bind, published
Work cannot be reclassified), `test_ingress_authority.py::
test_classified_non_work_cannot_enter_any_implementation_phase_or_finish`,
`test_operator_ingress_matrix.py::test_clause_l_tripped_bounded_valve_remains_effective`.
No refusal was weakened to make any other clause here terminal; every BLOCKED
above is blocked on a real boundary, not on an engine choice.

## Honest summary

Of 11 derived clauses: **3 VERIFIED** (R005, R008, R011), **3 DUPLICATE** of
requirements already carried by open Work (R001, R002, R010), **5 BLOCKED**
(R003, R004, R006, R007, R009). Every blocked clause is bound to a live owner
that can actually discharge it: T-1866 for the two engine clauses, T-1859 for
the two that need a genuine host event, T-1548 for the host output gate. Four
of the five wait on an authentic external boundary (a live host event, the
broker's installation, or the host-side gate); R003/R007 wait on engine work
this repository owns, which REVIEW moved off T-1675 and filed as T-1866.

The audit's own headline conclusion — "real host-authority integration
remains unavailable end-to-end; that requires repairing the bridge, not
weakening SAIPEN's refusal checks" — is confirmed by this mapping. Nothing in
this repository was weakened to close a clause.

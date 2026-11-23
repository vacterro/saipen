# SAIHANDOFF agent drift incident — 9 October 2026

This reference records the requested audit and its evidence limits under
T-1691. SRC-196 owns the operator's read-and-record request; SRC-197 preserves
the complete report verbatim, SHA256
`df983dc9ba85b05cba06672a3ae516f4d553aad0874a79bbd99fb6525f35cfa9`
(5505 bytes). The original named audit remains untouched. This record grants
no new protocol rule, host capability, publication authority or consumer repair.

## Evidence and finding disposition

| Report facet | Maintainer finding | Evidence / limit |
|---|---|---|
| Language switched to Russian despite pinned `reply_language: et` | Reported incident; the pinned contract is verified, the actual response is not independently captured here | Current STYLE.md and first-output gate; no original host transcript supplied |
| Multi-page narrative exceeded the reply budget | Reported incident; actual delivered lines/chars remain unmeasured | EXEC-RESPONSE-01 owns renderer/reason budgets; the report supplies descriptions and fragments, not the complete outgoing response |
| T-273 manually added while STATE still names T-271 | Current contradictory floor independently confirmed; attribution to a particular writer remains reported | Read-only `saipen --project-root V:\___VAC\__K\__CODE\__SAITULS status --json` exits 1 with VALIDATION_FAILED and the exact two-DOING refusal; stable source snapshots are preserved |
| `antigravity_b` could not reach/write the private SAIPEN path | Reported access failure, not a reproduced same-account ACL test | No impersonation, account logon, ACL change or live Antigravity execution occurred; the report's explanation also omits `__CODE` in one path |

The measured consumer STATE is BUILD T-271, `last_event: 2772`; its BOARD
contains both T-271 and T-273 in DOING. The canonical CLI rejects that shape
before ordinary work. Its diagnostic names `saipen recover`; this reference
records that route without executing it against the consumer. The existing
floor check therefore detects this state correctly. Neither a successful
consumer repair nor a green SAISPIN suite is claimed.

Exact snapshots and the canonical refusal live under
`.saipen/evidence/T-1691-saihandoff-drift/`: `snapshot.json`,
`snapshot/consumer-STATE.md`, `snapshot/consumer-BOARD.md` and
`saituls-status.json`. Graph verification used project SAITULS, generation
2026-09-23T14:49:26Z. Both checkpoint files are excluded by gitignore, so
the evidence is their directly read bytes, not graph completeness.

The producer's `critical`, `high`, `VIOLATIONS_IDENTIFIED_AND_LOCKED`, account,
root-cause and creation-time fields remain source claims. Its timestamp
2026-10-09T02:44:00Z is later than the initial observation on 2026-10-08 UTC; no
chronology or authority is inferred from it. Its references to audits 20/21
belong to the reported consumer context and are not rebound to this project's
unrelated audit layers 20/21.

## Proposed lock-in rules

1. **Language: qualified/rejected as written.** The pinned STYLE owner already
   determines chat language. The proposed conversational "inline override"
   is not a second setting or a reason to mirror an incoming message. Apply
   STYLE and the first-output gate; no parallel language policy is added.
2. **Compression: rejected as an unconditional five-line rule.** STYLE limits
   prose while EXECUTION owns the total rendered budget, authorized depth and
   safety boundaries. The report's blanket rule would erase those distinctions.
3. **Always run status first: rejected.** BOOT Entry routes a new actionable
   request to START first and persisted continuation to CONTINUE. Preserve
   canonical CLI mutation and the one-DOING invariant without replacing that
   entry contract with an unconditional status probe.
4. **T-271 untouched / SAISPIN green: consumer scope.** This SAIPEN record makes
   no product edits and claims no consumer test acceptance. Reading an incident
   does not authorize its console changes or manufacture a green suite.

## Existing hardening owners and next evidence

The adapter registry declares Antigravity admission, style and final-response
enforcement ADVISORY and declares no delivery hook. Instructions and a
source checkout cannot be represented as mechanical prevention in that host.
No installed Antigravity generation or host trust was proven during this Work.

T-1671/T-1672 already own canonical lifecycle mutation and removal of the old
manual-edit fallback; their engine work is verified locally, while delivery
and acceptance remain blocked. T-1644 owns the unresolved publication policy
that currently prevents clean-source distribution. T-1647 owns the machine
runtime path for a managed account; T-1652 owns real `antigravity_b` acceptance,
and T-1653 owns the external SAI Accounts integration. This report is linked
to those existing boundaries rather than duplicating them or declaring them
completed. The relevant reusable lessons already exist in the downstream-shape
and old-instruction cards; no new card is warranted.

Further verification requires the exact outgoing host responses/transcript,
the host's loaded STYLE/EXECUTION/activation generation and an actual
same-account runtime-access result. Consumer recovery remains consumer Work.
The operational `audit/` scanner treats this named file as foreign residue;
explicit source capture records it but does not rename, delete, consume or
silently convert it into a numbered layer.

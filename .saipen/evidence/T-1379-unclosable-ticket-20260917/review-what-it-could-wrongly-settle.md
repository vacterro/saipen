# T-1379 REVIEW -- every way this could settle something it should not

1. **A large specification's derived clauses.** No: only a clause whose text
   equals the request body's own `## Request` section is touched
   (`is_request_clause`), and the identity is read from the receipt's bytes, not
   from a flag an agent could write. Control:
   `test_a_derived_clause_is_never_settled_from_here` -- R002 keeps the gate red
   and the close is refused with SOURCE_UNRESOLVED naming it.

2. **A ticket that proved nothing.** No: the discharge runs only when
   `verification_evidence` already answers true for this Work, which is the same
   gate the finish enforces a few lines later. Control:
   `test_a_ticket_without_verification_evidence_still_refuses` asserts the
   ledger afterwards, not just the refusal -- nothing was written.

3. **Another Work's receipt.** No: only receipts whose `linked_work` IS this
   ticket and which BOARD links to it are considered (`_board_source_links` plus
   the meta check), so a receipt linked elsewhere is never reached.

4. **A receipt that is not a user request.** No: `source_kind` must be
   `user_instruction`. An audit, an imported spec or a review handoff keeps its
   own coverage obligation. Control: `ensure_request_clause` refuses a foreign
   receipt.

5. **Settling twice, or drifting on retry.** No: `ensure_request_clause` returns
   ALREADY_DERIVED once a contract has clauses, and `set_disposition` is only
   called for clauses the coverage summary still reports unresolved. Control:
   `test_ensure_is_idempotent_and_refuses_a_foreign_receipt`.

6. **A body with no request section.** `request_clause_text` returns "" and the
   seeding refuses rather than inventing a clause out of the header.

7. **Read-only gates quietly writing.** The discharge lives in `ticket done`
   alone -- `release_gate`, `boundary_gate` and `closure.py` still call
   `work_closure_gate` and still only read.

8. **The one thing it deliberately DOES settle:** the operator's own request,
   with the Work's own proof, at the one moment both exist. That is the claim
   the ticket was always making; what changed is that making it no longer
   requires a Python API no CLI exposes.

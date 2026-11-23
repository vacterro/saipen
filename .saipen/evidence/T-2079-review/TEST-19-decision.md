# T-2079 / TEST-19 -- review decision at dc39709c / tree cf7cd4a7

- measured: 2026-11-17 (review run recorded in the package; board state re-read at DEC time)
- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:cf7cd4a7512b88c0b0f2e57a05d17aef9e41b432f907486635c87aa3ab53aa42
- package: TEST-19 (identity sha256:7b6e46e4563f20edb8269137d429f0ff11f87f8e53c30a500b063db59c53f381)
- disposition event: E-21513 family (SUB_DISPOSITIONED; OUTBOX TEST-19 `reviewed`)
- decision event: E-21516 (LOG DEC)
- ticket state: T-2079 ## BLOCKED, blocker WAIT_USER_DECISION

## Review outcome: the hypothesis holds

The five scenarios in `.saipen/extensions/subs/saitest/kitchen/TEST-19.md`
were reproduced by Core: the audit-ingest routing dead end stays gone (S1),
the two-home verifier asymmetry is real and owned (S2), two dry-run crew
plans differ only in the scanned-file counter with no state writes (S3),
an unknown package is refused with no writes (S4), and the restore boundary
inserts only the pruned T-1936 row (S5). S5 also produced the load-bearing
new fact: the INSTALLED 8.1.0 engine contains no restore surface at all
(`gated_tickets`, `pruned_rows`, `restored_board_text`, `restore_board_rows`
exist only in the worktree 8.1.1), so FG-0046's T-1936 finding cannot be
repaired at the installed home by an agent.

Nothing in the package was rejected, so `finding_invalidated` would be false.
The package owns no implementation patch, so `own_patch` would be false, and
`inherited_verified` has no published release to inherit.

## Closure is refused by construction; the class is the honest one

The per-verb refusals are the same ones measured and recorded for the
sibling review ticket: see
`.saipen/evidence/T-2080-review/PY-20-decision.md` (claim ->
TICKET_NOT_WORKABLE, unblock -> WAIT_USER_DECISION with the row-text scan at
installed operations.py 6699-6721, done -> ILLEGAL_TICKET_LIFECYCLE,
ticket-DEC and ticket-RUN -> STALE_WORK_CONTEXT, supersede ->
SUPERSESSION_AUTHORITY_REQUIRED). That matrix is now complete for this
ticket class: every verb that could close a BLOCKED ticket either refuses
at a gate or would require a false claim (`own_patch` with no patch,
`external_implementation` with no lineage, `finding_invalidated` with a
confirmed finding). The three earlier review tickets that closed
`finding_invalidated` each carried a ticket-bound "premise disproven" RUN
event (E-21308, E-21319, E-21328); TEST-19's premises were confirmed, so that
precedent does not apply.

WAIT_USER_DECISION is not a mislabel that a relabelling trick could lift:
the decision that would let this ticket close is the operator's publication
staging authorization (T-2058 gates A/B) -- an operator decision, exactly
what the class says. PROTOCOL.md sec. 4 makes BLOCKED an accepted terminal
disposition for a review ticket: "the linked Core review ticket was
independently closed (DONE/BLOCKED) and the package was marked reviewed by
`sub dispose`". Re-blocking the same fact as BLOCKED_EXTERNAL would both
preserve the block and drag a review ticket into the crew's closure-blocking
set, which is why the current class stays.

## Operator action that lifts this

Authorize the 8.1.1 generation install/publication staging (T-2058). Once a
release names the delivered generation, a review ticket with no patch still
closes by its reviewed disposition, and the dependent chain (T-2062, the GC
patch integration) unblocks. Until then the ticket is in its protocol-correct
terminal state and no agent action can honestly move it.

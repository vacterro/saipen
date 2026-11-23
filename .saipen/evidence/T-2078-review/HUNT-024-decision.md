# T-2078 / HUNT-024 -- review decision at dc39709c / tree cf7cd4a7

- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:cf7cd4a7512b88c0b0f2e57a05d17aef9e41b432f907486635c87aa3ab53aa42
- package: HUNT-024 (identity sha256:54022dc2355cd6392f11192ec5ebc9ae0da9c1e22c31f0016c76d80369c45a60)
- disposition event: E-21513 family (SUB_DISPOSITIONED; OUTBOX HUNT-024 `reviewed`)
- decision event: E-21517 (LOG DEC)
- ticket state: T-2078 ## BLOCKED, blocker WAIT_USER_DECISION

## Review outcome: the sweep holds, with its stated limits

Core re-read of `.saipen/extensions/subs/saihunt/kitchen/HUNT-024.md`
confirms every signal against independent measurements taken this session:

- S1 failing tests -- REPRODUCED, entirely owned: the installed canonical gate
  reports 2 problems/16 warnings (audit-route P1 and FG-0046 P2, both pre-fix
  8.1.0 gaps the worktree payload repairs), and the repo gate's 29 problems
  are the single `runtime_manifest_untracked` class measured independently in
  `.saipen/evidence/T-2058-release-index/CONFORMANCE-DIAGNOSIS.md`.
- S2 commits unverified in LOG -- REPRODUCED, owned by T-1449/T-2057.
- S3 stale markers -- NOT_REPRODUCED (bounded census; one marker is a state
  label inside the T-1609 vocabulary).
- S4 silent failures -- counts only, no claim; correctly not treated as a
  defect.
- S5 symmetry -- the T-1430 producer fix is live (`record_crew_run` called
  from crew.py), and `record_producer_integration` still has zero call sites:
  a documented asymmetry, not a proven failure.
- S6 dead code/orphans -- no claim beyond the 29-path manifest class.

The sweep made no main-project write and invented no defect. Nothing was
rejected, so `finding_invalidated` would be false; the package owns no patch,
so `own_patch` would be false; `inherited_verified` has no published release
to inherit.

## Closure is refused by construction; the class is the honest one

The per-verb refusals for this ticket class are measured and recorded in
`.saipen/evidence/T-2080-review/PY-20-decision.md` (claim ->
TICKET_NOT_WORKABLE; unblock -> WAIT_USER_DECISION with the row-text scan at
installed operations.py 6699-6721; done -> ILLEGAL_TICKET_LIFECYCLE). The
decision that would let it close is the operator's publication staging
authorization (T-2058 gates A/B) -- an operator decision, which is exactly
what WAIT_USER_DECISION says. PROTOCOL.md sec. 4 accepts BLOCKED as a
terminal review disposition: "the linked Core review ticket was independently
closed (DONE/BLOCKED) and the package was marked reviewed by `sub dispose`".
Relabelling to BLOCKED_EXTERNAL would keep the block and drag a review
ticket into the crew's closure-blocking set, so the class stays.

## Operator action that lifts this

Authorize the 8.1.1 generation install/publication staging (T-2058). That
single decision clears the installed-generation gaps (audit route, FG-0046),
gives the repo the tracked generation its manifest check needs, and lets the
dependent chain (T-2062, GC patch integration) proceed.

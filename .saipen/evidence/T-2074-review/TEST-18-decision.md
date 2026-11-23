# T-2074 / TEST-18 -- review decision

- package: TEST-18 (identity sha256:945afd6abe3721a4771f1c6e1107e7fed753a20fc5fe605ab51cf9da0b9a28f6)
- package tree: f3dab073 (the board row before T-2077 moved the tree to cf7cd4a7)
- ticket state: T-2074 ## BLOCKED, blocker WAIT_USER_DECISION; owner saipen-cli, claimed 2026-11-16T16:48:47Z
- decision event: E-21518 (LOG DEC)

## Review outcome: accurate for its tree, re-issued at the live tree

The five TEST-18 scenarios were reproduced: the T-2047 tree keeps the
audit-ingest routing fix, the two-home verifier asymmetry measures
installed 3/19 vs repo 29/39 and is an owned publication condition, two
dry-run crew plans are byte-identical with no state writes, an unknown
package is refused with no writes, and the duplicating restore helper is
unreachable through the canonical verb.

The tree then moved: HUNT-024 and TEST-19 re-ran the same scenario family at
dc39709c / tree cf7cd4a7, where the asymmetry measures 2/16 vs 29/37 and the
restore surface is additionally found to be absent from the installed 8.1.0.
So TEST-18's evidence is historically correct at f3dab073 and its subject
matter was re-issued as TEST-19, whose own review ticket is T-2079. That makes
T-2074 triply terminal: reviewed, re-issued at the live identity, and parked
on the same publication condition.

## Closure: same measured dead end as the sibling review tickets

The full per-verb matrix (claim, unblock, done, ticket-DEC, ticket-RUN,
supersede) is measured and recorded in
`.saipen/evidence/T-2080-review/PY-20-decision.md`. Every truthfully
available closure mode would be false here: `finding_invalidated` because the
findings were confirmed (and `invalidation_error` refuses a confirmed
finding), `own_patch` because a review owns no patch, `inherited_verified`
because no published release names it, `superseded_verified` because the
successor route requires a DONE ticket plus a native supersession grant that
no receipt carries. PROTOCOL.md sec. 4 accepts BLOCKED as a terminal review
disposition. The class stays WAIT_USER_DECISION because the lifting decision
-- the T-2058 publication staging -- is the operator's.

## Operator action

Authorize the 8.1.1 generation install/publication staging (T-2058 gates A/B).
It clears the installed generation gaps, gives the repo the tracked
generation its manifest check requires, and lets the dependent chain
(T-2062, GC integration) proceed. See
`.saipen/evidence/operator-decision-map.md` for the leverage of each
decision.

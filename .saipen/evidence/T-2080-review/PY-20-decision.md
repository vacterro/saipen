# T-2080 / PY-20 -- review decision at dc39709c / tree cf7cd4a7

- measured: 2026-11-17T09:18:57Z
- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:cf7cd4a7512b88c0b0f2e57a05d17aef9e41b432f907486635c87aa3ab53aa42
- package: PY-20 (identity sha256:7424e7c0a6173d0d75b4aa0f09a756a4816efd184ce5a94fb202c7ab7e000f5c)
- disposition event: E-21513 (SUB_DISPOSITIONED, package reviewed)
- decision event: E-21514 (LOG DEC, recorded through the canonical checkpoint verb), corrected by E-21515 (the 8.1.1 install is a PENDING operator decision, not an existing authorization)
- ticket state: T-2080 ## BLOCKED, blocker WAIT_USER_DECISION

## Review outcome: the hypothesis holds

Independent re-measurement this session, against the current tree, confirms
every PY-20 claim:

- target bytes unchanged: gc.py sha256 f1921568..., lock.py sha256 30965c05...;
- `git apply --check kitchen/PY-20.patch` exit 0 (patch sha256 afb610b9...);
- 4 fresh baseline samples: 3 produced GC_MAINTENANCE_FAILED with
  durable_failures 1, 1 routed the collision as GC_NOT_DUE -- the lost-
  checkpoint race reproduces (`_py20_baseline.out`, sha256 bb676077...);
- patched overlay: 8/8 rounds, durable_failures 0, both closures counted,
  one maintenance run per round (`_py20_verify_patched.out`, sha256
  d64acd1b...);
- GC suite: Ran 63 tests, OK (skipped=1), exit 0
  (`_py20_gc_suite.out`, sha256 280dc7ec...).

No claim was rejected, so `finding_invalidated` would be a lie.

## Why the ticket cannot be closed: measured closure matrix

Every canonical route was attempted this session and refused by a different
gate, each with zero writes:

| attempt | result |
|---|---|
| `saipen claim T-2080 --dry-run` | `TICKET_NOT_WORKABLE` -- "carries a blocker; explicit priority override does not override authorization" |
| `saipen ticket unblock T-2080 "<decision>" --dry-run` | `WAIT_USER_DECISION` -- unblock reads the row's CURRENT blocker text and needs an authenticated operator carrier or a proof token in the payload (installed operations.py 6699-6721), neither of which exists |
| `saipen ticket done T-2080 --closure-mode inherited_verified --implementation-source T-2062 --dry-run` | `ILLEGAL_TICKET_LIFECYCLE` -- finish accepts only a DOING ticket (and T-2062 is itself BLOCKED, so no published implementation exists to inherit either) |
| `saipen checkpoint DEC T-2080 "<decision>" --dry-run` | `STALE_WORK_CONTEXT` -- the leading `T-2080` token makes it a ticket DEC; STATE.task is none and a claim of the blocked row is refused (row 1) |
| ticket-less `saipen checkpoint DEC "<decision>" --dry-run` then live | `CHECKPOINTED` (E-21514) -- the decision itself is recordable; only the ticket lifecycle is closed |
| `saipen ticket supersede T-2079 --by T-2059 --evidence E-21516 --authority SRC-415 --dry-run` (sibling ticket, same class) | `SUPERSESSION_AUTHORITY_REQUIRED` -- "authority receipt SRC-415 has no native Work supersession grant"; the verb also needs a DONE successor and a ticket-bound evidence event |
| `saipen checkpoint RUN T-2079 "<probe>" --dry-run` | `STALE_WORK_CONTEXT` -- "a ticket-bearing lifecycle event would record a decision for work it is not in"; canonical next is `saipen claim T-2079`, refused by row 1 |

The `finding_invalidated` precedent does not open a route either: the three
earlier review tickets that closed that way (T-2048, T-2053, T-2063) each
carried a ticket-bound RUN event whose text records a genuine "premise
disproven" (E-21308, E-21319, E-21328), and `invalidation_error` refuses any
such event for a reviewer whose finding was confirmed, for a WAIT/BLOCKED
taxonomy, and for an event that cannot be bound to the ticket in the first
place (the RUN probe above).

Only `own_patch` and `external_implementation` remain unmeasured, and both
would be false rather than refused: the review ticket owns no patch, and no
lineage authority names this work.

Gate completeness measured this turn (installed operator_task.py 629-860):
`unblock` accepts only `witness == "operator_carrier"` -- an active host
ingress envelope bound to THIS session -- or an `operator_origin.authenticated`
proof. A launched task file with matching bytes yields `model_supplied`
("matching carrier bytes are not authenticated operator origin"), and no
matching carrier at all yields `CODE_MISMATCH`. No certified-bypass shape
exists; the refusal is deterministic, not a missing command.

## Decision (standard engineering default), recorded

Keep the verified patch UNAPPLIED and leave T-2080 parked under
WAIT_USER_DECISION. Applying the patch now would mutate the main source and
grow the foreign-dirty delivery surface that the operator's pending 8.1.1
install must stage (`saipen-inject` already refuses on 64 dirty lines), so
integration stays with T-2062 inside the operator-owned install and
release route recorded in `.saipen/evidence/T-2058-release-index/BLOCKED.md`
(operator routes at E-21497). The protocol's reviewed-disposition contract
(PROTOCOL.md section 4) treats a BLOCKED linked review ticket as a terminal
review disposition, which is what E-21513 recorded.

The decision is durable in LOG as DEC E-21514 (checkpoint
`checkpoint-cddb4317fa5f48f5ab68302df97517fd`), written through the canonical
verb with no hand edit, and this file is its full measurement appendix. DEC
E-21515 corrects one clause of it: the 8.1.1 install is the operator's
pending decision, not an authorization that already exists. What
the decision does NOT do is close the ticket: DONE is unreachable from
`## BLOCKED`, and every path that would move it is refused by the table
above. That refusal is the protocol's answer, not a missing step.

## Operator action that lifts this

Authorize the 8.1.1 generation install/publication staging (T-2058 gate A
EX-000053 generation binding, gate B crew exclusion). That install is the
same route that lifts T-2062 and re-enables the T-2077 unblock classifier,
after which the GC patch can be integrated and T-2080's premise reaches its
natural DONE. The measured reason the current core receipt cannot turn PASS
without that decision -- 29 untracked engine/test files under the manifest's
`tools` managed dir -- is recorded separately in
`.saipen/evidence/T-2058-release-index/CONFORMANCE-DIAGNOSIS.md`.

## Completion audit for this turn's requirement

- Decide the engineering default: done -- keep PY-20 unapplied during intake.
- Record it as a DEC line: done -- E-21514 through `saipen checkpoint DEC`,
  corrected by E-21515; no hand edit of LOG.
- Implement the decision: done -- no patch was applied, and the decision's
  consequence (integration belongs to T-2062 / the release route) is carried
  in the DEC and this annex.
- Close the ticket: refused by the engine on every route, each refusal
  measured above. PROTOCOL.md sec. 4 confirms BLOCKED is an accepted terminal
  review disposition: "the linked Core review ticket was independently closed
  (DONE/BLOCKED) and the package was marked reviewed by `sub dispose`". The
  ticket is therefore in its protocol-correct terminal state; a DONE would
  require asserting an implementation-source that does not exist.
- No operator authority was minted: no proof token, no operator carrier, no
  install, no commit, no manifest edit.

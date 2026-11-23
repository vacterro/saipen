# Cross-project conformance deadlock: SRC-195

Status: RECORDED under canonical Work T-1689; append acceptance is under
verification. Investigation conclusions and any admission design remain open.
Controlling source: the immutable SRC-195 append. This record authorizes no
partial-admission change and alters no consumer state, finding or ledger.

## Observations

The read-only canonical Wintage status and dry-run continuation are preserved
in `consumer-status.json` and `consumer-continue-dry-run.json`.

- The incident receipt is exactly `receipt-417946d3e1da`.
- Its current core verdict is `CURRENT_FAIL`, with one blocking problem and
  56 warnings. The blocking problem is `subsaipen [sub-write-boundary]` in the
  saihunt OUTBOX, classified as global with rule_id `unclassified`.
- Continuation returns `CONFORMANCE_UNHEALTHY`, `ENGINEERING_REQUIRED`,
  `terminal: true`, no action and no canonical next command. Recovery has no
  pending operation or conflict.
- Wintage is DONE with task none and no workable ticket. Its six parked Work
  records are T-911, T-907, T-903, T-902, T-376 and T-359. This observation
  does not establish that unrelated runnable work was rejected.
- T-911 identifies the detector's engine owner as SAIPEN T-607. The current
  validator tests whether any canonical path string occurs anywhere in an
  OUTBOX, then reports the write-boundary failure (tools/validate.py:4700-4740).
- `router.conformance_idle_gate` applies to a successful `reason: maintain`
  route. `gate_route` separately applies crew and closure gates. Therefore the
  idle refusal alone is insufficient evidence of a universal Work-admission
  barrier.
- `conformance.conformance_decision` already emits a receipt-bound stable
  ENGINEERING_REQUIRED diagnostic when no executable repair is registered.
  This mechanism is owned by the completed SAIPEN T-1439; related independent
  release-scope Work is SAIPEN T-1404. They are related evidence, not proof that
  this incident's full scope is solved.
- Wintage T-907's preserved description names a launcher bound to a temporary
  core-unit checkout. SAIPEN T-1683 and T-1690 cover independently demonstrated
  fixture-write escape mechanisms. A shared cause with Wintage T-907 remains
  unverified; its present launcher bytes were not examined in this read.

## Ownership and safety dependencies

The normative boundary and its detector belong to SAIPEN, not Wintage. The
conformance/remediation owner is the diagnostic's exact owner, `SAIPEN
conformance/remediation`. T-1689 carries this architectural investigation
record without reopening T-1439 or creating duplicate implementation Work.

Consumer dependencies retain qualified identities: Wintage T-911 (detector),
Wintage T-907 (launcher), Wintage T-903 (historical ledger), and the SAIPEN
conformance/remediation owner. No consumer numeric ID is a SAIPEN dependency.
Wintage T-903's alternatives remain unresolved: reconstruct the 115 lost
events from operation records, or an explicitly authorized seal/restart above
E-3368. Neither option is selected, executed or classified as acceptance.
T-902's missing source, T-376's external input and T-359's authenticated live
browser acceptance remain unresolved consumer boundaries.

## Investigation plan and hypotheses

A. Bind the exact receipt finding to a stable rule/owner, including why it is
   currently classified `unclassified` and global. Preserve the original bytes.
B. Exercise active, queued, idle, crew and closure routes against this same
   invariant in disposable fixtures; compare the canonical refusal boundaries.
C. Separately test the six parked records' contribution. Do not infer a
   universal blocker from their presence beside a CURRENT_FAIL.
D. Read the owned launcher identity and investigate T-1683/T-1690 mechanisms
   against Wintage T-907 before claiming shared provenance.
E. Determine whether an existing canonical independent-Work path applies;
   current idle-gate source scoping is a lead, not admission permission.
F. Determine a detector or registered-remediation repair under its SAIPEN owner;
   compatibility and governance review precede any admission-scope change.
G. Verify repeated identical terminal responses retain the same bounded
   diagnostic and are not retried without changed state/runtime/input evidence.
H. Verify operator-only acceptance stays blocked while any independently
   executable engineering is routed solely by canonical authority.

Proposed conceptual distinctions GLOBAL_UNSAFE, WORK_BOUNDARY_BLOCKED,
EXTERNAL_ACCEPTANCE_PENDING, INDEPENDENT_WORK_ADMISSIBLE and REPAIR_REQUIRED
remain hypotheses, not new states or granted authority.

## Proposed acceptance

Retain all seven source scenarios: a relevant global integrity failure still
blocks; a policy-permitted local failure does not impose an unrelated blocker;
operator acceptance stays outstanding; a missing registered repair names its
owner; a temporary executable identity is detected; identical terminal
responses do not become an autonomous loop; partial admission cannot worsen
an unresolved ledger failure. Prove each with canonical routes and fixed
controls before proposing an implementation.

Next authorized investigation: test the detector/operation boundary against the
exact receipt in a disposable fixture, under SAIPEN ownership, preserving the
global safety invariant and both unresolved historical-ledger options.

The append's requested record/integration can finish independently of that
future design. No speculative product or protocol patch has been made.

## Roadmap integration and append acceptance

The existing roadmap reference index links
`conformance-admission-2026-10-09.md`, carrying this incident and its unresolved
investigation. The completed August roadmap is preserved as historical
acceptance evidence. No duplicate implementation ticket, replacement rule or
new protocol state has been allocated. T-1689 is the canonical record owner;
the conformance/remediation engineering owner is identified above.

All eight current append acceptance criteria are addressed: recorded finding,
identified owner, duplicate avoidance, unchanged safety invariants, distinct
facts and hypotheses, all seven proposed regression expectations, absence of
unauthorized implementation, and an exact next bounded investigation.
The future A-H investigations are retained as open questions rather than
misreported as completed engineering.

## Requested record fields

STATUS: RECORDED
CANONICAL_RECORD: T-1689 / SRC-195; this receipt-bound investigation record
RELATED_TICKETS: SAIPEN T-607, T-1439, T-1404, T-1683, T-1690;
Wintage T-903, T-907, T-911
INCIDENT_RECEIPT: receipt-417946d3e1da
CONFIRMED_FACTS: the canonical snapshots and detector/idle-route source above
UNVERIFIED_HYPOTHESES: universal unrelated-Work refusal; shared launcher cause;
future partial-admission design
SAFETY_DEPENDENCIES: unresolved qualified consumer dependencies above; global
integrity, explicit canonical admission, immutable history and real acceptance
PROPOSED_ACCEPTANCE: the seven preserved source scenarios above
NEXT_AUTHORIZED_ACTION: read-only trace of the exact detector finding and
canonical route boundary, using a disposable fixture and no consumer mutation

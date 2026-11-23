# T-1494 bounded policy preparation (not implemented)

Prepared read-only during T-1515's frozen declared-family run. No phase claim,
production change, new grant or acceptance result exists for T-1494 here.

All inspected tools/ paths are graph-excluded at generation
2026-09-01T13:16:39Z. Direct source fallback covers operator_task, state,
operations, CLI continuation, router, reconcile, fast_check, plan and journal.

One pure profile parser should own the four requested fields. No fields means
legacy operator_required/hard_wait. Partial/contradictory fields must refuse.
The persistent profile uses authority_until=goal_complete; bounded uses budget.
Every intent-family transition must clear all four owned fields together, and
new native goal entry should set a complete profile only from its actual
operator witness. Schema and PROTOCOL_REGISTRY must agree with this parser.

An original journaled goal_entry already stores request_provenance in its
semantic request. A possible canonical authority_source is GOAL:<operation-id>:
resolve its strict immutable journal/semantic evidence, verify the original
operator_carrier and raw objective digest, and bind those exact dependencies in
every plan that consumes the grant. The raw objective digest must be separate
from the redacted/normalized objective. Inspect the actual record layout and
pending/settled decoder before choosing this design; no arbitrary local JSON,
free-text goal marker or bare field assertion can become authority. Source
receipts are another allowed carrier only when integrity and their original
operator provenance both prove the grant. Existing original metadata never
gets promoted by a later retry.

At a persistent ceiling, journal a goal checkpoint naming the ORIGINAL
authority_source and safety review, then roll counters over; it is not goal
reauthorization. Reconcile's counter marker recognizer must include this
checkpoint so recovery cannot rebuild canceled increments. Transition/finish,
continue, stop, routing and core validation must use the same profile and
source predicate. Pure router code still cannot read files: its root callers
must validate the original source before trusting a persistent routing result.

Bounded renewal needs actual original operator cc (or a newly witnessed goal),
never an agent continue/cc alias. Both unconditional CLI branches currently
call reauthorize_valve and must be covered. A scoped external carrier can
prove an original cc in disposable controls; it must not be manufactured for
the live root to bypass its legacy cap. Root currently has goal_tickets=13.

Read-only metadata inspection confirms SRC-112, SRC-165 and SRC-166 each say
model_supplied. In particular SRC-112 retains body SHA256
e529a08ec14a8dd62150530f12ddf7935d72c1181d5e08bf3a37a8c6aa55ab4a.
None can be relabeled operator_persistent. The current host goal remains
active and explicitly user-authorized; determine an actual original carrier
if one is needed at the engine boundary rather than asserting host provenance.

Before production edits, claim T-1494 and complete the FIXED oracle with native
CLI persistent and bounded ceilings, actual operator cc/new-goal positives,
agent aliases, legacy mode, model-supplied receipts, partial/forged/deleted/
changed sources, CAS races, epoch/Work/Source preservation, counter recovery and
canonical core validation. Run that exact final oracle on the original subject
before implementing. Existing two preparation reds cover only bounded reset.

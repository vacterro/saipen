# T-1229 Phase Ownership Map

Scope: all 16 `saipen/phases/*.md` documents at the 100304-byte baseline.
Classification follows the T-1229 source contract: A phase delta; B CORE law;
C OPS/effect law; D MAINTENANCE law; E another owner; F history/rationale;
G repeated checkpoint, log, transition, or ticket mechanics.

Canonical owners confirmed before compression:

- CORE `PHASE-DELTA-01`: DFA, Work/Attempt, retry delta, phase shape, shared
  root/checkpoint/authorization/source/identity law.
- CORE checkpoint contract: `LOG -> BOARD -> STATE`, readback, phase/ticket
  boundary cadence.
- OPS `OPS-EFFECT-01`: effect vocabulary, authorization coverage, provenance.
- MAINTENANCE §§2.1/2.4: autonomous routing, intent-aware HUNT destinations,
  goal counters, caps, reauthorization, goal exit.
- SOURCES `SOURCE-AUTHORITY-01`: capture, contract, coverage, close/archive.
- EXECUTION: narration only; it does not own lifecycle, authorization, or
  evidence.

## Group B

- VERIFY
  - A retain: manual-verify wait; canonical harness/command selection;
    cheapest-first order; mandatory/advisory distinction; known-bad and
    known-good controls; unavailable versus failed verification; dependency
    pinning; regression tests; confidence/evidence; `verify_attempts`; 3 dead
    hypotheses or 2 failed fix cycles; exact PASS/FAIL exits and blocked-work
    cleanup.
  - B/C replace with references: generic Work/Attempt explanation, repeated
    retry law, generic destructive-command authorization, generic checkpoint.
  - D replace with reference: `goal_tickets` persistence/cap procedure.
  - F remove: v7.101 incident narrative and repeated motivation after the
    surviving false-green/false-red invariants.
- ADD
  - A retain: never under converge; evolutionary non-speculative ladder;
    minimal direct versus planned path; bugfix enters normal pipeline; mature
    exit; decision evidence.
  - D cite: autonomous entry, goal-wave lifecycle/cap and Industrial
    Completion policy. Keep only ADD's exact counting moment and no-double-count
    exception.
  - B/G cite: ticket claiming, normal lifecycle and checkpoint mechanics.
  - F remove: old `RETURN`/double-count defect narratives.
- HUNT
  - A retain: explicit full sweep; autonomous clean-tree/hash skip; six
    signals; five-ticket cap; duplicate finding check; no product mutation;
    finding classification; HUNT/MARKHUNT/CLEAN boundary; perf submode; exits.
  - D cite: halt eligibility and intent-aware clean routing.
  - B/C/G cite: generic authorization and checkpoint law.
  - F remove: mtime incident story; preserve the exact clean-tree/hash rule.
- PREPARE
  - A retain: named producer scope; forced-fresh inputs; package schema;
    producer-specific outputs; isolation; readiness/failure exits and evidence.
  - B/C/E/G cite: generic source capture, authorization, recovery and
    checkpoint mechanics.
  - F remove: history of ambiguous producer-less LOG lines; retain exact
    producer-bearing result forms.

## Smaller phases

- DONE — A retain current routing table and MARKHUNT brake; B/D/G cite atomic
  finish, Pick/MAINTAIN and goal entry; F remove old empty-board behavior story.
- PLAN — A retain text mode, proposal-mode legal WAIT, ticket/size decisions,
  ADD double-count exception; B/D/G cite priority, goal caps and checkpoint;
  F remove obsolete prefix history.
- VALIDATE — A retain canonical validator/degraded floor, structural-only
  repair, read-only behavior, no history rewrite and exits; B/E cite schema and
  conformance ownership; remove tutorial wording.
- REVIEW — A retain independent verifier rerun, disagreement handling,
  P0/P1 versus P2/P3 disposition, two-pass-per-finding cap, SHIP exit and
  ticket-stays-DOING; B/G cite lifecycle/checkpoint; F remove incident story.
- INIT — A retain root binding confirmation, template/degraded bootstrap,
  initial empty LOG and PLAN exit; B/E cite field schemas, identity and style;
  F remove placeholder incident narrative.
- BUILD — A retain smallest-safe change, reuse ladder, risky versus destructive
  distinction and failure exit; B/C/G cite prose, authorization and checkpoint;
  F remove explanatory repetition.
- SCOUT — A retain bounded discovery, one neighbor, canonical harness capture
  and architecture reuse; B/G cite claim and checkpoint mechanics.
- BLOCKED — A retain session-level entry test, precise WAIT, no-spin and
  resolved exits; B/G cite LOG/BOARD/STATE mechanics.

## Phase Compression A revisit

- SHIP — A retain entry authority, no-publish matrix, version-surface identity,
  first-publish brake, owned staging/index preservation, binding gate, branch
  before tag, failure recovery, digest and atomic finish. B/C/D/G cite generic
  authorization, goal continuation and checkpoint. F remove incident stories
  once exact ordering/refusal rules remain.
- TRANSLATE — A retain quarantine/parallel-state boundary, real translation
  surface, role split/locales, freshness/coverage, no main-project mutation,
  completion evidence and converge role. B/D/G cite shared checkpoint and
  autonomous entry. F remove past fabricated-UI and shared-state incidents.
- MARKHUNT — A retain explicit exhaustive dry audit, uncapped vectors,
  evidence threshold, BLOCKED recording/triage brake, resumable manifest,
  no-git truth, accounting and exact closure line. D/G cite entry and ordinary
  checkpoint. F remove prior-pass narrative after accounting invariants remain.
- CLEAN — A retain recovery proofs, five-file mass cap, reference sweep,
  HUNT boundary, user-data confirmation, dependency-safe board scrub, kitchen
  protection, LOG sealing, journal compaction and converge exit. B/C/G cite
  generic destructive/effect/checkpoint law. F remove incident narratives.

## MAINTENANCE cross-clean target

After phase deltas stabilize, keep MAINTENANCE as owner of halt/autonomous
routing, intent/caps, HUNT-to-ADD/CLEAN routing, goal waves and maintenance
policy. Remove its duplicated ADD pseudocode and phase-local procedure; phase
files retain their own action mechanics. Do not create a shared phase document.

## Implemented result

Final measured phase corpus: **42078 bytes** (baseline 100304; reduction 58226,
58.1%). All 16 registered files remain. Largest phase is SHIP at 6250 bytes;
median is 2409 bytes and maximum is 6250 bytes. Exact phase bytes:

`INIT 1677; PLAN 1827; SCOUT 748; BUILD 1414; VERIFY 4725; REVIEW 1457;
SHIP 6250; DONE 1147; BLOCKED 684; VALIDATE 1232; HUNT 3098; MARKHUNT 3212;
ADD 3136; CLEAN 3801; TRANSLATE 4679; PREPARE 2991`.

The preferred 72000-byte target is met, so no semantic-floor variance is
needed. Preferred per-phase bands remain non-enforced migration indicators:
several files safely fell below them because canonical-owner references made
the unique delta smaller; no padding was added.

MAINTENANCE now owns only halted-board/autonomous routing, intent-aware clean
HUNT destinations, goal lifecycle/caps, reauthorization and Industrial
Completion. ADD selection/routing/accounting is owned by `phases/add.md`;
CLEAN, MARKHUNT and TRANSLATE local procedure exists only in their phase docs.

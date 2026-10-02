# FUTURE GATE — CORE MAINTAINER AUDIT FINDINGS

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Gate: **do not start any finding below while T-1316 (P0, SRC-027 recovery
reconciliation) is the DOING ticket.** These were verified against the SAIPEN
8.0.1 tree and are recorded so they are not lost, not so they are done now.

This document is a record of an external maintainer audit. It is not a claim
that any finding has been fixed, and it must not be cited as evidence for a
coverage disposition.

## OBJECTIVE

Remove protocol friction that encourages agents to fabricate lifecycle state,
reduce unnecessary coupling to wall-clock and prose bytes, and dismantle
validator monolith risk without weakening fail-closed semantics.

Explicitly **not** one large refactor. Each finding is bounded and separately
gated by its own red control.

## FINDING A — CLOSURE AND PUBLICATION ARE OVERLOADED

Verified facts:

* `saipen/REGISTRY.json` defines `VERIFY -> REVIEW`, `REVIEW -> SHIP`,
  `SHIP -> DONE`.
* `VERIFY -> DONE` and `REVIEW -> DONE` are absent.
* `tools/saipen_engine/operations.py` `finish_ticket` refuses every closure
  unless the live phase is `SHIP`.
* `MANUAL-VERIFY RESULT: PASS` satisfies verification evidence but provides no
  closure authority.
* `saipen/phases/ship.md` states PUBLISH is an action rather than a phase, yet
  ordinary local/no-publish closure is still forced through phase `SHIP`.

Do **not** solve this by blindly adding `VERIFY -> DONE`; that would bypass
independent REVIEW authority as well as publication.

Target design: separate ticket completion from publication. Prefer a bounded
local closure path after REVIEW (`REVIEW -> DONE`) only when an explicit
non-publishing closure policy authorizes it and all closure evidence is present.
That path must require: completed VERIFY evidence; completed REVIEW evidence;
regression-oracle evidence when required; no open attempt; canonical core
validation; atomic BOARD/STATE/LOG closure; `transition_from` equal to the
actual source phase; zero fabricated SHIP evidence.

Publishing remains a separate explicit operation. An agent must never be able
to manufacture `transition_from: SHIP` merely to satisfy the DFA.

Required hostile tests: direct VERIFY closure stays refused unless a separately
specified protocol mode deliberately owns that reduced gate chain.

## FINDING B — WAIT GRAMMAR IS TOO BRITTLE, AND IDLE CHANGES POLICY

Verified facts:

* `wait_grammar_error` requires the literal delimiter `" -- "`.
* `WAIT: idle` is not a registered category.
* `DONE` with an empty TODO list currently allows only the contextual
  safety-valve, user-brake and MARKHUNT brakes.
* Otherwise the zero-prompt rule routes the system toward `HUNT -> ADD`.

Target design: add separator normalization at the parsing boundary — accept at
least canonical `--` and Unicode em dash forms with surrounding whitespace
variation, then persist one canonical representation. Do not silently broaden
arbitrary free-form WAIT text.

If an idle state is added it must be defined semantically, not as parser sugar.
Recommended contract: `WAIT: idle -- <reason>` is legal only when no ticket is
DOING, no workable TODO exists, no unresolved automatic continuation is
available, and no active goal/converge intent requires HUNT/ADD continuation.
Active autonomous goal execution must not be allowed to deadlock itself using
idle.

Update registry, shared state parser, router, validator, docs and hostile
scenarios from one authority.

## FINDING C — WALL CLOCK HAS TOO MUCH AUTHORITY OVER THE LEDGER

Verified facts:

* `tools/validate.py` uses `LOG_CLOCK_SLACK = 300`.
* `tools/_log_append.py` uses `CLOCK_SLACK_SECONDS = 300`.
* conformance receipt validation uses `MAX_CLOCK_SKEW_SECONDS = 300`.
* The actual immutable-ledger ordering contract in `saipen_engine/log.py` is
  already based on strictly increasing E-IDs and parent E-ID relationships.

Do **not** mechanically replace every 300-second constant with 900 seconds.
Separate clock policies by purpose:

* **Ledger ordering** — E-ID and parent graph are authoritative; timestamp
  inversion/future skew must not redefine event order; modest wall-clock skew
  should produce repairable diagnostic state rather than blocking an otherwise
  structurally valid event graph; impossible dates and extreme fabricated
  timestamps remain hard failures.
* **Evidence freshness** — conformance and other time-expiring receipts may
  retain a stricter clock-skew policy because wall time is semantically
  relevant there.

Define each policy once, in the registry or one shared clock-policy module, not
as repeated independent numeric constants. Add tests with 6-minute, 14-minute
and gross future skew proving the intended distinction.

## FINDING D — STYLE CONTRACT BINDS STATE TO COPY-EDIT BYTES

Verified facts:

* `tools/saipen_engine/state.py` computes `style_contract` by SHA-256 hashing
  almost the complete `STYLE.md` body and taking the first eight hex characters.
* A punctuation-only edit changes the required STATE marker. Observed example:
  `ded-4ae736e4 -> ded-0dd2c624`.
* Non-semantic documentation edits therefore invalidate otherwise valid
  checkpoints.

Target design: `STYLE.md` owns an explicit semantic style version; STATE records
that version. A content digest may remain as **non-binding** diagnostic
evidence, but punctuation, whitespace, spelling or explanatory prose changes
must not invalidate project state. A semantic change to reply-language rules,
voice policy or artifact behavior must require an explicit version increment.

Migration from the existing `ded-<hash>` form must be backward-readable and
journaled at the next canonical checkpoint rather than requiring mass historical
rewrites.

## FINDING E — VALIDATE.PY IS AN ORCHESTRATOR, POLICY ENGINE, HISTORY MUSEUM AND REGRESSION SUITE IN ONE FILE

Measured on the supplied file:

* 10,526 lines
* 309 top-level statements
* 329 `fail()` call sites
* 125 `warn()` call sites
* approximately 153 cross-document drift references

Do not create a second set of schema/transitions/board/log authorities. Existing
engine modules already include `state.py`, `board.py`, `log.py`, `phases.py`,
`closure.py`, `ownership.py` and `conformance.py`.

Desired end state — `tools/validate.py` keeps only: CLI argument handling,
snapshot acquisition, calling authoritative validators, aggregating structured
findings, rendering output, exit code. Engine modules own pure policy decisions,
structured finding/result objects, and no duplicate regex interpretations remain
in `validate.py`.

Migration must be behavior-preserving first. For every extracted rule: capture
current green and red controls; move the authority; make `validate.py` delegate;
prove identical verdict/code/evidence; remove the duplicate implementation; only
then consider retiring historical warning rules. Do not delete historical
warnings merely because they are old — delete or demote a rule only when its
underlying invariant is enforced elsewhere and a red control proves removal does
not reopen the defect.

## ADDITIONAL OBSERVATION — DIAGNOSTIC OUTPUT CAN CRASH ON A NON-ENCODABLE PATH

The supplied archive triggered `UnicodeEncodeError` while `validate.py` was
rendering a failure containing a filesystem path with surrogate characters. The
archive representation may be responsible for creating that filename, so the
malformed name itself is **not** attributed to the live repository without
native evidence.

The validator behavior is still undesirable: reporting an invalid path must not
crash the validator. Make diagnostic rendering encoding-safe with
escaped/backslash-replaced path representation and add a regression containing a
hostile filename.

This one is marked in the source audit as eligible to be taken earlier as an
isolated low-risk patch. It is still not taken now, because it touches
`validate.py` while T-1316 holds the DOING seat.

## RECOMMENDED BOUNDED ORDER (AFTER T-1316 CLOSES)

1. style-contract semantic versioning
2. closure/publication separation while preserving REVIEW authority
3. clock-authority separation
4. WAIT normalization and contextual idle semantics
5. incremental `validate.py` authority extraction
6. diagnostic Unicode hardening (may be taken earlier as an isolated patch)

## NON-GOALS

* no `VERIFY -> DONE` shortcut that silently removes REVIEW
* no global replacement of 300 seconds with 900 seconds
* no free-form WAIT grammar
* no second parallel validator architecture
* no one-shot rewrite of `validate.py`
* no feature work mixed into the maintenance campaign
* no historical LOG or BOARD rewriting to make new rules appear clean

## ACCEPTANCE PRINCIPLE

The result must reduce false protocol failures without weakening the properties
SAIPEN exists to provide: one canonical state; one real active ticket; monotonic
event authority; truthful transition provenance; fail-closed mutation;
restartable cold-state recovery; no closure claim without evidence.

The maintenance work is successful only if agents need fewer ceremonial lies
while the machine has at least as much ability to reject an actual lie.

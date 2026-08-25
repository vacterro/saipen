# SAIPEN OPS — the mechanical execution layer

OPS owns HOW protocol state is committed safely, never WHAT it means. It is the
contract for SAIOPS, the zero-dependency Python mechanical layer that performs
deterministic protocol operations agents currently do by hand-editing
STATE.md / BOARD.md / LOG.md.

The division of labour:

```
PROSE DEFINES WHY.      the phase docs / CORE define reasoning and checks
LLM DECIDES WHAT.       ticket choice, classification, severity, intent
PYTHON DEFINES HOW.     SAIOPS commits the decided representation safely
TESTS PROVE THE RESULT. red controls + crash injection + full gates
```

OPS does NOT restate phase semantics, the Pick Rule, HUNT, CLEAN, Improve, or
SubSaipen semantics. Those live where they already live. OPS owns only the
mechanical contract below.

## 1. Semantic / mechanical boundary

LLM owns decisions requiring understanding: choose the correct ticket, classify
a defect, determine severity, write ticket prose, decide whether evidence
proves something, choose architecture, interpret user intent, decide which
USERPERSON preferences are semantically relevant, decide whether a new task is
necessary.

Python owns deterministic mechanics: resolve project, parse STATE/BOARD/LOG,
allocate event IDs, generate timestamps, validate transition legality, move
ticket between sections, set checkbox/owner/claim_time/task/next_action/
transition_from/last_event/counters, append LOG, preserve formatting, lock
writer, journal operation, recover interrupted operation, validate result,
reject stale input.

Never put fuzzy reasoning into Python pretending it is deterministic.
`should_this_bug_be_P1()` is forbidden; `create_ticket(priority="P1")` is the
shape. The model chooses, Python records.

## 2. Operation lifecycle

Every mutating operation is PLAN / APPLY separated around one immutable
OperationPlan.

PLAN:

1. read a ProjectSnapshot (state_hash, board_hash, log_hash, log tail E-ID,
   HEAD where Git exists);
2. validate the semantic request (ticket exists, needs, binding, legal
   transition, lifecycle source);
3. compute ALL intended final bytes in memory, encoding/BOM/newline already
   applied (the codec preserves representation; the journal stores EXACT
   bytes);
4. validate the IN-MEMORY proposed STATE/BOARD/LOG (fast cross-file
   invariants);
5. return the OperationPlan with its stable op_id, semantic_payload_hash,
   preconditions and ordered targets -- writing ZERO bytes.

`--dry-run` calls PLAN and renders it. Nothing else.

APPLY consumes THAT plan object under the writer lock:

1. acquire the project writer lock (real OS lock, `.saipen/locks/core.lock`);
2. run Recovery preflight first (unfinished op journals) -- exactly one
   unambiguous recoverable op is recovered first; a conflict or multiple
   pending ops REFUSE before any new mutation;
3. re-read every declared precondition under the lock; compare; refuse
   STALE_STATE;
4. compute each target's before_hash (live file) and after_hash (planned
   bytes); journal PREPARED with those hashes and the staged final bytes;
5. apply targets in the plan's declared order; journal progress per target;
6. re-read all affected files; verify exact bytes AND fast cross-file
   invariants; only then journal VERIFIED;
7. journal COMMITTED; release the lock.

The plan's op_id is the applied op_id; the plan's bytes are the committed
bytes; the plan is never recomputed during APPLY. A retry of a committed op
returns ALREADY_APPLIED.

The LOG -> BOARD -> STATE order is preserved for canonical Core checkpoints
(TransactionPolicy.CORE_CHECKPOINT): LOG ahead of STATE after a crash is
recoverable. Single-file Improve writes use TransactionPolicy.ATOMIC_FILE:
one ordered target. Multi-file atomicity is NOT claimed: there is no atomic
multi-file primitive. The write-ahead journal is the truth about how far a
crash got.

## 3. Transaction / recovery behavior

The journal is GENERIC: every target is identified by path + role (log,
board, state, manifest, report, sweep, generic), never by its position in the
target list. A MANIFEST is never reported as LOG_WRITTEN.

### Lifecycle vocabulary (NITRO dogfood II)

Operation statuses split into two closed classes:

- **SETTLED** (`COMMITTED`, `ABORTED`): the operation owns no further
  mutation state. Recovery may not act; a committed retry returns
  ALREADY_APPLIED.
- **UNRESOLVED** (`PREPARED`, `APPLYING`, `VERIFIED`, `CONFLICT`): the
  operation still owns mutation state that must be resolved before any new
  canonical mutation.

CONFLICT is stable evidence but NOT permission to continue. `pending_ops()`
lists every UNRESOLVED journal; `pending_conflicts()` lists the CONFLICT
subset. Before ANY mutation, an unresolved CONFLICT REFUSES
RECOVERY_CONFLICT naming the exact op -- no new canonical mutation may start
over a conflict. `saipen status` / `saipen next` surface recovery_pending and
recovery_conflict; `saipen recover` on a conflict REFUSEs with the op named
and evidence preserved.

Evidence that cannot be decoded or safely traversed is `CORRUPT_JOURNAL`,
not CONFLICT: preflight, mutation, recovery, release, status, next, and
read-only context all refuse with that exact code and preserve the structured
detail. Corrupt evidence is never constructed as a Journal and never replayed
automatically.

### Recovery

Recovery is ROLL-FORWARD and CONFLICT-SAFE. LOG is append-only evidence; once
the operation's LOG event exists, do not "rollback" by deleting it.

Per unfinished target:

- current hash == before_hash: apply the staged planned bytes;
- current hash == after_hash: already applied; advance;
- anything else: CONFLICT. Preserve journal + staged bytes, write nothing
  further, refuse to guess.

Per already-applied target the live bytes MUST equal after_hash; otherwise the
applied work was overwritten: CONFLICT.

Every journal records a `verification_policy` from a closed registry
(core_fast / improve_atomic_file / userperson / sub_lifecycle / none) and the
READ-ONLY preconditions the original plan read but did not write. Recovery:

1. rechecks every READ-ONLY precondition against the plan's allowed state --
   a changed read dependency is CONFLICT (the plan is no longer the authorized
   decision), never rolled forward over;
2. applies/validates each unfinished target (staged bytes MUST hash to the
   planned after_hash);
3. byte-verifies every written target;
4. reruns the operation's registered semantic verifier (the SAME postcondition
   class the original APPLY ran) -- a semantically invalid recovered state is
   CONFLICT, never VERIFIED/COMMITTED.

"VERIFIED" on the recovery path means the verifier actually ran and passed.

Before ANY new mutation, `pending_ops` journals are scanned (Recovery
preflight):

- corrupt recovery evidence exists -> refuse CORRUPT_JOURNAL before replay;
- an unresolved CONFLICT exists -> refuse RECOVERY_CONFLICT naming the op;
- none pending -> proceed;
- exactly one recoverable -> recover/complete it first;
- recovery hits conflict -> refuse, evidence preserved;
- multiple unresolved -> refuse RECOVERY_REQUIRED naming the exact op_ids.

`saipen recover` lists pending operations and recovers the mechanically safe
ones; it refuses a conflict rather than hiding it. Repeated recovery is
idempotent.

## 4. Idempotency

Every mutating operation carries an op_id owned by its journal. A retry after
client/model/process failure must not duplicate ticket movement, LOG events, or
counter increments. Before applying, check the op journal: already COMMITTED
returns ALREADY_APPLIED with the original result; interrupted operations are
recovered first. Never create a second equivalent operation while an unresolved
first one exists.

## 4a. Mechanical provenance

Every SAIOPS structural operation writes its LOG event WITH its op_id as an
`[op: <op_id>]` marker: claim, transition, checkpoint, ticket lifecycle, goal
pivot, valve reauthorization, stop. Ordinary semantic LOG entries carry no
marker.

The migration boundary is self-establishing: the first event in a project's
LOG history that ever carries an `[op: ...]` marker. Every structural event
at/after that boundary MUST carry one. The validator's `[saio]` check fails a
structural SAIOPS-owned event after the boundary that lacks `[op: ...]`, so a
manual structural edit that bypassed the engine is detectable and reported.
Pre-boundary history is exempt (append-only, cannot be rewritten).

In `mode: full` with Python available, covered maintenance MUST use SAIOPS;
manual structural editing is FALLBACK / RECOVERY ONLY and must record why the
mechanical path was unavailable.

## 5. Locks

One project-local lock file, `.saipen/locks/core.lock`, using real OS file
locking (msvcrt on Windows, fcntl on POSIX). The lock file carries no canonical
truth. Process death releases the OS lock. All Core-mutating operations acquire
the same canonical project lock; read-only operations do not. Project path
aliases resolve to the same lock identity.

## 6. Dry-run

Every mutation supports `--dry-run`: it acquires no mutation ownership, computes
the planned result, validates it, prints affected files and structural
before/after, and writes zero canonical bytes.

## 7. Operation result shape

Every operation returns a structured result:

```
{
  "ok": true, "code": "CLAIMED", "op_id": "...",
  "changed_files": [...], "event_id": "E-2437", "ticket": "T-551",
  "phase": "SCOUT", "next_action": "PHASE SCOUT T-551",
  "recovery_required": false
}
```

CLI prints concise human text by default; `--json` emits JSON only. Stable
error codes: STALE_STATE, TICKET_NOT_FOUND, TICKET_NOT_WORKABLE,
TICKET_ALREADY_DONE, ILLEGAL_TICKET_LIFECYCLE, NOT_TOP_WORKABLE,
ACTIVE_TICKET_MISMATCH, ALREADY_CLAIMED, ACTIVE_CLAIM_FOREIGN, ILLEGAL_TRANSITION,
ILLEGAL_PHASE, WRITER_BUSY, VALIDATION_FAILED, RECOVERY_REQUIRED,
RECOVERY_CONFLICT, CORRUPT_JOURNAL, DESTRUCTIVE_CONFIRMATION_REQUIRED, CONFLICT,
NEEDS_REPAIR, PATH_ESCAPE, INVALID_ID, ACTIVE_IMPROVE_CYCLE,
INVALID_DISPOSITION, PACKAGE_INCOMPLETE, MALFORMED_PACKAGE,
INCOMPLETE_TICKET, INVALID_MANIFEST, INVALID_GOAL, STALE_PLAN, RELEASE_CLOSURE_PENDING,
TAG_CONFLICT, FIRST_PUBLISH_WAIT, NO_PUBLISH_MODE,
SOURCE_SCOPE_MISSING, RELEASE_FAILED. `HOME_REQUIRED` is the crew refusal
when STATE.saipen_home is missing or unusable -- the executable next action
is `saipen rebind-home <candidate>`: the ONE mechanical rebind path that
proves the candidate install (readable `VERSION`, compatible major, `BOOT`
layout, required protocol files) and journals a single narrowly-owned
`STATE.saipen_home` pointer update (T-1003 carrier-loss wave). `CREW_BLOCKED` is the EXPECTED crew
result when the circuit has no executable semantic continuation (an
unsatisfied stage needs inspection, not invention): the result carries the
unsatisfied `stage`/`role`/`reason` and an inspect-required next action --
a legitimate crew blocker is a structured result, never a traceback.
`CREW_NOT_READY` is the release executor's refusal when the human explicitly
asks to publish while the crew epoch is not terminal: an ordinary ticket under
an active crew epoch is DEFERRED to the crew (never silently published), and a
terminal publication requires SC-0..SC-10 all explicitly satisfied -- missing
evidence is never PASS (T-1003 hostile findings 3/4/6).
`INVALID_SOURCE_HOME` is the shared-contract refusal when the configured
saipen_home is missing any REQUIRED source item (PROTOCOL.md/README.md/
crew.md, the complete TEMPLATE surface, or any built-in role charter):
zero writes, zero obsolete deletion, and the operator refreshes the install.
Error messages name one exact
refusal and the executable next action. `RELEASE_FAILED` is the single stable
code every public release refusal that is not a named preflight gate
collapses to (subprocess/staging/commit/push/tag/receipt failures): the
diagnostic stage and the underlying error stay in the result's `detail` /
`stage` fields, never as new global codes. `ILLEGAL_PHASE` is the gate refusal:
`finish_ticket` (the atomic ticket-closure operation behind `ticket done`)
accepts a ticket only from `phase: SHIP` (the canonical SHIP -> DONE closure
edge); from SCOUT/BUILD/VERIFY/REVIEW it REFUSEs ILLEGAL_PHASE and writes
zero canonical bytes, because a ticket whose required gates did not run must
not be laundered into a legal-looking DONE state (NITRO dogfood IV, T-602).

COMMIT FAILURE ALWAYS WINS: a failed commit returns its own refusal
(STALE_STATE / RECOVERY_REQUIRED / CONFLICT / WRITER_BUSY), never the plan's
semantic success metadata. WRITER_BUSY is a structured result, not a
traceback.

## 8. Fallback

Python is the preferred mechanical path under `mode: full`. If Python is
genuinely unavailable, use the documented manual protocol as compatibility
fallback, state that mechanical enforcement was unavailable, and run available
validation afterwards. A repository must remain readable without an executable
environment: canonical files are the cold truth, never a cache or engine state.

## 9. Effect-based authorization (T-1160, INC-PERMISSION-EFFECT-BYPASS-001)

AUTHORIZATION FOLLOWS EFFECT, NOT TOOL IDENTITY. The law lives in CORE § 1.10's
host-agent rules; this section owns the deterministic vocabulary and mechanics.

**Closed effect vocabulary** (`tools/saipen_engine/effects.py`): `fs.read`,
`fs.write`, `fs.delete`, `repo.read`, `repo.mutate`, `process.execute`,
`network.read`, `network.write`, `external.mutate`. Mutating effects:
`fs.write`, `fs.delete`, `repo.mutate`, `network.write`, `external.mutate`.
Extending the set is a protocol change, not a code edit.

**Three separated concepts.** POLICY = what is authorized (derived from the
negotiated session capability by default; a project may tighten it through an
optional bounded `.saipen/policy.json` mapping effect -> ALLOW|MANUAL|DENY --
tightening never loosens). ENFORCEMENT = what the host prevents: UNAVAILABLE
unless declared via `SAIPEN_HOST_ENFORCEMENT` (`none`, `tool-conventions`,
`sandbox-readonly`); SAIPEN never claims a sandbox it cannot see, and a
MANUAL/DENY policy over a non-STRONG host surfaces as ENFORCEMENT_GAP.
AUDIT = what SAIPEN observes: cheap read-only Git worktree deltas
(`tree_snapshot`/`tree_delta`, porcelain only -- index/stash/HEAD untouched;
no Git means status UNAVAILABLE, never a fabricated clean bill).

**Tool contracts.** POSSIBLE != REQUESTED != OBSERVED. A dedicated edit tool
guarantees `fs.write`; a shell/interpreter POSSIBLY exercises anything and is
therefore never "read-only because the command looked harmless". Possible
effects are capability metadata for humans and diagnostics -- never proof.

**Coverage evaluation** (`evaluate_coverage`) answers one question
mechanically: WHAT AUTHORIZATION COVERS THIS OBSERVED EFFECT? DENY fails
closed; MANUAL requires a scope-bound Approval naming the exact EFFECT
(optionally paths, Work, Attempt; one-shot unless reusable); an
`fs.write` approval implies `repo.mutate` of the same paths and NOTHING else
-- a `process.execute` approval never promotes to `fs.write`. Declared-but-
absent or observed-but-undeclared effects are EFFECT_DRIFT (review trigger,
never silently absorbed). Verdicts are mechanical facts:
AUTHORIZED / AUTHORIZATION_MISSING / SCOPE_MISMATCH / EFFECT_DRIFT -- they
say nothing about intent.

**Provenance** uses KNOWN/UNKNOWN/UNAVAILABLE literally: paths from observed
delta are KNOWN; originating process UNKNOWN without durable evidence;
pre-existing dirt and concurrent external edits are never attributed to the
active Attempt. Mutation evidence remains separate from validation, review,
and completion evidence.

**Diagnostic**: `saipen permissions` (READ_ONLY, `--json` capable) prints
policy + source + overrides, host enforcement truth, gaps, tool contracts,
and the current worktree delta.

## 10. Self-resolving gates (T-1161)

The law lives in CORE § 1.10's host-agent rules (No Human Courier; Validator
Is a Sensor; Ship Means Converge; Traceability Is Not Optional). This section
owns the deterministic mechanics in `tools/saipen_engine/disposition.py`.

**Closed disposition vocabulary**: `EXECUTE_SELF`, `RECONCILE_SELF`,
`WAIT_USER`, `WAIT_EXTERNAL`, `BLOCKED`, `COMPLETE`, `INVALID`.
`classify_carrier()` maps the fields SAIPEN carriers ALREADY emit
(`execute_in_current_agent`, `requires_human`, `terminal`, `crew_complete`,
`next_action`, stable refusal codes) onto exactly one disposition. It never
derives WAIT_USER from optionality: only an explicit `requires_human: true`
or a human-boundary WAIT category (`user brake`/`manual-verify`/
`destructive-op`/`first-publish`) yields it. `blocked`/`safety valve` WAIT
categories classify as BLOCKED -- they are not user questions. STALE +
refreshable classifies EXECUTE_SELF, never BLOCKED.

**User-wait proof obligation**: `user_wait_proof()` fails any WAIT_USER whose
proof is incomplete -- `missing_authority`, `evidence_insufficient`,
`consequence`, each a substantive sentence fragment. "Need user decision" is
not a proof.

**Traceability reconstruction**: `reconstruct_traceability()` passes an
umbrella ticket ONLY when every source finding carries its own disposition,
evidence, and explicit verification (`verified` / `rejected-with-evidence` /
`duplicate-of`) and the ticket durably references every finding ID.
FINDING_VALIDITY != EVIDENCE_FRESHNESS.

**Diagnostic**: `saipen explain-next` (READ_ONLY, `--json`) routes the same
next action as `next`/`cc` WITHOUT executing and reports the disposition,
the owner (agent/user), the selected action, and why the human is or is not
required. Decision-trace output for debugging autonomy; writes nothing.

**Meaningful automatic reconciliations** (state repaired against authority,
stale evidence regenerated, traceability reconstructed) are recorded through
the existing LOG DEC convention so a cold agent can answer "why did STATE
change from X to Y?" without chat history. Trivial formatting is not logged.

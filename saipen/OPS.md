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

Recovery is ROLL-FORWARD and CONFLICT-SAFE. LOG is append-only evidence; once
the operation's LOG event exists, do not "rollback" by deleting it.

Per unfinished target:

- current hash == before_hash: apply the staged planned bytes;
- current hash == after_hash: already applied; advance;
- anything else: CONFLICT. Preserve journal + staged bytes, write nothing
  further, refuse to guess.

Per already-applied target the live bytes MUST equal after_hash; otherwise the
applied work was overwritten: CONFLICT.

Before ANY new mutation, `pending_ops` journals are scanned (Recovery
preflight):

- none pending -> proceed;
- exactly one recoverable -> recover/complete it first;
- conflict -> refuse, evidence preserved;
- multiple unresolved -> refuse RECOVERY_REQUIRED naming the exact op_ids.

`saipen recover` lists pending operations and recovers the mechanically safe
ones. Repeated recovery is idempotent.

## 4. Idempotency

Every mutating operation carries an op_id owned by its journal. A retry after
client/model/process failure must not duplicate ticket movement, LOG events, or
counter increments. Before applying, check the op journal: already COMMITTED
returns ALREADY_APPLIED with the original result; interrupted operations are
recovered first. Never create a second equivalent operation while an unresolved
first one exists.

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
ACTIVE_TICKET_MISMATCH, ALREADY_CLAIMED, ILLEGAL_TRANSITION, WRITER_BUSY,
VALIDATION_FAILED, RECOVERY_REQUIRED, DESTRUCTIVE_CONFIRMATION_REQUIRED,
CONFLICT, PATH_ESCAPE, ACTIVE_IMPROVE_CYCLE, INVALID_DISPOSITION. Error
messages name one exact refusal and the executable next action.

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

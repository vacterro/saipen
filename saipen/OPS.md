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

Every mutating operation:

1. acquire the project writer lock (real OS lock, `.saipen/locks/core.lock`);
2. run Recovery preflight first (unfinished op journals);
3. read a ProjectSnapshot (state_hash, board_hash, log_hash, log tail E-ID,
   HEAD where Git exists);
4. validate preconditions against the snapshot;
5. compute ALL intended final bytes in memory;
6. run fast validation on the proposed state;
7. write the journal PREPARED;
8. write LOG by temp + replace; journal LOG_WRITTEN;
9. write BOARD by temp + replace; journal BOARD_WRITTEN;
10. write STATE by temp + replace; journal STATE_WRITTEN;
11. re-read all affected files; run fast cross-file invariants; journal
    VERIFIED;
12. mark COMMITTED; release the lock.

The LOG -> BOARD -> STATE order is preserved because LOG ahead of STATE after a
crash is recoverable. Multi-file atomicity is NOT claimed: there is no atomic
multi-file primitive. The write-ahead journal is the truth about how far a
crash got.

## 3. Transaction / recovery behavior

Recovery is ROLL-FORWARD after LOG. LOG is append-only evidence; once the
operation's LOG event exists, do not "rollback" by deleting it.

- PREPARED: if no canonical target changed, ABORT safely.
- LOG_WRITTEN: if hashes prove the planned operation is still valid, roll
  BOARD + STATE forward.
- BOARD_WRITTEN: roll STATE forward.
- STATE_WRITTEN: validate and mark committed.
- Unexpected target hash: CONFLICT. Preserve evidence, refuse to guess.

This encodes the existing CORE section 1.5 recovery model into code. Repeated
recovery is idempotent.

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
ALREADY_CLAIMED, ILLEGAL_TRANSITION, WRITER_BUSY, VALIDATION_FAILED,
RECOVERY_REQUIRED, DESTRUCTIVE_CONFIRMATION_REQUIRED, CONFLICT. Error messages
name one exact refusal and the executable next action.

## 8. Fallback

Python is the preferred mechanical path under `mode: full`. If Python is
genuinely unavailable, use the documented manual protocol as compatibility
fallback, state that mechanical enforcement was unavailable, and run available
validation afterwards. A repository must remain readable without an executable
environment: canonical files are the cold truth, never a cache or engine state.

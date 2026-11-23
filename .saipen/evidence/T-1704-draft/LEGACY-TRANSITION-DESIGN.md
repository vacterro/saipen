# Narrow legacy-goal authority transition: proposed contract

This is a design for the unimplemented part of T-1704, not an executable
command or an authorization receipt. The current goal remains bounded. No
field, old receipt, goal objective, roadmap or counter was changed by this
design. The existing SRC-112 proof owner must implement and verify it before
it can be invoked.

The current `prove()` requires the persistent quartet's `authority_source`
to name the current goal pivot and the grant journal's operation id to equal
that pivot's operation id. A later instruction cannot satisfy that historical
proof. Rewriting the old goal-entry journal would fabricate original authority.

Introduce one canonical authority-transition operation in `operations.py` and
extend `goal_authority.prove()` to recognize its explicitly committed receipt.
Do not introduce a second authorization engine, a path exception, a maintainer
flag or a self-declared operator identity. Preserve the existing four-field
contract. Keep `authority_source: E-<original pivot>` and put the separate
upgrade event and fresh authorization binding in the transition journal.

The operation must consume a fresh, externally witnessed instruction through
`operator_task`, with exact ingress bytes and their existing digest semantics.
An agent-written file or environment variable cannot supply that witness.
The operator already requested autonomy; the host still needs to transport
that genuine instruction rather than ask the model to declare its origin.

Bind the new receipt to the canonical portable project lineage, original pivot
event and operation, original objective/ingress when available, complete frozen
history, and the fresh authorization's ingress identity and provenance. Require
explicit authority to persist until completion of precisely that goal. The
instruction must not be inferred from a path, agent name, imported audit,
model-supplied Source, transport obligation or unrelated operator request.
If the original objective cannot be recovered and bound unambiguously, refuse
the transition rather than guess it from the current ticket or broad shorthand.

Use the existing single `_read` snapshot, `OperationPlan`, writer lock,
preconditions and journal/recovery path. The atomic delta appends an explicit
authority-upgrade DEC and records the quartet and ingress binding. It preserves
BOARD, active task, exact phase/transition, owner and evidence. It does not reset
the counters. A subsequent proved checkpoint spends the standing grant through
`reauthorize_valve`, with its own safety review and old/new counter record.

Proof must require the transition's committed journal, matching LOG operation
and event, unchanged original pivot and objective, same project lineage and
fresh operator ingress. Replay for a different goal or project must refuse.
Replay of the already committed identical transition must return its original
result without a new grant, event or counter reset. Crash recovery must replay
the exact prepared bytes and fail on changed read dependencies. Missing,
corrupt, revoked or conflicting authority must fail closed.

Expose bounded/persistent/invalid authority and the original event through
existing status/explain surfaces. A revocation or goal replacement must make
the prior proof unusable. Preserve all existing real safety brakes and the
iteration owner's no-progress and failure limits; this operation cannot
convert a runtime or human-required STOP into automatic continuation.

Before admission, test fresh upgrade, model/import/forgery refusal, replay,
project isolation, incomplete history, corrupt/missing journals, writer conflict,
crash recovery and idempotence. Then test upgraded T-1703 REVIEW at 0/20 through
the existing checkpoint path and native validator. Those tests have not been
implemented or claimed as passing by this draft.

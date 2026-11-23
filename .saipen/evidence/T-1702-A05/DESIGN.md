# SRC-205 A05 prepared repair boundary

This is read-only reconnaissance while T-1713 owns VERIFY, not T-1714 BUILD.
T-1714 is already the linked R005 Work and waits for the existing T-1713 queue
reservation. The live tree remains frozen for the current declared family.

preflight.json executes the actual documented launcher against one healthy
repository-owned fixture and the same fixture after a deliberately invalid
missing-parent event. Healthy status/recover-preview/next all exit 0. Corrupt
status and next exit 1 with VALIDATION_FAILED and action `saipen recover`;
recover-preview exits 1 with HISTORY_LEDGER_CORRUPT and
FORENSICALLY_UNRECOVERABLE/no canonical_next_command. Both canonical triplets
remain unchanged. Actual original/recovery AUDAPACK roots were not touched.

The existing owners explain the mismatch: router.route_next sees checkpoint
errors and always returns recover; CLI _status and _route_once expose it. The
real reconcile.reconcile_protocol_state already owns a more precise refusal.
operations._read raises typed HISTORY_LEDGER_CORRUPT, and reconcile uses
_foreign_tail_route plus _blocked_recovery_fields to distinguish a genuinely
provable quarantine from unreconstructable history. Reuse that exact decision;
do not infer terminality from diagnostic prose or build a parallel classifier.

Prepared candidate implementation: extract the existing typed ledger refusal
assembly within reconcile.py, reuse it in recover and refine only an already
invalid checkpoint/lifecycle projection by asking reconcile_protocol_state's
actual read-only preview. That preview retains manifest-runtime preflight,
bound-home conditions, other error precedence and the existing quarantine
proof. Healthy routing does not add any strict history read or traversal.
route_next's pure interface and the generic route for genuinely repairable
checkpoint classes remain intact. Explain-next keeps its successful explanation
wrapper, while its actual blocked carrier carries the precise decision.

Initial owned candidate scope: reconcile.py, tools/saipen.py and existing
test_reconcile_history_ledger_blocked.py (or a smallest matching existing
neighbor). Do not add a new ledger, INIT, epoch, authorization or mutating API.
The native tests must use the subject CLI derived from the tested source path,
not this live bin/saipen.cmd hardcoded payload when restoring a pre-fix clone.

Required controls: exact missing-parent and duplicate/out-of-order history,
unbacked terminal claims, status/next/recover and continue parity, zero canonical
writes, healthy route, a genuinely repairable checkpoint, and a proven
quarantine route retaining its one executable command. Replay the same fixed
oracle on preserved and corrected subjects. Confirm the reported failure class
against a scratch copy of the real AUDAPACK memory/provenance surface before
claiming downstream applicability; preserve all copy limitations and unrelated
baseline drift. Do not apply anything to either live AUDAPACK root.

Before source application, compare exact pre-images and capture rollback. Cheap
focused/source contracts precede native core, pinned lint/whitespace and the
whole declared family. Current source-generation DONE reverify uses its existing
canonical route if actually stale. Final independent REVIEW and local
no-publish closure remain necessary; R005 stays UNKNOWN until actual proof.

Preliminary red-v3/candidate-v4 hold the same twelve-case oracle. Early invalid
control assumptions (a proven foreign suffix versus corruption inside the bound
history, and explain-next's wrapper success versus carrier refusal) were
corrected from the actual existing recovery owner; their old artifacts remain.
An initial text-decoding harness failure is also preserved, not counted as
subject proof. The current constructor captures raw stdout/stderr and explicitly
sets child UTF-8 output. The expanded thirteen-case oracle additionally checks
that manifest runtime denial keeps the actual recovery owner's precedence.

E-14446's reconnaissance prose said "thirteen-path context" incorrectly. The
actual preparation copied the production tree with root Git/.saipen excluded;
there was no thirteen-path declared execution contract. Three candidate source
paths were preserved. This clarification does not rewrite the canonical event.

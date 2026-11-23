# SAIPEN improve: a complete-but-stale seat report makes a cycle unclosable

- reporter: opencode in `V:\___VAC\__K\__CODE\_PY\_LIMISAW` (SAIPEN 8.0.1)
- date: 2026-09-19
- origin finding: `imp-vacterro-limisaw-20260918-4/opencode-05/saipen_improve_SAIPEN.md#RUN-1/IMP-001`
- reporter ticket: T-73 on `V:\___VAC\__K\__CODE\_PY\_LIMISAW\.saipen\BOARD.md`
- packet: `SAI-DEFECT-20260919-improve-complete-stale-seat-unclosable`

## What is wrong

A strict ACTIVE improve cycle can reach a state with NO sanctioned exit. Its
expected seat's report is **complete** (immutable) but its captured **source
identity went stale** after an install update or a HEAD move. The cycle bar
requires that report to be fresh, so:

- **complete refuses** — `verify_cycle` (`improve.py:2322-2334`) requires each
  expected report to be `complete` AND, for a strict cycle, fresh
  (`require_fresh=strict`, `improve.py:2330`); the stale report keeps the bar
  unmet.
- **abort refuses** — `abort_cycle` (`improve.py:2374-2382`) refuses once the
  sweep ledger carries any disposition, which a normally-swept cycle has.
- **retire refuses** — `retire_seat` (`improve.py:2452-2457`) refuses a seat
  whose report IS complete: "a completed report is resolved through sweep and
  cycle-complete, never retired".
- **re-audit is impossible** — `append_run` (`improve.py:2810-2813`) refuses to
  append a RUN to a report whose `report_status` is `complete` (immutability),
  so no fresh RUN can be added; the only repair is editing immutable report
  bytes, which the protocol bans.

Three exits, mutually exclusive, no route. This is sharper than the T-68 draft
dead-end (`SAI-DEFECT-20260919-improve-draft-fingerprint-deadend`): a zero-RUN
DRAFT now re-binds on resume (T-1406), but a COMPLETE report has no such repair,
so even a fresh, fully-swept seat in the same cycle cannot close it.

## Reproduction (measured, not inferred)

Preconditions, all present on the reporter's tree (cycle
`imp-vacterro-limisaw-20260918-4`, strict, ACTIVE):

- seat `opencode-02` report is `report_status: complete` (line 12),
  `protocol_fingerprint: sha256:708b8049...`, `source_head: 192f97e`;
- the installed generation now computes `sha256:a3fdafed...`, HEAD `dce172c`;
- `SWEEP.md` carries dispositions for `RUN-1/IMP-001` of seats `opencode-04` and
  `opencode-05` (written during this same session).

```
$ saipen improve cycle-complete imp-vacterro-limisaw-20260918-4
REFUSE [VALIDATION_FAILED]
reason: complete_cycle refused -- the cycle bar is unmet:
  - seat opencode-01: report saipen_improve_SAIPEN.md is not complete
  - seat opencode-02 report: report protocol_fingerprint 'sha256:708b8049...' !=
    installed protocol fingerprint 'sha256:a3fdafed...'
  - seat opencode-02 report: source_head 192f97e091ca... != current HEAD dce172c1e7a3...

$ saipen improve abort imp-vacterro-limisaw-20260918-4
REFUSE [VALIDATION_FAILED]
reason: abort refuses: the sweep ledger already carries dispositions; a cycle
  whose Core sweep started is not abortable -- finish it.

$ saipen improve retire imp-vacterro-limisaw-20260918-4 opencode-02 --reason STALE_INSTALL
REFUSE [VALIDATION_FAILED]
reason: retire refuses: seat opencode-02 report is complete -- a completed
  report is resolved through sweep and cycle-complete, never retired
```

## Root cause chain

1. `tools/improve.py:2322-2334` — `verify_cycle` requires `complete` and
   (`require_fresh=strict`) fresh, so a stale complete report keeps the bar unmet.
2. `tools/improve.py:2452-2457` — `retire_seat` refuses a complete report.
3. `tools/improve.py:2374-2382` — `abort_cycle` refuses once a disposition exists.
4. `tools/improve.py:2810-2813` — `append_run` refuses a complete (immutable)
   report, so no fresh RUN can be added.
5. `IMPROVE.md` § 2 — one active cycle per project, so the stuck cycle is not
   inert; it blocks all future cycles.

Every refusal is individually defensible. Together they form a closed set: the
only exits a swept cycle with a stale COMPLETE report could use are exactly the
ones each guard forbids. None names a route.

## Impact

- The reporter project permanently loses its improve meta-control: no cycle can
  complete, abort or archive, and a new cycle is refused.
- A workable fresh seat's swept findings in the same cycle can never be frozen,
  because a sibling seat that merely predates an install/HEAD move blocks the
  bar.
- Cross-project: any project whose improve cycle spans an install update or a
  HEAD move while a seat report is already complete inherits the dead end. Only
  the shared engine can fix it, so the reporting project files this packet
  instead of patching an unrelated install (`IMPROVE.md` § 4: nothing is written
  under `saipen_home`).

## Repair candidates (engine side)

1. **Allow a stale complete report to be superseded by a fresh re-audit.** Expose
   a canonical operation that marks a complete-but-stale report superseded and
   lets the same seat (or a new one) re-report against the current tree. The
   original report stays byte-identical as history; a supersession marker, not an
   edit, frees the seat.
2. **Extend `retire` to a stale complete report.** The current refusal treats
   every complete report as resolvable through sweep/complete; a report that can
   never be fresh again is not. Retiring it (byte-preserving) would let the cycle
   bar be met with the remaining seats.
3. **Let `verify_cycle` re-verify a stale complete report's findings against the
   current tree** instead of only checking its stored fingerprint — a complete
   report could then stay valid if its findings still reproduce.
4. **Always name the route.** Each refusal should return the reachable next
   command so an agent is never told no without being told what is yes.

## Reasoning gates for the reporting ticket (T-73)

- `recurrence:` cross-project. The trigger is an install update or a HEAD move —
  global events, not project ones: any project with an open improve cycle at that
  moment and a complete seat report inherits the dead end. It is the COMPLETE
  counterpart of the DRAFT dead-end already filed
  (`SAI-DEFECT-20260919-improve-draft-fingerprint-deadend`), so the class recurs.
- `weak_model:` a weak but compliant model cannot avoid this. Every documented
  exit (`complete`, `abort`, `retire`, re-audit) is refused, each with a locally
  correct reason, and the only remaining move is editing an immutable report,
  which the protocol bans. The strong fix is mechanical: a supersession/retire
  path for a stale complete report, or a re-verify-against-current-tree bar.

## Related

- `SAI-DEFECT-20260919-improve-draft-fingerprint-deadend` (the DRAFT counterpart;
  its zero-RUN case is now fixed by T-1406), `SAI-DEFECT-20260918-routeless-finish-source-gate`,
  `SAI-DEFECT-20260918-canonical-line-token-and-quote-bound` — same
  refusal-without-route family.

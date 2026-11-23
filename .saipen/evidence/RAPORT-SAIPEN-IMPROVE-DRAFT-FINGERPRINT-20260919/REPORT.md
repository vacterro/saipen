# SAIPEN improve: a stale draft report dead-ends a cycle that can no longer start, finish or abort

- reporter: opencode in `V:\___VAC\__K\__CODE\_PY\_LIMISAW` (SAIPEN 8.0.1)
- date: 2026-09-19
- origin finding: `imp-vacterro-limisaw-20260918-4/opencode-02/saipen_improve_SAIPEN.md#RUN-1/IMP-003`
- reporter ticket: T-68 on `V:\___VAC\__K\__CODE\_PY\_LIMISAW\.saipen\BOARD.md`
- packet: `SAI-DEFECT-20260919-improve-draft-fingerprint-deadend`

## What is wrong

Improve admission mints a seat report mechanically and stamps it with the
identity of the install that minted it:

```
protocol_fingerprint: sha256:<installed protocol fingerprint>
```

That is the correct choice for evidence: a report must not be able to claim an
identity its own install never had. The defect is the consumer, not the stamp.
`validate_bound_report` compares an ACTIVE cycle's DRAFT report against the
installed fingerprint unconditionally, so any install update between admission
and submission permanently disqualifies a report the engine itself wrote.

## Reproduction (measured, not inferred)

Preconditions, all present on the reporter's tree:

- `.saipen/improve/imp-vacterro-limisaw-20260918-4/MANIFEST.md` is a strict,
  ACTIVE cycle with two expected seats (`opencode-01`, `opencode-02`);
- `opencode-01/saipen_improve_SAIPEN.md` is a DRAFT carrying
  `protocol_fingerprint: sha256:f35fadcf37d343c6e6cfcd50bd0309c75c222372dc7fbd6dcbe81fe43cd4a430`;
- the installed generation now computes
  `sha256:708b8049db35cfab5be29b8e818fa0c974832412a7e6122dbe2b2be46bcd95f7`
  (the fingerprint `opencode-02` was minted under, later in the same cycle);
- `SWEEP.md` carries the three Core dispositions for `RUN-1/IMP-001..003`.

```
$ saipen improve verify imp-vacterro-limisaw-20260918-4 --json
{"ok": false, "code": "VALIDATION_FAILED",
 "detail": "seat opencode-01: report saipen_improve_SAIPEN.md is not complete",
 "delta_only": true}

$ saipen improve --session opencode-01 --json
{"ok": false, "code": "INVALID_REPORT", "cycle_id": "imp-vacterro-limisaw-20260918-4",
 "seat_id": "opencode-01", "report_path": ".saipen/improve/imp-vacterro-limisaw-20260918-4/opencode-01/saipen_improve_SAIPEN.md",
 "resumed": false,
 "detail": "session opencode-01 report fails the bound provenance bar: report protocol_fingerprint
  'sha256:f35fadcf37d343c6e6cfcd50bd0309c75c222372dc7fbd6dcbe81fe43cd4a430' != installed protocol
  fingerprint 'sha256:708b8049db35cfab5be29b8e818fa0c974832412a7e6122dbe2b2be46bcd95f7'"}
```

The original submission attempt failed the same way:

```
saipen improve submit imp-vacterro-limisaw-20260918-4 opencode-01 SAIPEN <findings.json>
  -> append_run refuses to extend a malformed strict report: report protocol_fingerprint
     '...f35fadcf...' != installed protocol fingerprint '...708b8049...'
```

## Root cause chain

1. `tools/improve.py:1286-1290` -- `validate_strict_provenance` compares the
   report's `protocol_fingerprint` to the installed one; reached from
   `validate_bound_report` (`:1359`) for an `active` cycle with no exemption for
   a report that has committed no audit content.
2. `tools/improve.py:1831-1868` -- the resume path (`prepare_audit_seat`,
   T-638/§5) requires the same full bound bar before returning
   `ALREADY_ASSIGNED`, so resuming the seat to refresh its draft refuses instead
   of repairing it.
3. `tools/improve.py:2155` inside `verify_cycle` (`:2114-2170`) -- any expected
   seat whose report is not `complete` fails the bar. `complete_cycle` (`:2245`)
   runs `verify_cycle` and cannot be satisfied.
4. `tools/improve.py:2175` (`abort_cycle`) -- refuses as soon as the sweep ledger
   carries a disposition, which it does after any normal sweep.
5. `saipen.py:6305` -- `improve clean` archives only a COMPLETE cycle, and
   `archive_cycle` enforces it.
6. `IMPROVE.md` § 2 -- one active cycle per project, so the stuck cycle is not
   merely inert; it blocks all future cycles.

Every one of those refusals is individually defensible; together they form a
closed set with no reachable exit, and none of them names a route. The two exits
that do exist (`abort` before the sweep, or discarding the seat and re-minting)
are exactly the ones a cycle with completed dispositions cannot use.

## Impact

- The reporter project cannot audit itself: no cycle can complete, abort or
  archive, and a new cycle is refused.
- An install update destroys publishable audit evidence the engine itself
  minted, through no action of the seat.
- Cross-project: any project whose improve cycle spans an install update
  inherits the dead end. Only the shared engine can fix it, so the reporting
  project files this packet instead of patching an unrelated install
  (`IMPROVE.md` § 4: nothing is written under `saipen_home`).

## Repair candidates (engine side)

1. **Re-bind an un-audited draft.** On resume (or on a new explicit `repair`),
   if the DRAFT has no committed `## RUN` section, re-derive the provenance
   header from the installed protocol and journal the change. Nothing has been
   audited yet, so no evidence is rewritten.
2. **Retire a dead expected seat.** A canonical roster operation that marks a
   seat whose report never reached `complete` as superseded/unavailable lets the
   cycle bar be met without a raw manifest edit.
3. **Always name the route.** Each refusal above should return the reachable
   next command (`repair`, `retire seat`, `abort`) so an agent is never told no
   without being told what is yes.

## Secondary claim (same session, for triage)

`IMPROVE.md` § 13 requires a protocol-level ticket (a `PROTOCOL_VIOLATION`
finding that produced a ticket) to carry `recurrence:` and `weak_model:` on the
ticket itself, and the validator enforces it (`tools/validate.py:3805-3824`,
`[sweep-ticket-link]`, red controls 15/16). The CLI surface exposes no operation
that writes either field: `saipen ticket add <PRIORITY> <text>` renders its own
line, and `ticket done|compact|block|block-for|unblock` write only their own
fields. The incident INDEX's own entry "PROPOSAL -- canonical mutation of a
ticket's description" records the same gap. Consequence measured on the
reporter's tree: `tools/validate.py` FAILs `[sweep-ticket-link]` for T-53, T-54,
T-55, T-66, T-67 and T-68 -- six protocol-level tickets that are non-conformant
by construction, because no compliant agent could have added the fields. This is
recorded here rather than filed as a separate packet, and is noted on T-68's own
BOARD line in the `blocker:` text, which is the only free-text field the CLI
writes onto a ticket.

## Reasoning gates for the reporting ticket (T-68)

- `recurrence:` cross-project. The trigger is an install update, which is a
  global event rather than a project one: any project with an open improve
  cycle at that moment loses the seat. The reporter has seen the same
  refusal-without-route shape in sibling defects
  (`SAI-DEFECT-20260918-routeless-finish-source-gate`,
  `SAI-DEFECT-20260918-ship-source-coverage-deadlock`), so the class recurs
  across projects.
- `weak_model:` a weak but compliant model cannot avoid this. The assignment's
  own `next:` command is the one that refuses, the refusal names the fingerprint
  mismatch (an install fact the agent cannot change), and every documented exit
  (`abort`, `clean`, re-seat) is either forbidden or destroys evidence. The
  strong fix is mechanical: re-derive the header of an un-audited draft, or
  expose a canonical seat-retirement operation; prose alone cannot help.

## Additional observation: a long blocker reason is refused with a false diagnosis

Measured while filing this ticket. `saipen ticket block T-68 <reason> --scope
ticket` succeeds with an 858-byte reason and fails with 932, 961 and
~1500-byte reasons, each time with:

```
VALIDATION_FAILED: proposed state fails fast validation: STATE proposed invalid
phase transition: SCOUT -> DONE (RFC 1.6). The block-parked shape requires the
latest phase-changing event through STATE.last_event to be the canonical
active-block DEC for the exact ticket still in BOARD.BLOCKED
```

The message names the phase transition, which is legal for an active block, and
never the payload length. The real bound is `MAX_NEW_EVENT_BYTES = 1024`
(`tools/saipen_engine/log.py:635`). A checkpoint whose text exceeds the bound
falls back to `.saipen/recovery/log-detail/<E>-<hash>.json` (used by this
session's own E-570 SCOUT line), but the ticket-block DEC has no such fallback:
the logged text is cut and `block_parked_evidence_error`
(`tools/saipen_engine/fast_check.py:189-243`) then finds no active-block evidence
and blames the transition. The practical effect is that a complete, honest
blocker reason is refused and a shorter one is silently required, or the agent
is nudged toward the raw BOARD edit that OPS.md 4a forbids.

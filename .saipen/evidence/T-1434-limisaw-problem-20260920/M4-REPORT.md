# T-1434 / SRC-088 — Milestone 4 evidence: strict Improve cycle finite exit

Date: 2026-09-21. Session continuation of T-1434 (SRC-088). Phase BUILD.
Mission: every strict ACTIVE Improve cycle has ONE canonical, lossless finite
exit; the validator-required sweep-ticket reasoning linkage has a canonical
writer; no report byte is ever rewritten.

## Defect reproduced before patch (live, current tree)

LIMISAW `validate --gate core` (protocol-home engine, carriers cleared) reported
24 problems, of which:

- `improve report [improve-report]` x1 -- cycle `imp-...-4` (ACTIVE) carried two
  un-started draft seats (`opencode-01`, `opencode-03`, zero RUNs, stale
  headers) and three COMPLETE seats stale against today's install/HEAD
  (`opencode-02`, `-04`, `-05`); cycles `-1` and `-3` were flagged by the
  naive red-control-22 substring test for a backticked prose citation
  (`## DOING` inside an evidence sentence, not a pasted board heading).
- `core sweep [sweep-ticket-link]` x1 -- seven tickets (T-53..T-55, T-66..T-68,
  T-73) produced by strict-sweep `CONFIRMED` `PROTOCOL_VIOLATION` dispositions
  lacked `recurrence:` / `weak_model:`, and NO canonical writer existed.
- Anchored dead end confirmed by `saipen improve cycle-complete` (stale seats),
  `saipen improve abort` (dispositions already written), `saipen improve
  retire` (report complete) -- three mutually closed exits.

## Implemented primitives

1. `saipen improve reconcile <cycle>` (strict active cycles):
   - classifies every roster seat into exactly one machine-readable class:
     `CURRENT_COMPLETE | SUPERSEDED | CANONICALLY_UNAVAILABLE |
     BLOCKED_EXTERNAL | EMPTY_DRAFT | STALE_COMPLETE | STILL_ACTIONABLE`;
   - executes only lossless transitions: retire `EMPTY_DRAFT` seats
     (zero committed RUNs; report bytes preserved at their path) and supersede
     `STALE_COMPLETE` seats onto a CURRENT, COMPLETE, same-role, same-scope
     replacement (existing `resolve_stale_complete_seat` evidence bar intact);
   - refuses while a `STILL_ACTIONABLE` seat (committed audit content, missing
     or malformed evidence, no replacement available) remains, naming the exact
     route;
   - re-derives every classification from disk after the transitions, requires
     the full `verify_cycle` bar, then terminalizes with WHY:
     `cycle_status: complete | superseded | blocked_external`;
   - idempotent: a terminal cycle returns `ALREADY_TERMINAL` with zero writes.

2. Terminal-status model: `superseded` / `blocked_external` join the closed
   set beside `active|complete|archived`; every terminal status seals a cycle
   (report freshness checks, `improve clean`, continue-fallback admission,
   successor-cycle admission).

3. `retire_reason: <CODE>` persisted on `availability: unavailable` seats, so a
   terminal cycle records why a seat was abandoned; `BLOCKED_EXTERNAL` is the
   explicit externally-blocked seat class and terminalizes the cycle as
   `blocked_external` without fabricated completion.

4. `saipen ticket reasoning <T-###> --recurrence <text> --weak-model <text>`
   (journaled BOARD/LOG/STATE transaction): refuses unless the ONE sweep
   grammar resolves a strict-cycle `CONFIRMED` `PROTOCOL_VIOLATION` disposition
   naming the ticket (`TICKET_REASONING_NOT_LINKED` otherwise); identical
   repeat returns `ALREADY_LINKED` with zero writes. No raw BOARD edit needed.

5. Validator: red control 22 now anchors to real heading LINES
   (`^## DOING[ \t]*$`), so backticked prose citations stop failing while a
   pasted board still does; the sweep-ticket-link FAIL names the executable
   repair (`saipen ticket reasoning ...`).

Files (sha256[:16] at capture):
- tools/improve.py 75d567880698ea3a
- tools/saipen.py 981fb7a333cfac3a
- tools/saipen_engine/operations.py 30df4aed5971b3a1
- tools/validate.py 18bde25b09f745e7
- saipen/REGISTRY.json 4f6d030b99654b22
- saipen/COMMAND_EFFECTS.json c39dc441ebad75a1
- saipen/COMMANDS.md bc63500ca5866111, saipen/IMPROVE.md bc64c707be1f76eb
- tools/test_improve_reconcile.py a59d38482b34b472 (new, 11 tests)

## Verification (current bytes)

- `python tools/test_improve_reconcile.py` -> 11/11 OK. Families: all-current
  terminalize + idempotent repeat; empty-draft lossless retirement (SUPERSEDED);
  stale COMPLETE supersession onto a fresh replacement (report + SWEEP bytes
  unchanged, preserved hash bound); no-replacement refusal with zero writes;
  STILL_ACTIONABLE prevents terminalization; legal early abort; post-disposition
  reconciliation instead of abort; BLOCKED_EXTERNAL terminal class; legacy
  cycle refused read-only; ticket-reasoning linkage writer (refusal, write,
  idempotence, validator green); red-22 line anchor.
- Neighbors (carriers cleared): test_t1411_stale_complete_resolution 16/16,
  test_source_retirement 8/8, test_external_resolution 10/10,
  test_work_reverify_cli 14/14, test_command_routing 63/63,
  test_effect_authorization 34/34, test_guard_events 55/55;
  test_check_inventory 37/42 (5 pre-existing reds at site
  17c1825e57d0436e; no new site, counted unchanged).

## Real LIMISAW acceptance (canonical operations only)

Before: 24 problems (21 closure-evidence, 1 closure-provenance EX generation
move, 1 improve-report, 1 sweep-ticket-link naming 6 tickets). Capture:
`V:\_TEMP_\limisaw-m4-home-before.txt`.

Executed (protocol-home engine, carriers cleared, LIMISAW as --project-root):

1. `saipen improve --new-seat --role core` -> seat `opencode-06`, report on the
   current tree (source_head dce172c, tree git-delta-v1:c66baf69...).
2. `saipen improve submit ... opencode-06 SAIPEN <findings.json>` -> bounded
   re-audit RUN with `NO_FINDINGS` (scope recorded in the RUN body).
3. `saipen improve complete ... opencode-06 SAIPEN` -> COMPLETE.
4. `saipen improve reconcile imp-vacterro-limisaw-20260918-4` ->
   `CYCLE_RECONCILED`, outcome `SUPERSEDED`:
   retired `opencode-01`/`opencode-03` (`retire_reason: EMPTY_DRAFT`),
   superseded `opencode-02`/`-04`/`-05` onto `opencode-06`
   (`preserved_report_sha256` bound in the manifest).
   `saipen improve verify ...` -> `IMPROVE_VERIFY_PASS` (preserved hashes match
   the untouched report bytes; no report, SWEEP or manifest history rewritten).
5. `saipen ticket reasoning` for T-53, T-54, T-55, T-66, T-67, T-68, T-73 --
   each proved its exact strict-sweep composite link (T-66/T-67 resolved two
   links each) and journaled E-656..E-662.

After: `Validation FAILED: 22 problem(s), 21 warning(s)` -- the improve-report
class and the sweep-ticket-link class are removed entirely, leaving exactly the
two M7-owned classes (21 closure-evidence; 1 closure-provenance generation-move
for EX-000001..3, the DESIGNED rollback semantics). Capture:
`V:\_TEMP_\limisaw-m4-final.txt`.

LIMISAW product source unchanged (every write landed under `.saipen/`), no
report byte rewritten, no manifest hand-edited.

## Milestone exit check

- every strict Improve cycle has a finite legal terminal path: yes (reconcile);
- validator-required sweep linkage has a legal producer: yes
  (`ticket reasoning`, refusal-proof linkage);
- validator no longer demands a remediation that does not exist for these two
  classes: yes (both FAIL classes are gone from the live LIMISAW run);
- historical evidence preserved: yes (improve verify PASS + hashes bound);
- no fabricated completion: yes (retire/supersede outcomes are recorded as
  classes, not as DONE).

## Home conformance note (PATCH_OWNED, resolution owned by T-1434 close)

Home `validate --gate core` after M4: 5 FAILs, all one class --
`runtime manifest names a file git does not track` for the T-1434 new files
`tools/saipen_engine/external.py`, `tools/test_external_resolution.py`,
`tools/test_work_reverify_cli.py`, `tools/test_source_retirement.py`,
`tools/test_improve_reconcile.py` (M1-M4 deliverables still untracked; the
same untracked state is what makes the scheduled injector skip DIRTY_SOURCE).
Resolution at T-1434 SHIP: one local commit of the T-1434 engine/test set
(no push, no tag, no release), which turns the manifest check green and lets
the installed generation move for M7's canonical re-resolution. A
`cross-doc drift [improve-command-parity]` FAIL raised by the first M4 pass
was fixed in the same milestone (`IMPROVE_ACTIONS` now names `reconcile`).

## Exact next action

M5 (SRC-088): audit every CURRENT error-level actionable validator remediation
and build ONE self-consistency gate proving each resolves to a registered
canonical command or a typed external action; review the M1 `work reverify`
caller-attested PASS authority with a RED control; keep the
`test_check_inventory` fail-site 17c1825e57d0436e debt untouched/unchanged.

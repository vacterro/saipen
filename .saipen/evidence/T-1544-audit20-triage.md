# T-1544 -- audit/20.md execution triage (SRC-128)

Ten findings. **Nine were LIVE and are fixed here. CORE-001 was mis-triaged: the
repair it asks for was built, measured, and rejected on evidence.** The uniformity
of the other nine is not a round number: the audit's wave report locates each
defect in the three `saipen.py` routing wrappers, `intake.py`'s mutators,
`_status`'s dependency wiring, `admission.py::_RESOLVE_CACHE`,
`audit_inbox.py`, `autoinject.py` and `log.py::read_history_snapshot` -- none of
which the reworked state, journal, admission and validator machinery touched
since September. Two partial mitigations exist (the `cold_route` field on
`_status`, and lean mode's `text`/`event_lines` drop); both are additive and
leave each finding's decisive behaviour intact.

## CORE-001 -- NOT A DEFECT. The repair was built, measured, and rejected.

**The finding.** `tools/saipen_engine/reconcile.py:1564-1566` states the
governing invariant: the LOG records destinations, the chain is what makes a
source knowable, "which is why a lone transition event can prove a destination
but never a pair". `_proven_pair` (`:1658-1660`) honours it and returns `None`
for a lone event. `:1841-1846` then falls back to the STATE's own
`transition_from`, and the audit calls that the opposite of the invariant: the
state claims a source the journal never recorded, and only the DFA stands
between that claim and a commit.

**The repro the audit gave.** `_state_phase_repairs({"phase":"IMPL",
"transition_from":"SCOUT","last_event":1}, [_event(1, _TRANSITION_OP,
"transition to BUILD")])` returned an UNBLOCKED repair. End to end on a
T-1318-shape temp project: DRY `REPAIR_REQUIRED`, LIVE `REPAIRED`.

**What was built.** The fallback was NOT deleted -- it is load-bearing for the
`CURRENT_DONE_JOURNAL_GAP` (T-1572) repair path directly above it, which also
needs a source when no pair is proven. A conditional fallback was added instead:
`_chain_proves(scoped, number, transition_from)` required the claimed source to
be a proven DESTINATION of an earlier event of the same scoped chain, and the
refusal fired otherwise. Five pinning tests were written. The audit's case went
from `REPAIRED` to `RECOVERY_BLOCKED`, as intended.

**Why it was rejected.** The declared core-unit family came back with 7 new red
across two suites:

- `tools/test_recover_approved_repair.PlanCollectionTests` (5) -- the plan
  collection returned `VALIDATION_FAILED` where `RECONCILE_REAUTH_REQUIRED` was
  expected, and `plan["repair_id"]` was absent entirely.
- `tools/test_t1363_zero_manual_entry.ReauthProducerMatrixTests` (2) -- the
  refusals carried `canonical_next_command: None` and
  `diagnosis: READ_ONLY_DIAGNOSIS_ONLY`.

That second pair is decisive. T-1363 exists to prove that a refusal always names
an executable move. The change did not merely alter which verdict a recovery
receives -- it converted a **recoverable** state into a dead end, and the fixture
it broke is structurally identical to the audit's own: `phase: BUILD`,
`transition_from: DONE`, one event `transition to SCOUT`, and `DONE -> SCOUT` is
legal per the very `strict_state_error` the refusal prints.

**The conclusion.** `transition_from` is a first-class STATE claim, and the DFA
check at `:1938-1941` is its validator, not a fallback for a missing proof. The
journal is authoritative about where the project IS; the state is authoritative
about where it came from; the DFA is what refuses the pair when those two
disagree illegally. Removing the claim from consideration does not tighten the
invariant -- it deletes the only corroboration the STATE has. `reconcile.py` was
reverted and the five tests removed.

The audit's underlying instinct is not baseless, and the narrower gap it gestures
at may still be real: a lone event plus a DFA-legal claim does commit a pair the
journal never recorded. But that is a *design question about the STATE schema*,
not a missing guard, and answering it by deleting the fallback measurably breaks
recovery. It is recorded here as **UNRESOLVED BY DESIGN, not fixed**, and belongs
to whoever owns the STATE contract.

## CORE-002 -- three public wrappers short-circuited past the router

**Decisive.** `tools/saipen_engine/router.py:138-144` already returns
`{"ok": False, "action": "saipen recover", "reason": "state-malformed", ...}`,
and `:129-134` the same for `checkpoint-invalid`. But `_status`
(`tools/saipen.py:1396-1409`), `_route_once` (`:2128-2136`, the sole route owner
`_next_action` calls at `:2477`) and `_explain_next` (`:2555-2564`) each
intercepted a malformed STATE first and emitted
`{"ok": False, "code": "VALIDATION_FAILED", "detail": ...}` with no `action` key.

**Repro.** On a fixture whose STATE carries a retired `parked_work` field,
`status`, `next` and `explain-next` all returned payloads with no `action`,
while `route_next` called directly on the same STATE text returned
`action: "saipen recover"`. Zero bytes written either way -- classification only.

**Fix.** `_malformed_route(state_text, board_text, state_error)` reads the
verdict from `router.route_next` through its pre-parsed seam, and all three
wrappers carry its `action`/`reason` into their refusal. `code`, `detail` and
the existing `_cold_route` field are unchanged.

**Known residual.** A fourth routeless copy exists at `tools/saipen.py:4104`
(reads `codec.read_doc` directly, no `board_text`). Outside the triaged three;
left alone for minimal diff.

## W2-001 -- `purge_receipt` was the only mutator with no writer lock

**Decisive.** `tools/saipen_engine/intake.py:3933-4035` performed the whole
read / plan / apply with no `with project_writer_lock(root):`, and
`run_mutation` (`journal.py:2698-2733`) acquires no lock itself. Every sibling
mutator has one -- `:1398` capture, `:1675` quarantine, `:2167` set_disposition,
`:3777` close, `:3859` archive, `:5145` reconcile. The CLI adds none
(`tools/saipen.py:5522`).

**Repro.** With another writer inside the lock, `purge_receipt` still returned
`{"ok": true, "code": "SOURCE_PURGED"}`, the body was gone and the status read
`purged` -- the second writer genuinely deleted through the first's critical
section.

**Fix.** The 107-line body is now inside `with project_writer_lock(root):`, so
every target and every `before_hash` is captured after acquisition.

## W2-002 -- the linkage transaction rolled back only BOARD

**Decisive.** `intake.py:867-874` wrote every compaction detail target, then
BOARD, then called `_relink_authorities`; the handler at `:875-885` restored
only `path` (BOARD). `_relink_authorities` (`:917-946`) writes metadata first
(`_write_meta`, `:935`) and the index second (`_write_index`, `:943`), so a
failure between them returned a refusal with metadata already durable and
nothing to restore it.

**Repro.** With `OSError` injected on the `_write_index` call inside
`link_work_to`: the call refused with `ORPHAN_RECEIPT`, BOARD was byte-identical,
and metadata still read `linked_work: "T-001"` while the index read `None` --
the exact three-authority split. `intake.validate_project` then reported
`active receipt SRC-001 linkage missing from BOARD Work T-001`.

**Fix.** `_link_undo` snapshots each path's bytes (or absence -- the plan targets
carry only a `before_hash`, which proves what a path was but cannot put it back),
and `_run_link_undo` reverses the whole list. Every authority the transaction
touched is restored: BOARD, the compaction detail files, the receipt metadata
and the intake index.

## W2-003 -- a busy lock read as a malformed receipt

**Decisive.** `intake.py` had no `WRITER_BUSY` at all. The contention signal
`PermissionError("WRITER_BUSY")` (`lock.py:318,327`) was caught by eight blanket
`except (OSError, PermissionError, ValueError)` handlers that flattened it to
`VALIDATION_FAILED`. A correct adapter already existed at `plan.py:205-213`.

**Repro.** `capture`, `set_disposition`, `close_receipt` and `archive_receipt`
each issued under a held lock returned
`{"ok": false, "code": "VALIDATION_FAILED", "detail": "WRITER_BUSY"}`. Zero
writes occurred, so this was classification only.

**Fix.** `_write_refusal(exc)` maps ONLY the lock's own signal to
`WRITER_BUSY`; every other `PermissionError` keeps `VALIDATION_FAILED`, because
an unopenable file is still a validation failure rather than a retry hint.

## PERF-001 -- `_status` computed the source identity three times

**Decisive.** `conformance_status(..., source_identity=None)`
(`conformance.py:1351-1357`) already accepted a pre-computed identity and
forwarded it at `:1375`; `automation_block` did too. `_status` used neither:
`conformance_decision(project_root, gate="core")` at `:1810`, then
`convergence_verdict(project_root)` at `:1848`, then a third hand-rolled capture
at `:1851-1856`.

**Repro.** Instrumented `freshness.compute_source_identity` over one healthy
`_status`: 3 calls.

**Fix.** One `_csi_auto(project_root)` capture after the checkpoint snapshot,
threaded into `conformance_decision(..., source_identity=)`,
`convergence_verdict(..., source_id=)` and `automation_block(..., source_identity=)`.

**Residual, recorded not closed.** `router.conformance_idle_gate`
(`router.py:969`) runs its own `conformance_decision` with no identity, inside
`gate_route`, which `_status` calls at `:1483`. So `status --json` now walks the
tree twice rather than once; reaching one requires threading an identity through
`gate_route` / `conformance_crew_gate` / `closure_finish_gate` /
`conformance_idle_gate`, which changes the shared router gate API.

**Audit claim NOT confirmed.** The fingerprint form disagreement
(`no-git-tree-v1:...` vs `no-git+no-git-tree-v1:...`) persists after the fix. It
is a rendering difference in `automation_block`, not a consequence of
independent captures -- the underlying digests already matched pre-fix on a
stable tree. The coherence symptom is a separate defect; the walk count was real.

## PERF-002 -- `_RESOLVE_CACHE` cached stale negatives and omitted every carrier

**Decisive.** `tools/saipen_engine/admission.py:1050-1062` held a
process-lifetime module global keyed only on `(start, explicit)`.
`SAIPEN_PROJECT_ROOT` and `SAIPEN_PROJECT_LINEAGE` (`paths.py:472-473`) are read
by `resolve_project_root` but appeared in neither key component; negatives were
cached; nothing bounded or expired the dict, and no caller ever cleared it.

**Repro.** Admission on a directory with no `.saipen` returned
`NOT_SAIPEN_PROJECT`; creating `.saipen` in the SAME process still returned
`NOT_SAIPEN_PROJECT` until `_RESOLVE_CACHE.clear()` was called by hand. With env
rebound from P1/lineage-1 to P2/lineage-2, the cached answer stayed P1 while
`resolve_project_root` called directly correctly answered P2.

**Fix.** The key is now `(normalized start, explicit,
os.environ[SAIPEN_PROJECT_ROOT], os.environ[SAIPEN_PROJECT_LINEAGE])`, and only a
SUCCESSFUL resolution is memoized.

## PERF-003 -- `_status` classified the audit inbox five times

**Decisive.** `audit_inbox.py:770-782` `status()` called `classify(root)` and
then `projection(root)`, and `projection` re-classified.
`receipt_for_digest` at `:384-398` called `_index(root)` once PER digest with no
memo. `tools/saipen.py` asked three logical consumers: `:1451`, `:1842`, and
the same `_audit_status` into `automation_block` at `:1859-1869`.

**Repro.** Instrumented `classify` and `intake._read_index` over one `_status`:
5 classifies.

**Fix.** `_receipts_by_digest(root)` builds ONE digest->receipt map from a single
`_index` read (tombstones first, then active, so ACTIVE wins; lowest receipt_id
first, the old loop's order). `projection_from_classification` and
`status_from_classification` are new; `status()` no longer re-classifies. The
audit_inbox side is self-sufficient -- `saipen.py` can adopt
`status_from_classification(root, classify(root))` later with no import change.

**Partially unproven.** The audit's second-order term (`_read_index: 15 calls`
from its own 4-layer inbox) was NOT reproduced -- the scenario fixture has no
audit-inbox layers, so the measured count was 1. The O(layers x receipts) term is
proven only structurally at `audit_inbox.py:384-398`. A multi-layer fixture
measures the new code's single-read behaviour but not the old one's 15.

## PERF-004 -- a discarded full-home hash when nothing is installed

**Decisive.** `tools/saipen.py:1733` called `distribution_report()`
unconditionally, gating only the RESULT at `:1734` on
`if _dist["installed"]`. Meanwhile `tools/autoinject.py:797-801` computed
`expected = runtime_generation_identity(HOME)` BEFORE the
`for target in TARGETS: if not target.is_dir(): continue` loop. No
`has_installed_targets` existed anywhere.

**Repro.** With `autoinject.TARGETS` pointed at three non-existent homes: zero
`_content_bytes` calls but 1 `runtime_generation_identity` call, and
`distribution` absent from the payload -- the full runtime generation hashed and
discarded. That one discarded call measured `[162.4, 157.1, 165.0]` ms.

**Caveat, stated plainly.** On THIS host the zero-home branch is simulated, not
native: six real installed homes exist, `_content_bytes` /
`runtime_generation_identity` are called 8/7 times, and `distribution` IS present
in the payload. The defect is the missing pre-check, which the simulation
isolates; it is not a claim that this machine wastes the hash.

**Fix.** `autoinject.has_installed_targets()` derives from the same `TARGETS`
registry `distribution_report` loops; `_status` skips the report call entirely
when it is false.

**Test corrected.** `tools/test_audit_2026_08_28_all3.py`
`test_parity_control_detects_a_capture_mode_dependent_projection` pins
`TARGETS` to `()`, which is exactly the state in which the new pre-check skips
the report -- so its drifting projection never reached the payload and the
control compared nothing. It now also pins `has_installed_targets` to true.

## PERF-005 -- lean mode still retained one dict per lifetime event

**Decisive.** `log.py:439-442` documents that lean omits "the O(history-text)
`text` and `event_lines` renderings", and the loop at `:474-503` still did
`events.append(parsed)` for every line, with `:517` returning
`events=tuple(events)`. `ProjectSnapshot.capture(..., lean=True)`
(`snapshot.py:81-116`) passes lean straight through at `:111`, and `_status` /
`_route_once` / `_explain_next` all use it.

**Repro.** Through the production `read_history_snapshot(..., lean=True)`:
5,000 events 0.0305 s / 4.26 MB peak; 20,000 events 0.1176 s / 17.12 MB;
50,000 events 0.2529 s / 42.96 MB. Linear in lifetime event count -- the
`text`/`event_lines` relief did not shrink the retained dict graph.

**Fix.** `read_history_routing_summary(project_root)` is a one-pass summary
(`ROUTING_TAIL_EVENTS=16`, `ROUTING_DIAGNOSTIC_CAP=32`) carrying hash, tail,
`illegal_lines`, `max_ticket_id`, `event_count`, `duplicate_event_ids`,
`ordering_errors` and `routing_events`. It keeps the same ownership check, the
same single open per segment, the same framed hash and the same `_SAITULS`
claimed-id tail rule. `history_hash` (`log.py:1053`) and `history_log_tail`
(`:1064`) route to it; live callers are `conformance.py:295` and
`release.py:3923`. Measured at 50,000 events: retained 34.2 MB -> 0.02 MB, time
0.2529 s -> ~0.19 s.

**NOT DONE -- the lean return-shape swap is blocked, deliberately.** Four
callers read `history.events` and the swap breaks them:
`snapshot.py:129` passes it onward as `history_events`, `saipen.py:745` reads it,
`tools/test_ticket_retirement.py:1165` asserts on
`read_history_snapshot(ROOT, lean=True).events`, and
`test_audit_2026_08_28_all3.test_lean_project_snapshot_preserves_routing_fields_and_drops_renderings`
asserts lean/full routing parity. That parity test PASSING is the evidence that
the swap is unsafe rather than merely inconvenient: the routing fields are still
read from the retained events.

**Residual, recorded.** The summary retains 0 events, but peak memory for the
full lean path stays ~31 MB because `text.splitlines()` materialises every line.
Left unchanged deliberately so illegal-line numbers stay byte-identical. The
seen-id set (~2.6 MB, ints not dicts) and `illegal_lines` (unbounded in the full
snapshot too, kept identical) still scale with the ledger.

## Not established

1. PERF-003's second-order `_read_index` term -- proven structurally, not
   measured against the pre-fix code on a multi-layer inbox.
2. PERF-004's zero-home branch -- proven by patching `TARGETS` to non-existent
   paths on a host that has six real installed homes.
3. PERF-001's coherence symptom -- the fingerprint form disagreement is a
   rendering difference, not a consequence of independent captures.
4. The audit's own wave-1 `TEST_LIMITATION` (the `_AUDAPACK_MANIFEST.json`
   root-file violation) concerns the September archive representation, not this
   checkout, and was not re-checked.

## Tests

- `tools/test_t1544_audit20.py` -- CORE-002, PERF-001, PERF-004. 11 tests,
  8 confirmed red before the fix by reverting every hunk; 3 pass-before are the
  negative controls.
- `tools/test_t1544_audit20_perf.py` -- PERF-002, PERF-003, PERF-005. 20 tests.
  The CORE-001 classes were written, proved red against the defect, and then
  removed with the change they pinned; they are described in the CORE-001
  section above rather than deleted silently.
- `tools/test_t1544_audit20_intake.py` -- W2-001, W2-002, W2-003. 8 tests,
  4 confirmed red on `HEAD` with `intake.py` reverted; the other 4 are the
  negative controls (an unrelated `PermissionError` is still `VALIDATION_FAILED`,
  a busy lock writes nothing, purge still succeeds uncontended, linkage still
  commits).

## Tests corrected rather than bent

`tools/test_audit_2026_08_28_all3.py`
`test_parity_control_detects_a_capture_mode_dependent_projection` pinned
`TARGETS` to `()`, which is exactly the state in which the PERF-004 pre-check
skips the report -- so its drifting projection never reached the payload and the
control compared nothing. It now also pins `has_installed_targets` to true. The
control's purpose (prove the parity detector detects a real capture-mode
difference) is preserved; only its drift source was restored.

`tools/test_audit_2026_08_28_all3.py` `test_family_host_reads_are_pinned` is
T-1552's control against un-pinned host reads. It accepts an env-level pin or a
recognized `patch.object` on the host-reading function itself;
`tools/test_t1544_audit20.py` had used a bare `setattr`, which the control
correctly refuses to guess at. The test was converted to `patch.object` rather
than the control widened to accept a spelling it cannot verify.

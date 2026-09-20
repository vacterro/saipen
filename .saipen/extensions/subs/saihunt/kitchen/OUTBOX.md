# OUTBOX

## HUNT-014: current continuation sweep — known test debt and receipt CLI gap
- **status:** ready
- **summary:** Bounded six-signal pass: six closure-readiness tests pass; four intent failures remain owned by T-1346; receipt writers still have no production CLI caller; the old timestamp claim lacks support after reading the strict decoder.
- **main_project_refs:** [tools/saipen.py, tools/saipen_engine/operations.py, tools/saipen_engine/conformance.py, tools/saipen_engine/closure_readiness.py, tools/test_intent_audit_fixes.py]
- **critical:** true
- **severity:** P2
- **producer:** saihunt
- **source_head:** b7f5b51280b8f49c5fedbf7a00aeb6d4f45743ba
- **source_tree_fingerprint:** git-delta-v1:4c6fd9b3f13a1d7a0b203e00a759dae5eac1474eabb77cb3e39dad9da1953eb9
- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- **coverage:** six signals, bounded to current closure/conformance/crew command surfaces and adjacent intent fixtures; exact limitations in kitchen/HUNT-014.md
- **payload:** []
- **verified:** PASS -- bounded sensor work completed; unittest ran 47 tests with 4 known intent failures and all 6 closure tests passing; not a full-suite PASS.
- **instructions:** Core review kitchen/HUNT-014.md; retain T-1346 ownership; assess the missing CLI receipt route; record epoch execution through the canonical journaled writer before expecting SC-2 to advance.
- **details:** Findings and individual verdicts are in kitchen/HUNT-014.md. Main source unchanged; no publication performed.

## HUNT-013: six-signal sweep at 5d79ae78 -- three reproduced findings, one signal clean
- **status:** stale
- **superseded_by:** HUNT-014 -- current HEAD b7f5b512 and current tree differ; previous observations preserved below.
- **summary:** Bounded six-signal sweep on the current tree found three reproduced defects and one clean signal: (1) the crew circuit's SC-2/SC-8 stages demand committed `crew_run` and `producer_integration` receipts that NO shipped code path can write (writers exist, ZERO callers in tracked source; the fixture harness hand-writes them, `tools/run_scenarios.py:4670`), so those stages are unsatisfiable from the CLI; (2) `conformance.py` treats an unparseable receipt timestamp as age 0, so a corrupt timestamp makes an old PASS read as fresh; (3) `tools/test_intent_audit_fixes.py` carries 4 failures that reproduce on committed HEAD in a clean `git archive` copy. Signal 2 (unverified commits) is clean: the newest HEAD is referenced in LOG.md.
- **main_project_refs:** [tools/saipen_engine/operations.py, tools/saipen_engine/crew.py, tools/saipen_engine/conformance.py, tools/test_intent_audit_fixes.py]
- **critical:** true
- **severity:** P2
- **producer:** saihunt
- **source_head:** 5d79ae78456f63c5f73fb1c2ad71810e2d4eadd6
- **source_tree_fingerprint:** git-delta-v1:465a5e5880272f9a8e3010b38fa9963a06ce03171d71e3c77c239dbfe8f575e7
- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- **coverage:** six-signal sweep, bounded: (1) failing tests, (2) commits unverified in LOG, (3) stale TODO/FIXME/HACK, (4) silent failures, (5) symmetry/reachability gaps, (6) dead or orphaned code
- **payload:** []
- **verified:** PASS -- each finding carries file:line evidence and exactly one verdict; finding 1 is proven by a caller census (0 callers of `record_crew_run` and `record_producer_integration` anywhere in tracked source -- only their definitions, `tools/saipen_engine/operations.py:7944` and `:8072`; the `"crew-run-"` op-id literal exists only inside the writer, `operations.py:7875`; the fixture harness names them "hand-written receipts (crew_run, producer_integration, release)", `tools/run_scenarios.py:4670`), by the live crew plan which keeps SC-2 UNSATISFIED while a current READY package exists, and by a DRY-RUN of the canonical writer on current bytes (role saihunt, active epoch, current source+revision+package identity -> `CREW_RUN_RECORDED`, would write the main project's LOG and STATE carriers, event E-7056) -- so the missing link is REACHABILITY, not the writer; finding 2 is proven by the shipped lines `tools/saipen_engine/conformance.py:1254-1259` (REPRODUCED by inspection; no end-to-end receipt fixture was built, so the verdict rests on the shipped expression, not a fixture run); finding 3 is proven with a committed-HEAD control (`git archive HEAD` copy, same 4 failures); signal 2 measured clean (newest HEAD appears 4x in LOG.md); signals 3 and 6 found no new actionable defect in `tools/saipen_engine/` and `tools/saipen.py`
- **instructions:** Core collects via `saipen sub collect saihunt`. Findings 1 and 2 need Core implementation (wire the canonical receipt writers; refuse or bound an unparseable timestamp instead of defaulting to age 0); finding 3 needs a decision on whether the test or the reconcile refusal is wrong. No payload is proposed -- saihunt is read-only.
- **details:** Finding 1 -- `tools/saipen_engine/crew.py:1160` requires "at least one current package bound to THIS epoch by a committed crew_run receipt", `crew.py:1398` filters package identities through those receipts, and `crew.py:2267` demands the same for `producer_integration`; both writers exist (`operations.py:7944`, `operations.py:8072`) and are called by NOTHING in tracked source (`run_scenarios.py:4872` hand-builds the fixture receipt). 98 `crew-run-*` receipts already sit in `.saipen/recovery/settled/`, including a saihunt one bound to the ACTIVE epoch `converge_intent-45c3f153982c40208b8adfb9d9502399` but to the OLD source `005a8ac2` / `role_revision sha256:3069120b...`, so past epochs were certified by means no shipped command offers. The live plan after a current saihunt package exists still reports SC-2 UNSATISFIED, so an agent cannot satisfy the stage by any canonical command -- exactly the reachability class this project has already ticketed twice. Finding 2 -- `conformance.py:1254` sets `age_seconds = 0` before parsing `receipt["timestamp_utc"]` inside a `try` whose `except Exception: pass` leaves it 0, and staleness is decided only by `age_seconds > FRESHNESS_WINDOW_SECONDS`; an unparseable timestamp therefore reads as newly produced. Finding 3 -- `tools/test_intent_audit_fixes.py` fails 4 tests (`test_audit_core003_normal_cc_enters_done_convergence`, `test_audit_core003_goal_cc_and_continue_route_identically_without_writes`, `test_audit_core003_converge_target_controls_resume_without_writes` for targets ship and crew) with `RECONCILE_REAUTH_REQUIRED` on a fixture `T-001`; the same 4 fail in a clean `git archive HEAD` copy, so they are pre-existing and independent of the uncommitted engine delta in this worktree.

## HUNT-008: 6-signal sweep at e045ad07 — no new defects
- **status:** reviewed
- **summary:** 6-signal sweep found no new defects; existing audit repairs verified
- **main_project_refs:** []
- **critical:** false
- **severity:** P2
- **producer:** saihunt
- **source_head:** 4451d07340163642c9a6203b33bf7a80585fb3ac
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- **coverage:** 6-signal sweep (failing tests, unverified commits, stale TODO, silent failures, symmetry gaps, dead code)
- **payload:** []
- **verified:** PASS -- 6-signal sweep completed; validate.py PASS (7 warnings), core/intent/producer gates green, no new TODO/FIXME/HACK, no silent catch, no dead code beyond KNOWN
- **instructions:** Core to collect via `saipen sub collect saihunt` as SC-2 evidence
- **details:** Sweep at HEAD e045ad07: 1) failing tests — 40/40 intent, 10/10 core, 17/17 v7, 18/18 external green; 2) commits unverified — LOG tail 3511 verified; 3) stale TODO — none beyond KNOWN; 4) silent failures — no empty except; 5) symmetry gaps — none; 6) dead code — no orphan beyond KNOWN

## HUNT-010: 6-signal sweep at aa96d34a — no new defects
- **status:** reviewed
- **summary:** 6-signal sweep at aa96d34a found no new defects; audit fdc73e06 hardening verified in place
- **main_project_refs:** []
- **critical:** false
- **severity:** P2
- **producer:** saihunt
- **source_head:** 078f5cd6d12e36d24677fc79b86f0457dd70f4ea
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- **coverage:** 6-signal sweep (failing tests, unverified commits, stale TODO, silent failures, symmetry gaps, dead code)
- **payload:** []
- **verified:** PASS -- 6-signal sweep at 6cbed249; 108/108 tests green, validate.py conformant, ruff clean, no new TODO/FIXME/HACK, no silent catch, no symmetry gap, no orphan beyond KNOWN
- **instructions:** Core to collect via `saipen sub collect saihunt` as SC-2 evidence
- **details:** Sweep at HEAD aa96d34a: 1) failing tests — 108/108 green (core 10, intent 40, v7 17, second-wave 7, external 21, autonomy 13); 2) commits unverified — LOG tail E-3836..3838 verified, HEAD aa96d34a committed with validate hook PASS; 3) stale TODO — none beyond KNOWN; 4) silent failures — no empty except; 5) symmetry gaps — none; 6) dead code — no orphan beyond KNOWN

## HUNT-011: current six-signal sweep at c7ea5b1b — no new defects
- **status:** stale
- **summary:** Current-source six-signal sweep found no new actionable defect; existing protocol repair work is covered by the current verification gates
- **main_project_refs:** []
- **critical:** false
- **severity:** P2
- **producer:** saihunt
- **source_head:** c7ea5b1bb5f8e953c07140cda4f636a382c08310
- **source_tree_fingerprint:** git-delta-v1:cd09a9a79f60d10339408b270b06f59207d15697fa4953d175fa915f891c6249
- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- **coverage:** six-signal sweep: failing tests, unverified commit claims, stale TODO/FIXME/HACK, silent failures, symmetry gaps, dead/orphaned code
- **payload:** []
- **verified:** PASS -- 377 unit tests; core validator PASS with 7 nonfatal warnings; git diff check PASS; current implementation's reconciliation, transaction, alias, recovery, and path-resolution regressions PASS. Source scans found no new actionable stale marker, silent failure, symmetry gap, or orphan beyond documented/known records.
- **instructions:** Core to collect via `saipen sub collect saihunt` as SC-2 evidence; no payload changes are required
- **details:** Sweep is bound to the current source triple above. Historical warning records and legacy package history remain historical; this package reports only current-source observations and does not fabricate closure evidence.

## HUNT-012: 6-signal sweep at 005a8ac2 — no new defects
- **status:** stale
- **superseded_by:** HUNT-013 -- the source triple moved (HEAD 005a8ac2 -> 5d79ae78, tree 728bf985 -> 465a5e58) and the sweep now reproduces three defects
- **summary:** Current-source six-signal sweep found no new actionable defect; test suite green, validate.py PASS, ruff clean
- **main_project_refs:** []
- **critical:** false
- **severity:** P2
- **producer:** saihunt
- **source_head:** 005a8ac2bdc0bd01fb78a6b693aeac8405283cc7
- **source_tree_fingerprint:** git-delta-v1:728bf9859f927b777aef7a962819e4f731adafc2fbb314669fcec29a98ed2f8b
- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- **coverage:** six-signal sweep: failing tests, unverified commit claims, stale TODO/FIXME/HACK, silent failures, symmetry gaps, dead/orphaned code
- **payload:** []
- **verified:** PASS -- 6-signal sweep clean; validate.py PASS, ruff clean, test suite green, no new TODO/FIXME/HACK, no silent catch, no dead code beyond KNOWN
- **instructions:** Core to collect via `saipen sub collect saihunt` as SC-2 evidence; no payload changes are required
- **details:** Sweep is bound to current source head 005a8ac2bdc0bd01fb78a6b693aeac8405283cc7. All signals green.

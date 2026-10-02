# SAIPEN — next stabilization roadmap

Planning reference, not execution authority. Created under T-1423 / SRC-077;
refreshed for SRC-094 on 2026-09-21 (Europe/Tallinn). Current STATE, BOARD, source
receipts and their verified evidence outrank every snapshot below. This document neither
reorders BOARD nor grants publication or ownership transfer.

**Next Astra:** [five-hour continuation handoff](ASTRA_HANDOFF_20260921.md).
T-1441 delivered the verification slice and closed at E-7783; T-1439 closed at
E-7789 after an independent REVIEW re-run; T-1440 integrates that result and
refreshes this roadmap before closing. The handoff gives exact entry commands,
dirty-source inventory, milestone budgets and acceptance checks. Final repair
evidence and limits:
[T-1439/T-1440 report](../.saipen/evidence/T-1440-astra-handoff-20260921/REPORT.md).
After T-1440's closure the existing chain is T-1437 -> T-1435 -> T-1361.

## Product outcome

Help the person finish a real task with fewer interruptions and help the agent
reach the correct next action with less reconstruction. A successful ordinary
session feels predictable: the task is remembered, useful work continues,
stops explain what is needed, and completion means what it says.

Optimize the complete task, not ticket throughput or the number of autonomous
stages. Every slice below must name both benefits: what the person no longer
has to do, and what the agent no longer has to guess. Measure friction removed
without weakening ownership, evidence or validation.

## First five minutes after a reset

1. Load the bound STYLE, EXECUTION and BOOT authorities, then the bounded
   current STATE/ticket/LOG context. Use `python tools/saipen.py` from the
   repository root if `saipen` is absent from PATH.
2. Resolve the current input before the old queue. A new task uses `start`;
   a continuation uses `continue --json`. Capture exact user wording rather
   than replacing it with this roadmap.
3. Read the returned owner/phase and original linked source. An executable
   route is an instruction to act, not evidence that the task is complete.
4. If entry reports `WAIT_FOREIGN_OWNER`, preserve the live claim. Do not
   interpret a more permissive diagnostic/continuation route as permission to
   bypass it. Resume through canonical ownership after actual release or
   expiry and current evidence that the prior writer is inactive.
5. Select one bounded slice from the active source. Read only its existing
   owner, current implementation and tests. Complete it or record its precise
   blocker, then use the canonical scheduler for the next eligible action.

Known working root: `V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN`.
Investigation baseline HEAD: `d97abdc097db432bafe2316b1e3577e44cd9cc4c`; worktree is dirty.
Do not use HEAD alone as the identity of an uncommitted implementation.

## Current facts — do not restart completed work

| Work | Snapshot truth | Next consequence |
|---|---|---|
| T-1423, T-1420, T-1421, T-1422, T-1347 | BOARD says DONE. The older roadmap's open-review/patch-in-pen instructions are obsolete. | Read their evidence only if a new regression requires it; do not reintegrate PY-14. |
| T-1424, T-1427 | BOARD says DONE; later host fixes remain in the dirty tree. | Preserve the implementation and distinguish deterministic loader checks from live host acceptance. |
| T-1432 / SRC-085, SRC-086; T-1434 / SRC-088 | DONE, including later LIMISAW recovery and current conformance routing. | Do not restart the obsolete T-1432 acceptance instructions below; historical failures need current reproduction. |
| T-1436 / SRC-091, SRC-092 | DONE: dependency resume ownership and queued-source wake. | Preserve this fix; voluntary model handoff and user-wait semantics remain separate questions. |
| T-1438 / SRC-094 | DONE locally at E-7754/E-7755: investigation, bounded quarantine repair and roadmap. Code remains uncommitted; see the evidence report for validation and packaging limits. | Preserve the regression and archive overlay; do not interpret local verification as installed delivery or publication. |
| T-1439 | DONE 2026-09-21 (E-7789) after an independent REVIEW re-run of the 10-module family (109 tests OK, E-7785/E-7786); the repair slice remains uncommitted in the dirty worktree. | Do not re-diagnose or re-run the same family unchanged. Live-root family reds are classified: three incoming root handoffs (PRE_EXISTING, T-1438) and the host-session carrier interaction (T-1442). |
| T-1441 / SRC-098 | DONE at E-7783: verification slice delivered (T-1439 acceptance, T-1440 report, roadmap facts), T-1439 slice REVIEWED with DEC: SHIP, chain released to T-1440. | Do not reopen; the SRC-098 mission continues under the released chain tickets. |
| T-1442 / T-1443 | T-1442 records the SAIPEN_HOST_SESSION dependency-resume classification finding; T-1443 records that the T-1440 evidence harness cannot reproduce its own recorded run (single `-c` git fixture). | Fix T-1442 by one carrier policy owner and T-1443 by making the committed harness reproducible. |
| T-1437 / SRC-093 | Refusal registry (4 tests) and multi-work linkage incl. `saipen source link` (5 tests) verified green 2026-09-21 in isolated runs; user-wait seat release proven by `tools/test_user_wait_release.py` (4 tests OK, neighbor family 11 OK, ruff clean; untracked like the other T-1437 tests). Open: the SAITULS end state (SRC-015 migration, T-168 user wait, T-164/T-165/T-171/T-182 closure reconciliation). | Resume existing code and original source; run the consumer validator and source closure gate against SAITULS. |
| T-1435 / SRC-090 | Parked behind T-1437; M1 complete, M2-M14 pending per E-7734. | Fix FastPrompter's four protocol blockers through existing owners, then run the actual ship gate. |
| T-1361 | Parked behind T-1435; scenario measurements already exist. | Classify captured failures by root cause and remeasure changed families; do not repeat the same full run as a substitute for diagnosis. |
| T-1428 / SRC-083 and T-1431 / SRC-084 | Existing orchestration envelope and continuation. | Preserve their dependency chain; do not create a replacement mega task. |
| T-1426 | Deferred live FreeBuff Desktop acceptance; source forbids agent quota consumption. | Operator result remains required; unrelated eligible work proceeds. |
| T-1429 | Native due-time/operator-action projection is TODO. | Reuse the scheduler owner; a timestamp in prose is not machine scheduling. |
| T-1430 | Reachable crew_run CLI producer is TODO. | Expose the existing journaled writer with real role/package/epoch evidence. |

T-1361's recorded run used `python tools/run_scenarios.py` on dirty ec53042a,
lasted 640 seconds and exited 1. Its note reports 959 PASS lines, 115 FAILED
summary lines and 24 unittest FAIL lines. These are different output forms,
not an established count of unique failures; do not sum them. There are 41
`PROJECT_LINEAGE_MISMATCH` occurrences, a clustering lead rather than proof of
41 independent bugs. Exact test IDs, ERROR/SKIP counts and a complete root-cause
partition remain to be established from the captures.

Evidence: [BOARD](../.saipen/BOARD.md), [LOG](../.saipen/LOG.md),
[scenario measurement](../.saipen/evidence/T-1361-scenario-remesure-20260920/EVIDENCE.md),
[current source](../.saipen/intake/active/SRC-085.md),
[reserved continuation](../.saipen/intake/active/SRC-084.md).
Receipt paths are hot paths; after canonical archival use `source show`.

Graph coverage checked at generation `2026-09-01T13:16:39Z` excludes `tools/`.
Implementation conclusions require direct current-source reads. A graph hit
or absence is not whole-code coverage.

### Historical verification handoff from SRC-086

The next paragraphs describe the earlier T-1432 checkpoint, not the current
gate verdict. T-1432 and T-1434 subsequently reached DONE. Current evidence
and current validation supersede these observations.

Read the [continuation evidence](../.saipen/evidence/T-1432-src086-continuation-20260920/REPORT.md)
before repeating a broad run. The explain-next correction has an unchanged
before/after regression; 15 focused tests, 11 tests under flat discovery and
44 related tests pass (overlapping sets, not a combined unique count). Ruff
and whitespace checks pass. Source-runtime diagnostic/admission observations
also pass on live AUDAPACK and PROBLIP DONE states without neighbor edits.

The full validator remains red: one Improve report group and five untracked
runtime files, all named in the evidence. Full core-unit discovery did not
finish within its declared 600-second family budget and was interrupted;
there is no complete test count or family PASS. Installed parity remains
unproven. The next agent should inspect these named evidence/integration
boundaries, not restart DONE work or repeat unchanged validation. For a new
full-family attempt retain verbose test IDs and an explicit timeout so a slow
or failing case is attributable. Resolve dependency changes canonically:
T-1361 already depends on T-1432; adding the reverse edge would create a cycle.

## Release stabilization first — SRC-094

The useful outcome is a verified product change reaching its intended local
completion or authorized release without manual protocol surgery. A green
protocol unit test alone does not establish this outcome.

The newest report is
`SAIPEN — SAIHANDOFF — credential-gate-src033_20260921_0140.md` in HOME.
The incident inbox is
`C:/Users/vac34/AppData/Local/saipen/protocol_incidents/inbox/`.
Treat reports as reproduction leads: compare each against current code and
the installed generation before opening another repair.

Two Wintage reports also arrived during this investigation:
`SAIPEN — SAIHANDOFF — conformance-validation-deadlock_20260920.md` and
`SAIPEN — SAIHANDOFF — conformance-validation-deadlock_20260921.md`.
The latter distinguishes current observations from an older debt snapshot;
use that distinction. The reported six current problems have not been
independently captured here. Their old nine-problem list is not current proof.

| Finding | Current evidence / owner | Small next action and exit proof |
|---|---|---|
| Archived credential refusal gives no executable route | SRC-094: existing quarantine writer; intake gate, remediation table, release preflight | Refusal must emit `saipen source quarantine SRC-033 --reason CREDENTIAL_PATTERN` for the actual failing receipt; the real CLI and validator receipt must carry the same command. Use a disposable receipt, never mutate AUDAPACK from HOME. |
| Quarantine after archival falsely invalidates closure references | Discovered while executing the reported remedy; intake archive readers | Preserve immutable closure carriers and resolve the body through the digest-bound distribution record. Full validator must change FAIL -> PASS; export excludes the body. Pre-closure and post-closure quarantine both pass. Corrupt bytes, corrupt references and unfinished coverage still refuse. |
| CURRENT_FAIL with no registered repair routes to validate again; output hides failures behind the warning tail | T-1439; Wintage reports above; current `conformance_decision` fallback and `_bounded_validator_output` confirm the mechanism | Next bounded release-friction slice: preserve this run's structured blocking findings, then replace the identical validate -> validate edge with a specific executable repair or a truthful terminal engineering diagnosis. Prove finite routing on the same identity. Do not treat carried-debt Work PASS as global conformance PASS or guess the live six findings. |
| Unrelated parked Work freezes every release | T-1399/T-1405 DONE; current release relevance checks recorded scope, shared files and identity | Keep the existing scope tests. Do not reintroduce repository-wide coverage or globally weaken credential/integrity checks. Unknown scope remains a real refusal. |
| SAITULS multi-work/user-wait/closure blockers | T-1437 / SRC-093, E-7739/E-7740 | Verify the partial membership implementation, then finish the source's remaining user-wait and closure reconciliation acceptance. `source link` adds membership; it must not silently move the historical primary. |
| FastPrompter legacy metadata, terminal producer state and runtime debris | T-1435 / SRC-090, E-7734 | Resume M2-M14: canonical metadata migration, producer-owned terminal reconciliation, runtime namespace hygiene, then the four-blocker live ship gate. No hand edits to BOARD/STATE/LOG. |
| Local-only completed work cannot resolve publication-shaped provenance | T-1408 remains BLOCKED | Add/prove the existing design's durable local completion provenance. Do not publish merely to manufacture closure evidence. |
| Model change inherits a fresh foreign lease after a stop checkpoint | This SRC-094 ingress reproduced WAIT_FOREIGN_OWNER on T-1437; original lease remained unchanged | Reuse the voluntary handoff proposal below. A stop/transfer must have real authority and stale-writer fencing; no copied session IDs or arbitrary shorter leases. |

For the credential slice, the executable regression entry is:

```text
python -B -m unittest tools.test_source_quarantine_route tools.test_source_receipts tools.test_remediation_self_consistency
```

Every refusal repair must be tested by actually executing the advertised
command, then re-running the consuming gate. Checking only that a command
string exists missed the archive-reference defect. A repair that merely
trades one protocol error for another is unfinished.

The [T-1438 evidence](../.saipen/evidence/T-1438-release-friction-20260921/REPORT.md)
records the exact scope and residuals. HOME's full core gate was already red:
two prior untracked test modules and three incoming root handoffs rejected by
the root-file-set and coverage checks. The new quarantine test adds an
ordinary untracked-file packaging obligation until included in Git. This is
not evidence that its runtime tests failed. Preserve and canonically classify
incoming reports instead of deleting evidence or exempting arbitrary source
files just to obtain a green gate.

Do not repeat an identical refused operation without changed input, authority,
state or evidence. Follow a supplied repair if authorized and safe. If no route
exists, preserve the exact refusal and diagnose its owner; never invent a
misrouting declaration, successful coverage or operator approval.

Three archive-settlement tests already failed before this slice on the
unmodified baseline: `test_untampered_interrupted_close_settles_idempotently`,
`test_corrupt_partial_archive_refusal_is_zero_write`, and
`test_source_body_limits_apply_before_write_and_during_recovery`, all in
`tools/test_audit_2026_08_28_all3.py`. They remain part of T-1361's classification,
not a claim that the full family is green. The previously suspected
`test_debt_gate.test_delta_resolves_and_reports_release_blocked` passes in the
isolated source environment; reproduce before attributing it to membership.

Installation is a separate acceptance step. Verify the shipped files in a
disposable flattened installation; refresh a live installation only from a
reviewed coherent source. If refresh reports DIRTY_SOURCE, preserve the work
and record that exact limit. Source tests do not mean installed users received
the fix. Actual remote publication still requires its existing authority.

## Execution order after the active source

After the release corridor above, this is the continuation map for
SRC-083/SRC-084, not a competing scheduler.
At every boundary resolve live dependencies and current source authority.

| Order | Existing owner | Small next deliverable | Person / agent benefit | Exit proof |
|---|---|---|---|---|
| 1 | T-1361 | Deduplicate current failing IDs and cluster fixture/environment/engine causes. | Trustworthy progress / no repair of historical ghosts. | Exact baseline, root-cause groups and current disposition per group; changed controls retain their meaning. |
| 2 | T-1346, then T-1345, then T-1344 | Repair stale fixture setup, fail-site inventory and declared-family closure evidence separately. | Honest green results / stable test oracle. | Affected discovery families pass; inventory has CASEs or justified omissions; missing required-family evidence refuses closure. |
| 3 | T-1383, T-1401, T-1402, T-1387, T-1430 | Make help/refusal/command grammar and effect policy agree. First inspect what T-1432 already covers. | Fewer manual instructions / one reachable legal command. | Bounded parity matrix and real crew receipt consumer; no duplicate writer or broadened arbitrary-shell corridor. |
| 4 | T-1302 with T-1429 | Distinguish workable, blocked, deferred, due and globally stopped work. | No repeated approval prompts / no queue deadlock. | A blocked/deferred ticket leaves unrelated work eligible; due gate becomes visible without automatic external action. |
| 5 | T-1408, T-1374, T-1375, inspect T-1282 | Separate local completion, publication, owned evidence and quotations. | Reliable handoff / no fabricated provenance. | Cold export resolves its owned proof or says incomplete; local completion never implies publication. |
| 6 | T-1327 and host acceptance owners | Verify current/stale/failed-refresh installed entry paths. | No recurring injection coaching / one bootstrap authority. | Actual supported entry, fingerprint parity and truthful host enforcement strength. |
| 7 | T-1283 | Measure bounded orientation/status/receipt access before optimizing. | Less waiting / fewer bytes and repeated reads. | Same workload before/after, exact bytes and timing; caches remain derived. |

## Small-model work card

Fill one card before editing; use the current ticket rather than another plan
document. If a field is unknown, make the bounded read/measurement the next
action. Do not fill gaps with plausible prose.

```text
Work / source clause:
Concrete failing behavior and who experiences it:
Benefit to the person:
Benefit to the agent:
Existing decision owner and files:
One bounded change:
Exact verification command and expected result:
Evidence proving the check can detect the defect:
Required broader gate and when it must run:
Unchanged permissions / publication boundary:
Stop condition and canonical recovery action:
Result, evidence paths and exact next action:
```

A card is ready when another agent can execute its first step without opening
the whole backlog, searching historical chat or inventing an internal API.
Do not turn every reversible prose change into a new test suite. Verification
must test the behavior at risk, not merely echo the implementation.

For each code slice: reproduce the ordinary failure safely, identify the
existing owner, make the smallest coherent correction, run meaningful focused
checks, review the diff, run required integration gates, then checkpoint via
the canonical writer. Classify failures as PATCH_OWNED, PRE_EXISTING,
ENVIRONMENTAL or UNKNOWN. Report residual UNKNOWN explicitly; never round it
up to PASS. Re-run broad gates only for changed bytes or unresolved evidence.

## Friction checks that serve both sides

Use the same small set of ordinary tasks before/after: a new local task,
interrupt/resume, an idle diagnostic, a refused operation with a lawful
remedy, a blocked task with unrelated work available, and a cold handoff.
Attach exact task inputs, revision/tree identity and evidence for each run.

| Measure | What to record | Desired change |
|---|---|---|
| Human intervention | Required decisions vs avoidable prompts, repeated instructions and manual protocol edits. | Avoidable prompts/edits reach zero; real decisions remain visible. |
| Agent effort | Commands and bytes read before the first useful action; repeated same-state actions. | Less reconstruction; zero identical-action loops without new evidence. |
| Task speed | Elapsed time to first useful action and verified local completion on the same task. | Reduce measured delay; do not claim an unmeasured percentage. |
| Predictability | Disagreements between entry, status, continuation and effect admission on one snapshot. | Zero contradictory executable decisions in the accepted matrix. |
| Pleasantness | At natural completion, optional operator feedback: what was confusing or annoying? | Remove named friction; do not infer satisfaction from silence or ask every phase. |
| Trust | False completion/publication, unresolved owned evidence, skipped required checks reported green. | Zero. |

Model-size acceptance: repeat the same bounded task with an available less
capable model only after deterministic checks pass and an appropriate host is
available. Record model/host, interventions, task result and cost where known.
If not run, say NOT RUN. A clearer roadmap is not proof of model acceptance.

## Intentional model switches — bounded follow-up, not a workaround

The [existing voluntary handoff proposal](FUTURE%20GATE%20%E2%80%94%20VOLUNTARY%20MID-WORK%20CLAIM%20HANDOFF.md)
already owns the design seed. This session observed an inherited seat name
with a foreign live session: start refused WAIT_FOREIGN_OWNER while continue
returned PHASE BUILD. The operator confirmed the previous agent had stopped;
after lease expiry canonical claim adopted the same BUILD Work at E-7664. Reconcile the same ownership decision across surfaces
before treating switching models as frictionless.

A future implementation should transfer the same Work/phase through explicit
operator/current-owner authority, preserve history and fence the old claim
generation. Ordinary unrelated live takeover must still refuse. The proposal's
example handoff command is not an implemented instruction to run today. Do not
shorten the lease, copy session identifiers or rewrite canonical state.

## Deferred human and external boundaries

T-1426's FreeBuff Desktop attempt is operator-owned, not before
`2026-09-21T00:00:00+03:00` (Europe/Tallinn). Due time permits asking for the
manual result; it never authorizes the agent to consume quota. The exact
disposable-project action and `cc GREEN` / `cc FAIL` signals live in SRC-084.
Preserve them and keep unrelated work moving.

T-1317's missing Kiro evidence remains an external boundary. T-576's recovery
scratch deletion still needs its separate decision. Publication remains
paused: no push, tag or release is granted by this roadmap or SRC-086.

## Completion and expansion gate

Keep focused checks, core conformance, full required families, installed
runtime, host acceptance and publication readiness as separate verdicts.
The local corridor must prove request -> execute -> verify -> review ->
truthful local completion, including interruption/retry and a real stop.

Only then revisit the existing [future architecture roadmap](SAIPEN_FUTURE_ARCHITECTURE_20260918/future_architecture/12_ROADMAP.md)
and [adoption rules](SAIPEN_FUTURE_ARCHITECTURE_20260918/future_architecture/16_ADOPTION_RULES.md):
registry, lease broker, eligibility, optional portfolio context, one-shot
dispatch, observability, continuous workers and field acceptance. One bounded
gate at a time. Same-project parallel mutation stays deferred.

## Next-session instruction

> Reload canonical state and the original active source before acting. Treat
> this roadmap as a map, not a claim that any gate passed. T-1441, T-1439 and
> T-1440 are DONE (E-7783/E-7789/E-7797); T-1437 is in BUILD with the user-wait
> regression delivered and the SAITULS end-state work open; next in the chain
> are T-1435 M2-M14 and T-1361, then T-1428/SRC-083 and SRC-084's ordered work,
> as the canonical scheduler permits. Preserve T-1438's completed quarantine
> repair. Preserve dirty work, ownership and publication limits. Do not restart
> DONE T-1420..T-1423 or T-1347. Finish one bounded useful slice, checkpoint its
> exact proof, and continue to the next eligible action without asking for
> routine permission.

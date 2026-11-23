# Recursive compression campaign — measured local candidate

CURRENT OBSERVATION (2026-10-23 12:14 Europe/Tallinn): full-family attempt 5
is live as PID 16884; see FULL5-CONTROLLER.md. Its source generation changed
after launch (FULL5-DRIFT-OBSERVATION.md), so no sandbox verdict can be cited
for the changed live tree without the canonical identity/reuse gates.
Attempt 2 was interrupted, attempts 1 and 3 failed, and attempt 4 produced a
7,427-test zero-red PASS record but could not cite it because its requested
immutable identity and this session's verifier environment differ. See
FULL4-RESULT.md. No current-environment full PASS is cited yet. Current live
`python -B tools/protocol_budget.py --summary` measures 21,389/27,643 cold
(-22.6242%), 39,472/56,160 command resolution (-29.7151%), and unchanged
40,943 ordinary phase. All three numerical reduction targets remain unmet.

STATUS: INCOMPLETE. T-1857 / SRC-289 is in VERIFY; T-1858/T-1859/T-1860 remain
open. The original 22-requirement campaign has not been discharged. No ticket
was marked complete by this campaign, and no release or native deployment was
performed. Attempt 5 is in flight; its final result is not yet known.

## Actual root causes and resulting behavior

The scheduler had no admissible old Work, but its diagnostic chose an older
external blocker rather than the shared release obstruction. Four publication
roots and three dependent TODO tickets now project one `release:shared-index`
group without changing ticket identities, dependency edges or release checks.
The existing operator-wait vocabulary is reused. A DONE lifecycle phase alone
cannot produce a human completion claim while blocked Work remains.

The continuation incident has two separate defects. The engine omitted some
documented continuation input forms from its resume policy. Those forms now
share registry-owned parsing; independent native proof still decides authority.
The ZAICODE diagnostic prioritized a generic valve/operator flag over an
undelivered trusted-ingress attempt, hiding the missing bridge. A scratch-tested
diagnostic patch is preserved separately; it is unapplied and does not install
or authenticate the absent native issuer. Retyping `cc` cannot supply that
infrastructure. T-1858 explicitly retains genuine native LIVE acceptance.

## Wave disposition and exact next operation

| Wave | Disposition | Proven result / remaining operation |
|---|---|---|
| W0 | Local admission preserved | Exact original request is SRC-289; model-supplied local admission does not renew operator authority. Native provenance remains due. |
| W1 | Implemented, full verification pending | Shared blocker projection, honest idle status, existing independent-work route retained. Await the current gate before a local verification verdict. |
| W2 | Disposable Git feasibility only | Foreign-stage red control and two isolated concurrent worktree candidates pass. Production journal, source attribution and evidence binding remain unproved. Preserve refusal. |
| W3 | Blocked | T-1815/T-1816/T-1817/T-1856 and dependent T-1853/T-1854/T-1855 remain intact; do not unblock on fixture evidence. |
| W4/W5 | Scoped consolidation | Explicit rule inventory, BOOT ownership, conditional command inventory, resume schema and budget facts. No exhaustive equivalence claim for unchanged unnumbered law. |
| W6 | Targets unmet | Current cold context -22.6242%, command resolution -29.7151%, ordinary phase unchanged; all three targets remain open. |
| W7 | One cohesive subsystem simplified | Shared goal-budget fact/predicate and lighter state-proof imports. Other temporal/authority revalidations remain distinct. |
| W8 | Read-only inventory | Potential identical bytes identified within a fixed read budget. Actual saving zero; no migration/deletion. Retention-root decision is pending. |
| W9 | Existing cost controls preserved | Prior failed/interrupted and incompatible PASS attempts retained; current-environment full attempt 5 is single-flight. No comparable verification cost reduction established. |
| W10 | Incomplete | Inspect the live gate's terminal result, then preserve valid evidence; native, publication, original-history and Source requirements remain independent. |

## Frozen before/after measurements

`frozen-metrics.json` is the current normalized source/context observation.
Earlier `measurements.json` / `measure-summary.txt` are development snapshots;
their older context sizes are not the final candidate's sizes.

| Surface | Before | Frozen candidate | Interpretation |
|---|---:|---:|---|
| Cold loaded context, bytes | 27,643 | 21,389 | -22.6242% |
| Command resolution context, bytes | 56,160 | 39,472 | -29.7151% |
| Ordinary continuation context, bytes | 34,570 | 34,570 | unchanged |
| Ordinary phase context, bytes | 40,943 | 40,943 | unchanged; target unmet |
| SHIP/IMPROVE context, bytes | 55,625 | 55,625 | unchanged |
| Captured product Python files, LF bytes | 2,739,609 | 2,750,904 | +11,295 at 10:04; later source correction needs remeasurement |
| Same captured product files, branch sites | 6,592 | 6,627 | +35; AST proxy, not formal cyclomatic complexity |
| Same captured product files, functions | 835 | 844 | +9; no net Python-size reduction claim |
| State-proof import surface, engine modules | 20 | 8 | One fresh-process fixed proof |
| Same represented source, bytes | 1,318,131 | 254,294 | -80.7% for this import surface only |
| Historical storage saving | — | 0 | No evidence deleted or migrated |

Mandatory load sets and profile budgets are unchanged. The 40-file owned source
manifest was captured at 10:04 local and needs a fresh hash check after E-17361;
it is not a current attestation. The source export
is incremental against the captured working baseline, not a claim to own all
file-versus-HEAD changes. No exact aggregate count of eliminated decision paths
is claimed: the documented budget and audit classifiers have one owner each,
while their semantically distinct independent proof checks remain.

The earlier fixed-fixture idle classifier measurement grew from roughly
0.96 ms to 1.37 ms median for the richer shared projection. It is not an engine
speed improvement. The isolated proof's 45/25 ms elapsed samples are individual
observations, not a comparable routing/continuation benchmark. Verification
reuse/cost improvements cannot be inferred from an unmeasured hypothetical
full-rerun baseline.

## Verification and semantic preservation

Frozen known-bad controls cover shared blockers, native input spelling,
cc-all payloads, bounded STATE headers and the budget import boundary. The
same oracle is used before and after each corresponding implementation fix.
Focused/neighbor suites, full-source registry coverage and full-tree Ruff have
recorded results. These are scoped observations, not current full publication
or deployed native acceptance. An accidental test-variable NameError during
lint cleanup was caught and restored; the failed log and successful affected
rerun remain preserved. No assertion or mandatory gate was weakened.

The detailed old/new owner and retained-contract map is in W4-OWNERSHIP.md;
W6-W9-MEASUREMENTS.md covers temporal safety boundaries. REQUIREMENT-AUDIT.json
records evidence limits for every original requirement; it is not Source
terminal coverage. Attempt 4's PASS is incompatible with this session; attempt
5's live PID is not a PASS. Check current-tree generation and verifier identity
on its actual terminal record.

## Remaining real blockers and owners

* Native host owner: implement and verify the genuine input/issuer/actual-worker
  handshake using the existing separated broker. Confirm deployed build identity
  and exercise replay/root/session/worker/budget hostile controls. The exact
  diagnostic candidate and receiving-owner steps are in
  ZAICODE-NATIVE-INGRESS-HANDOFF.md. No model envelope grants this trust.
* Release/source owners: establish ownership and a reviewed source generation
  for the 206 foreign staged paths, or finish the canonical isolated-release
  journal/evidence contract without adopting that batch. Several unpublished
  foundation modules are absent from HEAD; a shadow index alone cannot bind
  this candidate to a reviewed release tree. No index-clearing action is asked.
* Original-history owner: supply a trustworthy source containing the exact
  missing original objects. One bounded fresh check reports 112 missing objects;
  the configured reachable origin refuses the exact absent commit, and the two
  known local packs contain no matches. Backup availability and authentication
  are not object recovery. Do not repeat the same exhausted search frontier.
* Storage-policy operator: explicit retention-root decision remains pending.
  The proposed narrow root and dry-run are saved; silence is not approval.

NEXT EXACT ACTION: await existing core-unit PID 16884 to its
terminal result; do not start a duplicate run or edit the tested source. Then
record its actual scoped verdict and repair attributable failures if any.

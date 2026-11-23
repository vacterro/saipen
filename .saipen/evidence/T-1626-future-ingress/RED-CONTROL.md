# T-1626 red control for the changed AUTO-14 oracles

Two tests own AUTO-14 on the live `future_gate/` corpus:

- `test_t1618_future_maturation` `Auto14PerformanceTests.test_P1_the_live_corpus_migrates_within_a_measured_budget`
- `test_t1614_future_gate` `FutureGateAutoDiscoveryTests.test_AUTO14_the_live_corpus_migrates_without_touching_an_original`

Both counted every live document as historical (`NEEDS_REVIEW == len(originals)`,
`next is None`). The first gate recorded through `saipen future add`
(FG-0046, machine format) turned both red: `45 != 46`. The interrupted session
fixed only the first; VERIFY found the second.

Changed oracle, both tests: the historical corpus is every document without the
v1 marker; `NEEDS_REVIEW == len(legacy)`; the routed gate's path is not a
historical document. `status()["next"]` is a gate id, so the path comes from
the index (`{id: path}`); the interrupted session's `routed.get("path")` would
have raised AttributeError on any non-None route.

## Why the earlier two mutants stayed green

Both were equivalent mutants. `build_index` keeps a second net,
`if doc.problems and state == DEFERRED and not reviewed: state = NEEDS_REVIEW`,
and every historical document carries the problem "no machine header", so
mutating `_initial_state` alone (or forcing `machine=True`, which only yields
invalid-header problems) does not change the observable classification.

## Mutants that change behaviour (scratch copies; live tree untouched)

`red_control_t1626.py <repo root> <scratch dir>` copies tools/, future_gate/,
saipen/, extensions/, bin/ and VERSION per mutant. Measured 2026-10-06:

| Mutant | P1 | AUTO14 |
|--------|----|--------|
| control (none) | OK | OK |
| A both nets removed: historical document DEFERRED | FAIL `0 != 45` | FAIL `0 != 45` |
| B `_initial_state` always NEEDS_REVIEW: machine gate counted historical | FAIL `46 != 45` | FAIL `46 != 45` |
| C pre-T-1626 oracle on the current corpus (the defect) | FAIL `45 != 46` | FAIL `45 != 46` |
| D `status()["next"]` names a NEEDS_REVIEW gate | FAIL historical path routed | FAIL historical path routed |

Live tree: `python -B -m unittest test_t1618_future_maturation test_t1614_future_gate`
-> Ran 59, OK. ruff 0.16.0 check: clean on both files.

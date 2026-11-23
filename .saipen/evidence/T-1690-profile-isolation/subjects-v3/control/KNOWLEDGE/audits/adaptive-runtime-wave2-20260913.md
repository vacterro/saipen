# Adaptive Runtime Wave 2 — executable strategies (2026-09-13)

Post-T-1317 super-wave, Phase 1 (+ the parts of Phases 2/3 that are semantics).
This record exists so the conclusion can be reproduced without trusting prose.

## What landed

`saipen/RUNTIME.md` promised Wave 2 as staged and unimplemented. Wave 2 is now
executable in `tools/saipen_engine/runtime/base.py`:

* bounded task classes `IMPLEMENT|REPAIR|VERIFY|RESEARCH|AUDIT|MAINTENANCE`;
* bounded strategies `LONG_BUILD|BOUNDED_RESEARCH|VERIFY_ONLY|RECOVERY`;
* `select_strategy(task_class, helper_reason=None, control_plane=False)`;
* `strategy_projection(..., capabilities=...)`;
* `StrategyError` (a `RuntimeInfoError`) for out-of-vocabulary input.

`LONG_BUILD` is the default and `helper_ceiling` is 0 by default. A helper needs
one of exactly four declared justifications (`isolated-research`,
`independent-verification`, `noisy-investigation`, `genuinely-parallel`, the last
buying a maximum of 2). `max_subagent_depth = 1`, `recursive_helpers =
DENIED_BY_POLICY`, and `depth_enforcement = "UNKNOWN"` because the Wave-1
capability vocabulary exposes no depth control — the policy is stated, the
enforcement is NOT claimed. `subagents=false` collapses the ceiling to 0.

Read-only surface:

```text
saipen runtime [--task-class NAME] [--helper-reason NAME] [--control-plane] [--json]
```

Nothing is persisted: no provider/model/strategy value reaches STATE, BOARD,
LOG, a cache, or a handover.

## Reproduce

```bash
cd <clone>
python -m unittest tools.test_adaptive_runtime        # -> Ran 29 tests, OK
python -m ruff check tools/saipen_engine/runtime tools/test_adaptive_runtime.py
python tools/saipen.py runtime --task-class repair --control-plane
python tools/validate.py --gate core
```

Observed at this gate:

* `tools.test_adaptive_runtime` — 29 tests, OK (15 Wave-1 + 14 Wave-2).
* ruff — all checks passed.
* `saipen runtime --task-class repair --control-plane` prints
  `task class : REPAIR / strategy : RECOVERY / helpers : max 0 (depth 1,
  enforcement UNKNOWN) / context : RECOVERY (56320 bytes, child packet <= 8192)`.
* `validate.py --gate core` — **38 problem(s), 25 warning(s)**.

## Broad-gate baseline vs final

| | problems | warnings |
|---|---|---|
| last recorded pre-wave core gate (E-6043) | 37 | 25 |
| previous T-1317 gate final | 38 | 25 |
| this gate, after the Wave-2 change | 38 | 25 |

DELTA FROM THIS WAVE: **0 problems, 0 warnings**. No validator finding mentions
`saipen/RUNTIME.md`, the runtime package, or the strategy surface. The 38
problems are the pre-existing T-1317 working-tree condition: every one is
`runtime manifest names a file git does not track`, naming files this wave did
NOT create (they are untracked from the earlier T-1317 gates and clear on
commit). Wave 2 added **no new files at all** — deliberately, because a new file
under `tools/` becomes a manifest problem until it is committed.

## Honest limits

* `child_packet_ceiling_bytes` is EXPRESSED, not enforced in-process. No harness
  currently routes a helper launch through it. Reported UNKNOWN where unproven.
* Recursive-helper prevention is POLICY only (see `depth_enforcement`).
* The `why` strings and ceilings are pure functions of declared input; they are
  not a model-performance claim, and this record claims no token saving.
* T-1317 remains BUILD and T-1318 (canonical malformed-`phase` recovery) remains
  open; this wave does not close them.

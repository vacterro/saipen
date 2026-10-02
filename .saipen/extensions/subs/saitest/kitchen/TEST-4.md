# TEST-4 -- HUNT-11 independent reproduction

Source: `3a343e8d0e5a04e2cb43b671c9072996e810c65a` / `git-delta-v1:0e4e6d78f40ffa3cd8fa5ea9c0d5ca1e64307f1c1f98d8803c75e224100a0440`

## Scenario A -- Ruff gate

- Minimal input: current `tools/` and `tests/`.
- Command: `python -m ruff check tools/ tests/ --output-format concise`
- Observed: exit 1, exactly 89 diagnostics.
- Verdict: REPRODUCED.

## Scenario B -- release parity

- Minimal input: current source read by `run_release_executor_probes()`; mutations remain inside its temporary fixture clones.
- Command: `python -c "import sys; sys.path.insert(0,'tools'); import run_scenarios as r; r.run_release_executor_probes()"`
- Observed: exit 1 at `tools/run_scenarios.py:6683`; `tools/saipen_engine/release.py:3303` refuses because 32 locale kitchen README badges lack fixture version `v7.226.1`.
- Verdict: REPRODUCED.

T-1115 receipt repair was separately green: receipt 26/26, CORE 17/17, conformance 29/29. No third scenario emerged.

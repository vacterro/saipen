# TEST-3 run record

Source: `3a343e8d0e5a04e2cb43b671c9072996e810c65a` / `git-delta-v1:9964e4c9d5e4335b64c3d6faa7c25942e7dd71b4995646e7c5e5229f20ef1f25`.

Safety ceiling: two read-only project invocations; release probe owns only temporary fixture clones; 120 seconds; no network beyond local file remotes; no project-tree mutation.

## Scenario A — declared Ruff gate

- Family: adversarial content / dead code.
- Minimal input: current `tools/` and `tests/`.
- Command: `python -m ruff check tools/ tests/`.
- Observed: nonzero; 89 diagnostics. Representative evidence: `tools/freshness.py:474 E501`, `tools/test_v7_producer_parallelism.py:30 F401`, `tools/test_v7_producer_parallelism.py:206 F841`.
- Verdict: `REPRODUCED`.

## Scenario B — release fixture with stale locale baseline

- Family: environment / order and repetition.
- Minimal input: `run_release_executor_probes()` reading current release metadata; its writes stay in temporary clones.
- Command: `python -c "import sys; sys.path.insert(0,'tools'); import run_scenarios as r; r.run_release_executor_probes()"`.
- Observed: nonzero traceback at `tools/run_scenarios.py:6683`; `tools/saipen_engine/release.py:3303` rejects locale badges that do not equal fixture version `v7.226.1`.
- Verdict: `REPRODUCED`.

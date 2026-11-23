# T-1946 — commit and push T-1944/T-1945 repairs to GitHub

Request (SRC-345): "commit the completed T-1944 and T-1945 repair work to GitHub".
BAR: the requested change is present and demonstrated against the user's own description.

## Pushed

- local main == github-backup/main == 1535d2e519564f7e5108c81bf955f9d2797fd133
- commits pushed: 7949027c, 05275edb, fdfa5886 (merge), 1535d2e5
- the 8 GitHub-only docs commits (README/SUPPORT/FUNDING) were MERGED, not discarded

## Verified on a fresh clone of the GitHub remote

```
$ git clone --depth 1 https://github.com/vacterro/saipen.git
$ python tools/saipen.py status --json
{"ok": true, "phase": "SCOUT", "task": "T-1946", "log_tail_event": 18968, ...}
$ python tools/validate.py
Validation FAILED: 2 problem(s), 19 warning(s)  # both inherited, see below
$ PYTHONPATH=tools python -m unittest test_t1945_host_trust test_t1945_analysis_progress \
    test_t1945_campaign_driver test_t1945_incremental_discovery \
    test_t1944_core_wave1 test_t1944_wave2
Ran 104 tests in 2.842s
OK
```

## The two remaining validator problems are inherited, not introduced

1. engine-state-contract -- state.schema.json drifted from state.py. Present
   before this work; needs a deliberate two-file change, out of this scope.
2. closure provenance EX-000022 / T-1630 -- EX-000022 lives under
   .saipen/recovery/conformance/, which .gitignore line 42 declares
   unshipped per-machine receipts (23 MB). A clone inherits no verdict.
   The worktree reports the same class of failure for the same reason.

## Blocker encountered and repaired

git fetch failed on every remote: 'bad object
refs/codex/turn-diffs/captures/1785165795234/fb80dcb4-.../base'. The ref
pointed at 9d3542bd, an object this repository does not have. Recorded the
value in V:/_TEMP_/deleted_ref.txt and deleted the ref with
git update-ref -d. Fetch and push both succeeded afterwards, so the ref was
the only obstacle.

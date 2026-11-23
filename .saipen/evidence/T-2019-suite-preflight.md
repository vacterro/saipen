# T-2019 — long-suite preflight

Source: SRC-389 and the operator-supplied
`audit/SAIHANDOFF_BZDECOMP_SUITE_PREFLIGHT_20261104_031152_2fa73462.md`.

## Implemented

- VERIFY owns SUITE-PREFLIGHT-01: last duration >300 s means affected tests
  first; after any red run, repair/rerun the failing script, inspect siblings,
  then one full suite. A consistently >600 s PASS gets a project speed-ticket
  suggestion, not a new closure gate.
- `test suite run [T-###] --fail-fast` incrementally scans both complete output
  streams and terminates the owned process tree on a FAIL verdict. PowerShell
  Exception/Write-Error prefixes and display gutters are recognized; source
  excerpts are not verdicts. A partial run stays FAIL even with exit code 0.
- Records keep process time, pre/post subject hash and parsing overhead,
  explicit script durations, timing availability, first FAIL line, and whether
  fail-fast stopped the process. Status exposes duration and first failure.
- Timing input: `SAIPEN-SCRIPT {"script":"Test-X.ps1","duration_s":1.2}`
  or `DURATION: Test-X.ps1 1.2s`, flushed by the project runner. Missing timing
  output stays unavailable. BZDECOMP's current runner prints no script timings;
  its T-651 owns instrumentation and suite speed. No runner timings invented.
- `test suite affected [T-###]` is read-only, includes staged/unstaged/untracked
  paths and changed qualified symbols/count constants, follows fixture text
  references, and includes the declared runner's nested Git owner. It labels
  limitations, omits the full-suite entrypoint and utility generators from the
  runnable candidate list, and does not execute candidates.

## Evidence

- Initial isolated focused run: 76 PASS, record
  `.saipen/evidence/focused-unit/cf8fb49f84bff5cd-20261104T032613036726Z.json`.
  Runtime 255.579 s: execution 71.265 s, copying 151.219 s, cleanup 30.657 s.
  This is SAIPEN's own unit sandbox, not the in-place declared-suite runner.
- Final PowerShell grammar delta: only `test_t2019_suite_preflight.py`
  rerun, 12 PASS in 6.121 s, including real pwsh and the ignored nested repo.
  Final exact-tree canonical record:
  `.saipen/evidence/focused-unit/67ef25d5a3ddabff-20261104T033002415179Z.json`,
  12 PASS, duration 170.328 s (request wall 181.406 s). No full-suite retry.
- Same unchanged stub-mismatch test with only `_failure_line` disabled:
  expected FAIL, 4.187 s exceeds its 3 s stop bound. Enabled detector stops
  under 3 s and its descendant cannot start the next fixture after 3.1 s.
- The old suite-record refusal test found one new usage placeholder error;
  repaired it and reran only that failed test: PASS. Other 29 tests passed;
  the isolated focused run subsequently confirmed all 30.
- Targeted Ruff: PASS. Pre-work Git index/current comparison of touched Python
  files: 0 new diagnostics, 40 inherited diagnostics in tools/saipen.py.
- Canonical full Ruff was diagnostic FAIL: 849 findings in the existing tree.
- Core validator was diagnostic FAIL: EX-000045 installed-generation proof
  is stale; three manifest files are untracked (two new T-2019 files and the
  foreign tools/t2017_red_control_lifecycle.py). No global-green claim,
  publication, foreign staging, or full-family rerun.
- BZDECOMP was read only. Real `affected` includes both `.` and `vrv` Git
  owners and locates Test-NativeMissionRouter.ps1, Test-ClassicWrecks.ps1 and
  Test-GamePrefs.ps1. No BZDECOMP state or source edits and no test execution.

## Review limits

Static text candidates cannot certify dependency completeness or every table
count assertion. The agent must review those; policy requires it explicitly.
Output buffering delays fail-fast until the child flushes. Untimed runners
need to emit the documented timings before per-script values can appear.

An independent existing limitation was reproduced in a disposable fixture:
subject(root) ignores a nested source directory excluded by the outer Git
repository. Changing an ignored production file leaves that subject unchanged
(`.saipen/tmp/t2019_nested_subject_probe.py`). The candidate planner fixes
discovery across the declared nested Git owner; evidence-subject/reuse identity
for ignored nested production trees remains separate work, not claimed fixed.

# T-1409 installed acceptance — 2026-09-19

Continuation SRC-071: park T-1408 truthfully (no mutation; reported in the
closure), repair T-1371, install the current committed runtime and field-prove
T-1386 on the installed bytes. No push, no tag, no public release.

## 1. T-1371 repair — source

- Commit `36771d12` on `main`: `tools/autoinject.py`, `tools/saipen.py`,
  `tools/test_distribution_report.py`; 3 files, 142 insertions, 36 deletions.
- `distribution_report` publishes the newest scheduler run under `last_run`
  (status/skip/rc/dirty/at/head/in_flight) and the `fresh` verdict no longer
  consults it. `blocked`/`blocking_paths` were removed: one meaning, current
  state in current fields, history in `last_run`.
- Anchored oracle pair, same module run as a script:
  - verifier `test_distribution_report.py` sha256
    `7C94AC4447E139D4980DE2334FB0931FFF52403AD204608DF36179C5622E045A`
  - pre-fix subject `autoinject.py` sha256
    `66C456A6C2998EB3BA407E6917A57AE1508AD322CE2EEC8003AC53B67DF8740D`:
    RED — 27 tests, failures=1 errors=8; specimen
    `test_a_historical_skip_no_longer_poisons_current_homes` line 283
    `AssertionError: False is not true` on `fresh`.
  - post-fix subject sha256
    `7E5E4684E5092E1A37566E5803A6920602C7158949BBBBCA88083FD5E88EA2A6`:
    GREEN — 27 tests OK.
- Review questions: no historical scheduler event can move the current
  freshness verdict (the `fresh` expression references no run), and a currently
  dirty injected surface cannot be published on last-run success
  (`bootstrap/schedule-run.ps1` re-runs the scoped
  `git status --porcelain -- <injected surface>` on every run).
- Scheduler probe group (`SAIPEN_SCHEDULER_PROBES_ONLY=1`): 59/60; the dirty
  tracked and untracked-inside-surface refusals PASS; the single
  `scheduler shell uninstall without schtasks` failure reproduces identically
  on a pristine `1a8f15f5` worktree and is inherited.
- Validator conformant (34 inherited warnings); `ruff check tools/ tests/`
  clean; `git diff --check` clean.

## 2. Committed injected surface

Surface taken from its one owner `saipen/MANIFEST.json` (copy_trees + files +
the manifest), 53 paths. At `36771d12`:

    git status --porcelain=v1 --untracked-files=all -- <surface>  ->  CLEAN

## 3. Supported injection

Ran the scheduled runner itself, the supported mechanism:

    powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass ^
      -File bootstrap\schedule-run.ps1 -CloneRoot <repo>   ->  rc=0

    inject.log: head=36771d12d47003aa2c5ccb81d410919ae1ba12ce exit=0
    stamped 6 homes at gen-sha256:2ccdb77a2fd80f1543acb20dfddd4e70ddc3efdd47c859b546215e0baecdb0b6

Post-injection current state (worktree `distribution_report`):

    installed 6, stale 0, unknown 0, surface_unknown 0, fresh true
    expected_generation = newest_installed_head generation
      = gen-sha256:2ccdb77a2fd80f1543acb20dfddd4e70ddc3efdd47c859b546215e0baecdb0b6
    last_run: status success, rc=0, head=36771d12, dirty []

`python tools/autoinject.py --check` -> `fresh: 6 agent home(s) at
gen-sha256:2ccdb77a...`. Installed `saipen status --json` carries the same
fresh/`last_run` schema, proving the installed runtime includes `36771d12`.

## 4. Installed T-1386 field proof

Runtime under test: installed home
`C:\Users\vac34\.config\opencode\skills\saipen` (generation 2ccdb77a, stamped
2026-09-19 17:51:05). Guard identity:

    source tools/saipen_engine/guard_events.py sha256
      6A9E1B9ACDF21C6768110DE7AE28FCE5747F410E913A9FA68822A14B60C7DE6E
      (= the T-1386 anchored post-fix subject)
    installed .../guard_events.py sha256
      86948D939F0B5E5B03CD3B1539F95D77621B615DF6BDDB80957CD64B65B9F11A
      (one CRLF of transport: normalized-equal True, 72823 vs 72824 bytes)
    same_runtime_generation(repo, installed) -> True

Executed the anchored oracle from the installed home, so the classification and
the CLI both run installed bytes:

    python "<installed>/tools/test_t1386_canonical_payload.py"  ->  17 tests OK

Covered there: the three exact field checkpoint lines whose quoted evidence
mentions `.saipen/STATE.md` classify `saipen_op` and are admitted in a
session-shaped project with no `PROTECTED_CANONICAL_NAMESPACE` and no reworded
retry; `rm -rf .saipen/STATE.md` stays `shell` with
`shell_protected_namespace` true; shell tails outside the payload stay shell;
T-1398 ingress (`saipen start '2>&1'` never mints a request) preserved.

## 5. T-1408 operator disposition

Unchanged and parked: BLOCKED, ticket-scope, no product bytes, no synthetic
release. The continuation's decision is recorded on its BOARD blocker field.

# T-1893 — eight unattached probe scripts, four now under canonical discovery

Status at SCOUT: the ticket asked whether the eight scripts were retained
deliberate probes or leftovers CLEAN may retire. The question answered itself
in a way that changed what the ticket should do, so the finding is recorded in
full before any code changed.

## Why discovery never ran them

The canonical family command is `python -m unittest discover -s tools -p test_*.py`
(`tools/saipen_engine/core_unit.py:4`), and `test_runner.py:71/92` declares the
same `test_*.py` pattern. Five of the eight are therefore invisible to the suite
by name alone:

```
regression_conformance_closure.py       regression_core_audit_fixes.py
regression_second_wave.py               regression_second_wave_audit_fixes.py
regression_second_wave_receipt_fixes.py second_wave_regressions.py
t1318_current_generation_probe.py       t1382_field_probe.py
```

No test, CI step, MANIFEST entry, doc, pyproject/ruff entry or BOARD/LOG row
names any of them (searched `tools/`, `saipen/`, `docs/`, `.github/`, `*.md`,
`.saipen/BOARD.md`, `.saipen/LOG.md`, `.saipen/logs/*.md`,
`.saipen/MANIFEST.json`). They are tracked files, so this is not a staging
accident — they were committed and then never wired up.

## What running them actually showed

Every script was executed as-is, twice, from the project root. Exit codes are
the scripts' own.

| script | exit | its own verdict | verdict |
|---|---|---|---|
| `regression_conformance_closure.py` | 0 | `29/29 checks passed` | **GREEN, 29 unique checks** |
| `regression_second_wave_receipt_fixes.py` | 0 | `33/33 SECOND-WAVE receipt regressions passed` | **GREEN, 33 unique checks** |
| `regression_second_wave.py` | 0 | `ALL TESTS PASSED` (T-1015 redaction) | **GREEN** |
| `second_wave_regressions.py` | 0 | `All Second Wave Regressions PASSED` | **GREEN** |
| `regression_core_audit_fixes.py` | 1 | `AttributeError: ... has no attribute 'build_event'` | **ROTTED** |
| `regression_second_wave_audit_fixes.py` | 0\* | 3 `FAIL` lines then `ValueError: substring not found` | **ROTTED** |
| `t1318_current_generation_probe.py` | 1 | `RUNTIME_STALE` | **needs a live host** |
| `t1320_fleet_native_smoke.py` | 1 | `HOST_CHAIN_FAILED` (source==installed hash) | **needs a live host** |

\* `regression_second_wave_audit_fixes.py` raises an uncaught `ValueError` inside
`main()`, which Python exits with status 1; the `0` above is the shell pipeline's
status, not the script's. Its three recorded `FAIL` lines are the real verdict.

### The two rotted scripts

Neither is a product defect; both are fixtures that drifted away from the engine
they pin:

* `regression_core_audit_fixes.py:210` reads `ops_mod.build_event` and patches it.
  `tools/saipen_engine/operations.py` has no `build_event` (only
  `no_delta_build_events`), so the CORE-003 redaction case cannot even set up.
  The probe's own docstring sends the reader to
  `python tools/test_core_audit_fixes.py`, a path that does not exist.
* `regression_second_wave_audit_fixes.py` builds a fixture STATE the current
  schema refuses (`current-schema STATE requires absolute saipen_home, got
  'fixture-home'`) and at line 459 indexes `"T-9"` in a board that no longer
  contains it (`ValueError: substring not found`).

Repairing them means re-deriving each assertion against today's engine, which is
real work with its own VERIFY — not something to bolt onto a wrapper ticket. They
are left exactly as they are, recorded here, and **no file is deleted or
renamed** (HUNT owns no destructive mutation and this ticket took none).

### The two host probes

`t1318` and `t1320` report on an installed OpenCode runtime, not on this tree:
`t1320` prints `source_hash == installed_hash` and still `HOST_CHAIN_FAILED`, and
`t1318` reports `RUNTIME_STALE` twice with empty `stderr_tail`. Wrapping them
would turn an unrelated host's state into a red in this project's suite, which
is the isolation rule in §04B of the campaign (a test subject must not inherit
an unrelated runtime home). They stay manual field probes.

## What was built

`tools/test_t1893_probe_wrappers.py` — four unittest cases, one per green probe.
Each runs the script as a subprocess from the project root and asserts **two**
things:

1. the probe exits 0, and
2. the probe prints its own success line.

Both are required because two of the four return 0 from a `main()` that prints
its verdict: an exit-code-only check would pass on a script that silently lost
its final assertion, and a success-line-only check would pass on a script that
printed and then crashed. Failure messages quote the probe's own last 25 output
lines, so the wrapper never invents a verdict.

Total added suite cost: **8.9 s** for 62 previously-uncollected checks.

## Red/green control (`.saipen/evidence/T-1893-probe-wrappers/red-control.log`)

Transcript, not a claim:

* **GREEN** — `python -m unittest tools.test_t1893_probe_wrappers -v` →
  `Ran 4 tests in 7.160s / OK`, exit 0.
* **RED, real mutation** — one assertion inverted inside
  `regression_second_wave_receipt_fixes.py`
  (`"clean2" not in` → `"clean2" in`, 42→38 bytes):

  ```
  FAIL W2-005 entry NOT compacted while in debt -- {'ok': True, 'compacted': [], 'skipped': ['clean2']}
  32/33 SECOND-WAVE receipt regressions passed
  FAILED (failures=1)
  exit: 1
  restored byte-exact: True
  ```

  So the wrapper follows the probe's real verdict; it does not merely re-run a
  file that always passes.
* **RED, both assertions** — two synthetic stubs: one exits 1, one exits 0
  without the success line. Both produced the intended `AssertionError`, which
  proves the success-line half of the contract is live and not dead code.

## Isolation verified

None of the four wrapped scripts writes into this project. Each one was checked
for `Path(__file__).parent.parent` writes and for `cwd=`:

* `regression_conformance_closure.py` — `tempfile.mkdtemp(prefix="conformance_")`,
  all receipts and STATE under that root.
* `regression_second_wave_receipt_fixes.py` — nine separate `tempfile.mkdtemp()` roots.
* `regression_second_wave.py` — `tempfile.TemporaryDirectory()`, invoking
  `tools/saipen.py --project-root <temp>`.
* `second_wave_regressions.py` — `tempfile.TemporaryDirectory()`, same pattern.

No canonical STATE/BOARD/LOG/index was read-modify-written by any of them.

## Not claimed

* The four wrapped probes are not claimed to be complete coverage of anything.
  They are claimed to run, to pass, and to fail when their subject fails.
* The four unwrapped scripts are not claimed to be dead. Two are rotted fixtures,
  two are host probes. Retiring or repairing them is a separate decision with
  its own evidence and is deliberately **not** taken here.
* No suite-level claim: this ticket adds four tests to the inventory and reports
  the focused run only.

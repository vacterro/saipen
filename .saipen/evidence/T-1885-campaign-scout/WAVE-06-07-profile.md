# WAVE 06/07 — process leaks and test cost, measured

Both waves were profiled before any change, per the campaign's rule that a
performance claim needs a workload identity and real numbers.

## WAVE 06 — the six "leaked" PIDs are not leaks

`processes_leaked` in the last complete core-unit record
(`0ade2cd4b0d85ad8-20261024T142656492584Z.json`) lists six PIDs:

```
10044 14672 19260 19928 25660 33052
```

All six are **gone** when checked now. That matches the field's documented
semantics in `tools/saipen_engine/test_runner.py:617`: it is the historical
**PRE-close** observation, taken before `ProcessTree`'s context exit reaps the
descendants. The producer says so in its own comment, and
`_unit_family_report` deliberately does not relabel the observation as a
post-cleanup failure.

Verdict: **not a defect, and nothing to fix.** No process was killed. The
campaign forbids terminating a process because an old report names its PID, and
that prohibition was the correct call here — the PIDs were already dead.

## WAVE 07 — the slowest modules are real integration cost

From `module_durations_s` in the same record:

| rank | module | seconds |
|---|---|---|
| 1 | test_t1613_publication_convergence | 237.4 |
| 2 | test_t1553_mid_session_activation | 162.9 |
| 3 | test_t1326_board_compaction | 154.7 |
| 4 | test_protocol_admission | 151.1 |
| 5 | test_validator_layout_parity | 143.9 |

Distribution over 504 modules: sum 8025s, median 5.2s, mean 15.9s, p90 45.8s.
The top 20 modules are 2615s, **32.6% of all module time**; 18 modules over
100s account for 2416s.

The top module was profiled per test rather than assumed:

```
import: 0.06s
  10.7s  test_L_installation_and_distribution_suites
  38.7s  test_A_B_H_I_the_locked_plugins_defer_and_the_publication_stays
  53.3s  test_C_K_the_next_run_converges_the_deferred_consumers_without_a_human
  31.6s  test_D_an_install_already_holding_this_generation_is_not_rewritten
  17.7s  test_E_a_host_this_machine_never_installed_is_skipped_not_created
  17.3s  test_F_a_dirty_injected_surface_refuses_before_publishing
  30.2s  test_G_a_terminal_failure_on_a_blocking_surface_still_fails_closed
TOTAL 199.5s, ran 7
```

Each test builds a throwaway publisher and runs the real
`bootstrap/schedule-run.ps1`. Building that fixture costs **1.7s** and 43.6 MiB
(measured twice: 1.6s, 1.7s) — so ~32s per test is genuine multi-process
publication work, not fixture overhead. There is no cheap win here, and
"optimizing" it would mean replacing real integration evidence with a mock,
which the campaign forbids.

## The real cost is the sandbox copy, not the tests

The focused gate on T-1885 reported:

```
duration_s 79.688
timings_s {"execution_wall_s": 0.172, "environment_identity_wall_s": 2.188,
           "copy_wall_s": 60.5, "hash_wall_s": 0.156, "cleanup_wall_s": 16.657}
copy_metrics {"subject_copy_s": 17.766, "canonical_copy_s": 42.39,
              "canonical_copy_attempts": 1}
```

**0.17s of test execution inside an 80s gate.** Direct `shutil.copytree`
measurements of this checkout, same ignore rules, pristine temp targets:

| exclusion | copy time | files | size |
|---|---|---|---|
| none (production behaviour) | 77.0s | 135450 | 1815.7 MiB |
| minus `.git` | 39.3s | 90487 | 1470.7 MiB |
| minus `.saipen` | 17.7s | 46306 | 366.5 MiB |
| minus `.git`, `.saipen`, `audit` | 0.53s | 1332 | 21.4 MiB |

Tree composition: `.saipen` 89660 files / 1474 MiB (evidence alone 53117 files
/ 1079 MiB, recovery 161 MiB, kitchen 109 MiB); `.git` 44963 files / 345 MiB.

So the gate's cost is dominated by copying durable history that a selected test
rarely reads — and because `.saipen/evidence` grows with every run (584
core-unit records already), that cost rises over time on its own.

## Why no change was made in this wave

The obvious exclusion is not safe as stated:

- **203** of 511 test modules mention both `.saipen` and `evidence`, and **18**
  build literal `.saipen/...` paths against the live tree (e.g.
  `test_t1817_handoff_artifacts.py:29-30` reads
  `.saipen/evidence/T-1817-*.md`; `test_source_contract_derivation.py:425`
  reads `.saipen/archive/source/SRC-272.md`). Excluding `.saipen/evidence`
  wholesale would break tests that verify history — the exact thing the
  campaign's §07 hard rules forbid.
- `.git` cannot be excluded wholesale either: `tools/validate.py` itself runs
  `for-each-ref`, `rev-list --remotes` and `git show HEAD:<path>`, so a sandbox
  without history cannot validate.
- Deciding "this selection needs no history" from static imports is precisely
  the inference the protocol says does not prove dependency completeness.

A correct fix has to be *selection-aware* — copy the durable trees only when
the selected modules need them, with a fail-closed default — and that is a
design change, not a one-line exclusion. It is recorded here rather than
guessed at, so the next attempt starts from measurement instead of from zero.

## Incidental finding, not acted on

`.git` contains 98 MiB of `lost-found/` (2285 files) and twelve `t1283lab*`
directories totalling ~110 MiB that nothing in `tools/`, `saipen/` or
`.saipen/KNOWLEDGE/` references. Excluding just those from the copy measured
70.1s → 56.2s (-13.9s, -19.8%) on 135439 → 96530 files. That is a property of
this particular local checkout, not of the codebase: hard-coding those names
into the copy filter would be a local-environment hack that a fresh clone
silently does not need. Left in place deliberately.

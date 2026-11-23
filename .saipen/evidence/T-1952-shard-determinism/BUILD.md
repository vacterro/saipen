# T-1952 BUILD — make the sandbox describe itself

## The defect in one sentence

A `core_unit` sandbox is a copy of the working tree, and it carried two install
pointers copied verbatim that name the **source** tree, so a test inside the
copy could be answered by the source tree's engine and STATE — which made one
tree fingerprint produce opposite verdicts depending on whether the source tree
happened to be clean.

## The measurement that located it

Induced drift in a copy (`# drift probe` appended to `tools/saipen_engine/phases.py`,
which is inside the tested subject), then each pointer rewritten or not:

| rewritten | `test_t1645_zero_hunt` | `test_t1880` | `test_t1939` |
| --- | --- | --- | --- |
| nothing | `FAILED (failures=2)` | `FAILED (failures=3)` | `FAILED (errors=3)` |
| `.saipen/STATE.md` only | `FAILED (failures=2)` | `OK` | `OK` |
| `bin/` only | `OK` | `FAILED (failures=3)` | `FAILED (errors=3)` |
| both | `OK` | `OK` | `OK` |

Two pointers, two distinct mechanisms, no overlap. Without drift all four
configurations pass — which is why this looked like flakiness and why `--jobs 1`
in the T-1606 REVIEW run (8387 ran, 0 red) never fired it.

**Mechanism A — `bin/saipen`, `bin/saipen.cmd`.** The launchers name the engine
by absolute path:

```
"C:\ProgramData\SAI\SAIPEN\python\3.11.9-64\python.exe" "V:\___VAC\...\_SAIPEN\tools\saipen.py" %*
```

T-1645's two PATH-miss tests EXECUTE that launcher from inside the copy, so the
child ran the source engine against the source STATE and asserted about a
fixture project it never read: `AssertionError: None != 'T-1'`.

**Mechanism B — `.saipen/STATE.md`'s `saipen_home:`.** Inside the copy,
`state.running_home()` is the copy (`Path(__file__).resolve().parents[2]`), but
`saipen_home` named the source install. `operations._read` calls
`home_refusal(state.get("saipen_home"))`, which blocks only when
`diagnose_install_mismatch` finds the two fingerprints **unequal**. So the
refusal appeared exactly when source and install had drifted:

```
File "...\operations.py", line 735, in _read
    raise HomeDeadError(
home-dead: home-divergent: the RUNNING install is V:\___VAC\...\_SAIPEN
but STATE.saipen_home names V:\_TEMP_\saipen-core-unit-...\project
```

Both files are install GENERATED: gitignored (`.gitignore:92:/bin/`), untracked,
machine-specific, and `bin/` contributes **0 of 843** frames to
`install_identity.normalize_install_frames`.

## The repair

`tools/saipen_engine/core_unit.py`:

1. `FINGERPRINT_EXCLUDED = (".git", ".saipen", "bin")` — generated plumbing is
   not tested subject, and leaving it in the digest meant the rewrite itself
   would have changed the identity it was being compared by.
2. `COPY_ALWAYS = ("bin",)` — a DECLARED sandbox scope drops excluded top-level
   names; `bin` must survive that, because the family executes it.
3. `rebind_sandbox_pointers(sandbox)` — rewrites both launchers to the canonical
   relocatable form (`machine_runtime.render_launchers(".", None, sys.executable)`,
   `%~dp0..` / `$here/../`) and rewrites `saipen_home` to the copy's own resolved
   path. Called at the end of `copy_tree_consistent`, so EVERY sandbox (whole or
   shard) gets it, and what it did is returned as `copy_metrics["pointers"]` for
   the record.

A missing or unreadable launcher/STATE is skipped, never invented: `missing:bin/...`
is already the honest answer.

## Proof the repair names the copy

```
copy_metrics.pointers: {'rewritten': ['bin/saipen.cmd', 'bin/saipen',
                                      '.saipen/STATE.md'],
                        'home': 'V:/_TEMP_/t1952-real-eq1ejm1p/project'}
fingerprint stable across copy: True 5f0962626c0c90fc
copy launcher: "...python.exe" "%~dp0..\.\tools\saipen.py" %*
copy home:     saipen_home: "V:/_TEMP_/t1952-real-eq1ejm1p/project"
```

Then, with drift induced in the copy, all three previously-red modules green.

## The regression test and its RED control

`tools/test_t1952_sandbox_points_at_itself.py`, 5 tests:

```
Ran 5 tests in 0.044s
OK
```

RED control — the two `rebind_sandbox_pointers(...)` calls replaced by a literal
`{"rewritten": [], "home": None}`:

```
FAIL: test_a_copy_of_a_drifted_source_agrees_with_itself
FAIL: test_the_copy_names_itself_and_not_the_tree_it_copied
FAIL: test_the_rebind_is_recorded_for_the_evidence_record
Ran 5 tests in 0.041s
FAILED (failures=3)
```

Restored, and green again. The test fails for the right reason without the fix.

## Determinism, two rounds through the real copy path

`copy_tree_consistent` → fingerprinted → three previously-red modules:

```
round 1 fingerprint=a16c7df0d09310e4
   test_t1645_zero_hunt                           OK
   test_t1880_wait_survives_phase_shortcut        OK
   test_t1939_needs_detach                        OK
round 2 fingerprint=a16c7df0d09310e4
   test_t1645_zero_hunt                           OK
   test_t1880_wait_survives_phase_shortcut        OK
   test_t1939_needs_detach                        OK
```

Same fingerprint, same verdict, twice.

## Regression set (all green after the change)

| suite | result |
| --- | --- |
| `test_t1779_family_ignores_inbox` | OK |
| `test_t1889_sandbox_scope` | OK |
| `test_t1479_core_unit_consistent_copy` | OK |
| `test_t1505_core_unit_sandbox_reclaim` | OK |
| `test_core_unit_gate` | OK |
| `test_t1832_single_flight` | OK (skipped=2) |
| `test_t1828_verification_policy` | OK |
| `test_t1734_source_drift` | OK |
| `test_t1687_identity_diagnostics` | OK |
| `test_t1647_machine_runtime` | OK |
| `test_install_identity_doctor` | OK |
| `test_runtime_generation_identity` | OK (skipped=1) |
| `test_distribution_report` | OK |
| `test_userperson_global` | OK — `Ran 37 tests in 950.733s` |

`test_userperson_global` is the one that carried 28 `FileNotFoundError` errors
in the failing records. It passes in full now, and
`tests/scenarios/cold-handoff-continuity` is present and tracked (4 files,
`.saipen/` holding BOARD, LOG, STATE). SCOUT's Cause 2 is therefore **withdrawn**
in `SCOUT.md` rather than kept as a plausible story.

## Second mechanism found in VERIFY: a shard is a copy of a copy

The first fix rebound `sandboxes[0]` only, because `copy_tree_consistent` runs
once. Shards 1..N are then created by `shutil.copytree(sandboxes[0], target)`,
so every shard inherited **shard 0's** home:

```
WITHOUT per-shard rebind -> shard1 names: saipen_home: "V:/_TEMP_/red-shard-_o3dyhd7/shard0"
but shard1 actually is:                   V:\_TEMP_\red-shard-_o3dyhd7\shard1
```

Five of six shards would resolve a project living in another shard. Repaired in
`run_family`: each shard is rebound right after its copytree and before it runs.
Pinned by `test_a_shard_copied_from_another_shard_is_rebound`, which asserts the
raw inheritance first (so the test keeps measuring the hazard) and then the
rebound result.

Note the measured nuance: an inherited-but-IDENTICAL home did not by itself make
the three probe modules red — the pointers disagreed with the *path*, but the
content fingerprints matched, so `diagnose_install_mismatch` stayed non-blocking.
It is still wrong (a shard must describe itself) and it is exactly the kind of
latent disagreement that turns into a verdict the moment the source drifts.

## Determinism runs

| # | jobs | fingerprint | ran | red | verdict | wall |
| --- | --- | --- | --- | --- | --- | --- |
| pair1 run 1 | 6 | `2d3a87b54a6a1ff2` | 8392 | 0 | PASS | 2412 s |
| pair1 run 2 | 6 | `d2019828e9239071` | 8393 | 0 | PASS | 2667 s |

`SAME_VERDICT: True`, `SAME_FP: False`. The fingerprint moved because **I edited
`tools/test_t1952_sandbox_points_at_itself.py` between the two runs** (5 tests →
6 tests, 8392 → 8393 discovered) — i.e. the subject genuinely changed, so this
pair does NOT yet satisfy the ticket's proof. It is recorded because it is
honest: two sharded runs both returned 0 red on a subject I then modified.

A clean pair with the subject frozen for the whole window was then run. THIS is
the run the ticket's verify asks for:

| # | jobs | fingerprint | ran | red | verdict | wall |
| --- | --- | --- | --- | --- | --- | --- |
| clean run 1 | 6 | `d2019828e9239071` | 8393 | 0 | PASS | 2176 s |
| clean run 2 | 6 | `d2019828e9239071` | 8393 | 0 | PASS | 2026 s |

```
SAME_FP: True SAME_VERDICT: True SAME_RAN: True
```

`tools/test_t1952_sandbox_points_at_itself.py` was frozen for the whole window
(sha256 `73c0b3ae29c83180`, recorded by the runner at start), so both runs tested
identical bytes. Same fingerprint, same verdict, same count, twice: the pairs
`7e924cf0` (PASS 0 red / FAIL 12 red) and `7b04fc65` (FAIL 34 red / PASS 0 red)
did not reproduce.

## An earlier contradiction, and what it was

A `--jobs 6` run returned `ran: 8359, red: 1228, status: FAIL` on fingerprint
`a16c7df0d09310e4`, while an earlier run on the same fingerprint returned
`8392 ran, 0 red, PASS`. 1228 is not a flaky-test count — it is roughly two
whole shards. At that moment I was running `test_userperson_global` (950 s) and
four other suites CONCURRENTLY in the same tree, which is a self-inflicted load
condition, not the shipped configuration. It is recorded as unexplained rather
than as fixed: the clean frozen pair is what decides, and if it contradicts, the
1228 belongs to the oracle and not to my test harness.


- It does not claim the four historical records are now reproduced as PASS. They
  were taken with stale pointers; their verdicts describe the source tree's
  cleanliness, not the copied bytes.
- It does not claim `--jobs 6` is proven until the CLEAN frozen pair returns one
  fingerprint with one verdict twice. The pair above does not meet that bar.

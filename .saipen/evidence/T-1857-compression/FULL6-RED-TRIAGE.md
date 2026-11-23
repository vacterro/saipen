# FULL6 red triage: 6 reds are sandbox/live byte drift, not product defects

Record: `.saipen/evidence/core-unit/6a15cb0158c18309-20261023T111724527855Z.json`
(`status: FAIL`, `ran: 7427`, `tallied: 6`, `exit_code: 1`, `duration_s: 1758.9`,
`jobs: 6`, `head: 025bf596...`).

## The six reds

| test | count |
|---|---|
| `test_t1627_operator_question` | 4 |
| `test_t1645_zero_hunt` | 2 |

All six pass on the live tree and in a sandbox whose bytes match live:

```
python -m pytest tools/test_t1627_operator_question.py -q  -> 16 passed, 14 subtests passed
python -m pytest tools/test_t1645_zero_hunt.py -q          ->  7 passed
```

The same 23 tests also pass inside `saipen-core-unit-7tuu9ju1/project`, a
sandbox created **after** the last source edit.

## Mechanism (t1645, both reds)

The sandbox error text is decisive:

```
VALIDATION_FAILED: home-dead: home-divergent: the RUNNING install is
V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN but STATE.saipen_home names
V:\_TEMP_\saipen-core-unit-l_0w48jx\project -- the installs carry different
protocol or engine bytes.
```

`bin/saipen.cmd` is generated with an **absolute** path baked in:

```bat
"C:\ProgramData\SAI\SAIPEN\python\3.11.9-64\python.exe" "V:\...\_SAIPEN\tools\saipen.py" %*
```

A snapshot copy carries that same file, so the launcher inside the sandbox
invokes the LIVE engine while `STATE.saipen_home` names the SANDBOX. The
`state.py:995` guard (`resolve(home) != running_home()`) fires whenever the two
trees differ by even one byte — which is exactly the condition a verification
run creates when the source changes mid-run.

## Mechanism (t1627, four reds)

Same class, seen through status rather than the launcher: the four assertions
read `automation.disposition == "CONTINUE"` / `operator_action_due` from a
subprocess run of the snapshot's own `saipen.py`. They pass in a matching
snapshot and fail in a mismatched one, which is a generation difference and not
an operator-question logic error.

## Why the sequence looked like this

`EVIDENCE_DRIFT_RETRIES = 3` (`core_unit.py:73-77`) makes `evidence`
re-snapshot when the live tree drifts from the copy that ran. The first pass
snapshotted at 13:52; the coupling test, `.mcp.json` and the `ROOT_ALLOWED`
line were written at 14:05-14:12, so the first pass's sandbox no longer matched
live. `fingerprint_excludes` is `[".git", ".saipen", "audit"]`, so writes under
`.saipen/` are invisible to the fingerprint while writes under `tools/` are not.

A retry therefore started at 11:17:26Z against a fresh snapshot whose bytes
match live. That retry is the run whose verdict is authoritative for T-1857.

## Not a claim

This file explains a verification artifact. It does not assert that the
sandbox launcher design is correct, and it does not substitute for the retry's
record. If the retry reproduces any of these six, the explanation above is
wrong and the reds are real.

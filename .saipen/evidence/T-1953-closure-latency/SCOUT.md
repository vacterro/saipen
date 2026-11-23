# T-1953 SCOUT — where ten minutes actually goes

Handoff claim: a ticket closure "reportedly takes approximately 10 minutes",
attributed to "~10-12 serial CLI calls" at "10-30 seconds per CLI launch".

That attribution is wrong, and the measurements below say so before any repair
is proposed. Nothing here is taken from the previous agent's estimate.

## The script under investigation

`Close-Ticket.ps1` exists in exactly three places on this machine and none of
them is the project it closes tickets in:

```
/v/_TEMP_/claude/V-----VAC---K---CODE--MISC--BZDECOMP/{065c31a8,4c51d23a,e9f0f98a}/scratchpad/
```

`find V:/___VAC/__K/__CODE/_MISC/_BZDECOMP -maxdepth 3 -iname "*Close*Ticket*"`
returns nothing. The script is an agent scratchpad artifact, not a project
file. It is nevertheless readable and its shape is fully observable, which is
what the measurements below use. It is **not** modified.

Its own two constants are what matter:

- `Set-Location 'V:\___VAC\__K\__CODE\_MISC\_BZDECOMP'`
- `$sp = 'C:/Users/vac34/.agents/skills/saipen/bin/saipen.cmd'`

`_BZDECOMP/.saipen/STATE.md` names `saipen_home` as the **V: install**
(`V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN`), so every mutating call the
script makes is answered:

```
HOME_REQUIRED  home-dead: home-divergent: the RUNNING install is
C:\Users\vac34\.agents\skills\saipen (install-v1:b29342bfc4dbb85d...)
but STATE.saipen_home names V:\___VAC\...\_SAIPEN (install-v1:a33673c718faebcd...)
```

That refusal costs ~250 ms and produces no closure. The script, as written,
cannot close a ticket in this project at all -- both installs are v8.1.0 with
the same 171 engine modules, but their bytes differ, and divergence is what the
guard exists to catch.

## Launch cost is not the problem

Measured with `perf_counter` around `subprocess.run`, 7 samples each, cwd =
project root, same engine files:

| call | median | min | max |
|---|---|---|---|
| bare `python -c "import sys"` | 32.6 ms | 30.7 ms | 121.2 ms |
| engine via `saipen.cmd` (a refused command) | 203.8 ms | 197.9 ms | 278.7 ms |
| engine direct, same refusal | 192.9 ms | 191.1 ms | 201.9 ms |

A CLI launch is **~0.2 s**. Twelve of them is 2.4 s. The "10-30 seconds per
launch" figure in the handoff does not describe this machine.

## Where the time is

Measured in the consumer project (`_BZDECOMP`), 3-5 samples, median:

| command | wall |
|---|---|
| `saipen status --json` | 4410 ms (4.4 s) |
| `saipen test suite run` (declared `Test-TacticalOrders.ps1`) | 402-690 s |
| `claim` / `transition` / `checkpoint` (each) | 0.24-0.29 s |
| `ticket done` (refused, dry-run) | 1.31 s |

The dominant cost is not launch and not the protocol mutations. It is **the
declared verification suite**, which the consumer project re-runs on every
closure.

## The suite got slower for the same work

The consumer's own suite records (273 of them, `.saipen/evidence/suite/`) hold
the answer. Same declared command, same 16 tests:

| window | n | median duration |
|---|---|---|
| Oct 15-19 | 87 | **1.5 s** |
| Oct 28-29 | 35 | **451.0 s** |

The last twelve runs: `439.5, 453.0, 499.1, 633.0, 570.5, 536.0, 648.0, 20.1,
689.8, 79.0, 563.5, 673.0` seconds. The suite itself grew slower; the protocol
did not.

## The repeated work

Grouping those 273 records by the tree identity they recorded as their subject:
78 distinct subjects. On subjects executed more than once, one execution
suffices and the rest are repeated work:

| subject (first 12) | runs | sum | one run | redundant |
|---|---|---|---|---|
| `037816ade2e6` | 12 | 5439.1 s | 487.9 s | 4951.2 s |
| `86bb24cf8c38` | 66 | 4211.0 s | 123.7 s | 4087.3 s |
| `70a63572223c` | 28 | 2894.6 s | 159.5 s | 2735.1 s |
| `2ec7ac877194` | 13 | 1929.9 s | 211.8 s | 1718.1 s |
| `8c535ae21344` | 4 | 1842.6 s | 499.1 s | 1343.5 s |
| `7d8d4dae741e` | 3 | 1739.5 s | 633.0 s | 1106.5 s |
| `9b3ecd0b62c2` | 9 | 1469.6 s | 439.1 s | 1030.5 s |
| `2bfa5244bba7` | 10 | 1129.5 s | 161.6 s | 967.9 s |

**Total redundant execution: 19 675 s = 5.5 hours**, of 27 172 s (7.5 h) of
recorded suite time overall. Since 2026-10-26 alone it is 14 631 s = 4.1 h.
The 439 s and 633 s outliers inside `9b3ecd0b62c2` and `7d8d4dae741e` are
their own subject's variance, not a different tree.

`86bb24cf8c38` was executed **66 times** for 4211 s where one 123.7 s run
answered every one of them.

## Why the reuse did not happen

Not a missing feature. `suite_record.current_record` already answers exactly
the right question -- "the newest record of the DECLARED suite, when it tested
THIS tree" -- and `_admissible` already checks the record is the engine's own
shape for that command digest. Both were correct and both were **unused by
`run`**, which executed unconditionally and wrote a fresh record.

So the contract existed and the closure path never asked it. That is the
defect: a verifier-owned eligibility decision that no caller consulted.

## The second defect, found while measuring

`saipen status` reported 4.4 s in the consumer project, and a profile showed
`compute_source_identity` running **4 times** per call -- from `_status`, from
`conformance_status`, from `convergence_verdict` and from `automation_block`.

`saipen.py` already threads ONE identity into all four (PERF-001). It was being
defeated: the identity **raised**, so the sentinel stayed `None`, so each
consumer re-derived it and re-raised.

The raise:

```
FreshnessError: Git returned a non-canonical path:
b'contributions/.tooling/upstream-parser/'
```

`git ls-files -o` emits an untracked **directory** with one trailing slash --
here a nested repository git does not enter. `_path_from_git` treated the
trailing slash as a non-canonical path and raised. One nested untracked
directory therefore disabled source identity for the entire tree, and the
`None` sentinel turned that into four repeated failing walks.

## What is in scope

SAIPEN-owned code only, in this project. The consumer project is read, never
written: its 273 records are evidence, not a work area. `Close-Ticket.ps1` is a
foreign scratchpad artifact and gets an owner-specific handoff rather than an
edit (CASE 17).

## DEC

**DEC-1** Reuse is opt-in (`--reuse`), not default. A caller wanting the
freshness argument newly made asks for a run; only a caller that can name the
tree it is closing asks the engine to reuse. The command that never re-runs is
not the safe default.

**DEC-2** The eligibility decision stays in the engine (`reusable_record`), not
in the caller. The handoff's constraint -- "the verifier owns reuse
eligibility; the script does not" -- is implemented literally: `--reuse` is a
request, and it is refused for five separate reasons, each named in the answer.

**DEC-3** A reuse writes a LOG line that marks itself `PASS-REUSED` and cites
the record path and that record's sha256. It never restates a PASS. The
evidence grammar was extended so a reader can always tell reuse from
execution.

**DEC-4** The trailing slash is stripped, and the canonicality bounds are left
exactly as they were: `..`, `.`, absolute paths, empty paths and NUL are still
refused. The fix widens acceptance by exactly one spelling git itself emits.

**DEC-5** An untracked directory that git did not enter is recorded by its
presence (`kind=b"D"`, mode `0o040000`, empty content) rather than descended
into. This matches the rule `suite_record._git_subject` already applies: its
presence is the fact, its content belongs to its own tree.

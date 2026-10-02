# T-1361 scenario-family remeasurement, 2026-09-20

Produced while resuming SRC-084 phase A on T-1361 (SCOUT), then interrupted by
the new explicit user task SRC-085 / T-1432. Recorded here so the measurement is
durable when T-1361 resumes; the ticket remains parked behind T-1432.

## Identity

- Command (cwd = project root): `python tools/run_scenarios.py`
- Revision: `ec53042a9262bc5bd22f2d39f2d08bef103cca3e` (HEAD)
- Working tree: dirty at run time (same dirty set the distribution report
  names: bootstrap/inject.ps1, bootstrap/inject.sh,
  extensions/adapters/registry.json, saipen/COMMANDS.md,
  saipen/COMMAND_EFFECTS.json plus `.saipen/` memory writes by the session)
- Exit code: 1
- Duration: 640 s
- Raw captures (machine-local temp, regenerable):
  - `V:\_TEMP_\t1361-ec53042a\stdout.txt` (1252 lines, sha256
    6776E198E82606D6A5FA5B9CA226C3F30252E43074FC5ADEAA10EA809923B294)
  - `V:\_TEMP_\t1361-ec53042a\stderr.txt` (31 lines, sha256
    31B09F5799F2B5AD50C7C7BA0FD162B5862DF5622C66570FFD4BA2CD84CE7099)

## Counts (visible summary lines, current bytes)

- `FAILED:` summary lines: 115
- unittest-style `FAIL:` lines: 24
- `PASS:` lines: 959
- Cluster counters printed by the suite: third_wave 71/95 (24 failed),
  perf wave 40/42 (2 failed)
- The historical "153" is therefore in the same order of magnitude but is NOT
  the current number; no per-cluster classification has been performed yet.

## Dominant observed root cause (unclassified, one hypothesis)

`PROJECT_LINEAGE_MISMATCH` appears 41 times in the capture, each time from a
temporary fixture project (`V:\_TEMP_\saipen-...`) whose explicit project
lineage is None while the engine expects
`lineage-b512942bac884a8691f6c98afcd6ddb9` (the host project's lineage leaking
into fixture construction). Representative cases: digest-stale project,
continuity probes H28/H30, SCOUT->BUILD transition probe, nitro-integrity
harness. This single shared cause likely owns a large share of the failures and
must be measured, not assumed, when T-1361 resumes.

Other visible clusters, unpartitioned: source receipts (5), converge
gate/naming (several), release-freshness staged-tree probes, hunt-mark probes,
third-wave checks (24), perf-wave checks (2), continuity probes.

## Status

No fixes attempted. T-1361 measurement is complete for this run; classification
by shared root cause and the repair/partition decision remain open and must not
be inferred from the historical ticket text alone.

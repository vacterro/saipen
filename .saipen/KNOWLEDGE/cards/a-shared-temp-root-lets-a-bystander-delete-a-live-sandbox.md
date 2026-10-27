<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: the declared core-unit family, sandbox lifecycle, machine-shared TEMP/TMP roots, concurrent sessions, stale-sandbox sweeps, mass red counts
trigger: reading a mass red count from a family run, or changing how a sandbox is created, stamped or swept
status: active
evidence: T-1823, SRC-281, .saipen/evidence/core-unit/ba2b164261cabb7d-20261019T082651Z.json, tools/test_t1505_core_unit_sandbox_reclaim.py, tools/saipen_engine/core_unit.py
supersedes: none

# A shared temp root lets a bystander delete a live sandbox

A single-process (`--jobs 1`) run reported 2767 reds of 6810 with 1353 of them `FileNotFoundError` on files of the *running sandbox itself* (`saipen/BOOT.md`, `saipen/STYLE.md`, `extensions/adapters/registry.json`, ... under the run's own `project/`), the red modules forming one contiguous alphabetical range of 302 modules, in 1358.6 s against a ~5000 s sequential norm.

Why:
That shape is one event, not thousands: the sandbox tree was removed underneath the live family child part-way through, and every later module died on its own cwd. Offline in-process cleanup was ruled out -- no test deletes `saipen-core-unit-*`; the only deleters are `run_family`'s own `finally` and `sweep_stale_sandboxes`. The sandbox root is machine-shared, so a sweep that asks only "is the creating pid alive?" reclaims a directory a sibling session is actively running in, and the damage lands on whichever run is unlucky.

How to apply:
A sandbox stamp is scoped and multi-witnessed: record the owning `project` and never sweep a candidate whose recorded project differs from yours; record the family child that is *reading* the tree as well as the creator, and keep the sandbox if any recorded pid is alive. Controls: `tools/test_t1505_core_unit_sandbox_reclaim.py`.

A mass red whose failures all name the runner's own tree is an environment event, not a code regression: read the record before believing the count, and never accept such reds into the baseline.

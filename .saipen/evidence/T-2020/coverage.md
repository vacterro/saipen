# SRC-390 requirement audit — T-2020

Original body, exact contract and coverage read from the CLI-provided locators.
Implementation candidate is DONE T-2019, locally pending publication. This
audit closes the handoff's behavior, not a claim of publication or global green.

| Clause | Current source and direct proof |
| --- | --- |
| R001 | Canonical claim/SCOUT/BUILD/VERIFY journal; BZDECOMP remains a read-only reference, never a suite execution target or state writer. The executable status probe uses only a disposable fixture; its JSON records `bzdecomp_executed:false`. |
| R002 | saipen/phases/verify.md SUITE-PREFLIGHT-01 and REGISTRY owner; test_rule_owner_requires_subset_and_failed_script_before_full_run; affected fixtures cover changed basenames, qualified symbols, row-count constants, staged/unstaged/untracked files. Explicit manual review retains grown-table and indirect-dependency obligations. |
| R003 | VERIFY text requires only failed-script retries, sibling stub/cut searches, then one full run. Exact rule conformance test and fixture dependency selection pass. |
| R004 | Existing test module exercises FAIL/exit-zero, stderr, PowerShell prefix/gutter, timeout and descendant cleanup. Current disposable stub-mismatch status_probe.json stops in 1.266 s (<120 s), records FAIL and cannot be reused as PASS. BZDECOMP is never the target. |
| R005 | suite_record.run/write_record/_summary/_status retain explicit script timings and separate pre/post hash/parsing fields. Current public status probe verifies duration_s, first_failure_line, scripts and all overhead fields; untimed runners remain marked unavailable. |
| R006 | suite_preflight.affected and suite_record.cli expose read-only candidates. Tests cover sibling references, nested Git ownership, entrypoint exclusion and generator exclusion. Text selection explicitly remains provisional. |
| R007 | VERIFY advises project-owned speed work for consistently >600 s PASS, with parallel scripts, one compiler environment and source-hash compile cache, explicitly nonblocking. This is the requested optional nudge, not automatic mutation of BZDECOMP T-651. |

Current commands/results:

- python -B -m unittest test_refusal_registry test_canonical_command_reachability test_subprocess_utf8 (cwd tools): 23 PASS, 30.210 s.
- python -B tools/core_unit.py focused T-2020 --pattern test_t2019_suite_preflight.py: PASS, 12 tests; exact-tree/environment record `.saipen/evidence/focused-unit/67ef25d5a3ddabff-20261104T033002415179Z.json` reused, request wall 7.219 s. No new execution or fictitious fresh-run claim.
- python -B .saipen/evidence/T-2020/status_probe.py: PASS, initial 1.266 s; independent REVIEW rerun 0.172 s. `.saipen/evidence/T-2020/status_probe.json` contains the latest measured replay and status fields.

No implementation delta in T-2020. Existing T-2019 diagnostic global core/lint
failures are neither repaired nor waived by this audit. No full suite rerun.

# T-1602 verification in progress

Current implementation recognizes `| needs:` fields in both existing portable
dependency checks. The parity dispatcher uses `os.name == "nt"` and reports
the actual native floor on failure. No check, floor baseline, timeout or
canonical control table changed.

The seven-test regression oracle is unchanged: verifier `f33e4b6ba84b3b16`,
current subject `1a136e0e0886f91f`. `green-verify.json` and its output record
the independent seven-test PASS. Original `red-final.json` retains the same
verifier against subject `a6e1480300efbcd4`, six behavioral failures, no errors.
Known-good narrative fixtures pass in both Bash and PowerShell; actual dangling
and cyclic fields fail in both, with fixture bytes unchanged.

The first core gate correctly failed because the new test had no Git index
membership. Only this owned file received intent-to-add; no test or implementation
bytes changed. `verify-core-tracked.txt` records the resulting zero-failure core
gate with 31 retained warnings. Pinned Ruff 0.16.0 and `git diff --check` passed.
`verify-audit-floor.txt` records 28 controls on each of the two available runtimes.
`verify-audit-order.txt` records the 347-tool ordering check.

The complete declared family finished: 4855 tests, red 0, new_red 0, six
complete shards, no leaked sandboxes. The immutable record is
`.saipen/evidence/core-unit/bfdadc11eaa0d3af-20261003T102125Z.json`, cited by
canonical event E-12005. The scenario run remains live under its original handle.

The full audit-checks run has an observed control-instrument failure:
`warn-slug-ownership` cannot run Git add on a deeply nested copied evidence path.
This does not establish a defect in warning ownership. `longpath-control.json`
proves identical owned known-good bytes fail with `core.longpaths=false` and
are indexed with `core.longpaths=true` (379-character path, exit 128 then 0).
The unchanged ownership control passed with process-local path support;
`longpath-warn-control.json` records the real result. Repository and user Git
configuration remain untouched.

The audit's `symlink-restore` and external-identity mutation report UNPROVEN
for actual WinError 1314. Audit-checks permits unrelated probes to proceed;
this is not proof that either symlink control was constructed.

The exact parity gate is stricter. Its rerun with process-local path support
completed 246 of the unchanged 247 canonical mutations, caught 14 in both
validators (baseline stays 11), caught 232 only in the canonical validator,
and caught none in neither. It then correctly returned FAIL because the
external-identity symlink could not be constructed and the denominator was
incomplete. `verify-audit-parity-longpath.txt` preserves this real refusal.
The known-good preflight succeeded; this is a missing host capability, not
an implementation failure. No missing case, denominator, baseline or timeout
was waived.

T-1602 cannot close while this mandatory proof is absent. The independently
green implementation remains attributable to this ticket, and its four-file
patch is preserved as `pending-implementation.patch`. It is not a failed
implementation to roll back; the host proof is unavailable. Parent T-1507
remains blocked on this child. Work can continue on other admitted tickets.

Review draft: the narrow implementation matches the canonical board delimiter
and preserves the existing genuine dependency controls. No new memory card is
needed; the existing narrative-authority and red-control cards cover this lesson.
No REVIEW, completion, publication or aggregate full-green verdict is claimed.

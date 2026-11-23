# T-2045 ticket-scoped self-audit

Executing-agent inspection; this is not the independent review.

## Exact revision

- `tools/saipen_operator_gateway.py`: `f7fdd935fe97bf5ebdcf82e139b27a1c4c8050508bc3d4fcb7401fa0e8f49a91`
- `tools/test_t2045_operator_gateway.py`: `34b6973d0cf92bc7612cfb362fd8b1ab395bc8ec88dbbb9d253a5ce3013baac4`
- `extensions/adapters/FREEBUFF_INGRESS_CONTRACT.md`: `246bf85d0991e5d292bb2631ba0d4fd52654c978c5851a41b3dafcd2c45e2837`

Inspected both exact saved product diffs, the unchanged new oracle, `_load_state`, `status`, `main`, direct shared `prove_owned_dir_chain`, `prove_owned_regular`, `read_bound_regular_bytes`, and `parse_state_or_error` implementations. Compared documented output/refusals with CLI and registry consumers. The independent review record binds the same three hashes.

## Result

No confirmed required-behavior defect in this revision. Strict parsing refuses empty, malformed, duplicate, unknown-field and invalid-schema STATE; invalid UTF-8 and OS/read errors return typed failures. Absolute, unresolved root retains topology for owned-path checks. Ancestor/final-node probes and descriptor identity/size/read-stability checks precede status output; descriptor closes in `finally`. Recorded counters remain null when absent. CLI rejects approval/mint/renew/authority/run flags. Repeated fixture CLI calls leave fixture bytes unchanged. No gateway call approves, issues, consumes or renews authority, launches a broker, publishes or writes project state. BOOT routing, unavailable Freebuff registry capability and T-1822 transport blocker remain unchanged.

The oracle was created before the repair and was not edited afterward. Native same-oracle pair `regression-execution-360e6c15b6c5499fae003d89985576d1` ran 15 methods: before 11 failures, after zero, no skips. Existing REVIEW rerun is `review.run.json`: 15 passed, five subtests passed. Independent reviewer reran the same revision separately: 15 passed, five subtests passed.

## Limits and gate disposition

Permission and symlink controls are mocked; no gateway-specific real NTFS reparse or race construction was executed. Descriptor helper source inspection does not constitute installed-host acceptance. Fixture snapshots cover fixture files, not machine-global effects. `OwnedPathUnavailable` retains ValueError compatibility and is classified STATE_INVALID, whereas direct read OSError is STATE_UNREADABLE; both refuse without claiming authority.

The 64-test focused record is intact and compatible under the proven exec invocation. The measured otherwise identical direct capture differs only at public SHLVL=1 versus exec SHLVL=0; `focused-launch-diagnosis.json` preserves this distinction. Canonical focused replay reused the original PASS and exec SHIP dry-run admitted it. No digest is transplanted and no admission policy is weakened. A separate fresh focused execution is running; its result is not yet claimed. `canonical-validation.json` is FAIL, with EX-000050 closure-generation drift and four untracked runtime paths. This is not conformance or publication PASS. T-2045 local closure, if admitted by the focused policy, must say publication pending. Shared foreign staging is untouched.

Memory promotion: NO. Shared strict-reader/authority rules already exist; this bounded reuse supplies no unique new durable lesson.

# T-1392 repair path -- what executes the corridor's retirements

Recorded 2026-09-17 by the T-1392 cleanup session
(SAIPEN_HOST_SESSION ses_f4f0a877bffeANRWtvzKJlMb0A) while executing the
operator handoff captured as SRC-061. Steps 1-2 of the handoff (prove the
contamination, refuse to implement it) are complete; this file records the
measured state of the execution path for steps 3-4 (retire T-1391/SRC-060,
then T-1390/SRC-059). No mutation was attempted through any refused path;
every measurement below is `--dry-run` or a read.

## T-1392 source bytes (uncommitted)

* `tools/saipen_engine/retirement.py`: `RETIREMENT_REASONS` extended with
  `TEST_FIXTURE_CONTAMINATION` and its closed-set doc block.
* `tools/test_ticket_retirement.py`: the closed-set pin in
  `test_control_6_unknown_reason_fails_closed` updated to both reasons.
* `ruff check`: All checks passed.
* `python -m unittest tools.test_ticket_retirement`: Ran 55, failures=2,
  both `test_control_8_a_crash_mid_transaction_converges`
  (`PROJECT_LINEAGE_MISMATCH`) because this host session's environment
  (`SAIPEN_PROJECT_ROOT` / `SAIPEN_PROJECT_LINEAGE` of this project) is
  inherited by the test subprocess and out-states the fixture's own lineage.
  Re-run of the same test with those two variables cleared: OK. The two reds
  are environment-caused and not owned by these patch bytes.

## Measured execution paths for `ticket retire T-1391 --reason TEST_FIXTURE_CONTAMINATION`

1. Installed shim, guard-admitted, artifact evidence:
   `saipen ticket retire T-1391 --reason TEST_FIXTURE_CONTAMINATION --evidence .saipen/evidence/T-1391-T-1390-fixture-contamination-20260917/PROOF.md --authority SRC-061 --dry-run --json`
   -> `RETIREMENT_REASON_UNKNOWN`: the installed runtime at
   `C:\Users\vac34\.config\opencode\skills\saipen` carries the pre-extension
   `retirement.py`; distribution is blocked DIRTY_SOURCE and supported
   injection is gated behind this corridor (handoff step 11).
   Also `saipen claim T-1392` -> `ALREADY_CLAIMED`, "DOING holds T-1391": the
   seat frees only through the retirement.

2. Source engine, artifact evidence:
   `python tools/saipen.py ticket retire T-1391 --reason TEST_FIXTURE_CONTAMINATION --evidence .saipen/evidence/T-1391-T-1390-fixture-contamination-20260917/PROOF.md ...`
   -> guard refusal `PROTECTED_CANONICAL_NAMESPACE`, attempted string echoed
   truncated at `.../PROOF.m`, route printed `saipen next --json`. The guard
   grants the canonical exemption only to a literal `saipen` first token, so
   the source-CLI spelling is judged an ordinary shell line and
   `_PROTECTED_SHELL_SEGMENT` matches the artifact path. Same class as T-1386
   (a `.saipen` spelling inside an option value); T-1386/T-1385 own it and it
   is not fixed here (registered, not current work).

3. Source engine, event evidence, zero mutation:
   `python tools/saipen.py ticket retire T-1391 --reason TEST_FIXTURE_CONTAMINATION --evidence E-7017 --authority SRC-061 --dry-run --json`
   -> `RETIREMENT_AUTHORITY_REQUIRED`: "authority receipt SRC-061 grants no
   retirement authority for T-1391: naming Work is not authorizing it -- a
   capsule is a line ...". Everything before the authority gate passes:
   reason registered, evidence resolves (a canonical event that precedes the
   retirement), identity and lifecycle gates untested only because the plan
   stops at authority.

## Remaining blockers, in order

1. The operator-authority capsule. The mechanism requires the operator's own
   stored bytes to carry a closed-grammar capsule granting exactly
   `T-1391 / SRC-060` and `T-1390 / SRC-059`; SRC-061 (and every other ACTIVE
   receipt -- only SRC-049 carries a capsule, for T-1368/T-1369) grants
   nothing. Exact text requested from the operator 2026-09-17.
2. Artifact-reference spelling is guard-refused on the source-CLI transport
   (T-1386 class). The real retirement will therefore cite canonical event
   evidence plus a note; `PROOF.md` remains the supporting artifact of this
   evidence directory.
3. The installed runtime is stale for the new reason code, by design until
   the corridor's supported injection step (handoff step 11).

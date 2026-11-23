# T-1756 option (b), prepared and measured (T-1788, 2026-10-14)

Option (b) from T-1756's decision: keep the environment binding, drop only
variables that name the invoking shell or host session.

- `regression_execution.option-b.patch` -- the whole change to
  `tools/saipen_engine/regression_execution.py` (31 diff lines): a closed set
  `SESSION_ONLY_KEYS` = `_`, `OLDPWD`, `PWD`, `SHLVL`, `PROMPT`, `WT_SESSION`,
  `TERM_SESSION_ID`, plus prefixes `SAIPEN_` (as before) and `CLAUDE`. Those
  keys are neither digested nor passed to the verifier child, so nothing the
  verifier can read is left unbound.
- `test_t1788_verifier_session_env.py` -- two sessions on one environment share
  the verifier digest; a PYTHONPATH or PATH change still moves it.
- Measured pair: E-15629/E-15630, record
  `.saipen/evidence/regression/` (op of T-1788): pre-fix FAIL (exit 1),
  post-fix PASS (exit 0). Related suites with the change applied: 79 tests OK
  (test_t1711_regression_execution, test_t1726_closed_contracts,
  test_t1726_contract_oracle, test_t1788). The core-unit family was stopped
  before completion when the duplicate of T-1756 was noticed.
- Trigger seen live: T-1787's pair recorded under `timeout 590 saipen work
  regression` was refused at VERIFY -> REVIEW because bash set `_` to the
  wrapper path (STALE_REGRESSION_EVIDENCE). Session keys
  (`CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID`) stale every receipt after `/clear`.

Not applied: the engine file was restored to its pre-change bytes
(sha256 088d7caa27afa304...). Applying (b) after the operator chooses it:
copy `regression_execution.option-b.py` over the engine file, copy the test into
`tools/`, re-run the pair with `regression.json`, then the core-unit family.

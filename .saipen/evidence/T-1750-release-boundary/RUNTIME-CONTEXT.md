# Observed verifier environment mismatch

The old and current native regression measurements retained identical
contract, context, oracle-file bytes, runtime path and runtime executable hash,
but had different full verifier fingerprints. T-1695's focused RV-000065
executed 38/0, while a separate native read correctly classified its contract
UNVERIFIED / ENVIRONMENT_CHANGED. Its result was not treated as global PASS.

`environment_probe.cmd` reproduces the launcher's interpreter/frame and uses
the actual `regression_execution._runtime` environment normalization. Two
separate host command calls produced different environment digests. Only one
environment key's value hash changed: `CODEX_TOOL_CALL_ID`. The two snapshots
store key names and value hashes, never environment values.

The existing launcher knowledge card explains why an execution envelope is
part of verifier identity. No production code, environment exclusion, stored
receipt, oracle, scope or admission rule was changed to hide the difference.
T-1756's portable-context policy remains a separate existing operator decision.

Current native operations use ONE actual persistent command process, host
session 38301. It inherits its environment once; subsequent host input writes
do not replace that environment. RV-000066 executed the same 38-case focused
contract in this frame. A separate native `work contracts T-1695` within that
same process returned CURRENT_PASS / BOUND_DEPENDENCIES. Canonical validation
then minted CURRENT_PASS receipt-9f1537850fec, 0 problems / 9 warnings.

This is a current-frame workflow, not portable proof for a later host context.
Continue dependent native regression, VERIFY/REVIEW and closure operations
through this same live session. If that process genuinely ends, refresh proof
in the new actual frame; never transplant digests or claim the old frame current.

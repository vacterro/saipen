<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: executed regression receipts, regression_execution, review remeasurement, Windows launchers, Python runtime
trigger: a read-only evidence audit reports STALE_REGRESSION_EVIDENCE while current subject and oracle bytes still match
status: active
evidence: T-1714, .saipen/evidence/T-1714-diagnostics/verifier-context-comparison.json, .saipen/evidence/T-1714-diagnostics/current-evidence-audit.json, .saipen/evidence/T-1714-diagnostics/review-pair-resumed.json
supersedes: none

# The launcher is part of the verifier

Recheck executed receipts through the same proven launcher, absolute runtime
and environment as the admitted operation. Matching Python versions and
executable hashes do not establish that identity. Diagnose the mismatch
before re-running a pair or changing production code.

Why:
T-1714 measured identical Python 3.11.9 executable bytes at two absolute
locations. A native helper and the canonical Windows batch launcher also
differed on the `PROMPT` environment key. The execution verifier binds both
runtime path and environment digest, so the native helper refused an otherwise
current receipt. Running the audit and independent before/after review through
the proven launcher succeeded without changing subject, oracle or assertions.

Compare environment value hashes or key names without saving secret values.
If the admitted context really changed, execute a fresh pair through the
supported operation. Preserve previous failures; never transplant a verifier
digest or relax the admission check to make an old receipt current.

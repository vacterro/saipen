<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: unittest, nested suites, borrowed tests, test isolation, module cleanup, host environment
trigger: running a test case from another module inside an active unittest case
status: active
evidence: T-1690, tools/test_t1690_profile_isolation.py, .saipen/evidence/T-1690-profile-isolation/red-v4.json, .saipen/evidence/T-1690-profile-isolation/review-v4-final.json
supersedes: none

# Nested unittest suites can restore the real host mid-test

Use `test_hermetic_env.borrow` for one case without class fixtures. When an
inner suite needs its module or class fixtures, hold the caller's module
cleanups with `test_hermetic_env.nested_run`. Keep every installer fixture's
profile explicit even when isolation is present.

Why:
Unittest's module cleanup list is process-wide. Ending an inner suite can
drain the caller's isolation cleanup while the caller is still running,
restoring the real profile carrier and authority endpoint. The next fixture
installer may then write the operator's hook. A disposable child proves the
bare-suite hazard and verifies that the protected run retains isolation
until the outer module actually ends. A single-case run avoids suite-level
teardown while retaining the case's setup, teardown and instance cleanups.

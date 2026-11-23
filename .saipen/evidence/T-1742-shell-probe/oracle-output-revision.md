# Oracle output correction

The native regression executor refused the first carrier with
`REGRESSION_EXECUTION_INVALID: no unambiguous completed unittest summary`.
The failing outer assertion embedded the child runner's complete output,
including its own `Ran 1 test` summary, before the outer `Ran 3 tests` summary.

The oracle now carries only the child's assertion diagnostic in its failure
message. Its process exit, collected-test count, successful-run check and all
three input profiles are unchanged. The strict summary parser is unchanged.
Re-establish both pre-fix FAIL and post-fix PASS through the native executor
using this one revised oracle; the earlier manually observed FAIL is not a pair.

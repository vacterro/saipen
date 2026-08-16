expect: fail
expect_fail_contains: missing transition_from

Hostile-regression P0#1: a non-INIT STATE with no transition_from must be
refused by the shared STATE validator (engine, fast gate and release gate).

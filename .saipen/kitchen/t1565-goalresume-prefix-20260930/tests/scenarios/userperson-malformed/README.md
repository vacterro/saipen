expect: fail
expect_fail_contains: USERPERSON file must open with the exact heading

Test: a present USERPERSON profile must be well-formed. A malformed file is a
hard FAIL, not a silently ignored preference blob -- the file being optional
does not make an active file's shape optional (T-574).

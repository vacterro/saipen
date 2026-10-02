expect: fail
expect_fail_contains: end mid-line

Test: `BOARD.md` stops on `## BLOCKED` with no trailing newline. Appending the next ticket to that file does not add a line, it extends the heading -- one write costs both the section and the ticket, and every structural check still passes because the bytes never become a second line.

The same shape in `.saipen/LOG.md` cost two of the 45 red controls in `tools/audit_checks.py`: the mutations it appends landed inside the final entry instead of after it, and the harness kept printing PASS. Three live `.saipen` files were in this state when the check was written.

This is checked by reading the last byte, which nothing else here does. The mutation is the file's bytes, so the red control cannot be satisfied by rewording a check.

expect: fail
expect_fail_contains: is not the claimed ## DOING ticket

Test: the v7.215.0 crash state -- STATE names task T-999 in a ticket-bearing
phase (SCOUT) while BOARD carries no ## DOING claim and T-999 sits in
## TODO. This was validator-conformant until T-573; the checkpoint that
produced it wrote STATE ahead of BOARD, the exact interruption RFC section
1.5 exists to catch. Recovery may observe it, but canonical validation MUST
reject it, with one focused diagnostic naming the unclaimed task.

Test: the block-parked DONE shape (phase DONE + transition_from BUILD) is
legal ONLY while the active LOG's most recent ticket event is a canonical
`ticket block via SAIOPS` line. Here the same STATE and BOARD carry a plain
build event instead, so the hand-edited DONE state must FAIL on the
transition edge -- the block exception cannot be forged by copying the state
without the operation that produced it.

expect: fail
expect_fail_contains: invalid phase transition

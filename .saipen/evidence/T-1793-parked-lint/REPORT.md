# T-1793: inherited parked-output lint

The two inherited T-1787 Ruff findings are corrected: a separate loop input
variable replaces reassignment of the loop variable, and a long fixture literal
is split into equivalent adjacent literals. No output behavior changed.

The retained parent T-1792 command-contract addition initially made nine members
of the full family fail one context budget. Its compact equivalent was reviewed
and attributed to that parent at E-15715; budget limits and verifiers stayed fixed.
The failed run remains in `e86aa5bb69345c20-20261014T221559Z.json` (6,606 tests,
nine red), and the final run is `2fc1f8dc089b4d68-20261014T224242Z.json`
(6,606 tests, zero red, E-15719).

Independent REVIEW reruns: pinned Ruff 0.16.0 on `tools/ tests/`, both parked-output
tests and all six context profiles PASS. Diff review confirms the fixture value
and formatting semantics are unchanged. No P0/P1 findings; no memory promotion.

The local core signal has 19 findings: 18 untracked runtime copy-tree tests under
the existing T-1644 publication-policy hold, and the existing T-1695 closure
reverification. Exact output is `local-core-gate.json`. This is no CURRENT_PASS
claim. SHIP step 5 declares this check a signal; mandatory Work lint, output and
whole-family checks pass. Publication is skipped by the existing policy; no Git
index, commit, tag, push or host installation was changed by this Work.

The family record's six process cleanup ids were checked against the current OS:
none remained live. No process was terminated by this session.

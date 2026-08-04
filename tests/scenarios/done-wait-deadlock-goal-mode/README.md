expect: fail
expect_fail_contains: auto-transition HUNT

Test: the deadlocked `DONE` board from `done-wait-deadlock/`, under
`goal_mode: true`.

Same defect, the mode that costs most. The check carried a `goal_mode is not
True` exemption, so it was switched off in exactly the situation where a
deadlocked board is worst: an unattended run parked on a `WAIT:` nobody was
asked. Removing the exemption (T-453) made the branch live, and nothing stood
behind it -- `tools/audit_checks.py` mutates ONE file per case, and this defect
needs `STATE.md` and `BOARD.md` to be wrong together. Mutate STATE alone and the
board still has open tickets; mutate BOARD alone and `next_action` is still
legal. Every single-file attempt went not-red, so CONFORMANCE 209 stated the gap
as a limit rather than claiming a control (T-457).

The route was already here. `tests/scenarios/` fixtures construct a whole
`.saipen/`, which is what a compound condition needs; this directory is that,
not a new mechanism. A validator condition whose trigger spans more than one
project file belongs here, and an `audit_checks` case for it will report itself
as not-evidence rather than fail loudly.

The counters are load-bearing and deliberately UNDER section 2.4's 3/20 caps:
at or over them the safety-valve wording would be the legal answer and this
would stop being the deadlock case. `LOG.md` carries the matching
`DEC: goal_waves`/`goal_tickets` increment lines because section 1.5 rebuilds
those counters by counting events, and a fixture whose STATE disagrees with its
own log fails on the counter check first -- red for the wrong reason, which is
not evidence.

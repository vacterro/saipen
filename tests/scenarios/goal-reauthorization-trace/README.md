Test: a bare `saipen goal` re-authorization clears a tripped safety valve by resetting `goal_waves`/`goal_tickets` to `0`. The reset MUST leave a `DEC: goal reauthorized -- goal_waves N->0, goal_tickets M->0` line (RFC § 2.4 Entry), because § 1.5 Recovery rebuilds the counters by counting completion events since the NEWEST goal marker -- pivot or re-authorization.

Without that line the newest marker is the older `saipen goal <text>` pivot, so a rebuild counts every bump the re-authorization already cancelled, restores the at-or-over-cap counters, and re-trips a valve the human just cleared -- while § 2.4 forbids tidying those counters back down. The re-authorization then expires at the next crash, and every later one revokes it again from a count that only grows.

expect: pass

The rule is enforced by replaying the rebuild, not by grepping for the line: `tools/validate.py` counts increment bumps after the newest marker and FAILs when the result disagrees with `STATE.md`. A marker that exists but does not explain the counters is the same defect, and only replaying the count sees it. Decrements are not completion events, so a reset line's own `N->0` cannot be miscounted as work.

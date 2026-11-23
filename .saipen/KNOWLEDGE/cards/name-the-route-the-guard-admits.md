<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: validator findings, engine refusals, next_action values, protocol prose that names a command, guard admission of shell lines
trigger: writing a finding, refusal or law sentence that tells a reader which command clears a condition
status: active
evidence: T-1640, T-1665, .saipen/evidence/T-1640-findings/guard_probe_verbs.txt, tools/test_canonical_command_reachability.py, tools/test_t1640_log_seal.py (test_the_named_route_is_one_a_guarded_shell_admits)
supersedes: none

# Name the route the guard admits, and prove the route clears the finding

Before a finding or refusal names a command, pass that exact spelling through `guard_events._saipen_cli_verb` and run it on a fixture that shows the finding, because a documented verb is not necessarily one a guarded shell admits.

Why:
T-1640 existed because the validator said "seal it at the next checkpoint" to an agent the guard refuses on every path a seal writes. The first repair named `saipen clean`, and the guard refuses that spelling too while no Work is active, answering that `clean` is not a verb; `saipen transition CLEAN` enters the same phase and is admitted in every state. `test_canonical_command_reachability` caught the engine literal only because it STARTS with the command word. A command quoted inside a longer message, which is how the validator prints its findings, is not harvested by that test.

How to apply:
Give the finding a behavioural test with three steps: the fixture shows the finding and the finding contains the command; the command is admitted by the guard; after the command runs, the validator no longer prints the finding and prints no FAIL. `tools/validate.py --gate core` runs on a bare fixture project in about a second, so this costs nothing. State a cap as what a route can clear: T-1640's BOARD finding measured the whole file, and open work alone exceeded it, so no command could ever have cleared it.

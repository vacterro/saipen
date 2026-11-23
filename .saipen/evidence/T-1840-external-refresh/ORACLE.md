# Acceptance oracle correction

The first live verifier required READY for SMART_VAC_CLEANER regardless of
project state. Its actual run failed, preserved in live-current-initial-strict.json.
The account/machine/token facts and write dry-run were admitted, but another
project Work had entered SHIP with pending release recovery. Existing account
code correctly reported PROJECT_LIFECYCLE_DENIED for that state.

The original T-289 criterion requires an actual admitted write dry-run on the
named project, unchanged STATE/BOARD/LOG, and refusal for an unlisted foreign
home. SRC-105 additionally forbids reporting complete READY when project
admission fails. Therefore unconditional READY was an invented stronger premise
and would encourage a false success or interference with another project's
release. The corrected oracle requires truthful DENIED when the actual broker
status reports pending recovery, while still demanding all separate account,
credential, project-access, machine, host-token and write-admission facts.

A fresh disposable positive project must independently be READY before its
unlisted-home negative control. Its control still requires actual cross-user
write refusal and unchanged canonical bytes. Negative model controls require
the corrected predicate to reject READY during recovery, provider-only READY,
missing write admission and contradictory token/runtime facts. The old stronger
failure is retained; no subject code or external state was changed to make this
observation green. Final same-oracle subject pairs are re-established after all
oracle/context edits; earlier pairs do not certify a changed oracle.

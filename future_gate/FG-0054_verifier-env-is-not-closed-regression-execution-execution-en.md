<!-- SAIPEN FUTURE GATE v1 -->
id: FG-0054
title: VERIFIER ENV IS NOT CLOSED: regression_execution.execution_environment() copies the inherited shell's `_` variable into the verifier environment, so the same regression pair hashed under a different parent (e.g. wrapped in `timeout`) yields a different environment_digest and closed_contracts.py:275 flips a stored contract to UNVERIFIED/ENVIRONMENT_CHANGED with no code change. Fix: drop volatile shell-owned variables (`_`) from execution_environment, then re-record the T-1937/T-1938 pair WITHOUT a timeout wrapper.
state: DEFERRED
priority: P2
basis: measured
estimate: 1
slice: TODO -- name the ONE bounded unit this gate may promote
needs: none
evidence: TODO -- reference an existing path

# VERIFIER ENV IS NOT CLOSED: regression_execution.execution_environment() copies the inherited shell's `_` variable into the verifier environment, so the same regression pair hashed under a different parent (e.g. wrapped in `timeout`) yields a different environment_digest and closed_contracts.py:275 flips a stored contract to UNVERIFIED/ENVIRONMENT_CHANGED with no code change. Fix: drop volatile shell-owned variables (`_`) from execution_environment, then re-record the T-1937/T-1938 pair WITHOUT a timeout wrapper.



Deferred authority candidate. Not Work, not a rule source, not
implementation authority until `saipen future promote`.

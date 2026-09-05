<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: convention
scope: tests, gates, red controls, regression oracle
trigger: adding a check or claiming a defect is fixed
status: active
evidence: T-1276, T-1268, tools/audit_checks.py
supersedes: none

# Prove a check can go red before trusting its green

A new or repaired check earns belief only from a demonstrated red state on its own condition with the verifier held fixed, because a green result also describes a check that cannot fail.

Why:
Repeated defects here passed every gate while their controls were disarmed: a weakened oracle inside the same build made a fix look verified, and a quoted marker silently retired a suppressor's control. Each was caught by running the check against the pre-fix subject, so the red control is the evidence and the green alone is not.

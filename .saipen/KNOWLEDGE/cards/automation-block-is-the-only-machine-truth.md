<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: convention
scope: saipen status --json, automation block, external drivers, Run to Closure
trigger: deciding whether an external driver may continue, stop, or trust a completion signal
status: active
evidence: SRC-021, SRC-023, tools/saipen_engine/automation.py, tools/test_automation_block.py
supersedes: none

# Only the automation block is machine truth; prose never is

`saipen status --json` carries an `automation` object (schema_version 1) whose `disposition` is one of CONTINUE, COMPLETE, WAIT_USER, WAIT_EXTERNAL, BLOCKED, INVALID, and whose `next_command` is `cc` exactly for CONTINUE and null otherwise. SAIPEN owns that semantic truth; external automation consumes it and never re-derives it. The human-visible `SAIPEN_CLOSURE_COMPLETE` line is display-only and must never be parsed as authority.

Why:
An external Run-to-Closure driver that guesses completion from assistant prose or an empty board can loop past a real stop or halt before real work. COMPLETE is therefore gated by eight mechanical conditions, including a fresh convergence pass committed strictly after the last audit-empty boundary and bound to the current `audit_epoch`; a new audit generation or a source mutation invalidates the prior proof. Unknown or ambiguous state fails closed to INVALID, never optimistically to CONTINUE or COMPLETE.

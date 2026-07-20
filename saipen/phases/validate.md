# Phase: VALIDATE
## Goal
Execute the conformance script to verify the structural integrity of `.saipen/`.
This prevents "schizophrenic READMEs" and agent hallucinations.

## Steps
1. **Terminal availability**: You MUST be able to execute scripts. If blocked, LOG `FAIL: no terminal, cannot validate` and exit to BLOCKED.
2. **Execute Validator**: The agent MUST evaluate the protocol's integrity across the three vectors CONFORMANCE.md defines:
   1. **Repo Validation**: `STATE.md`, `BOARD.md`, `LOG.md`, and `KNOWLEDGE/` conform to the shapes RFC.md § 1.2 defines.
   2. **Session Validation**: Acyclic dependencies in `BOARD.md`, graph integrity in `LOG.md`.
   3. **Phase Contract Validation**: Capability `mode` matches legal `phase` transition.
   If on Windows, the agent MUST run `tests\validate.ps1`. If on Unix, `tests/validate.sh`.
3. **Parse Output**: 
   - If PASS, LOG the success.
   - If FAIL, read the error message. Fix the structural corruption (e.g. malformed `LOG.md` line, missing `STATE.md` frontmatter) and rerun the validator.
4. **Transition**: If fixed or passed, transition to `PLAN` or `SCOUT` depending on the state of the `BOARD.md`.

# Phase: VALIDATE
## Goal
Execute the conformance script to verify the structural integrity of `.saipen/`.
This prevents "schizophrenic READMEs" and agent hallucinations.

## Steps
1. **Terminal availability**: You MUST be able to execute scripts. If blocked, LOG `RUN: validate -> FAIL, no terminal` (normal § 1.2 skeleton -- `FAIL` is a result inside the text, never a taxonomy label) and exit to BLOCKED.
2. **Execute Validator**: The agent MUST evaluate the protocol's integrity across the three vectors CONFORMANCE.md defines:
   1. **Repo Validation**: `STATE.md`, `BOARD.md`, `LOG.md`, and `KNOWLEDGE/` conform to the shapes RFC.md § 1.2 defines.
   2. **Session Validation**: Acyclic dependencies in `BOARD.md`, graph integrity in `LOG.md`.
   3. **Phase Contract Validation**: Capability `mode` matches legal `phase` transition.
   Canonical validator: `python <saipen-home>/tools/validate.py` from the project root (stdlib only, no installs; `python` may be `py` on Windows). It checks STATE.md against `extensions/schemas/state.schema.json` directly and covers graph checks the shell pair can't (E-### uniqueness/monotonicity, parent resolution). No Python on this host? Fall back per § 1.3 degradation to the frozen portable floor: `tests\validate.ps1` on Windows, `tests/validate.sh` on Unix -- same core checks, fewer of them.
   Optional, recommended on git projects: `python <saipen-home>/tools/install_hook.py` installs a pre-commit hook that runs this same validator before every commit -- checkpoint corruption gets caught at commit time instead of at the next VALIDATE. False positive? `git commit --no-verify`. To remove it later: `python <saipen-home>/tools/uninstall_hook.py`.
3. **Parse Output**: 
   - If PASS, LOG the success.
   - If FAIL, read the error message. Fix the structural corruption (e.g. malformed `LOG.md` line shape, missing `STATE.md` frontmatter field, missing `BOARD.md` heading) and rerun the validator. **Structure only** -- VALIDATE MUST NOT rewrite `LOG.md`'s historical event content, or silently alter any other file's real content, to make a check pass. A line whose shape is wrong gets its shape fixed; what actually happened stays what actually happened.
4. **Transition**: If fixed or passed, transition to `PLAN` or `SCOUT` depending on the state of the `BOARD.md`.

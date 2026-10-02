# T-1317 fresh-session reproduction — 2026-09-13

This is the pre-change Phase A record. It separates the observed host failure
from the earlier hook-installation evidence.

## Real fresh OpenCode session

- OpenCode: `1.18.30`.
- Session: `ses_f66a2dd5dffemRDGxYKmg06WYb`, created at
  `2026-09-13T06:03:32.898Z` by a new OpenCode instance.
- `context.directory`: `V:\___VAC\__K\__CODE\_PY\_FastPrompter` (OpenCode log
  and factory diagnostic).
- `context.worktree`: `V:/___VAC/__K/__CODE/_PY/_FastPrompter` (the OpenCode
  project row bound to that session's `projectID`).
- Audit input: the external staging file
  `V:\_TEMP_\fastprompter_drag\FastPrompter — AUDIT_20260913_0903.md`.
- `SAIPEN_PROJECT_ROOT`, `SAIPEN_PROJECT_LINEAGE`, `SAIPEN_AGENT`, and
  `SAIPEN_SKILL_ROOT`: unset in the reproducing environment.
- Hook: `C:\Users\vac34\.config\opencode\plugins\saipen-guard.js`.
- Loaded and installed hook SHA-256:
  `b5d4accdd747e68c2e1a5f0fbdc03ce22eb8a51429e00dbe1244ac29df51b6a0`.
- Guard runtime:
  `C:\Users\vac34\.config\opencode\skills\saipen\tools\saipen.py`.

The session read the staging audit successfully. The exact native Todo tool
identity recorded in the OpenCode part table was `todowrite`; the hook refused
it before host execution with `TARGET_UNRESOLVED`. This is SAIPEN-owned, not a
missing Todo backend or an OpenCode permission failure: OpenCode configuration
declared `todowrite` allowed, and the part's error is the guard refusal.

## Root and protocol-state cause

Running the shipped guard in a fresh Python process with the session's exact
`bash` root-probe event resolved:

```text
project_root: V:\___VAC\__K\__CODE\_PY\_FastPrompter
project_root_source: git-worktree
project_lineage: lineage-c13f771bc2924a5a81b65fc79e5aca08
```

Root selection was therefore correct. The staging audit path was not treated
as a project root, no ancestor `.saipen` was selected incorrectly, and no
stale/contradictory environment carrier was present. Admission then refused
the ordinary shell event with:

```text
PROTOCOL_STATE_INVALID
malformed STATE: phase 'IMPL' not one of INIT|PLAN|SCOUT|BUILD|VERIFY|REVIEW|SHIP|DONE|BLOCKED|VALIDATE|HUNT|MARKHUNT|ADD|CLEAN|TRANSLATE|PREPARE; invalid phase transition: DONE -> IMPL. Allowed from DONE: SCOUT, PLAN, HUNT, BLOCKED
```

The exact invalid source is FastPrompter's `.saipen/STATE.md`: `phase: IMPL`,
`transition_from: DONE`. The guard correctly treats generic shell as
potentially mutating, so it blocked the host before the harmless discovery
command could execute. That creates the bootstrap deadlock: OpenCode already
knows the worktree, but the adapter does not expose the canonical resolver's
answer to the model before consequential admission.

## Pre-change broad baseline

- `python tools/validate.py --gate core`: `37 problem(s), 25 warning(s)`.
- Existing durable broad baseline from the immediately preceding T-1317 tree:
  `1695 tests, 32 FAIL, 1 ERROR, 2 SKIP`.
- A new broad discovery was started before edits and reproduced the existing
  red clusters; it did not yield a retained final summary, so it is not used
  as stronger numerical evidence than the durable baseline above.

Phase B may proceed only against this cause. Generic shell admission is not a
valid repair.

# Phase: INIT

No `.saipen/` directory found. Create from `templates/` or write the core schema manually:
- `STATE.md` (MUST contain: `phase: PLAN`, `task: none`, `next_action: saipen continue`, `blocker: none`, `asp_version: 7`, `schema_version: 1`)
- `BOARD.md` (MUST contain empty sections: `## DOING`, `## TODO`, `## DONE`)
- `LOG.md` (MUST be empty or contain a single initial event `[E-001] DEC: Initialize SAIPEN`)
- `KNOWLEDGE/` directory (created on first need)

After bootstrap is physically written to disk, transition:
STATE -> `PLAN`
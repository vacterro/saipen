# Phase: INIT

No `.saipen/` directory found. Copy `extensions/templates/` (`STATE.md`,
`BOARD.md`, `LOG.md`) from the SAIPEN home -- do NOT freehand the schema.
Templates missing or unreachable (degraded capability only)? Write by hand,
matching exactly:
- `STATE.md`: frontmatter `phase: PLAN`, `task: none`, `next_action:
  "WAIT: provide the first project goal or raw backlog"` (RFC § 1.2's
  narrow INIT-bootstrap `WAIT:` exception -- ask for the goal/backlog
  only, nothing else), `blocker: none`, `agent: none`, `saipen_version: 7`,
  `saipen_home:` (absolute path of the SAIPEN home this bootstrap read the
  protocol from -- § 1.7's bootloader pointer; TEMPLATE COPIES TOO: the
  template ships it empty, fill it in), `mode:` (per § 1.3 capability
  negotiation, `full` unless something's actually missing),
  `goal_mode: false`, `updated:` (ISO-8601 UTC now).
- `BOARD.md`: `## DOING` / `## TODO` / `## DONE` / `## BLOCKED`, no tickets yet.
- `LOG.md`: starts empty. The first REAL entry (once work begins) MUST
  already follow the § 1.2 LOG skeleton -- no placeholder/example line
  gets written into a fresh project. A reasonable first entry once the
  user answers the bootstrap `WAIT:`: a `DEC` line recording the goal
  itself (e.g. "DEC: bootstrap SAIPEN for project -- goal: <what the user
  said>").
- `KNOWLEDGE/` directory (created on first need, not upfront).

After bootstrap is physically written to disk, transition:
STATE -> `PLAN`

# Phase: INIT

No `.saipen/` directory found. **Confirm that's actually true before creating
anything** (CORE.md §1.1): bind the project root exactly as BOOT describes. A
linked worktree resolves through its common Git directory to the main
worktree's existing memory; a nested non-Git cwd resolves to the nearest
ancestor already carrying `.saipen/`. No owner found means refuse a relative
write until the intended root is explicit. Bootstrapping in an unbound cwd
creates a second, disconnected `.saipen/` and orphans the project's real
continuation memory -- the one mistake this phase can make that no later
phase can detect on its own. Only genuinely absent at the explicitly chosen
or resolved root does the rest of this doc apply, and every path below is
absolute under that root.

Copy `extensions/templates/` (`STATE.md`,
`BOARD.md`, `LOG.md`) from the SAIPEN home -- do NOT freehand the schema.
Templates missing or unreachable (degraded capability only)? Write by hand,
matching exactly:
- `STATE.md`: frontmatter `phase: PLAN`, `task: none`, `next_action:
  "WAIT: init -- provide the first project goal or raw backlog"` (CORE.md §1.2's
  narrow INIT-bootstrap `WAIT:` exception -- ask for the goal/backlog
  only, nothing else), `blocker: none`, `agent:` (**never `none`**: `INIT` is executed by a real
  agent, and § 1.4 compares this field against itself to decide whether
  another agent is live, so an undefined identity makes that comparison
  meaningless in both directions from the very first checkpoint. This step
  ordered `none` and the shipped template carried it, so every project ever
  bootstrapped was born with one; unlike an angle-bracket slot it reads as a
  deliberate answer, which is why nothing caught it. `tools/validate.py`
  rejects it with the other placeholders and requires the template to ship
  one, so the field cannot survive as-copied. **Where the value comes from is not a choice**: CORE.md 1.4 derives it from the agent home this protocol was loaded from -- take that directory's own name, strip a leading dot, lowercase it. `.claude` -> `claude`, `.codex` -> `codex`, `.config/opencode` -> `opencode`. BOOT already resolved that path to find the phase docs, so there is nothing new to look up and nothing to invent. A model build name is never a seat and the validator FAILs one. No agent home identifiable at all? Use the platform's canonical name and LOG a `DEC` saying it was self-reported rather than derived), `saipen_version: 7`, `schema_version: 3`,
  `style_contract:` (the boot marker declared at the top of `STYLE.md` --
  § 1.2's voice marker, required from the very first checkpoint; it is the
  only field here whose value lives outside `.saipen/`),
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
  The initial STATE omits `last_event` because this LOG has no event. The
  first checkpoint after that real entry writes its numeric `E-###` ID as
  `last_event`, per CORE.md §1.2/§ 1.5.
- `KNOWLEDGE/` directory (created on first need, not upfront).

After bootstrap is physically written to disk, transition:
STATE -> `PLAN`, setting `transition_from: INIT`.

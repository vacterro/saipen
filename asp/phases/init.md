# Phase: INIT

No `.asp/` found. Create from `templates/` or write equivalent:
- STATE.md (phase: PLAN, task: none, next_action: ask user for goal)
- BOARD.md (empty sections: DOING / TODO / DONE)
- LOG.md (header only)
- KNOWLEDGE/ and tmp/ on first need

Ensure root `AGENTS.md` has this block (search `VACSKILL:BEGIN`, never dup):

```md
<!-- VACSKILL:BEGIN -->
## asp protocol (any agent)
Memory: .asp/ here. Read .asp/STATE.md before work; checkpoint as you go.
On "asp SET": read <VACSKILL_HOME>/PROTOCOL.md + <VACSKILL_HOME>/STYLE.md.
Path missing? clone github.com/vacterro/vacskill.
UI work: also obey <VACSKILL_HOME>/UI.md.
<!-- VACSKILL:END -->
```

`CLAUDE.md`/`GEMINI.md` missing: create each with
`Read AGENTS.md and obey its asp protocol block.`

After init: STATE -> PLAN.
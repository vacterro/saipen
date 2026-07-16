# vacskill Protocol v5

Vendor-neutral execution protocol for LLM agents. Memory owns the project;
model is a temporary worker. `.vacskill/` is the truth; chat is not memory.
STYLE.md loads with this file. UI work: also load UI.md.

## Boot sequence

1. Read `.vacskill/STATE.md` -- get `phase`, `task`, `next_action`.
2. Read `.vacskill/BOARD.md` -- find the current ticket.
3. Read `.vacskill/LOG.md` tail (~20 lines).
4. Read `.vacskill/KNOWLEDGE/` filenames (contents on demand).
5. Load `phases/<phase>.md` for the current phase rules.
6. Execute `next_action`. Checkpoint after every action.

No `.vacskill/`? Init from `templates/`. Ensure `AGENTS.md` has the
`VACSKILL:BEGIN` block (see `phases/init.md`).

## Commands -- `vacskill` / `vac`

| Say | Phase loaded |
|---|---|
| `vacskill GOAL` | init.md if needed, then plan.md |
| `vacskill` / `VACSKILL SET` | Resume current phase. Board done: hunt.md |
| `vacskill stop` | Checkpoint + handoff |
| `vacskill status` | Report only, change nothing |
| `vacskill ship` | review.md -> ship.md |
| `vacskill fix SYMPTOM` | verify.md (Debug path) |

## Capabilities -- protocol degrades, agent never fakes

| Missing | Degradation |
|---|---|
| git | no SHIP; backups via `.vacskill/history/`; hunt anchor = mtimes |
| terminal | VERIFY = MANUAL-VERIFY only, conf never above low |
| file write | read-only advisor: report, write nothing |
| network | no PUBLISH, no dep audits; LOG once |

## Memory -- `.vacskill/` at project root

```
STATE.md     rewrite   phase, task, next_action, blocker, agent, updated
BOARD.md     rewrite   TODO / DOING / DONE -- the scheduler
LOG.md       append    one line per event: DEC|RUN|H
KNOWLEDGE/   edit      durable truth (architecture, conventions, decisions, traps)
tmp/         scratch   empty by stop/ship
```

UTF-8 no BOM. No secrets. Travels with repo.

**Checkpoint -- write as you go; dying agents get no goodbye.**
Ticket done: tick BOARD + STATE `next_action` NOW.
Run/decision: LOG line NOW.
Before risky op: STATE `next_action` = that op FIRST.

### STATE.md
Frontmatter: `phase` `task` `next_action` `blocker` `agent` `updated`.
Body <=3 handoff lines at stop only.

### BOARD.md
```
- [ ] T-005 VERB+OBJECT | files: PATHS | verify: CMD | needs: T-003
```
DONE keeps `(verified: CHECK, conf: high|med|low)`. No verification = not done.
Pick: first DOING, else first TODO with all `needs:` done. Board order = law.

### LOG.md
`- DD.MM.YY HH:mm [T-###] DEC|RUN|H: ONE LINE <=120 CHARS`
DEC = decision. RUN = cmd PASS/FAIL. H = hypothesis confirmed/rejected.
Durable truth graduates to KNOWLEDGE/.

### KNOWLEDGE/
architecture.md, conventions.md, decisions.md, traps.md.
Create on first real content, never empty placeholders.

## Switch

**Resume:** boot sequence above. `updated` <15 min + different `agent:`:
confirm takeover. Set `agent:`, announce resume, continue in `phase`.

**Stop:** empty tmp/, STATE handoff <=3 lines + executable `next_action`,
tick BOARD, say `Saved. On any agent: VACSKILL SET`.

**Crash recovery:** LOG tail + first DOING over stale STATE. `git status`
reveals in-flight edits. Re-verify, finish or reset.

## Iron rules

1. Not run = not done.
2. Board picks task, not the agent.
3. `next_action` executable with zero chat history.
4. LOG = events. KNOWLEDGE/ = truth. Never mix.
5. Destructive ops: user confirms.
6. Every loop has a cap. Hit cap = BLOCKED + facts.
7. No litter. Delete only proven-unreferenced.
8. UTF-8 plain text. Unreadable memory = no memory.
9. Never fake a capability; degrade per table above.

## Token discipline

STATE + BOARD: full. LOG: tail only. KNOWLEDGE/: on demand.
Re-read only changed files. Grep before read. Batch tool calls.
Chat report <=8 lines. Quote <=3 decisive output lines.

## Maintenance

LOG >300 lines: compact in place (keep DECs, last RUN per task).
BOARD DONE >30: oldest to archive.md.
STATE contradicts files: rebuild from BOARD + LOG. Reality wins.
Protocol too: new rule evicts stale one.
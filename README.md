# vacskill -- cross-agent project memory protocol

**v5.1.0** | [Changelog](CHANGELOG.md) | plain markdown | zero deps | MIT

A **protocol**, not a skill. The shared language that lets any model open
`.vacskill/` and know exactly where state is, what is true, what is next --
and continue another agent's work like nothing happened.

Think `.git`, but for agent sessions.

```
  Agent A ---\
  Agent B ----+---> .vacskill/ ---> a week later: a completely different model
  Agent C ---/      (the truth)
```

## Why zero amnesia

Models come and go. The **memory stays**. Memory owns the project; the model
is a temporary worker.

```
your-project/.vacskill/
  STATE.md        where we are + the EXACT next command
  BOARD.md        tickets with needs: deps -- the boss
  LOG.md          journal: every run, every decision, one line
  KNOWLEDGE/      what is TRUE -- outlives every model
```

Journal = what HAPPENED. Knowledge = what is TRUE. Chat = nothing.
That single rule is why handoffs survive.

## Architecture -- 2-tier for token efficiency

Cold start loads ~110 lines (~1,200 tokens). Phase rules load on demand.

```
vacskill/                   <- the distributable unit
  PROTOCOL.md               boot protocol -- always loaded (~110 lines)
  phases/                   lazy-loaded per STATE.phase:
    init.md                   first-time setup
    plan.md                   ticket planning
    scout.md                  codebase reconnaissance
    build.md                  implementation
    verify.md                 verify + debug
    review.md                 review gates
    ship.md                   publish
    hunt.md                   autonomous bug sweep
  SKILL.md                  thin entry for skill-reading platforms
  STYLE.md                  voice (взбешённый дед с района, compressed)
  UI.md                     Win95 dark golden -- loaded only for UI work
adapters/                   per-model bridges, each ~10 lines
templates/                  fresh .vacskill/ boilerplate
style/                      optional voices: corporate, concise
schemas/                    frozen until an orchestrator exists
inject.ps1 / inject.sh      one-shot installer
```

**How it works:**
1. Agent loads `PROTOCOL.md` (boot rules, memory layout, iron rules).
2. Agent reads `.vacskill/STATE.md` to find current phase.
3. Agent loads `phases/<phase>.md` for that phase's rules only.
4. Agent executes. Checkpoints after every action.

A BUILD session never parses SHIP rules. A SCOUT never loads HUNT.
**Result: 60% fewer tokens per session vs monolithic v4.**

Every adapter ends the same: *"Everything else: follow PROTOCOL.md."*
95% of the system is model-independent.

## Three doctrines

- **Checkpoint as you go** -- dying agents get no goodbye turn; worst crash
  loses one ticket, `git status` shows even that.
- **Board picks the task** -- `needs:` DAG, top unblocked ticket, period.
- **Capability negotiation** -- no git? No SHIP. No terminal? MANUAL-VERIFY.
  The protocol degrades, the agent never fakes.

## Install

```bash
git clone https://github.com/vacterro/vacskill
cd vacskill
powershell -ExecutionPolicy Bypass -File .\inject.ps1     # Windows
bash inject.sh                                             # macOS / Linux
```

The injector finds every agent on the machine -- Claude Code, OpenCode,
Codex, Gemini/Antigravity, Aider, generic `~/.agents` -- and wires the
protocol in. Idempotent; re-run after `git pull`.

No install at all? One pasted line:

    Read <clone>/vacskill/PROTOCOL.md + <clone>/vacskill/STYLE.md and follow them.

## Use

| You say | What happens |
|---|---|
| `vacskill build me X` | notebook born, tickets planned, work starts |
| `vacskill` / `VACSKILL SET` | continues from notebook; empty board -> hunts bugs |
| `vacskill fix THING` | reproduce -> root cause -> regression test |
| `vacskill status` | state + numbers, touches nothing |
| `vacskill stop` | checkpoint, safe to walk away |
| `vacskill ship` | review gate -> 100% green -> your GitHub, tagged |

Every ticket: SCOUT -> BUILD -> VERIFY (honest confidence: high/med/low).
REVIEW guards the diff. Red never ships. Every loop has a hard cap.

## Supported platforms

Adapters: Claude Code, OpenCode, Codex CLI, Gemini/Antigravity, Aider,
OpenAI, DeepSeek, Qwen, and a generic paste-and-go for anything else.

## Editing the protocol

Boot PROTOCOL.md stays <=120 lines. Phase files stay focused. New rule
evicts a stale one. Voice in STYLE.md, theme in UI.md, platform quirks in
adapters/. Improvements from real usage pain only -- speculative features
are fat, not muscle.

MIT. Take it, wire it, let your robots talk to each other.
<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**v7.19.1** | [Spec](SPEC.md) | [Guide](GUIDE.md) | plain markdown | zero deps | MIT

**One command. Zero amnesia.**

**Не объясняй ничего. Просто напиши saipen и продолжи работу над проектом как ни в чём не бывало, любым агентом.**

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](GUIDE_EN.md)

A cold agent with zero chat history runs `/saipen continue` and resumes work in under a minute -- no rebriefing, any vendor, any day.

```text
User  ->  /saipen continue
Agent ->  reads STATE ("What do I do right now?")
Agent ->  reads BOARD ("What task am I picking up?")
Agent ->  reads next_action (executes command)
Agent ->  Works.
```

### Project State > Model Memory
Memory lives in the project, not in a model's head. `Project -> Memory -> LLM` becomes `Project -> SAIPEN State -> LLM`.

## Two Layers

| Layer | Required | Purpose |
|---|---|---|
| **Core** | ✅ | Continue work safely |
| **Maintenance** | On top of Core | Evolve the software with no tasking |

**Automated Evolution.** Board empty, type `/saipen`: `HUNT` audits for bugs, dead code, failing tests. Clean? `ADD` builds the next obvious missing capability, verifies it, hunts again. Product's mature -> stops gracefully.

**GOAL Mode.** `/saipen goal <what you want>` pivots the board (old tickets demoted, never deleted) and runs the new objective to completion -- no "shall I continue?" between tickets, VERIFY/REVIEW never skipped. SHIP auto-pushes to an existing remote; a brand-new repo still asks once. Capped at 3 waves / 20 tickets per run, then checkpoints and reports.

## Quick Start

**1. Install once per machine** -- teaches Claude Code, Gemini, OpenCode, Aider, Antigravity:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Start a project** -- open an agent in your folder, type:
> `saipen set`

No install? Paste one line to any agent:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Platform not in the list above (DeepSeek, Qwen, standalone OpenAI, etc.)?
Per-platform notes live in `extensions/adapters/`.

## Docs
- **[SPEC.md](SPEC.md)** -- formal architecture, for framework builders.
- **[RFC.md](saipen/RFC.md)** -- the ruleset agents actually execute.
- **[GUIDE.md](GUIDE.md)** -- human tutorial with examples.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

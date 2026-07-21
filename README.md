<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Continuation protocol for AI coding agents.** Persistent project memory in
plain markdown, so a cold agent with no chat history runs `/saipen continue`
and resumes work in under a minute -- no rebriefing, any vendor, any day.

**One command. Zero amnesia.**

**v7.31.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | plain markdown | zero deps | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](GUIDE_DED.md)

```text
User  ->  /saipen continue
Agent ->  reads STATE ("What do I do right now?")
Agent ->  reads BOARD ("What task am I picking up?")
Agent ->  reads next_action (executes command)
Agent ->  Works.
```

### Project State > Model Memory
Memory lives in the project, not in a model's head. `Project -> Memory -> LLM` becomes `Project -> SAIPEN State -> LLM`.

### Key Protocol Logic & Guarantees
- **Core State Machine**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Zero-Prompt Autonomy**: Board empty? Auto-transitions `HUNT` (scan bugs) → `ADD` (evolve features) → `HUNT` loop. Zero questions asked.
- **Explicit Triggers**: `/saipen clean` (repo scrub), `/saipen translate` (isolated `.saitranslate/` factory), `/saipen validate` (conformance check), `/saipen goal` (autonomous wave execution).
- **Strict Reliability**: Batch input parsing (surgical 1-by-1 tickets), dirty-tree adoption (never wipes uncommitted work), secret redaction (`sk-***`).

## Two Layers

| Layer | Required | Purpose |
|---|---|---|
| **Core** | ✅ | Continue work safely |
| **Maintenance** | On top of Core | Evolve the software with no tasking |

**Automated Evolution.** Board empty, type `/saipen`: `HUNT` audits for bugs, dead code, failing tests. Clean? `ADD` builds the next obvious missing capability, verifies it, hunts again. Product's mature -> stops gracefully.

**GOAL Mode.** `/saipen goal <what you want>` pivots the board (old tickets demoted, never deleted) and runs the new objective forward -- no "shall I continue?" between tickets, VERIFY/REVIEW never skipped. SHIP auto-pushes to an existing remote; a brand-new repo still asks once. Shipping the objective isn't the stopping point either -- it falls straight into autonomous HUNT/ADD maintenance until the product is mature, blocked, or the run hits its cap (3 waves / 20 tickets, then checkpoints and reports).

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

## Documentation & Specification Links
- **[SPEC.md](SPEC.md)** -- formal architecture, design goals, litmus test.
- **[RFC.md](saipen/RFC.md)** -- normative specification executed by agents.
- **[GUIDE.md](GUIDE.md)** -- human tutorial & ELI5 guides:
  - 🇷🇺 [Русский](GUIDE_RU.md) | 🇺🇸 [English](GUIDE_EN.md) | 🇪🇪 [Eesti](GUIDE_EE.md) | 🇯🇵 [日本語](GUIDE_JA.md) | 👴 [Версия Деда](GUIDE_DED.md)
  - 🇺🇦 [Українська](GUIDE_UK.md) | 🇩🇪 [Deutsch](GUIDE_DE.md) | 🇫🇷 [Français](GUIDE_FR.md) | 🇪🇸 [Español](GUIDE_ES.md) | 🇮🇹 [Italiano](GUIDE_IT.md)
  - 🇵🇹 [Português](GUIDE_PT.md) | 🇳🇱 [Nederlands](GUIDE_NL.md) | 🇵🇱 [Polski](GUIDE_PL.md) | 🇸🇪 [Svenska](GUIDE_SV.md) | 🇩🇰 [Dansk](GUIDE_DA.md)
  - 🇫🇮 [Suomi](GUIDE_FI.md) | 🇳🇴 [Norsk](GUIDE_NO.md) | 🇨🇳 [中文](GUIDE_ZH.md) | 🇰🇷 [한국어](GUIDE_KO.md) | 🇹🇭 [ไทย](GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](GUIDE_VI.md) | 🇸🇦 [العربية](GUIDE_AR.md) | 🇮🇱 [עברית](GUIDE_HE.md)
  - 🇹🇷 [Türkçe](GUIDE_TR.md) | 🇮🇳 [हिन्दी](GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](GUIDE_ID.md) | 🇬🇷 [Ελληνικά](GUIDE_EL.md) | 🇨🇿 [Čeština](GUIDE_CS.md) | 🇷🇴 [Română](GUIDE_RO.md)
  - 🇭🇺 [Magyar](GUIDE_HU.md) | 🇧🇬 [Български](GUIDE_BG.md) | 🇸🇰 [Slovenčina](GUIDE_SK.md) | 🇭🇷 [Hrvatski](GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- agent communication style & voice definition.
- **[UI.md](saipen/UI.md)** -- Dark Golden Win95 UI design guidelines.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- behavioral test scenarios & validator rules.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

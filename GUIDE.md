<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide

It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN fixes that.** Tiny `.saipen/` folder in project. Agent reads STATE, BOARD, next_action. Resumes where other stopped. Zero briefing.

**Fast keys:** `cc` continues an active Goal Mode run, `sss` checks status without touching code, and `ss` checkpoints and stops. [Full 13-key map](saipen/RFC.md#110-command-surface); Cyrillic twins `сс`, `ссс`, `аа`, `ее`, `еее`, `рр` work too.

**Package keys:** `ee`/`qq` prepare complete translation/wiki packages without integrating; `eee`/`qqq` accept only ready packages, then integrate, verify, review, and push.

## How

1. **Install once** -- teaches Claude, Gemini, Codex, OpenCode, Aider, Antigravity, any skill reader:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Init project** -- open agent in project folder, type:
> `saipen set`

Agent creates `.saipen/`. Start planning.

3. **Work** -- type `saipen continue`. Agent reads notes, picks top task, does work.

4. **Next day? Different agent?** Same command: `saipen continue`. Reads `.saipen/`. Continues. No re-explain.

## Commands

| You type | What happens |
|---|---|
| `saipen set` | Bootstrap `.saipen/` memory, start planning |
| `saipen continue` | Wake up, read state, execute next action |
| `saipen stop` | Checkpoint work, hand back control |
| `saipen status` | Report current board state, no code touch |
| `saipen goal <text>` | New objective. Agent plans, builds, tests, ships autonomously. Then HUNT→ADD loop until mature or capped (3 waves / 20 tickets) |
| `saipen plan [text]` | Generate task list. Bare = autonomous proposal |
| `saipen clean` | Scrub repo: prune done tickets, delete orphans, fix paths |
| `saipen translate` | Build 32-language bundle in isolated `.saipen/saitranslate/`. Safe. |
| `saipen markhunt` | Dry exhaustive audit. Records findings, fixes nothing |
| `saipen prepare` | Package work for handoff. Freshness check, injection instructions |
| `saipen ship` | Release: version bump, changelog, tag, push |
| `saipen validate` | Conformance check + fix structural corruption |

**Experimental crew:** `extensions/subs/` spawns read-only helpers (`saihunt` finds bugs, `saipython` fixes small ones). Each in own window. Reports via OUTBOX.md. Active testing, not battle-hardened yet.

## Multilingual Guides

| | | |
|---|---|---|
| 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) |
| 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md) | 🇺🇦 [Українська](guides/GUIDE_UK.md) |
| 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) |
| 🇮🇹 [Italiano](guides/GUIDE_IT.md) | 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) |
| 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md) |
| 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) |
| 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) |
| 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md) | 🇹🇷 [Türkçe](guides/GUIDE_TR.md) |
| 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) |
| 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md) | 🇭🇺 [Magyar](guides/GUIDE_HU.md) |
| 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md) |

## Memory, not just rules

`.saipen/KNOWLEDGE/` holds durable truth: architecture decisions, conventions. Survives agent death. Two formats: running `decisions.md` or numbered `ADR-001.md`. Agent reads before planning.

Kitchen (`.saipen/kitchen/`) = scratchpad. Half-finished files. Agent dies? Next one picks up from kitchen.

## Messy folder? Normal

Uncommitted changes expected. Agent commits at `ship`, not every step. Before touching, checks ownership: own ticket → continue. Your edits → leave alone. No surprise commits. No surprise reverts.

## Obsidian compatible

`.saipen/` = plain markdown. Open project root as vault. KNOWLEDGE/ shows in graph. `[[wikilinks]]` work. Kitchen + LOG can be excluded. Only KNOWLEDGE/ is for your notes.

## When agent can't do something

Checks host capabilities first. No git? Says so. No shell? Hands you exact command. `WAIT: <category> -- <question>` = needs you. The category is one of seven
(`manual-verify`, `destructive-op`, `first-publish`, `user brake`, `blocked`,
`safety valve`, `init`) and tells you what kind of answer unblocks it.
Answer, it continues.

## Lock it down

```bash
python <saipen-clone>/tools/install_hook.py
```
Pre-commit hook. Broken board, bad log line caught before commit. Remove:
```bash
python <saipen-clone>/tools/uninstall_hook.py
```

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

---

**Full command list / complete command reference:** [RFC § 1.10](saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.

<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Naklejka" width="200"/>
</p>

# SAIPEN

**Protokół kontynuacji dla agentów programujących AI.** Trwała pamięć projektu w
zwykłym markdownie, dzięki czemu zimny agent bez historii czatu uruchamia `/saipen continue`
i wznawia pracę w mniej niż minutę -- bez ponownego wprowadzania, dowolny dostawca, dowolny dzień.

**Jeden nakaz. Zero amnezji.**

**Szybkie klawisze:** `cc` kontynuuje aktywny Goal Mode, `sss` pokazuje stan bez dotykania kodu, a `ss` zapisuje punkt kontrolny i zatrzymuje się. [Zobacz pełną mapę 15 klawiszy](saipen/RFC.md#110-command-surface). Cyrylickie bliźniaki też działają: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Język odpowiedzi.** Agent domyślnie odpowiada **po estońsku** — to ustawienie, a nie dziwactwo, i nic więcej w SAIPEN nie jest estońskie. Zmienia się to w jednym miejscu: linia `reply_language:` na początku [`saipen/STYLE.md`](saipen/STYLE.md). `et` estoński, `en` angielski, `ru` rosyjski, `auto` wybiera na podstawie języka Twojej wiadomości. Protokół, kod, commity i wszystkie dokumenty pozostają angielskie przy każdej wartości.

**v7.210.0** | [Spec](SPEC.md) | [Przewodnik](GUIDE.md) | [RFC](saipen/RFC.md) | [Styl](saipen/STYLE.md) | [UI](saipen/UI.md) | [Zgodność](saipen/CONFORMANCE.md) | zwykły markdown | zero zależności | MIT

```text

### Stan Projektu > Pamięć Modelu

Pamięć żyje w projekcie, nie w głowie modelu. `Projekt -> Pamięć -> LLM` staje się `Projekt -> Stan SAIPEN -> LLM`.


## Commands

The full surface is 16 commands; complete details in [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Command | What it does |
|---|---|
| `/saipen set` | Adopt a project |
| `/saipen continue` | Resume exactly where you left off |
| `/saipen plan` | Turn a request or raw queue into tickets |
| `/saipen goal <text>` | Autonomous wave assault on a new objective |
| `/saipen hunt` | Force an immediate defect/improvement scan |
| `/saipen ship` | Version bump, changelog, tag, push |
| `/saipen clean` | Repository cleanup |
| `/saipen validate` | Conformance check |
| `/saipen markhunt` | Dry uncapped audit, record only |
| `/saipen translate` | Isolated translation factory |
| `/saipen prepare` | Package work for handoff |
| `/saipen collect` | Integrate a ready package |
| `/saipen status` | Read-only report |
| `/saipen stop` | Checkpoint and halt |

<sub>`saipen init` and `saipen sub` complete the sixteen; both are called by the protocol, not typed daily.</sub>

**Package keys.** `ee`/`qq` prepare a complete translation or wiki package without integrating; `eee`/`qqq` accept only a ready package, then integrate, verify, review, and push.

**Experimental: saicrew.** Optional bonus layer (`extensions/subs/`, zero Core changes) for running a multi-agent crew — one Core writer plus read-only `saihunt`/`saipython` workers reporting through their own `OUTBOX.md`. Under active live testing, not finalised — see `extensions/subs/crew.md`.

## Two layers

| Layer | Required | Purpose |
|---|---|---|
| **Core** | ✅ | Resume work safely |
| **Maintenance** | On top of Core | Evolve software without task direction |

**Automated evolution.** No open tasks remain, type `/saipen`: `HUNT` audits for bugs, dead code, and failing tests. Clean? `ADD` builds the next obvious missing capability, verifies it, and hunts again. Product mature -> stops gracefully.

**GOAL Mode.** `/saipen goal <what you want>` pivots the board (deprioritises old tickets, never deletes them) and drives the new objective forward — no "should I continue?" between tickets, VERIFY/REVIEW never skipped. SHIP auto-pushes to the existing remote; a brand-new repository still asks once. Shipping a goal is not the end point either — it transitions straight into autonomous HUNT/ADD maintenance until the product is mature, blocked, or the run hits its cap (3 waves / 20 tickets, then checkpoints and reports).

## Quick Start

**1. Install once per machine** — teaches Claude Code, Codex, Gemini, OpenCode, Aider, Antigravity and any generic `~/.agents/skills` reader (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What this touches, so there are no surprises: the script adds a tagged block `<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` to your agent instruction files (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) — backing up first as `.bak` — and copies the protocol into the relevant skill folders. Nothing outside those paths, no daemon, no network calls.</sub>

**Regret it?** One command takes it back:
```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```
This removes exactly the tagged block (leaving the rest of the file untouched), saves a pre-removal `.uninstalled.bak` copy, and removes the skill folders.

**2. Start a project** — open an agent in your folder and type:
> `saipen set`

Not installed? Paste one line into any agent:
> Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Platform not in the list above (DeepSeek, Qwen, standalone OpenAI, etc.)?
Platform-specific notes live in `extensions/adapters/`.

## Documentation

| Document | What it is |
|---|---|
| [SPEC.md](SPEC.md) | Formal architecture, design goals, litmus test |
| [RFC.md](saipen/RFC.md) | Normative specification agents execute |
| [GUIDE.md](GUIDE.md) | Human tutor and ELI5 guides |
| [STYLE.md](saipen/STYLE.md) | Agent communication style and voice definition |
| [UI.md](saipen/UI.md) | Vintage Golden UI design guidelines |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Behavioural test scenarios and validator rules |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [English](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Deutsch](guides/GUIDE_DE.md) · 🇫🇷 [Français](guides/GUIDE_FR.md) · 🇪🇸 [Español](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Português](guides/GUIDE_PT.md) · 🇳🇱 [Nederlands](guides/GUIDE_NL.md) · 🇵🇱 [Polski](guides/GUIDE_PL.md) · 🇸🇪 [Svenska](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Built with SAIPEN

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — High-performance prompt management tool built natively around the SAIPEN memory protocol.

## Screenshots

<details>
<summary>Click to expand</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- source-digest: README.md sha256:535e0088a9f9fcb5b9dc4d0a6e1072ac643101e0083789f57d4850be564931ce -->




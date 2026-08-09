<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол за приемственост за AI агенти за кодиране.** Персистентна проектна памет в чист markdown, така че нов агент без история на чата да стартира `/saipen continue` и да възобнови работа за под минута -- без повторен брифинг, всеки доставчик, всеки ден.

**Една команда. Нула амнезия.**

**Бързи клавиши:** `cc` продължава активен Goal Mode, `sss` показва статус без допиране до кода, а `ss` запазва контролна точка и спира. [Виж пълната карта с 15 клавиша](saipen/RFC.md#110-command-surface). Кирилските близнаци също работят: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Език на отговорите.** Агентът по подразбиране отговаря **на естонски** — това е настройка, а не приумица, и нищо друго в SAIPEN не е на естонски. Променя се на едно място: редът `reply_language:` в началото на [`saipen/STYLE.md`](saipen/STYLE.md). `et` естонски, `en` английски, `ru` руски, `auto` избира според езика на твоето съобщение. Протоколът, кодът, комитите и всички документи остават на английски при всяка стойност.

**v7.219.0** | [Спецификация](SPEC.md) | [Ръководство](GUIDE.md) | [RFC](saipen/RFC.md) | [Стил](saipen/STYLE.md) | [UI](saipen/UI.md) | [Съответствие](saipen/CONFORMANCE.md) | чист markdown | нула зависимости | MIT

```text

### Project State > Model Memory

**Project state is stronger than model memory.** Memory lives in the project, not the model's head. `Project -> Memory -> LLM` becomes `Project -> SAIPEN state -> LLM`.

- **Core state machine** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomy without prompting** — board stalled (no workable `TODO`, `DOING` empty) **and not `BLOCKED`**? Auto-transition to `HUNT` (bug scanning) → `ADD` (feature development) → `HUNT`, no questions asked. A `BLOCKED` session never launches autonomous hunting — it waits for a human to resolve the block (RFC § 2.1).
- **Strict reliability** — batch input parsing (surgical 1-at-a-time tickets), dirty tree adoption (never wipes uncommitted work), secret redaction (`sk-***`).

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


| Слой | Задължителен | Цел |
|---|---|---|
| **Основен (Core)** | ✅ | Безопасно продължаване на работата |
| **Поддръжка (Maintenance)** | Върху Основния | Развитие на софтуера без възлагане на задачи |

**Автоматизирана еволюция.** Няма останали отворени задачи, напишете `/saipen`: `HUNT` одитира за бъгове, мъртъв код, падащи тестове. Всичко е чисто? `ADD` изгражда следващата очевидно липсваща възможност, верифицира я, търси отново. Продуктът е зрял -> спира плавно.

**Режим GOAL.** `/saipen goal <какво искате>` преориентира дъската (старите тикети се понижават, никога не се изтриват) и придвижва новата цел напред -- без "да продължа ли?" между тикетите, VERIFY/REVIEW никога не се прескачат. SHIP автоматично push-ва към съществуващо дистанционно хранилище; чисто ново хранилище все пак пита веднъж. Доставянето на целта също не е точка на спиране -- то преминава директно в autonomous HUNT/ADD поддръжка, докато продуктът стане зрял, блокиран или изпълнението достигне лимита си (3 вълни / 20 тикета, след което прави чекпойнт и докладва).


## Quick Start


**1. Инсталирайте веднъж на машина** -- обучава Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex и всеки родов четец на `~/.agents/skills` (FreeBuff и др.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Стартирайте проект** -- отворете агент във вашата папка, напишете:
> `saipen set`

Нямате инсталация? Поставете един ред на всеки агент:
> Прочетете <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md и ги следвайте.

Платформата не е в списъка по-горе (DeepSeek, Qwen, самостоятелен OpenAI и т.н.)?
Бележките за отделните платформи са в `extensions/adapters/`.


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




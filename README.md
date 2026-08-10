<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp; 
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp; 
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Continuation protocol for AI coding agents.** SAIPEN keeps project memory in
plain Markdown, so a cold agent with no chat history can run
`/saipen continue`, read `STATE.md` -> `BOARD.md` -> active `LOG.md` tail ->
`human_note` (if set), and execute the persisted `next_action` without relying
on chat history or one model vendor's memory.

**One command to resume. Plain-file state. Machine-checked contracts.**

**Fast keys.** A shortcut is the entire message, never a prefix. `cc` continues the project context to convergence (resuming a running goal if one is set), `sss` reports status without touching code, and `ss` checkpoints and stops. [See the full 15-key map](saipen/CORE.md#110-command-surface). Cyrillic twins work too: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**v7.221.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | MIT

```text
User  ->  /saipen continue
Agent ->  reads STATE.md (phase, task, next_action, mode, human_note)
Agent ->  reads BOARD.md (DOING / TODO / DONE / BLOCKED tickets)
Agent ->  reads active LOG.md tail (recent events)
Agent ->  reads human_note (if set, one-time nudge)
Agent ->  executes next_action (command) immediately
Agent ->  loads phase doc only when rules are needed
Agent ->  Works.
```

## How it works

**Project state beats model memory.** Memory lives in the project, not in a
model's head. `Project -> Memory -> LLM` becomes `Project -> SAIPEN State -> LLM`.

- **Core state machine** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomous maintenance** — board halted (no workable `TODO`, nothing in
  `DOING`) **and not `BLOCKED`**? Auto-transitions `HUNT` (scan bugs) → `ADD`
  (evolve features) → `HUNT`, zero questions asked. A session sitting at
  `BLOCKED` never auto-hunts; it waits for the human to resolve the blocker
  ([Maintenance § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Safety rules** — batch input parsed into surgical one-by-one tickets,
  dirty-tree adoption preserves uncommitted work, and secret-like values are
  redacted from logs (`sk-***`).

## Engineering evidence

SAIPEN combines a normative plain-file protocol with executable, failure-oriented
checks. The repository demonstrates protocol/state-machine design, Python
tooling, schema-driven state, recovery reasoning, regression testing,
multi-agent workflow boundaries, and specification discipline.

- **Designed contract:** [SPEC.md](SPEC.md) defines the file-backed continuation
  model and stable on-disk contract; [CORE.md](saipen/CORE.md) and
  [MAINTENANCE.md](saipen/MAINTENANCE.md) own current normative behavior.
- **Machine-checked state:** the stdlib-only
  [canonical validator](tools/validate.py) reads the live
  [STATE schema](extensions/schemas/state.schema.json) and checks phase
  transitions, ticket dependencies, event-graph links, cross-document
  invariants, capabilities, and recovery state.
- **Failure coverage:** [CONFORMANCE.md](saipen/CONFORMANCE.md) maps requirements
  to [scenario fixtures](tests/scenarios/); the
  [scenario runner](tools/run_scenarios.py) executes structural pass/fail cases
  including corrupt recovery state, invalid transitions, dependency cycles,
  and read-only restrictions.
- **Regression controls:** [audit_checks.py](tools/audit_checks.py) mutates
  known-good copies and proves validator checks can still go red, rather than
  treating a permanently green check as evidence.
- **Executable layer:** [saipen.py](tools/saipen.py) provides journaled state
  operations; [bootstrap/](bootstrap/) contains install, uninstall, and export
  helpers, with an optional [pre-commit hook installer](tools/install_hook.py).
- **Explicit tradeoffs:** Core protocol state is plain files with no runtime
  dependency. Canonical validation and CLI tooling require Python, but use only
  its standard library and need no `pip` install. Journaled SAIOPS state
  mutations use a project-scoped OS lock and recovery journal; ordinary project
  edits and disconnected writers are outside that lock. SAIPEN is not
  distributed consensus, so disconnected writers require external coordination
  ([boundary](SPEC.md#concurrency--distribution-boundaries),
  [mechanics](saipen/OPS.md#5-locks)).

**Reply language.** The agent answers in **Estonian** by default — that is a setting, not a quirk, and nothing else about SAIPEN is Estonian. Change it in one place: the `reply_language:` line at the top of [`saipen/STYLE.md`](saipen/STYLE.md). `et` Estonian, `en` English, `ru` Russian, `auto` picks from the message you sent. The protocol, the code, the commits and every document stay English at every value.

## Common commands

Common entry points are below; the complete current surface lives in
[Core § 1.10](saipen/CORE.md#110-command-surface).

| Command | Does |
|---|---|
| `/saipen set` | Adopt a project |
| `/saipen continue` | Resume exactly where it stopped |
| `/saipen plan` | Turn a request or raw backlog into tickets |
| `/saipen goal <text>` | Autonomous wave execution against a new objective |
| `/saipen hunt` | Force the defect/improvement sweep now |
| `/saipen ship` | Run release gates; commit, tag, and push when permitted |
| `/saipen clean` | Repo scrub |
| `/saipen validate` | Conformance check |
| `/saipen markhunt` | Dry uncapped audit, records only |
| `/saipen translate` | Isolated translation factory |
| `/saipen prepare` | Package work for handoff |
| `/saipen collect` | Integrate a ready package |
| `/saipen status` | Read-only report |
| `/saipen stop` | Checkpoint and halt |

**Package keys.** `ee`/`qq` prepare complete translation/wiki packages without
integrating; `eee`/`qqq` accept only ready packages, then integrate, verify,
review, and push.

**Experimental: saicrew.** An optional bonus layer (`extensions/subs/`, zero Core
changes) for running a multi-agent crew: one Core writer plus read-only
`saihunt`/`saipython` workers reporting through their own `OUTBOX.md`. Under live
testing, not yet verified end to end — see
[extensions/subs/crew.md](extensions/subs/crew.md).

## Two layers

| Layer | Required | Purpose |
|---|---|---|
| **Core** | ✅ | Continue work from project-backed state |
| **Maintenance** | On top of Core | Evolve the software with no tasking |

**Automated evolution.** No open to-dos left, type `/saipen`: `HUNT` audits for
bugs, dead code, failing tests. Clean? `ADD` builds the next justified missing
capability, verifies it, and hunts again. When its completion rule finds no
justified addition, it stops.

**Goal Mode.** `/saipen goal <what you want>` pivots the board (old tickets
demoted, never deleted) and runs the new objective forward -- no "shall I
continue?" between tickets, with each ticket routed through VERIFY/REVIEW. In a
publish-capable mode, SHIP pushes to an existing remote; a brand-new repo still
asks once. Shipping the objective isn't the stopping point either -- it falls
straight into autonomous HUNT/ADD maintenance until the completion rule fires,
work is blocked, or the run hits its cap (3 waves / 20 tickets, then checkpoints
and reports).

## Quick start

**1. Install once per machine** -- teaches Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, and any generic `~/.agents/skills` reader (FreeBuff, etc.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` block to the agent instruction
files you already have (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) -- backing each up to `.bak`
first -- and copies the protocol into the matching skill folders. Nothing
outside those paths, no daemon, no network calls.</sub>

**2. Start a project** -- open an agent in your folder, type:

> `saipen set`

**No install?** Paste one line to any agent:

> Read &lt;clone&gt;/saipen/BOOT.md first (cold-start kernel), then &lt;clone&gt;/saipen/INDEX.md + &lt;clone&gt;/saipen/STYLE.md and follow them.

Platform not in the list above (DeepSeek, Qwen, standalone OpenAI, etc.)?
Per-platform notes live in `extensions/adapters/`.

**Changed your mind?** One command puts it back:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

It strips exactly the marked block (leaving the rest of your file alone), saves
a `.uninstalled.bak` copy first, and removes the skill folders.

## Documentation

| Document | What it is |
|---|---|
| [SPEC.md](SPEC.md) | Formal architecture, design goals, litmus test |
| [CORE.md](saipen/CORE.md) | Normative continuation, state machine, and command contract |
| [MAINTENANCE.md](saipen/MAINTENANCE.md) | Autonomous maintenance and Goal Mode |
| [RFC.md](saipen/RFC.md) | Compatibility redirect to the split normative documents |
| [GUIDE.md](GUIDE.md) | Human tutorial and ELI5 guides |
| [STYLE.md](saipen/STYLE.md) | Agent communication style and voice |
| [UI.md](saipen/UI.md) | Vintage Golden UI design guidelines |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Behavioral test scenarios and validator rules |
| [БРОШЮРА](BROCHURE_DED.md) | MUST BE TRANSLATED by saitranslate |

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
<img width="1920" height="1080" alt="clipboard_20260806_183348_73b2c6b5" src="https://github.com/user-attachments/assets/7cc6fe44-cbba-4d8c-85c4-728be4fbb54c" />

## Built with SAIPEN

⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — high-performance
prompt management tool built around the SAIPEN memory protocol.

## Screenshots

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

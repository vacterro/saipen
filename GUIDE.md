<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide

Welcome to SAIPEN! If you're a human developer looking to tame your AI agents, you're in the right place. 

## What is SAIPEN?
When you switch agents (or use the same agent on different days) working on a codebase, they tend to forget decisions, step on each other's toes, or hallucinate capabilities. SAIPEN acts like a tiny `.git` folder specifically for the AI agent's working memory.

## How it works
1. **Global Install:** You run `bootstrap/inject.ps1` (or `.sh`) once on your machine. This teaches Claude, Gemini, Aider, and Antigravity what SAIPEN is.
2. **Project Init:** You open an agent in your project folder and type `saipen set` (or `saipen init`). The agent reads its global rules and creates a `.saipen/` directory in your current project.
3. **Working Memory:** From now on, the agent stores its current task, progress board, and logs in `.saipen/STATE.md` and `.saipen/BOARD.md`.
4. **Resuming:** You close your laptop, wait a week, open a completely different agent, and type `/saipen continue`. The new agent reads the `.saipen/` folder and resumes exactly where the old one left off.

## Commands you can type to the Agent
While agents interact with the file system directly, you just type normal chat messages to control them:

| What you type | What the agent does |
|---|---|
| `saipen set` | Bootstraps the project with `.saipen/` memory and starts planning. |
| `saipen continue` | Wakes up, reads the state, and executes the very next action. |
| `saipen stop` | Forces the agent to checkpoint its work and hand control back to you. |
| `saipen status` | Reads `.saipen/BOARD.md` and tells you what's currently going on without doing work. |
| `saipen goal <text>` | Demotes (never deletes) current tasks, plans the new objective, and drives it forward autonomously -- including auto-push on ship. Shipping the objective isn't the stopping point either: it falls straight into autonomous HUNT/ADD maintenance until the product is mature, blocked, or the run hits its cap (3 waves / 20 tickets). |
| `saipen clean` | Forces the agent to scrub the workspace, prune old done tickets, remove orphaned files, fix bad paths, and ensure everything is updated. |
| `saipen translate` | Builds/updates a 32-language translation bundle in an isolated `.saipen/saitranslate/` folder, never touching your actual source. |
| `saipen ship` | Explicitly triggers a release (version bump, changelog, tag, push) even outside the normal ticket flow. |
| `saipen validate` | Runs the conformance check on `.saipen/` and fixes any structural corruption it finds. |

## Multilingual Guides / Руководства на разных языках

Read SAIPEN guides in your native language:

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

## Project Knowledge & Kitchen
Don't put project-specific rules in the global agent prompts. Put them in `.saipen/KNOWLEDGE/`!
- Create ADRs (Architecture Decision Records) or simple text files.
- The agent reads everything here before it starts planning.

The agent also has a `.saipen/kitchen/` directory. It uses this to store intermediate, half-finished files and scratchpads. If an agent dies mid-process, the next agent can just look into the `kitchen/` and immediately pick up where it left off.

## Coming back to a messy folder
If you (or a previous agent session) left uncommitted changes sitting in the project, that's not a red flag -- it's normal. SAIPEN treats work as committed at `saipen ship`, not after every small step, so mid-ticket edits sitting uncommitted are expected, not an accident. Before touching anything, the agent checks whose changes those are: its own unfinished ticket -- it continues; anyone else's edits (yours, another tool's) -- it leaves them exactly alone. No surprise auto-commits, no surprise reverts.

## Recording decisions, not just rules
`.saipen/KNOWLEDGE/` isn't only for "always use tabs" -- it's also the right place for actual architecture decisions, so they outlive any single agent's memory. Two accepted shapes: one running `decisions.md` you keep appending to, or numbered `ADR-001.md`, `ADR-002.md`... files, one immutable record per decision. Use whichever already fits how your team documents things.

## Already keep an Obsidian vault or your own notes?
SAIPEN doesn't compete with your existing system -- `.saipen/` is plain markdown by construction, so it's already Obsidian-compatible with zero setup. Open your project root as a vault and `.saipen/KNOWLEDGE/` shows up as a normal part of your graph: `[[wikilinks]]`, backlinks, your own frontmatter properties -- none of that is something the protocol polices, KNOWLEDGE/'s only real rule is "durable truth, not an event log." Don't want `.saipen/kitchen/` or `LOG.md`'s event stream cluttering search/graph view? Exclude them in Obsidian's settings -- KNOWLEDGE/ is the one folder actually meant to live in your notes.

If your real project tracking already lives in your head and your own vault, that's fine -- SAIPEN's board/ticket machinery exists for what the *agent* needs to stay oriented session to session. It doesn't ask you to replace whatever discipline already works for you; it just means the agent stops being the one part of the system with no memory of its own.

## When the agent genuinely can't do something
Before doing any work, the agent checks what the host actually supports -- is git installed, is there a shell, can it write files at all -- and records that as `mode` in `STATE.md`. No git: it won't attempt a push, it'll say so. No shell: it'll hand you the exact command to run yourself and wait for your report. That's also why you'll sometimes see `next_action: WAIT: <a specific question>` -- it's not stalling, it's asking the one thing only you can answer. Answer it in chat and it proceeds immediately.

## Locking it down before every commit (optional)
On a git project and want a safety net? Run this once from the project root:
```bash
python <path-to-your-saipen-clone>/tools/install_hook.py
```
It installs a pre-commit hook that checks `.saipen/`'s structural integrity before every commit -- a broken board or a malformed log line gets caught right there, not three sessions later when you're trying to figure out who broke what. Want it gone later? `python <path-to-your-saipen-clone>/tools/uninstall_hook.py` removes exactly that hook and restores whatever was there before it, if anything.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

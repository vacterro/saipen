<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide

Welcome to SAIPEN! If you're a human developer looking to tame your AI agents, you're in the right place. 

## What is SAIPEN?
When you have multiple agents (or even the same agent on different days) working on a codebase, they tend to forget decisions, step on each other's toes, or hallucinate capabilities. SAIPEN acts like a tiny `.git` folder specifically for the AI agent's working memory.

## How it works
1. **Global Install:** You run `bootstrap/inject.ps1` (or `.sh`) once on your machine. This teaches Claude, Gemini, Aider, and Antigravity what SAIPEN is.
2. **Project Init:** You open an agent in your project folder and type `saipen SET` (or `saipen INIT`). The agent reads its global rules and creates a `.saipen/` directory in your current project.
3. **Working Memory:** From now on, the agent stores its current task, progress board, and logs in `.saipen/STATE.md` and `.saipen/BOARD.md`.
4. **Resuming:** You close your laptop, wait a week, open a completely different agent, and type `/saipen continue`. The new agent reads the `.saipen/` folder and resumes exactly where the old one left off.

## Commands you can type to the Agent
While agents interact with the file system directly, you just type normal chat messages to control them:

| What you type | What the agent does |
|---|---|
| `saipen SET` | Bootstraps the project with `.saipen/` memory and starts planning. |
| `saipen continue` | Wakes up, reads the state, and executes the very next action. |
| `saipen stop` | Forces the agent to checkpoint its work and hand control back to you. |
| `saipen status` | Reads `.saipen/BOARD.md` and tells you what's currently going on without doing work. |
| `saipen GOAL <text>` | Overrides current tasks and sets a new high-level plan. |
| `saipen clean` | Forces the agent to scrub the workspace, prune old done tickets, remove orphaned files, fix bad paths, and ensure everything is updated. |

## Adding Project Knowledge
Don't put project-specific rules in the global agent prompts. Put them in `.saipen/KNOWLEDGE/`!
- Create a file like `.saipen/KNOWLEDGE/ADR-001-database.md`.
- Tell the agent: "Always use PostgreSQL according to ADR-001".
- The agent will now obey this forever, and any future agent will too.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

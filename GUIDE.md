# Agent Session Protocol (ASP) Guide

Welcome to ASP! If you're a human developer looking to tame your AI agents, you're in the right place. 

## What is ASP?
When you have multiple agents (or even the same agent on different days) working on a codebase, they tend to forget decisions, step on each other's toes, or hallucinate capabilities. ASP acts like a tiny `.git` folder specifically for the AI agent's working memory.

## How it works
1. **Global Install:** You run `bootstrap/inject.ps1` (or `.sh`) once on your machine. This teaches Claude, Gemini, Aider, and Antigravity what ASP is.
2. **Project Init:** You open an agent in your project folder and type `asp SET` (or `asp INIT`). The agent reads its global rules and creates a `.asp/` directory in your current project.
3. **Working Memory:** From now on, the agent stores its current task, progress board, and logs in `.asp/STATE.md` and `.asp/BOARD.md`.
4. **Resuming:** You close your laptop, wait a week, open a completely different agent, and type `/asp continue`. The new agent reads the `.asp/` folder and resumes exactly where the old one left off.

## Commands you can type to the Agent
While agents interact with the file system directly, you just type normal chat messages to control them:

| What you type | What the agent does |
|---|---|
| `asp SET` | Bootstraps the project with `.asp/` memory and starts planning. |
| `asp continue` | Wakes up, reads the state, and executes the very next action. |
| `asp stop` | Forces the agent to checkpoint its work and hand control back to you. |
| `asp status` | Reads `.asp/BOARD.md` and tells you what's currently going on without doing work. |
| `asp GOAL <text>` | Overrides current tasks and sets a new high-level plan. |

## Adding Project Knowledge
Don't put project-specific rules in the global agent prompts. Put them in `.asp/KNOWLEDGE/`!
- Create a file like `.asp/KNOWLEDGE/ADR-001-database.md`.
- Tell the agent: "Always use PostgreSQL according to ADR-001".
- The agent will now obey this forever, and any future agent will too.

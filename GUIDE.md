# Agent Session Protocol (ASP) Guide

Welcome to ASP! If you're a human developer looking to tame your AI agents, you're in the right place. 

## What is ASP?
When you have multiple agents (or even the same agent on different days) working on a codebase, they tend to forget decisions, step on each other's toes, or hallucinate capabilities. ASP acts like a tiny `.git` folder specifically for the AI agent's working memory.

## How it works
1. You run the `inject.ps1` script. It creates a `.vacskill/` directory.
2. The agent reads `.vacskill/STATE.md` and `.vacskill/BOARD.md`.
3. The agent negotiates its capabilities against the protocol's demands.
4. The agent goes to work, saving its progress to `.vacskill/` atomically.
5. You can type `vacskill validate` at any time to ensure the agent hasn't corrupted its memory.

## Adding Extensions
Want your agent to run security checks during `VERIFY`? Add an extension:
- Place your security rules in `extensions/security/README.md`.
- When the agent enters the `VERIFY` phase, it will read those rules automatically.

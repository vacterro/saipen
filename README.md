# Agent Session Protocol (ASP)

**v7.1.2** | [Spec](SPEC.md) | [Guide](GUIDE.md) | plain markdown | zero deps | MIT

**One command. Zero amnesia.**

ASP is a stable, vendor-neutral continuation protocol. Its sole purpose is to guarantee that a completely cold agent with zero chat history can execute `/asp continue` and resume productive work within one minute, without asking the user to repeat context.

```text
User  ->  /asp continue
Agent ->  reads STATE ("What do I do right now?")
Agent ->  reads BOARD ("What task am I picking up?")
Agent ->  reads next_action (executes command)
Agent ->  Works.
```

Instead of writing a README instructing models "how to behave", you drop ASP into your project. Whether you use Claude today and Gemini tomorrow, both agents will instantly negotiate capabilities, follow the state machine, and execute the next action.

## Quick Start (5 minutes)

**1. Install Globally (Once per machine)**
Inject the protocol into your agents (Claude Code, Gemini, OpenCode, Aider, Antigravity):
```bash
git clone https://github.com/vacterro/asp
cd asp
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Start a Project**
Open an agent in your project folder and type:
> `asp SET` (or `asp INIT`)

No install? Paste one line to your agent:
> Read <clone>/asp/RFC.md + <clone>/asp/STYLE.md and follow them.

## Documentation
- **[SPEC.md](SPEC.md)**: The formal RFC specification. Read this if you are building extensions or agent frameworks.
- **[RFC.md](asp/RFC.md)**: The brutal, machine-readable ruleset that agents execute.
- **[GUIDE.md](GUIDE.md)**: The human tutorial with examples.
- **ELI5 Guides (Grandpa Style)**: [GUIDE_RU.md](GUIDE_RU.md) | [GUIDE_EN.md](GUIDE_EN.md)
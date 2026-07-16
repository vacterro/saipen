# Agent Session Protocol (ASP)

**v6.0.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | plain markdown | zero deps | MIT

*Formerly known as the Cross-Agent Project Memory Protocol (vacskill).*

**ASP** is a stable, vendor-neutral contract between your project and whatever AI agent is currently at the keyboard. It acts like `.git` for agent sessions.

Instead of writing a README instructing models "how to behave", you drop ASP into your project. The protocol ensures that whether you use Claude today and Gemini tomorrow, both agents will:
1. Negotiate capabilities (git, shell, files).
2. Follow a strict state machine (PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP).
3. Safely hand off state using atomic memory (`.vacskill/`).
4. Prove conformance via `vacskill validate`.

## Quick Start (5 minutes)

Run these three commands to inject the protocol into any project:
```bash
git clone https://github.com/vacterro/vacskill
cd vacskill
powershell -ExecutionPolicy Bypass -File .\inject.ps1     # Windows
bash inject.sh                                             # macOS / Linux
```

No install? Paste one line to your agent:
> Read <clone>/vacskill/PROTOCOL.md + <clone>/STYLE.md and follow them.

## Documentation
- **[SPEC.md](SPEC.md)**: The formal RFC specification. Read this if you are building extensions or agent frameworks.
- **[PROTOCOL.md](vacskill/PROTOCOL.md)**: The brutal, machine-readable ruleset that agents execute.
- **[GUIDE.md](GUIDE.md)**: The human tutorial with examples.
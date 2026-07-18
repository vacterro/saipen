<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**v7.2.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | plain markdown | zero deps | MIT

**One command. Zero amnesia.**

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](GUIDE_EN.md)

SAIPEN is a stable, vendor-neutral continuation protocol. Its sole purpose is to guarantee that a completely cold agent with zero chat history can execute `/saipen continue` and resume productive work within one minute, without asking the user to repeat context.

```text
User  ->  /saipen continue
Agent ->  reads STATE ("What do I do right now?")
Agent ->  reads BOARD ("What task am I picking up?")
Agent ->  reads next_action (executes command)
Agent ->  Works.
```

Instead of writing a README instructing models "how to behave", you drop SAIPEN into your project. Whether you use Claude today and Gemini tomorrow, both agents will instantly negotiate capabilities, follow the state machine, and execute the next action.

### Automated Continuous Evolution
When your project has no active tasks, just type `/saipen`. The protocol automatically triggers:
1. **HUNT**: A deep audit for bugs, failing tests, and dead code.
2. **ADD**: If no bugs remain, SAIPEN enters ADD and searches for the next obvious missing capability that naturally completes the product. The agent MUST prefer industry-standard functionality, UX completeness, and feature symmetry over novelty. Every addition MUST pass full verification before another HUNT begins. If the software is already mature, the agent gracefully stops.

It never spins its wheels. It just safely evolves your app step-by-step without you lifting a finger.

## Quick Start (5 minutes)

**1. Install Globally (Once per machine)**
Inject the protocol into your agents (Claude Code, Gemini, OpenCode, Aider, Antigravity):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Start a Project**
Open an agent in your project folder and type:
> `saipen SET` (or `saipen INIT`)

No install? Paste one line to your agent:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

## Documentation
- **[SPEC.md](SPEC.md)**: The formal RFC specification. Read this if you are building extensions or agent frameworks.
- **[RFC.md](saipen/RFC.md)**: The brutal, machine-readable ruleset that agents execute.
- **[GUIDE.md](GUIDE.md)**: The human tutorial with examples.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

# T-1625 -- does any project with its own launch need to adjust? (SRC-183)

The operator asked: once the host-integration mechanism is ready, where it
matters and IF it requires it, pass it on to each project that has its own
launch (SAITULS, AUDAPACK, wherever else) so their agents adjust on their side.

Measured 2026-10-06 on the operator's machine, after T-1624 and T-1634 shipped.
Answer: **no launcher needs a change.** The request's condition is not met, so
nothing was written into another project. The one real gap is SAIPEN's own and
is ticketed here (T-1635).

## What a launcher could do that the new mechanism punishes

| launcher behaviour | effect under HOST-INTEGRATION-01 |
|--------------------|----------------------------------|
| sets `SAIPEN_ADMISSION_TRANSPORT` | measured: the Claude hook strips it, nothing happens; presented to the engine directly it is `CAPABILITY_FORGED` in every mode |
| exports `SAIPEN_PROJECT_ROOT` naming another SAIPEN project | measured: `BINDING_CONFLICT`, blocks in every mode |
| exports `SAIPEN_PROJECT_ROOT` naming a directory that is no project | measured: the hook treats the session as ordinary chat even inside a project (T-1636) |
| calls `saipen authority mode\|status\|start\|stop` | subcommand gone (`host mode` replaced it); a helper that depends on it stops before launching |
| starts a renamed or copied `claude.exe` | never authenticated: works, UNVERIFIED for ever |
| wraps Claude in `claude1.ps1` / `saipen launch` | unnecessary; the native launch is the supported path |

## Every launch surface found, and what it does

Searched for those five behaviours in source files (tests, caches and vendored
copies excluded) of: `__SAITULS`, `_PY/_AUDAPACK`, `_PY/_FastPrompter`,
`_PY/_SAIMASTER`, `_PY/_SAISENT`, `_PY/_SAIPENVIEW`, `_PY/_SAIPLAN`,
`_AI_STUFF_AGENTIC/{__TERMISAI,_SAIRELAY,_SAICONT,_SAIPAL,_SAITALK,_ZAICODE}`.

| project | launch surface | what it does | needs a change |
|---------|----------------|--------------|----------------|
| SAITULS | `Scripts/consoles/CONSOLES.ps1`, `ACCOUNTS.ps1`, `consoles.json` (Explorer cascade and SAITULS itself) | resolves the bare command on PATH; `claude --dangerously-skip-permissions`; environment map per profile: `CLAUDE_CONFIG_DIR` (`claude-1` -> `~/.claude`, `claude-2` -> `~/.claude-account2`), `CODEX_HOME` for three Codex profiles; no `SAIPEN_*` variable, no `saipen` call | no |
| AUDAPACK | `audapack/cli_launchers.py` (`claude1`, `claude2`, `antigravity`, `zcode`) | `& claude.exe --dangerously-skip-permissions`, `CLAUDE_CONFIG_DIR` for the second profile; `saipen_manifest_gate.py` STRIPS the binding carriers from its own `saipen` subprocess, which is the right direction | no |
| ZAICODE | desktop app -> `pwsh` -> `claude.exe "<prompt>"` | the session this report was written in was started that way; it inherited `ZAICODE_*` and `SAIMAIL_WORKSPACE` only, no `SAIPEN_*` carrier, and the hook delivered protocol authority at session start | no |
| the others | none launches Claude Code | matches were data files (prompt history, caches, session inboxes), not code | no |

Live confirmation that the two operator launch paths in use today work with no
wrapper: the session started from the SAITULS console (`SAIPEN | Claude 1`,
`CLAUDE_CONFIG_DIR` set) and the one started from the ZAICODE desktop app were
both given admission by the installed hook; `saipen host doctor` reads claude
`HEALTHY_VERIFIED ... MECHANICAL`.

No live copy of the retired `claude1.ps1` exists outside
`.saipen/evidence/T-1624-host-integration/legacy/`.

## The gap that IS real, and whose it is

SAIPEN is installed into one Claude profile (`~/.claude`) and one Codex home
(`~/.codex`). The consoles above also start `claude-2` (`~/.claude-account2`),
`codex-2` (`~/.codex-account2`) and `codex-3-free` (`~/.codex-account3free`).
Checked: those directories carry no SAIPEN hook entry and no SAIPEN skill (the
two Codex configs only list this repository as a trusted project). Those
accounts run the plain host in a SAIPEN project: never blocked, and nothing is
admitted, delivered or gated either. That is not a launcher defect and no
launcher can cure it; it is T-1635 (and the deferred account-aware launch,
SRC-184).

## For whoever adds a launcher later

`LAUNCHER-CONTRACT.md` beside this file states the contract in one page.

# SAIPEN host integration changed (HOST-INTEGRATION-01) -- what a project that launches Claude Code must know

From: SAIPEN (`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`), tickets T-1624 and T-1634, 2026-10-06.
Source of the request: the operator, SRC-183 ("distribute it to each project that has its own launch").

## What changed in SAIPEN

Claude Code is started the ordinary way. No wrapper, no seat, no environment
variable and no prompt phrase is part of the supported path any more. On each
prompt the installed hook asks a local SAIPEN authority service, which the
first prompt starts by itself. When admission cannot be proven the prompt
proceeds marked `SAIPEN_ADMISSION_UNVERIFIED` (default policy
`DEGRADED_ALLOWED`); only a conflict blocks.

Operator commands: `saipen host doctor`, `saipen host repair`,
`saipen host mode [strict|degraded|default]`.

## What a launcher must NOT do

1. Do not set `SAIPEN_ADMISSION_TRANSPORT`. Measured: the Claude hook removes
   it from the engine's environment, so through the hook it does nothing; a
   direct `saipen admission establish` that presents one the authority did
   not issue is refused in every mode (`CAPABILITY_FORGED`). It is never a way
   to be admitted.
2. Do not export `SAIPEN_PROJECT_ROOT` / `SAIPEN_PROJECT_LINEAGE` for a
   console the user may `cd` out of. Measured: a carrier naming ANOTHER SAIPEN
   project than the one the session is in blocks the prompt in every mode
   (`BINDING_CONFLICT`: "SAIPEN_PROJECT_ROOT names X but the session
   directory belongs to Y"). A carrier naming a directory that is no SAIPEN
   project makes the hook treat the session as ordinary chat even inside a
   project (SAIPEN T-1636, open). Start the host IN the project directory;
   the hook finds the project from the session directory.
3. Do not call `saipen authority mode|status|start|stop`. Those subcommands
   are gone; `saipen authority` is `capture` only. The policy command is
   `saipen host mode`. The emergency helper `claude1.ps1` of 2026-10-06 is
   retired for that reason and is not needed.
4. Do not start Claude Code through a renamed or copied `claude.exe`. The
   authority proves the host by its image name and code signer; a copy runs,
   unverified, for ever.

## What a launcher may rely on

- Plain `claude` (or `claude.exe`) with any arguments, any working directory.
- `--dangerously-skip-permissions` and other host flags are untouched.
- An uninstall or a repair under a running session cannot lock that session
  out (bootstrap command spelling, inert stand-in).

## Known limit that concerns multi-account launchers (SAIPEN T-1635, open)

SAIPEN is installed into ONE Claude profile, `~/.claude`. A console started
with `CLAUDE_CONFIG_DIR` pointing elsewhere (measured on this machine:
`~/.claude-account2`) loads no SAIPEN hook and no SAIPEN skill: that account
runs plain Claude Code in a SAIPEN project -- it is never blocked, and nothing
is enforced or delivered either. Do not copy hook entries between profiles by
hand; the authority accepts only the hook of the profile it was installed in.
A launcher needs no change for this; T-1635 will make the doctor list every
profile and install per profile on request.

## Checked on 2026-10-06, nothing to change

- SAITULS `Scripts/consoles/CONSOLES.ps1`, `ACCOUNTS.ps1`: resolve the bare
  command on PATH, apply the profile's environment map (`CLAUDE_CONFIG_DIR`),
  set no `SAIPEN_*` variable, call no `saipen` subcommand.
- AUDAPACK `audapack/cli_launchers.py`: `claude1` / `claude2` start the
  installed `claude.exe` with `CLAUDE_CONFIG_DIR` for the second profile, set
  no `SAIPEN_*` variable.

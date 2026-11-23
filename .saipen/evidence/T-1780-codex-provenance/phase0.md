# T-1780 (SRC-251) Phase 0 -- feasibility facts, read-only, 2026-10-14

Measured on this machine by the SAIPEN seat; nothing was installed or changed.

## Installed host

- `codex --version`: `codex-cli 0.162.1` (`/c/nodejs/codex`).
- `CODEX_HOME` is not set in the SAIPEN seat's process; profiles on disk:
  `~/.codex`, `~/.codex-account2`, `~/.codex-account3free`.
- `~/.codex/hooks.json`: one `Stop` handler, the SAIPEN guard
  (`~/.codex/hooks/saipen-guard.py --host codex`, EXEC-RESPONSE-01 final gate).
  `~/.codex/config.toml` also declares `[[hooks.SessionStart]]` and
  `[[hooks.SubagentStart]]`, and `[hooks.state]` holds trust entries for them.
- `~/.codex-account2`: `config.toml` present, no `hooks.json`, no `hooks/`
  directory -- the profile the handoff names as active carries no SAIPEN hook.
- SAIPEN adapter registry (`extensions/adapters/registry.json`, id `codex`):
  `blocking_capability: true`, Stop transport only (T-1551); no
  UserPromptSubmit handler exists in `extensions/adapters/codex/saipen-guard.py`.

## Hook specification (https://learn.chatgpt.com/docs/hooks, read 2026-10-14)

- Events: SessionStart, SessionEnd, SubagentStart, SubagentStop, PreToolUse,
  PermissionRequest, PostToolUse, PreCompact, PostCompact, UserPromptSubmit,
  Stop, Interrupt.
- UserPromptSubmit payload: `session_id`, `transcript_path` (may be null),
  `cwd`, `hook_event_name`, `model`, `turn_id`, `prompt`, `permission_mode`.
  It can block (`"decision": "block"` with `reason`, or exit 2) and add context
  (`hookSpecificOutput.additionalContext`).
- Locations: `~/.codex/hooks.json`, `~/.codex/config.toml`, repo `.codex/`
  layers, plugin and managed (`requirements.toml`) hooks.
- Trust: non-managed hooks run only after the operator reviews and trusts
  them with `/hooks`; trust is bound to the hook's hash, so a new or changed
  hook is skipped until trusted again. Managed hooks are trusted by policy.
- Not stated by the page: which events fire under `codex exec`, and how
  `CODEX_HOME` selects the user layer. Both must be measured on the real host.

## What this means for SRC-251

- A UserPromptSubmit transport is supported by the host and carries the turn
  identity the receipt needs (`session_id`, `turn_id`, `prompt`).
- Installing it into `~/.codex-account2` is a host-configuration mutation
  (SRC-251 R002) and, being non-managed, it does nothing until the operator
  trusts it with `/hooks` -- a human action no agent can perform.
- The hook and the agent run as the same OS user; a file or variable the
  hook writes, the agent can write too. Provenance therefore has to come from
  the host-authority broker that proves the hook's own invocation from the OS
  (EXECUTION.md PROTOCOL-ADMISSION-01; T-1563: same-user signing stays
  disabled), not from the payload.
- Real acceptance (R010) needs a live Codex session on the trusted profile
  and an operator typing `cc`.

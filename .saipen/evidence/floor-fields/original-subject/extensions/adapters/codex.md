# Codex CLI adapter

- Skill route: `~/.codex/skills/saipen` junction; global
  `~/.codex/AGENTS.md` carries the saipen block (injector writes both).
- Sandbox limits -> declare capabilities honestly; degrade per protocol table.

## Stop-hook response gate (T-1551)

The supported Codex `Stop` event carries the outgoing final message
(`last_assistant_message`). The installed hook
(`~/.codex/hooks/saipen-guard.py`, configured in `~/.codex/hooks.json` by
`tools/install_host_guard.py`) forwards that text to the canonical
renderer/checker -- `tools/saipen.py response check --classify`, the SAME
authority OpenCode's text gate uses -- and maps its single verdict onto Codex
hook output:

- invalid operational response -> `{"decision": "block", "reason": ...}` with
  the correction route through `saipen response render --stdin` and
  `saipen response check --stdin --classify`;
- valid EXEC-RESPONSE-01 boundary and ordinary non-operational chat -> the
  stop completes untouched.

No response schema lives in the adapter: EXEC-RESPONSE-01's fields and rules
exist only in `saipen/EXECUTION.md` and `tools/saipen_engine/response_surface.py`.

Stop re-entry is deliberate and bounded. The first invalid stop of a turn
requests exactly ONE correction continuation. A stop that is already a
Stop-hook continuation (`stop_hook_active`) records the exact capability
boundary `CODEX_STOP_REENTRY_NO_FAIL_CLOSED` instead of requesting another
one: Codex continues by injecting a new user prompt with no finite correction
limit and cannot retract a rendered message, so a second continuation would be
an uncontrolled loop and terminal fail-closed correction is not claimed.
`CODEX_STOP_TEXT_CLASSIFICATION` is the second recorded boundary: the Stop
event carries no turn ingress or tool context, so a markerless reply on an
idle turn is indistinguishable from ordinary chat and passes.

Trust is an external host boundary. Codex skips non-managed hooks until the
operator reviews and trusts the hash-bound hook definition via `/hooks`;
installing the hook never marks it trusted. `declared_strength` stays
`ADVISORY` until a real trusted-host refused-effect proof is recorded.

Boot order: read `saipen/BOOT.md` first -- the cold-start kernel is all a
bare `saipen continue` needs. `saipen/BOOT/INDEX/CORE chain` is the constitution, reached
only when a rule question comes up. `saipen/STYLE.md` is a boot-read: apply it before any output.
Everything else: follow the BOOT/INDEX/CORE loading contract in `saipen/INDEX.md`.

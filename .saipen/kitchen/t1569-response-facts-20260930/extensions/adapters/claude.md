# Claude adapter (Claude Code / claude.ai)

T-1563: admission is UNAVAILABLE and fails closed. The same-user hook has no
signing authority. A separated host provider is required; init works while
same-turn admission is unavailable. See `protocol_admission`.

- Skill route: `~/.claude/skills/saipen/` carries SKILL.md -> BOOT.md. It is a
  COPY made by the injector (`saipen status --json` -> `distribution` says when
  it is stale), not a junction; the scheduled injector refuses to publish a
  dirty source tree, so commit before expecting hosts to see new protocol text.
- Final-response gate (T-1558): `python tools/install_host_guard.py claude`
  installs `~/.claude/hooks/saipen-guard.py` and merges two entries into the
  shared `~/.claude/settings.json` (backup once, every other hook kept):
  `UserPromptSubmit` injects the chat contract generated from STYLE.md, `Stop`
  checks the final message through `saipen response check --classify` and asks
  for one correction. The installer REPORTS, never removes, an operator hook
  that carries its own voice or language rule (`style_hook_conflicts`): remove
  that hook by hand, two sources of the rule is the defect.
- Plain chat without skills? Paste:
  `Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/BOOT.md + INDEX.md then CORE.md + STYLE.md on demand and follow them.`
- Write repo files with editor tools, never shell redirects -- BOM risk.
- Native todo lists mirror `.saipen/BOARD.md`, never replace it.

Everything else: follow the BOOT/INDEX/CORE loading contract in `saipen/INDEX.md`.

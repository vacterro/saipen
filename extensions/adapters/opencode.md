# OpenCode adapter

- Skill route: `~/.config/opencode/skills/saipen/` junction (injector) --
  SKILL.md -> RFC.md automatically.
- Global `~/.config/opencode/AGENTS.md` also carries the saipen block.

Boot order: read `saipen/BOOT.md` first -- the cold-start kernel is all a
bare `saipen continue` needs. `saipen/BOOT/INDEX/CORE chain` is the constitution, reached
only when a rule question comes up. `saipen/STYLE.md` is a boot-read: apply it before any output.
Everything else: follow the BOOT/INDEX/CORE loading contract in `saipen/INDEX.md`.

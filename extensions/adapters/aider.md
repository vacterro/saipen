# Aider adapter

- `~/.aider.conf.yml` `read:` auto-loads RFC.md every session
  (injector writes it).
- Aider auto-commits: keep its commits, but SHIP versioning/tagging still
  follows the protocol, not aider defaults.

Boot order: read `saipen/BOOT.md` first -- the cold-start kernel is all a
bare `saipen continue` needs. `saipen/RFC.md` is the constitution, reached
only when a rule question comes up; `saipen/STYLE.md` loads alongside it.
Everything else: follow `saipen/RFC.md`.

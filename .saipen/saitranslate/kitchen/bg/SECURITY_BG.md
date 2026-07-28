<!-- TRANSLATED TO BG -->
# Security Policy

## Scope

SAIPEN is a specification plus a small set of local install/export
scripts (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). It does not run a server, does not collect
telemetry, and does not transmit any data anywhere. Everything the
scripts do is local filesystem writes to files you already control
(your own `~/.claude`, `~/.gemini`, project `.saipen/`, etc.).

Two different levels of care apply there, and it's worth being exact
rather than claiming blanket safety:

- **Your own config files** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) are only ever edited by adding or removing a
  delimited `SAIPEN:BEGIN`/`END` block, and the original is copied to
  `<file>.bak` before the first modification. Uninstall additionally
  writes `<file>.uninstalled.bak` before stripping.
- **The skill directories** the injector creates (`~/.claude/skills/saipen`
  and friends) are SAIPEN-owned copies and are **not** backed up: install
  overwrites them wholesale and uninstall removes them recursively. That is
  intentional -- they hold nothing but copies of this repo's own files --
  but if you hand-edit a local skill copy, those edits are lost on the next
  `inject`/`uninstall`. Keep customizations in your own config block or a
  fork, not inside the copied skill folder.

The two things actually worth a security report:
1. A bootstrap script doing something to your filesystem or git history
   beyond what its own comments/README describe.
2. The protocol's own secrets-hygiene rule (RFC.md § 1.1 -- never write
   API keys, tokens, passwords into `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/
   `recovery/`/`logs/`) having a real gap that would cause an
   agent following SAIPEN to leak a secret into a committed file. The last two
   are the subtle ones: Recovery copies a corrupt `STATE.md` verbatim into
   `.saipen/recovery/`, and LOG sealing moves lines verbatim into
   `.saipen/logs/`, so anything that reached the original is archived by
   machinery whose whole job is not to alter content.

## Supported Versions

Only the latest tagged release on `main` is supported. This is a
protocol specification, not a long-lived service -- there is no LTS
branch.

## Reporting a Vulnerability

Open a GitHub issue. If the report involves a real, currently-exploitable
problem (not a hypothetical), mark it as a private/security advisory via
this repository's **Security** tab ("Report a vulnerability") instead of
a public issue, so it isn't publicly visible before a fix ships.

Include: which script or RFC rule, the concrete scenario, and what
actually happens vs. what should happen. Same evidence standard as any
other bug report (see `CONTRIBUTING.md`).

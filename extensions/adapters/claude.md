# Claude adapter (Claude Code / claude.ai)

Start Claude Code the way you always do. Nothing else is required: no wrapper,
no seat, no environment variable, no prompt phrase.

HOST-INTEGRATION-01 (T-1624). The hook mints nothing (T-1563 stands). On each
prompt it asks the SAIPEN authority service, which runs as its own process and
admits exactly one caller: Claude Code's own hook invocation, proven from the
operating system (`saipen_engine/host_authority_identity.py`). The first prompt
that needs the service starts it. What happens when admission cannot be proven
is decided by one table (`saipen_engine/host_taxonomy.py`), never by a message:

- a gap -- the service is absent or another generation, the runtime behind the
  hook cannot be run, the hook is stale -- lets the prompt through, marked
  `SAIPEN_ADMISSION_UNVERIFIED`, under the default policy `DEGRADED_ALLOWED`;
- a conflict -- a forged, replayed or transplanted capability, a project
  binding that contradicts the project -- blocks under every policy;
- `STRICT` is the operator's opt-in: every failure blocks, with one action.

Operator surface. Ordinary work needs none of it:

    saipen host doctor                           read-only state of every host
    saipen host repair                           reinstall what is stale or broken
    saipen host mode [strict|degraded|default]   show or set the policy

`saipen --agent <seat> launch claude -- [arguments]` is an optional diagnostic
launcher, never the routine path.

Known limit, recorded rather than hidden: the anchor is what the operating
system reports about live processes -- the host image and its code signer
(`protocol_admission.host_authority` in `REGISTRY.json`), shells started with
exactly the hook command, and the shipped hook bytes. It is not a boundary
against code injected into the host process, a same-user process that rewrites
the installed hook or its settings entry, or a forged parent process. No
same-user local scheme defends those, and none is claimed.

- Skill route: `~/.claude/skills/saipen/` carries SKILL.md -> BOOT.md. It is a
  COPY made by the injector (`saipen status --json` -> `distribution` says when
  it is stale), not a junction; the scheduled injector refuses to publish a
  dirty source tree, so commit before expecting hosts to see new protocol text.
- Hook: `python tools/install_host_guard.py claude` installs
  `~/.claude/hooks/saipen-guard.py` and merges its entries (`SessionStart`,
  `UserPromptSubmit`, `PostToolUse` on Bash, `PostModelSwitch`, `Stop`) into
  the shared `~/.claude/settings.json` (backup once, every other hook kept).
  The new artifact is staged and self-tested before it replaces the active
  one; a failed self-test activates nothing, and `--rollback` puts the previous
  generation back. The hook command names the INSTALLED runtime, never a
  source checkout, and starts the hook through a bootstrap that does nothing
  when the hook file is absent: an interpreter handed a missing script exits
  2, and Claude Code reads that as a hook that blocks every prompt. A session
  keeps the command it loaded at start, so an uninstall while Claude Code is
  running leaves an inert stand-in where the hook stood; it goes with the
  next install, or the next uninstall once no host is alive.
  The installer REPORTS, never removes, an operator hook that
  carries its own voice or language rule (`style_hook_conflicts`): remove that
  hook by hand, two sources of the rule is the defect.
- Final-response gate (T-1558): `Stop` checks the final message through
  `saipen response check --classify` and asks for one correction. It is
  post-render: it cannot retract text that was already shown. A refused reply
  is handed to `saipen response preserve` before the correction is requested,
  so it is kept byte for byte under `.saipen/evidence/response/` with its
  overflow account beside it (T-1657).
- Plain chat without skills? Paste:
  `Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/BOOT.md + INDEX.md then CORE.md + STYLE.md on demand and follow them.`
- Write repo files with editor tools, never shell redirects -- BOM risk.
- Native todo lists mirror `.saipen/BOARD.md`, never replace it.

Everything else: follow the BOOT/INDEX/CORE loading contract in `saipen/INDEX.md`.

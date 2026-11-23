# T-1624 acceptance on the real host (2026-10-06)

Host: Claude Code 2.1.291 (`C:\Users\vac34\.local\bin\claude.exe`), Windows 10
19045, Python 3.11.9, Git Bash. Model for the probes: haiku. Every run below is
a real `claude -p` process; nothing on the proving side is simulated.

## 1. A measured lockout class found during acceptance

A hook command whose script file is missing BLOCKS every prompt. Probe: a
disposable directory whose `.claude/settings.local.json` holds one
`UserPromptSubmit` hook, `<python> C:/nonexistent-saipen-probe/hook.py`.

    UserPromptSubmit operation blocked by hook:
    [...python.exe C:/nonexistent-saipen-probe/hook.py]: ...python.exe: can't open
    file 'C:\\nonexistent-saipen-probe\\hook.py': [Errno 2] No such file or directory

The interpreter exits 2 for a missing script and the host reads 2 as "block".
A session keeps the hook command it loaded at start, so an uninstall (or any
loss of the file) under a running session was a lockout of that session.
Repair in this ticket: every hook command starts its artifact through
`HOOK_BOOTSTRAP` (no-op when the file is gone), and an uninstall under a live
host leaves `tools/retired_host_hook.py` for sessions holding an older command.
Regression: `InstallerTests.test_a_missing_hook_file_cannot_block_the_host`
(the pre-fix spelling exits 2 on the same oracle),
`test_uninstall_under_a_live_host_leaves_an_inert_stand_in`,
`DoctorTests.test_a_retired_hook_file_is_not_an_installation`.

## 2. Isolated real acceptance (no change to the operator's global config)

Setup: hook installed by `tools/install_host_guard.py claude --home <iso home>`
(stage, self-test, activate); a disposable SAIPEN project whose
`.claude/settings.local.json` carries the installed hook entries plus the
diagnostic flags `--home <iso home> --runtime <iso runtime>`; the shipped
service entry (`tools/authority_service.py serve`, source generation
`svc-5afd0219ef2b01af55ea006d`) on that isolated runtime root with the SHIPPED
policy (no policy override: host image AND code signer required).

| step | observed |
|------|----------|
| prompt, instruction block absent | prompt reaches the model, reply returned; health `DEGRADED` / `ACTIVATION_BLOCK_ABSENT`; service `authenticated_requests: 2, refused_requests: 0` |
| prompt, instruction block present | health `ADMITTED`, 218 ms; service `last_client.host_image: claude.exe`, `host_signer: Anthropic, PBC`, transport `named-pipe`; ledger record written |
| next session (new `claude -p`) | `ADMITTED`, 189 ms, no ritual |
| service stopped | prompt reaches the model; health `DEGRADED` / `AUTHORITY_UNREACHABLE`, 525 ms |
| service started again | `ADMITTED`, 184 ms, automatically |
| tool call (`echo TOOL-OK-7391` through the Bash tool) | output `TOOL-OK-7391`; health `ADMITTED`, 195 ms |
| policy `strict`, service stopped | `UserPromptSubmit operation blocked by hook: SAIPEN PROTOCOL ADMISSION REFUSED -- The SAIPEN authority service did not answer. [AUTHORITY_UNREACHABLE] ... Do this: saipen host repair`; health `REFUSED` |

The observed chain is the one the proof names: `claude.exe` -> `git/bin/bash.exe
-c <command>` -> `git/usr/bin/bash.exe -c <command>` -> hook (bootstrap
spelling) -> engine. The global hook of the older installed generation also
ran for these prompts (it cannot be switched off without touching the global
configuration) and talked to its own older service; the two are independent.

One wording defect surfaced and was repaired: with nothing answering on an
explicit endpoint the refusal said `state answered`; it now says
`state unanswered` (`IncidentControls.test_control_a_...`).

## 3. A machine fact repaired on the way

The operator's global OpenCode install was broken since 2026-10-06 05:15 local:
`C:\nodejs\node_modules\opencode-ai\bin\opencode.exe` was the 479-byte stub of
an npm update whose postinstall never ran (the old package directory was left
as `.opencode-ai-HMw9iBDj`). Six real-host smoke tests of the declared family
were red for that reason alone. Repaired with the package's own documented
step (`node postinstall.mjs`, no network: the 1.18.34 platform binary was
already unpacked); `opencode --version` answers `1.18.34`, and
`test_opencode_bound_launch_smoke` (5) and `test_opencode_host_smoke` (10) are
green. The stub is kept at
`%USERPROFILE%\.saipen\rollback\20261006-opencode-stub\opencode.exe.stub`.
What interrupted that update was not established.

## 4. Global restore on this machine (after the isolated acceptance passed)

`bootstrap\inject.ps1 -AdapterId claude` from the source checkout: skill copied,
provenance verified, hook staged, self-tested and activated (the replaced
generation kept as `saipen-guard.py.previous`), the older-generation authority
service retired by the installer. Rollback kit unchanged:
`%USERPROFILE%\.saipen\rollback\20261006-pre-t1624\restore.ps1`.

Every prompt below is a real `claude -p` in a disposable SAIPEN project with
only the GLOBAL hooks (no project-level hook file).

| step | observed |
|------|----------|
| `saipen host doctor` right after install | claude `INSTALLED_UNVERIFIED`, runtime current, hook current, admission `MECHANICAL_UNOBSERVED`; authority idle |
| first prompt, with a tool call | output `GLOBAL-OK-5521`; health `ADMITTED`, 270 ms; the hook started the authority service by itself (`running pid 25696 current generation`); doctor `HEALTHY_VERIFIED`, admission `MECHANICAL` |
| authority service stopped, next prompt (a new session) | `RESTART-OK`; health `ADMITTED`, 285 ms; service running again as pid 18608 with no operator action |
| reinstall | `already-current`, `settings.json` byte-identical |
| hook uninstall (`install_host_guard.py claude --uninstall`) while Claude Code sessions were running | 5 entries removed, artifact replaced by the retired stand-in, service retired; next prompt `PLAIN-OK` with no SAIPEN hook |
| `saipen host repair --host claude` | `repair install:claude: ok INSTALLED`, `repair authority:start: ok AUTHORITY_STARTED`, `repair complete` |
| prompt after repair | `REINSTALL-OK`; health `ADMITTED`, 283 ms; doctor `HEALTHY_VERIFIED`, admission `MECHANICAL` |

Operator configuration across uninstall + reinstall: top-level keys and all
non-hook content identical; the 13 hook entries are the same set (the
operator's own hooks included); only the order of two event keys inside
`hooks` moved, because an event that became empty was removed and re-added.

Not executed on the live profile, deliberately: the all-hosts
`bootstrap\uninstall.ps1`. It also removes every other host's integration and
the scheduled task, which this ticket has no reason to disturb. That path is
proven on sandbox profiles: `test_public_install_lifecycle` (PowerShell and
bash, install -> use -> uninstall -> reinstall -> uninstall) and the
Python-less native path on Windows PowerShell 5.1 and PowerShell 7
(`InstallerTests.test_the_emergency_uninstall_needs_no_python*`).

The other installed hosts (OpenCode, Codex, ZAICODE, ZCode, Gemini, CodeBuddy,
FreeBuff) read `STALE_RUNTIME` in the doctor view: their installed runtime is
the previous generation. None of them can block a Claude prompt; one
`saipen host repair` brings them to this generation.

## 5. The final generation, after the review repair (2026-10-06 13:12-13:21Z)

Session `saipen-27`. Review pass 1 (`REVIEW.md` here) found that the hook
activated in section 4 still blocked a prompt with an empty reason when its
engine answered with no admission verdict, and exited 2 on a command line of
another generation. The repair changed the hook and the installer's self-test,
so the generation this ticket ships is NOT the one sections 2 and 4 exercised.
It was put on the machine and exercised again. Claude Code 2.1.291, model
haiku, every prompt a real `claude -p` in a disposable SAIPEN project made by
`saipen init`, GLOBAL hooks only.

| step | observed |
|------|----------|
| baseline, generation of section 4 still installed | reply names `BEFORE-OK-4419` (Bash tool ran); health `ADMITTED`, 347 ms |
| `saipen host repair --host claude` | `repair install:claude: ok INSTALLED`, `authority:stop: ok`, `authority:start: ok AUTHORITY_STARTED`, `repair complete`; rc 0 |
| installed hook against the source | content sha256 `94c03df84a460b84...` on both; `settings.json` byte-identical before and after (`7483ea3eee3e0db0...`); the replaced generation kept as `saipen-guard.py.previous` |
| first prompt on the new generation, with a tool call | reply names `AFTER-OK-7731`; health `ADMITTED`, 279 ms |
| authority service stopped (`authority_service.py stop` -> `BROKER_SHUTDOWN`, then `BROKER_UNREACHABLE`), next prompt in a new session | reply names `RESTART-OK-7732`; health `ADMITTED`, 282 ms; the service answers again with no operator action |
| `authority_service.py status` from a tool shell under Claude Code | `BROKER_CLIENT_NOT_AUTHENTICATED`: a command the model runs is not the hook, on the live service |
| `saipen host doctor` | claude `HEALTHY_VERIFIED`, runtime current, hook current, admission `MECHANICAL` |

The two inputs of review pass 1, against the INSTALLED bytes and the installed
runtime, in an isolated `--home` so the operator's health record and policy
are not touched:

| input | installed generation | `saipen-guard.py.previous` |
|-------|----------------------|----------------------------|
| bootstrap spelling, an unknown argument, `--saipen-root` with no value | exit 0, `SAIPEN is running in degraded mode ... (hook command line names no --saipen-root) ... ENGINE_UNREACHABLE` | exit 2, `error: unrecognized arguments` (a host reads 2 as block) |
| `UserPromptSubmit` with no `session_id` | exit 0, `... (runtime answer is not an admission verdict: --session is required) ...` | `{"decision": "block", "reason": ""}` |

The other installed hosts still read `STALE_RUNTIME` at this point; they are
brought to this generation by the all-hosts `saipen host repair` after the
ticket closes (recorded in the LOG, not here).

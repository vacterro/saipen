# T-1747 / SRC-241 -- "degraded mode" in the Claude 2 session started from AUDAPACK

## 1. What the screenshot showed, and why (measured)

```
SessionStart:startup says: SAIPEN is running in degraded mode. ... Not verified because:
AUTHORITY_UNREACHABLE/HOOK_ARTIFACT_MISMATCH: The SAIPEN authority service did not answer.;
ACTIVATION_BLOCK_ABSENT: ...; HOOK_STALE: ...  To restore verification run: saipen host repair
```

- "Claude 2" is the Claude Code profile `C:\Users\vac34\.claude-account2`. AUDAPACK
  starts it as `$env:CLAUDE_CONFIG_DIR = '<profile>'; & claude.exe` (process chain read
  from the running session: `claude.exe <- powershell.exe <- pythonw.exe AUDAPACK.pyw`).
- That profile had never been installed: no `CLAUDE.md`, no `hooks/`, no `skills/saipen`.
  Its `settings.json` (2026-10-08 21:23) carried five SAIPEN hook entries that ran the
  hook of the DEFAULT profile (`C:/Users/vac34/.claude/hooks/saipen-guard.py
  --saipen-root C:/Users/vac34/.claude/skills/saipen`). Copy:
  `account2-settings.before.json`.
- The identity check named the cause exactly -- HOOK_ARTIFACT_MISMATCH, "the hook
  belongs to another configuration profile than the host". No authority service is
  started for a caller that is not the host's own hook, so the failure was filed as
  AUTHORITY_UNREACHABLE and the notice printed the table sentence of THAT code.
- The printed remedy, bare `saipen host repair`, repairs the default installation of
  every host and leaves a second profile untouched (`doctor-before.json`: the profile
  is UNINSTALLED, next action `saipen host repair --host claude --profile "..."`).

## 2. What was repaired on this machine

- `saipen host repair --host claude --profile "C:\Users\vac34\.claude-account2"`:
  runtime, hook, six hook entries and a `CLAUDE.md` with the activation block now live
  in the profile itself (`repair-account2.json`, `repair-account2-final.json`).
- `saipen host repair`: every installed host is on the current generation
  (`repair-all-final.json`, `doctor-after.json`).
- `saipen host doctor` now: default profile HEALTHY_VERIFIED; second profile
  INSTALLED_UNVERIFIED, "no prompt has been observed through this installation yet".

## 3. What was wrong in the engine, and is fixed

| # | Defect | Fix |
|---|--------|-----|
| 1 | The notice and the doctor said "The SAIPEN authority service did not answer" for a refusal about WHO asked | one sentence per identity step (`host_taxonomy.step_summary`), used by `degraded_notice` and `host_integration.derive_state` |
| 2 | The notice named a repair command that does not repair the profile the session runs | `protocol_admission.scoped_repair`: `saipen host repair --host claude --profile "<profile>"` outside the default profile; the 900-character cap is spent on the explanation, never on the command |
| 3 | `saipen host repair --dry-run` ran a full repair: `host doctor/repair/mode`, `host machine`, `host launcher` and the runtime install flags dispatch before the flag was consulted | `host repair --dry-run` answers the doctor report as `DRY_RUN_PLAN`; `host mode <value>`, `host machine install/remove`, `host launcher install/remove`, `runtime --prelaunch/--bootstrap` refuse the flag and write nothing |
| 4 | `saipen runtime --prelaunch --adapter claude` (the step that keeps an installed host fresh before it starts) measured the default profile while the installer, reading `CLAUDE_CONFIG_DIR` itself, wrote into the profile named there | `runtime_bootstrap._launch_profile`: measurement and write name one profile, in `prelaunch` and `run_bootstrap` |

Not fixed here, filed: the activation block prints `<clone>/saipen/bin/saipen`, a path
that does not exist in a source clone (T-1753).

## 4. Evidence

- `tools/test_t1747_degraded_profile.py`: 22 cases; every installer, repair and mode
  writer is a recorder, so neither half of the pair can touch the machine.
- Engine-measured regression pair, one verifier: see `regression-result.json`.
  Pre-fix subject: red on 17 cases; the five that stay green are guards (a service
  that really did not answer is still said so, by the notice and by the doctor; a
  repair without the flag still repairs; `host mode` without a value stays a view;
  no carrier keeps the default profile).
- 14 mutation controls, each run twice, every one turns its named case red
  (`mutations.json`, `mutate1747.py`).
- Neighbours: host integration, admission, launch, runtime bootstrap, profile carrier
  and the whole-source contract modules, all green before each family run.
- Declared core-unit family: PASS records after the first, second and third pass;
  the record of the final tree is cited in the ticket's VERIFY line.
- Real surface: `saipen host repair --dry-run --json` after the fix answers
  `DRY_RUN_PLAN`, lists nine installations it would repair and carries no `steps`
  (`repair-dry-run-after-fix.json`); before the fix the same command printed eleven
  executed steps (`repair-dry-run.json`). `saipen runtime --prelaunch --adapter claude
  --no-resync --json` with the carrier naming the second profile now reports
  `surface: C:\Users\vac34\.claude-account2\skills\saipen`.

## 5. What is not proven

No real Claude 2 prompt has gone through the repaired profile: only the operator can
start that session. Expected: no degraded line at start, and `saipen host doctor`
reads HEALTHY_VERIFIED for `.claude-account2` afterwards.

## 6. A dependency outside this repository

AUDAPACK starts `claude.exe` directly. Every change of the SAIPEN source makes the
installed runtime of every profile older than its source, and a host started then
opens degraded until it is resynced. The supported step for that is

```
saipen runtime --prelaunch --adapter claude --json
```

run after `CLAUDE_CONFIG_DIR` is set and before the host starts (exit 0 with
`RUNTIME_CURRENT` or `RUNTIME_RESYNCED` means start; it writes nothing when the
runtime is current). Since this Work it follows the profile. Adding that line to
AUDAPACK's launch command is AUDAPACK's own change; nothing was edited there.

## 7. Side effects of this session the operator should know

- At 18:58 `saipen host repair --dry-run` executed a real repair of every default
  host (defect 3). It did what the notice asks for and nothing else; it was not a plan.
- At 18:59 a hand-run copy of the installed second-profile hook wrote a DEGRADED
  health record for that profile (a probe of mine, not a session). It made the doctor
  call the profile unavailable; removed at 21:17, copy kept as
  `probe-health-record-removed.json`.
- The installer kept its own backup of the profile's previous settings:
  `C:\Users\vac34\.claude-account2\settings.json.70b51160f43eaf37.bak`.

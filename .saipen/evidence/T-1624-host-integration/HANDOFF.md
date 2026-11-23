# T-1624 handoff -- state at 2026-10-06 15:45 local (12:45Z)

Written by the Claude Code session that ran 10:30-15:45 local (peer name
`saipen-e5`). A second session (`saipen-27`, started 15:30 by the operator's
`/goal cc all`) is working the same seat. From this point `saipen-27` is the
ONLY writer of the tree; `saipen-e5` stops. Nothing below is a claim to trust:
every item names where to re-derive it.

Source: SRC-182. Queued: T-1625 (SRC-183), T-1626 (SRC-184, a FUTURE target:
`saipen future add`, not an implementation), T-1627 (SRC-185,
OPERATOR-QUESTION-01), T-1628 and T-1629 (filed in this session, see below).
T-1620 is parked on T-1624. T-1623 is absorbed by this ticket.

## Live machine state (changed in this session)

- Claude Code integration is GLOBALLY ACTIVE on the working-tree generation as
  of 11:48: `bootstrap\inject.ps1 -AdapterId claude`, then the real lifecycle
  (`ACCEPTANCE.md` sections 2 and 4). `saipen host doctor` read
  `claude HEALTHY_VERIFIED ... MECHANICAL` at 11:52. Tree edits made after
  11:48 (listed below) make the installed runtime read `STALE_RUNTIME` again:
  run `saipen host repair` ONCE after the final ship, for every host.
- Hook entries in `~/.claude/settings.json` are the bootstrap spelling. A
  Claude Code session started before 11:48 still holds the old spelling; both
  are accepted by the proof and by the uninstaller.
- Authority service: started by the hook from `~/.claude/skills/saipen`,
  policy file `degraded` (operator).
- Rollback kit unchanged: `%USERPROFILE%\.saipen\rollback\20261006-pre-t1624\restore.ps1`.
- OpenCode global install repaired (`ACCEPTANCE.md` section 3).

## Done in the tree by this session (uncommitted; re-derive with `git diff`)

1. `saipen/COMMAND_EFFECTS.json`: `host doctor|repair|mode` effect classes
   (`DoctorTests.test_the_operator_commands_carry_a_declared_effect_class`).
2. Service start bound to the hook's own shape, not "a host is above me":
   `host_authority_client.hook_invocation`, `ensure(host=, home=)`,
   `host_authority_broker.hook_artifacts`. Red-then-green on real processes:
   `ClaudeHostPathTests.test_a_tool_call_under_the_host_never_starts_the_service`.
3. Hermeticity: hostile child tests name the world's endpoint
   (`test_protocol_admission._hostile_python`), `test_claude_stop_hook` harness
   (full option namespace, `--runtime`, SRC-182 contract for an unreachable
   engine), `test_hermetic_env.isolated_authority_runtime`, and the endpoint
   isolation moved into the reference-counted registry
   (`restore_authority_endpoint`; this is what turned the two
   `test_module_duplication_guard.CooperatingHarnessStateTests` cases green).
4. `bootstrap/uninstall.ps1`: works with no Python (native ownership rules,
   native hook-config surgery, exact byte restore from the installer backup).
   Tested on Windows PowerShell 5.1 and PowerShell 7.
5. Lockout by absence: `HOOK_BOOTSTRAP` command spelling
   (`host_authority_identity`, `install_host_guard.hook_argv`), retired
   stand-in on uninstall under a live host (`tools/retired_host_hook.py`,
   `install_host_guard.host_alive`, `machine_profile`), doctor treats the
   stand-in as not installed. Measured on the real host first
   (`ACCEPTANCE.md` section 1).
6. `host_authority_client.attempt_admission`: `state unanswered` instead of
   `state answered` when nothing answered on an explicit endpoint.
7. Docs: `extensions/adapters/claude.md` rewritten, `saipen/RUNTIME.md`
   HOST-INTEGRATION-01 section, `saipen/COMMANDS.md` rows, `saipen/EXECUTION.md`
   admission paragraph. `human_markdown_total` tripwire re-derived to 327 KiB
   (`T-1624-budget-rederivation.md`, 185 bytes of slack left).
8. Family stdin (found 15:30, fixed 15:34): `test_runner._run_family` starts
   the family with `stdin=DEVNULL`; `core_unit._git_head` has no shared stdin
   and a timeout. Red-then-green:
   `test_t1442_family_env...test_a_family_never_shares_its_launchers_stdin`.

## The 5400 s core-unit record is this session's, and why it happened

Record `c9a98f598cc8821c-20261006T102333Z.json` (LOG E-12501, FAIL, `ran:None`)
is the evidence run this session started at 11:51. It did not test a bad tree.
Proven mechanism: the family inherited its launcher's stdin; a real
`opencode.exe run` started by a smoke test at 11:55:53 never exited and held a
blocking read on that shared handle; every later child that inherited the
handle hung in its own startup (0.00 s CPU, one thread in `Wait/Executive`,
five such children between 11:56:00 and 13:23:33, the last one the evidence
process's own `git rev-parse HEAD`). Causal test at 15:32: killing that ONE
`opencode.exe` released both remaining stuck children within three seconds.
A probe that spawned 37 000 children with `stdin=DEVNULL` in the same window
stalled zero times. Why that `opencode run` never exited is NOT established.
Still open: a smoke test's timeout kills only the `opencode.cmd` shim, so the
real host process is orphaned (not filed yet; file it).

Earlier records of this session: `ce2977fd` (3 new red), `7ccf992c` (5),
`91250d82` (2, both the harness-state cases fixed in item 3). All three were
taken while the tree was being edited, so none is cited.

## NOT done for T-1624

1. A cited `CORE-UNIT-EVIDENCE PASS` on the final tree. `saipen-27` started
   one at 15:34:46; this session's last tree edit landed about then and a red
   control swapped `test_runner.py` for ~20 s at 15:35, so expect that run to
   re-snapshot once.
2. VERIFY / REVIEW / SHIP. Precedent of the last four tickets (LOG E-12452 to
   E-12478): verify PASS checkpoint, CORE-UNIT-EVIDENCE, `saipen scope`, then
   `ticket done` from SHIP. `main` is 33 commits ahead of `origin/main` and
   nothing was pushed: T-1607 records "no GitHub push without a fresh operator
   instruction".
3. Close T-1623 `inherited_verified`, unblock T-1620.
4. `saipen host repair` for all hosts after the final ship.

## Filed here

- T-1628: OpenCode tool gate fails closed on a gap (parity with
  HOST-INTEGRATION-01).
- T-1629: README "no daemon" wording versus the on-demand authority helper.

## T-1627 (OPERATOR-QUESTION-01): drafts, not in the tree

`.saipen/kitchen/T-1627-drafts/` holds a complete engine module, a CLI
function, the Claude hook handler and a test module, with `README.md` naming
the design decisions and what has and has not run. Use or discard.

## Traps

- Do not edit the tree outside `.saipen/` while `core_unit.py evidence` runs:
  it re-snapshots three times and then refuses the citation.
- Bash heredocs eat backslashes. Write patch scripts and JSON with the Write
  tool.
- A child process a test starts must get `stdin=DEVNULL` or its own pipe.

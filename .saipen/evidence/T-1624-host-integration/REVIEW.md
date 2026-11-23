# T-1624 late review passes (2026-10-06, session `saipen-27`)

SRC-182 asks for review passes after functional closure, continued until three
in a row find no new P0/P1 on the Claude normal-use path. Pass 1 found three.
They were fixed, and the count restarted.

## Pass 1 -- the hook artifact, read and probed: 3 findings, all fixed

Subject before: `extensions/adapters/claude/saipen-guard.py`
sha256 `f85ab88301254ab39eae361681b8ea57f80df191c0ecc52f6fa2a43561019fad`.

1. **An engine answer that is no admission verdict blocked the prompt with an
   empty reason, under the default policy.** `handle_prompt` read
   `verdict.get("permitted")`; the engine refuses its own command line in its
   general schema (`{"ok": false, "code": ..., "detail": ...}`), which carries
   no `permitted`. Reproduced on the REAL engine, not a stand-in: a
   `UserPromptSubmit` event with no `session_id` makes `admission establish`
   answer `VALIDATION_FAILED "--session is required"`, and the hook printed
   `{"decision": "block", "reason": ""}`. A runtime of another generation
   answering in another schema took the same path.
2. **A command line the artifact cannot read exited with status 2.** argparse
   reports an unknown argument, a missing required one or an invalid choice by
   exiting 2, and Claude Code reads status 2 from a hook as "block this event".
   A host snapshots hook commands at session start (ACCEPTANCE.md section 1),
   so the command of one generation can meet the artifact of another.
3. **A refusal could reach the operator with no text.** `reason` was
   `str(verdict.get("diagnostic") or "")`.

Repair (same file, plus the installer gate):

- an answer without a boolean `permitted` is `ENGINE_UNREACHABLE` and the
  operator's policy decides it -- DEGRADED_ALLOWED proceeds marked
  `SAIPEN_ADMISSION_UNVERIFIED`, STRICT blocks with the one action;
- `read_command_line` never exits: every value is optional to the parser and
  checked afterwards, an unknown argument is read past (counted in the health
  record as `unread_arguments`), and what argparse still refuses is raised as
  `CommandLineFault`. A command line that names no usable runtime is decided
  by the same policy rule; outside a SAIPEN project it does nothing;
- a refusal without a diagnostic names its code and `saipen host doctor`;
- `install_host_guard.self_test` gained steps 4 (`engine-off-schema`) and 5
  (`foreign-command-line`), so a hook with either defect is never activated.

Regression pair, one verifier, two subjects (LOG E-12503 / E-12504):

    REGRESSION-EVIDENCE FAIL verifier:7e7eb72e7be1564f subject:0116bbcf132c1c8e   5 tests, 17 failures
    REGRESSION-EVIDENCE PASS verifier:7e7eb72e7be1564f subject:00f9ae1f9dd29d36   5 tests OK

The runner is `regression_pair_runner.py.txt` here: the verifier identity is
the command plus `tools/test_t1624_host_integration.py`, the subject is the
guard plus `tools/install_host_guard.py`. The red controls for the two new
self-test steps are mutations of the repaired hook inside
`InstallerTests.test_the_self_test_names_which_property_failed`.

## Pass 2 -- hostile host events through the repaired hook and the real engine

`hostile_events_probe.py.txt` here; isolated home, authority runtime and
project. 25 events: session ids that are a path traversal, quoted, 10 000
characters long, non-ASCII, a number, a list; a `cwd` that is a number, a
missing directory, a file; a model string that spells engine flags; missing and
directory transcripts; a list and an empty object as the event; every event
name including Stop re-entry and `PostToolUse` after `saipen init`.

Result: 25/25 exit 0, none blocks, none answers with an empty reason. No P0/P1.

Two neighbours filed, neither on the Claude prompt path as a lockout:

- T-1630 (P2): the Codex Stop hook has finding 2's class and loops on it.
- T-1631 (P3): the engine's global-flag scan reads option VALUES as flags, so
  a forwarded value spelling `--project-root=...` rebinds the call (measured:
  UNBOUND, permitted, no marker). Host-generated values never spell a flag.

## Pass 3 -- activation, rollback, service start, repair: read

`install_host_guard._activate_verified` / `rollback`,
`host_authority_client.ensure` / `attempt_admission`,
`host_integration.repair`. No P0/P1.

Recorded, not defects:

- `rollback` holds a kept generation to the CURRENT self-test, so the
  generation this pass repaired is refused as a rollback target. That is the
  gate doing its job; `restore.ps1 -RemoveHook` and the uninstaller remain.
- Worst-case admission wait is connect 8 s + start 6 s + retry 8 s, above the
  hook's own 20 s budget; the hook then decides it as `ENGINE_UNREACHABLE` by
  policy. Bounded, and below the 30 s the installer writes for the host.

## Pass 4 -- state model and the emergency uninstaller: read

`host_integration.derive_state` / `effective_admission` / `effective_response`
and `bootstrap/uninstall.ps1` (`Remove-HookNative`, `Remove-SkillNative`).
No P0/P1.

- The repaired hook's two new outcomes land in states the model already has:
  `DEGRADED` + `ENGINE_UNREACHABLE` is `DEGRADED_UNVERIFIED` with
  `saipen host repair`; `BLOCKED` under STRICT is `BROKEN` with the same action.
- The native uninstaller removes SAIPEN's hook ENTRIES by ownership of the
  command, and the hook FILE only while its bytes equal the shipped hook or the
  retired stand-in. While source and installed generation differ (between an
  edit here and the next `saipen host repair`) the file is preserved as
  not-ours; with its entries gone nothing runs it, and a session that still
  holds the command runs a working hook. Not a lockout in either order.

Passes 2, 3 and 4 follow the repair of pass 1 and found no P0/P1.

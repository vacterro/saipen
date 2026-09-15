# SAIPEN recovery: where to look further

This handoff preserves the investigation of the 2026-09-13 screenshot and the
operator's request to remove artificial blockers. Work through one defect at a
time. A successful skill load or router response is not proof that work ran.
The operator has authorized diagnosis, reversible fixes and verification; do
not ask them what `saipen continue` means or whether to inspect known files.

## Start here, with minimal context

Repository: `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`.
Current wave: **T-1319**. Read the actual checkpoint; this document is a handoff,
not a replacement for STATE, BOARD or LOG.

1. Read `saipen/BOOT.md`, `saipen/STYLE.md`, `.saipen/STATE.md`, the active
   BOARD entries and the last 25 LOG lines. Open only the required phase owner.
2. Use `python tools/saipen.py status --json` from the repository if the shell
   cannot resolve `saipen`. This fallback is usable in this Codex environment;
   it is not automatically admitted by another host's protected shell guard.
3. In a working OpenCode installation use standalone `saipen continue --json`.
   Read `load_path` and execute `action` in the same turn. `cold_route` names
   exact memory paths. `--dry-run` is a preview, never permission to apply.
4. Check Git status before edits. The repository already contained extensive
   staged, unstaged and untracked work. Do not reset, blanket-stage, clean,
   commit, or publish that unrelated work as part of this repair.

## What the screenshot and actual session records establish

Evidence source: screenshot `V:\___VAC\_PIC\_PRNTSCREEN\2026-09-13_135616.png`
and read-only queries of `C:\Users\vac34\.local\share\opencode\opencode.db`.
Never edit that database or print authentication/configuration secrets.

| Observation | Evidence and interpretation |
| --- | --- |
| FastPrompter stops after Skill saipen | Session `ses_f659cf4a8ffeUL0e3qRyOTSbcP`: two successive requests load `skill {name: saipen}` and stop. Actual tool output is the skill instructions. The assistant claims the skill reported a clean tree and nothing to commit, then says STATE/BOARD/LOG were not checked. That Git claim is unsupported by the tool output. |
| ProBlipAndroid cannot find Git or Java | Session `ses_f659d3014ffe0CfeTQnSubeeM4`; screenshot shows command-not-found and missing JAVA_HOME. These are host/toolchain failures, not evidence that guard denied the commands. Determine actual child-shell PATH and installed JDK before changing protocol gates. |
| ProTrail continues reading and editing | Session `ses_f659ab34bffe2nCguHE7knxmsb`; subsequent records include successful source edits. Do not label the entire installation blocked from the screenshot. |
| Recovery used to be admitted but unreachable | `KNOWLEDGE/audits/T-1318-live-recovery-proof-20260913.md`: Windows lacked a resolvable `saipen` launcher. An earlier patch creates `saipen.cmd` and a POSIX launcher. Preserve that fix. |
| An updated guard blocks diagnostics | Before T-1319, module freshness was checked before exact built-in read/skill/question fast paths. Replacing its file blocked even the tools needed to inspect the problem. |
| An existing launcher can still lose PATH priority | Before T-1319, an already-present bin entry was left in place. A competing earlier launcher ran instead. The new regression executes a real shell with two competing launchers. |

## T-1319 patch and evidence

Changes made in this wave:

- `saipen/SKILL.md`, `BOOT.md`, `COMMANDS.md`, `ACTIVATION_BLOCK.md`: explicit
  instruction to execute continuation after skill loading; no fabricated Git
  result, no stopping because required state reads were not performed.
- `tools/saipen.py`: routed output names `cold_route`, exact `load_path` for
  the **routed** phase, and `execution_instruction`. Both JSON and text output
  distinguish routing from completion. Existing actions and WAIT remain.
- `extensions/adapters/opencode/saipen-guard.js`: build
  `T-1319-opencode-continue-entry-20260913.6`; current CLI bin is moved to PATH
  front; exact built-in diagnostics remain available after module replacement;
  consequential calls still require a current module and Core admission.
- `tools/test_continue_entry.py`: regression checks for the two layout forms,
  aliases, preview purity, human-readable route, stale-plugin diagnostics,
  namespaced/consequential refusals, and actual launcher execution.
- Existing stale-module test in `tools/test_opencode_adapter.py` now exercises
  an edit rather than a question. The new matrix separately proves that edits,
  shell, task and namespaced read/skill remain refused after replacement.

Initial causal check: the four new tests failed against the pre-fix subject
(nine failing subcases), then all four passed with the same verifier after the
patch. The harness had been corrected before this comparison: valid flat
installation markers and valid JavaScript, so syntax/fixture errors are not
counted as causal evidence. Further verification status is appended below.

## Ordered follow-up work

### 1. Finish verification and installation of this exact patch

Run the focused tests below, inspect each failure, and preserve an unchanged
oracle when comparing the old and new subject. Do not declare unrelated
pre-existing failures fixed or use a skipped live test as PASS.

```powershell
python -m unittest tools.test_continue_entry tools.test_opencode_adapter tools.test_guard_events tools.test_guard_hostile_matrix tools.test_continue_improve_fallthrough tools.test_command_routing tools.test_reconcile_valve
python -m ruff check tools/test_continue_entry.py tools/saipen.py tools/test_opencode_adapter.py
```

Check installed files and the fresh-process diagnostic, not just source files:

- OpenCode skill: `C:\Users\vac34\.config\opencode\skills\saipen`.
- Plugin: `C:\Users\vac34\.config\opencode\plugins\saipen-guard.js`.
- Active diagnostic: OS temp `saipen-opencode-guard-active-<pid>.json`.
- Compare source SHA256, installed SHA256, and loaded module SHA256.
- A running OpenCode process does not hot-reload its module. Preserve its
  work and restart it before claiming the new plugin is active. Do not kill
  working user sessions automatically.
- Installation is not a blanket release of the dirty source tree. Preserve
  old installed bytes and install only the verified intended files, or use
  the canonical injector once its complete source payload is accepted.

### 2. Test the actual weak-model continuation failure

Use a disposable project and a fresh host process. Send exactly
`saipen continue`, then `cc`, and inspect actual tool events. Success requires
state reads or canonical continuation, the correct phase owner and a concrete
work action. Reading Skill alone, quoting BOOT, saying "not confirmed", or
inventing "nothing to commit" must FAIL the evaluation.

Use `tools/test_opencode_live_session.py` and the existing native harness as
the starting point. Do not rewrite another model's messages or interfere with
the user's live FastPrompter work. A deterministic test of an instruction
string proves distribution, not that every model follows the instruction.
If credentials/model availability prevent the live test, report that exact
limitation and retain the fixture for the next run.

### 3. Verify every refusal has a reachable remedy

Inspect `tools/saipen_engine/admission.py`, `guard_events.py`,
`reconcile.py`, `operations.py`, `router.py`, and the host adapter.
Build a small matrix: healthy state, malformed phase with evidence, pending
journal, conflicting journal, wrong explicit actor, missing launcher, missing
Python, stale plugin, protected multi-file patch and foreign project target.

For each row prove: exact refusal code; safe reads still work; suggested
canonical command is admitted **and actually executes**; ambiguous repair
changes zero bytes; successful repair preserves original bytes and is
idempotent; work resumes afterward. Do not infer reachability from an allow
verdict. Do not suppress real ownership, integrity or protected-path checks.

### 4. Audit continuation early returns

Inspect `_continue`, `_next_action`, `_continue_improve_fallthrough` in
`tools/saipen.py`. Some success branches return reauthorization or prepared
improvement results, not a phase action. Determine whether callers have an
executable next step, especially after safety-valve reauthorization. Avoid
infinite `continue -> continue` loops and automatic repeated reauthorization.
Keep dry-run pure and keep user-owned WAIT intact.

Review the guard binding instruction too: it currently generalizes a later
consequential refusal as protocol repair. Wrong actor, protected path,
unclassified tool and stale plugin require different remedies. Consider a
closed code-to-remedy projection in the existing owner, not fuzzy inference
or another competing router.

### 5. Diagnose Git/JDK in the actual host environment

Check `Get-Command git, java, javac` and child-shell PATH/JAVA_HOME in a bounded
probe. A launcher can work in Codex and fail in OpenCode's inherited shell.
Use known installation paths and project build requirements. An old Java 8
runtime found on disk is not proof that Android's required JDK is available.
Do not scan all disks, install arbitrary runtimes, disable optimizations, or
weaken security settings to silence a build error. Do not claim tests ran if
the required toolchain never started.

### 6. Reconcile previous lifecycle work separately

At entry to this wave: T-1318 was VERIFY; T-1317 was blocked on T-1318.
T-1318 was canonically parked for the user's new priority, preserving its
VERIFY evidence. Inspect fresh STATE/BOARD/LOG before resuming it.

Read `SRC-035` and its current contract/coverage when returning to that work.
Do not treat its historical "do not begin Fleet Recovery in this run" as a
perpetual ban overriding a later user request. Do not falsely close T-1317 or
T-1318 just because this continuation patch is working. Distinguish unavailable
external validation from discretionary deferred work and avoid global release
deadlocks caused by unrelated active source receipts.

## Rules for the next, smaller model

- Execute one concrete step and verify it before expanding scope.
- A tool description is not an execution result; cite actual output.
- Missing reads are your work. Known command semantics are not a user question.
- Separate HOST failure, protocol-state failure, permission refusal and model
  failure. Preserve the exact error rather than summarizing all as "blocked".
- Do not run repeated identical attempts against unchanged failures.
- Never manually rewrite STATE/BOARD/LOG to manufacture PASS, clear an owner,
  erase a blocker, or claim another agent's work. Use canonical operations.
- Keep existing safety checks; remove the deadlock by making the lawful remedy
  reachable and testing it through the same host that failed.
- Record test counts, skipped tests, installed generation and unresolved work.
  Do not promise that any protocol can prevent all future model mistakes.

## Verification and installation outcome

Originating-session verification:

- Four new regressions: PASS after a causal red/green comparison.
- Focused continuation, guard-event and recovery suite: **70 tests PASS**.
- Expanded seven-module suite: **192 run, 182 PASS, 10 FAIL**.
- All ten failing cases also failed in a comparison with the entry changes
  removed from in-process routing and the adapter's PATH/freshness behavior.
  The fixed bootstrap reminder remained observational in that comparison.
  Evidence: `RECOVER_ROADMAP/T-1319-baseline-failures.txt`.
- Nine of these failures concern old fixtures/expectations against the
  pre-existing stricter active-Work requirement. An empty DONE fixture returns
  `NO_ACTIVE_WORK`; a fixture with BOARD.DOING but STATE=DONE/task=none returns
  `PROTOCOL_STATE_INVALID` before ownership comparison. The tenth is
  `test_gg_new_goal_is_create_pivot_not_resume`. Do not weaken admission or
  silently update expectations: inspect each intended contract first.
- Ruff on the three changed Python files: PASS. Scoped `git diff --check`:
  PASS (Git printed only Windows newline-conversion notices).
- All six registry-owned context load budgets: PASS; no budget increased.
- **Not installed into live agent homes.** Replacing the plugin while the
  user's windows are active would immediately force those old modules into
  `PLUGIN_RESTART_REQUIRED`. The source patch is ready for installation after
  preserving work and closing those sessions. Existing global files were not
  overwritten by this wave.
- No new weak-model native continuation run, no full release gate, no commit
  or publication. T-1319 must not be described as deployed or globally proven.
- Final originating checkpoint: E-6072, phase VERIFY, task T-1319,
  `next_action: PHASE VERIFY T-1319`. Resume verification using this note;
  do not start an unrelated roadmap ticket or redo the initial investigation.

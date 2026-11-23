# T-1705: prevent direct lifecycle writes through host-relative paths

The operator redirected the work toward preventing recurrence rather than
recovering AUDAPACK's disputed historical closure. This follow-up implements a
separate, demonstrated SAIPEN guard correction. It does not reconcile AUDAPACK,
assign Widget a new task ID, invent historical events, or close any live Work.

## Proven defect and incident boundary

The sealed AUDAPACK investigation proved a FreeBuff assistant appended E-3146
outside SAIOPS. Its installed adapter declares ADVISORY enforcement with no
blocking hook. The original validator and seven forensic controls rejected the
resulting inconsistency; they did not reproduce an engine acceptance defect in
those specific controls. That historical finding remains unchanged.

This broader prevention investigation reproduced two additional engine defects
in a healthy, canonically admitted disposable BUILD project:

1. A host file event with working directory `<project>/.saipen` and relative
   target `LOG.md` was evaluated as `<project>/LOG.md`. The guard admitted direct
   edits of STATE, BOARD and LOG because it classified a different file.
2. `printf "fabricated closure" >> LOG.md` from the same working directory was
   admitted. The command did not literally spell `.saipen`, and the existing
   shell resolver reported only deletion/move effects. Literal output writes
   and named file writers escaped the same protected-path checks.

These are PROVEN pre-execution guard defects. The recorded AUDAPACK transcript
does not prove that either relative-working-directory vector caused its exact
duplicate T-299. FreeBuff's missing interception remains a distinct enforcement
gap; a unit test invoking a guard cannot establish a hook in that running host.

## Correction and exact files

- `tools/saipen_engine/admission.py`: preserve the existing canonicalizer and
  project jurisdiction, while accepting the host's actual target base for
  relative file targets. Keep their original relative spelling for traversal
  refusal; reject an unproven relative host working directory.
- `tools/saipen_engine/guard_events.py`: pass that working directory to the same
  admission owner. Extend the existing bounded shell-effect resolver with
  literal output redirection and `tee`, `tee-object`, `set-content`,
  `add-content`, `out-file`. Reuse operand resolution, wrapper/navigation bounds
  and file-effect admission. Quote contents and descriptor duplication remain
  data/non-file effects. Computed or unreadable targets fail closed.
- `tools/test_t1705_lifecycle_write_preflight.py`: seventeen controls for the
  relative canonical targets, patch batches, both move endpoints, parent paths,
  escape refusal, ordinary evidence/read availability, output spellings,
  wrappers/navigation, named writers, unreadable/computed operands, actual CLI
  refusal, advisory-strength honesty and unbound-project non-interference.
- `saipen/CORE.md`: clarify host-relative target semantics and the existing
  protection's bounded effect scope.
- `saipen/OPS.md`: declare the same resolution vocabulary and explicitly retain
  the installed-hook proof boundary.

No second authorization or recovery engine was introduced. The existing
`canonicalize_target` / `evaluate_admission` owners still decide protection,
containment, ownership and recovery. No persistent authority was granted, no
counter reset occurred, and no unsupported host was relabeled MECHANICAL.

The exact incremental delta against the pre-change working tree is
`correction.patch`, SHA256
`5f619f98a77f4f7482b26d509a29f07bc61fde116d00e9a8b06020c21dd588ff`.
Original bytes of the four existing files remain in `original-*`; this is
separate from the pre-existing staged/unstaged work. Only the new test file was
added to Git's existing index. No commit, publication, host installation or
consumer project modification was performed.

## Red/green and command evidence

`CHECKS.json` records all exact commands, exits, output hashes and source hashes.

- Initial unchanged production counterexample: 2 tests, 4 failing subcases,
  exit 1 (`preflight-red.txt`). The full expanded oracle then ran 14 tests with
  20 failing subcases, exit 1 (`preflight-expanded-red.txt`).
- Initial correction: 14 tests, zero failures, exit 0. Extra wrapper and output
  spellings exposed three further failing subcases; their original output is
  retained, then the same resolver was corrected.
- The unknown working-directory expansion exposed a real refusal gap and a
  fixture expectation mistake: the guard CLI returns exit 1, while native
  transport wrappers translate refusal to exit 2. Both original failures remain
  in `preflight-base-red.txt`; the fixture now asserts the actual CLI contract.
- Final targeted oracle: 17 tests, zero failures, exit 0, 2.531 seconds.
- Initial guard family: 172 tests, zero failures, one skip, exit 0. A later
  expanded command misspelled an existing test module and ended with one import
  error. That is preserved as a command/setup failure, not a production defect
  or an overall PASS.
- Corrected complete focused command: 205 tests, zero failures/errors, one skip,
  exit 0, 134.401 seconds (`focused-corrected.txt`). It includes the guard
  families and T-1671/T-1673/T-1679 lifecycle enforcement regressions.
- Final targeted Ruff and whitespace checks exited 0. No existing oracle or
  baseline was weakened.

At this report's initial checkpoint the fresh declared full family was still
running: `python tools/core_unit.py evidence T-1705 --fresh --jobs 6`.
`subject-before-full.json` pins the five final files. The older 6079/0/0 run is
historical evidence for its former subject, not proof of this changed tree.
The final run result and current native receipt will be appended after actual
completion; an incomplete run is not PASS.

## Native validation and canonical operations

Canonical `saipen start --file REQUEST.txt --json` captured the exact latest
instruction as SRC-207 / T-1705 at E-14227. It reported `model_supplied`, preserved
active T-1703 and explicitly did not reauthorize its valve. That local candidate
receipt is not authenticated operator ingress for the legacy goal.

Canonical checkpoint E-14228, operation
`checkpoint-fd868426669945f58f65dd699c710bff`, records the initial counterexample.
The current execution position stayed REVIEW T-1703, owner `saipen-cli`,
0 waves / 20 tickets. T-1705 remains a candidate, not a fabricated completed
lifecycle. T-1702 / SRC-205 and the remaining enforcement roadmap remain open.

Native validation of the changed source initially exited 1, CURRENT_FAIL, with
one problem and nine warnings: T-1695's old re-verification receipt did not cover
the new tree. The validator's exact remediation, `saipen work reverify T-1695`,
executed canonically and produced RV-000013, exit 0,
`PASS_WITH_CARRIED_DEBT`. That individual disposition is not an overall native
PASS. The final native validator must independently establish current conformance
after the completed family and final evidence checkpoint.

## Actual prevention and remaining scope

Installed blocking host hooks invoking the shared guard now refuse the tested
writes before execution. Ordinary source/evidence files and canonical SAIOPS
operations retain their original admission routes. A process that never invokes
the guard can still write files under its own OS permissions; no source-code
change here demonstrates an OS sandbox or creates a FreeBuff interception API.

Local FreeBuff package metadata reports version 0.0.188. Its actual registered
profile still declares ADVISORY / no hook. The upstream
[agent reference](https://www.codebuff.com/docs/agents/agent-reference) describes
agent tools and programmatic control; the
[FreeBuff tool architecture](https://github.com/CodebuffAI/freebuff/blob/main/docs/agents-and-tools.md)
describes SDK tool execution and a terminal process broker. Those mechanisms
alone are not evidence that this installed native FreeBuff session runs a
SAIPEN before-tool hook. No account, credential, launch, executable-agent import
or external installation was attempted to manufacture that proof.

Distribution also retains the existing publication-policy gate. This patch is a
reviewable local correction; it does not establish convergence of installed
copies or close the host-enforcement roadmap. AUDAPACK's historical integrity
blocker and next-task NO_GO remain unchanged; recovery of its disputed content
was not pursued after the latest steering.

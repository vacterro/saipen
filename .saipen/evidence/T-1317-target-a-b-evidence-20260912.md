# T-1317 — Target A+B evidence (2026-09-12)

Bounded durable transcript of the repair run. All numbers are from this tree
(`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`), Windows, Python 3.11,
node present, OpenCode runtime present (`opencode debug config`).

## Target A — P0 unknown-tool fail-open (repaired)

Defect (verified pre-fix reproduction, healthy SAIPEN fixture):

```
host=kiro tool=control_bash_process
tool_input={"processId":"123","input":"rm -rf src"}
actor=test-agent
-> exit 0, code ADMITTED, admitted true, action unknown,
   effect mutating, targets [], targets_unresolved false
```

Repair surface:

- `tools/saipen_engine/guard_events.py`: reviewed Kiro translation for
  `control_bash_process` (and translated identity `process_control`) ->
  unknown action with `targets_unresolved=True`; docstring hard-rule 4
  (unclassified consequential tools never ride healthy state to ADMITTED).
- `tools/saipen_engine/admission.py`: `action == "unknown"` on an applicable
  project (targets present and not wholly outside, or empty target set)
  refuses with the existing closed code `TARGET_UNRESOLVED` before the
  protocol-state check. NOT_SAIPEN_PROJECT non-interference, canonical
  `saipen_op` recovery and read-only diagnostics decided earlier, preserved.
- `tools/host_guard.py`: Kiro v3 surface translation updated — `fs_write`,
  `str_replace`, `delete_file`, `execute_bash`, `shell`,
  `control_bash_process`. `control_bash_process` never becomes an admitted
  targetless unknown; Kiro effective strength remains ENFORCEMENT_GAP (no
  native refused-effect proof), unchanged by this repair.

Post-fix verification (real `saipen guard --event-json - --json`):

| case | result |
|---|---|
| kiro control_bash_process (healthy) | rc=1 TARGET_UNRESOLVED |
| mystery_tool targetless (healthy) | rc=1 TARGET_UNRESOLVED |
| mcp__server__invoke (healthy) | rc=1 TARGET_UNRESOLVED |
| mystery_tool path=src/app.py (healthy) | rc=1 TARGET_UNRESOLVED |
| mcp__server__read path=.saipen/STATE.md | rc=1 PROTECTED_CANONICAL_NAMESPACE |
| write file_path=src/app.py (healthy) | rc=0 ADMITTED |
| bash "saipen recover" (recovery debt) | rc=0 ADMITTED (saipen_op) |
| read .saipen/STATE.md (broken state) | rc=0 ADMITTED_READ_ONLY |
| mystery_tool (non-SAIPEN dir) | rc=0 NOT_SAIPEN_PROJECT, applicable=false |

Red proof: with the two Target-A edits temporarily reverted, the new
healthy-fixture controls failed for the CORRECT reason:

```
test_A healthy unknown targetless -> AssertionError: 0 != 1 ... 'code': 'ADMITTED'
test_C kiro control_bash_process  -> AssertionError: 0 != 1 ... 'code': 'ADMITTED'
FAILED (failures=2)
```

Restored, `test_unknown_tool_fail_closed` is 8/8 OK.

## Regressions added

- `tools/test_unknown_tool_fail_closed.py` — requirements A–H of the repair
  contract, driving the public guard CLI; 8/8 OK.
- `tools/test_guard_hostile_matrix.py` — new `test_14c` healthy-fixture
  unknown-tool fail-closed control (fails against pre-fix with ADMITTED);
  `test_14`/`test_28` updated to accept either closed refusal
  (RECOVERY_REQUIRED or TARGET_UNRESOLVED) since the unknown refusal now
  fires before the state check.
- `tools/test_guard_events.py` — process-control translation mapping test.
- `tools/test_opencode_adapter.py` — live-chain unknown-tool +
  process-control cases refused with TARGET_UNRESOLVED (15 cases total).

Focused suite results (this run):

```
test_unknown_tool_fail_closed test_guard_events test_guard_hostile_matrix
test_guard_admission test_native_host_guard  -> Ran 80 tests, OK
test_opencode_adapter                        -> Ran 10 tests, OK
```

## Earlier native OpenCode CLOSE-3 evidence (guard semantics only)

Historical/superseded actor contract: the actor-binding claims in this section
and the following APPEND section predate SRC-034. They are retained as run
history, not current admission behavior. Current unbound sessions inherit
canonical `STATE.agent` and still receive ownership, recovery and protected
path checks; SRC-034 remains 16/16 VERIFIED.

`tools/test_opencode_host_smoke.py` against the REAL runtime
(`opencode debug config`, global plugin factory invoked, startup probe):

1. allowed tool effect — `read` and admitted `write` proceed (rc=0).
2. direct protected write — `.saipen/STATE.md` write prevented before host
   execution (`PROTECTED_CANONICAL_NAMESPACE`).
3. multi-file patch — `apply_patch` carrying `src/app.py` AND
   `.saipen/BOARD.md` prevented as one host tool
   (`PROTECTED_CANONICAL_NAMESPACE`); bytes unchanged.
4. exact standalone `saipen recover` remains usable while recovery debt
   exists (rc=0, saipen_op).
5. compound `saipen recover && rm -f .saipen/STATE.md` blocked
   (`RECOVERY_REQUIRED`).
6. NEW (Target A): unknown consequential tool refused by the installed hook
   (`TARGET_UNRESOLVED`).
7. Red control (`test_4_chain_bytes_prove_prevention_and_a_bypass_changes_them`):
   after the whole chain, protected STATE.md/BOARD.md bytes are unchanged;
   a deliberate bypass write changes exactly those bytes and is then
   restored, proving the refusals — not filesystem permissions — kept the
   bytes unchanged.

Correction: these cases manually supplied `SAIPEN_AGENT` after process launch.
They proved admission and blocking semantics, not production actor-binding
creation. The missing supported launcher was a repository production defect;
`ACTOR_UNBOUND` remained the correct fail-closed result for unsupported
unbound sessions. No allow-all fallback was introduced.

## APPEND — actor-binding lifecycle (same run)

Observed live failures traced and pinned:

- `GUARD_UNREACHABLE` on bootstrap `skill`: the common guard already knew
  `skill` was read-only, but the OpenCode adapter fast-path did not. The exact
  OpenCode built-in `skill` identity is now fast-pathed alongside exact reads;
  namespaced/lookalike identities still consult the guard and fail closed.
- `ACTOR_UNBOUND` on supported implementation launches: the adapter consumed
  `SAIPEN_AGENT` but no repository production path created it. The canonical
  path is now `saipen --agent <seat> launch opencode -- [args]`, backed by one
  environment builder that binds actor, project root and portable lineage
  before OpenCode starts. No session-id actor or STATE fallback exists.

The earlier `tools/test_actor_binding_lifecycle.py` result (7/7) proves common
guard semantics only. SAIPEN-side launch-boundary proof comes from
`tools/test_opencode_bound_launch_smoke.py` against real OpenCode 1.18.30:

1. test process removes `SAIPEN_AGENT` before launch;
2. launcher creates actor `launch-seat` before plugin factory startup;
3. native `skill` and repository `read` succeed;
4. two sequential native source writes succeed under the same captured actor;
5. native protected STATE write is refused and bytes remain unchanged;
6. native unknown consequential `task` is refused with TARGET_UNRESOLVED;
7. independent foreign-owner project launch is refused with OWNERSHIP_CONFLICT;
8. direct unbound plugin negative control is refused with ACTOR_UNBOUND;
9. valid supported launch contains neither GUARD_UNREACHABLE nor ACTOR_UNBOUND.

Focused native result: 2 PASS, 0 FAIL, 0 ERROR, 0 SKIP.

Operator-path amendment (SRC-033): the operator normally starts OpenCode from
AUDAPACK at `V:\___VAC\__K\__CODE\_PY\_AUDAPACK`. The native proof above uses
the same canonical SAIPEN launch-envelope implementation, but it does not yet
prove that AUDAPACK automatically supplies its explicit trusted worker/seat to
that boundary. The operator assigned that producer integration to another
agent. Therefore the SAIPEN launcher is implemented and natively verified,
while end-to-end Target-A closure for the actual AUDAPACK launch path remains
non-terminal. No claim here treats a manually supplied per-tool environment as
producer closure.

Earlier common-guard suite details:

1. `skill` maps to the read class in the guard;
2. `skill` runs with no actor and no guard dependency (kiro + gemini);
3. reads stay available with no actor at all;
4. a bound actor survives 3 sequential guarded calls;
5. actor identity does not leak across independent projects
   (foreign actor -> OWNERSHIP_CONFLICT in the other project);
6. HISTORICAL/SUPERSEDED: a genuinely missing actor on a consequential write
   was then expected to fail closed (ACTOR_UNBOUND); SRC-034 replaced this
   with canonical `STATE.agent` inheritance;
7. clean-session path skill -> read -> admitted write produces no
   GUARD_UNREACHABLE and no ACTOR_UNBOUND.

The historical 130/130 focused run predates the production launcher and must
not be read as launch-binding closure. A fresh aggregate result is recorded in
the later BUILD checkpoint/evidence update.

Canonical checkpoint: E-6037 (checkpoint-e161501efd0d4f90aad0906cc2487302),
LOG/BOARD/STATE journaled through `saipen checkpoint RUN`.

The stale snapshot note claiming canonical checkpointing had not been
journaled was removed: E-6037 already records that canonical checkpoint.

## Evidence-retention append

`EVIDENCE-RETENTION-01` now owns the rule in CORE and `REGISTRY.json` owns the
25 MiB artifact, 100 MiB warning, 250 MiB review, and four-class facts. The
runtime implementation removes its exact run-owned temporary root after
compact proof extraction on success and failure, refuses external/unregistered
cleanup, preserves active references, and writes classed retention manifests.

Historical `.saipen/evidence` classification before cleanup: 1
`DURABLE_REQUIRED` file (this transcript, 7205 bytes at classification time),
0 `EPHEMERAL_REPRODUCIBLE`, 0 `SUPERSEDED`, 0 `UNKNOWN`; no cleanup performed.
Storage regression result: 16 PASS, 0 FAIL, 0 ERROR, 0 SKIP, including a sparse
340 MiB synthetic runtime matrix leaving less than 1 MiB durable proof.

## Fresh BUILD verification after SRC-033

- Focused enforcement/adapter/launcher/retention aggregate: 169 PASS, 0 FAIL,
  0 ERROR, 0 SKIP (`Ran 169 tests in 68.862s`).
- Python Ruff, Python byte compilation, OpenCode adapter `node --check`, and
  both changed JSON registries: PASS.
- General command-routing family: 61 PASS, 1 FAIL, 0 ERROR, 0 SKIP. The one
  failure is the pre-existing CORE-003 allocation-frontier condition in
  `test_gg_new_goal_is_create_pivot_not_resume`, outside T-1317.
- `python tools/validate.py --gate core`: FAIL with 37 problems and 25 warnings.
  The reported failures are existing dirty-tree/source/allocation/runtime-
  manifest coverage conditions, including the deliberately untouched T-1307;
  this run does not claim a green global gate and does not repair them in this
  corridor.
- Canonical RUN checkpoint E-6038 records the green focused result and the
  non-terminal AUDAPACK producer dependency.

Truth remains non-terminal outside this repair slice: the AUDAPACK producer
carrier, Kiro native proof, and FastPrompter producer carrier are
external/non-terminal; broader Gemini smoke keeps its prior non-terminal
disposition. T-1317 therefore remains BUILD.

## 2026-09-13 Target A+B follow-up

The later shell audit found ordinary `bash` with
`python -c "...Path('.saipen/STATE.md').write_text(...)"` was `ADMITTED` on a
healthy project: targetless shell effects bypassed the structured-path rule.
The repair refuses explicit `.saipen` references in ordinary shell command
text, including quotes, Windows/POSIX separators, `./` and simple traversal.
Standalone `saipen recover` remains the recovery path. This command-text
preflight cannot prove dynamically computed or deliberately obfuscated
arbitrary code safe; it is no sandbox. Normal source-oriented shell remains
admitted. Nested historical ephemera now classify below UNKNOWN ancestors;
cumulative hard-threshold excess refuses terminal EvidenceRun finalization
unless justified via `large_evidence_required`, preserving proof and retry
state. The OpenCode native smoke is the first production EvidenceRun producer;
it retains compact proof and a manifest after removing its owned HOME/cache
root. T-1317 remains BUILD while linked closure requirements are non-terminal.

Current-tree validation, in required order: focused guard/adapter 93 PASS;
focused evidence hygiene 18 PASS; SRC-034 actor/binding 28 PASS; OpenCode
synthetic-home native smoke 4 PASS and real installed/global/bare/optional
launch native smoke 3 PASS. The native smoke manifest reports 4189 retained
bytes, equal to the actual two retained files; its OS-temp HOME/cache/workdir
root no longer exists. The installed OpenCode plugin and guard skill files were
updated after retaining their prior bytes in `.saipen/kitchen`; a new host
process loaded the current hook and had no GUARD_UNREACHABLE or ACTOR_UNBOUND.
The exact built-in `question` tool now bypasses the guard as non-mutating;
the adapter test proves it remains usable without a Python guard runtime.
Ruff, Python compilation and Node syntax checks PASS.

Broader Core verification remains non-terminal: 1695 tests, 32 FAIL, 1 ERROR,
2 SKIP (unrelated existing inventory/allocation/attribution failures and a
pre-existing 5-second latency tripwire in the native-smoke module). Core gate
remains 37 problems, 25 warnings, including existing untracked runtime
manifest members and allocation history gaps. No SAITULS/AUDAPACK production
change or cross-repo suite was run for this repair.

## 2026-09-13 OpenCode task delegation follow-up

User-visible reproduction from multiple ordinary OpenCode projects:
`task` for a General Task was refused before execution as
`TARGET_UNRESOLVED`. Pre-fix focused regression reproduced that exact
classification/refusal. The exact OpenCode built-in `task` now maps to a
consequential `delegate` action, admitted only after canonical state, actor,
ownership and recovery checks. An unrelated namespaced/lookalike task remains
unclassified and refused. Native OpenCode child-session proof: the parent task
completed, child source write landed, child `.saipen/STATE.md` write and
`.saipen/BOARD.md` shell mutation were refused by the child tool guard; STATE
and BOARD bytes stayed unchanged. No seat or launcher requirement was added.
The guarantee is scoped to the tested native OpenCode runtime and built-in
task path; it is not a sandbox or proof for third-party delegation tools.

## 2026-09-13 active plugin generation follow-up

The earlier native smoke's newly launched process proved its own hook bytes,
but installed-file equality alone did not establish what already-running user
windows had imported. Their old loaded hook continued to route exact question
through the guard and could report GUARD_UNREACHABLE. The current hook now
captures its module SHA-256 at evaluation, writes a bounded factory-startup
diagnostic outside `.saipen`, and checks its loaded hash against the file
before every tool call. A changed file produces PLUGIN_RESTART_REQUIRED in
this generation; an older loaded generation cannot gain that diagnostic and
requires a process restart. Neither injector terminates user processes.

Focused validation: guard/adapter 90 PASS; evidence 18 PASS; actor/launch 15
PASS; synthetic-home real OpenCode host smoke 4 PASS; PowerShell injector
smoke 1 PASS; real installed-generation checks 2 PASS; bound native OpenCode
smoke 4 PASS. The shell injector and PowerShell injector both overwrite the
plural artifact, remove a seeded exact singular copy, and report matching
SHA-256 plus the explicit restart requirement. The real user installation
reported SHA-256
`b5d4accdd747e68c2e1a5f0fbdc03ce22eb8a51429e00dbe1244ac29df51b6a0`.
A NEW `opencode debug config` process launched after installation reported
exactly one SAIPEN hook origin; its factory diagnostic carried that hash,
the canonical plural module path, skill root, guard runtime path, and a
startup timestamp after installation. A deliberate module-file replacement
test produced PLUGIN_RESTART_REQUIRED even for exact `question` before any
host effect. The native bound smoke exercised skill/read/bash, ordinary
write, task delegation and protected-path refusals. Existing user windows
were not killed and must restart for the new generation. T-1317 stays BUILD.

Post-native static checks: Ruff, Python byte compilation, Node syntax, Git
Bash syntax and PowerShell injector execution PASS. A fresh broad unittest
discovery was attempted after these focused checks. It made progress through
hundreds of tests, including failures in the already dirty Core tree, then
spent over four minutes in one CPU-intensive test without emitting another
result; only that test-runner process was stopped. No completed broad-suite
verdict is claimed. The subsequent Core gate still reports 37 problems and
25 warnings, including untracked runtime-manifest members and existing
coverage/ledger debt. This does not justify moving T-1317 beyond BUILD.

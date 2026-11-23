# T-1956 VERIFY -- the ticket's own three criteria, executed

## Criterion 1: the test exits 0 on the installed host

```
$ python -B -m unittest tools.test_host_bootstrap.ActivationDeliveryTests.test_32_installed_desktop_loader_reads_the_injected_block
Ran 1 test in 0.169s
OK
```

**PASS.** It was `FAILED (failures=1)` / `EXTRACT_FAILED` before the change.

## Criterion 2: a red control shows the test still FAILS against a deliberately mispointed extractor

The probe takes the loader name as an argument precisely so this can be
measured. Pointed at `loadUserKnowledgeFiles` -- the symbol the 2026-10-29
bundle removed -- it must not quietly answer:

```
$ node probe.js <orchestrator> loadUserKnowledgeFiles <project-with-block>
rc 3 | EXTRACT_FAILED:loadUserKnowledgeFiles
```

**PASS.** The failure is loud, named, and distinct from a "delivered nothing"
answer, so leg 2 of the test (`assertEqual(probe(home_only), "")`) cannot be
satisfied by a broken extractor returning `""` for the wrong reason.

The complementary control -- the bundle stops delivering -- was also run:

```
fixture AGENTS.md without the block
delivered: '\n\nProject instructions loaded by Freebuff:\n\nInstructions fro...'
block absent: True
```

The loader still wraps whatever it reads, so the test reds on the
`assertIn("<!-- SAIPEN:BEGIN -->")` line rather than on an unrelated string.
That is the assertion the ticket exists to protect.

**Third control, the strongest one:** the *old* test at HEAD, restored with
`git stash push -- tools/test_host_bootstrap.py`:

```
$ python -B -m unittest tools.test_host_bootstrap.ActivationDeliveryTests.test_32...
Ran 1 test in 0.084s
FAILED (failures=1)
```

HEAD fails, the patch passes. The change is what fixes it -- not a host change
that happened to land in between.

## Criterion 3: the disposition names the artifact that actually builds the prompt, with file:byte evidence

The packaged Electron main process decides the runtime:

- **artifact that builds the prompt:** `resources/orchestrator/orchestrator.js`,
  9,387,635 bytes, mtime `2026-10-29 08:27:12`.
- **evidence it is the spawned one:** `app.asar` → `/electron/main.cjs`,
  `resolveOrchestrator()`, packaged branch:
  `args: bunLaunchArgs(path.join(orchDir, 'orchestrator.js'))` with
  `orchDir = path.join(process.resourcesPath, 'orchestrator')`.
- **evidence the old surface is gone:** in that file,
  `loadUserKnowledgeFiles` count 0, `selectKnowledgeFilePaths` count 0,
  `.AGENTS.md` count 0, `.CLAUDE.md` count 0; `userKnowledgeFiles` count 1 and
  that one occurrence is the **schema field**, never an assignment.
- **evidence the new surface is the project root:**
  `loadClaudeProjectInstructions(cwd)` joins `KNOWLEDGE_FILE_NAMES` entries and
  `.claude/CLAUDE.md` onto `cwd`; its only call site is
  `turn.projectInstructions ? loadClaudeProjectInstructions(turn.cwd) : ""`.
- **exhaustive negative:** no `join(<homedir>, '*.md')` exists in the bundle
  (0 matches over every `join*()` call), and `app.asar`'s only occurrences of
  the loader name are inside `@codebuff/sdk/src/__tests__/user-knowledge-files.test.ts`
  and `@codebuff/sdk/src/run-state.ts` -- TypeScript **source**, while the
  executed artifact is the bundled `.js`.

**PASS.**

## Full suite state

```
tools.test_host_bootstrap                  25 tests OK in 13.154s
tools.test_instruction_loader_contracts     9 tests OK in 0.140s
```

## Diff footprint

```
 tools/test_host_bootstrap.py | 178 +++++++++++++++++++++++++++------------
 1 file changed, 128 insertions(+), 50 deletions(-)
```

One file. The 50 deletions are the old home-scanner extractor and its
implementation-coupled assertions; nothing outside this module is touched,
confirmed by `git grep -ln "test_32_installed_desktop_loader\|loadUserKnowledgeFiles" -- tools/`
returning only this module plus the baseline file.

## The declared family red is cleared by this ticket

`tools/core_unit_baseline.json` carries this test as its single red -- grown
during T-1955 with the reason recorded. With the test green, the family gate
for this tree should report `red: 0`; that run follows in VERIFY.

## Carried forward, not fixed here

`T-1957` (filed P2, `--needs T-1956`) owns the registration-strategy decision:
the registry still declares `~/.AGENTS.md` as the FreeBuff Desktop surface and
`autoinject.instruction_contract_status` still reports `current` on that basis,
even though no running desktop code reads a home dotfile. Recorded in SCOUT,
BUILD and here so it cannot be lost.

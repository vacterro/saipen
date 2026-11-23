# T-1956 SCOUT -- which artifact builds the desktop prompt, and what it reads

## What the ticket asks

`test_32` extracts `loadUserKnowledgeFiles` from the installed FreeBuff Desktop
bundle and executes it. Since 2026-10-29 it fails with `EXTRACT_FAILED`. Decide
whether the *test* drifted or the *host surface* did.

## Which artifact actually runs

The packaged app spawns one bundle, named by its own main process
(`app.asar` → `/electron/main.cjs`, `resolveOrchestrator()`):

```js
if (app.isPackaged) {
  const orchDir = path.join(process.resourcesPath, 'orchestrator')
  return { bun: ..., args: bunLaunchArgs(path.join(orchDir, 'orchestrator.js')), ... }
}
```

So the live artifact is `resources/orchestrator/orchestrator.js` (9,387,635
bytes). `app.asar` is the Electron shell; its `@codebuff/sdk/src/run-state.ts`
is TypeScript **source**, not the executed bundle.

## What the live bundle now contains

Measured on the file the app actually spawns:

| string | count |
|---|---|
| `loadUserKnowledgeFiles` | **0** |
| `selectKnowledgeFilePaths` | **0** |
| `userKnowledgeFiles` | 1 -- and it is a *schema field*, never assigned |
| `knowledgeFiles:` | 2 -- one schema field, one `knowledgeFiles: {}` literal |
| `loadClaudeProjectInstructions` | 2 -- definition + call site |

The one surviving instruction loader is project-root scoped:

```js
function loadClaudeProjectInstructions(cwd) {
  let paths = [KNOWLEDGE_FILE_NAMES.map((n) => join51(cwd, n)).find(isFile),
               join51(cwd, '.claude', 'CLAUDE.md')].filter(isFile);
  ...
}
```

It reads `cwd/AGENTS.md` (or `cwd/CLAUDE.md`) and `cwd/.claude/CLAUDE.md` --
**under the project root, not the home directory**. Its call site gates it:

```js
turn.projectInstructions ? loadClaudeProjectInstructions(turn.cwd) : ""
```

Every exhaustive sweep for a home read came back empty: no
`join(<something homedir>, '*.md')` exists, and the literal strings `.AGENTS.md`
and `.CLAUDE.md` do not occur anywhere in the bundle (0 occurrences of the
dotted forms; the undotted `KNOWLEDGE_FILE_NAMES` entries are joined to `cwd`).

`resources/orchestrator/ui/assets/index-*.js` also carries no `AGENTS.md`,
`CLAUDE.md` or `userKnowledge` at all.

## Verdict

**The host surface really moved, and the test was measuring the old one.**
This is not a test that drifted away from a working behavior: the behavior it
asserted (a `~/.AGENTS.md` reaching the desktop first-turn prompt) no longer
has an implementation in the shipped bundle. The extractor reported
`EXTRACT_FAILED` -- loudly and correctly -- rather than silently passing.

Magnitude, stated honestly:

- The activation block now reaches the desktop **only from the project root**.
- This repository has **no `AGENTS.md` at all** (`saipen host instructions
  status` → `PROJECT_BLOCK_ABSENT`), while `~/.AGENTS.md` and `~/.knowledge.md`
  both exist and carry current blocks.
- Therefore, on this machine, **the project-scoped read has nothing to read**
  for this project, and the home surfaces it used to rely on are no longer
  consulted by the desktop path.

That is a real behaviour change to the registration strategy, not a test
nuisance. It is however a *different* ticket's decision (whether SAIPEN should
write a project-root block, and whether the registry should keep declaring home
surfaces for this host). T-1956 is scoped to making the instrument honest, so
that whichever decision is taken is measured rather than assumed.

## Also found: two oracles still assert the old contract

- `extensions/adapters/registry.json:487-493` still declares the FreeBuff
  Desktop loader surface as `["~/.AGENTS.md", "~/.CLAUDE.md"]`.
- `autoinject.instruction_contract_status(...)` therefore returns
  `status: current` for this host, on the strength of `~/.AGENTS.md` being
  present -- while nothing in the running desktop bundle reads it.

Both are recorded here and carried into the disposition. Changing the registry
is a strategy decision with its own blast radius (`test_instruction_loader_contracts`
asserts the exact declared lists), so it is not folded into this ticket
silently.

## Instrument for the fix

The old probe extracted a **home scanner** by name. The honest replacement
executes the loader that exists and asserts both halves of the new contract:

1. project-root `AGENTS.md` carrying the block **is** delivered;
2. a home carrying only `.AGENTS.md` is delivered to **nothing** (so the
   accepted staleness cannot come back unnoticed);
3. a loader name the bundle never defines makes the probe exit non-zero with
   `EXTRACT_FAILED`, so leg 2 cannot pass vacuously.

Bounds (`PROJECT_INSTRUCTION_LIMIT`, `PROJECT_INSTRUCTION_TRUNCATION_NOTE`) are
read out of the bundle by regex rather than hardcoded in the probe -- otherwise
the probe would keep answering an old number after the host moved it, which is
the same drift class this test exists to catch.

## Commands used

```
python - (asar header parse; extract /electron/main.cjs resolveOrchestrator)
python - (string census of resources/orchestrator/orchestrator.js)
python - (exhaustive join(...homedir...) and literal ".AGENTS.md" sweep)
python - (as_ar entry scan for loadUserKnowledgeFiles)
python -B -m unittest tools.test_host_bootstrap.ActivationDeliveryTests.test_32...
saipen host instructions status
python - (autoinject.instruction_contract_status on the live registry)
```

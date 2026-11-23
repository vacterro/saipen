# T-1957 VERIFY -- the ticket's own three criteria, executed

## Criterion 1: the registry names the surface the shipped bundle reads

The ticket asks for `file:byte` evidence from the artifact that runs. Both
loaders, measured out of the binaries (SCOUT has the full excerpts):

**freebuff CLI 0.2.34** -- `~/.config/manicode/freebuff.exe`, 123,988,736 bytes,
mtime 2026-10-22 09:11:33, version from `freebuff-metadata.json`:

- home reader `Ro$` at offset **100333821** matches stripped dotfile names
  against `v7 = ["agents.md","claude.md"]` case-insensitively and `break`s on
  the first hit **in that order** -> `.AGENTS.md` then `.CLAUDE.md`;
- `\.knowledge\.md` occurs **once** in the whole binary, in the *project*
  predicate `D8A` (`A.endsWith(".knowledge.md")`) -- never a home read.

Registry now: `["~/.AGENTS.md", "~/.CLAUDE.md"]`.

**FreeBuff Desktop** -- `resources/orchestrator/orchestrator.js`, 9,387,635
bytes, mtime 2026-10-29 08:27:12:

- `loadUserKnowledgeFiles` 0, `selectKnowledgeFilePaths` 0, `.AGENTS.md` 0,
  `.CLAUDE.md` 0 as home reads;
- `loadClaudeProjectInstructions(cwd)` joins `KNOWLEDGE_FILE_NAMES =
  ["AGENTS.md","CLAUDE.md"]` onto `cwd`, plus `.claude/CLAUDE.md`;
- call site: `turn.projectInstructions ? loadClaudeProjectInstructions(turn.cwd) : ""`.

Registry now: `scope: project`, `surfaces: []`,
`project_surfaces: ["AGENTS.md","CLAUDE.md",".claude/CLAUDE.md"]`.

**PASS.**

## Criterion 2: the verdict reports the truth rather than current-by-home-file

Red control -- the **HEAD** registry (`git show HEAD:...`) fed through the
**new** verdict code, on this machine's real home:

```
HEAD registry -> current
    freebuff CLI | ~/.knowledge.md | current
    FreeBuff Desktop | ~/.AGENTS.md | current
current registry -> current
    freebuff CLI | ~/.AGENTS.md | current
    FreeBuff Desktop | None | not-applicable
```

The first block is the defect, reproduced: two rows claiming delivery from
files those loaders do not open -- `.knowledge.md` is not a home surface of the
0.2.34 CLI, and the desktop has no home surface at all.

The second block is the fix: the CLI row names the file the binary opens first,
and the desktop row no longer claims a home delivery it cannot perform.

**PASS.**

## Criterion 3: both oracles pass, and one goes stale on a home-only dotfile

```
$ python -B -m unittest tools.test_instruction_loader_contracts tools.test_host_bootstrap
Ran 36 tests in 21.591s
OK
```

The ticket's third clause -- *a red control shows the new verdict goes stale
when only a home dotfile is current* -- is
`test_knowledge_only_home_is_stale_and_names_the_cli_surface`: a home carrying
only `~/.knowledge.md` (the exact T-1426 live shape) must read `stale`, and it
does, naming `freebuff CLI` and `.AGENTS.md`. Under the old constants that same
fixture was `stale` for a *different* reason (the desktop could not see
`.knowledge.md`); it is now `stale` because the CLI cannot see it either, which
is the measured truth rather than the inherited one.

The pinned pre-fix subject still exhibits the defect on that fixture
(`test_pre_fix_subject_reported_the_knowledge_only_home_current`: blob
`98dd6e77` answers `current`, the fixed owner answers `stale`), so the red half
of the pair is unchanged evidence.

**PASS.**

## Note on `absent` vs `stale`, caught in BUILD

Moving `.knowledge.md` out of the read list initially made the knowledge-only
fixture report `absent`, because the verdict's "did anything get installed"
signal was computed from the read loop. That would have been a *softer* verdict
than the truth: the installer demonstrably ran on that home. The signal now
keys on the adapter's declared **write** surfaces, so an installed-but-blind
home is `stale`. `test_an_uninstalled_adapter_without_any_surface_is_absent`
still passes, so the two states stayed distinct.

## Declared family

`python tools/core_unit.py evidence T-1957 --fresh` -- full sweep, recorded
under `.saipen/evidence/core-unit/`. The command's own verdict is cited in the
VERIFY checkpoint; the record path and fingerprint are in the LOG line.

## Scope

Four files: `extensions/adapters/registry.json` (+8/-5), `tools/autoinject.py`
(+22/-3), `tools/test_instruction_loader_contracts.py` (+~110/-~35),
`tools/test_host_bootstrap.py` (+~40/-~25). No installer behaviour changed, so
no home needs re-writing: the fix removes a false report, it does not move a
byte on disk.

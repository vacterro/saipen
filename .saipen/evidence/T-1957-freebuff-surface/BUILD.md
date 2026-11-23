# T-1957 BUILD -- the change, and the two corrections my own tests forced

## What changed

Four files, one decision each.

### 1. `extensions/adapters/registry.json` -- state what the loaders read

```diff
   "instruction_loaders": [
     { "name": "freebuff CLI",
+      "scope": "home",
       "surfaces": [
-       "~/.knowledge.md",
         "~/.AGENTS.md",
-       "~/.claude.md"
+       "~/.CLAUDE.md"
       ] },
     { "name": "FreeBuff Desktop",
-      "surfaces": [
-        "~/.AGENTS.md",
-        "~/.CLAUDE.md"
-      ] }
+      "scope": "project",
+      "surfaces": [],
+      "project_surfaces": ["AGENTS.md", "CLAUDE.md", ".claude/CLAUDE.md"] }
   ],
```

`instruction_surfaces` -- the installer's WRITE list -- is deliberately
untouched. It still writes `~/.knowledge.md` and `~/.AGENTS.md`. Writing a file
an older CLI reads is not a false claim; *reporting* delivery from it was.

### 2. `tools/autoinject.py` -- a home verdict cannot measure a project reader

`instruction_contract_status` gains one branch and two corrections:

```python
if str(contract.get("scope") or "home") == "project":
    deliveries.append({"loader": loader, "surface": None, "status": "not-applicable"})
    continue
...
states = [e["status"] for e in deliveries if e["status"] != "not-applicable"]
```

and the install-presence signal moved off the read loop:

```python
saw_any_surface = any(
    _expand_home(str(surface)).is_file()
    for surface in (adapter.get("instruction_surfaces") or [])
)
```

### 3. `tools/test_instruction_loader_contracts.py` -- the oracles follow

`CLI_SURFACES` becomes `(".AGENTS.md", ".CLAUDE.md")`, `DESKTOP_SURFACES`
becomes `()`, a new `PROJECT_SURFACES` carries the desktop's real contract, and
the fixture declares `scope` on both loaders. One test added
(`test_a_project_scoped_loader_is_not_applicable_not_a_home_verdict`), one
rewritten (`test_the_installer_writes_the_surface_each_loader_reads_first`), and
the four existing acceptance tests re-pointed at the CLI's real surfaces.

### 4. `tools/test_host_bootstrap.py` -- same, at the delivery layer

`FREEBUFF_CLI_HOME_SURFACES = (".AGENTS.md", ".CLAUDE.md")`;
`FREEBUFF_DESKTOP_HOME_SURFACES = ()` with the reason in the constant.
`test_31` and `test_33` now assert the sharper truth: a `.knowledge.md`-only
home reaches **no** home loader.

## Two corrections my own tests forced

Both were the BUILD writing something that did not hold, caught before VERIFY.

**A. `.name` collapses `.claude/CLAUDE.md`.** My first assertion compared
`[Path(s).name for s in loaders[1]["project_surfaces"]]` against
`PROJECT_SURFACES` and got `['AGENTS.md','CLAUDE.md','CLAUDE.md']`. Comparing
the declared strings is the right assertion; a path accessor silently drops
the subdirectory the bundle actually joins.

**B. "the installer writes every read surface" is false and should not be a
rule.** `.CLAUDE.md` is a *fallback*: the CLI reads it only when `.AGENTS.md`
is absent. Requiring the installer to write it would demand a file nothing
needs. The invariant that actually matters is that the installer writes the
surface each loader reads **first**, because that is the one a stale copy would
shadow. Rewrote the test to that, and it passes for the right reason.

**C. `absent` vs `stale` for a knowledge-only home.** Moving `.knowledge.md`
out of the read list made that fixture report `absent`, which is wrong: the
installer demonstrably ran there. The verdict now keys install-presence on the
adapter's declared *write* surfaces, so an installed home that delivers nothing
reads `stale` -- which is the T-1426 shape and the whole reason the test exists.

## The pre-fix red control got sharper, and I checked that it did not go slack

`test_33` runs the pinned pre-fix injector, which writes `.knowledge.md`
(preferred) or falls back to `.AGENTS.md`. Under the old constants it passed
because the CLI still accepted `.knowledge.md`. Under the measured 0.2.34
contract that file reaches neither loader, so the test asserts `None` for the
CLI contract as well. This is a *stronger* red, not a weaker one -- but it is
also no longer proving the same proposition (T-1426's "desktop is blind"), so
the assertion text names what it proves now rather than letting a passing test
imply the older claim.

`test_pre_fix_subject_reported_the_knowledge_only_home_current` still runs the
pinned `autoinject.py` blob 98dd6e77 and still requires it to answer `current`
on the same fixture where the fixed owner answers `stale`. That is the
unchanged control: the defect is exhibited by the old code on the new fixture.

## Live measurement, before and after

```
BEFORE (T-1957 SCOUT)                    AFTER
overall: current                          overall: current
  freebuff CLI ~/.knowledge.md current      freebuff CLI ~/.AGENTS.md current
  FreeBuff Desktop ~/.AGENTS.md current     FreeBuff Desktop (none) not-applicable
```

The CLI row now names the file the 0.2.34 binary actually opens first, and the
desktop row no longer claims a home delivery its loader cannot perform.

## What BUILD did not change

- `saipen_engine/project_block.py` -- it is the owner of the project half and
  its contract ("a block is never created") is what closed the
  "installer writes a root `AGENTS.md`" option. Untouched.
- `protocol_admission._agents_component` -- unions `surfaces` only. The union
  shrinks with the registry, which is the correct direction: it must not treat
  a home dotfile as evidence for a loader that does not read it.
- `bootstrap/inject.ps1` -- still writes every `instruction_surfaces` entry.
  No installer behaviour changed, so no migration is needed for homes already
  written.

## Failing-first evidence

Before the registry edit, the live verdict was the false `current` quoted in
SCOUT. After it, the desktop row cannot be `current` from a home file because
the loader has no home surfaces to read -- the code path that produced the
false claim no longer exists for it, rather than being merely re-worded.

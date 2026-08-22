# Harness — the gate commands, cited rather than rediscovered

There is no Taskfile, Makefile or package manifest here: the gates are plain
stdlib Python scripts run from the SAIPEN home. Recording them once because a
command each session re-derives is a command two sessions can disagree about
while both believe they ran the check (phases/scout.md step 3).

Run every one from the repository root.

```
python tools/validate.py            # full conformance gate; 0 FAILs required
python tools/audit_checks.py        # every validator check must go red on its own condition
python tools/run_scenarios.py       # executable fixtures + probes
python tools/audit_floor.py         # portable-floor parity
python tools/audit_parity.py        # phase/command/shortcut parity
python tools/audit_order.py         # document ordering
python tools/audit_tags.py          # release ledger vs git tags
python -m ruff check tools/ tests/  # lint, pinned to ruff==0.16.0
git diff --check                    # whitespace
```

The lint line is the ONE canonical ruff surface: `tools/` and `tests/` both, pinned to
`ruff==0.16.0`. `.github/workflows/validate.yml` runs exactly this command and this
version; `tools/validate.py`'s parity check proves the two stay in agreement. A host
without Ruff MUST report the lint gate as missing evidence, never as green -- run the
rest of the suite, LOG `lint: not run (ruff unavailable)`, and do not claim full-green
for a pass that never linted.

`tools/validate.py --gate <name>` narrows the gate (`core`, `ship`,
`collect:<sub>`). `tests/validate.sh` / `tests/validate.ps1` are the portable
floor — a deliberate SUBSET of `validate.py`, for hosts without Python.

## Layout facts the gates depend on

- `tools/` is a `copy_trees` entry in `saipen/MANIFEST.json` and the injectors
  copy it with `rglob("*")`, so a package under `tools/` ships with an install
  without needing its own manifest row. A package outside `tools/` does not.
- `tools/` is on `sys.path` whenever a tool is run as `python tools/<x>.py`,
  so `import saipen_engine` resolves from any tool with no path juggling.
- `saipen/MANIFEST.json`'s `files` list is checked two ways: the file must
  exist AND `git ls-files` must track it. An uncommitted runtime file passes
  locally forever and fails every CI run.
- Copy-tree membership is context-sensitive by design: ordinary/core checks
  inspect the complete live tree because direct injectors copy it; the binding
  SHIP gate inspects the Git index tree because only the scoped release index
  may enter the commit. Thus foreign untracked copy-tree noise is visible to
  installation audits but cannot hijack an otherwise exact release scope.

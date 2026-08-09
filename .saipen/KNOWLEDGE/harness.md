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
python -m ruff check tools/         # lint
git diff --check                    # whitespace
```

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

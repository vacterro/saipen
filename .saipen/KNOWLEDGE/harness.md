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

## The declared core-unit family is SHIP evidence (T-1344)

```
python tools/core_unit.py evidence T-###   # whole family, cited in LOG
python tools/core_unit.py baseline         # re-record the inherited red set
```

`saipen_engine/test_runner.py` declares the core-unit family as
`python -m unittest discover -s tools -p test_*.py`. A closure citing named
modules (`python -m unittest tools.test_x`) is not a run of it: those import
dotted, skip discovery order and never see the rest of the family, and waves
closed green that way while the family carried dozens of red tests.

So a transition into SHIP in this repository requires, in the ticket's current
VERIFY cycle, an anchored `CORE-UNIT-EVIDENCE` line written by
`core_unit.py evidence`. It cites a JSON record under
`.saipen/evidence/core-unit/` by path and sha256; the gate refuses a record
with any red id outside `tools/core_unit_baseline.json`, a run that did not
reach its summary, a record judged against another baseline, or one whose
content fingerprint is not the tree being shipped. The fingerprint covers
everything the sandbox copies except `.saipen/` and `.git/` -- the family
reads `tests/`, `bootstrap/`, `extensions/` and the root file set too -- and
is taken from the copy that ran. Any edit outside `.saipen/` after the copy
(a stray root file included) means a rerun, unless the tree returns to the
tested bytes, in which case `evidence` reuses that PASS record.

The baseline only shrinks freely: `baseline` refuses to add a red id without
`--grow "<reason>"`, and the reason is stored in the file. A run that fixed an
inherited red reports it under `fixed`; shrink the baseline in the same Work.
Projects without `tools/saipen_engine/test_runner.py` are untouched.

`tools/validate.py --gate <name>` narrows the gate (`core`, `ship`,
`collect:<sub>`). `tests/validate.sh` / `tests/validate.ps1` are the portable
floor — a deliberate SUBSET of `validate.py`, for hosts without Python.

## What the red-control line does NOT prove (T-1292)

`audit_checks.py` CASES is hand-maintained. Line 12's law — every validator
check goes red on its own condition — is therefore only as complete as that
list, and the list is not derived from the validator. A check landed in
v7.254.0 with no control and the closing sweep line read the same total before
and after it arrived, so the number a checkpoint quotes as proof the control
ledger is intact did not move.

The partial binding is `check_inventory_probe`: `VALIDATOR_FAIL_SITES` in
`tools/audit_checks.py` records how many `fail(...)` sites `tools/validate.py`
declares, and the sweep fails when that count moves. Growing the validator now
forces a decision — add the CASE, or record why the new check has none — and
raising the constant belongs in the same change.

**Deliberate limitation, deliberately not closed here.** The count binds
VOLUME, never IDENTITY: it cannot say which check has a control, and a change
that adds one check while deleting another keeps the total and passes. Closing
that needs stable per-check identity in the validator (named checks, not
`fail(...)` call sites), which is separate Work. Until then, treat a green
inventory line as "the surface did not silently grow", not as "every check is
covered".

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

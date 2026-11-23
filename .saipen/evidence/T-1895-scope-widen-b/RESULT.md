# T-1895 — thirty-nine more modules, proven by `ran` equality

T-1894 declared eighteen modules from the static filter plus a narrowed run.
This ticket takes the rest of the filter's output and raises the proof bar: a
declaration is accepted only when the module's **own test count** in the
narrowed sandbox equals its count in a full one. `PASS` alone was never enough —
a module that silently collected fewer tests would still exit 0.

## Selection, and what the filter got wrong

The static filter (no `.saipen`, `.git`, `STATE.md`, `BOARD.md`, `LOG.md` or
`evidence/` reference in the module's own source) yielded 86 undeclared modules.

Two corrections came from evidence, not from reading:

* **46 modules import another `test_*` module that does reference those trees.**
  `test_operator_origin_support.py` is the concrete case: its own text is clean,
  but it does `import test_t1844_origin_broker as controls`, and that module
  reads `.saipen/STATE.md`. In a narrowed sandbox it collected **0 tests** and
  the batch stopped there. These 46 stay undeclared.
* **`tools/test_runner.py` is a CLI wrapper, not a test module** — it collects
  0 tests even in a full copy. `focused` treats a zero-test run as a failure and
  stops the batch, so it cannot be a pattern at all. (Three sibling helpers —
  `test_fixture_support.py`, `test_host_fixture.py`,
  `test_operator_origin_support.py` — have the same zero-collection shape.)

39 modules survived both corrections and are declared here.

## Proof: per-module `ran`, FULL against narrowed

Both sides select the same 39 modules in the same two batches, on the same tree,
with the same unittest command. `compare.py` compares them module by module.

| batch | modules | FULL ran | narrowed ran | FULL wall | narrowed wall | copy FULL → narrow |
|---|---|---|---|---|---|---|
| 1 | 20 | 176 | 176 | 94.2 s | 28.0 s | 54.2 s → 0.36 s |
| 2 | 19 | 139 | 139 | 102.0 s | 39.3 s | 50.1 s → 0.39 s |
| **total** | **39** | **315** | **315** | **196.3 s** | **67.2 s** | — |

`compare.py` verdict on both batches: `EQUAL` — zero patterns present on only
one side, zero `ran` mismatches, zero red-set changes. The 315 tests are the same
315 tests.

Wall time drops 65.8% for the identical work; the residue is the modules' own
subprocess execution, not the harness.

## What is NOT claimed

* The 46 transitively-heavy modules are **not** declared and still copy
  everything. Their exclusion comes from import analysis, which the manifest
  comment forbids as proof — it is used only to avoid spending 46 × ~70 s on
  runs whose outcome the batch already demonstrated once.
* `test_runner.py` is not deleted, renamed or changed; this ticket only stops
  selecting it as a pattern.
* No test was edited, skipped or removed. Every module's `ran` is identical.
* The 55-red full-suite baseline is untouched: this changes which bytes a
  focused sandbox copies, never what a test asserts.

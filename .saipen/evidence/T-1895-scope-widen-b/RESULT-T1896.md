# T-1896 — the last 45 filtered modules, and why the filter was wrong twice

T-1895 excluded 46 modules as "transitively heavy" on the strength of import
analysis. This ticket shows that exclusion was wrong, and proves the 45 real
test modules among them instead.

## The filter was wrong in both directions

The first filter flagged any module whose own text contained the substring
`saipen`. That caught engine imports like `from saipen_engine.test_runner import
TestFamily` — 46 false positives.

The second filter flagged any module importing a helper whose text mentions
`.saipen`. That also failed, for the reason the manifest comment already states:
**a path literal in a helper is not a read of the project tree.**

* `test_hermetic_env.py` mentions `Path.home() / ".saipen" / "authority"` — a
  path under the *test machine's home*, not the project being tested.
* `test_t1844_origin_broker.py` writes `self.root / ".saipen/STATE.md"` where
  `self.root` is its own `TemporaryDirectory`.

A strict re-scan of all 375 modules that `grep` says touch `.saipen` found the
same thing: almost every hit is a fixture constructing its own project, not a
read of this repository. **Static inspection does not decide this.** Only the
run does.

One module among the 46 is genuinely unusable as a pattern:
`test_operator_origin_support.py` defines classes but collects **0 tests** (it is
a helper others import). Tried under a narrowed scope it still collected 0 and
`focused` correctly stopped the batch. It is excluded, not declared.

## Proof: per-module `ran`, FULL against narrowed

Same 45 modules, same three batches, same tree, same unittest command.

| batch | modules | FULL ran | narrowed ran | FULL wall | narrowed wall | copy FULL → narrow |
|---|---|---|---|---|---|---|
| 1 | 15 | 143 | 143 | 293.0 s | 198.0 s | 53.0 s → 0.41 s |
| 2 | 15 | 135 | 135 | 202.7 s | 126.4 s | 52.8 s → 0.38 s |
| 3 | 15 | 133 | 133 | 132.5 s | 58.1 s | 50.4 s → 0.39 s |
| **total** | **45** | **411** | **411** | **628.2 s** | **382.5 s** | — |

`compare.py` reports `VERDICT EQUAL` on all three batches: zero patterns on only
one side, **zero `ran` mismatches, zero red-set changes**. The 411 tests are the
same 411 tests.

The wall gain here is smaller (39.1%) than in T-1894/T-1895 because these
modules do heavy work of their own — one batch spends 224 s executing. The copy
still collapses from ~52 s to ~0.4 s, which is the part this ticket owns.

## Final state

`tools/sandbox_scope.json` now declares **108 modules**. Of the 511 test modules
in `tools/`, the rest still copy the full tree by default, which remains the
fail-closed behaviour T-1889 specified.

## What is NOT claimed

* No test was edited, skipped or removed; every module's `ran` is identical.
* `test_operator_origin_support.py` is untouched — it is simply not selected as
  a pattern, because it has no tests to run.
* The 55-red full-suite baseline is untouched.
* The remaining undeclared modules are NOT declared here. Some of them really do
  read project history, and each needs its own narrowed run as evidence.

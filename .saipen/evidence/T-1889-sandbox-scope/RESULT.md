# T-1889 — a focused sandbox copies what its subject declared

**Status:** implemented and verified. Phase ladder SCOUT → BUILD → VERIFY → REVIEW → SHIP.

## The measured cost this removes

A focused gate on this tree spent 54-60 s of a 71-80 s run copying the sandbox:
1815 MiB in 135450 files, of which `.saipen` was 1474 MiB and `.git` 345 MiB,
while the selected tests executed in 1.5 s. Excluding both plus `audit` copied
21 MiB in 0.53 s.

## Why narrowing does not weaken what a PASS claims

`core_unit.tree_fingerprint` already excludes `.git` and `.saipen` at the top
level (`FINGERPRINT_EXCLUDED`). A record never attested those bytes, so not
copying them preserves exactly the file set the record describes. The source
tree — `tools/`, `tests/`, `saipen/`, `bootstrap/`, `extensions/`, the root
files — is copied in both modes, always.

## What was built

`tools/saipen_engine/sandbox_scope.py` (new):

- `SCOPE_REL = "tools/sandbox_scope.json"` — a tracked manifest beside the
  tests, like `verification_policy.json`.
- `resolve(root, patterns)` — **all** patterns must be declared for a narrow
  copy; one undeclared pattern makes the whole run FULL, because one sandbox
  holds one snapshot.
- `copy_plan(scope)` → `(extra_top_trees, allowed_saipen_children)`.
- `identity(scope)` — `{mode, trees}`; deliberately excludes the manifest
  digest, so editing an unrelated module's entry does not invalidate records.
- `is_current(recorded, current)` — the reuse guard.

`core_unit.py`:

- `copy_tree_consistent(..., scope=None)` — `None`/FULL is the pre-existing
  behaviour; DECLARED drops undisclosed top-level `FINGERPRINT_EXCLUDED` trees
  and undisclosed `.saipen` child directories.
- `_only_saipen_subtrees()` — filters only child **directories**; the canonical
  top-level files are always copied, because project resolution reads them.
- `copy_metrics` gains a `trees` field (`None` = everything).

`focused_unit.py`:

- `run_focused` resolves the scope, passes it to the copier, and records it as
  `sandbox_scope`.
- `configuration()` folds `sandbox_scope` into the verification identity, so a
  narrow record cannot be replayed for a different copy decision (INV-20).
- `record_problem` refuses a record whose decision no longer matches the
  manifest, and refuses a pre-T-1889 record once a manifest narrows.

## Fail-closed properties, all pinned by tests

| Condition | Behaviour |
|---|---|
| No manifest | FULL — the pre-existing behaviour |
| Module absent from manifest | FULL |
| One of several patterns undeclared | FULL for the whole run |
| Malformed / wrong-schema manifest | `ScopeError` refusal |
| Entry naming a missing subtree | `ScopeError` refusal |
| Entry that would drop subject (`tools`, `.saipen`, `audit`, `../`) | `ScopeError` refusal |
| Recorded decision ≠ current manifest | reuse refused |
| Pre-T-1889 record under a narrowing manifest | reuse refused |

## The A/B measurement

`.saipen/evidence/T-1889-sandbox-scope/ab-copy.py`, log beside it. Same tree,
same copier, only `scope` differs:

| Arm | Wall | Files | Size | `.git` | `.saipen` children |
|---|---|---|---|---|---|
| FULL (pre-T-1889) | 51.4 s | 132904 | 1793.1 MiB | yes | all 17 |
| DECLARED (source only) | 0.39 s | 1210 | 22.4 MiB | no | none |

Delta 51.0 s on identical bytes; size ratio 0.0125. The file counts differ
because the heavy trees are precisely what was dropped — that is the subject of
the measurement, not drift.

End-to-end, on the real gate command:

| Run | Scope | Tests | Duration |
|---|---|---|---|
| three patterns, third undeclared | FULL (fail-closed) | 22 | 74.7 s |
| three patterns, all declared | DECLARED | 22 | 5.8 s |

Both PASS. The 74.7 s run is the fail-closed default working as designed: my
own new test module was not yet declared, so the run copied everything.

## The red control

`.saipen/evidence/T-1889-sandbox-scope/red-control.py`. **It is a mutation
control, and that is stated rather than glossed:** `focused_unit.py` is an
intent-to-add index entry here (index blob 0 bytes, `git diff --cached` empty,
`git show HEAD:...` → "exists on disk, but not in 'HEAD'"), so there is no
git-recorded pre-fix baseline to fetch. Inventing one would be worse than
declaring the limitation.

The mutation makes `resolve` treat every module as undeclared: the manifest
parser, the copier and the record wiring all stay intact. Result:

```
FAILED (failures=4, errors=1)   Ran 12 tests
```

- `test_a_declared_module_copies_no_history` — `.git` arrived anyway
- `test_a_declared_history_reader_still_sees_evidence` — undeclared subtree arrived
- `test_the_decision_is_in_the_evidence_record` — record said FULL for a declared module
- `test_the_declaration_is_load_bearing_for_a_real_reader` — the starved arm passed, the false green the test exists to catch
- `test_a_record_from_a_narrower_copy_is_not_reused_after_a_new_declaration` — error, scope guard unreachable

Every fail-closed test stayed green, which is correct: they do not depend on the
decision being honoured, only on bad input being refused.

## The load-bearing control

`test_the_declaration_is_load_bearing_for_a_real_reader` runs one real test
module through `run_focused` twice. Declared with `.saipen/evidence`, it passes.
Declared with `[]`, it FAILS — the sandbox genuinely lacks the file. That is
what makes the manifest a contract rather than a comment: a wrong entry is a
red gate, not a silent pass.

## Regression surface

`tools/test_t1889_sandbox_scope.py` — 12 tests, green. Neighbours run together:
`test_t1836_verification_impact`, `test_core_unit_gate`,
`test_t1779_family_ignores_inbox`, `test_t1830_verification_observations` —
77 tests, OK.

`test_t1828_verification_policy.PublicationWiringTests.test_release_executor_refuses_before_external_validator`
fails, and it is **pre-existing**: the 55-red record
`.saipen/evidence/core-unit/0ade2cd4b0d85ad8-20261024T142656492584Z.json` lists
it by exact id. `release.py` calls no `publication_gate` at HEAD, in the index
or in the working tree.

Lint: my four files are clean. `ruff check tools/ tests/` reports 24 errors,
all in foreign uncommitted work (`operator_origin`, `host_authority_*`,
`test_t1859`, `test_t1868`, `test_t1792`, `saipen.py`, `verification_cache`,
`install_host_guard`). One of them was in `core_unit.py`'s `ship_gate`
environment-identity hunk, which this ticket did not author; it was a pure
line-wrap with no behaviour change, made because a whole-surface lint gates
REVIEW.

## What is NOT claimed

- The full family is not green; the 55 baseline reds are untouched.
- Only three modules are declared. The other 509 copy everything, exactly as
  before. Widening the manifest is per-module work, each needing its own
  narrowed run as evidence — never an inference from imports.
- No claim that a narrowed sandbox is correct for a module that was not run in
  one. That is the whole point of the fail-closed default.
- Copy cost was measured on this tree at this size; the ratio will differ
  elsewhere, and the numbers above are the ones measured, not projected.

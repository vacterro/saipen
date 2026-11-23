# T-1974 -- the nine working-tree-only files under tools/

Measured 2026-10-31T04:48:20Z.

## What the gate said, and what is actually true

`validate.py --gate core` reported nine `runtime manifest names a file git does not track`.
The manifest copies the whole `tools/` tree (`saipen/MANIFEST.json` copy_trees: src `tools` -> dst `tools`),
so every file on disk under `tools/` becomes a manifest member by construction. The nine:

| file | bytes | in HEAD |
|---|---|---|
| `tools/saipen_engine/identity_audit.py` | 29347 | no |
| `tools/test_t1443_basetemp_transience.py` | 4727 | no |
| `tools/test_t1443_identity_audit.py` | 22140 | no |
| `tools/test_t1952_sandbox_points_at_itself.py` | 7241 | no |
| `tools/test_t1953_suite_reuse.py` | 9705 | no |
| `tools/test_t1961_pruned_slice.py` | 4858 | no |
| `tools/test_t1967_qualification_provenance.py` | 14608 | no |
| `tools/test_t1968_foreign_protocol_route.py` | 7761 | no |
| `tools/test_t1969_finding_revision_identity.py` | 8674 | no |

## The dependency question the gate asked first

Committing an untracked test whose runtime subject is itself uncommitted trades one local
FAIL for a red suite in every clone (T-1592). So each file was parsed with `ast` and every
`ImportFrom`/`Import` module resolved against `git cat-file -e HEAD:<path>`:

```
only stdlib resolved as absent (__future__, pathlib, datetime, dataclasses, unittest).
Every in-repo module these nine import is already at HEAD, including
saipen_engine.audit_manifest (blob a390a73d) which the advisor named as missing.
```

## The advisor has a false-positive class

`_uncommitted_symbols` (validate.py:593) was called twice for `test_t1443_basetemp_transience.py`.
It reports `saipen_engine.audit_manifest` even though that module is in HEAD. The parser
treats `from saipen_engine import audit_manifest` as "the symbol `audit_manifest` inside
`saipen_engine/__init__.py`", but it is a SUBMODULE import; `__init__.py` never names it.
The same shape produces `saipen_engine.as` and `saipen_engine.SR` for alias imports.
This is advisory only -- it attaches a warning beside an existing FAIL -- so the nine
FAILs were correct and the nine warnings were partly noise.

## Each file runs green in this tree

| module | result |
|---|---|
| tools.test_t1443_basetemp_transience | Ran 10 tests, OK |
| tools.test_t1443_identity_audit | exit 0, provenance HOLDS |
| tools.test_t1952_sandbox_points_at_itself | Ran 6 tests, OK |
| tools.test_t1953_suite_reuse | Ran 11 tests, OK |
| tools.test_t1961_pruned_slice | Ran 6 tests, OK |
| tools.test_t1967_qualification_provenance | Ran 10 tests, OK |
| tools.test_t1968_foreign_protocol_route | Ran 15 tests, OK |
| tools.test_t1969_finding_revision_identity | Ran 4 tests, OK |

## What was done

All nine staged by explicit path (no `git add .`, no `git add -A`), consistent with the
enumerated staging T-1972 established for this index. Measured effect:

| gate | before | after |
|---|---|---|
| `validate.py --gate core` | 10 problems | **1 problem** |

The remaining failure is not this subject: EX-000029's closure provenance records engine
generation `06c1149a...` while the running engine is `6f2cd4c3...`. That is T-1973.

## Correction: the external bytes did NOT move (measured after the first draft)

This note first said `SaiAccounts.cs` had moved, reading `f9cffd24...` from the
`__SAITULS` working tree and `d771f95c...` from the receipt. That was wrong, and the
wrong version was written before the check that distinguishes the two:

```
$ git -C V:/___VAC/__K/__CODE/__SAITULS rev-parse HEAD:Scripts/accounts/SaiAccounts.cs
0eac11caef25dd4308af881ed99281a7501af8f8
$ git -C ... rev-parse d93b212f:Scripts/accounts/SaiAccounts.cs
0eac11caef25dd4308af881ed99281a7501af8f8        # same blob
$ git -C ... show HEAD:Scripts/accounts/SaiAccounts.cs | sha256sum
d771f95c48ece2c0...                             # exactly the receipt's digest
$ git -C ... show d93b212f:Scripts/accounts/SaiAccounts.cs | sha256sum
d771f95c48ece2c0...                             # same
$ git -C ... status --porcelain -- Scripts/accounts/SaiAccounts.cs
 M Scripts/accounts/SaiAccounts.cs              # the f9cffd24 bytes are UNCOMMITTED
```

The committed external implementation is identical at the carrying commit `d93b212f` and
at `__SAITULS` HEAD `555911f`, and its content digest is the one the receipt records.
`f9cffd24...` is an uncommitted edit sitting in another repository's worktree.

That matters for T-1973 because `capture()` compares `_read(upstream, rel)` — the
WORKTREE bytes — against `git show <commit>:<rel>`. So an unrelated dirty file in a
different repository invalidates this project's external closure, and the gate's
"external implementation differs from its carrying commit" is true of the worktree
while false of every immutable artifact. Both facts belong in T-1973; neither is a
reason to weaken the predicate here.

## The family run caught a regression this ticket caused

The first core-unit family run over the staged tree reported two NEW red tests:

```
test_t1592_manifest_orphan_advice.OrphanDetectionTests.test_a_self_contained_test_reports_nothing
test_t1592_manifest_orphan_advice.OrphanDetectionTests.test_a_symbol_absent_from_head_is_named
```

Both were `NameError: name '_imported_names' is not defined`. T-1592 executes
`_uncommitted_symbols` by slicing its source, from `def _uncommitted_symbols` to the next
`def` — correct only while the function is self-contained, which it was until this ticket
made it call two helpers. The nine files were green and the pair was green; only the
whole-family run saw it. Had it shipped, every clone would have been red.

The loader now follows an explicit dependency list, and every assertion in that file is
unchanged (`diff` touches only `_run_uncommitted_symbols` and adds `_HELPERS`):

```
before  FAIL  11 of 13 ran, 0 skipped
after   PASS  13 of 13 ran, 0 skipped     same verifier 6f30684d...
```

Pre-fix bytes are kept beside this note as `prefix-t1592-orphan-advice.py`
(`5cde0812...`); current is `_HELPERS`-aware. One contract, both changed files as
subject, `tools/test_t1974_manifest_orphan_symbols.py` as the only oracle.

## Honest limit

The nine-file half of this ticket is a staging decision, and staging cannot be
regression-tested: `.saipen/` and `.git` are refused as execution subjects by
`regression_execution._paths`, so no pair can be formed over them by design. The
measured pair above covers the CODE half only (the two defects and the loader). The
staging half is evidenced by the gate transition 10 -> 1, which is a measurement any
reader can repeat.

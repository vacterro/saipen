# Board

## DOING

## TODO

## DONE
- [x] PY-017 Re-verify the T-2062 GC serialization patch at tree c9c3e86c | verify: kitchen/PY-17.md; baseline GC_MAINTENANCE_FAILED, patched 8/8 rounds and GC suite 63 OK (1 skipped); apply check PASS
- [x] PY-015 Prepare a pen-only serialization patch for the concurrent T-2062 GC checkpoint failure | verify: kitchen/PY-15.md; 8/8 concurrent rounds pass; GC suite 63 PASS, 1 skipped; apply check PASS
- [x] PY-014 Prepare T-1347 timeout-detector patch in pen | verify: kitchen/PY-14.md; 10 tests, 0 failures, 1 opt-in skip; red control; Ruff; apply check
- [x] PY-009 post-PY-8 Python hygiene sweep -- Ruff clean; no Python patch warranted
- [x] PY-008 make improve admission drift check formatting-invariant | verify: PY-8 patch apply check, Ruff, and validator admission gate pass
- [x] PY-001 lint + type hygiene -- deferred; no runtime impact
- [x] PY-002 small correctness bugs -- deferred; no runtime impact
- [x] PY-003 missing error paths -- deferred; no runtime impact
- [x] PY-004 dead code -- deferred; no runtime impact
- [x] PY-005 docstring + type-hint gaps -- deferred; no runtime impact
- [x] PY-018 re-verify T-2062 GC serialization patch at tree 1a368781: baseline WRITER_BUSY reproduced, 8/8 patched rounds and 63-test GC suite green | verify: kitchen/PY-18.md; apply check exit 0; patched gc.py sha256 9fab03b3; suite Ran 63 OK (skipped=1)

- [x] PY-006 clear current Ruff gate -- 89 diagnostics to 0 in pen; tested unified diff ready
- [x] PY-007 recut Ruff repair after T-1115 -- 89 diagnostics to 0; recovery fix preserved; tested root-relative diff ready

## BLOCKED

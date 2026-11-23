# T-1515 independent continuation review

The current criterion distinguishes the POSIX shell command_form from the
Win32 argv_prefix and proven programmatic exec_prefix. The carrying launcher
repair is commit 423dfed4; this continuation strengthens the native verifier.
Reviewed paths: tools/saipen_engine/entry_resolver.py and
tools/test_t1515_posix_shell_entry.py.

Independent native neighbors: 53 PASS, zero SKIP, 48.395 seconds, recorded in
REVIEW-takeover-neighbors.stderr. The unchanged six-case paired oracle
6f40117e693ec19c08914e75b47d1af3d41209fb953ee8e149ca80404e83ca1f still detects
the original production defect, including injected.txt --json. Current
production passes six native cases with zero skips and exact successful query
transport. Raw original/current results are REVIEW-takeover-original.json and
REVIEW-takeover-current.json; earlier input records are preserved separately.
This verifier refuses failed shell execution and altered query text.

The current canonical full-family record remains fingerprint 897f117d9995d092,
4897 run, 4839 PASS, zero FAIL/ERROR and 58 separately reported skips. No product
source changed during these accepted executions. Ruff 0.16.0 and whitespace
checks pass. Canonical core validation minted CURRENT_PASS receipt-be1def0cc49f,
zero blocking findings and 31 warnings (REVIEW-takeover-core.json).

No P0/P1 finding. Memory promotion: NO; existing verifier-integrity knowledge
covers this lesson. Pending C-004 evidence closure is authorized; release
publication remains excluded by the controlling source.

## Resumed review, 2026-10-03 23:58 UTC

The recorded independent review and SHIP verdict were retained. The resumed
native transport check ran six tests in 0.286 seconds with no failures or skips.
The live tree now has fingerprint
e7acc6aa3b764ccee16a51bafc44500e5375d10fad93be61a373ee599498ec70,
so the earlier whole-family receipt was not treated as current proof.

The canonical six-shard runner completed a fresh family against that tree:
4897 tests ran, red 0, new_red 0, no leaked sandboxes. Its durable record is
.saipen/evidence/core-unit/e7acc6aa3b764cce-20261003T235746Z.json.
The product tree remained frozen through completion. Canonical core validation
then minted CURRENT_PASS receipt-b645d19fe2e6, zero blocking findings and
31 warnings. This continuation adds no P0/P1 finding and no implementation
delta beyond the reviewed native verifier. Pending C-004 closure remains the
authorized action; publication remains excluded.

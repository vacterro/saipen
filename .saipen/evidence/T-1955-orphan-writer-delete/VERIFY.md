# T-1955 VERIFY -- four claims, each executed

## Claim 1: `record_producer_integration` has zero hits under `tools/`

```
$ git grep -n "record_producer_integration" -- tools/
ZERO hits
```

**PASS.**

## Claim 2: `_plan_producer_integration` has zero hits under `tools/`

```
$ git grep -n "_plan_producer_integration" -- tools/
ZERO hits
```

**PASS.**

## Claim 3: the live `producer_integration` path still passes its own coverage

The live writer is `producer.py:2155`, a `run_mutation` call with
`op_id = "producer-integrate-" + identity[:32] + "-" + base_head[:12]`. The
cluster that covers it, plus the reachable neighbour the delete sits beside:

```
$ python -B -m unittest tools.test_v7_producer_parallelism \
    tools.test_producer_terminal_consistency tools.test_producer_gate_policy \
    tools.test_t1430_crew_run_receipt -v
Ran 75 tests in 30.525s
OK

$ python -B -m unittest tools.test_t1577_op_id_provenance \
    tools.test_t1746_crew_terminal_outcome tools.test_intent_audit_fixes \
    tools.test_t1561_probe_fixture
Ran 126 tests in 72.687s
OK (skipped=3)
```

`test_t1746_crew_terminal_outcome` asserts the real receipt shape
(`integration_op == "producer-integrate-fixture"`), `test_v7_producer_parallelism`
reads committed `producer_integration` receipts through
`semantic_receipts_for_operation`, and `test_intent_audit_fixes` pins the live
`integration_op_id`. All green with the orphan gone. **PASS.**

## Claim 4: a red control records that the two symbols existed before the delete

The pre-delete bytes are kept as `prefix-operations.py` (`git show
HEAD:tools/saipen_engine/operations.py`, 571,073 bytes):

```
record_producer_integration occurrences: 1
_plan_producer_integration occurrences: 2
def record_producer_integration(: 1
def _plan_producer_integration(: 1
```

Post-delete, from the same counter on the working tree: `0` and `0`.
**PASS** -- the red control is the actual prior bytes, not a claim about them.

## A real finding this VERIFY produced: the delete was incomplete

The first cluster run was **red**:

```
FAIL: test_every_registered_class_has_a_live_writer
  (test_t1577_op_id_provenance.RegistryCoversEveryWriter)
AssertionError: Lists differ: ['producer-integration-'] != []
```

`journal.OP_CLASSES` still registered `producer-integration-` as an op-id class
a writer mints. That test is the registry's converse: a class earns its place
only by a writer that mints it today, precisely so the registry "can neither be
padded with a hand-typed class nor keep one whose writer is gone"
(`test_t1577_op_id_provenance.py:328-333`). Deleting the only writer made the
registry row a lie, and the delete was therefore incomplete until the row went
with it.

Fixed in the same ticket: `journal.py` loses the `"producer-integration-",` row
(one line, `tools/saipen_engine/journal.py:486`). Evidence that removal is safe
rather than merely convenient:

- No op id of that class exists anywhere in this repository's history:
  `grep -rn "producer-integration-[0-9a-f]\{8\}" .saipen/` returns nothing, and
  no `.saipen/recovery/ops/` directory carries the prefix.
- The only occurrences of the literal in the tree are prose about the class
  (`intent.py:962`, T-1954/T-1955 evidence), not id-carrying records.
- `_OP_ID_GRAMMAR` is compiled from the registry, so removing the row narrows
  what `op_id_provenance` will call `canonical` -- it cannot retroactively
  change any existing LOG line, because no LOG line carries one.

Red control for this second edit is the same run: with the row present, the
converse test fails naming exactly `['producer-integration-']`; with it gone,
`test_t1577_op_id_provenance` is green (part of the 126-test run above).

## Validator

```
$ python -B tools/validate.py
Validation FAILED: 1 problem(s), 16 warning(s)

FAIL: closure provenance does not resolve: EX-000022 ...
Scripts/accounts/SaiAccounts.cs
```

The single FAIL is the pre-existing `EX-000022` external-closure drift
(installed generation `fbbb910716437391` vs running `a057d164a2c5ea0b`, and an
external implementation differing from its carrying commit). It is the same
FAIL that blocked commit before this ticket and is unchanged in kind by it. The
warning set gained the two expected `producer-package-stale` lines for W-052 and
HUNT-016, because editing `operations.py` and `journal.py` moved the tree
fingerprint past both packages' binding -- correct behaviour, and it is the
operator-gated `qqq`/collect path those packages await, not this ticket's work.

## Declared family gate

`python tools/core_unit.py evidence T-1955` -- recorded below once the sweep
completes; the tree moved, so the T-1954 record is not reusable and this is a
full run.

# T-1588 BUILD evidence — the fixture named one checkout, the family runs another

## The red

Three `test_t1412_conformance_truth` controls pass individually on the live tree
and red inside the declared core-unit family, where every test runs from a
sandbox copy. No single-seat run reproduces it.

## How the cause was isolated

Three hypotheses were ruled out by experiment, not by argument:

1. **Shard co-tenancy.** The exact 83-module shard-1 set, run as one process,
   passes: `Ran 952 tests ... OK`.
2. **Full-tree import.** The shard runner calls `super().discover(...)`, which
   imports every module in the tree and then keeps only the shard's. Running
   t1412 alone under that full import passes: `Ran 10 tests ... OK`.
3. **Concurrency.** With 1 and 2 eliminated, the remaining difference between
   the passing and failing runs is the tree itself. Copying the repo to a
   sandbox and running the same shard there reproduces it exactly.

(One false start is worth recording: the first sandbox repro failed on
`cross-doc drift [root-file-set]` over `_spec.json` / `_manifest.json` — my own
scratch files, written into the sandbox root by the reproduction itself. The real
runner keeps its spec in a separate work directory. Removed, and the sandbox
reproduced the real three.)

## The cause

`T1412Base`'s `_STATE` template hardcoded one absolute path:

    saipen_home: "V:\\___VAC\\__K\\__CODE\\_AI_STUFF_AGENTIC\\_SAIPEN"

`saipen validate` refuses `VALID` when the RUNNING install and the install
`STATE.saipen_home` names are different installs answering to the same VERSION.
From the live checkout the two are the same directory, so the check is silent.
From the family sandbox the running install is `V:\_TEMP_\saipen-core-unit-*`
and STATE names the author's checkout, so every `validate` returns:

    "code": "INSTALL_IDENTITY_MISMATCH"
    "mismatch": "the RUNNING install is V:\\_TEMP_\\... but STATE.saipen_home
                 names V:\\___VAC\\__K\\__CODE\\_AI_STUFF_AGENTIC\\_SAIPEN"

The canonical validator itself is fine — the receipt in the failing payload reads
`"status": "CURRENT_PASS"`, `"verdict": "PASS"`, `exit_code 0`. The install
identity gate refuses VALID on top of a passing validator, which is exactly what
it exists to do. The defect is the fixture, not the gate: a fixture that names
one author's checkout is only valid in that checkout.

`___VAC` appears in exactly one place in the whole test corpus, so the defect is
contained to this one line.

## The fix

`tools/test_t1412_conformance_truth.py` derives the value from the install the
test is running from:

    _SAIPEN_HOME = str(ROOT).replace("\\", "\\\\")

`ROOT` is already `TOOLS.parent`, i.e. the running install. In the author's
checkout the emitted line is byte-identical to the old hardcoded one — which is
why the test passed there and gives nothing away — and in a sandbox it names the
sandbox.

## Red / green control, same sandbox, same runner

| file | result |
|---|---|
| pre-fix (`git show HEAD:tools/test_t1412_conformance_truth.py`) | `Ran 10 tests ... FAILED (failures=4)`, `INSTALL_IDENTITY_MISMATCH` |
| post-fix | `Ran 10 tests ... OK` |

The pre-fix failure belongs to the verifier that now passes, and that verifier
still sees the original bug when the file is reverted (VERIFY-ORACLE-01).

## No assertion weakened

No `assert*` line was touched, no test skipped, no timeout raised, and the
install identity gate itself is untouched. Only the fixture's idea of "where am
I" changed, from a literal to the truth.

Standalone in the live tree, post-fix: `Ran 10 tests ... OK`.

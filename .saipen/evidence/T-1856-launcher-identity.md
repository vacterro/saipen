# T-1856 — verification identity must not follow the launcher spelling

Status: delivery complete; publication blocked by the operator's pre-staged batch.
Owner: saipen-cli. Ticket: T-1856 [P1]. Filed while closing T-1815.

## The measured defect

While trying to satisfy T-1815's SHIP gate I hit a contradiction: the focused
record the engine had just written was accepted by one invocation and refused by
another, on an unchanged tree.

| Invocation | Result |
| --- | --- |
| `saipen transition SHIP T-1815` (PATH shim, execs `python.EXE`) | `INCOMPLETE_TICKET` — `focused check has missing or incompatible verification environment identity` |
| `python tools/saipen.py transition SHIP T-1815` (same tree) | `TRANSITIONED`, op `transition-8ef30f3361f84ad0a3739421d5470b5e` |

The record was `.saipen/evidence/focused-unit/ee1a8bbd8d49eda5-20261022T160119496857Z.json`,
verdict PASS, 64 tests, fingerprint `ee1a8bbd8d49eda5…`, and the tree fingerprint
still matched it exactly.

## Root cause

`verification_cache.capture` hashes the whole canonical child environment into
`environment_sha256`. That environment is built by `test_runner.family_environment`
from `os.environ`. Bash maintains `_` as the last argument of the previous
command, so the name carried the interpreter spelling of whatever launched the
process:

```
lower ("python")     _ = C:/Users/vac34/.../Python311/python
upper ("python.EXE") _ = C:/Users/vac34/.../Python311/python.EXE
```

Measured directly: the two captured identities differed in exactly one key,
`environment_sha256`, and once `_` was removed from both dictionaries their
digests were equal. Nothing in the child's behaviour depends on `_`, so the
identity was hashing the invocation instead of the subject.

This is the same class T-1834 closed for the per-tool-call carriers
(`CODEX_TOOL_CALL_ID`, `PROMPT`): evidence identity must follow the tested
generation, never the shell that started the run.

## The fix

`tools/saipen_engine/test_runner.py`, one owner:

```python
SHELL_BOOKKEEPING_ENV = frozenset({"_"})
...
    for key in ("SAIMAIL_WORKSPACE", "ZAICODE_HOME", "CLAUDE_CONFIG_DIR", "PYTHONPATH",
                *VERIFIER_DIAGNOSTIC_ENV, *SHELL_BOOKKEEPING_ENV):
        env.pop(key, None)
```

The list is deliberately narrow and asserted as such in the test suite: adding a
real carrier here would hide genuine drift. The comment names the measurement and
the class so the next reader does not treat the name as arbitrary.

## Verification

`tools/test_t1856_launcher_identity.py` — 6 tests, all pass (14.5 s):

- the child never carries the shell's last argument, for both spellings;
- two launcher spellings capture one identity (the exact T-1815 measurement);
- **red control**: a real environment change (`SAIPEN_TEST_MODE`) still
  invalidates the identity, so the rule is not a no-op;
- the rule names exactly `{_}`;
- a real execution through `_run_family` shows `os.environ.get('_')` is `null`;
- an identity captured under one spelling is `compatible` under the other.

**Red control executed with the fix disabled** (`SHELL_BOOKKEEPING_ENV` patched to
`frozenset()`): 3 of 3 selected tests fail, reporting
`['environment_sha256']` as the single differing key and the child environment
still containing `'_': '…python.exe'`. So the tests fail for the stated reason on
the pre-fix code, not merely because they are new.

Focused gate: `python tools/core_unit.py focused T-1856` with
`test_t1856_launcher_identity.py`, `test_t1834_tool_call_identity.py`,
`test_t1832_single_flight.py`, `test_t1828_verification_policy.py` →
**PASS, 42 tests**, record
`.saipen/evidence/focused-unit/070eb54d747ac5ec-20261022T164919536237Z.json`.

Related-cluster regression (unchanged before/after): 115 tests across
`test_t1832_single_flight`, `test_t1833_verification_owner`,
`test_t1834_tool_call_identity`, `test_t1835_verification_economics`,
`test_t1836_verification_impact`, `test_core_unit_gate`,
`test_t1828_verification_policy` → OK (9 skipped).

`ruff check` clean on both changed files.

## Deliberately not done

- No change to `paths.PROJECT_BINDING_ENV`. `_` is not a project binding; it
  cannot be, since it names no project. Stripping it belongs where the canonical
  child environment is owned.
- No weakening of the compatibility check. Existing records written before this
  fix carry the old `environment_sha256` and will not compare equal; that is the
  correct conservative outcome (the fix makes future records comparable, it does
  not retroactively authenticate old ones).
- No attempt to publish. `saipen ship` refuses because 206 foreign paths are
  pre-staged in the shared tree — the operator's in-flight batch.

## Publication

`saipen ship` → `VALIDATION_FAILED: foreign pre-existing staged path(s) would
enter this release` (the same 206-path set T-1815, T-1816 and T-1817 report).
Recording the truthful block; resuming SHIP requires the operator to commit or
clear that staged batch.

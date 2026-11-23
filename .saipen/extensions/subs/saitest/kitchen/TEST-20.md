# TEST-20 -- bounded host/runtime test sweep at dc39709c / tree 0f69fe84

- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:0f69fe84ecb98bfc84e2c33be0bb35ef7310de8bbd75c223f7d6b77232be14d2
- role_revision: sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08
- method: five bounded scenarios, each a real command at the declared identity;
  no main-project write.

The tree moved from cf7cd4a7 (TEST-19) to 0f69fe84 while HEAD stayed
dc39709c, so this pass re-measured the bounded test surface at the live
identity. The source identity excludes `.saipen` (T-1900 pathspec), so the
role's own writes do not move it.

## Scenario 1 -- host bootstrap, install identity, runtime home: PASS

```
python -m unittest tools.test_host_bootstrap tools.test_install_identity_doctor \
    tools.test_t1854_runtime_home
-> Ran 55 tests in 17.470s -- OK (skipped=1)
```

This is the same 55-case set the T-2039 review reproduced, unchanged at the
new tree.

## Scenario 2 -- T-2077 unblock-gate regression: PASS

```
python -m unittest tools.test_t2077_unblock_gate
-> Ran 4 tests -- OK
```

Both directions hold: a dependency hold whose tail mentions an operator token
lifts, and a genuine operator head still refuses with `WAIT_USER_DECISION` and
zero writes.

## Scenario 3 -- T-1430 crew-run receipt: PASS

```
python -m unittest tools.test_t1430_crew_run_receipt
-> Ran 5 tests -- OK
```

## Scenario 4 -- refusal registry and generation binding: PASS

```
python -m unittest tools.test_refusal_registry tools.test_t2077_unblock_gate \
    tools.test_t2076_installed_generation_binding
-> Ran 17 tests -- OK
```

The group includes the T-2077 module again; the registry and
installed-generation-binding controls are green at this tree.

## Scenario 5 -- conformance gates: BOTH RED, classes owned

- Installed canonical gate: `CONFORMANCE_UNHEALTHY`, `CURRENT_FAIL`,
  `Validation FAILED: 2 problem(s), 16 warning(s)`; structural gate pass,
  install identity MATCH, repair `ENGINEERING_REQUIRED` with
  `engine_work_count: 0`, `operator_action_count: 0`. Both problems are the
  installed pre-fix generation gaps (audit-route; FG-0046/T-1936), carried
  only by the T-2058 install route.
- Repo-generation gate: exit 1, `Validation FAILED: 31 problem(s), 39
  warning(s)`, all 31 the untracked runtime-manifest class under
  T-1449/T-2058/T-2052/T-2040. The same run warns that the saiwiki OUTBOX
  package W-051 is stale (fingerprint f6e0d368 against the live 0f69fe84).

Scenario 5 is a faithful negative: the bounded suites are green while the
canonical conformance state is red for the owned classes. This package is
evidence, not a conformance verdict.

## Limits

- Five scenarios only; the repository harness was not run as a whole.
- The installed-gate findings are generation gaps, not live repo defects.
- No main-project file was written; all captures are inside
  `saitest/kitchen/`.

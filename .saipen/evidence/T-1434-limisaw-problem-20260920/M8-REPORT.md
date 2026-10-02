# T-1434 / SRC-088 — Milestone 8 evidence: cross-shape regression and determinism

Date: 2026-09-21. Phase BUILD. Continuation of T-1434 (SRC-088).

Mission: prove no LIMISAW-specific magic was introduced; the recovered
primitives hold across synthetic shapes and a real second project, and the
broad protocol family is deterministic on ONE unchanged tree.

## M8.1 broad family, twice, on one unchanged tree

Run 1 and run 2 captured the SAME identity before their execution:

    HEAD         464003066fd9c21789500d1e9d61c80d989a2638
    tree_state   sha256(git status --porcelain)[:16] = 2d7122436b81f773
    engine sha256:06c6b72ba0a5dccf8... (tools/saipen_engine + saipen.py + validate.py + VERSION)
    ruleset      82e5e183ae8f0fd9

Both runs produced IDENTICAL per-suite results (rc + summary line) over the
17-suite family: all T-1434 suites and binding/guard neighbours green
(work reverify, reverify, source retirement, external resolution, improve
reconcile, remediation self-consistency, foreign observation authority,
T-1411, command routing, effect authorization, guard events, session binding,
guard admission, debt gate, T-1412 conformance truth, router closure
readiness) with exactly ONE nonzero rc, the recorded pre-existing
`test_check_inventory` 5-failure debt at fail site 17c1825e57d0436e.
No code, evidence or environment value changed between the runs.
Raw captures: `V:\_TEMP_\m8-run1.json`, `V:\_TEMP_\m8-run2.json`.

## M8.2 validator remediation self-consistency

`tools/test_remediation_self_consistency.py` ran inside the family (rc 0) and
was re-run standalone: 12/12 OK -- every actionable emitted remediation
resolves to a registered canonical command or a typed external action; no
dangling command shape. (Full audit in M5-REPORT.md.)

## M8.3 extra real read-only project

`_SAIPENVIEW` (15 strict Improve cycles of shared-engine history), observed
read-only from this A-ambient session under the M6 authority model:

- `saipen --project-root _SAIPENVIEW status --json` -> ok, phase DONE;
- `validate.py --gate core --no-receipt --project-root _SAIPENVIEW` ->
  `Validation complete. Agent is conformant.` (0 problems, 47 warnings);
- zero writes: the run used `--no-receipt`, no product file touched.

## Cross-shape index gate

`tools/test_t1434_cross_shape_index.py` (new): every recovered shape's
executable owner must exist. 2/2 OK.

| shape | executable owner |
|---|---|
| normal single-repo project | test_work_reverify_cli / successful reverify clears the defect |
| shared SAIPEN engine | live: LIMISAW M7 acceptance (M7-REPORT.md) |
| ticket satisfied by dependency upgrade | test_external_resolution / dependency rollback non-green |
| external protocol-home implementation verified locally | test_external_resolution / local defect fixed upstream |
| stale source with zero actionable requirements | test_source_retirement / empty stale source |
| source with actionable unresolved requirement | test_source_retirement / unknown+blocked refuse |
| strict Improve stale COMPLETE seat | test_improve_reconcile / stale supersedes onto fresh replacement |
| strict Improve externally blocked terminal seat | test_improve_reconcile / BLOCKED_EXTERNAL terminalizes |
| current-tree work reverify | test_work_reverify_cli / attested-only never cures |
| stale verification after tree changes | test_reverify / stale checkpoint not current-tree evidence |
| immutable historical evidence | test_work_reverify_cli / DONE+LOG bytes preserved |
| explicit foreign read-only observation | test_foreign_observation_authority / status observes foreign |
| wrong-project mutation refusal | test_foreign_observation_authority / mutation refused |
| validator remediation self-consistency | test_remediation_self_consistency (12/12) |

## Exit check

- cross-shape: every required shape has a living, individually runnable owner;
- determinism: two identical results on one unchanged identity, no excluded
  outputs involved;
- no LIMISAW-specific magic: shapes 2/13 are the real project, the rest are
  synthetic throwaway fixtures;
- supplementary real read-only acceptance: done without writes.

## Exact next action

Final T-1434 REVIEW over M1-M8 as ONE protocol-recovery feature set (not the
last diff), then truthful terminalization (local close/SHIP; no push/tag/
release), then automatic T-1361 resumption and the freshest roadmap.

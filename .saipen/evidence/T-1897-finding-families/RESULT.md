# T-1897 — the validator's own failures had no identity

## What was measured

Running the canonical validator on this repository:

```
python tools/validate.py --project-root . --gate core --findings-json <out>
```

then classifying its output through the engine's own `findings.classify`:

| | before | after |
|---|---|---|
| problems | 41 | 42 |
| distinct `finding_key` | **2** | **42** |
| `rule_id: "unclassified"` | **40** | **0** |
| distinct manifest paths | **0** | **39** |
| `finding_ownership.partition().unknown_count` | **40** | **0** |
| `engine_work_count` | 1 | 42 |

The 42 vs 41 is the new test file this ticket added, which is itself untracked
at measurement time; the set difference between the two runs is exactly
`tools/test_t1897_manifest_findings.py` added and nothing removed.

## The defect

`finding_key` is `sha256(rule_id|subject_kind|subject_id)[:16]`. Forty distinct
validator failures shared one key because all forty were:

- `rule_id: "unclassified"` — neither manifest failure nor closure-provenance
  drift nor coverage gap existed in the 23-entry rule table, and
- `subject_kind: "global"`, `subject_id: None` — the unclassified fallback
  hard-codes both.

So `finding_key` was `sha256("unclassified|global|")` forty times over, and
`finding_ownership.partition` — which maps *rule ids* to owner classes — had no
entry to look up and returned `UNKNOWN` for every one of them. The consequence
is not cosmetic: **fixing one untracked file could not change the reported
finding set**, because all 38 files were the same finding. Debt baselines
compare by `finding_key`, so per-file progress was invisible to the whole
debt engine.

A second, quieter defect rode along: `_normalized_detail` extracted ids with
`T-\d+|SRC-\d+|E-\d+` with no left boundary, so the literal `CORE-003` in the
provenance message yielded a phantom `E-003` and that became the finding's
`detail`. `CORE-004` yields `E-004`. Every message citing a CORE rule invented
an event id.

## The change

`tools/saipen_engine/findings.py`

- three rules appended to `_RULES`, in the shapes actually measured:
  `runtime_manifest_untracked` (subject = the offending **path**),
  `closure_provenance_drift` (subject = the **EX id**), `coverage_gap`;
- the id extractor gains `(?<![A-Za-z])` so an id must begin a token.

`tools/saipen_engine/finding_ownership.py`

- the three new rule ids map to `ENGINE_INTERNAL`. Each repair is one an agent
  performs: commit the file or drop the entry, re-verify the closure at the
  running engine generation, put the document under a check or exempt it. A
  separately gated *publication* does not change who owns the finding, and
  reading it as this one would hide the manifest defect behind the gate.

`tools/test_t1897_manifest_findings.py` — 9 tests. The load-bearing one is
`test_forty_distinct_manifest_paths_yield_forty_distinct_keys`, which is the
measured collapse stated as an assertion.

## Red/green control

`red-control.py` loads the archived pre-fix classifier and the working-tree
classifier through the same loader and runs the **same** assertions on each:

```
PREFIX  manifest_keys_40=False manifest_named=False coverage_named=False
        provenance_named=False provenance_subject=False legit_still_work=True
NOW     all True
CONTROL OK
VERDICT RED->GREEN
```

`legit_still_work` is the control: a family that was already classified
(`legacy_closure_evidence`, `subject_kind: work`, `T-1446`) is unchanged in
both halves, so the green is the new families and not a general loosening.

## What this does NOT claim

- The validator still reports 42 problems. This ticket makes each of them a
  **visible, separately trackable, engine-owned** finding. It does not make
  them go away, and it does not touch the publication blocker that keeps 39
  manifest paths untracked.
- `ruleset_fingerprint` changed (`d682e4a0…` → `9a47d608…`) and
  `RULESET_VERSION` stays 2. Every existing debt baseline now refuses
  comparison with `BASELINE_RULESET_CHANGED` rather than silently comparing
  incompatible keys. That refusal is the designed behaviour of a fingerprinted
  identity change; 97 snapshots were already at the current version, 464 older
  ones were already refusing. Fresh snapshots are captured automatically when
  work enters BUILD.

## Verification

- `python -m pytest` on the new module: 9 passed.
- The five affected modules together: **80 passed, 6 subtests** in 22.0 s.
- `core_unit.py focused T-1897` over the four directly impacted modules:
  **PASS, 45 ran**, 75.2 s, record
  `.saipen/evidence/focused-unit/123a2e7caef73b8d-20261024T224532472371Z.json`.

# Why core conformance is CURRENT_FAIL -- measured diagnosis

- measured: 2026-11-17T09:33Z (status --json snapshot .saipen/kitchen/_status_final.json)
- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:cf7cd4a7512b88c0b0f2e57a05d17aef9e41b432f907486635c87aa3ab53aa42
- conformance receipt: receipt-d78b8d47903c
- automation reason_code: conformance-remediation
- diagnostic kind: ENGINEERING_REQUIRED; engine_work_count 29, operator_action_count 0

## The whole red set is one rule: runtime_manifest_untracked

The canonical validator receipt names 29 blocking findings, all of the same
rule, all routed ENGINE_INTERNAL with route `saipen continue`:

| class | count | paths |
|---|---|---|
| engine modules/tools | 6 | tools/_t2040_experiment.py, tools/saipen_engine/discovery_providers.py, tools/saipen_engine/gc.py, tools/saipen_engine/outcome_truth.py, tools/saipen_engine/persistent_goal.py, tools/saipen_engine/source_reindex.py |
| tests | 23 | tools/test_gc.py and 22 test_t20xx_*.py files (full list: .saipen/kitchen/_manifest_untracked.txt) |

Measured with git: all 29 exist on disk; `git ls-files -- <all 29>` returns
zero paths. `git status --porcelain saipen/MANIFEST.json` is clean, so the
manifest is not dirty -- the repository simply never tracked the files.

## Why the manifest check fires on files it never names

`saipen/MANIFEST.json` (dict, keys description/managed_dirs/copy_trees/
files/phase_docs) lists `tools` in `managed_dirs`, and the validator requires
every file under a managed dir to be git-tracked (installed
tools/validate.py:6790-6835; rule identity in
tools/saipen_engine/findings.py:262-269). An untracked engine module under
`tools/` is therefore a red finding by construction, not a stale entry that
could be "dropped": the entry is a directory.

## Why this is not agent-repairable in this session

The validator's own message offers two repairs: "Commit the file or drop the
manifest entry". Measured against this session's binding:

1. **Commit** -- the 29 files are exactly the delivery surface T-2058 exists
   to settle. Committing changes HEAD (invalidating the convergence chain
   again), grows the divergence from origin/main, and is the publication act
   that gate A (EX-000053 generation binding) reserves for the operator's
   release route. This session's handoff states it "makes no new operator
   authorization"; the harness rule is to commit only when the user asks.
2. **Drop the entry** -- impossible: the entry is a directory (`tools`).
   Deleting or moving the files instead would remove runtime modules the
   engine imports (gc.py, persistent_goal.py, source_reindex.py) and 23 tests
   the suite names, i.e. ship a broken home.
3. **Stage without committing** -- would grow the preserved staged batch from
   7 to 36 entries, which the handoff forbids, and would not clear the check
   anyway (tracked != staged).

The T-1592 orphan warning is also relevant: the validator warns against
committing such a file alone when it imports runtime HEAD does not carry; any
repair must ship the dependent runtime as one generation -- again the
publication route, not a hand commit.

## Consequence for the circuit

The crew's SC-7 needs a CURRENT_PASS core conformance receipt before the E/H
stages can be re-recorded. The red set is a repo-tracking defect on the
generation the operator is about to install, so the operator's publication
staging decision (T-2058 gates A/B) is the exact action that both clears this
receipt class and unblocks the delivery chain. No agent action short of that
decision can produce a PASS without minting the authority this session does
not have.

The installed pre-fix generation blocks even the audit cleanup: measured
`saipen audit ingest --dry-run` -> `SOURCE_UNRESOLVED`, "linked Work T-2016
is not DONE" (SRC-386), so the 3 closed-pending-delete audit layers cannot be
consumed at the installed home. This is the same installed-generation gap
HUNT-024 named (installed audit_route/future_gate pre-fix) and it clears on
the same install.

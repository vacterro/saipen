# T-290 APPEND — versioned visual-test baselines in portable archives

Measured 2026-10-07 on the AUDAPACK implementation target.

## Downstream evidence (the defect that opened this append)

- The audited project's visual suite declares **9 canonical baselines** under
  `tests/baselines/*.png` (`home`, `docs`, `spec`, `ecosystem`, `pricing`,
  `debug-components`, `debug-themes`, `debug-rendering`, `home-dracula`) and
  passes against all nine.
- The portable AUDAPACK archive of that same project carried **3** of them:
  `docs.png`, `debug-rendering.png`, `home-dracula.png`.
- **6 missing.** Verdict: the archive was *sufficient for a code handoff* but
  **not reproducible for its declared visual validation**.

Route names above are acceptance evidence only. Nothing in the implementation
is keyed on a project name, a route name, or the literal directory
`tests/baselines`.

## Root cause

The project is not a Git repository, so packing runs in **filesystem mode**.
`build_fidelity_plan` classified every `tests/baselines/*.png` as ordinary
media by extension and routed it into the per-`(media class, parent dir)`
sampler, which kept `PROFILE_MEDIA_SAMPLES["standard"] == 3` and dropped the
rest with `REASON_MEDIA_BUDGET`.

Reproduced two ways:

- synthetic tree → 3/9;
- the real project with the new predicate disabled → **the same three files**
  (`docs`, `debug-rendering`, `home-dracula`), i.e. an exact match to the
  downstream report.
  Evidence: `.saipen/evidence/T-290-visual-baseline-policy-diff.txt`
  (`OLD policy: kept 3 … dropped 9` vs `NEW policy: kept 12 … dropped 0`).

## The rule (one canonical classification, no new subsystem)

A file is **versioned test-oracle material** when BOTH hold:

1. some path segment is a recognized **test context** directory:
   `tests`, `test`, `__tests__`, `e2e`, `playwright`, `visual-tests`,
   `visual-regression`, `regression-tests`; and
2. a **test-oracle** directory name appears **below** that context:
   `baselines`, `baseline`, `golden`, `goldens`, `snapshots`, `__snapshots__`,
   `reference`, `references`, `expected`.

Context must be an *ancestor* of the oracle directory. `docs/reference/` is
prose and stays ordinary optional media; only `tests/**/reference/**` is an
oracle. Extension is never the test.

Applied in three existing places, in this order:

| Place | Effect |
|---|---|
| `fidelity._priority_for` | oracle → **priority 1** (mandatory); never trimmed by `REASON_SIZE_LIMIT` |
| `fidelity.build_fidelity_plan` media walk | oracle **never enters `media_groups`** → no `REASON_MEDIA_BUDGET` |
| `source_inventory._tier` (nested components) | oracle → mandatory, before `COMPONENT_OPTIONAL_SUFFIXES` → no `REASON_COMPONENT_OPTIONAL` |

Fail-closed truth (`source_inventory.source_review_reconciliation`):

- `test_oracle_files_total` / `test_oracle_files_included` are reported in the
  review dict;
- an oracle dropped by `REASON_MEDIA_BUDGET`, `REASON_SIZE_LIMIT` or
  `REASON_COMPONENT_OPTIONAL` is an **issue**, so `source_review_ready` is
  `False`;
- `packing.stage_inventory_zip` re-proves the actual archive members and
  refuses with `CODE_SOURCE_REVIEW_INCOMPLETE` before committing a ZIP. A 3/9
  set can therefore never ship behind `source_review_ready=true`.

## Non-goals honoured

No every-PNG-in-the-repo rule. No automatic archiving of generated Playwright
reports or `test-results/**` actual/diff screenshots. No project special case.
No `tests/baselines` literal special case. No Complete Source requirement for
ordinary tracked oracles. Binary/media filtering is not globally disabled.
No language-specific test parser. Hard-safety exclusions untouched. Partial
baseline loss is never hidden behind `source_review_ready=true`.

## Regression coverage

`tests/test_test_oracle_baselines.py` (28 tests, red-then-green — 14 failures
with the predicate forced to `return False`):

- the 9-baseline set survives the standard profile, never sampled;
- `media_samples=1`, `max_mb=1` still cannot reduce a baseline set;
- ordinary media under `public/screenshots/` keeps the existing sampling
  policy (exactly 2 of 5 dropped, `REASON_MEDIA_BUDGET`);
- filesystem pack and Git pack both carry every baseline with matching bytes;
- a partial 3/9 inventory reports total 9 / included 3 / ready `False` and
  `stage_inventory_zip` raises `ArchiveVerifyError(CODE_SOURCE_REVIEW_INCOMPLETE)`
  leaving no staging zip;
- a nested component keeps its own versioned baseline under both `auto` and
  `complete_source`;
- a foreign-origin component keeps its existing named omission.

## Real acceptance (SAIPEN Website, live worktree)

After the rule, the real project was repacked through the ordinary
`PackingService(load_config()).pack_project(...)` path while the worktree was
snapshotted before and after:

- archive: `_SAI_WEBSITE_07.10.26-T06-47-12.zip`
- baselines in worktree **12**, in archive **12**, missing **[]**,
  unexpected **[]**, SHA-256 mismatches **[]**, files changed during the pack
  **[]**
- `source_review_ready: True`, `test_oracle_files_total: 12`,
  `test_oracle_files_included: 12`
- `inventory_mode: filesystem`, `archive_scope: auto`, 1710 members
- the 9 originally reported routes are all present; the worktree had grown to
  12 baselines (three `*-mobile.png`) before this pack, so the assertion is a
  superset
- generated run output stayed out of `tests/baselines/**`
  (`test-results/.last-run.json` and the `*-actual.png` files are ordinary
  filtered content, not oracles)

Evidence: `.saipen/evidence/T-290-visual-baseline-acceptance.txt`
(`ACCEPTANCE: PASS`).

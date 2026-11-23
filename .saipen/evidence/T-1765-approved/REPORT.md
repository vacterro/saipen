# T-1765 — approved finding semantics and baseline compatibility

The actual asynchronous user reply selected RULESET_VERSION 2, retaining old
baseline files and remeasuring fresh ones when needed. Exact choice is SRC-260,
appended to SRC-245 at E-15951 and projected at E-15953; E-15954 lifted the old
WAIT_USER_DECISION. T-1801 finished at E-15963; this repair then claimed
E-15964, entered BUILD E-15967 and VERIFY E-15969. No second choice is owed.

## Bounded implementation

`tools/saipen_engine/findings.py` now has RULESET_VERSION 2. After existing
credential/template/special-case handling and volatile-value normalization,
a global rule with nonempty captured semantic parts keeps the normalized
condition before the generic incidental-ID collapse. The old generic collapse,
not the bracket in a filename, caused the reported loss.

The handoff retains root-file-set, T-1446 and tuple[bool. Two same-rule findings
with the same incidental ID but different subtypes or offending filenames have
different detail hashes. Finding keys keep their existing rule+subject identity;
credential redaction and subject-scoped ID normalization remain intact. Global
findings remain blocking even when carried; this change weakens no gate.

The only second owned path is `tools/test_t1765_finding_subtypes.py`, copied
unchanged from the reviewed preparation oracle. Eleven cases cover the report,
subtype and filename changes, another captured global family, volatile values,
credential redaction, scoped IDs, explicit v2 binding, immutable v1 refusal in
load and Work comparison, and a fresh loadable v2 snapshot. The actual original
findings.py is preserved at `before/findings.py`.

## Existing baseline files and current behavior

`baselines-before.json` captured all 460 local debt files immediately before
the actual product edit. `baselines-after.json` proves every one remains
byte-identical: none missing or changed, no conversion or deletion. Scope is
this root's `.saipen/recovery/conformance/debt`, not other projects.

Actual DEBT-000460 now refuses BASELINE_RULESET_CHANGED and names itself and
ruleset 1. `current-policy.json` records that refusal and the retained handoff.
Current ruleset fingerprint is
d682e4a0e542976ddfe3e5518a2b4f8bc81d7eea1e4bbdcd8642a8d5c7fefc5c;
the old one is 82e5e183ae8f0fd909be3fa3627f00489cacaab813d942186c832db02a05a1c1.
The existing pre-BUILD baseline owner skips incompatible snapshots and measures
new ones when subsequent Work needs them. No new command or state was added.

Only the new test's intent-to-add entry was registered. `index-intent.json`
proves 5,214 other index entries and product bytes unchanged by registration.
No content was staged for publication, and no commit, tag or push is authorized.

## Current verification and remaining obligations

Focused discovery executed 84 finding/debt/reverify/conformance cases: PASS,
0 failures/0 skips (`focused.txt`). Ruff 0.16.0 over tools/ and tests/ and
whitespace passed. The isolated preparation had 8 pre-fix failures and 11/11
candidate passes, but native executed evidence remains the required authority.
Its frozen contract is `regression.json`. Original session 78768 completed;
native receipt regression-execution-4861f25d857c49da9f3b9b04859e97aa records
11 tests with 8 pre-fix failures and 0 post-fix failures, no skips, same
verifier 4b37781730e75118abf4835a86da50bcccc07d76c733304942d0dac35f2804b8.
E-15970/E-15971 are the anchored native pair. Do not rerun the completed session.
Product fingerprint before native run:
6210f45822e17ba4e4d953b5ed2fd1519729e6c240347e99678c140b42c4498c.

T-1695's unchanged focused contract was re-executed on ruleset 2: RV-000059,
38/0, focused CURRENT_PASS; the initial strict capture carried the expected
old-receipt gap. Subsequent canonical validation returned VALID/CURRENT_PASS,
0 problems/9 warnings with ruleset_version 2 (`canonical-validation.json`).
The full declared family is running in original session 42198, PID 17944,
creation 1792088968.2195702, started 18:29:28Z. `running-job.json` binds those
facts. Freeze product inputs until that original process completes; no duplicate
run. After its verdict, independently REVIEW all
11 cases and account for SRC-245:R007 and SRC-260's append Work T-1802. All
other SRC-245 requirements remain T-1764-owned and nonterminal; a green local
repair cannot waive their provenance, incident and foreign-authority limits.
If the canonical whole-Source close gate waits on T-1764, record that real
dependency after preserving the completed implementation and its evidence.

Graph project/discovery/coverage service returned Transport closed; exact
normalizer, ruleset binding, baseline loading/creation, pre-BUILD owner and
fixtures were read directly. No graph completeness or all-project migration
claim is made. The full cc all goal remains active.

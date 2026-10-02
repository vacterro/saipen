# T-1297 / SRC-024 continuation verification and review

Target: live repository `V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN`, complete Git metadata, main baseline `b71590b548ba373cb9608f2b23ddae12645a9cb1`, VERSION `7.257.0`.

The implementation, ten migration tests (including two instrumented cases), terminal coverage labels, E-5854 BUILD checkpoint and E-5855 VERIFY transition existed before this continuation resumed. The handoff's E-5853/BUILD/UNKNOWN snapshot was older than disk. E-5856 truthfully records this discovery; no historical event was manufactured or rewritten. Subsequent phase changes and coverage updates used SAIOPS.

## Scope

`t1297-repair/initial-path-classification.json` classifies all 109 initially changed tracked paths. Runtime: `tools/saipen.py`. Machine contract: `saipen/REGISTRY.json`, `tools/validate.py`. Tests: `tools/test_command_routing.py`, `tools/test_audit_2026_08_27_core.py`. Current documentation/discovery: `saipen/COMMANDS.md`, `saipen/SKILL.md`, both bootstrap injectors, root README and GUIDE. Generated/localized: locale READMEs, root mirrors, current guides. Conformance: corpus case 177, generated CONFORMANCE digest and semantic golden. Journal/source state: STATE/BOARD/LOG, intake and the already completed SRC-023 archive move.

Seven unrelated SubSaipen paths were identified from their actual hunks: PROTOCOL LOG-slot prose, README/crew applicability prose, and four saiwiki board/log/state/outbox files describing earlier W-042/W-043 work. Their exact pre-resume bytes were preserved under `t1297-repair/preserved-unrelated/`, then only those paths were restored to baseline under the user's explicit narrowing instruction. These backups and other pre-existing untracked producer/kitchen work are excluded from release.

The golden's key-order rewrite was removed after proving JSON equality; its final delta is only `ss` key becoming `st`. Seventy current/generated documents were independently compared against baseline: only their shortcut callout and canonical release badge differ. The canonical producer's `_refresh_readmes.py:sync_shortcut_callouts` was re-executed. Existing translation source-digest debt predates this wave: baseline English digest `587e98d3003181b49ec785a59cd37f2c34fe373a51179b3e4a6a6288f9a009a9` already disagreed with locale marker `bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7`; no false refresh of those markers was performed.

## Contract and independent inspection

- `st` enters the existing STOP branch. AST comparison proves its complete body identical to the baseline branch; only the accepted shortcut tuple changed.
- `_status` is AST-identical to baseline; `sss` still executes it. Public CLI pairwise comparisons pass for both long forms.
- `ss` returns exit 1 / `SHORTCUT_RETIRED`, names `st` and `sss`, and invokes neither `operations.stop_checkpoint` nor `_status` under instrumented spies.
- Two real `ss` subprocess calls without `--dry-run` produce identical results and leave the complete temporary-project file digest unchanged. Real `sss` also leaves it unchanged; real `st` changes the checkpoint.
- The normalization owner `saipen_engine/commands.py` is unchanged. Cyrillic `сс` resolves to `cc`; no `s` fold exists. The active registry has 19 keys including `st` and `sss`, excluding `ss`.
- Surplus handling matches STOP and preserves STATUS refusal. Current COMMANDS Unicode prose now names `st` and explicitly documents retired refusal.
- Existing historical archive hashes and audit/11 through audit/15 hashes were checked unchanged before closure. CHANGELOG contains exactly one new migration entry; its old entries are unchanged.

## Verifier integrity and results

The continuation strengthened existing tests without changing runtime semantics: disabled dry-run for zero-write evidence, asserted repeat determinism, replaced the tautological dictionary control with mutations of an exact copy of the real REGISTRY. The unchanged positive registry check fails on either added `ss -> stop` or stolen `sss -> stop`.

`python .saipen/kitchen/t1297-red-control.py` runs the unchanged F/G test against a bounded mutation of the real adapter's resolution seam (`ss` resolves to `stop`). It exits **1**, raises `_HandlerFired: stop_checkpoint`, and reports one ERROR. The same test passes against the unmodified runtime. This is an observed red, separate from the suite's expected-failure control.

| Check | Result |
|---|---|
| Initial RetiredShortcutMigrationTests / StopAuditTests | 10 / 5 PASS |
| Final command-routing and audit-core modules | 71 PASS |
| Authoritative `unittest discover -s tools -p test_*.py -v` | 1,228 PASS, 2 skips |
| Canonical `test_runner.py --family unit` | PASS |
| Consumer `unittest discover -s tests -p test_*.py -v` | 35 PASS |
| Ruff 0.16.0, `tools/ tests/` | PASS |
| Live `validate.py --gate core` | PASS, 0 FAIL / 28 warnings |
| `conformance_corpus.py --check` | PASS |
| REVIEW independent rerun of focused modules | 71 PASS |
| REVIEW live core validator rerun | PASS, 0 FAIL / 28 warnings |
| AST/byte/history inspection and `git diff --check` | PASS |

Logs live under `t1297-repair/`. Two SIM117 findings were fixed narrowly; E-5863 corrects the premature transition text claiming Ruff had automatically fixed them, which it had not. No false green was retained as final evidence. REVIEW inspected moved oracles: routing expectations and corpus/golden changes follow the explicit new contract, while the zero-write/spies tests are stronger; no existing handler behavior or normalizer was weakened. No P0/P1 finding. Memory promotion: NO, the already documented control-safety contract and existing red-control card suffice.

## Additional broad-gate finding

The initial `audit_parity.py` run exited 1 because its nested full mutation suite was not green. Independent reproduction isolated `tools/audit_checks.py:2937`: the missing-trigger control still searched for `cc, ccc, ss, sss, dd`, which occurs once in baseline SKILL and zero times in current SKILL. Its mutation therefore did not remove `sss`. REVIEW routed back to BUILD and changed only `ss` to `st` in this fixture's anchor/replacement; the expected missing-registry-trigger diagnostic is unchanged. This is a required regression fixture, not a new runtime or validator rule. A duplicate full sweep accidentally started by unsupported `--help` was terminated and supplies no evidence.

## Versioning and lifecycle

CONTRIBUTING.md lines 57-59 assigns a major bump to breaking contract changes. Removing the previously executable STOP alias is an intentional compatibility break. Version `8.0.0` was computed as `(current major + 1).0.0` from `7.257.0`, not selected arbitrarily. `release_contract.version_metadata_paths` supplied the exact badge inventory; standard SHIP owns parity, scope, commits, push, tag and atomic Work finish. No protocol architecture or state schema redesign accompanies this command compatibility boundary.

SRC-024 R001-R006 were re-dispositioned VERIFIED through `source disp`, each with concrete evidence and verification; coverage reports 6/6 terminal and zero unresolved. Source remains ACTIVE until SHIP finishes Work, then canonical source close and journaled `audit_inbox.consume_layer` may consume audit/11. Audit/12-15 are outside this run.

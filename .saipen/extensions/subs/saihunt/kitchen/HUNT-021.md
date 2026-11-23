# HUNT-021: bounded six-signal sweep at dc39709c (tree c9c3e86c)

Current identity: `dc39709c0c17a3272126c01a626ffcaa4176140b` /
`git-delta-v1:c9c3e86c3626f36973a4e75543aeebc51f174d8fa3c2271c89e1afe963a229a1`.
Role revision: `sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5`
(`saipen sub status saihunt` reports it CURRENT).
Raw captures: `_hunt021_validate_installed.txt`, `_hunt021_validate_repo.txt`,
`_hunt021_controls.txt`, `_hunt021_git_status.txt`.

This pass is bounded to the two validator generations, the focused control
modules, the recent-commit census, and the untracked runtime-manifest cluster
under `tools/`. It does not claim a full repository audit and converts no
static count into a defect.

## Signal 1 -- failing tests/gates: REPRODUCED

The controlling installed gate refuses: `saipen validate` returns
`CONFORMANCE_UNHEALTHY`, `CURRENT_FAIL`, validator exit 1, **3 problems and 18
warnings**. The three problems are:

1. `closure provenance does not resolve: EX-000052 was verified against
   installed engine generation sha256:42c597df657582cf... but the running
   engine is sha256:d64ee12ee476fde8...` -- `.saipen/recovery/conformance/external/EX-000052.json`
   carries `installed_identity.engine_digest` for a generation the installed
   engine no longer is.
2. `STATE.md audit route not followed -- the audit inbox routes 'saipen audit
   ingest' (layer None, audit/SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md) but
   next_action is 'saipen crew'`. The inbox projection's action is
   `saipen audit ingest`, `work: T-2016`, receipt `SRC-386`, state
   `CLOSED_PENDING_DELETE`.
3. `FUTURE GATE: future gate FG-0046 names slice ticket T-1936, which is not
   on BOARD`. `.saipen/future/index.json` records FG-0046 as PROMOTED with
   slice `T-1936`, closure `done`; T-1936 is absent from `.saipen/BOARD.md`.

The repo-generation validator `python -B tools/validate.py` exits 1 with
**27 problems and 36 warnings**: the same three classes plus **26
runtime-manifest paths Git does not track**. The delta is an identity
asymmetry, not a count difference: the installed validator resolves
`home_path("MANIFEST.json")` to its own installation and checks those entries
against the project clone, while the repo-generation validator resolves the
source manifest (`saipen/MANIFEST.json`) and sees the untracked cluster. The
controlling gate therefore cannot report the project's own manifest debt.
Captures: `_hunt021_validate_installed.txt`, `_hunt021_validate_repo.txt`.

Focused controls are green: `python -B -m unittest tools.test_refusal_registry`
6/6 OK and `python -B -m unittest tools.test_t1430_crew_run_receipt` 3/3 OK,
both exit 0 (`_hunt021_controls.txt`). No focused test failure reproduced.
Verdict: **REPRODUCED** as the current conformance red, under existing Core
ownership (T-1449 cc-all closure audit; T-2057/T-2058 for the publication and
evidence carriers).

## Signal 2 -- commits unverified in LOG: BLOCKED

Census of the last twelve commits: six carry a LOG citation by short hash or
full hash (`dc39709c0` 5, `7857dbf21` 1, `00f290d90` 1, `66ef622a4` 63,
`b152e6de2` 2, `7373fcb9b` 1), six carry none (`88dab8ae4`, `983470bd3`,
`bc752edfa`, `326fcdddb`, `08e84d137`, `d5eca177a`). LOG.md does carry
40-character hashes (17 lines), so a short-hash-only census would be
misleading; the full-hash check was run per commit and left the same six
uncited.

Literal absence still cannot distinguish an unverified commit from evidence
recorded under the ticket ID alone, which is the dominant LOG convention. The
six uncited commits name T-1943, T-1950 and T-1951 in their subjects; proving
their verification requires semantic release-ledger attribution this bounded
pass did not do. Verdict: **BLOCKED**, no commit claimed unverified. Limit:
hash-citation census only.

## Signal 3 -- stale TODO/FIXME/HACK: BLOCKED

Raw census under `tools/saipen_engine/` and `tools/saipen.py`: 164 matching
lines. The corpus includes protocol vocabulary, section names and test
fixtures; no per-marker age/ownership/reachability review was performed, so
the count cannot establish staleness. Verdict: **BLOCKED**, pending an
individual review. Limit: raw grep, no word-boundary or age filter.

## Signal 4 -- silent failures: CLEAN (bounded)

AST census over `tools/saipen_engine/*.py` and `tools/saipen.py` for
`except:` whose whole body is `pass`: **0** occurrences. All handlers either
name an exception type or do something in the body. This is a bounded verdict
on that exact shape only; `except Exception: pass` bodies with more than one
statement were not judged. Verdict: **NOT_REPRODUCED** (tried the AST census,
no hit).

## Signal 5 -- symmetry gaps: REPRODUCED

The manifest gate is symmetric in the source layout and asymmetric in the
installed layout: the same manifest entry set is inspected by the repo
generation but not by the installed generation, because the installed
validator reads `home_path("MANIFEST.json")` from its own home. Measured
consequence: 26 untracked runtime files are FAIL under
`python -B tools/validate.py` and invisible under the controlling
`saipen validate`. This is a single-truth violation of the same class the
night shift names: source checkout and installed engine silently disagree
about which bytes the runtime needs. No code was changed. Verdict:
**REPRODUCED** by the two captures above.

## Signal 6 -- dead code / orphan files: REPRODUCED as an uncommitted cluster

`saipen/MANIFEST.json` names 26 files `git` does not track. Reachability of
the six engine modules in that cluster:

| module | tracked-source imports | live via |
|---|---|---|
| `tools/saipen_engine/gc.py` | 3 | tracked engine code |
| `tools/saipen_engine/persistent_goal.py` | 1 | tracked engine code |
| `tools/saipen_engine/source_reindex.py` | 2 | tracked engine code |
| `tools/saipen_engine/outcome_truth.py` | 0 | untracked T-2040 tests only |
| `tools/saipen_engine/discovery_providers.py` | 0 | untracked T-2040 tests only |
| `tools/_t2040_experiment.py` | 0 | untracked T-2040 harness |

Three of the six are imported by tracked source, so the checkout is carrying
runtime bytes that no clone receives; the other three are an uncommitted
T-2040 test/harness cluster. The manifest's "this home ships complete and
every checkout of it does not" sentence applies to all 26. Verdict:
**REPRODUCED** as a durability finding under T-1449/T-2057 ownership; no file
was edited, deleted or staged.

## Ownership and limits

- Reported classes are already owned on the current Core BOARD: T-1449
  (cc-all closure audit, residual validator FAILs), T-2057 (missing regression
  evidence carrier / full-family red), T-2058 (warning ownership / publication
  staging). No new ticket and no payload are proposed.
- The sweep did not run the full test family, did not mutate any tracked file,
  and did not judge the six-signal censuses beyond the stated limits.
- The role wrote only inside `.saipen/extensions/subs/saihunt/`.

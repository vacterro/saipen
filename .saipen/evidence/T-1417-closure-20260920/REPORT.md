# T-1417 committed and installed; T-1412 lifecycle blocker

## Outcome

T-1417 reached canonical DONE at E-7485. Its final field-C implementation is
local commit `3b0650f18b43ec04e44278e0c370e957c92ac6d2`, on top of the already
existing initial implementation `9527cdfb2c3fe45bde31e8482e503f57d9fede76`.
No push, tag, public release, history rewrite, or product rewrite occurred.
SRC-074 remains ACTIVE: finish mechanically settled its request clause, but
the receipt has not been closed or archived while the corridor is unresolved.

T-1412 was moved from TODO to BLOCKED at E-7486. This is deliberately
NONTERMINAL. The defect is implemented, but current protocol has no truthful
terminal supersession disposition applicable to this original ticket. It is
no longer normal schedulable implementation work. Do not reimplement it.

The operator explicitly required STOP at this Phase 0C boundary. No new Work
was allocated. EXEC-RESPONSE-01 and T-1403 have NOT been implemented or claimed.
After resolving this lifecycle blocker, the authorized order is exactly one
new P1 response-surface owner, then T-1403, then STOP (not T-1401/T-1402).

## Exact path ownership and scope

The index was empty before staging. E-7481 replaced the stale E-7471 scope
through `saipen scope T-1417`; the new record binds current raw SHA-256 values.
Immediately before commit all three hashes and the exact staged set matched.

| Path | Owner | Commit action |
| --- | --- | --- |
| tools/saipen.py | T-1417 field-C correction | committed |
| tools/saipen_engine/router.py | T-1417 shared production gate | committed |
| tools/test_t1412_conformance_truth.py | T-1417 production regression | committed |
| saipen/COMMANDS.md | initial T-1417 implementation | unchanged, already in 9527cdfb |
| saipen/REGISTRY.json | initial T-1417 implementation | unchanged, already in 9527cdfb |
| tools/saipen_engine/conformance.py | initial T-1417 implementation | unchanged, already in 9527cdfb |
| tools/test_recovery_reachability.py | initial T-1417 implementation | unchanged, already in 9527cdfb |

Unrelated dirty and untracked user files remained outside the commit.

## Verification

- Current focused oracle: 10/10 PASS before REVIEW, in REVIEW, and from committed HEAD.
- Unchanged field-C oracle against a detached 9527cdfb CLI: FAIL as expected.
  The pre-fix subject emitted `saipen crew` with rc=0 while conformance was
  NOT_RUN; the identical assertion requires nonzero and executable validate.
  Only the implementation path was changed for this comparison.
- `python -m unittest tools.test_recovery_reachability tools.regression_conformance_closure -q`:
  84 unittest cases PASS. The regression script was separately executed below;
  its 29 checks are not included in the 84 count.
- `python tools/regression_conformance_closure.py`: 29/29 PASS.
- Ruff over the exact three changed paths and staged diff whitespace: PASS.
- Full-family attribution is inherited evidence from E-7477, not a new full
  suite run: PATCH_OWNED=0, UNKNOWN=0; 209 inherited reds of 2933 cases against
  214 baseline reds of 2923. No product code changed during this session.

Core validation is NOT green: one inherited stale Improve report failure.
Public ship validation is NOT green: that same failure plus two failures to
enumerate/compare the unrelated release metadata pathspec. The operator's
explicit narrow LOCAL commit instruction was followed; public release was
not attempted. E-7483 records the distinction. The normal Git hook ran (no
bypass) and accepted the commit after its portable-floor validation; its
Python validator failure remains a real failure, not a PASS claim.

## Installed acceptance

The 53 pathspecs derived from saipen/MANIFEST.json were clean against HEAD
before injection. `tools/autoinject.py --force` initially reported failure
with a truncated diagnostic tail. Direct supported `bootstrap/inject.ps1`
under the current PowerShell succeeded, followed by supported
`tools/autoinject.py --stamp-only`. An intermediate read showed missing stamp
facts; the final fresh process re-read every actual stamp and distribution.

Final distribution:

    source_head: 3b0650f18b43ec04e44278e0c370e957c92ac6d2
    expected_generation: gen-sha256:2bfcc050155b38babb717bb4eb039786c225c94a162d1129a89bd0debec0eb11
    installed: 6
    stale: 0
    unknown: 0
    surface_unknown: 0
    fresh: true

Two installed CLI surfaces each passed four selected field tests using their
installed test module, installed CLI, and disposable project home bound to
that installation:

- `C:/Users/vac34/.config/opencode/skills/saipen`: 4/4 PASS.
- `C:/Users/vac34/.codex/skills/saipen`: 4/4 PASS.

Fields: A human STALE_FAIL truth plus validate refresh to CURRENT_PASS; B
actual full-validator failure produces CURRENT_FAIL and nonzero; C production
continue refuses NOT_RUN, names validate, and admits crew after remediation.
These are installed-runtime CLI acceptance, not observed model sessions.
The acting seat glm-5.3-max was inherited as protocol ownership, not asserted
as this session's model identity.

## Exact canonical blocker

Read-only production retirement PLAN:

    python tools/saipen.py ticket retire T-1412
      --reason SUPERSEDED_BY_IMPLEMENTATION --evidence E-7477
      --authority SRC-074 --dry-run --json

returned:

    ok: false
    code: RETIREMENT_REASON_UNKNOWN
    changed_files: []
    reason 'SUPERSEDED_BY_IMPLEMENTATION' is outside the registered set
    MISROUTED_PROJECT_BINDING|TEST_FIXTURE_CONTAMINATION;
    retirement never accepts a free-text reason

Neither supported retirement reason is true for T-1412. The engine's current
set in retirement.py is broader than OPS prose (it also includes fixture
contamination); neither authority grants duplicate/supersession retirement.

After T-1417 was DONE, the shared strict resolver
`resolve_implementation_source(root, 'T-1417')` returned:

    ok: false
    kind: work
    detail: T-1417 is DONE but no committed release evidence names it;
            DONE is an evidence claim, never proof of publication

The inherited_verified finish gate translates that verdict to
VALIDATION_FAILED. A local Git commit is not a release receipt. Fabricating
one, or choosing own_patch for T-1412 without its own delta, would be false
provenance. Cohort closure would assert shared publication ownership and
leave pending publication; it does not retire superseded Work. `ticket block`
honestly removes schedulability but is not terminal. No terminal claim is made.

## Required operator decision

Authorize a bounded protocol change introducing a truthful, evidence-bound
terminal supersession disposition for original Work implemented by a named
other Work, before the already requested response-surface ticket. This is a
change of the explicitly ordered scope, so the Phase 0C STOP applies until
the operator decides. Do not turn this into a request to rerun tests or type cc.

The canonical stop checkpoint at E-7487 wrote generic digest lines
`remaining: none` / `awaiting: nothing` and `next_action: saipen continue`.
Those do not encode this corridor's operator gate. No manual STATE/digest
surgery was used to hide that limitation. The explicit T-1412 BLOCKED record
and the subsequent DEC checkpoint preserve the operator's actual stop scope.
An attempted checkpoint taxonomy WAIT was refused with zero writes; the
supported DEC taxonomy was used instead. The temporary pre-fix checkout was
removed only after verifying its exact resolved path and clean Git status;
it can be recreated from commit 9527cdfb.

## Discovery limitations

Codebase-memory generation 2026-09-01 excludes tools/ entirely. Relevant
coverage checks reported excluded/stale paths; code and closure claims above
were checked against current source bytes. No graph completeness claim.

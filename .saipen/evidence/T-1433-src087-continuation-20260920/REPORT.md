# T-1433 / SRC-087 — continuation envelope: acceptance-boundary dispositions

Date: 2026-09-20. Source HEAD: `ec53042a` plus the inherited dirty worktree
(no clean-tree claim). No push, tag or release was performed.

## Scope

SRC-087 asks for sequential roadmap execution starting with finishing the
T-1432 / SRC-085 + SRC-086 acceptance corridor and classifying every wider
boundary instead of rerunning unchanged broad failures.

## Current facts re-derived on these bytes

| Boundary | Measured result | Classification | Canonical owner / disposition |
|---|---|---|---|
| Improve report group | Active strict cycle `imp-vacterro-saipen-20260919-2` (created 19.09 14:41) carried three zero-RUN drafts whose protocol/tree identity went stale; `tools/validate.py` 3617 skips a cycle carrying `cycle_aborted` | PRE_EXISTING (abandoned assignment, predates current bytes; no immutable report rewritten) | Improve lifecycle: `saipen improve abort imp-vacterro-saipen-20260919-2` -> COMMITTED; roster archived, `cycle_aborted: draft-preserved`, all three reports byte-preserved at their original paths |
| Five untracked runtime files | `tools/saipen_engine/host_bootstrap.py`, `tools/test_host_bootstrap.py`, `tools/test_instruction_loader_contracts.py`, `tools/test_src085_conformance_disposition.py`, `tools/test_src085_improve_run_body.py` are named by `saipen/MANIFEST.json` `copy_trees` but are absent from the Git index | INTEGRATION_REQUIRED (legitimate implementation; integration authority = narrow local commit under this ticket, no push/tag) | This ticket's SHIP: exact 5-path commit, per E-7066 / E-7112 / E-7135 commit-only closure precedent |
| Full core-unit discovery | Prior run exceeded the declared 600-second family budget and was interrupted: TIMEOUT / INCOMPLETE, no terminal count, no family PASS or FAIL | PRE_EXISTING, not measurable to a verdict under this ticket; partial output retained in T-1432 evidence | T-1344 (declared-family closure evidence) and T-1346 (stale-fixture reds); no further 600-second spend without a new hypothesis |
| Installed runtime parity | `runtime --check-freshness` = `CANONICAL_RUNTIME_SOURCE_UNPROVEN` (source root has no installer provenance marker); distribution reports 5 of 6 homes stale and the scheduled refresh was skipped `DIRTY_SOURCE` | AUTHORITY_BLOCKED (dirty-source policy forbids publishing or installing an unreviewed mixed tree) | T-1327; exact limitation recorded, no injection and no parity claim made |
| M1 / M2 / M3 | Focused SRC-085 evidence green at E-7668 / E-7669 (guard + admission + hostile matrix + Improve append + conformance disposition + explain-next regression); live read-only observations on AUDAPACK and PROBLIP recorded in T-1432 evidence | PRE_EXISTING green; no bytes changed by this run | Preserved; no neighbor project was patched |

UNKNOWN = 0. PATCH_OWNED = 0 code deltas in this run: the improve report group
was historical evidence resolved through its canonical lifecycle, and the
runtime files already existed.

## Commands and observed results

```text
python tools/saipen.py improve abort imp-vacterro-saipen-20260919-2
    -> COMMITTED; roster cycle_status: archived, cycle_aborted: draft-preserved
python tools/saipen.py improve status --json
    -> imp-vacterro-saipen-20260919-2 archived; three seats still report_status: draft
python -m unittest tools.test_host_bootstrap tools.test_instruction_loader_contracts
                   tools.test_src085_improve_run_body tools.test_src085_conformance_disposition
    -> Ran 49 tests in 22.436s -- OK
python -m ruff check <the five paths>
    -> All checks passed!
python tools/validate.py
    -> before dispositions (T-1432 evidence, validate.txt): 6 problem(s), 29 warning(s)
    -> after the improve abort: 5 problem(s), 29 warning(s); all five are
       "runtime manifest names a file git does not track" for the five paths above
```

## Boundaries preserved

- No immutable improve report bytes were edited or moved; the archives keep
  the drafts exactly where they were.
- No file was staged, committed, deleted or rewritten to change the validator
  answer; the abort is a journaled lifecycle transition, and the commit that
  discharges the remaining five FAILs has not been made yet.
- No AUDAPACK (or other neighbor) patch was required or made.
- Publication remains paused: no push, no tag, no release, no install refresh.

## SHIP result

```text
staged exactly 5 paths; git diff --cached --check clean
python tools/validate.py --gate ship
    -> FAIL x2: staged release metadata cannot be read/compared -- expected
       for a commit-only local closure (E-7066 / E-7112 / E-7483 precedent);
       the staged scope itself had no refusal
git commit -F <message>
    -> 46400306 feat(runtime): commit host bootstrap runtime and its tests
       5 files changed, 2002 insertions(+)
       pre-commit validator: "PASS: runtime manifest complete (413 files, all
       tracked)"; "PASS: improve seat report schema valid (12 report(s)
       scanned)"; "Validation complete. Agent is conformant. (29 warning(s))"
no push, no tag, no release
```

## Exact next action

T-1433 closes own_patch over the five committed paths. T-1432 then resumes at
VERIFY, then the roadmap order T-1361 -> T-1346/T-1345/T-1344 ->
command/refusal corridor -> scheduler -> evidence -> runtime -> performance.

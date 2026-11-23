# HUNT-029: bounded six-signal sweep at 5706afe0d / tree c66baf69 -- T-2137 closure landing measured on both gates; installed VALID 0 problems, repo conformant 0 problems, family green at the pre-commit identity, no new defect

Identity (executed read-only by the crew SC-2 role adoption):

- source_head: 5706afe0d814e734b389d5979bde5bff0d149876
- source_tree_fingerprint: git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195
- core-unit family record .saipen/evidence/core-unit/22511643bf418504-20261122T001237364511Z.json
  (8910 ran, judge verdict PASS, new_red [], red 104 baseline, refusal-completeness
  moved to fixed, wall 2386s) was measured at the PRE-commit tree identity that the
  T-2137 closure consumed (E-22443 carried tree-identity 22511643bf418504). The
  family was NOT re-measured at the post-commit tree; both canonical gates below
  were measured green at the exact committed HEAD instead. The commit's own
  source delta is one comment-only unit (tools/test_validator_layout_parity.py,
  30 ins / 1 del) plus .saipen records and _TEMP_ artifacts.

Exact commands and limits:

1. Installed canonical gate: `saipen.py validate --json --project-root <repo>`
   (installed engine) -> capture `_hunt029_installed_validate.json`;
   ok=true, code=VALID, structural_gate=pass
2. Repo-generation validator: `python tools/validate.py` (cwd=repo)
   -> capture `_hunt029_repo_validate.txt`; exit 0, 53 PASS lines, 0 FAIL lines,
   `Validation complete. Agent is conformant. (13 warning(s))`
3. Whole-token census: last 25 commit hashes (`git log -25 --format=%H`) against
   .saipen/LOG.md (`grep -w -c <hash>` per hash) -> capture `_hunt029_signals.txt` S2
4. Marker census TODO/FIXME/HACK by grep -rn over tools/saipen_engine/*.py +
   top-level tools/*.py (declared set includes the audit fixture files, so totals
   are not directly comparable to the HUNT-028 AST census over the 175 engine
   files) with ticket-named marker inspection -> `_hunt029_signals.txt` S3
5. Exception census: grep `except:` bare + grep -A1 `except...$` pass-only line
   count over the same declared set (line census, not AST) -> S4
6. `record_crew_run` / `record_producer_integration` call-site census by grep -rn
   over the same set -> S5
7. `git status --porcelain -- tools/` for the untracked-manifest class -> S6

## Verdicts

- Signal 1 (failing tests): NOT_REPRODUCED. Installed gate answers ok=true /
  code=VALID / structural_gate=pass with an empty problems list; repo gate is
  conformant with 0 problems (53 PASS, 0 FAIL, 13 warnings, 8 of which are the
  expected producer-package-stale reports against the previous HUNT-028 package
  that this package replaces); the declared core-unit family is green (8910 ran,
  new_red []) at the pre-commit tree identity the closure consumed; no failing
  test surfaced anywhere in this sweep.
- Signal 2 (commits unverified in LOG): REPRODUCED. 1 of the last 25 whole commit
  hashes is cited in the main LOG (13f2e7579..., 3 citations, the CORE-TASK
  governance line); 24 uncited including HEAD 5706afe0d -- the standing census
  class already owned by tickets T-1449/T-2057; no new ticket proposed.
- Signal 3 (stale TODO/FIXME/HACK): NOT_REPRODUCED over the declared grep set.
  Raw totals: TODO 893 lines (373 non-test), FIXME 0, HACK 0. Ticket-named
  markers inspected (T-1762, T-1384, T-1609, T-576, T-803..808 board fixtures,
  T-1637, T-999/T-998 synthetic tickets) are all historic-prose/docstring
  vocabulary or audit-fixture content; zero stale live work markers.
- Signal 4 (silent failures): no claim. Line census (not AST): 0 bare `except:`
  sites; 32 except-then-pass handler lines over the declared set. Static shape
  consistent with the tolerated pattern; no change claimed against the AST
  census of HUNT-028.
- Signal 5 (symmetry gaps): no new gap. record_crew_run: definition plus the
  single production call site tools/saipen_engine/crew.py:1587 (the `crew
  record-run` verb, covered by tools/test_t1430_crew_run_receipt.py) -- the
  same live-caller shape HUNT-028 measured; record_producer_integration:
  definition only, the documented asymmetry, unchanged.
- Signal 6 (dead code/orphan files): NOT_REPRODUCED. 0 untracked paths under
  tools/ (`git status --porcelain -- tools/` empty) -- the manifest class of
  HUNT-025 remains closed land.

## Boundary

Read-only against the main project: the role wrote only inside
.saipen/extensions/subs/saihunt/ (this note, the three _hunt029_* captures,
OUTBOX entry, role LOG and STATE). No main-project file was written; no fix was
made (saihunt is not a fixer). Note: the completed-run capture step reads the
repo verifier exactly as the crew instruction requires; the gates were
launched from a temp wrapper outside the repo (C:/Users/vac34/AppData/Local/Temp/
cuprobe/t29_gates.py) whose writes go only into the role kitchen.

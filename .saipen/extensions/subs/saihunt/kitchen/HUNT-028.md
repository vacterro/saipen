# HUNT-028: bounded six-signal sweep at 13f2e7579 / tree 28904dfc -- T-2136 landing measured on both gates; installed 0 problems (drift class resolved by EX-000060), repo 0 problems and zero untracked tools, no new defect

Identity (executed read-only by the crew SC-2 role adoption):

- source_head: 13f2e7579b29a2892a7130796558ecf5e441bba0
- source_tree_fingerprint: git-delta-v1:bdd63a980a507dc5457e35a5d9b718de7d950aa9757e8f097946bbf4426f26f3
- live tree_fingerprint() measured equal to the committed core-unit family record
  .saipen/evidence/core-unit/28904dfc12dd4d11-20261121T212031607891Z.json (8904 ran,
  judge verdict PASS, new_red [], its earlier baseline red test_refusal_registry moved to fixed)

Exact commands and limits:

1. Installed canonical gate: `saipen validate --json` (this host CLI = installed engine 04ebf376)
   -> capture `_hunt028_installed_validate.json`
2. Repo-generation validator: `python tools/validate.py` -> capture `_hunt028_repo_validate.txt`
   exit 0, `Validation complete. Agent is conformant. (7 warning(s))`, zero lines beginning FAIL
3. Bounded census scripts over 175 engine files + saipen.py:
   `Python311 cuprobe/hunt_census.py` + `hunt_census2.py` -> captures `_hunt028_signals.txt`,
   `_hunt028_signals2.txt` (the first script's signal-5 line died on a directory-read mistake;
   the second script remeasured signals 5 and 6 and completed)
4. Whole-token census: last 25 commit hashes (git log --format=%H -25) against .saipen/LOG.md
5. Marker census TODO/FIXME/HACK over the same bounded file set; ticket-named markers printed for
   inspection
6. AST except-handler census over the same bounded set
7. `git status --porcelain=v1 -uall -- tools/` for the untracked-manifest class

## Verdicts

- Signal 1 (failing tests): NOT_REPRODUCED. Installed gate answers VALID with 0 problems
  (HUNT-025 measured 2); repo gate conformant with 0 problems (HUNT-025 measured 31);
  the declared family is green at the exact committed tree (8904 ran, new_red empty); the entry
  HUNT-025 t1465 shape complaint is repaired land (fix(t2136), canonical form).
- Signal 2 (commits unverified in LOG): REPRODUCED. 0 of the last 25 whole commit hashes cited
  in the main LOG, 25 uncited -- the standing census class already owned by tickets T-1449/T-2057;
  no new ticket proposed.
- Signal 3 (stale TODO/FIXME/HACK): NOT_REPRODUCED. 162 marker lines in the bounded 175-file set;
  3 name tickets and all three are historic-prose vocabulary of past or DONE tickets
  (closure_readiness.py:101 T-1762; operations.py:3341 T-1384; reconcile.py:1941 T-1609);
  zero stale live markers.
- Signal 4 (silent failures): no claim. AST census: 0 bare except handlers, 47 pass-only handlers
  over the same set -- static shape unchanged since HUNT-025 (48->47 with the tree's two commits).
- Signal 5 (symmetry gaps): no new gap. record_crew_run: 2 textual sites (definition + live
  caller at crew.py); record_producer_integration: 1 textual site (definition only) -- the
  documented producer asymmetry, unchanged.
- Signal 6 (dead code/orphan files): NOT_REPRODUCED. 0 untracked tools paths (HUNT-025 measured
  the 31-path manifest class; the class is closed land after the fix(t2136) commit tracked the
  board-compaction and evidence files).

## Boundary

Read-only against the main project: the role wrote only inside
.saipen/extensions/subs/saihunt/ (this note, the four _hunt028_* captures, OUTBOX entry,
role LOG and STATE). No main-project file was written; no fix was made (saihunt is not a fixer).

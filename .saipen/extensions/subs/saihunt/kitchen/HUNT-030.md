# HUNT-030: bounded sweep at 975477b04 / tree c66baf69 -- T-2062 landing measured on both gates; family green at the patched tree; no new defect

Identity: source_head 975477b0465203ed8f5969de2de6df0904b23c0c; tree git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195; role_revision sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5.

## What was measured

- Installed canonical gate: installed engine `validate --json`, capture `_hunt030_installed_validate.json`.
- Repo-generation validator: `python tools/validate.py` (cwd=repo), capture `_hunt030_repo_validate.txt`.
- Family record .saipen/evidence/core-unit/4404dda4f5d33ff2-20261122T025758382034Z.json: verdict PASS, ran 8911, red 104 all inside the recorded baseline, new_red [], test_refusal_registry moved to fixed -- measured at the patched tree that the commit 975477b04 then published (the commit adds .saipen records only; source bytes GC-serialization-verified by the pair op regression-execution-b9c4bdd8...).
- Signals: `_hunt030_signals.txt` (S2 commit census, S3 marker census, S4 bare-except census, S6 untracked tools census).

## Boundary

Read-only against the main project: the role wrote only inside .saipen/extensions/subs/saihunt/ (this note, the three _hunt030_* captures, OUTBOX entry, role LOG and STATE).

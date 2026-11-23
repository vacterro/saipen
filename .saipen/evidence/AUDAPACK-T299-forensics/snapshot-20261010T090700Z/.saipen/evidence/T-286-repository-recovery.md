# T-286 — repository recovery: local source of truth

Ticket: T-286 (repository-integrity recovery, not a product feature).
Owner: buffy. Scope: finish the checkpoint the previous recovery pass left open —
curve the curated index into one reviewed **local** commit. No push.

## 1. Before state (verified from the raw Git index, not from a summary)

- HEAD (old): `a37250f700ec4b93c81d36ec563675bab1c1d9d2` — unchanged by the
  previous recovery pass.
- Index: **271 curated paths** staged against that HEAD —
  **180 additions** (the paths the previous pass moved from untracked to
  tracked) and **91 modifications**. The 180/271 split is exactly the
  "180 paths moved from untracked to tracked while HEAD stayed unchanged"
  the checkpoint described.
- Worktree: 374 untracked entries (mostly `.saipen/` archive/protocol/runtime
  plus screenshot output), and for all 271 staged paths the worktree bytes were
  byte-identical to the index — so the gates below ran on exactly the bytes the
  commit carries.

The coverage invariant holds: `audapack/`, `scripts/`, `tools/` and
`.saipen/evidence/` had **zero** untracked source files, and the current-wave
files are all tracked — `audapack/sai_accounts.py`,
`audapack/prepared_worker.py`, `audapack/launch_federation.py`,
`audapack/cli_launchers.py`, `audapack/launch_authority.py`,
`audapack/instances.py`, `audapack/ui_qt/main_window.py`,
`tests/test_plane_launch.py`, `tests/test_launch_federation.py`,
`tests/test_sai_accounts_federation.py`, plus the T-279/T-280/T-283/T-285
evidence.

## 2. Disposition of the two tracked deletions

`.saipen/archive/source/SRC-033.md` and `SRC-034.md` were reported deleted in
the worktree. Resolved as **intentional quarantine, not accidental loss**:

| path | HEAD blob | quarantine blob | verdict |
| --- | --- | --- | --- |
| `.saipen/archive/source/SRC-033.md` | `3f87d25e9871afeb08ea21d42ca4bda522258b85` | `3f87d25e9871afeb08ea21d42ca4bda522258b85` | identical |
| `.saipen/archive/source/SRC-034.md` | `0fc6591dd991e8a1bb6af9919813bc5b620ddba5` | `0fc6591dd991e8a1bb6af9919813bc5b620ddba5` | identical |

Both were moved to `.saipen/quarantine/source/` on 2026-09-24 14:02 (same
timestamp as the quarantine dir itself), byte for byte, and the two sibling
receipt families (`SRC-033.*` / `SRC-034.*` machine receipts, 47 tracked files)
stay in the archive. No STATE/BOARD/LOG entry records a reason for the move, and
the quarantine copies are untracked.

Decision: the two files were **restored to their HEAD content**
(`git checkout -- .saipen/archive/source/SRC-033.md .../SRC-034.md`) and the
quarantine copies were left untouched on disk. Rationale: the recovery commit is
a source-of-truth capture and must not carry a local drift deletion whose reason
no protocol record explains; restoring is a no-op against HEAD (the file simply
stays), costs nothing, and loses nothing. The operator's quarantine intent
survives in `.saipen/quarantine/source/`. **The recovery commit carries zero
deletions.**

## 3. Secret / garbage review of the cached diff

The staged diff is 95 327 added lines across 271 paths. Reviewed before commit:

- No credential material: no private-key blocks (`BEGIN ... PRIVATE KEY` count
  0), no `api_key`/token/bearer literals other than code identifiers, doc prose,
  deny-policy filename lists (`*.token`, `id_rsa`, `secrets` …) and the
  scrubbed-env constant `("OPENAI_API_KEY", "CODEX_API_KEY",
  "CODEX_ACCESS_TOKEN")` which names variables to strip, never their values.
- No archives, caches, databases, `.env`, `.pem` or `*.key` paths staged.
- The only binary is `resources/app_icon.ico` (tracked before, 410 -> 11 200
  bytes) — the shipped AUDAPACK icon.
- No staged file over 200 KB.
- `.saipen/evidence/T-261-live-repro-ffs.jsonl` is content-free telemetry
  (event, severity, timings, trace ids) — reviewed, no token values.

Nothing secret or generated was staged.

## 4. Deliberate untracked classification

Not committed, on purpose, and recorded here so the 374 untracked entries are a
decision rather than an omission:

- **`.saipen/` protocol/runtime/archive artifacts** — `archive/source/SRC-036 …
  SRC-117` receipt families, `archive/retired/`, `quarantine/`, `improve/`,
  `logs/`, `shots/`, loose probe scripts and capture output. SAIPEN working
  memory, not product source; the current-wave evidence is already tracked.
- **`tests/screenshot_*.png` (12)** — generated geometry output.
- **`tests/repro_widget_geometry.py`** — an ad-hoc, 213-line Playwright repro
  harness that measures widget geometry and writes those screenshots. Classified
  deliberately: no test/script/CI file references it, it is not collected by
  pytest (`python_files = test_*.py`), and its outputs are the untracked
  screenshots above. It is a local probe, not a durable test or tool, so it stays
  intentionally untracked. Promote it only if it is wired to a gate.
- **`tests/fixtures`/scratch at repo root** — `_sweep_*.out`, `_fullrun*.out`,
  `val_tmp.json`, `w7dbg.js`, `full-suite.txt`, `.pytest_*` logs, `.zcode/`,
  `README.ded.md`/`README.ee.md`/`README.ja.md` (not yet part of the shipped
  README set).

`.gitignore` reports no worktree change after a status refresh (stale stat only);
it was not staged separately.

## 5. Gates on the exact staged tree

- focused: `python -m pytest -q tests/test_plane_launch.py
  tests/test_launch_federation.py tests/test_sai_accounts_federation.py
  tests/test_prepared_binding.py tests/test_prepared_worker.py
  tests/test_prepared_delivery.py` -> **231 passed** in 4.97s, exit 0.
- `python -m ruff check audapack tests` -> **All checks passed**, exit 0.
- `python -m compileall -q audapack tests` -> exit 0.
- `python -m pytest -q` -> **2713 passed, 16 skipped, 1 warning** in 695.31s
  (0:11:35), exit 0. Receipt: `.saipen/evidence/T-286-full-suite-run.txt`.

### Collection delta, explained exactly

The T-283/T-285 baseline was **2712 passed / 16 skipped** (receipt
`.saipen/evidence/T-285-full-suite-run.txt`, 714.66s). This run collects
**2729** tests (verified by `--collect-only`) against the same 2728. The +1 is
not a lost or newly-skipped test — skips are unchanged at 16 and no test was
deselected:

- `tests/test_repository_hygiene.py` is the **only** test file in the tree whose
  mtime is newer than the T-285 receipt (10:29 vs 09:48); the recovery pass
  rewrote it, and the net test-function delta in that file is exactly **+1**:
  `test_product_python_sources_are_tracked_by_git` — the guard that asserts no
  live product module lives only as an untracked file, i.e. the enforcement of
  this recovery's own invariant.
- A causal check confirms the count is independent of this ticket's other work:
  collecting with and without the restored SRC-033/034 markdown gives 2729 both
  times.

2712 + 1 = 2713 passed.

## 6. Result

- Old HEAD: `a37250f700ec4b93c81d36ec563675bab1c1d9d2`.
- Recovery commit: `db396923f9f28ccc27f90b90e8d8551a0e87d9da`
  (`chore(recovery): capture verified AUDAPACK source of truth`), parent
  `a37250f`. `git ls-tree HEAD` proves the critical current-wave files are in
  HEAD's tree, not merely in the index.
- 273 paths committed (the 271 curated + this receipt family); 95 211
  insertions / 3 338 deletions; `git diff --diff-filter=D --name-only a37250f
  HEAD` returns **zero paths** — nothing is deleted, every changed path is an
  addition or a modification.
- **Nothing pushed** — no `git push`, no PR, no tag, no `git add -A`, no
  `git clean`, no `git reset --hard`, no rebase, no pull, no history rewrite.
  `a37250f` is preserved as the parent.
- `next_action` returns to `PHASE SCOUT T-284`; T-284 is untouched and remains a
  separate, unstarted ticket.

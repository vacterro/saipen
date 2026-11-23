# Incident: the soak project vanished at a generation boundary

Observed 2026-09-23 by astra (T-1481 session), 35 minutes into the relaunched
24H gate (driver pid 35584, started 05:30:22Z, sairoute/SAIFREN, SAIPEN_GPU=on).

## What happened

| time (UTC) | observation | source |
|------------|-------------|--------|
| 06:01:52 | generation 4 starts (`opencode run cc`, pid 8712), session `ses_f3324cf98ffeGf5E3fT9JPox15` | opencode.db `part` |
| 06:04:34 | the agent writes `README.md` for T-3 | opencode.db `part` (write) |
| 06:04:43 | the agent's `Test-Path README.md` answers `True` -- the project is intact | opencode.db `part` (bash) |
| 06:04:44.782 | the last line opencode ever logged: `llm runtime selected ... SAIFREN` for step 10 | `~/.local/share/opencode/log/opencode.log` (file mtime 06:04Z) |
| 06:04:50 | the supervisor writes `autonomy-worker.json`: `failure: HOST_RUNTIME_FAILURE`, `returncode: 1`, `work: null`, `slices_total: 1` -- the prior checkpoint is gone | the recreated `.saipen/cache/autonomy-worker.json` |
| after | `V:\_TEMP_\t1363-g5_tuyfn` holds only `.saipen\cache\autonomy-worker.json`: `.git`, `src`, `README.md`, STATE/BOARD/LOG all removed | directory listing |
| after | supervise stopped; the driver died in `assess()` with `FileNotFoundError ... .saipen\BOARD.md`, so `report.json` was never written | `driver.stderr.txt` |

## What was ruled out

- The agent: no delete, move or clean command in any of the five sessions of this
  project (all tool calls read back from opencode.db); its last command read the file.
- The declared-family evidence run: its sandbox was created at 06:05:41Z, after the removal.
- Test fixtures: no test removes a directory it did not create (`t1363-` fixtures clean
  only their own `mkdtemp` roots; the chaos suite uses `saipen-supervise-*`/`saipen-fence-*`).
- Engine code: no `rmtree` in worker/supervisor/watchdog/cold_recovery/gpu.
- Other Claude sessions: none running on this machine (ListAgents).

## Open

What removed a whole `mkdtemp` project, `.git` included, within ~6 s of the host
process ending abnormally is not established. The two remaining candidates both sit
outside SAIPEN's code: opencode's own shutdown (its snapshot store tracks this
worktree under `~/.local/share/opencode/snapshot/6894fc21...`) and an external
temp-directory cleaner acting on `V:\_TEMP_`.

## What SAIPEN owns regardless

The driver lost the whole run's evidence to one missing file. The report must be
written even when the project is gone (quality `PROJECT_VANISHED`, supervise counters
and history intact).

## Same window, elsewhere in V:\_TEMP_

- The astra session's own scratch git worktree under
  `V:\_TEMP_\claude\...\scratchpad\saigpu` lost its `.git` file and most of its tree
  in the same minutes (directory mtime 06:06Z); `git worktree list` marks it prunable.
  Nothing in that session ran against it between 05:40Z and 06:10Z.
- 367 other top-level directories of `V:\_TEMP_` (fastprompter-tests-*, limisaw_*,
  saimail-*, opencode, saipen-controls-*) changed mtime between 05:59Z and 06:08Z; the
  sampled ones still hold their contents, so this is concurrent activity, not a wipe.

Two git trees under `V:\_TEMP_` losing `.git` in one window points outside the
soak and outside SAIPEN's engine; not established further.

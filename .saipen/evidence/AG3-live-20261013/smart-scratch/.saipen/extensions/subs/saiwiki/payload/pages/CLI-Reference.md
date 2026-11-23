# CLI Reference

The CLI is **dry-run by default** — it only reports what would be deleted.
Add `--delete` to actually remove files. `--dry-run` forces preview even when
`--delete` is present.

| Flag | Effect |
|---|---|
| `--cli` | Force console mode |
| `--portable` / `--system` / `--custom` | Select cleaning layers (default: dry-run preview) |
| `--all` | All layers at once (portable + system + custom) using **safe** system-target defaults; risky opt-ins (Recycle Bin, DNS, Windows Update) stay OFF |
| `--delete` | **Real delete** (without it the run is a dry-run preview) |
| `--dry-run` | Force preview even with `--delete` |
| `--status` | Planned bytes per target from the same read-only planner as dry-run (safe CLI system-target policy; saved `exclude_patterns`/`exclude_paths` apply); nothing is deleted |
| `--analyze-caches` | Scan `%LOCALAPPDATA%`/`%APPDATA%` for cache/temp/log/crash folders over 5 MB and print the biggest — cache discovery for auditing, nothing is deleted |
| `--sys-targets` | Comma list of system targets to force-enable (`System Temp`, `User Temp`, `Recycle Bin`, `DNS Cache`, `Windows Update Cache`, ...). Unknown names error out (exit code 2) instead of silently no-oping |
| `--disable-targets` | Comma list of **safe-default** targets to switch OFF (e.g. `System Temp`). Used by the scheduled/background surface to preserve a GUI state that disabled a safe default — plain `--all` never re-enables it. Unknown names error out (exit code 2) |
| `--exclude` | Comma list of extra exclude patterns (`--exclude "*.db,*.tmp"`) |
| `--hidden` | Hide console window (used by Task Scheduler) |
| `--install-task` | Register the daily silent full-clean task |
| `--time HH:MM` | Start time for the scheduled task (default `09:00`) |

Examples:

```bat
REM preview everything
python _SMART_VAC_CLEANER.py --cli --all

REM actually delete everything (safe system targets; risky opt-ins stay off)
python _SMART_VAC_CLEANER.py --cli --all --delete

REM preview, then real delete, dry-run flag always wins
python _SMART_VAC_CLEANER.py --cli --all --delete --dry-run

REM include risky opt-in system actions (Recycle Bin, DNS, Windows Update)
python _SMART_VAC_CLEANER.py --cli --all --delete --sys-targets "Recycle Bin,DNS Cache,Windows Update Cache"

REM how much junk exists
python _SMART_VAC_CLEANER.py --status

REM daily silent task at 09:00
python _SMART_VAC_CLEANER.py --install-task --time 09:00
```

Task removal:

```bat
schtasks /Delete /TN SmartVACCleaner /F
```

After a `pip install .`, the same commands work as `vac-cleaner ...`.
The standalone exe supports the identical flags: `SmartVACCleaner.exe --all --delete`.

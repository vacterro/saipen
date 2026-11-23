# Smart VAC Cleaner

Smart, safe, layered junk cleaner for Windows. GUI + CLI + Task Scheduler.

## What it does

| Layer | What | Where |
|---|---|---|
| System | Temp, crash dumps, Explorer thumbnails, Windows Update Cache, DNS cache, Recycle Bin, 100+ per-user app cache targets | `%TEMP%`, `%LOCALAPPDATA%`, `%APPDATA%` |
| Deep C: Junk | Updater leftovers, `*.exe.tmp`, Viber QmlWebCache, Yandex.Disk backups, ODIS logs, `app.asar.bak` | `%LOCALAPPDATA%`, `%TEMP%` |
| Portable roots | Known junk patterns inside portable-app roots you configure | `portable_roots` in config |
| Custom rules | Your own path + glob pattern rules | `custom_rules` in config |

## Key properties

- Dry-run by default; `--delete` is explicit (CLI) / confirm dialog (GUI)
- Fully portable: config and logs live next to the script or the exe
- Zero hardcoded user paths: portable roots are candidates, only existing ones are swept
- GUI is localized: English / Russian / Estonian / Dedicated (`lang` in config, `strings/` bundle in the exe)
- GUI Exclusions editor for never-delete patterns and paths; live per-category progress dashboard
- automated regression suite, ruff-clean, CI on GitHub Actions

## Pages

- [Safety](Safety.md)
- [CLI Reference](CLI-Reference.md)
- [Configuration](Configuration.md)
- [Build & Install](Build-and-Install.md)
- [FAQ](FAQ.md)

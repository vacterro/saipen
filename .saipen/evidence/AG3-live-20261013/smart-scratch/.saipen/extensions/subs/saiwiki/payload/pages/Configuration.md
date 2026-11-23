# Configuration

`cleaner_config.json` is auto-created next to the script (or next to the exe)
on first run, with defaults.

```json
{
  "portable_roots": [],
  "custom_rules": [{"path": "D:\\Apps\\TestApp", "pattern": "*.log"}],
  "exclude_patterns": ["*.db"],
  "exclude_paths": ["C:\\Users\\me\\AppData\\Local\\Important"],
  "auto_clean_interval_hours": 0,
  "lang": "en",
  "window_geometry": ""
}
```

## Keys

- `portable_roots` — folders whose known-junk subfolders are swept (names like
  `Cache`, `Code Cache`, `GPUCache`, `Temp`, `Logs`, `Crashpad`). Numbered
  copies (`Name (2)`) are only removed when the base name is a proven
  cache/temp/log/crash artifact — profile-data backups such as `Login Data (2)`
  or `History (3)` are always kept. Anything not matching junk patterns is
  untouched. A fresh config defaults to `[]` — no personal portable roots are
  hardcoded; add your own folders (a root under `C:\`, `C:\Windows`,
  `USERPROFILE`, Program Files, or the cleaner's own folder is rejected).
- `custom_rules` — `path` (folder) + `pattern` (glob, `*` = whole contents).
- `exclude_patterns` — fnmatch patterns, applied to every deletion.
- `exclude_paths` — exact paths never touched.
- `system_targets` — persisted per-target preferences (T-108): a map of
  `SYSTEM_TARGET_DEFAULTS` names to booleans overriding the safe defaults
  (e.g. `{"System Temp": false}` disables it, `{"Recycle Bin": true}` opts
  into a risky target). Unknown names are dropped on load. The GUI session
  reads it at start; foreground/preview/background/scheduled runs all resolve
  the same mask, and scheduled/background argv carries the full deviation
  (including disabled safe defaults via `--disable-targets`, T-129).
- `auto_clean_interval_hours` — GUI auto-reclean interval; `0` = off.
- `lang` — GUI language: `en`, `ru`, `et`, or `ded`; any missing string falls back
  to English. Read at GUI start.
- `window_geometry` — last GUI window size/position, saved on close and
  restored on start; `""` means the default geometry (clamped to a minimum
  of 800x500).

## Canonicalization (on load)

Every path is normalized the moment the config is read:

- slash style unified (`/` and `\`), trailing separators and duplicate
  separators collapsed, `..` segments resolved
- `%ENV%` variables expanded (e.g. `%LOCALAPPDATA%\Cache`)
- surrounding quotes stripped
- relative paths rejected (must be absolute)
- duplicate roots collapse to one canonical entry
- roots nested inside another configured root are rejected with a warning
- protected paths (blacklist: `C:\`, Windows, Program Files, user profile,
  the cleaner's own folder) are rejected for user roots and custom rules —
  including every descendant; reviewed internal system targets are not user
  roots and keep their own scoped per-target SafetyGuard root

User config values survive upgrades; a legacy `profiles` key is dropped
automatically. The GUI **Exclusions** button edits `exclude_patterns` and
`exclude_paths`; other keys are edited in the JSON by hand.

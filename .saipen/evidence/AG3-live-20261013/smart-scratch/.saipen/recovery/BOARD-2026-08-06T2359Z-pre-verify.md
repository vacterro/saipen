# Board
## DOING
- [/] T-056 Conformance debt (pre-existing, historical): LOG.md E-029..E-038 reused x2 (L200-210 vs L31-33/L188-194), ~100 non-skeleton lines (L35-199), MARKHUNT L192 missing tickets=, taxonomy WARNs, 14 historical ## DONE tickets missing | verify: (T-027, T-019..T-021, T-008..T-017); fix shapes only — renumber reused IDs, wrap historical notes as DEC/H lines, add verify: from LOG evidence | verify: validate.py PASS | owner: buffy | claim_time: 2026-08-07T00:00:00Z

## TODO


## DONE
- [x] T-064 v2.4.14 junk sweep: 12 new safe USER_APPDATA_TARGETS (Windows Search Device/AppIcon cache, iTop Easy Desktop Thumbs, Freebuff, AIChatter Edge profile, Telegram media_cache, Photoshop WebView Local, Adobe Bridge Code/GPU, Ollama Shader, Opera SW CacheStorage/ScriptCache) + _deep_junk_sweep guard fix + Viber per-account glob + Firefox profile caches + ThumbCacheToDelete | verify: 84/84, ruff clean, dry-run 0 errors
- [x] T-065 v2.4.15 Run in bg button: background_clean_argv() (frozen-aware), detached Popen (DETACHED_PROCESS|CREATE_NO_WINDOW), poll() double-click guard, i18n run_bg keys en/ru/et | verify: 84/84, ruff clean, live detached-spawn probe PASS
- [x] T-061 [from saitest ST-001] Remove 4 dead i18n keys (find_new_junk, junk_window_title, scanning, nothing_found) from DEFAULT_STRINGS + strings/ru.json + strings/et.json; add i18n-symmetry regression test (DEFAULT_STRINGS keys ⊆ source refs, ru/et key-sets == en) | reproduction: assert fails with the 4 dead keys | verify: 86/86 PASS, ruff clean, reproduction assert dead=[], TestI18nSymmetry green
- [x] T-062 [from saitranslate TRANSLATE-002] Translate surface sync: README.ru/et GUI sections -> five buttons (Run in bg), 22 GUI keys identical en/ru/et, dead keys dropped | verify: payload==main hash-identical, key-sets green, 86/86 PASS
- [x] T-063 [from saiwiki WIKI-002] Wiki sync: test count 81 -> 86 in docs/Home.md + docs/Build-and-Install.md | verify: payload==docs hash-identical, 86/86 PASS

## DONE
- [x] T-060 HUNT dedupe: `--time HH:MM` row duplicated in docs/CLI-Reference.md + saiwiki payload CLI-Reference.md — removed second copy in both | verify: rg -c "--time HH:MM" == 1 per file, 81/81, ruff clean
- [x] T-059 HUNT dead code: ProgressLogger.warn() + ProgressTracker.set_total() removed (zero callers) | verify: rg dead defs == 0, 81/81, ruff clean
- [x] T-058 collect saiwiki: Exclusions + doc drift sync — Configuration (GUI editor note), Home (Exclusions/progress bullets), CLI-Reference (--time flag) | verify: diff payload vs docs empty, 81/81 passed, ruff clean
- [x] T-057 collect saitranslate: Exclusions surface sync — 23 GUI keys en/ru/et identical, README.ru/et GUI sections synced (Find New Junk removed, Exclusions added) | verify: key-set cross-check clean, 81/81 passed, ruff clean
- [x] T-048 GUI exclude list editor shipped: Exclusions sidebar button + dialog (patterns textbox, paths list + add/remove via browse), Save persists to config, excludes wired into cleaning job, i18n keys en/ru/et | verify: 81/81 passed, ruff clean, GUI smoke PASS, keys present in all lang files
- [x] T-023 GUI exclude list editing delivered via T-048 Exclusions dialog (supersedes "config-only today") | verify: superseded by T-048
- [x] T-053 ProgressTracker wired into cleaners: advance() in _del_dir/_del_file, start/finish_category per cleaner in run_cleaning_job — dashboard Items/Freed now live | verify: 81/81 passed, ruff clean, progress smoke PASS
- [x] T-054 Dead function format_env_path removed (was _SMART_VAC_CLEANER.py:197, zero call sites, no tests) | verify: grep format_env_path=0, 81/81 passed, ruff clean
- [x] T-055 Tray failures no longer silent: _create_tray_icon bare except + _install_scheduled_task parse wrapped, warn via logging.getLogger("vac_cleaner") | verify: warn trace present, 81/81 passed, ruff clean
- [x] T-052 v2.4.11 junk targets: 14 new safe cache paths (DriveFS Logs Local, Razer Engine Cache/Code/GPU/Service Worker, Epic webcache Local, VS Code WebStorage CacheStorage, VerifiedSkill CRX, MaxonApp WebView, Photoshop 2024 Logs, Obsidian GPUCache) | verify: 81/81 passed, ruff clean
- [x] T-051 CLI --analyze-caches dispatch: parsed in main() now calls analyze_caches.main() (previously dead flag) | verify: test_main_analyze_caches_flag PASS
- [x] T-050 saiwiki collect: payload applied to docs/ (v2.4.11 refresh: --analyze-caches, window_geometry, 100+ targets, 81 tests) | verify: diff payload vs docs clean
- [x] T-049 CLI flags docs update: document `--exclude-paths` and `--exclude-patterns` in README CLI table + docs/CLI-Reference.md | verify: flag cross-check clean
- [x] T-047 CLI `--analyze-caches`: native discovery flag (>5 MB caches) in CLI mode without separate script | verify: 81/81 passed, ruff clean
- [x] T-046 Fix doc-drift cluster x4: update "60+ AppData targets" to "100+ AppData targets" in README.md:L18, README.ru.md:L16, README.et.md:L16, docs/Home.md:L9 | verify: grep_search "60+" returns 0
- [x] T-045 Add 38 new junk target paths to USER_APPDATA_TARGETS (Devin, Claude, Antigravity, CodeNomad, Ollama, LM Studio, Substance 3D, AccuRIG, Topaz, Unreal, etc.) | verify: 80/80 passed, ruff clean
- [x] T-041 Fix vintage golden tokens to match UI.md exactly (lighter default golden background, uniform button text color) | verify: python syntax check
- [x] T-040 Apply exact vintage theme tokens to GUI | verify: python syntax check
- [x] T-039 DONE v2.4.2: window geometry persistence restored (parse_geometry, window_geometry key, save_config in close path), 6 tests | verify: 77/77, ruff clean, tag->commit == HEAD (3e02c8c)
- [x] T-038 Ship v2.4.1: saitranslate collected (README.ru/et lang lines), VERSION 2.4.1, pyproject synced, CHANGELOG | verify: 71/71, ruff clean, tag->commit == HEAD (7c8341d)
- [x] T-037 Ship v2.4.1: saiwiki collected (docs/ sync: Home/Configuration/Build-and-Install/FAQ refreshed), OUTBOX applied | verify: diff payload vs docs empty
- [x] T-036 Inject qq+ee: saitranslate -> GUI i18n (lang key, load_strings, all GUI strings localized, strings/ bundled via spec + _MEIPASS fallback); saiwiki -> docs/ (v2.3.1); OUTBOXes applied | verify: 71/71, ruff clean, v2.4.0 c37c241
- [x] T-035 Ship v2.3.1: i18n README ru/et + language switcher, docs/ (saiwiki payload applied), CHANGELOG.md created, VERSION bump 2.3.1, tag pushed | verify: tag->commit == HEAD (0bd6160), 68/68, ruff clean
- [x] T-022 post-publish sanity: GH Actions verified — CI green on main (aeba559) + v2.3.0 + v2.2.0, Build EXE green on v2.3.0 | verify: gh run list success
- [x] T-033 PREPARE WIKI (qq): saiwiki package — 6 pages payload + OUTBOX ready | verify: OUTBOX 7 fields, source_head aeba559, main untouched
- [x] T-034 PREPARE TRANSLATE (ee): saitranslate package — README ru/et + 14 GUI strings ru/et + OUTBOX ready | verify: JSON parses, key sets identical, coverage complete
- [x] T-031 README update: CLI flag table (13 flags, all real), dry-run examples, --find-junk removed (GUI-only), config auto-create + canonicalization notes, GUI section | verify: flag cross-check script clean
- [x] T-032 Path hardening: normalize_path (env vars, slash style, trailing sep, dot-segments, quotes), config loads canonical paths only, portable-root dedupe + nesting/blacklist rejection, custom rule paths normalized | verify: 68/68 tests, ruff clean, user config intact
- [x] T-028 EXE build: PyInstaller onefile console, BASE_DIR next to exe (config/logs portable), build_exe.ps1, spec committed | verify: exe --status OK, GUI exe runs, 32.5 MB
- [x] T-029 CI: build-exe.yml workflow on v* tags, artifact upload | verify: workflow file
- [x] T-030 README: screenshot at top (assets/screenshot.png) + Build-the-exe section | verify: rendered paths exist

- [x] T-024 pyproject.toml + console entry point `vac-cleaner` | verify: pip install -e ., `vac-cleaner --status` OK
- [x] T-025 GUI: confirm dialog (messagebox.askyesno, default No) before real delete | verify: GUI smoke PASS
- [x] T-026 First run: auto-create cleaner_config.json with defaults when missing | verify: test_load_creates_config_file PASS
- [x] T-027 GUI runs write logs/clean_*.log — already implemented (Logger with file in _run_job), verified

- [x] T-018 Git repo: init, LICENSE (MIT), first commit, branch main | verify: `git status` clean, commit b95568d
- [x] T-019 GitHub Actions CI: pytest + ruff on push/PR (.github/workflows/ci.yml)
- [x] T-020 Tests for PortableCleaner sweep logic (numbered copies, running-app skip, old Opera versions, universal cache, chromium profile) — 56 tests total
- [x] T-021 Config migration: dead `profiles` key dropped on load + persisted; user values kept (5 roots, 0 rules)

- [x] T-008 bare `except:` in `_on_close` — tray icon stop failure silently swallowed
- [x] T-009 DeprecationWarning: invalid escape sequences x2 — L884 docstring (raw string), L1637 dead vars removed
- [x] T-010 SystemCleaner + CustomCleaner now pass `progress=` to super().__init__
- [x] T-011 `_del_dir_contents` + `safe_del_dir_contents` now call log.skipped() on safety block
- [x] T-012 Test mocks updated to real args (hidden, time, exclude); added test_main_hidden_flag
- [x] T-013 `get_size()` rewritten iterative — no recursion, no RecursionError
- [x] T-015 `get_running_processes` redundant guard removed
- [x] T-016 Add "Clean Junk" button (real execution) and hide console on GUI start
- [x] T-017 Fix 103 ruff linting errors (implicit optionals, blind exception catches, bad datetimes)

## BLOCKED


# Build & Install

## Requirements

- Windows 10/11
- Python 3.10+

## From source

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run the GUI:

```bat
python _SMART_VAC_CLEANER.py
```

## As a pip package

```bat
pip install .
vac-cleaner --status
```

Installs the `vac-cleaner` console command.

## Standalone exe (no Python needed)

Download `SmartVACCleaner.exe` from the GitHub Releases tab — fully
portable, config and logs live next to the exe. The GUI strings bundle
(`strings/et.json`, `strings/ru.json`, `strings/ded.json`) is embedded in
the exe, so all four languages work offline.

Build it yourself:

```bat
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

Produces `dist\SmartVACCleaner.exe` (PyInstaller onefile). On every `v*`
tag, CI builds and uploads the exe as an artifact automatically.

## Tests

```bat
python -m pytest -q
```

Runs offline, touches only disposable temp directories (automated regression suite).

## CI

- `ci.yml` — pytest + ruff on every push/PR
- `build-exe.yml` — builds the exe on `v*` tags

# OUTBOX

## WIKI-002: maintenance mechanism delivered
- **status:** reviewed
- **summary:** added version-badge drift detection to validate.py + pre-commit hook templates
- **main_project_refs:** [tools/validate.py:604-622, githooks/pre-commit, githooks/pre-commit.ps1]
- **critical:** false
- **severity:** P3
- **details:**
  Drift found across v7.64..v7.80: 4 root docs changed (README +23/-7, SECURITY +20/-4, CONTRIBUTING +13/-5, SPEC +9/-4). All 32 locales showed stale v7.55.0 badge vs current 7.80.0. Fix: added drift detection to validate.py (FAILs on stale badges) + pre-commit hook templates. Collected 2026-07-27 — translate executed, RU/ET/DED refreshed, 29 non-Core ticketed T-186.

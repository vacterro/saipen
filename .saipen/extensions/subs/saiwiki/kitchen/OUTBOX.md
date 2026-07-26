# OUTBOX

## WIKI-002: maintenance mechanism delivered
- **status:** delivered to main project (27.07.2026)
- **action taken:** added translation version-badge drift detection to `tools/validate.py` (canonical validator) + created `githooks/pre-commit` (bash + ps1) hook templates for catching drift before commit
- **drift found (v7.64..v7.80):** 4 root docs changed, not 1. README (+23/-7), SECURITY (+20/-4), CONTRIBUTING (+13/-5), SPEC (+9/-4). All 32 locales show stale version badge (v7.55.0 vs current 7.80.0)
- **main_project_refs:** [tools/validate.py:604-622, githooks/pre-commit, githooks/pre-commit.ps1]
- **critical:** false
- **recommendation:** Run `saipen translate` to refresh all 32 locales against v7.80.0 root docs. The drift is now machine-detectable (validate.py FAILs on stale badges) -- a pre-commit hook using `githooks/pre-commit` catches it before commit, and validate.py catches it in CI
- **collected:** 2026-07-27 — translate executed (RU/ET/DED refreshed, 29 ticketed T-186). Fully consumed.

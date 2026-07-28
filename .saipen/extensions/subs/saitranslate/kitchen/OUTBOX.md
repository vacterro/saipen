# OUTBOX

## SAIT-001: translation kitchen validation
- **status:** reviewed
- **summary:** 32-locale kitchen validated — structure sound, 29 non-Core stale badges (T-186)
- **main_project_refs:** [.saipen/saitranslate/kitchen/]
- **critical:** false
- **severity:** P3
- **details:**
  ALL 32 locales have 4/4 expected files (README, SECURITY, CONTRIBUTING, SPEC) + valid UTF-8. Extra files: all 32 carry `CODE_OF_CONDUCT_XX.md` — not in expected_files list, harmless. Badges: 3 Core (ded, et, ru) at v7.80.0, 29 non-Core stale — matches T-186 scope. Collected 2026-07-27 — consumed, no action needed.

## SAIT-002: WAIT category format in 29 non-Core guides
- **status:** ready
- **summary:** All 29 non-Core locale guides updated from `WAIT: <word>` to `WAIT: <category> -- <word>` format — matches Core v7.93.0+ requirement
- **main_project_refs:** [guides/GUIDE_AR.md, GUIDE_BG.md, GUIDE_CS.md, GUIDE_DA.md, GUIDE_DE.md, GUIDE_EL.md, GUIDE_ES.md, GUIDE_FI.md, GUIDE_FR.md, GUIDE_HE.md, GUIDE_HI.md, GUIDE_HR.md, GUIDE_HU.md, GUIDE_ID.md, GUIDE_IT.md, GUIDE_JA.md, GUIDE_KO.md, GUIDE_NL.md, GUIDE_NO.md, GUIDE_PL.md, GUIDE_PT.md, GUIDE_RO.md, GUIDE_SK.md, GUIDE_SV.md, GUIDE_TH.md, GUIDE_TR.md, GUIDE_UK.md, GUIDE_VI.md, GUIDE_ZH.md]
- **critical:** false
- **severity:** P2
- **details:**
  Each guide had one inline WAIT code reference in the "Good to know" / equivalent section. Changed code literal `<WAIT: <word>>` to `<WAIT: <category> -- <word>>` where `<word>` is locale-specific translation of "question". The 7 category keywords stay English (same as the category values themselves: `manual-verify`, `destructive-op`, etc.). Drift detector should now show 0 stale guides.

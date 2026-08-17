# OUTBOX

## SAIT-008: translated fast-keys callout roll-out -- superseded by SAIT-011
- **legacy:** true
- **status:** stale
- **superseded_by:** SAIT-011 -- README.md prose moved again (cc routes to `saipen continue`, no-install reads INDEX.md), FORCE-FRESH re-pass landed
- **summary:** Translated fast-keys callout (T-394) deployed across 32 kitchen locales, 3 root mirrors, 28 non-Core guides at v7.146.0-era. Old cc description ("Goal Mode") superseded by convergence semantics in SAIT-011.
- **critical:** false
- **producer:** saitranslate
- **source_head:** 0c73f36
- **coverage:**
  - 13 locale GUIDE files (GUIDE_AR/DA/FI/HE/IT/KO/NL/NO/PL/PT/SV/TH/VI.md) opening prose contract
  - guides/ directory (33 guides total, all checked)
- **payload:**
  - guides/GUIDE_AR.md, GUIDE_DA.md, GUIDE_FI.md, GUIDE_HE.md, GUIDE_IT.md, GUIDE_KO.md, GUIDE_NL.md, GUIDE_NO.md, GUIDE_PL.md, GUIDE_PT.md, GUIDE_SV.md, GUIDE_TH.md, GUIDE_VI.md -- English narrative prose paragraph before fast keys
- **verified:** PASS -- tools/validate.py PASS (0 FAILs) at production time; all 13 guides parse-valid, prose contract satisfied
- **instructions:**
  1. Superseded -- collect SAIT-011 instead.

## SAIT-011: FORCE-FRESH translation to v7.219.0 truth (cc continue semantics + INDEX.md)
- **status:** ready
- **summary:** FORCE-FRESH re-translation of the 28 non-Core kitchen locales + their guides to the current README.md truth (HEAD 2720d5d1, v7.219.0): cc callout moved from "Goal Mode" to continue/convergence semantics (CORE.md § 1.10 T-537), no-install line reads saipen/INDEX.md instead of saipen/RFC.md. All 32 kitchen locale READMEs restamped to the new normalized source digest.
- **critical:** false
- **producer:** saitranslate
- **source_head:** 2720d5d151c49eb7987145f7365e3ed5b17da1a5
- **source_tree_fingerprint:** git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:**
  - 28 non-Core kitchen locale READMEs (ar bg cs da de el es fi fr he hi hr hu id it ko nl no pl pt ro sk sv th tr uk vi zh) -- fast-keys callout retranslated to `cc`-continues-context semantics; no-install line switched to saipen/INDEX.md where carried
  - 32/32 kitchen locale READMEs -- source-digest marker restamped to 7550073e... (README.md normalized content)
  - 28 non-Core guides (guides/GUIDE_{AR..ZH}.md) -- callout synced link-adjusted with their locale source
  - Core-owned kitchen copies (et/ru/ded/ja) -- digest restamp only; callout already current (Core did it), no-install line fixed to INDEX.md
- **payload:**
  - guides/GUIDE_AR.md, GUIDE_BG.md, GUIDE_CS.md, GUIDE_DA.md, GUIDE_DE.md, GUIDE_EL.md, GUIDE_ES.md, GUIDE_FI.md, GUIDE_FR.md, GUIDE_HE.md, GUIDE_HI.md, GUIDE_HR.md, GUIDE_HU.md, GUIDE_ID.md, GUIDE_IT.md, GUIDE_KO.md, GUIDE_NL.md, GUIDE_NO.md, GUIDE_PL.md, GUIDE_PT.md, GUIDE_RO.md, GUIDE_SK.md, GUIDE_SV.md, GUIDE_TH.md, GUIDE_TR.md, GUIDE_UK.md, GUIDE_VI.md, GUIDE_ZH.md -- fast-keys callout updated to new cc semantics (link-adjusted ../saipen/RFC.md#110-command-surface)
  - Kitchen working copies already carry the new callouts/digests (sub-owned surface, not a collect payload)
- **verified:** PASS -- tools/validate.py PASS: "shortcut callouts aligned across 32 locale sources, 3 mirrors, 33 locale guides, and both root entry docs"; translation-stale WARN cleared (32/32 digests = 7550073e...); per-locale marker check, guide-sync spot checks (bg/zh/fr), and freshness triple all satisfied
- **instructions:**
  1. Verify source_head: `git rev-parse --short HEAD` == 2720d5d1 and `python tools/freshness.py` triple matches the fields above.
  2. Validate: `python tools/validate.py` -- expect no FAILs; translation-stale must not list any locale.
  3. Review the 28 guide callouts for translation quality.
  4. Commit: `git add guides/GUIDE_{AR,BG,CS,DA,DE,EL,ES,FI,FR,HE,HI,HR,HU,ID,IT,KO,NL,NO,PL,PT,RO,SK,SV,TH,TR,UK,VI,ZH}.md` and commit with message style `saitranslate: SAIT-011 retranslate cc callout + INDEX.md to v7.219.0 truth`.

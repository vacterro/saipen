# OUTBOX



## SAIT-030: FORCE-FRESH re-bind to 71455482 (v8.0.1 closure) -- 32/32 locales CURRENT, zero content drift
- **status:** ready
- **summary:** SAIT-029 re-bound to the current source triple with zero locale-content change. HEAD moved 35ca656e -> 71455482 (v8.0.1 ship 380b30f6 + closure 71455482) and the tree carries the next release's in-flight engine delta; the README translation digest sha256:877128c30331e9502a2b2cde921db503e98f9e63ee38fb9a9acee408eacdbd0b is unchanged (v8.0.1's badge bump normalises out). All 33 surfaces (32 locales + ded) verified by the kitchen's own structurally_current contract: digest stamps 877128c3, badges v8.0.1, fence/heading/table counts current, no model-leak markers, shortcut callouts synced (README.ee/ded/ja mirror sources, guides/GUIDE_*.md others, saipen/RFC.md#110-command-surface anchor preserved). No translation pass was needed and none was faked. Payload = 32 locale README_*.md + 3 root mirrors (35 authenticated entries), strict READY sha256:2a004520d1d128ec9b1f841001fcf0a3e2b311fc73030b42f414bf16a94e10fd at epoch 5.
- **main_project_refs:** [README.md, VERSION, SPEC.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, GUIDE.md, saipen/phases/translate.md, guides/GUIDE_*.md, README.ee.md, README.ja.md, README.ded.md]
- **critical:** false
- **severity:** P3
- **producer:** saitranslate
- **source_head:** 7145548211d2ee3ca9babf5e8b251960ea8f0527
- **source_tree_fingerprint:** git-delta-v1:c53b5d85ed1b470590003e1d5c2b0f531fd55a6d730f3c20bcdf1b01b4d1025a
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md in .saipen/saitranslate/kitchen/*/README_*.md (ar bg cs da de ded el es et fi fr he hi hr hu id it ja ko nl no pl pt ro ru sk sv th tr uk vi zh) + 3 root README.ee/ja/ded mirrors; all 35 bound to README translation digest sha256:877128c30331e9502a2b2cde921db503e98f9e63ee38fb9a9acee408eacdbd0b with badges v8.0.1; no in-app UI surface
- **payload:** [.saipen/saitranslate/kitchen/ar/README_AR.md, bg/README_BG.md, cs/README_CS.md, da/README_DA.md, de/README_DE.md, ded/README_DED.md, el/README_EL.md, es/README_ES.md, et/README_ET.md, fi/README_FI.md, fr/README_FR.md, he/README_HE.md, hi/README_HI.md, hr/README_HR.md, hu/README_HU.md, id/README_ID.md, it/README_IT.md, ja/README_JA.md, ko/README_KO.md, nl/README_NL.md, no/README_NO.md, pl/README_PL.md, pt/README_PT.md, ro/README_RO.md, ru/README_RU.md, sk/README_SK.md, sv/README_SV.md, th/README_TH.md, tr/README_TR.md, uk/README_UK.md, vi/README_VI.md, zh/README_ZH.md, README.ee.md, README.ja.md, README.ded.md]
- **verified:** PASS -- strict READY sha256:2a004520d1d128ec9b1f841001fcf0a3e2b311fc73030b42f414bf16a94e10fd published at producer epoch 5 with 44 read dependencies and 35 authenticated payload entries; 33/33 surfaces structurally_current against digest 877128c3 (zero page-content delta vs SAIT-029); freshness bound at 71455482/c53b5d85; no integration, commit, tag, push, or remote write performed
- **instructions:** Run python -B tools/validate.py --gate collect:saitranslate; refuse on any source/role/payload mismatch. Integrate only READY package sha256:2a004520d1d128ec9b1f841001fcf0a3e2b311fc73030b42f414bf16a94e10fd through the canonical Core writer; recheck mirror byte-equality, Core gate, and REVIEW before SHIP.
- **details:** SAIT-029 (35ca656e/f2e3a0e1) went stale on the freshness triple alone: v8.0.1 ship + closure landed and the worktree carries the T-1303/T-1301/T-1302 engine delta, neither touching any translation-facing byte. Deterministic re-scan first: 32/32 digest stamps equal the live 877128c3 README digest, callout parity exact, structurally_current 33/33 -- so the package re-published through kitchen/_publish_package.py (ProducerEpoch.claim epoch 5, StagingGeneration, atomic READY) with zero locale mutation. Known moving-target hazard: if T-1304's audit execution or any engine work mutates the tree before collection, the triple moves again and ee must rerun. Main tree and wiki/remote surfaces untouched.

## SAIT-029: FORCE-FRESH translation package v8.0.1 -- 32/32 locales CURRENT (HEAD 35ca656e)
- **status:** stale
- **superseded_by:** SAIT-030 -- FORCE-FRESH re-bind to 71455482/c53b5d85 after v8.0.1 closure; zero content drift
- **summary:** All 32 kitchen locale README_*.md surfaces + 3 root mirrors re-stamped against the live README.md translation digest sha256:877128c3: badges v8.0.0 -> v8.0.1, digest stamps bb47f715 -> 877128c3; locale shortcut callout links stay saipen/RFC.md#110-command-surface (validator contract pins locale callouts to the RFC anchor). Zero prose drift: no translation pass needed, and none was faked. Payload = 32 locale README_*.md + 3 root mirrors (35 authenticated entries), strict READY sha256:77c225b1 at epoch 4.
- **main_project_refs:** [README.md, VERSION, SPEC.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, GUIDE.md, saipen/phases/translate.md, guides/GUIDE_*.md, README.ee.md, README.ja.md, README.ded.md]
- **critical:** false
- **severity:** P3
- **producer:** saitranslate
- **source_head:** 35ca656e7a9bcee92f3fed6ecde58fee1c9795de
- **source_tree_fingerprint:** git-delta-v1:f2e3a0e1f406832828f0947de295d178d6d6cad6732a3b8c9df57953a7fd86e4
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md in .saipen/saitranslate/kitchen/*/README_*.md (ar bg cs da de ded el es et fi fr he hi hr hu id it ja ko nl no pl pt ro ru sk sv th tr uk vi zh) + 3 root README.ee/ja/ded mirrors; all 35 bound to README translation digest sha256:877128c30331e9502a2b2cde921db503e98f9e63ee38fb9a9acee408eacdbd0b with badges v8.0.1; no in-app UI surface
- **payload:** [.saipen/saitranslate/kitchen/ar/README_AR.md, bg/README_BG.md, cs/README_CS.md, da/README_DA.md, de/README_DE.md, ded/README_DED.md, el/README_EL.md, es/README_ES.md, et/README_ET.md, fi/README_FI.md, fr/README_FR.md, he/README_HE.md, hi/README_HI.md, hr/README_HR.md, hu/README_HU.md, id/README_ID.md, it/README_IT.md, ja/README_JA.md, ko/README_KO.md, nl/README_NL.md, no/README_NO.md, pl/README_PL.md, pt/README_PT.md, ro/README_RO.md, ru/README_RU.md, sk/README_SK.md, sv/README_SV.md, th/README_TH.md, tr/README_TR.md, uk/README_UK.md, vi/README_VI.md, zh/README_ZH.md, README.ee.md, README.ja.md, README.ded.md]
- **verified:** PASS -- strict READY sha256:77c225b1b8677383c0483dfa1aed08b2ee4dd88ee731cdf8b9d2c4092eeff7e1 published at producer epoch 4 with 44 read dependencies and 35 authenticated payload entries; 32/32 locale digest stamps match 877128c3 (current validator-rule README digest); badges v8.0.1 across all 35 surfaces; freshness bound at 35ca656e/f2e3a0e1; core validator 0 FAILs before publish; no integration, commit, tag, push, or remote write performed
- **instructions:** Run python -B tools/validate.py --gate collect:saitranslate; refuse on any source/role/payload mismatch. Integrate only READY package sha256:77c225b1b8677383c0483dfa1aed08b2ee4dd88ee731cdf8b9d2c4092eeff7e1 through the canonical Core writer; recheck mirror byte-equality, Core gate, and REVIEW before SHIP.
- **details:** SAIT-028 (bound to 02fd4892/eab67ebe, badges v7.249.0, digest bb47f715) marked stale: the source triple moved 02fd4892/eab67ebe -> 35ca656e/f2e3a0e1 across the v8.0.0 -> v8.0.1 ships while the English README's only textual drift was its version badge line. The validator-rule README digest moved bb47f715 -> 877128c3 with the stamp, so all 35 surfaces were restamped and their badges bumped to v8.0.1. An interim RFC->CORE callout-link swap across the 32 locales was reverted: validate.py pins locale callouts to saipen/RFC.md#110-command-surface (the RFC anchor stub), and the core run passes with 0 FAILs. Re-verified live before publish. No integration, commit, tag, push, or remote write performed.

## SAIT-028: FORCE-FRESH translation package v7.249.0 -- 32/32 locales CURRENT (HEAD 02fd4892)
- **status:** stale
- **superseded_by:** SAIT-029 -- source triple moved 02fd4892/eab67ebe -> 35ca656e/f2e3a0e1 (v8.0.1 ship); all 35 surfaces restamped to digest 877128c3, badges v8.0.1
- **summary:** All 32 kitchen locale README_*.md surfaces re-verified CURRENT against the live README.md translation digest sha256:bb47f715 (version strings normalised out). Zero prose drift: 32/32 digest stamps match, badges v7.249.0. Root mirrors README.ee/ja/ded at v7.249.0 and aligned with the kitchen et/ja/ded sources. Payload = 32 locale README_*.md + 3 root mirrors (35 authenticated entries), strict READY sha256:4ae185840a717cae5c6ccaa03e9272b0aff82432bdb0bfcb9745630b2acba081 at epoch 3.
- **main_project_refs:** [README.md, VERSION, SPEC.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, GUIDE.md, saipen/phases/translate.md, guides/GUIDE_*.md, README.ee.md, README.ja.md, README.ded.md]
- **critical:** false
- **severity:** P3
- **producer:** saitranslate
- **source_head:** 02fd489277227ffe65971f7cf06febb355233892
- **source_tree_fingerprint:** git-delta-v1:eab67ebe378ac04b1ebbf7bfb9a19d5d897f48739279d8f969ee8c227f3d28fd
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md in .saipen/saitranslate/kitchen/*/README_*.md (ar bg cs da de ded el es et fi fr he hi hr hu id it ja ko nl no pl pt ro ru sk sv th tr uk vi zh) + 3 root README.ee/ja/ded mirrors; all 35 bound to README translation digest sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 with badges v7.249.0; no in-app UI surface
- **payload:** [.saipen/saitranslate/kitchen/ar/README_AR.md, bg/README_BG.md, cs/README_CS.md, da/README_DA.md, de/README_DE.md, ded/README_DED.md, el/README_EL.md, es/README_ES.md, et/README_ET.md, fi/README_FI.md, fr/README_FR.md, he/README_HE.md, hi/README_HI.md, hr/README_HR.md, hu/README_HU.md, id/README_ID.md, it/README_IT.md, ja/README_JA.md, ko/README_KO.md, nl/README_NL.md, no/README_NO.md, pl/README_PL.md, pt/README_PT.md, ro/README_RO.md, ru/README_RU.md, sk/README_SK.md, sv/README_SV.md, th/README_TH.md, tr/README_TR.md, uk/README_UK.md, vi/README_VI.md, zh/README_ZH.md, README.ee.md, README.ja.md, README.ded.md]
- **verified:** PASS -- strict READY sha256:4ae185840a717cae5c6ccaa03e9272b0aff82432bdb0bfcb9745630b2acba081 published at producer epoch 3 with 44 read dependencies and 35 authenticated payload entries; 32/32 locale digest stamps match bb47f715 (current normalised README content); badges v7.249.0 across all 35 surfaces; freshness bound at 02fd4892/eab67ebe; git diff --check clean; no integration, commit, tag, push, or remote write performed
- **instructions:** Run python -B tools/validate.py --gate collect:saitranslate; refuse on any source/role/payload mismatch. Integrate only READY package sha256:4ae185840a717cae5c6ccaa03e9272b0aff82432bdb0bfcb9745630b2acba081 through the canonical Core writer; recheck mirror byte-equality, Core gate, and REVIEW before SHIP.
- **details:** SAIT-027 (bound to 312d4f37/4d4bdae8, badges 7.248.0) marked stale: ship v7.249.0 (T-1270, 6fe83d60/02fd4892) moved the source triple while the English README's only textual drift was its version badge. The translation digest (bb47f715, versions normalised out) is therefore unchanged and the ship already bumped every locale and root-mirror badge to v7.249.0, so this force-fresh is a verify-and-rebind with zero prose re-translation required -- no translate pass needed, and none was faked. Re-verified live: the normalised README digest equals bb47f715 and the 35 surface badges match VERSION 7.249.0. No integration, commit, tag, push, or remote write performed.

## SAIT-027: FORCE-FRESH translation package v7.248.0 -- 32/32 locales CURRENT (HEAD 312d4f37)

- **status:** stale
- **superseded_by:** SAIT-028 -- source triple moved 312d4f37/4d4bdae8 -> 02fd4892/eab67ebe (v7.249.0 ship); locale badges already bumped to v7.249.0
- **summary:** All 32 kitchen locale README_*.md surfaces re-verified CURRENT against the live README.md translation digest sha256:bb47f715 (version strings normalised out). Zero prose drift: 32/32 digest stamps match, badges v7.248.0. Root mirrors README.ee/ja/ded at v7.248.0 and aligned with the kitchen et/ja/ded sources. Payload = 32 locale README_*.md + 3 root mirrors (35 authenticated entries), strict READY sha256:e3a17cc98d03753f20595cf4f73bedba46c1a43a4d7a1376c50806e25378aabc at epoch 2.
- **main_project_refs:** [README.md, VERSION, SPEC.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, GUIDE.md, saipen/phases/translate.md, guides/GUIDE_*.md, README.ee.md, README.ja.md, README.ded.md]
- **critical:** false
- **severity:** P3
- **producer:** saitranslate
- **source_head:** 312d4f37b69f3a52f6b46ad7854bad45ff31a356
- **source_tree_fingerprint:** git-delta-v1:4d4bdae83a2d787b1880a4e80324a164f6dcc1679295c90e269dd137e8dc79cd
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md in .saipen/saitranslate/kitchen/*/README_*.md (ar bg cs da de ded el es et fi fr he hi hr hu id it ja ko nl no pl pt ro ru sk sv th tr uk vi zh) + 3 root README.ee/ja/ded mirrors; all 35 bound to README translation digest sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 with badges v7.248.0; no in-app UI surface
- **payload:** [.saipen/saitranslate/kitchen/ar/README_AR.md, bg/README_BG.md, cs/README_CS.md, da/README_DA.md, de/README_DE.md, ded/README_DED.md, el/README_EL.md, es/README_ES.md, et/README_ET.md, fi/README_FI.md, fr/README_FR.md, he/README_HE.md, hi/README_HI.md, hr/README_HR.md, hu/README_HU.md, id/README_ID.md, it/README_IT.md, ja/README_JA.md, ko/README_KO.md, nl/README_NL.md, no/README_NO.md, pl/README_PL.md, pt/README_PT.md, ro/README_RO.md, ru/README_RU.md, sk/README_SK.md, sv/README_SV.md, th/README_TH.md, tr/README_TR.md, uk/README_UK.md, vi/README_VI.md, zh/README_ZH.md, README.ee.md, README.ja.md, README.ded.md]
- **verified:** PASS -- strict READY sha256:e3a17cc98d03753f20595cf4f73bedba46c1a43a4d7a1376c50806e25378aabc published at producer epoch 2 with 44 read dependencies and 35 authenticated payload entries; 32/32 locale digest stamps match bb47f715 (current normalised README content); badges v7.248.0 across all 35 surfaces; freshness bound at 312d4f37/4d4bdae8; git diff --check clean; no integration, commit, tag, push, or remote write performed
- **instructions:** Run python -B tools/validate.py --gate collect:saitranslate; refuse on any source/role/payload mismatch. Integrate only READY package sha256:e3a17cc98d03753f20595cf4f73bedba46c1a43a4d7a1376c50806e25378aabc through the canonical Core writer; recheck mirror byte-equality, Core gate, and REVIEW before SHIP.
- **details:** SAIT-026 (bound to 0c931d76/9f44e944, badges 7.243.0) marked stale: the source triple moved through v7.244.0-v7.248.0 while the English README's only textual drift was its version badge. The translation digest (bb47f715, versions normalised out) is therefore unchanged and every locale surface already carries the v7.248.0 badge, so this force-fresh is a verify-and-rebind with zero prose re-translation required -- no translate pass needed, and none was faked. Re-verified live: validate.py reports no translation-stale and no translation-unstamped WARN, and the 32 locale badges match VERSION. No integration, commit, tag, push, or remote write performed.

## SAIT-026: FORCE-FRESH translation package v7.243.0 -- 32/32 locales CURRENT (HEAD 0c931d76)

- **status:** stale
- **superseded_by:** SAIT-027 -- source triple moved 0c931d76/9f44e944 -> 312d4f37/4d4bdae8 (v7.248.0); locale badges already bumped to v7.248.0
- **summary:** All 32 kitchen locale README_*.md surfaces verified CURRENT against the live normalized README.md (sha256:bb47f715). No drift: 32/32 digests match, badges 7.243.0. Root mirrors README.ee/ja/ded also CURRENT (same digest, badges 7.243.0). Payload = 32 locale README_*.md + 3 root mirrors (35 authenticated entries), strict READY sha256:d26a31407d99efef6a1e45c585190fdd638e88aed732be4713953e4fbdf6b2c2 at epoch 1.
- **main_project_refs:** [README.md, VERSION, SPEC.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, GUIDE.md, saipen/phases/translate.md, guides/GUIDE_*.md, README.ee.md, README.ja.md, README.ded.md]
- **critical:** false
- **severity:** P3
- **producer:** saitranslate
- **source_head:** 0c931d769e54080344fc05fece0044bd819afa44
- **source_tree_fingerprint:** git-delta-v1:9f44e94477fcad090a3e644969f6d5b6624e81447e99cd62d2be5eb7c11e5544
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md in .saipen/saitranslate/kitchen/*/README_*.md (ar bg cs da de ded el es et fi fr he hi hr hu id it ja ko nl no pl pt ro ru sk sv th tr uk vi zh) + 3 root README.ee/ja/ded mirrors; all 35 bound to normalized README digest sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7; no in-app UI surface
- **payload:** [.saipen/saitranslate/kitchen/ar/README_AR.md, bg/README_BG.md, cs/README_CS.md, da/README_DA.md, de/README_DE.md, ded/README_DED.md, el/README_EL.md, es/README_ES.md, et/README_ET.md, fi/README_FI.md, fr/README_FR.md, he/README_HE.md, hi/README_HI.md, hr/README_HR.md, hu/README_HU.md, id/README_ID.md, it/README_IT.md, ja/README_JA.md, ko/README_KO.md, nl/README_NL.md, no/README_NO.md, pl/README_PL.md, pt/README_PT.md, ro/README_RO.md, ru/README_RU.md, sk/README_SK.md, sv/README_SV.md, th/README_TH.md, tr/README_TR.md, uk/README_UK.md, vi/README_VI.md, zh/README_ZH.md, README.ee.md, README.ja.md, README.ded.md]
- **verified:** PASS -- 32/32 locale digests match sha256:bb47f715 (current normalized README.md 7.243.0); 3/3 root mirrors digests match same source and badges 7.243.0; strict READY sha256:d26a31407d99efef6a1e45c585190fdd638e88aed732be4713953e4fbdf6b2c2 published at producer epoch 1 with 44 read dependencies and 35 authenticated payload entries (freshness CURRENT at 0c931d76/9f44e944); git diff --check clean; no integration, commit, tag, push, or remote write performed
- **instructions:** Run python -B tools/validate.py --gate collect:saitranslate; refuse on any source/role/payload mismatch. Integrate only READY package sha256:d26a31407d99efef6a1e45c585190fdd638e88aed732be4713953e4fbdf6b2c2 through the canonical Core writer; recheck mirror byte-equality, Core gate, and REVIEW before SHIP.
- **details:** SAIT-025 (c7ea5b1b -> staged) claimed 32 locales stale under digest 9fbc9510 because it only regenerated the 3 root mirrors. Live kitchen proves the opposite: all 32 locale digests are bb47f715, which equals the current normalized README digest, and validate.py confirms no translation-stale WARN. SAIT-025 is therefore superseded as stale even though its source_head differs (it was 3-root-only, not 32-wide). Re-reading the live tree at 0c931d76 gives CURRENT; no in-app UI surface exists to claim.

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

- **status:** stale
- **superseded_by:** SAIT-012 -- README.md was substantially rewritten; the old 32-locale bundle no longer represented the source
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

## SAIT-012: FORCE-FRESH complete translation package for current README truth

- **status:** stale
- **superseded_by:** SAIT-013 -- Core VERIFY rejected widespread trailing whitespace and 1.7B model commentary/JSON leakage; the package was settled but never shipped
- **summary:** Rebuilt all 32 locale README surfaces from the current 316-line README.md, preserved the maintained shortcut callouts, verified the five unchanged translated policy/spec surfaces across every locale, and prepared current ET/JA/DED root-mirror candidates. No tracked in-app UI/i18n surface exists.
- **critical:** false
- **producer:** saitranslate
- **source_head:** 3a343e8d0e5a04e2cb43b671c9072996e810c65a
- **source_tree_fingerprint:** git-delta-v1:4ec002cc5f2d23a8858d6c959ec2704e25be28f555a0396e5502685a0a4f3eb6
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:**
  - README.md: 32/32 locale candidates (ar, bg, cs, da, de, ded, el, es, et, fi, fr, he, hi, hr, hu, id, it, ja, ko, nl, no, pl, pt, ro, ru, sk, sv, th, tr, uk, vi, zh), all bound to normalized source digest `2a33e364c3c12e8b1b9b2caf41b05db3ee27f17161336579ae85ee59da34fe56`
  - SPEC.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md: 32/32 existing locale files per source, all non-empty and structurally checked; canonical sources are unchanged since those translations were produced
  - GUIDE.md/guides/: 33 hand-maintained locale siblings retained under the carve-out; the 28 non-Core shortcut callouts remain the exact link-adjusted source for their locale README callouts
  - Root README mirrors: README.ee.md, README.ja.md, README.ded.md complete candidates derived from the current README structure, with maintained language switcher and shortcut callout preserved
  - In-app UI: none -- tracked-source scan found no i18n/locale bundle or app-view source (`tsx`, `jsx`, `vue`, `svelte`, `html`, `qml`); no fictional UI bundle was created
- **payload:**
  - `.saipen/saitranslate/kitchen/ar/README_AR.md`, `.saipen/saitranslate/kitchen/bg/README_BG.md`, `.saipen/saitranslate/kitchen/cs/README_CS.md`, `.saipen/saitranslate/kitchen/da/README_DA.md`, `.saipen/saitranslate/kitchen/de/README_DE.md`, `.saipen/saitranslate/kitchen/ded/README_DED.md`, `.saipen/saitranslate/kitchen/el/README_EL.md`, `.saipen/saitranslate/kitchen/es/README_ES.md`, `.saipen/saitranslate/kitchen/et/README_ET.md`, `.saipen/saitranslate/kitchen/fi/README_FI.md`, `.saipen/saitranslate/kitchen/fr/README_FR.md`, `.saipen/saitranslate/kitchen/he/README_HE.md`, `.saipen/saitranslate/kitchen/hi/README_HI.md`, `.saipen/saitranslate/kitchen/hr/README_HR.md`, `.saipen/saitranslate/kitchen/hu/README_HU.md`, `.saipen/saitranslate/kitchen/id/README_ID.md`, `.saipen/saitranslate/kitchen/it/README_IT.md`, `.saipen/saitranslate/kitchen/ja/README_JA.md`, `.saipen/saitranslate/kitchen/ko/README_KO.md`, `.saipen/saitranslate/kitchen/nl/README_NL.md`, `.saipen/saitranslate/kitchen/no/README_NO.md`, `.saipen/saitranslate/kitchen/pl/README_PL.md`, `.saipen/saitranslate/kitchen/pt/README_PT.md`, `.saipen/saitranslate/kitchen/ro/README_RO.md`, `.saipen/saitranslate/kitchen/ru/README_RU.md`, `.saipen/saitranslate/kitchen/sk/README_SK.md`, `.saipen/saitranslate/kitchen/sv/README_SV.md`, `.saipen/saitranslate/kitchen/th/README_TH.md`, `.saipen/saitranslate/kitchen/tr/README_TR.md`, `.saipen/saitranslate/kitchen/uk/README_UK.md`, `.saipen/saitranslate/kitchen/vi/README_VI.md`, `.saipen/saitranslate/kitchen/zh/README_ZH.md`
  - README.ee.md from `.saipen/saitranslate/kitchen/et/README_ET.md`
  - README.ja.md from `.saipen/saitranslate/kitchen/ja/README_JA.md`
  - README.ded.md from `.saipen/saitranslate/kitchen/ded/README_DED.md`
- **verified:** PASS -- 32 locales; normalized digest 32/32; version badge 32/32; heading/fence/table-row parity 32/32; no leaked placeholders; required `reply_language`, `/saipen continue`, `/saipen crew`, and 15-key shortcut surface present 32/32; `python -B tools/validate.py --gate core` PASS; strict v7 package published at epoch 3 with 44 read dependencies and 35 payload entries
- **instructions:**
  1. Recompute source identity and require exact `source_head`, `source_tree_fingerprint`, and `role_revision` matches above.
  2. Run `python -B tools/validate.py --gate collect:saitranslate`; refuse on any producer or payload mismatch.
  3. Open strict READY package `sha256:f03d49dd90998c9b3aa84e14f120d02bdd572f1d6f0310192ca381d0c9132fc9` and integrate only its 35 declared payload entries through the canonical Core writer.
  4. Verify the three root mirrors, 32 source digests, shortcut-callout parity, UTF-8 validity, and full repository gate before REVIEW/SHIP.

## SAIT-013: verified 14B regeneration of the complete translation package

- **status:** stale
- **superseded_by:** SAIT-014 -- HEAD 3a343e8d -> e045ad07 (v7.226.0 audit commit CORE-002..007 + W2-004..008), tree git-delta-v1:d3538d0b -> git-delta-v1:da948fff; kitchen READMEs were rewritten 21.08 23:41 (after SAIT-013's 06:47 publish), so content as well as the freshness triple moved; FORCE-FRESH re-bind + re-package
- **summary:** Regenerated all 32 current README translations with qwen3:14b after Core rejected SAIT-012's 1.7B output. Cache identity now binds the model and prompt contract; publish rejects model commentary, replacement characters, structural drift, and trailing whitespace.
- **critical:** false
- **producer:** saitranslate
- **source_head:** 3a343e8d0e5a04e2cb43b671c9072996e810c65a
- **source_tree_fingerprint:** git-delta-v1:d3538d0b049e9f36c9bb009fd2e4ca1944be44c48b823ad36a115010e93e74c4
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:**
  - README.md: 32/32 locale candidates (ar, bg, cs, da, de, ded, el, es, et, fi, fr, he, hi, hr, hu, id, it, ja, ko, nl, no, pl, pt, ro, ru, sk, sv, th, tr, uk, vi, zh), all bound to normalized source digest `2a33e364c3c12e8b1b9b2caf41b05db3ee27f17161336579ae85ee59da34fe56`
  - Model/cache contract: qwen3:14b + `structured-markdown-v2` marker on 32/32 outputs; old qwen3:1.7b cache entries cannot satisfy the new cache key
  - Structure: heading/fence/table parity 32/32; maintained shortcut callout synced from each canonical guide/mirror source
  - Quality: zero `</think>`, `*Note:`, JSON-explanation leakage, U+FFFD replacement characters, leaked placeholders, or trailing whitespace across all 32 outputs
  - Root README mirrors: README.ee.md, README.ja.md, README.ded.md payloads derive byte-for-byte from ET, JA, and DED kitchen outputs
  - In-app UI: none -- no tracked i18n/locale bundle or app-view surface exists
- **payload:**
  - `.saipen/saitranslate/kitchen/{ar,bg,cs,da,de,ded,el,es,et,fi,fr,he,hi,hr,hu,id,it,ja,ko,nl,no,pl,pt,ro,ru,sk,sv,th,tr,uk,vi,zh}/README_*.md` -- exact 32 paths authenticated in READY
  - README.ee.md from `.saipen/saitranslate/kitchen/et/README_ET.md`
  - README.ja.md from `.saipen/saitranslate/kitchen/ja/README_JA.md`
  - README.ded.md from `.saipen/saitranslate/kitchen/ded/README_DED.md`
- **verified:** PASS -- independent audit found 32 files, structural_bad=[], leaks=[], replacement_chars=[], normalized digest 32/32; `git diff --check` PASS; Ruff 0.16.0 PASS; strict READY epoch 4 has 44 read dependencies and 35 authenticated payload entries
- **instructions:**
  1. Recompute and require the exact source triple above.
  2. Run `python -B tools/validate.py --gate collect:saitranslate`; refuse on any mismatch.
  3. Integrate only READY package `sha256:401234f6adbd111251822a708243911acf48118466b7c3a4feb3e746926e73ff` through the canonical Core writer.
  4. Re-run the independent 32-file quality audit, mirror byte equality, Core gate, and REVIEW before SHIP.

## SAIT-014: FORCE-FRESH re-bind + re-package to e045ad07 (v7.226.0)

- **status:** stale
- **superseded_by:** SAIT-015
- **summary:** SAIT-013 went stale by freshness triple (HEAD 3a343e8d -> e045ad07 from the v7.226.0 audit commit CORE-002..007 + W2-004..008) and by content (the 32 kitchen READMEs were rewritten 21.08 23:41, after SAIT-013's 06:47 publish). FORCE-FRESH re-ran the producer pipeline: recomputed source identity (HEAD e045ad07, tree git-delta-v1:da948fff), rebuilt the package, and re-published a fresh strict READY. 32 locale README_*.md payloads + 3 root mirrors (README.ee/ja/ded) = 35 payload entries; 44 read dependencies (README/VERSION/SPEC/CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/GUIDE.md/saipen/phases/translate.md + 33 guides + 3 mirrors). All 32 locales remain bound to normalized source digest 2a33e364c3c12e8b1b9b2caf41b05db3ee27f17161336579ae85ee59da34fe56 -- README.md itself was unchanged by the audit commit, so the translations still represent current source.
- **critical:** false
- **producer:** saitranslate
- **source_head:** e045ad07d21aac78cce073caa732a5780652882b
- **source_tree_fingerprint:** git-delta-v1:da948fff473f55fd9259f33606e1d19f4db8141bf037cc76c367c4737a0b8e8b
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:**
  - README.md: 32/32 locale candidates (ar, bg, cs, da, de, ded, el, es, et, fi, fr, he, hi, hr, hu, id, it, ja, ko, nl, no, pl, pt, ro, ru, sk, sv, th, tr, uk, vi, zh), all bound to normalized source digest `2a33e364c3c12e8b1b9b2caf41b05db3ee27f17161336579ae85ee59da34fe56`
  - SPEC.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md: 32/32 existing locale files per source, structurally checked; canonical sources unchanged
  - GUIDE.md/guides/: 33 hand-maintained locale siblings retained under the carve-out; 28 non-Core shortcut callouts link-adjusted from their locale source
  - Root README mirrors: README.ee.md, README.ja.md, README.ded.md complete candidates, language switcher + shortcut callout preserved
  - In-app UI: none -- tracked-source scan found no i18n/locale bundle or app-view surface; no fictional UI bundle created
- **payload:**
  - `.saipen/saitranslate/kitchen/{ar,bg,cs,da,de,ded,el,es,et,fi,fr,he,hi,hr,hu,id,it,ja,ko,nl,no,pl,pt,ro,ru,sk,sv,th,tr,uk,vi,zh}/README_*.md` -- exact 32 paths authenticated in READY
  - README.ee.md from `.saipen/saitranslate/kitchen/et/README_ET.md`
  - README.ja.md from `.saipen/saitranslate/kitchen/ja/README_JA.md`
  - README.ded.md from `.saipen/saitranslate/kitchen/ded/README_DED.md`
- **verified:** PASS -- strict READY `sha256:dbcddc71fee86ac29e705b1e7be25d2d5f8b808006cdded1c449b551faa2367a` published at producer epoch 5 with 44 exact read dependencies and 35 authenticated payload entries (32 locale README_*.md + 3 root mirrors); source identity capture + bounded revalidation PASS (HEAD e045ad07, tree git-delta-v1:da948fff, role_revision sha256:f241e6b8...); 32/32 normalized digest `2a33e364...`; 32/32 version badge v7.226.0; heading/fence/table parity 32/32; no leaked placeholders; charter role revision matches; no integration, commit, tag, push, or remote write performed.
- **instructions:**
  1. Recompute and require the exact source triple above (HEAD e045ad07 / tree git-delta-v1:da948fff / role_revision sha256:f241e6b8...).
  2. Run `python -B tools/validate.py --gate collect:saitranslate`; refuse on any producer or payload mismatch.
  3. Integrate only READY package `sha256:dbcddc71fee86ac29e705b1e7be25d2d5f8b808006cdded1c449b551faa2367a` through the canonical Core writer.
  4. Re-run the independent 32-file quality audit, mirror byte equality, Core gate, and REVIEW before SHIP.

## SAIT-015: FORCE-FRESH re-bind + re-package to 6cbed249 (v7.226.0)

- **status:** stale
- **superseded_by:** SAIT-017
- **summary:** SAIT-014 went stale by freshness triple (HEAD e045ad07 -> 6cbed249 from the ruff-hygiene commit PY-11). FORCE-FRESH re-ran the producer pipeline: recomputed source identity (HEAD 6cbed249, tree git-delta-v1:55f5361), rebuilt the package, and re-published a fresh strict READY. README.md and all 32 locale sources are content-unchanged by the ruff commit (tools/*.py only), so package identity is preserved; only the source binding moved.
- **critical:** false
- **producer:** saitranslate
- **source_head:** 6cbed2492abee837962583c14566d60487337511
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:**
  - README.md: 32/32 locale candidates (ar, bg, cs, da, de, ded, el, es, et, fi, fr, he, hi, hr, hu, id, it, ja, ko, nl, no, pl, pt, ro, ru, sk, sv, th, tr, uk, vi, zh), all bound to normalized source digest 2a33e364c3c12e8b1b9b2caf41b05db3ee27f17161336579ae85ee59da34fe56
  - Root README mirrors: README.ee.md, README.ja.md, README.ded.md candidates from ET/JA/DED kitchen outputs
  - In-app UI: none -- no tracked i18n/locale bundle or app-view surface exists
- **payload:**
  - .saipen/saitranslate/kitchen/{ar,bg,cs,da,de,ded,el,es,et,fi,fr,he,hi,hr,hu,id,it,ja,ko,nl,no,pl,pt,ro,ru,sk,sv,th,tr,uk,vi,zh}/README_*.md -- exact 32 paths
  - README.ee.md from .saipen/saitranslate/kitchen/et/README_ET.md
  - README.ja.md from .saipen/saitranslate/kitchen/ja/README_JA.md
  - README.ded.md from .saipen/saitranslate/kitchen/ded/README_DED.md
- **verified:** PASS -- strict READY sha256:dbcddc71fee86ac29e705b1e7be25d2d5f8b808006cdded1c449b551faa2367a at producer epoch 14 with 44 read dependencies and 35 authenticated payload entries; source identity 6cbed249 / git-delta-v1:55f5361 / role_revision sha256:f241e6b8...; content-identical to SAIT-014 (README.md unchanged); no integration, commit, tag, push, or remote write performed.
- **instructions:**
  1. Recompute and require the exact source triple above.
  2. Run python -B tools/validate.py --gate collect:saitranslate; refuse on any mismatch.
  3. Integrate only READY package sha256:dbcddc71fee86ac29e705b1e7be25d2d5f8b808006cdded1c449b551faa2367a through the canonical Core writer.
  4. Re-run the independent 32-file quality audit, mirror byte equality, Core gate, and REVIEW before SHIP.

## SAIT-017: FORCE-FRESH re-bind + re-package to e75367f7 (v7.226.0)

- **status:** stale
- **superseded_by:** SAIT-018
- **summary:** FORCE-FRESH re-bind to e75367f7 after crew fix commits; content-identical (README.md unchanged), package identity dbcddc71fee86ac29e705b1e7be25d2d5f8b808006cdded1c449b551faa2367a preserved
- **critical:** false
- **producer:** saitranslate
- **source_head:** e75367f79c68c5386f73cd76a0fcb89cdc6223bb
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md payloads + 3 root mirrors = 35 payload entries; 44 read dependencies
- **payload:** []
- **verified:** PASS -- integrated CURRENT against e75367f7
- **instructions:** Core records the integrated saitranslate disposition.

## SAIT-018: FORCE-FRESH re-bind to 078f5cd6

- **status:** stale
- **superseded_by:** SAIT-019 -- HEAD 078f5cd6 -> b666b77f (v7.226.0 closure T-1150; SPEC.md +29 from audit-hardening, read_set moved)
- **summary:** FORCE-FRESH re-bind to 078f5cd6; content-identical (README.md unchanged), package identity dbcddc71fee86ac29e705b1e7be25d2d5f8b808006cdded1c449b551faa2367a preserved
- **critical:** false
- **producer:** saitranslate
- **source_head:** 078f5cd6d12e36d24677fc79b86f0457dd70f4ea
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md payloads + 3 root mirrors = 35 payload entries; 44 read dependencies
- **payload:** []
- **verified:** PASS -- integrated CURRENT against 078f5cd6
- **instructions:** Core records the integrated saitranslate disposition.

## SAIT-019: FORCE-FRESH re-bind to b666b77f (v7.226.0 closure)

- **status:** stale
- **superseded_by:** SAIT-020
- **summary:** FORCE-FRESH re-bind to b666b77f (v7.226.0 closure T-1150). README.md content-unchanged (normalized digest 2a33e364...), so all 32 locale translations remain valid; SPEC.md +29 from audit hardening changed the read_set, so package identity moved to sha256:51c1785b. Identical payload, fresh binding.
- **critical:** false
- **producer:** saitranslate
- **source_head:** b666b77ff3ad8e5066de4d3ec3ad3fc03c63f1c8
- **source_tree_fingerprint:** git-delta-v1:c7765ad85e0a01ffb4f4c2664da36402efacdbb55f240a6f090910f06a1be15c
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md payloads + 3 root mirrors = 35 payload entries; 44 read dependencies
- **payload:** []
- **verified:** PASS -- strict READY sha256:51c1785bf8f44a26060b7440b5413f183be4d071bb1ed89e327af70be4e9ffc6 at producer epoch 18; 44 read dependencies, 35 authenticated payload entries; source identity b666b77f / git-delta-v1:c7765ad8 / role_revision sha256:f241e6b8...; 32/32 normalized digest 2a33e364...; no integration, commit, tag, push, or remote write performed.
- **instructions:**
  1. Recompute and require the exact source triple above.
  2. Run python -B tools/validate.py --gate collect:saitranslate; refuse on any mismatch.
  3. Integrate only READY package sha256:51c1785bf8f44a26060b7440b5413f183be4d071bb1ed89e327af70be4e9ffc6 through the canonical Core writer.
  4. Re-run the independent 32-file quality audit, mirror byte equality, Core gate, and REVIEW before SHIP.

## SAIT-020: FORCE-FRESH re-bind to b666b77f (uncommitted working tree drift)

- **status:** stale
- **superseded_by:** SAIT-021
- **summary:** SAIT-019 went stale by freshness triple (fingerprint moved from git-delta-v1:c7765ad8 to git-delta-v1:e0834df2 due to uncommitted working tree changes in saipen/ docs and tools/). README.md, SPEC.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, guides/, and phases/translate.md are all unchanged -- 32 locale translations remain valid. FORCE-FRESH re-bound the same package to the current source identity.
- **critical:** false
- **producer:** saitranslate
- **source_head:** b666b77ff3ad8e5066de4d3ec3ad3fc03c63f1c8
- **source_tree_fingerprint:** git-delta-v1:e0834df25cbd22526918223e7027a6d5030a2161b28a80860c6f3d3af7f28738
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md payloads + 3 root mirrors = 35 payload entries; 44 read dependencies
- **payload:** []
- **verified:** PASS -- content-identical to SAIT-019; source surfaces (README/SPEC/CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/guides/translate.md) unchanged; only saipen/ docs and tools/ modified in working tree; package identity preserved
- **instructions:** Core records the integrated saitranslate disposition.

## SAIT-021: verified qwen3:14b FORCE-FRESH package

- **status:** stale
- **superseded_by:** SAIT-022
- **summary:** FORCE-FRESH regenerated all 32 locale README candidates with qwen3:14b and published a new strict package against the current source identity; independent hashing disproved E-4192's stale `d7c62e72` premise and confirmed the live normalized README digest remains `2a33e364`.
- **critical:** false
- **producer:** saitranslate
- **source_head:** b666b77ff3ad8e5066de4d3ec3ad3fc03c63f1c8
- **source_tree_fingerprint:** git-delta-v1:ffafd93a02dc3fecb0dea8e1c92dd53685d6813c5bb6c1d50160e71d7c0b12b6
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md candidates; 3 root mirrors; 44 exact read dependencies; no tracked in-app i18n surface exists
- **payload:**
  - `.saipen/saitranslate/kitchen/{ar,bg,cs,da,de,ded,el,es,et,fi,fr,he,hi,hr,hu,id,it,ja,ko,nl,no,pl,pt,ro,ru,sk,sv,th,tr,uk,vi,zh}/README_*.md` -- exact 32 paths authenticated in READY
  - README.ee.md from `.saipen/saitranslate/kitchen/et/README_ET.md`
  - README.ja.md from `.saipen/saitranslate/kitchen/ja/README_JA.md`
  - README.ded.md from `.saipen/saitranslate/kitchen/ded/README_DED.md`
- **verified:** PASS -- 32/32 structurally current; digest/model/heading/fence/table/trailing-whitespace checks clean; strict READY `sha256:44b2f4020915a66aaf9301cf4050a9c5c403b471b278f4460febc5c230e4469c` at epoch 19 with 35 authenticated payload entries and 44 read dependencies; `git diff --check` PASS
- **instructions:**
  1. Recompute and require the exact source triple above.
  2. Run `python -B tools/validate.py --gate collect:saitranslate`; refuse on any mismatch.
  3. Integrate only READY package `sha256:44b2f4020915a66aaf9301cf4050a9c5c403b471b278f4460febc5c230e4469c` through the canonical Core writer.
  4. Re-run the 32-file quality audit, mirror byte equality, Core gate, and REVIEW before SHIP.

## SAIT-022: reviewed qwen3:14b FORCE-FRESH package

- **status:** stale
- **superseded_by:** SAIT-023
- **summary:** Supersedes SAIT-021 after independent review found and repaired one malformed Turkish scenario-fixture link plus leaked English prose; all 32 locale candidates were re-audited and the strict package was republished.
- **critical:** false
- **producer:** saitranslate
- **source_head:** b666b77ff3ad8e5066de4d3ec3ad3fc03c63f1c8
- **source_tree_fingerprint:** git-delta-v1:ffafd93a02dc3fecb0dea8e1c92dd53685d6813c5bb6c1d50160e71d7c0b12b6
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md candidates; 3 root mirrors; 44 exact read dependencies; Turkish link/prose review fix included
- **payload:**
  - `.saipen/saitranslate/kitchen/{ar,bg,cs,da,de,ded,el,es,et,fi,fr,he,hi,hr,hu,id,it,ja,ko,nl,no,pl,pt,ro,ru,sk,sv,th,tr,uk,vi,zh}/README_*.md` -- exact 32 paths authenticated in READY
  - README.ee.md from `.saipen/saitranslate/kitchen/et/README_ET.md`
  - README.ja.md from `.saipen/saitranslate/kitchen/ja/README_JA.md`
  - README.ded.md from `.saipen/saitranslate/kitchen/ded/README_DED.md`
- **verified:** PASS -- 32/32 structurally current; Turkish empty-link and English-leak controls false; digest/model/heading/fence/table/trailing-whitespace checks clean; strict READY `sha256:2f94c904719a0635fdace2617baf8ce22b7774b48b5f4995bb42bf79dbecf7e2` at epoch 20 with 35 authenticated payload entries and 44 read dependencies; `git diff --check` PASS
- **instructions:**
  1. Recompute and require the exact source triple above.
  2. Run `python -B tools/validate.py --gate collect:saitranslate`; refuse on any mismatch.
  3. Integrate only READY package `sha256:2f94c904719a0635fdace2617baf8ce22b7774b48b5f4995bb42bf79dbecf7e2` through the canonical Core writer.
  4. Re-run the 32-file quality audit, mirror byte equality, Core gate, and REVIEW before SHIP.

## SAIT-023: v7.226.1 release-metadata rebind

- **status:** stale
- **summary:** Rebound the reviewed qwen3:14b translation payload after the v7.226.1 release metadata and all 32 locale badges were finalized; translation prose is unchanged from SAIT-022.
- **critical:** false
- **producer:** saitranslate
- **source_head:** b666b77ff3ad8e5066de4d3ec3ad3fc03c63f1c8
- **source_tree_fingerprint:** git-delta-v1:53d374c6c00ca7d3e9c9ef7d3ae90cb523f7740b0f41913c6b809fd982141b95
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:** 32/32 locale README_*.md payloads + 3 root mirrors; 44 exact read dependencies; v7.226.1 badges current
- **payload:** [.saipen/saitranslate/kitchen/{ar,bg,cs,da,de,ded,el,es,et,fi,fr,he,hi,hr,hu,id,it,ja,ko,nl,no,pl,pt,ro,ru,sk,sv,th,tr,uk,vi,zh}/README_*.md, README.ee.md, README.ded.md, README.ja.md]
- **verified:** PASS -- strict READY `sha256:99c5be50394acad757928a2c7fa8f49f21670f84d733abfe8a5b9067cfc30bc6` at epoch 21; 35 authenticated payloads; normalized source digest remains `2a33e364c3c12e8b1b9b2caf41b05db3ee27f17161336579ae85ee59da34fe56`
- **instructions:** Run `python -B tools/validate.py --gate collect:saitranslate`; integrate only the named READY package through Core.
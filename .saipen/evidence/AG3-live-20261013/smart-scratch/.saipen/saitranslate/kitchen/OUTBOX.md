# OUTBOX

## TRANSLATE-007: fresh EE @c826eb7 (post-v2.6.9 full mirror)
- **status:** ready
- **summary:** FORCE-FRESH regeneration bound to the shipped v2.6.9 tree (c826eb7). README.{ru,et,ded}.md mirror the current English README.md's 12-bullet Safety section (incl. all v2.6.9 wording: physically-read-only dry-run, fail-closed process check, --all safe defaults, Releases contract); previously ru/et carried 7-10 bullets (missing No-hardcoded, Owner coverage, Backup files, GUI-worker-Tk thread invariant) and ded carried 11 (missing Tk-thread invariant). strings/{ru,et,ded}.json are 27/27 key-parity with DEFAULT_STRINGS — zero drift. Payload bytes are integration-ready; main-project files were NOT touched by this prepare.
- **critical:** false
- **producer:** saitranslate
- **source_head:** c826eb7177f29a4714b69637390081e038e052c0
- **source_tree_fingerprint:** git-delta-v1:1d502b0f14532150916f850e4feffff9cd924b9764d8956b3da2f14c8dd99d4e
- **role_revision:** sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5
- **coverage:**
  - Documentation: README.ru.md, README.et.md, README.ded.md (12-bullet Safety section in exact bullet order matching README.md; --all safe-defaults wording; Releases contract; numbered and compound never-delete variants; GUI worker thread invariant)
  - UI Strings: strings/ru.json, strings/et.json, strings/ded.json (27 keys == DEFAULT_STRINGS, no dead/extra)
  - Source-digest footer on every payload README: `README.md sha256:0e75f3cd673d01f8f6a5080a4d789367a1122c9dce45ec707a1b9e7b73c14fed`
- **payload:**
  - README.ru.md (170 lines, payload sha256 ce9da8890442f30e069500d014e9269491ec97ad825870540ea87b5433df7452)
  - README.et.md (172 lines, payload sha256 83619219b529108131f10c9be62bf51eb70804df964dc971bffc2e0bcbe67f9e)
  - README.ded.md (155 lines, payload sha256 8d05b93e1b8aa1be0840460fab69de47a29b5a5131774d3e49409bdb05eda6fc)
  - strings/ru.json (27 keys)
  - strings/et.json (27 keys)
  - strings/ded.json (27 keys)
- **verified:**
  - source_head matches HEAD (`c826eb7177f29a4714b69637390081e038e052c0`)
  - source_tree_fingerprint computed via tools/freshness.py.compute_source_identity
  - role_revision matches saitranslate charter (sha256:f241e6b83c39e9b46bfa586638efb0374bbb39889646f723b9189bbb4912c0c5)
  - ru/et/ded safety-bullet count == 12 == README.md safety-bullet count
  - bullet order mirrors README.md 1:1
  - ru/et/ded key-sets == DEFAULT_STRINGS (27/27, zero missing, zero extra)
  - payload README digest footers match live README.md sha256
  - payload files UTF-8 no BOM, parseable as JSON / markdown
  - main project tree was NOT touched (payload lives in .saipen/saitranslate/payload/)
- **instructions:**
  - On collect (`eee`): replace `README.ru.md`, `README.et.md`, `README.ded.md` at project root and `strings/ru.json`, `strings/et.json`, `strings/ded.json` under project root `strings/` with the payload copies; the current main-tree README.{ru,et,ded}.md carry stale v2.6.8 wording (7-10 bullets, missing v2.6.9 invariants) and `strings/` is empty (no locale files at all). After replacement run `python -m pytest -q` (must stay green; the i18n parity test asserts `set(DEFAULT_STRINGS) - refs == ∅` and `set(localex) - set(DEFAULT_STRINGS) == ∅` for every locale) and `ruff check`. Commit + tag via the normal Core release chain. Do NOT edit payload to force `status: ready` over incomplete coverage -- the 12/12 bullet parity + 27/27 string parity are the gate, forging it is indistinguishable from the work being done.
- **details:**
  The previous `TRANSLATE-006` package was bound to e4e2b85 (v2.6.8) and is stale at this HEAD; it cannot be collected. The drift that drove this regeneration is the post-v2.6.9 hardening (CORE-001..014 + W2-001..008 + PERF-001..008), which rewrote the Safety contract in the English README (12 bullets vs 10 in the v2.6.8 README) and was never propagated to ru/et/ded. Three audit-imounds (T-144 `.. canonicalized+confined`, T-135 blacklist boundary, T-143 Releases contract) are also carried in the new payload. The ded README now also carries the GUI worker-thread invariant that the previous payload missed. Strings files (27 keys each, all locales) had no drift and were verified against DEFAULT_STRINGS byte for byte. Source-tree fingerprint includes 3 modified tracked files (`_SMART_VAC_CLEANER.py`, `test_cleaner.py`, `test_package_install.py`) and a large untracked junk set; `.saipen/` is excluded from the fingerprint per PROTOCOL.md §6.
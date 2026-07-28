# Board

## DOING

## TODO

## DONE
- [x] WIKI-001 saitranslate locale freshness audit -- baseline v7.55, current v7.64, drift confirmed minimal
- [x] WIKI-002 maintenance mechanism delivered: `tools/validate.py` translation badge drift check + `githooks/pre-commit` hook templates (bash + ps1) | verify: python tools/validate.py now FAILs on stale translation badges -- confirms detection works (32/32 locales stale, all detected)
- [x] WIKI-003 wiki inject — saipen wiki live on GitHub: Home + Getting Started + sidebar + footer
- [x] WIKI-004 wiki content expansion — Phases, Scenarios, Tutorials, Use-Cases, SubSaipen pages added (880 lines)

- [x] WIKI-005 wiki drift audit -- v7.97.0 vs v7.64-era: 6 drift categories across 8 wiki pages | verify: OUTBOX written with full findings

- [x] WIKI-006 maintenance scan + verify -- v7.97.0 deep audit: 1 validate FAIL (saitranslate), 8 wiki pages stale, 4 positive findings | verify: OUTBOX WIKI-006 written with full per-page delta

- [x] W-014 OUTBOX collection + cross-sub fixes -- collected WIKI-005/WIKI-006 into main BOARD (T-260, T-261); fixed saitranslate validate FAIL (phase TRANSLATE→DONE) | verify: tools/validate.py PASS, saitranslate BOARD now tracks SAIT-003

- [x] W-015 wiki refresh + validate fixes -- regenerated 8 wiki pages from v7.97.0 sources (pushed 0e99a90); closed T-260/T-261; fixed saitranslate STATE | verify: tools/validate.py PASS, wiki live at github.com/vacterro/saipen/wiki

- [x] W-016 v7.98.0 drift scan — project working tree at v7.98.0 (uncommitted), wiki at v7.97.0. 5 wiki pages need light refresh: Home (version badge), Scenarios (row 67), SubSaipen (guards), Footer (version). OUTBOX WIKI-007 written | verify: validate.py PASS, OUTBOX well-formed

- [x] W-017 wiki light refresh — Home/Footer version v7.97.0→v7.98.0, Scenarios 66→67 (row 67), SubSaipen validation guards section added. Pushed to github.com/vacterro/saipen.wiki (340d4be) | verify: wiki live at github.com/vacterro/saipen/wiki, all 4 pages render

## BLOCKED
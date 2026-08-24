# Board

## DOING

## TODO

## DONE
# LEGACY HISTORY (read-only, pre-W- era): tickets below are committed history under older prefixes and can never become actionable
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
- [x] W-018 CI trigger drift fix — Home.md CI section said PR-only, updated to push:+concurrency truth. Pushed (4dd270f) | verify: Home.md shows real trigger, CI ran green on push
- [x] W-019 v7.103.0 full wiki refresh — drift scan (WIKI-008), then regenerated all 8 wiki pages: Home (badge, features, CI), Scenarios (68→99 rows), SubSaipen (liveness, TEMPLATE), Getting-Started (cygpath-w, audit_floor), Phases (gate-stuck-red, release guard), Tutorials (validator lint, push-claim), Use-Cases (citation, boundary check), _Footer. Pushed ed51225 | verify: wiki live at github.com/vacterro/saipen/wiki
- [x] HUNT-002 clean sweep @3efc567 — 6-category HUNT after v7.103.0 refresh: validate.py PASS, wiki in sync, no stale refs, no orphan kitchen files. Wiki fully compliant. | verify: all 8 wiki pages render at v7.103.0, validate.py PASS
- [x] WIKI-009 verify drift v7.103.0..v7.121.0 — 18 releases, 8 wiki pages. All 8 pages inspected live on GitHub. 6 of 8 stale. OUTBOX WIKI-009 written with per-page findings and recommendations. | verify: OUTBOX written with comprehensive per-page delta, validate.py PASS, 8 wiki pages confirmed at v7.103.0 on remote
- [x] W-022 wiki refresh v7.103.0→v7.121.0 — 6 pages updated and pushed to github.com/vacterro/saipen.wiki (b466666). Home (badge+19 bullets), Scenarios (99→140 rows), _Footer (version), Phases (6 phase-level checks), Getting-Started (hook+5 audit tools), SubSaipen (read-only dual meaning). Tutorials/Use-Cases/_Sidebar stable — unchanged. | verify: all 6 updated pages confirmed live on GitHub; Home shows v7.121.0, Scenarios shows 140 rows, Footer shows v7.121.0
- [x] W-023 wiki refresh v7.121.0→v7.133.0 — deep analyze, 7 pages updated, pushed e2d0ad8. Home (badge + 15 bullets v7.122-v7.133), Phases (reuse ladder, retry-delta, SHIP repair loop, exact-ref publish, 5 new checks), Scenarios (140→157 rows), Getting-Started (installs complete, audit tools +run_scenarios, project root), SubSaipen (status + role-adopt/sync), Tutorials (+12), Use-Cases (+13,+14), _Footer. | verify: origin/master = e2d0ad8; Home/Scenarios/_Footer show v7.133.0; Scenarios 157 rows; no v7.121.0 badge refs remain; tools/validate.py PASS
- [x] W-024 verify v7.133.0 sync — project HEAD 8f685d6 unchanged; wiki origin/master e2d0ad8, local in sync; CONFORMANCE 157 rows == Scenarios 157 rows; badges v7.133.0; ship.md/BOOT.md claims spot-checked against wiki text; validate.py PASS. Uncommitted T-365 work unshipped, not wiki-relevant. 0 drift. | verify: PASS — all 8 pages match v7.133.0 sources; 0 stale refs; validator PASS

- [x] W-028 prepare v7.157.0-era → v7.170.0 -- 6 pages refreshed (Scenarios 182→195 rows, T-400 wiki half closed), OUTBOX ready | verify: OUTBOX W-028 well-formed (status ready, all fields), Scenarios 195 rows mirror CONFORMANCE 1-195, badges v7.170.0
- [x] W-029 prepare v7.170.0 → v7.173.0 -- 6 pages refreshed (Scenarios 195→201 rows, 4 new feature bullets, 4 phase checks, audit 79→91), OUTBOX W-029 ready | verify: OUTBOX W-029 well-formed (status ready, all fields), Scenarios 201 rows mirror CONFORMANCE 1-201, badges v7.173.0, validate.py PASS
- [x] W-030 prepare v7.173.0 → v7.176.0 -- 6 pages refreshed (Scenarios 201→216 rows, 6 new feature bullets, 12 phase checks, audit 91→104), OUTBOX W-030 ready | verify: OUTBOX W-030 well-formed (status ready, all fields), Scenarios 216 rows mirror CONFORMANCE 1-216, badges v7.176.0, no stale era badges left
- [x] W-031 prepare v7.176.0 → v7.219.0 -- full FORCE-FRESH regeneration (Scenarios rebuilt to 254 rows by ID, Home badge/table/shortcuts to v7.219.0 truth, Phases range + 13 checks, Getting-Started audit 104→231 + gen-7 hook, SubSaipen charters/role-rev/saiui, _Footer v7.219.0), OUTBOX W-031 ready | verify: OUTBOX W-031 well-formed (status ready, producer/source_head/source_tree_fingerprint/role_revision/coverage/payload/verified/instructions all present), Scenarios 254 rows mirror CONFORMANCE 1-254 by ID, badges v7.219.0, no stale v7.15x-18x era badges, freshness triple bound
- [x] W-032 prepare v7.219.0 → v7.226.0 -- Scenarios 254→256, badges/current phase notes refreshed, OUTBOX W-032 prepared at 00aa12db and later superseded by W-033 | verify: 256 IDs + mirror digest matched at production; package now explicitly stale
- [x] W-033 FORCE-FRESH current v7.226.0 wiki -- all 9 pages reverified; producer parallelism/audit closure documented; stale RFC, shortcut, collect, and role-status prose corrected; OUTBOX + strict READY package current | verify: validator PASS; 256 unique contiguous IDs + sha256:9babcb02e659febc; freshness triple revalidated; 8-page payload diff-check clean
- [x] W-034 FORCE-FRESH re-bind to e045ad07 -- W-033 went stale without content drift (HEAD 3a343e8d -> e045ad07, tree 4ec002cc -> a9b068ed from CORE-002..007 + W2-004..008; producer.py/journal.py/operations.py only, no CONFORMANCE/saipen docs). All 8 pages re-read, write_set/read_set recomputed (42 deps, none absent), package rebuilt + re-published at new identity. Zero page-content delta vs W-033. OUTBOX W-034 ready; strict READY sha256:4481cb57... published at epoch 1. Not integrated or pushed.
- [x] W-039 FORCE-FRESH command-routing and safety-valve truth -- 9 pages re-read; 5 corrected; Scenarios 1-256 mirror b5e98946da9926b6; strict READY sha256:7ee12026 at epoch 1 | verify: 9/9 inventory; stale prose scan clean; diff whitespace clean; source triple current
- [x] W-040 v7.226.1 final wiki rebind -- current-version badge/footer/range and producer rows refreshed; 9-page strict READY sha256:86bd88bf at epoch 3 | verify: collect:saiwiki PASS; 256 contiguous scenario IDs; source triple current
## BLOCKED

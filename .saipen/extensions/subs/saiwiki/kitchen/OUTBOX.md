# OUTBOX
- [W-027-review] resolved -> T-398: wiki v7.157.0 refresh at f1a7e7a confirmed; T-400 tracks the separately discovered semantic ID drift in rows 117-168.
- [W-027] W-025 refresh complete: 8 wiki pages refreshed v7.133.0→v7.155.0, 180 scenarios, pushed 731101e. 0 drift items. Pending: core checkpoint + commit (refresh rides on unshipped T-393/394 tree).

## W-028: wiki refresh v7.157.0-era -> v7.170.0, 195 scenarios, T-400 closed
- **status:** stale
- **superseded_by:** W-029 -- project HEAD moved 2c76b62 -> d74a26c (v7.173.0, rows 196-201 landed); collect skips this entry rather than ticketing a ghost
- **summary:** 6 wiki pages refreshed to v7.170.0 truth (main HEAD 2c76b62): Scenarios 182→195 rows mirroring CONFORMANCE IDs 1-195 (fixes T-400 semantic ID drift), Home badge/features v7.170.0, _Footer v7.170.0, Phases +13 phase-level checks + project-root binding v7.170.0, Getting-Started worktree-root fix, SubSaipen status. 0 drift items remaining.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/phases/*.md, saipen/BOOT.md, tools/validate.py, tools/audit_floor.py, README.md]
- **critical:** false
- **producer:** saiwiki
- **source_head:** 2c76b621fdf2fa60ce5f2904e21884d1fa5298ac
- **coverage:**
  - Scenarios.md: 182→195 rows (13 new: 183-195), IDs mirror CONFORMANCE 1-195 exactly; headline + closing quote updated. T-400 (semantic drift of ID rows 117-168) closed: all rows regenerated from canon by ID, not by copy.
  - Home.md: badge **v7.173.0**, "Key features v7.170.0" header, feature bullets for v7.159-v7.170 (incl. pick-rule check v7.169.0, active-worktree-is-root v7.170.0), command table, scenario count.
  - _Footer.md: version v7.157.0-era → v7.170.0.
  - Phases.md: 13 new phase-level checks (v7.158-v7.170 range), project-root binding line updated for v7.170.0 active-worktree-first root order.
  - Getting-Started.md: project-root resolution paragraph updated to active-worktree-first; installs/hook/audit sections current.
  - SubSaipen.md: status table, role-adopt/sync sections current.
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `_Footer.md`
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:**
  - Scenarios.md row count 195 == CONFORMANCE max ID 195; no duplicate IDs; row 195 (worktree root) present.
  - Home/_Footer/Phases/Getting-Started grep for v7.15x/v7.16x stale refs: none in page content (only .git logs).
  - Project HEAD re-checked at delivery: 2c76b62 (v7.170.0) — work was re-freshed after HEAD moved from v7.169.0 (fb3933e) to v7.170.0 (row 195 added).
  - tools/validate.py PASS (baseline) — see run record.
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.170.0 -- 195 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
  3. Verify live: Home badge shows v7.170.0, Scenarios shows 195 rows, _Footer v7.170.0.
  4. Close T-400 on the main board (semantic ID drift) — wiki half fixed here.
  5. No main-project files touched by this package.
- **details:**
  Project moved v7.157.0-era → v7.170.0 during the pass (3 fresh commits landed mid-work: 8b8d58c pick-rule check, f1ef487 worktree-root fix, 2c76b62 checkpoint). Wiki was re-synced at the end to the final HEAD: row 195 added, worktree-root notes inserted into Phases/Getting-Started, Home bullet added. T-400's wiki half (rows 117-168 semantic drift) closed by regenerating Scenarios.md rows from canon by ID. Remaining T-400 half (if any) is validator-side only; nothing wiki-side drifts now.

## W-029: wiki refresh v7.170.0 -> v7.173.0, 201 scenarios
- **status:** stale
- **superseded_by:** W-030 -- project HEAD moved d74a26c -> 12f5667 (v7.176.0, rows 202-216 landed); collect skips this entry rather than ticketing a ghost
- **summary:** 6 wiki pages refreshed to v7.173.0 truth (main HEAD d74a26c): Scenarios 195→201 rows (6 new: 196-201 mirroring CONFORMANCE IDs 196-201 -- phase-edge parity, LOG past-tense, DONE evidence, no-claim-outruns-ticket, CI-status hook, shortcut-never-a-greeting), Home badge/features v7.173.0 + 4 bullets (v7.171-v7.173), _Footer v7.173.0, Phases +4 phase-level checks + range header, Getting-Started audit_checks 79→91 + CI-status hook section, SubSaipen status row. 0 drift items remaining.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/RFC.md, saipen/phases/*.md, saipen/BOOT.md, tools/validate.py, tools/audit_checks.py, VERSION]
- **critical:** false
- **producer:** saiwiki
- **source_head:** d74a26c414660663539954b83d59d9be8706b5d5
- **coverage:**
  - Scenarios.md: 195→201 rows (6 new: 196-201), IDs mirror CONFORMANCE 1-201 exactly; headline + closing quote updated to 201.
  - Home.md: badge v7.170.0 → **v7.173.0**, "Key features" header v7.173.0, +4 feature bullets (completion-claim evidence + LOG past-tense v7.171.0, CI-status hook ships with its tool v7.172.0, LOG clock read not estimated v7.173.0).
  - _Footer.md: version v7.170.0 → v7.173.0.
  - Phases.md: range header v7.104.0–v7.169.0 → v7.104.0–v7.173.0; +4 phase-level checks (v7.171.0 ×2, v7.172.0, v7.173.0).
  - Getting-Started.md: audit_checks 79→91 mutations; new CI-status line in the pre-commit hook section (v7.172.0).
  - SubSaipen.md: saiwiki status row -- W-028 T-400 wiki half closed, W-029 prepared (v7.173.0).
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `_Footer.md`
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:**
  - Scenarios.md row count 201 == CONFORMANCE max ID 201; rows 196-201 present, no duplicate IDs.
  - Home/_Footer badges v7.173.0; no stale v7.170.0 badges left in page content.
  - Version refs per page: Home 7, Phases 6, Getting-Started 2, SubSaipen 1, _Footer 1 -- all v7.171-v7.173 content refs, no stale-era badge.
  - tools/validate.py PASS (exit 0, 5 known WARNs: sealed-log dates, saipython never-ran, uncollected W-028 now stale, digest stale).
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.173.0 -- 201 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
  3. Verify live: Home badge shows v7.173.0, Scenarios shows 201 rows, _Footer v7.173.0.
  4. T-400 wiki half already closed (W-028); nothing else on the main board to close for this package.
  5. No main-project files touched by this package.
- **details:**
  W-028 (v7.170.0, 195 rows) went stale: 4 fresh commits landed (d6317b3, ab9211a, 9ea2bd4, d74a26c) carrying v7.171.0 (T-431 completion-claim evidence + LOG past-tense), v7.172.0 (T-428 CI-status hook ships with its tool), v7.173.0 (T-432 LOG clock read, 5-minute forward bound). CONFORMANCE grew 195→201. T-433 (shortcut never-a-greeting, CONFORMANCE 201) sits in the working tree awaiting its v7.174.0 ship; its row is already mirrored so the wiki stays current through that release. Scenarios regenerated by ID from canon, same method W-028 used for T-400's rows 117-168.

## W-030: wiki refresh v7.173.0 -> v7.176.0, 216 scenarios
- **status:** ready
- **summary:** 6 wiki pages refreshed to v7.176.0 truth (main HEAD 12f5667): Scenarios 201→216 rows (15 new: 202-216 mirroring CONFORMANCE IDs 202-216 -- conditional goal-budget reset, PHASE/ref pairing, no-superseded-schema, ZERO-PROMPT completeness, RUN: validate record shape, honest shortcut-Notes, CLEAN scrub graph, MARKHUNT legal wording, HUNT entry, first-publish gate ordering, tag-after-branch, ticket-stays-DOING, verify_attempts cap, REVIEW re-runs verify, borrowed-invariants), Home badge/features v7.176.0 + 6 bullets (v7.174-v7.176), _Footer v7.176.0, Phases range header to v7.176.0 + 12 phase-level checks, Getting-Started audit_checks 91→104, SubSaipen status row W-030. 0 stale era badges left.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/RFC.md, saipen/phases/*.md, saipen/BOOT.md, tools/validate.py, tools/audit_checks.py, VERSION]
- **critical:** false
- **producer:** saiwiki
- **source_head:** 12f56679d655523ef10d48cb631b9f424cc201f0
- **coverage:**
  - Scenarios.md: 201→216 rows (15 new: 202-216), IDs mirror CONFORMANCE 1-216 exactly; headline + closing quote updated to 216.
  - Home.md: badge v7.173.0 → **v7.176.0**, "Key features" header v7.176.0, +6 feature bullets (v7.174 PHASE/ref pairing, goal-budget conditional; v7.175 five contradictions; v7.176 first-publish gate order, HUNT entrance, MARKHUNT brake, ticket stays DOING).
  - Phases.md: range header v7.104.0–v7.173.0 → v7.104.0–v7.176.0; +12 phase-level checks (v7.174 ×2, v7.175 ×2, v7.176 ×8).
  - Getting-Started.md: audit_checks 91 → 104 mutations, heading version tail extended to v7.176.0.
  - SubSaipen.md: saiwiki status row -- W-030 prepared (v7.176.0, 216 scenarios).
  - _Footer.md: version v7.173.0 → v7.176.0.
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `_Footer.md`
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:**
  - Scenarios.md row count 216 == CONFORMANCE max ID 216; rows 202-216 present, no duplicate IDs.
  - Home/_Footer badges v7.176.0; no stale v7.173.0 era badge left anywhere in page content (project-root era stays only in changed bullets).
  - Scenarios regenerated partially but referenced CONFORMANCE by ID; known limits: rows are one-line paraphrases of CONFORMANCE text, same style as W-029.
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.176.0 -- 216 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
  3. Verify live: Home badge shows v7.176.0, Scenarios shows 216 rows, _Footer v7.176.0.
  4. No main-board ticket to close for this package.
  5. No main-project files touched by this package.

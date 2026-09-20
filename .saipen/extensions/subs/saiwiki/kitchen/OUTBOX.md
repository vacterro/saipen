# OUTBOX

## W-047: FORCE-FRESH current-tree truth -- entry command, binding, command ownership, record cap, retirement
- **status:** stale
- **superseded_by:** W-048 -- the source triple moved after 16 commits landed (HEAD 5d79ae78 -> a1e9c09f, tree git-delta-v1:465a5e58 -> git-delta-v1:4c6fd9b3); FORCE-FRESH re-bound the identical 9-page payload with zero page-content delta (refresh script no-op); collect skips this entry rather than ticketing a ghost
- **summary:** All 9 maintained wiki pages re-read against the current source triple (HEAD 5d79ae78, tree git-delta-v1:465a5e58). Five pages corrected, four verified byte-identical: Home's command table is rebuilt to the current public surface and gains the current-tree truths (one entry command, cold route + host-search-fault rule, seat vs host session, the 1200-character live BOARD record cap, retirement as a third terminal verdict, a measured inventory line); Getting-Started gains a "Start a new task" section naming START's four answers plus the current binding order; Tutorials points at the command-semantics owner and gains a START tutorial; Phases puts retirement beside DONE/BLOCKED and gains four phase-level checks; SubSaipen's producer rows name W-047 and SAIT-030. Scenarios stays a 257-row canonical mirror at digest sha256:43ab86d596572a90.
- **main_project_refs:** [VERSION, CHANGELOG.md, README.md, saipen/BOOT.md, saipen/COMMANDS.md, saipen/CONFORMANCE.md, saipen/CORE.md, saipen/OPS.md, saipen/REGISTRY.json, saipen/RUNTIME.md, saipen/SOURCES.md, saipen/STYLE.md, saipen/phases/*.md, extensions/subs/*.md, tools/freshness.py, tools/validate.py, tools/saipen_engine/*.py]
- **critical:** false
- **severity:** P2
- **producer:** saiwiki
- **source_head:** 5d79ae78456f63c5f73fb1c2ad71810e2d4eadd6
- **source_tree_fingerprint:** git-delta-v1:465a5e5880272f9a8e3010b38fa9963a06ce03171d71e3c77c239dbfe8f575e7
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 9/9 maintained pages re-read; 5 corrected (Home, Getting-Started, Tutorials, Phases, SubSaipen); 4 verified byte-identical (Scenarios, Use-Cases, _Footer, _Sidebar); 257 scenario IDs unique and contiguous by canonical ID
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Getting-Started.md, Phases.md, Scenarios.md, SubSaipen.md, Tutorials.md, Use-Cases.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- strict READY sha256:647ed9d3394ac8954a1acd78904a92d0f43514cbcf93d26a5a15c1543fc2801b published at producer epoch 8 with 54 exact read dependencies (saipen/COMMANDS.md and saipen/REGISTRY.json added this pass, because the pages now mirror them) and 9 authenticated payload entries; Scenarios marker sha256:43ab86d596572a90 equals the canonical corpus digest for rows 1-257 under the validator's own payload rule; every page edit was applied by an asserted single-match replacement in kitchen/_refresh_pages.py and re-running it changes nothing; wiki `diff --check` clean; and `python -B tools/validate.py --gate collect:saiwiki` exits 0 with "Validation complete. Agent is conformant.", 0 problem(s), `PASS: producer gate: saiwiki has a ready package and every completeness, freshness and role check above ran hard against it`, and 0 `wiki-mirror*` warning (the remaining warnings are the pre-existing project-wide set and none names a saiwiki artifact); no integration, commit, tag, push, or remote write performed.
- **instructions:** Run `python -B tools/validate.py --gate collect:saiwiki`; integrate only the 9 declared payload pages through Core's named saiwiki collect path; publish the wiki only through an authorized SHIP path; then verify Home shows the START-first entry line and the COMMANDS.md shortcut pointer, Getting-Started shows "Start a new task", Scenarios shows 257 rows and _Footer v8.0.1 live.
- **details:** Three real drifts were found and fixed, all of them user-visible and all pre-existing (none was introduced after W-046). (1) Three pointers still sent readers to `CORE § 1.10` for the 19-key shortcut table (Home 2x, Tutorials 1x) although that section has named `COMMANDS.md` as the command-semantics owner and carries no table -- the routing rules have moved to COMMANDS.md and the machine vocabulary to REGISTRY.json. (2) Home's "27 commands, full surface" table predated `saipen start`, `saipen ticket retire`, `saipen cohort`, `saipen context orient`, `saipen brief`, `saipen search`, `saipen knowledge`, `saipen audit`, `saipen sub`, `saipen push`, `saipen user-request`, `saipen hush` and the explicit-actor `launch` envelope, so the entry command of the current kernel was absent from the page that introduces the surface. (3) The closing bullet claimed "Audit closure on the current v7.248.0 tree" -- it named a tree that had stopped being current long before W-046, and it published test and control counts that no run on today's bytes re-derived; it is replaced by a measured inventory line (139 `tools/test_*.py` modules declaring 2791 test methods, 229 declared full-sweep mutation controls) that claims no run it did not perform. The tree after 71455482 also moved BOOT.md (entry table, project-binding carrier, host-search-fault rule, actor-vs-seat rule), COMMANDS.md (the new canonical commands, skill-only-no-op rule) and CORE.md (1200-character live record cap, retirement as a third terminal verdict); those are now mirrored. No main-tree file was written by this pass.

## W-048: FORCE-FRESH re-bind to a1e9c09f, zero content delta vs W-047
- **status:** ready
- **summary:** W-047 re-bound to the current source triple (HEAD a1e9c09f, tree git-delta-v1:4c6fd9b3) with zero page-content change: 16 commits landed after W-047 published (T-1407/T-1406/T-1400 log-evidence preservation, distribution current-bytes truth, quoted-payload guard classification, receipt-body quarantine, improve seat retire, release fail-closed scopes, ingress shell-control transport), none touching any wiki-facing page (REGISTRY.json gained two machine facts, SOURCES.md the quarantine contract, IMPROVE.md the seat-retire verb, saitranslate.md its namespace charter -- all mirrored surfaces already covered by the declared 54-dep read set). All 9 kitchen pages re-verified; kitchen/_refresh_pages.py re-run is a no-op ("already fresh"); Scenarios stays a 257-row canonical mirror at digest sha256:43ab86d596572a90.
- **main_project_refs:** [VERSION, CHANGELOG.md, README.md, saipen/BOOT.md, saipen/COMMANDS.md, saipen/CONFORMANCE.md, saipen/CORE.md, saipen/OPS.md, saipen/REGISTRY.json, saipen/RUNTIME.md, saipen/SOURCES.md, saipen/STYLE.md, saipen/phases/*.md, extensions/subs/*.md, tools/freshness.py, tools/validate.py, tools/saipen_engine/*.py]
- **critical:** false
- **severity:** P2
- **producer:** saiwiki
- **source_head:** a1e9c09f1fa9b9a94ed297ada143a949015fe4e9
- **source_tree_fingerprint:** git-delta-v1:4c6fd9b3f13a1d7a0b203e00a759dae5eac1474eabb77cb3e39dad9da1953eb9
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 9/9 maintained pages re-read at the new binding; 0 corrected (W-047 content is still current truth); 257 scenario IDs unique and contiguous by canonical ID
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Getting-Started.md, Phases.md, Scenarios.md, SubSaipen.md, Tutorials.md, Use-Cases.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- strict READY sha256:aff306cebb5a7802ea1ba7be64422dc2fbc6997badc5797371f2dd00720f0a5e published at producer epoch 9 with 54 exact read dependencies and 9 authenticated payload entries; Scenarios marker sha256:43ab86d596572a90 unchanged; kitchen/_refresh_pages.py idempotent (no change; already fresh); source identity captured after the final read with bounded revalidation; charter role revision matches; no integration, commit, tag, push, or remote write performed.
- **instructions:** Recompute and require this exact freshness triple (head a1e9c09f / tree git-delta-v1:4c6fd9b3 / role_revision sha256:54a42...) before collection; any mismatch means run `qq` again. Run `python -B tools/validate.py --gate collect:saiwiki`; integrate only the 9 declared payload pages through Core's named saiwiki collect path; publish the wiki only through an authorized SHIP path; then verify Home shows the START-first entry line and the COMMANDS.md shortcut pointer, Getting-Started shows "Start a new task", Scenarios shows 257 rows and _Footer v8.0.1 live.
- **details:** Triple-only re-bind in the W-045/W-046 lineage: the payload content of W-047 is unchanged, only the freshness binding refreshed. If the in-flight T-1407 work or the active improve cycle lands further mutations before collection, the triple moves again and qq must rerun -- package is fresh at publish instant, guaranteed nothing more. Main tree and wiki remote untouched.

## W-046: FORCE-FRESH re-bind to c53b5d85 (v8.0.1 closure + ee/saitranslate packages), zero content drift
- **status:** stale
- **superseded_by:** W-047 -- the source triple moved (HEAD 71455482 -> 5d79ae78, tree c53b5d85 -> 465a5e58) and FORCE-FRESH found real user-visible drift in the entry, binding, command-ownership, record-cap and retirement truth; W-046 remains content-identical otherwise
- **summary:** W-045 re-bound again after the ee/saitranslate SAIT-030 publication moved the working-tree fingerprint (b6b8f5da -> c53b5d85); HEAD unchanged at 71455482. Zero page-content change: badges v8.0.1, Home shortcut row st/ss-retired, audit bullet current, Scenarios 1-257 mirror marker sha256:43ab86d596572a90 unchanged, _Footer v8.0.1.
- **main_project_refs:** [VERSION, README.md, CHANGELOG.md, tests/conformance_cases.jsonl, saipen/CORE.md, saipen/CONFORMANCE.md, extensions/subs/saiwiki.md, extensions/subs/saitranslate.md, tools/validate.py, tools/freshness.py, tools/saipen_engine/producer.py, tools/saipen_engine/corpus.py]
- **critical:** false
- **severity:** P2
- **producer:** saiwiki
- **source_head:** 7145548211d2ee3ca9babf5e8b251960ea8f0527
- **source_tree_fingerprint:** git-delta-v1:c53b5d85ed1b470590003e1d5c2b0f531fd55a6d730f3c20bcdf1b01b4d1025a
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 9/9 maintained pages; 257 scenario IDs unique/contiguous by canonical ID; badges v8.0.1; stop-key truth current
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Phases.md, Getting-Started.md, SubSaipen.md, Tutorials.md, Use-Cases.md, Scenarios.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- strict READY sha256:2da5a6d14740e288854b59e0da1d717acd92f3ede481e15cdb14154c6070f74f published at producer epoch 7 with 52 exact read dependencies and 9 authenticated payload entries; Scenarios marker sha256:43ab86d596572a90 equals the canonical corpus digest for rows 1-257; zero page-content delta vs W-044/W-045; no integration, commit, tag, push, or remote write performed
- **instructions:** Run `python -B tools/validate.py --gate collect:saiwiki`; integrate only the 9 declared payload pages through Core's named saiwiki collect path; publish the wiki only through an authorized SHIP path; then verify Home badge v8.0.1, Scenarios 257 rows, _Footer v8.0.1 live.
- **details:** Second triple-only rebind in this session: the SAIT-030 publication (its own READY staging) and saitranslate's mirror-OUTBOX sync moved the tree fingerprint after W-045 published. Package is fresh at publish instant; if the in-flight T-1304 audit execution or T-1303 lands mutations before collection, qq must rerun. Main tree and wiki remote untouched.

## W-045: FORCE-FRESH re-bind to 71455482 (v8.0.1), zero content drift
- **status:** stale
- **superseded_by:** W-046 -- ee/SAIT-030 publication moved the tree fingerprint after W-045 published; W-045 re-bound without content change
- **summary:** W-044 re-bound to the current source triple with zero page-content change. HEAD moved 35ca656e -> 71455482 (v8.0.0 ship -> v8.0.1 ship/closure) plus a live working-tree delta in tools/ and saipen/ (T-1303/T-1301/T-1302 debt/verify engine work staged for the next release); no CONFORMANCE row, wiki-facing doc or repo doc surface changed. All 9 kitchen pages re-verified: badges v8.0.1, Home shortcut row st/ss-retired, Home audit-release-integrity bullet, Scenarios 1-257 mirror marker sha256:43ab86d596572a90 unchanged (payload rule: id|setup lines joined by newline), _Footer v8.0.1, Phases range v7.104.0-v8.0.1.
- **main_project_refs:** [VERSION, README.md, CHANGELOG.md, tests/conformance_cases.jsonl, saipen/CORE.md, saipen/CONFORMANCE.md, extensions/subs/saiwiki.md, extensions/subs/saitranslate.md, tools/validate.py, tools/freshness.py, tools/saipen_engine/producer.py, tools/saipen_engine/corpus.py]
- **critical:** false
- **severity:** P2
- **producer:** saiwiki
- **source_head:** 7145548211d2ee3ca9babf5e8b251960ea8f0527
- **source_tree_fingerprint:** git-delta-v1:b6b8f5daca2a8373945b15c3f42e5f14a5d31f9d3962c49f084a68b2385798d0
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 9/9 maintained pages; 257 scenario IDs unique/contiguous by canonical ID; badges v8.0.1; stop-key truth current
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Phases.md, Getting-Started.md, SubSaipen.md, Tutorials.md, Use-Cases.md, Scenarios.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- strict READY sha256:01cab8d2feceed8638a4de9c7e352e260d694b38f18da157d232fbbeafa44b9b published at producer epoch 6 with 52 exact read dependencies and 9 authenticated payload entries; Scenarios marker sha256:43ab86d596572a90 equals the canonical corpus digest for rows 1-257 (payload rule: id|setup lines joined by newline); zero page-content delta vs W-044; no integration, commit, tag, push, or remote write performed
- **instructions:** Run `python -B tools/validate.py --gate collect:saiwiki`; integrate only the 9 declared payload pages through Core's named saiwiki collect path; publish the wiki only through an authorized SHIP path; then verify Home badge v8.0.1, Scenarios 257 rows, _Footer v8.0.1 live.
- **details:** W-044 (35ca656e/v8.0.1-ship) went stale on the freshness triple alone: v8.0.1 ship (380b30f6) + closure (71455482) landed, and the worktree carries the next release's in-flight engine delta (tools/saipen_engine/debt.py etc.), both of which move source_head/source_tree_fingerprint without touching any wiki-facing byte. W-044 marked stale; package re-published through kitchen/_publish_package.py (ProducerEpoch.claim epoch 6, StagingGeneration, atomic READY). Note: if the in-flight T-1304 audit execution or T-1303 lands mutations before collection, the triple moves again and qq must rerun -- package is fresh at publish instant, guaranteed nothing more. Main tree and wiki remote untouched.

## W-044: FORCE-FRESH wiki v8.0.1 -- scenarios rebuilt by ID, stop key, audit release truth
- **status:** stale
- **superseded_by:** W-045 -- FORCE-FRESH re-bind to 71455482/b6b8f5da after v8.0.1 closure; zero content drift
- **summary:** Rebuilt all 257 Scenarios.md rows by canonical ID from tests/conformance_cases.jsonl (246 titles had drifted into paraphrase; marker sha256:43ab86d596572a90 recomputed and verified against the corpus payload rule). Home badge/features v8.0.1 + 2 new bullets (v8.0.0 st-stop key T-1297/SRC-024; v8.0.1 audit release integrity + bounded receipt lookups T-1298/SRC-025). Home shortcut row now names `st` with `ss` retired. Tutorials shortcut table ss->st. _Footer v8.0.1. Phases range header v7.104.0-v8.0.1. SubSaipen saiwiki row W-044 / saitranslate row corrected to SAIT-028-stale truth.
- **main_project_refs:** [VERSION, README.md, CHANGELOG.md, tests/conformance_cases.jsonl, saipen/CORE.md, saipen/CONFORMANCE.md, extensions/subs/saiwiki.md, extensions/subs/saitranslate.md, tools/validate.py, tools/freshness.py, tools/saipen_engine/producer.py, tools/saipen_engine/corpus.py]
- **critical:** false
- **severity:** P2
- **producer:** saiwiki
- **source_head:** 35ca656e7a9bcee92f3fed6ecde58fee1c9795de
- **source_tree_fingerprint:** git-delta-v1:763699b617e97ff6b839c0dc013b56343865cc8dff5a0791866f72cde5759f43
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 9/9 maintained pages; 257 scenario IDs unique/contiguous by canonical ID; badges v8.0.1; stop-key truth current
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Phases.md, Getting-Started.md, SubSaipen.md, Tutorials.md, Use-Cases.md, Scenarios.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- strict READY sha256:e1bf2dc14cbae72a500d8dde9a6529ecafbe8c56d173f7b79541a0da2de786ba published at producer epoch 5 with 52 exact read dependencies and 9 authenticated payload entries; Scenarios marker sha256:43ab86d596572a90 equals the canonical corpus digest for rows 1-257 (payload rule: id|setup lines joined by newline); validator wiki-mirror checks clean; wiki diff --check clean; no integration, commit, tag, push, or remote write performed
- **instructions:** Run `python -B tools/validate.py --gate collect:saiwiki`; integrate only the 9 declared payload pages through Core's named saiwiki collect path; publish the wiki only through an authorized SHIP path; then verify Home badge v8.0.1, Scenarios 257 rows, _Footer v8.0.1 live.
- **details:** W-041 (c7ea5b1b/v7.231.9) went stale after many releases (v7.234.0-v8.0.1). During the gap the Scenarios page title paraphrases drifted from the canonical corpus (246/256 titles no longer matched; old marker 61c6c71a1d6bbc1f predated row 257). Rows regenerated BY ID with notes kept only where provably authored against the same invariant; 243 notes dropped as unverifiable, canonical titles verbatim. v8.0.0's ss->st rename (T-1297) and v8.0.1's release-integrity wave (T-1298) are reflected in Home/Tutorials. saitranslate row corrected: SAIT-028 is stale against the v8.0.1 tree, collect refuses it until a fresh ee run. Main tree and wiki remote untouched.

## W-041: FORCE-FRESH wiki v7.231.9 -- badges, feature bullets, phase range
- **status:** stale
- **superseded_by:** W-044 -- FORCE-FRESH re-bound and rebuilt rows to the v8.0.1 corpus
- **summary:** Rebound all 9 maintained wiki pages to current v7.231.9 source triple (HEAD c7ea5b1b, tree git-delta-v1:f6607050). Home badge/features v7.231.9 with 6 new bullets (v7.231.4-v7.231.9: bootstrap activation parity, shortcut payload routing, runtime manifest completeness, CCC ship control, repeated cc hardening, SRC-003 audit repair wave). _Footer v7.231.9. Phases range header v7.231.9. SubSaipen saiwiki/saitranslate status rows refreshed. Scenarios 256 IDs verified against CONFORMANCE; canonical mirror sha256:46f20ddd1cd655be current.
- **main_project_refs:** [VERSION, README.md, CHANGELOG.md, KNOWLEDGE/ADR-0001-v7-producer-parallelism.md, saipen/BOOT.md, saipen/CORE.md, saipen/STYLE.md, saipen/CONFORMANCE.md, saipen/CONVERGE.md, saipen/OPS.md, saipen/phases/*.md, extensions/subs/PROTOCOL.md, extensions/subs/crew.md, extensions/subs/sai*.md, tools/freshness.py, tools/validate.py, tools/saipen_engine/producer.py, tools/saipen_engine/intent.py, tools/saipen_engine/journal.py, tools/saipen_engine/crew.py, tools/saipen_engine/release.py, tools/saipen_engine/subs.py]
- **critical:** false
- **severity:** P2
- **producer:** saiwiki
- **source_head:** c7ea5b1bb5f8e953c07140cda4f636a382c08310
- **source_tree_fingerprint:** git-delta-v1:f66070504b62818234b56162a1daa4243b1ab7462c178b2cf251de8831e45862
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 9/9 maintained pages; 256 scenario IDs unique/contiguous; v7.231.9 badges
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Phases.md, Getting-Started.md, SubSaipen.md, Tutorials.md, Use-Cases.md, Scenarios.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- strict READY sha256:5f1eb7d6ffbeb28ecb99b20c5d473837527af6d5abeaf7b4bf9c76962ef3752c at epoch 5 with 42 exact read dependencies and 9 authenticated payload entries; canonical mirror sha256:46f20ddd1cd655be; 256 unique contiguous scenario IDs; badges v7.231.9; no integration, commit, tag, push, or remote write performed
- **instructions:** Run saipen conformance validation starting (tools/validate.py)...
- **details:** W-040 (b666b77f) went stale after 6 releases (v7.231.4-v7.231.9). Home badge/features updated with 6 new bullets. _Footer version updated. Phases range header updated. SubSaipen saiwiki/saitranslate status rows refreshed. Scenarios 256 IDs re-verified; canonical mirror digest unchanged. No page content drift beyond version metadata.

## W-028: wiki refresh v7.157.0-era -> v7.170.0, 195 scenarios, T-400 closed
- **legacy:** true
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
- **legacy:** true
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
- **legacy:** true
- **status:** stale
- **superseded_by:** W-031 -- project HEAD moved 12f5667 -> bf62b8f (v7.219.0, rows 217-254 landed); collect skips this entry rather than ticketing a ghost
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

## W-031: wiki refresh v7.176.0 -> v7.219.0, 254 scenarios
- **status:** stale
- **superseded_by:** W-032 -- project HEAD moved 7d2bd0e -> 00aa12db (v7.226.0, rows 255-256 landed); collect skips this entry rather than ticketing a ghost
- **summary:** 6 wiki pages refreshed to v7.219.0 truth (main HEAD 7d2bd0e): Scenarios 216→254 rows (38 new: 217-254 mirroring CONFORMANCE IDs 217-254 -- typed-command-outranks-next_action, ROUTE-derived Notes, WAIT one-sentence, Proposal-Mode halt, multi-file fixtures, HUNT recovery proof, PREPARE names producer, multi-command message, derived seat, MARKHUNT countable, no-git readable, closed root, no-publish permission, unmeetable-ticket BLOCKED, stale-translation signal, BLOCKED holds foreign work, defect-class section, wiki-mirror-by-ID, red controls that could not go red, future-stamp repair, circuit evidence, move-is-destructive, habit counter, CHANGELOG order, installed/repo validator agreement, session BLOCKED, intent-aware clean-HUNT, intent-aware valve resume, CLEAN owns mutations, machine-readable charters, role freshness, Golden Default, nonempty-OUTBOX, gate context, SHIP stages-before-gates, schema keyword FAIL, full-OID identity, RFC-not-a-destination), Home badge/features v7.219.0 + 18-command table + 15-key shortcuts (gg/hh/cc/ccc/ss/sss/dd/aa/qq/qqq/ee/eee/pp/tt/sc), _Footer v7.219.0, Phases range header to v7.219.0 + 13 phase-level checks, Getting-Started audit_checks 104→231 + gen-7 hook, SubSaipen status row W-031 + machine-readable charters + saiui. 0 stale era badges left.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/CORE.md, saipen/phases/*.md, saipen/BOOT.md, saipen/STYLE.md, tools/validate.py, tools/audit_checks.py, VERSION]
- **critical:** false
- **producer:** saiwiki
- **source_head:** 7d2bd0eed5676645c2352cbefecb2ff98dbee79f
- **source_tree_fingerprint:** git-delta-v1:d0daa244b97507286381e4a28e72611e8f2ad68e700fd7da6b81a253e368cdff
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:**
  - Scenarios.md: 216→254 rows (38 new: 217-254), IDs mirror CONFORMANCE 1-254 exactly; headline + closing quote updated to 254; junk partial rows removed.
  - Home.md: badge v7.158.0 → **v7.219.0**, "Key features" header v7.219.0, command table 14→18 (crew, test, userperson, improve added), shortcuts 13→15 keys (gg new-goal, cc continue/converge, ccc continue-and-ship, dd plan, aa markhunt, pp saipython, tt test, sc crew), +20 feature bullets (v7.159-v7.219).
  - Phases.md: range header v7.104.0–v7.157.0 → v7.104.0–v7.219.0; +13 phase-level checks (OBEY, WAIT one-sentence, PHASE/ref pairing, ticket-stays-DOING, verify_attempts, REVIEW re-runs verify, first-publish gate, tag-after-branch, hunt-entry, MARKHUNT brake, execution_intent, HUNT/CLEAN split, session-BLOCKED).
  - Getting-Started.md: audit_checks 104 → 231 mutations; hook generation 7 section; +5 commands (hunt, crew, test, userperson, improve).
  - SubSaipen.md: saiwiki status row -- W-031 prepared (v7.219.0, 254 scenarios); machine-readable charters + role freshness section; saiui added to active sub-agents.
  - _Footer.md: version v7.158.0 → v7.219.0.
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `_Footer.md`
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:** PASS -- Scenarios.md 254 rows == CONFORMANCE 254; badges v7.219.0; 18-verb table matches CORE S1.10; 15 shortcuts; freshness triple via tools/freshness.py; charter role_revision matches; tools/validate.py PASS (known WARNs unchanged)
- **details:** verification checklist: Scenarios.md rows 217-254 present, no duplicate IDs, junk rows removed; Home/_Footer badges v7.219.0 with no stale era badge; command table 18 verbs matches CORE S1.10; shortcut count 15 matches canonical; freshness triple computed by tools/freshness.py; charter role_revision matches extensions/subs/saiwiki.md; tools/validate.py PASS baseline (known WARNs unchanged: sealed-log dates, saipython never-ran, digest stale)
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.219.0 -- 254 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
   3. Verify live: Home badge shows v7.219.0, Scenarios shows 254 rows, _Footer v7.219.0.
   4. No main-board ticket to close for this package.
   5. No main-project files touched by this package.

## W-032: wiki refresh v7.219.0 -> v7.226.0, 256 scenarios
- **status:** stale
- **superseded_by:** W-033 -- project HEAD moved 00aa12db -> 3a343e8d and the current audit delta changed producer/crew behavior; FORCE-FRESH also found stale RFC/shortcut/collect prose in maintained pages
- **summary:** 6 wiki pages refreshed to v7.226.0 truth (main HEAD 00aa12db): Scenarios 254->256 rows (2 new: 255-256 mirroring CONFORMANCE IDs 255-256 -- blocker-is-ticket-status, default-goal-driven-execution), mirrors: marker stamped with current canonical digest; Home/_Footer badges v7.219.0->v7.226.0, Phases range header v7.219.0->v7.226.0, SubSaipen saiwiki status row. 0 stale era badges left.
- **main_project_refs:** [saipen/CONFORMANCE.md, saipen/CORE.md, saipen/phases/*.md, tools/validate.py, tools/freshness.py, VERSION]
- **critical:** false
- **producer:** saiwiki
- **source_head:** 00aa12db9f01c55cb76c3e2a6e6ba35c33a4135c
- **source_tree_fingerprint:** git-delta-v1:dbf4dbd65033040a35f23dd831020659be6cf8d0e33bdb31a973b8a6a153ec6b
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:**
  - Scenarios.md: 254->256 rows (2 new: 255-256), IDs mirror CONFORMANCE 1-256 exactly; headline updated to 256; mirrors: marker stamped `sha256:9babcb02e659febc` (matches canonical CONFORMANCE 1-256 digest computed via tools/validate.py's exact payload rule).
  - Home.md: badge v7.219.0 -> **v7.226.0**, "Key features" header v7.226.0, NITRO bullet (v7.226.0).
  - _Footer.md: version v7.219.0 -> v7.226.0.
  - Phases.md: range header v7.104.0-v7.219.0 -> v7.104.0-v7.226.0; Session BLOCKED bullet (v7.226.0).
  - SubSaipen.md: saiwiki status row -- W-032 prepared (v7.226.0, 256 scenarios).
  - Tutorials.md, Use-Cases.md, _Sidebar.md: no drift (unchanged).
- **payload:** 6 modified pages in the wiki clone `kitchen/wiki/` (local, uncommitted):
  - `Home.md`, `Scenarios.md`, `Phases.md`, `SubSaipen.md`, `_Footer.md` (Getting-Started.md unchanged)
  - To integrate: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` review, commit, push to github.com/vacterro/saipen.wiki.
- **verified:** PASS -- Scenarios 256 rows == CONFORMANCE 256; markers sha256:9babcb02e659febc; Home/_Footer badges v7.226.0; freshness triple via tools/freshness.py (git-delta-v1); charter role_revision matches; no stale era badges
- **instructions:**
  1. Review the uncommitted diff: `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  2. Commit with message style `saiwiki: refresh wiki to v7.226.0 -- 256 scenarios, 6 pages` and push to origin (github.com/vacterro/saipen.wiki).
  3. Verify live: Home badge shows v7.226.0, Scenarios shows 256 rows, _Footer v7.226.0.
  4. No main-board ticket to close for this package.
  5. No main-project files touched by this package.

## W-033: FORCE-FRESH current v7.226.0 wiki, producer hardening and audit closure
- **status:** stale
- **superseded_by:** W-034 -- project HEAD moved 3a343e8d -> e045ad07 and the tree fingerprint changed (git-delta-v1:4ec002cc -> git-delta-v1:a9b068ed) from CORE-002..007 + W2-004..008; FORCE-FRESH re-bound the same 8 verified pages to the new source triple without content change; collect skips this entry rather than ticketing a ghost
- **summary:** All 9 maintained wiki pages re-read against the current source triple. Six pages gained current producer-parallelism/audit truth or stale-rule corrections; Scenarios remains a verified 256-row canonical ID mirror; 8 pages differ from the wiki remote and are ready for explicit integration.
- **main_project_refs:** [VERSION, README.md, CHANGELOG.md, KNOWLEDGE/ADR-0001-v7-producer-parallelism.md, saipen/BOOT.md, saipen/CORE.md, saipen/STYLE.md, saipen/CONFORMANCE.md, saipen/CONVERGE.md, saipen/OPS.md, saipen/phases/*.md, extensions/subs/PROTOCOL.md, extensions/subs/crew.md, extensions/subs/sai*.md, tools/freshness.py, tools/validate.py, tools/saipen_engine/producer.py, tools/saipen_engine/intent.py, tools/saipen_engine/journal.py, tools/saipen_engine/crew.py, tools/saipen_engine/release.py, tools/saipen_engine/subs.py]
- **critical:** false
- **producer:** saiwiki
- **source_head:** 3a343e8d0e5a04e2cb43b671c9072996e810c65a
- **source_tree_fingerprint:** git-delta-v1:4ec002cc5f2d23a8858d6c959ec2704e25be28f555a0396e5502685a0a4f3eb6
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:**
  - `Home.md`: v7.226 producer-local lock/epoch/staging, dependency-aware CURRENT/COMPATIBLE_DRIFT/STALE model, ADR link, current audit closure, and stale 13-key count corrected to 15.
  - `Phases.md`: PREPARE now states real FORCE-FRESH execution, complete verification, exact dependency sets, atomic READY publication, `ROLE_NOT_RUN`, and no Core mutation; stale RFC rule destinations corrected to CORE.
  - `Getting-Started.md`: no-install rule path corrected from RFC redirect to CORE; mutation-count copy made drift-safe; dependency-aware producer package section added.
  - `SubSaipen.md`: all six crew roles described from current evidence; stale “saipython never run” and v7.157 translation claims removed; intake/disposition semantics corrected; producer parallelism documented.
  - `Tutorials.md`: BOOT/CORE/STYLE path corrected; shortcut tutorial rebuilt to all 15 exact assignments (`gg` goal, `cc` continue); concurrent producer-prepare tutorial added.
  - `Use-Cases.md`: stale `cc = goal` removed; isolated concurrent `ee` + `qq` use case added.
  - `Scenarios.md`: complete IDs 1-256, unique and contiguous; mirror marker `sha256:9babcb02e659febc` freshly recomputed from the canonical CONFORMANCE ID-to-title map and matched exactly.
  - `_Footer.md`: v7.226.0 current; `_Sidebar.md`: all maintained pages linked and unchanged.
- **payload:** 8 modified pages in `kitchen/wiki/`: `Home.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `Tutorials.md`, `Use-Cases.md`, `Scenarios.md`, `_Footer.md`. `_Sidebar.md` was regenerated/verified content-equivalent and needs no write.
- **verified:** PASS -- strict READY `sha256:7889cd32216030b9182006f61a7b79f20067549028333d968825b87d930766fa` published at producer epoch 1 with 42 exact read dependencies and 8 payload/write targets; `tools/validate.py --gate collect:saiwiki` exit 0; strict READY decode has zero errors and payload bytes equal the kitchen pages; source identity capture + bounded revalidation PASS; charter role revision matches; 256 unique contiguous scenario IDs; canonical mirror digest matches; wiki diff whitespace check PASS; 9/9 page inventory complete; no stale RFC rule destinations outside canonical scenario-history rows; no integration, commit, tag, push, or remote write performed.
- **instructions:**
  1. Recompute and require this exact freshness triple before collection; any mismatch means run `qq` again.
  2. Review `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff --check` and `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff`.
  3. Integrate only the 8 declared payload pages through Core's named saiwiki collect path; leave `_Sidebar.md` unchanged.
  4. Run the collect:saiwiki gate plus the normal VERIFY and REVIEW gates.
  5. Commit the wiki clone with a message such as `docs: refresh v7.226 producer and audit truth`, push only through the authorized SHIP path, then verify Home, Tutorials, Scenarios, and SubSaipen live.
- **details:** W-032 was structurally fresh when produced at 00aa12db but became stale after three implementation commits and the current audit delta. FORCE-FRESH inspection found user-visible drift beyond the source triple: two pages still routed readers to the RFC redirect, Tutorials and Use-Cases still assigned `cc` to goal, the shortcut tutorial claimed 13 instead of 15 keys, SubSaipen described pre-disposition collect behavior and a never-run Python worker, and the committed producer-parallelism ADR had no wiki explanation. W-033 supersedes it without touching the main tree or wiki remote.

## W-034: FORCE-FRESH re-bind to e045ad07, 8 pages (content unchanged from W-033)
- **status:** stale
- **summary:** W-033 was structurally fresh when produced at 3a343e8d but became stale after CORE-002..007 + W2-004..008 landed (11 files, +3090/-627, touching producer.py/journal.py/operations.py but NOT CONFORMANCE.md or saipen/ docs -- canonical scenario IDs and wiki-facing prose unchanged). FORCE-FRESH regenerated and re-published the identical 8-page payload bound to the new source triple (head e045ad07, tree git-delta-v1:a9b068ed). No page content changed; only the producer freshness binding was refreshed. 8 pages are ready for explicit integration.
- **main_project_refs:** [VERSION, README.md, CHANGELOG.md, KNOWLEDGE/ADR-0001-v7-producer-parallelism.md, saipen/BOOT.md, saipen/CORE.md, saipen/STYLE.md, saipen/CONFORMANCE.md, saipen/CONVERGE.md, saipen/OPS.md, saipen/phases/*.md, extensions/subs/PROTOCOL.md, extensions/subs/crew.md, extensions/subs/sai*.md, tools/freshness.py, tools/validate.py, tools/saipen_engine/producer.py, tools/saipen_engine/intent.py, tools/saipen_engine/journal.py, tools/saipen_engine/crew.py, tools/saipen_engine/release.py, tools/saipen_engine/subs.py]
- **critical:** false
- **producer:** saiwiki
- **source_head:** e045ad07d21aac78cce073caa732a5780652882b
- **source_tree_fingerprint:** git-delta-v1:a9b068edabfdf9861f2aad20cd4502d29357e552166c3ac426eb6fbb21e7fea6
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:**
  - `Home.md`: identical content to W-033 (v7.226 producer-local lock/epoch/staging, dependency-aware CURRENT/COMPATIBLE_DRIFT/STALE model, ADR link, current audit closure, 15-key correct count); re-bound to e045ad07.
  - `Phases.md`: identical content to W-033 (PREPARE FORCE-FRESH execution, ROLE_NOT_RUN, no Core mutation); re-bound.
  - `Getting-Started.md`: identical content to W-033 (no-install path via CORE, dependency-aware producer package section); re-bound.
  - `SubSaipen.md`: identical content to W-033 (six crew roles, producer parallelism); re-bound.
  - `Tutorials.md`: identical content to W-033 (15 exact shortcut assignments, concurrent prepare tutorial); re-bound.
  - `Use-Cases.md`: identical content to W-033 (isolated concurrent ee + qq use case); re-bound.
  - `Scenarios.md`: complete IDs 1-256, unique and contiguous; mirror marker sha256:9babcb02e659febc unchanged; re-bound to e045ad07.
  - `_Footer.md`: v7.226.0 current; `_Sidebar.md`: maintained pages linked and unchanged.
- **payload:** 8 modified pages in `kitchen/wiki/`: `Home.md`, `Phases.md`, `Getting-Started.md`, `SubSaipen.md`, `Tutorials.md`, `Use-Cases.md`, `Scenarios.md`, `_Footer.md`. `_Sidebar.md` regenerated/verified content-equivalent, no write needed.
- **verified:** PASS -- strict READY `sha256:4481cb57bd31c46e5bebdf5180f26eeae583cb258b40a0b7cfeb5dfbc9063fea` published at producer epoch 1 with 42 exact read dependencies and 8 payload/write targets; source identity capture + bounded revalidation after the e045ad07 landing PASS; charter role revision matches; 256 unique contiguous scenario IDs; canonical mirror digest sha256:9babcb02e659febc matches; zero page-content delta vs W-033 (only freshness binding refreshed); no integration, commit, tag, push, or remote write performed.
- **instructions:**
  1. Recompute and require this exact freshness triple (head e045ad07 / tree git-delta-v1:a9b068ed / role_revision sha256:54a42...) before collection; any mismatch means run `qq` again.
  2. Review `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff --check` and `git -C .saipen/extensions/subs/saiwiki/kitchen/wiki diff` (diff vs W-033 should be empty except the binding metadata).
  3. Integrate only the 8 declared payload pages through Core's named saiwiki collect path; leave `_Sidebar.md` unchanged.
  4. Run the collect:saiwiki gate plus the normal VERIFY and REVIEW gates.
  5. Commit the wiki clone with a message such as `docs: refresh v7.226 producer and audit truth (re-bound to e045ad07)`, push only through the authorized SHIP path, then verify Home, Tutorials, Scenarios, and SubSaipen live.
- **details:** W-033 (3a343e8d) went stale without content drift: CORE-002..007 + W2-004..008 touched producer.py/journal.py/operations.py only -- no CONFORMANCE.md or saipen/ doc edits, so canonical IDs and wiki-facing prose are unchanged. FORCE-FRESH re-read the 8 kitchen pages, recomputed the write_set from page bytes and the read_set from the live tree (42 deps, none absent), rebuilt the package with the current identity, and published a fresh strict READY. W-034 supersedes W-033 with identical payload content, refreshed binding only. Main tree and wiki remote untouched.
## W-035: saiwiki package bound to e98bcb03
- **status:** stale
- **superseded_by:** W-039
- **summary:** current saiwiki package bound to committed source
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saiwiki
- **source_head:** e98bcb0363deb76963ee54897da8b3599e346acc
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** current saiwiki package
- **payload:** []
- **verified:** PASS -- saiwiki package integrated CURRENT
- **instructions:** Core records the integrated saiwiki disposition.
- **details:** saiwiki integration bound to e98bcb03/git-delta-v1:55f5361.


## W-036: saiwiki re-bind to 6cbed249
- **status:** stale
- **summary:** superseded by W-037 (HEAD moved to e75367f7)
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saiwiki
- **source_head:** 6cbed2492abee837962583c14566d60487337511
- **source_tree_fingerprint:** git-delta-v1:81eef5d668f4b6b15df8ddb0a5ad304d475a97f25b78a9ac43f7f27da94d9210
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 8 maintained wiki pages + _Sidebar; content-identical to W-035 (only freshness binding refreshed)
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Phases.md, Getting-Started.md, SubSaipen.md, Tutorials.md, Use-Cases.md, Scenarios.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- strict READY sha256:0c9bb0d46a5394d17b401f453... at producer epoch 6; 9 payload targets; content-identical to W-035; charter role revision matches; no integration, commit, tag, push, or remote write performed.
- **instructions:** Core integrates the 9 declared payload pages through the canonical saiwiki collect path; leave wiki remote untouched until the authorized SHIP path.
- **details:** W-035 (e98bcb03) went stale by freshness triple (HEAD moved to 6cbed249 after PY-11 ruff commit). Re-read source identity, rebuilt the package with the current binding, re-published strict READY with identical payload content. Main tree and wiki remote untouched.


## W-037: saiwiki re-bind to e75367f7
- **status:** stale
- **summary:** superseded by W-038 (HEAD 078f5cd6)
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saiwiki
- **source_head:** e75367f79c68c5386f73cd76a0fcb89cdc6223bb
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 8 maintained wiki pages + _Sidebar; content-identical to W-035/W-036
- **payload:** []
- **verified:** PASS -- integrated CURRENT against e75367f7; identity 4414fe51acb8...
- **instructions:** Core records the integrated saiwiki disposition.
- **details:** content-identical re-bind to e75367f7/55f5361 after crew fix commits.


## W-038: saiwiki re-bind to 078f5cd6
- **status:** stale
- **superseded_by:** W-039
- **summary:** current saiwiki package re-bound to committed source 078f5cd6
- **main_project_refs:** []
- **critical:** false
- **severity:** P3
- **producer:** saiwiki
- **source_head:** 078f5cd6d12e36d24677fc79b86f0457dd70f4ea
- **source_tree_fingerprint:** git-delta-v1:55f536106504e1e87a44617c149d6c741e6227860e93ddfb56bdd0cb08576776
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 8 maintained wiki pages + _Sidebar; content-identical to W-035/036/037
- **payload:** []
- **verified:** PASS -- integrated CURRENT against 078f5cd6
- **instructions:** Core records the integrated saiwiki disposition.
- **details:** content-identical re-bind to 078f5cd6/55f5361.

## W-039: FORCE-FRESH command-routing and safety-valve truth
- **status:** stale
- **superseded_by:** W-040
- **summary:** Rebuilt the maintained wiki against current command-routing and safety-valve semantics: six changed canonical scenario titles, mechanical Cyrillic folding (six twins/nine without; `сс` is continue), uniform `cc` valve resume, 15 exact routes, and the fixed WAIT shape.
- **main_project_refs:** [VERSION, README.md, CHANGELOG.md, KNOWLEDGE/ADR-0001-v7-producer-parallelism.md, saipen/BOOT.md, saipen/CORE.md, saipen/STYLE.md, saipen/CONFORMANCE.md, saipen/CONVERGE.md, saipen/OPS.md, saipen/phases/*.md, extensions/subs/PROTOCOL.md, extensions/subs/crew.md, extensions/subs/sai*.md, tools/freshness.py, tools/validate.py, tools/saipen_engine/producer.py, tools/saipen_engine/intent.py, tools/saipen_engine/journal.py, tools/saipen_engine/crew.py, tools/saipen_engine/release.py, tools/saipen_engine/subs.py]
- **critical:** false
- **severity:** P2
- **producer:** saiwiki
- **source_head:** b666b77ff3ad8e5066de4d3ec3ad3fc03c63f1c8
- **source_tree_fingerprint:** git-delta-v1:ffafd93a02dc3fecb0dea8e1c92dd53685d6813c5bb6c1d50160e71d7c0b12b6
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 9/9 maintained wiki pages re-read; Home, Phases, Tutorials, Use-Cases and Scenarios corrected; Getting-Started, SubSaipen, _Footer and _Sidebar verified content-current
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Phases.md, Getting-Started.md, SubSaipen.md, Tutorials.md, Use-Cases.md, Scenarios.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- 9-page inventory; Scenarios IDs 1-256 unique/contiguous; canonical mirror `sha256:b5e98946da9926b6`; stale valve/twin prose scan clean; wiki diff whitespace check PASS; strict READY `sha256:7ee12026e17ee890111247a5b9a3aa6aa49bb3c8ef5d7c374084f590d08a58e9` at epoch 1 with 42 exact read dependencies and 9 authenticated payload entries
- **instructions:**
  1. Recompute and require the exact source triple above; any mismatch means run `qq` again.
  2. Run `python -B tools/validate.py --gate collect:saiwiki`; refuse on any mismatch.
  3. Integrate only the 9 declared payload pages through Core's named saiwiki collect path.
  4. Re-run the scenario mirror, wiki whitespace, Core VERIFY and REVIEW gates before SHIP; leave the wiki remote untouched until authorized SHIP.
- **details:** W-035/W-038 were stale bindings and carried no payload. W-039 is a fresh complete package. It also corrects the old scenario footer count from 254 to 256 and replaces historical current-state prose that assigned valve reauthorization to bare `saipen goal`.

## W-040: v7.226.1 final wiki rebind
- **status:** stale
- **summary:** Rebound all nine reviewed wiki pages after final v7.226.1 metadata; current-version badges, footer, phase range and producer-status rows now name the release packages SAIT-023/W-040.
- **main_project_refs:** [VERSION, README.md, CHANGELOG.md, KNOWLEDGE/ADR-0001-v7-producer-parallelism.md, saipen/BOOT.md, saipen/CORE.md, saipen/STYLE.md, saipen/CONFORMANCE.md, saipen/CONVERGE.md, saipen/OPS.md, saipen/phases/*.md, extensions/subs/PROTOCOL.md, extensions/subs/crew.md, extensions/subs/sai*.md, tools/freshness.py, tools/validate.py, tools/saipen_engine/producer.py, tools/saipen_engine/intent.py, tools/saipen_engine/journal.py, tools/saipen_engine/crew.py, tools/saipen_engine/release.py, tools/saipen_engine/subs.py]
- **critical:** false
- **severity:** P2
- **producer:** saiwiki
- **source_head:** b666b77ff3ad8e5066de4d3ec3ad3fc03c63f1c8
- **source_tree_fingerprint:** git-delta-v1:53d374c6c00ca7d3e9c9ef7d3ae90cb523f7740b0f41913c6b809fd982141b95
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:** 9/9 maintained pages; 256 scenario IDs unique/contiguous; v7.226.1 current-version surfaces refreshed
- **payload:** [.saipen/extensions/subs/saiwiki/kitchen/wiki/Home.md, Phases.md, Getting-Started.md, SubSaipen.md, Tutorials.md, Use-Cases.md, Scenarios.md, _Footer.md, _Sidebar.md]
- **verified:** PASS -- strict READY `sha256:86bd88bf46b7b4281edf2b0653bbeb827578a18c921e1f286f1ebcb18d7763d7` at epoch 3 with 42 exact read dependencies and 9 authenticated payload entries; canonical mirror `sha256:b5e98946da9926b6`
- **instructions:** Run `python -B tools/validate.py --gate collect:saiwiki`; integrate only the named READY package through Core; publish the wiki only through an authorized SHIP path.
- **details:** W-039 content fixes are preserved. W-040 adds only final release-version truth and a current producer-status rebind before the main v7.226.1 ship.

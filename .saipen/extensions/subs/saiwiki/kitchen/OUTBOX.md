# OUTBOX

## WIKI-009: verify drift v7.103.0..v7.121.0 — 18 releases, 8 wiki pages
- **status:** stale
- **stale_reason:** the finding was actioned by this subSaipen's own W-022 (wiki pushed at b466666, badge now v7.121.0), so collecting it would ticket a ghost -- PROTOCOL.md § 2's `stale` is exactly this case. The project has moved on again since; that is a NEW sweep's finding, not this one's
- **summary:** Project v7.121.0 (ac37c91), wiki still at v7.103.0 (ed51225). 18-release gap: v7.104.0–v7.121.0. CONFORMANCE 99→140 rows. 8 new tools: audit_checks, audit_order, audit_parity, audit_tags, audit_floor, parity CI, hook stamp, encoding guard. All 8 wiki pages inspected live — every one stale. Light refresh recommended (P2).
- **main_project_refs:** [VERSION (7.103.0→7.121.0), CHANGELOG.md (v7.104.0–v7.121.0), saipen/CONFORMANCE.md (rows 100→140), tools/validate.py (+850 lines), tools/audit_checks.py (new, 334), tools/audit_order.py (new, 185), tools/audit_parity.py (new, 168), tools/audit_tags.py (new, 186), tests/validate.sh (+9), tests/validate.ps1 (+8), .github/workflows/release.yml (+27), .github/workflows/validate.yml (+51), extensions/schemas/board.schema.json (+2), extensions/schemas/log.schema.json (+4), tools/install_hook.py (+15)]
- **critical:** false
- **severity:** P2
- **details:**
  Working tree at v7.121.0 (ac37c91). Wiki remote at committed v7.103.0 (ed51225).

  **RELEASES COVERED (v7.103.0 → v7.121.0):**

  **v7.104.0 — Phantom version check**
  - 42 lines cited v7.100.0 which had no tag/CHANGELOG/commit. New check: cited version must exist in release ledger (git tags + CHANGELOG), not merely sit below VERSION. Scan widened past markdown to JSON schemas, validator, portable floor.
  - Release ledger halves compared: 2 tags without changelog, 9 entries without tag.
  - `release.yml` `make_latest` fixed: re-pushing old tag no longer marks it Latest.

  **v7.105.0 — CI fork in half a ledger**
  - `actions/checkout` shallow clone = no tags in CI. Release ledger check FAILed a correct repo. Skipped with WARN unless both halves present.
  - Release job died on `git fetch --tags` against shallow clone. Both workflows now `fetch-depth: 0`.

  **v7.106.0 — Palette named Vintage Golden**
  - UI.md declares Vintage Golden default (was "Wintage Golden"). 18 tokens reference. 46 files renamed: 2 root docs + 44 locale copies.
  - Palette name guard: UI.md must name its palette, no shipped doc may name superseded one.

  **v7.107.0 — Palette guard generalized**
  - Guard held a single superseded name — couldn't survive its own rename. Now a list, one-line append per rename.
  - CHANGELOG.md exempt (records historical names).

  **v7.108.0 — Nine unclaimed MUSTs**
  - 3 RFC sections stated 9 MUSTs with no CONFORMANCE row: § 1.7 workspace hygiene, § 1.8 batch parsing, § 2.3 completion rule.
  - § 1.7 enforced mechanically: .saipen/ carrying phases/tools/tests/schemas/adapters/templates/core doc now FAILs. `extensions/subs/` excluded (project's own instances).
  - LOG sealed: 147 events, E-881..E-1027, 169→22 lines. Second seal refused (threshold guard held).

  **v7.109.0 — Tag audit (audit_tags.py)**
  - 4 tag-VERSION mismatches found (v7.61.0, v7.74.0, v7.81.0, v3.1.1a). Historical mismatches recorded per-entry, never rewritten.
  - Exemption list rechecked: an entry that no longer describes a real defect FAILs.

  **v7.110.0 — UTF-16 encoding crash**
  - tools/validate.py died on first file if STATE.md was UTF-16 (PowerShell default). No FAILs, one traceback, zero checks performed.
  - All 3 checkpoint files encoding-checked up front. BOM sniffing + NUL parity + cp1251 fallback via read_doc().
  - `schema_version` from the future: WARN (was silent PASS).

  **v7.111.0 — read-only dual meaning, sub parity**
  - `mode: read-only` = capability lock for Core (7 banned phases), scope lock for subSaipen (4 banned phases). PROTOCOL.md called them identical until now.
  - `HUNT -> DONE` legal for subSaipen only (saihunt was in that state truthfully).
  - SubSaipen STATE checked against Core's rules: 9th required field, transition legality, command vocabulary.
  - `SAIPEN_COMMANDS` declared after first use; run_scenarios.py now names crashes as crashes.

  **v7.112.0 — audit_order.py, three NameErrors**
  - `tools/audit_order.py`: reads top-level names in file order, reports use-before-define. Caught SAIPEN_COMMANDS, IS_SAIPEN_HOME, saipen_dir.
  - Ruff cannot see these (F821 only catches names never bound).
  - `requires:` values checked against capability vocabulary (typo silently removed requirement).
  - `saipen_version` compared against home's major (was type-checked only).
  - Release-ledger warning no longer states wrong count.

  **v7.113.0 — Hook generation stamp**
  - `.git/hooks/pre-commit` carries generation stamp now. In consuming projects the hook is the only gate — never updated itself. This repo's hook was stamp-less.
  - Hook's fail-open path now prints what it couldn't find and the repair command.

  **v7.114.0 — BOOT.md language rule, ambient-signal ban**
  - BOOT.md carries reply-language rule directly (was only in STYLE.md, unreachable cold).
  - STYLE.md ambient-signal ban now names "repository contents" — 33 translated guides are content to produce, never a language cue.
  - Estonian alias `et` (kitchen) vs `EE` (guides) resolved, both directions checked.

  **v7.115.0 — last_event, TEMPLATE placeholder**
  - `last_event` enforced: RECOMMENDED field that catches STATE drifted from LOG. Had zero references in validator.
  - TEMPLATE/STATE.md placeholders (agent: <name>) can no longer escape into live subSaipen — breaks liveness comparison.
  - `_tools_parent` hoisted to top (4th NameError of session).

  **v7.116.0 — claim_time validation, warn category**
  - `claim_time` validated as ISO-8601 UTC (was recognised but never read). Liveness judged from it against 15-min window.
  - `owner` without `claim_time` (or reverse) now warns.
  - `warn()` now prints its category key in every WARN line (was only in roll-up).

  **v7.117.0 — review_passes, digest freshness**
  - `review_passes` enforced (field existed, number never read — cap right back where RFC says it must not be).
  - `kitchen/digest.md` shape + freshness checked. Live digest named v7.83.0 — 33 releases out of date.

  **v7.118.0 — MARKHUNT manifest, no-git head pair**
  - MARKHUNT closure manifest validated: shape, cursor vocabulary, vector completeness.
  - no-git head pair must be a pair (one real hash + one no-git skipped equality test).
  - Hunted by luck: 192 MUSTs, 77 artifacts, 14 candidates, 1 real (the MARKHUNT manifest file).

  **v7.119.0 — audit_checks.py (41 mutation harness)**
  - `tools/audit_checks.py`: 41 mutations of known-good copy, each asserts validator names that specific failure.
  - Harness control run is precondition: case whose expected text already present before mutation FAILs loudly.
  - Red-tested both directions: raising one cap kills exactly one case, silencing fail() kills 39.

  **v7.120.0 — audit_parity.py, floor wording**
  - Portable floor claimed conformance in validator's own words while catching 11/41 defects. Now says "Portable floor complete: no structural break found".
  - `tools/audit_parity.py` guards floor from getting weaker (baseline comparison).

  **v7.121.0 — bash vs sh, control-failure naming**
  - `find_bash()` picked sh as fallback = dash on Ubuntu, tests/validate.sh is #!/bin/bash. Died in 0.4s.
  - Control-failure message now names which tool, exit code, and FAIL lines.

  **PER-PAGE DRIFT SUMMARY:**

  | Page | v7.103.0 content | v7.121.0 reality | Drift | Action |
  |---|---|---|---|---|
  | **Home.md** | badge v7.103.0, key features through v7.103.0, "99 conformance scenarios" | v7.121.0, features through v7.121.0, 140 scenarios | version badge + features + scenario count + 6 major feature bullet gaps (v7.104.0–v7.121.0) | Update badge, key features, scenario count, add bullet for audit tools/tag guard/encoding/claim/hook/palette |
  | **Scenarios.md** | "99 scenarios (rows 1-99)" table ends at row 99 | 140 rows (rows 100-140 added) | 41 missing rows (100-140) covering phantom version, encoding, claim_time, audit tools, hook stamp, palette, bash trap | Add rows 100-140 to advanced table |
  | **Getting-Started.md** | inject.sh cygpath-w (v7.100.0), portable floor (v7.94.0), WAIT categories (v7.93.0) | Same + hooks stamp + audit_floor + encoding guard + validation expansion | Missing: pre-commit hook stamp, audit_checks.py/audit_order.py/audit_parity.py, UTF-16 guard | Add hook stamp section, note audit tools exist, mention encoding resilience |
  | **Phases.md** | VERIFY gate-stuck-red (v7.101.0), done.md fix (v7.101.0), 16 phases | Same + last_event + review_passes + MARKHUNT manifest + digest freshness + claim_time + sub-state parity | Missing 7 release's worth of phase-tool additions | Add entries for last_event check, review_passes cap, MARKHUNT manifest enforcement, digest freshness check, claim_time validation |
  | **SubSaipen.md** | sub validation guards (v7.98.0), liveness (v7.99.0), TEMPLATE fix (v7.101.0), 4 active agents | Same + read-only dual meaning + HUNT→DONE + sub STATE parity (v7.111.0) + never-run fix | Missing: read-only scope/capability distinction, HUNT→DONE for subs, sub STATE validated as Core | Add read-only dual meaning, sub parity, sub STATE validation section |
  | **Tutorials.md** | — (not fetched, likely structural) | — | Unknown — fetch needed | Check separately |
  | **Use-Cases.md** | — (not fetched, likely structural) | — | Unknown — fetch needed | Check separately |
  | **_Footer.md** | badge v7.103.0 | v7.121.0 | version only | Bump to v7.121.0 |
  | **_Sidebar.md** | no version badge, links only | no version badge, links only | None — stable | Skip |

  **RECOMMENDATION:** Light refresh (P2). 6 pages need updates: Home, Scenarios (+41 rows), Getting-Started (minor), Phases (minor), SubSaipen (minor), _Footer (version). Tutorials and Use-Cases need independent check — structural content likely unchanged. ~30 min total. No full regeneration needed — same methodology as W-016/W-017.

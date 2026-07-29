# Board
## DOING

## TODO

## DONE
- [x] T-279 [P0] Rule coverage: every RFC section stating a MUST must be cited by a CONFORMANCE row. Three sections stated nine MUSTs with no row at all -- 1.7, 1.8, 2.3. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-280 [P0] RFC 1.7 workspace hygiene enforced mechanically: .saipen/ carrying phases/tools/tests/schemas/adapters/templates or a core doc now FAILs. extensions/subs/ deliberately excluded -- those are the project's own instances, not a copy. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-281 [P1] 1.8 and 2.3 given rows that state they are behavioral and unenforceable by any tool here. A MUST with no row is indistinguishable from a MUST nobody remembered. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-282 [P1] Active LOG sealed into logs/LOG-004.md: 147 events, E-881..E-1027. 169 -> 22 lines. Second run refused -- the outer threshold guard held. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-283 [P2] Ship v7.108.0. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-276 [P1] Palette name corrected to Vintage Golden across 49 files. CHANGELOG.md and the append-only logs deliberately keep the old name -- they are history. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-277 [P0] The palette guard now holds a list of superseded names and exempts CHANGELOG. Enforcing exactly one name meant the guard could not survive its own name being corrected. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-278 [P2] Ship v7.107.0. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-272 [P1] UI.md declares Vintage Golden the default palette, states the eighteen tokens are the reference, and says how an implementation may extend it without inline hex. The lighter values had been sitting uncommitted since before this session; they are already what SAIPENVIEW ships. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-273 [P1] Palette renamed across 46 files -- 2 shipped root docs, 44 locale copies. A proper-noun swap, identical in every language, so not delegated as translation work. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-274 [P0] New [palette-name] check: UI.md must name its palette, and no shipped doc may name the superseded one. Red-tested both directions. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-275 [P2] Ship v7.106.0. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-269 [P0] The release-ledger check FAILed a correct repo on its first CI run: checkout is shallow and carries no tags, so the ledger arrived half-empty and two tagged-but-unchangelogged releases read as phantoms. Skips with a WARN unless both halves are present. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-270 [P0] Both workflows check out with fetch-depth: 0. The release job also died on `git fetch --tags` against a shallow clone, so v7.104.0 was tagged with no GitHub Release published. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-271 [P2] Ship v7.105.0 and publish the missing v7.104.0 release. | verify: tools/validate.py PASS (2026-07-29)
- [x] T-263 [P0] 42 lines named v7.100.0 as the release they shipped in. No tag, no CHANGELOG entry, no commit whose VERSION said it. All below VERSION, so the future-version bound certified every one. Corrected to v7.101.0, where the work actually shipped. | verify: 0 phantom citations, red test reinstating one FAILs (2026-07-29)
- [x] T-264 [P0] New [phantom-version] check: a cited version must exist in the release ledger (git tags + CHANGELOG), not merely sit below VERSION. Scan widened past markdown -- the JSON schemas and the validator itself carried the number. | verify: red-tested, found 25 citations my own manual sweep had missed (2026-07-29)
- [x] T-265 [P1] Release ledger halves compared: 2 tags without a CHANGELOG entry, 9 entries without a tag. WARN -- closing it means rewriting history or publishing backdated releases. | verify: both directions reported (2026-07-29)
- [x] T-266 [P0] release.yml pinned make_latest to whether this is the highest tag. Re-pushing an old tag marked it Latest and buried v7.103.0; observed live. | verify: yaml parses, Latest repointed to v7.103.0 (2026-07-29)
- [x] T-267 [P1] saipen/phases/hunt.md carried a UTF-8 BOM and five cp1251-mangled section signs from an uncommitted PowerShell edit. Repaired, content change kept. | verify: text lint PASS (2026-07-29)


## BLOCKED


# Board
## DOING

## TODO

## DONE
- [x] T-272 [P1] UI.md declares Wintage Golden the default palette, states the eighteen tokens are the reference, and says how an implementation may extend it without inline hex. The lighter values had been sitting uncommitted since before this session; they are already what SAIPENVIEW ships. | verify: tools/validate.py PASS (2026-07-29)
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


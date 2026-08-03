# OUTBOX
- [ST-009] [reviewed -> T-397] SAIT-008 output collected after user-approved boundary review: 63-document coverage retained as review material; weak guide translations require Core correction before ship.

## ST-010: ee prepare (E-1821) -- Core-owned README restructure + palette
- **status:** draft
- **producer:** saitranslate (main-flow prepare)
- **source_head:** d74a26c (v7.173.0)
- **coverage:** Core-owned 3/32 kitchen READMEs (ru/et/ded) + 2/3 root mirrors (README.ee.md, README.ded.md) restructured to e073234 outline (How it works / Commands table / Documentation table / Built with SAIPEN); README.ee.md language switcher restored; palette "Vintage Golden" fixed in ded/et; SPEC_RU/ET/DED untouched (current).
- **gap:** 29 locales + README.ja.md mirror still on pre-restructure outline; palette corruption in 5 SPECs (da/de/hi/sv/zh) + 14 READMEs (ar da es fi fr hu it ko no pl pt ro sk sv tr + hi/zh equivalents); SPEC_DA stale tree + English leak -- all ticketed SAIT-009 for sub saitranslate instance.
- **payload:** [.saipen/saitranslate/kitchen/{ru,et,ded}/README_*.md, README.ee.md, README.ded.md]
- **verified:** tools/validate.py PASS (conformant, 5 pre-existing warnings); shortcut callouts mirror==kitchen for et/ded; badges v7.173.0 present
- **instructions:** integrate via eee when SAIT-009 completes the 29-locale sweep; then bump badges, validate, ship

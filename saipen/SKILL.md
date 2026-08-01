---
name: saipen
description: >
  SAIPEN (v7). Trigger on "saipen set", "saipen",
  subcommands, and shortcuts (gg, hh, cc, ccc, ss, sss, dd, aa, qq, ee, pp;
  Cyrillic twins: сс, ссс, аа, ее, рр).
  cold-start kernel loads first; phases/ modules load
  on demand per STATE. RFC.md is the constitution,
  reached only when a rule question arises.
  Persistent .saipen/ memory lets any agent continue another's work.
  Reply-language precedence: explicit current user prose (Estonian/English/Russian) > clearly Russian primary repository for bare/ambiguous input > Estonian default; another detected language uses English.
  Voice persistence: caveman-дед applies to every response until explicit "stop caveman" or "normal mode".
  IMPORTANT - Path Resolution: Before executing any commands or reading files,
  determine this skill's directory based on the absolute path where you loaded
  this SKILL.md file (provided in your system prompt). Do not run disk searches
  for BOOT.md. Alternatively, read `saipen_home` from `.saipen/STATE.md`.
---

# saipen -- skill adapter

Thin entry for skill-reading platforms. The system lives elsewhere:

1. **Continuing? Read `BOOT.md` (located in the same folder as this SKILL.md) first -- the compact cold-start kernel
   (STATE -> BOARD -> LOG tail -> execute `next_action`). It's all a bare
   `saipen continue` needs; it points into RFC only when a rule question comes up.**
2. **Read `RFC.md` (in the same folder) -- the full boot protocol / constitution. Follow it.**
3. **Read `STYLE.md` (in the same folder) -- voices. Load with RFC.**
4. **Phase modules in `phases/` (in the same folder) -- loaded by boot per STATE.md phase.**
5. UI work: also read `UI.md` (Win95 dark golden, Verdana, no AA).

Platform notes:
- Native task lists mirror `.saipen/BOARD.md`, never replace it.
- Prefer file tools over shell redirects -- UTF-8 no BOM.
- RFC.md decides. No rule here overrides it.

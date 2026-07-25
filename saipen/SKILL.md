---
name: saipen
description: >
  SAIPEN (v7). Trigger on "saipen set", "saipen",
  and subcommands. 2-tier architecture: boot RFC.md
  loads always; phases/ modules load on demand per STATE.
  Persistent .saipen/ memory lets any agent continue another's work.
---

# saipen -- skill adapter

Thin entry for skill-reading platforms. The system lives elsewhere:

1. **Continuing? Read `BOOT.md` first -- the compact cold-start kernel
   (STATE -> BOARD -> LOG tail -> execute `next_action`). It's all a bare
   `saipen continue` needs; it points into RFC only when a rule question comes up.**
2. **Read `RFC.md` -- the full boot protocol / constitution. Follow it.**
3. **Read `STYLE.md` -- voices. Load with RFC.**
4. **Phase modules in `phases/` -- loaded by boot per STATE.md phase.**
5. UI work: also read `UI.md` (Win95 dark golden, Verdana, no AA).

Platform notes:
- Native task lists mirror `.saipen/BOARD.md`, never replace it.
- Prefer file tools over shell redirects -- UTF-8 no BOM.
- RFC.md decides. No rule here overrides it.
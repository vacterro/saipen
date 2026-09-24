---
name: saipen
description: >
  SAIPEN (v7). Trigger on "saipen set", "saipen",
  subcommands, and shortcuts (gg, hh, ff, xx, vv, zz, cc, ccc, st, sss, dd,
  aa, qq, qqq, ee, eee, pp, tt, sc; Cyrillic twins: сс, ссс, аа, ее, еее,
  рр, хх).
  cold-start kernel loads first; phases/ modules load
  on demand per STATE. CORE.md is the constitution (successor to RFC.md),
  which was split in v7.190.0; MAINTENANCE.md covers autonomous evolution.
  The RFC.md stub is a compatibility redirect only — never treat it as
  authoritative and never route a rule question there.
  Persistent .saipen/ memory lets any agent continue another's work.
  Reply language is STYLE.md's `reply_language:` setting, default `et`
  (Estonian, always); `en`/`ru` pin another language and `auto` restores
  the precedence rule below. Under `auto` only:
  Reply-language precedence: explicit current user prose (Estonian/English/Russian) > clearly Russian primary repository for bare/ambiguous input > Estonian default; another detected language uses English.
  Voice persistence: caveman-дед applies to every response until explicit "stop caveman" or "normal mode".
  IMPORTANT - Path Resolution: determine this skill's directory from the
  absolute path where you loaded this SKILL.md file (provided in your system
  prompt) — the anchor for `protocol_dir`/`saipen_home`. Do NOT run disk
  searches for BOOT.md and do NOT scan the workspace, its parents or siblings
  for `.saipen/`: the SAIPEN home is often a sibling of the workspace. Project
  memory is exactly `<project_root>/.saipen/` (BOOT.md step 2); absent there
  means "not bootstrapped", never "no saipen state to load". Alternatively,
  read `saipen_home` from a bound `.saipen/STATE.md`.
---

# saipen -- skill adapter

**`saipen continue`, bare `saipen`, `cc` and `сс` mean EXECUTE the current
work. Loading this skill only returns instructions; it does not run Git,
inspect the project, or complete a command.** After loading it, follow BOOT,
run `saipen continue --json`, read the returned `load_path` and project memory,
and perform the returned action in this turn. Do not ask what `continue`
means, repeat this skill call, or stop at "state not checked": read that state.
Only an observed refusal or a canonical WAIT can justify a blocked report;
include its exact evidence and take available safe recovery first.

Thin entry for skill-reading platforms. The system lives elsewhere:

0. **Resolve the cold route deterministically -- never by searching.** Run the
   installed launcher (`bin/saipen.cmd`/`bin/saipen status --json` beside this
   file; BOOT.md Entry owns transport) and read its `cold_route`
   block. It names the bound `project_root`, `protocol_dir`, `boot`, `style`,
   `phase_module` and the `.saipen/` memory files, and states
   `search_required: false`. Open those exact paths. Do NOT use the host's
   grep/glob/search tool to locate protocol files, and never conclude that
   protocol startup failed because a host search tool errored: a ripgrep or
   search fault is a HOST fault, unrelated to SAIPEN. If the launcher itself
   is unavailable, read `BOOT.md` and the documents beside this SKILL.md by
   their known paths -- still without searching.

   When a search IS genuinely needed and the host's own search tool returns a
   transport error (never for zero matches -- that is a normal empty result),
   use the canonical read-only fallback `saipen search --hex
   <hex-encoded-utf8>`. It needs no generic shell admission, so it still works
   while the protocol state is invalid. Do not fall back to `grep`/`bash`.

1. **Read `BOOT.md`** (the file in the same folder as this SKILL.md) -- the
   compact cold-start kernel: STATE -> BOARD -> LOG tail -> execute
   `next_action`. That is everything a bare `saipen continue` needs. **Read it
   once; this list names it once.**
2. **`BOOT.md` loads `STYLE.md` before any output** -- voice governs the first
   token, so the kernel's own step 1 opens it. Nothing here overrides that
   order.
3. **Rule question? Route through `INDEX.md`** (same folder), the document map.
4. **`CORE.md` only for the exact rule you looked up.** It is the constitution;
   do not read it speculatively.
5. **`RFC.md` is a compatibility redirect and nothing else.** It holds no
   rules, it is not a destination, and no step above sends you there.
6. **Phase modules in `phases/`** (same folder) -- loaded by boot per STATE.md
   phase.
7. UI work: also read `UI.md` (Win95 dark golden, Verdana, no AA).

Platform notes:
- Native task lists mirror `.saipen/BOARD.md`, never replace it.
- `<project_root>/.saipen/` remains the only project memory/checkpoint area.
  Global USERPERSON lives in the deterministic user-configuration directory
  (`SAIPEN_USER_CONFIG_HOME` override or platform default), never in `.saipen/`
  or `saipen_home`; it cannot bootstrap or become an ancestor project root.
- Prefer file tools over shell redirects -- UTF-8 no BOM.
- CORE.md decides. No rule here overrides it.

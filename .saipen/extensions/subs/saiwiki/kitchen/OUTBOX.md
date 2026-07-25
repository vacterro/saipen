# OUTBOX

## WIKI-001: saitranslate locale freshness audit -- baseline v7.55, current v7.64, drift confirmed minimal
- **status:** reviewed (collected 2026-07-24 -- "minimal" undercounted it: same-session T-168 work found real invalid-UTF-8 corruption in 4 languages too, not just the 3 drift items below; 10/32 languages already fixed, 22 remain. WIKI-002's proposal forwarded to _shared/inbox.md)
- **summary:** 3 drift items found in README.md only (version badge, saicrew bullet, platform list). SECURITY/CONTRIBUTING/CODE_OF_CONDUCT/SPEC: zero drift. Structural integrity of 32+Дед translations verified: 5 files each, correct ISO codes, no orphans. Estonian `ee`→`et` already fixed by T-169.
- **main_project_refs:** [.saipen/saitranslate/kitchen/]
- **critical:** false
- **severity:** P3
- **details:**
  **Freshness baseline:** v7.55.0 (tag 0cd9772). Current: v7.64.0 (d83a53a). Drift span: ~9 versions.

  **Drift items (README.md only):**
  1. `**v7.55.0**` → `**v7.64.0**` version badge (line 15)
  2. New bullet added: "In development -- saicrew: optional bonus layer (extensions/subs/, zero Core changes) for running a multi-agent crew..." (line after "Strict Reliability")
  3. "Claude Code, Gemini, OpenCode, Aider, Antigravity" expanded to "Claude Code, Codex, Gemini, OpenCode, Aider, Antigravity, and any generic `~/.agents/skills` reader (FreeBuff, etc.)" (line 57)

  **Structural audit:**
  - 32 language dirs + Дед: each has exactly 5 files (CODE_OF_CONDUCT_XX, CONTRIBUTING_XX, README_XX, SECURITY_XX, SPEC_XX) -- PASS
  - No orphan flat files at kitchen/ root -- PASS (T-169 already cleaned)
  - No RFC_XX/STYLE_XX out-of-scope leftovers -- PASS (T-169 removed 64 files)
  - Estonian ISO code: `et` (correct) -- PASS (ee→et fixed in T-169)
  - No `en` translation dir (English=source, not translated) -- PASS

  **Recommendation:**
  - Drift is small enough (3 lines in 1 file) that a dedicated `saipen translate` run targeting just README drift across all 32+1 languages would be lightweight
  - The bridge from v7.55 to v7.64 for README is known and bounded -- no fabrication risk (translate.md §2)
  - Maintenance cadence suggestion: either a git hook checking README version badge vs VERSION on commit, or a periodic `WIKI-` ticket to re-scan after every SHIP
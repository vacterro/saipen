# OUTBOX

## WIKI-007: fresh QQ @e4e2b85 (converge L -- post-v2.6.8 sync)
- **status:** ready
- **summary:** FORCE-FRESH regeneration bound to the shipped v2.6.8 tree (e4e2b85). Safety.md carries the T-144 `.. canonicalized+confined` wording and the T-135 blacklist-boundary wording; CLI-Reference.md carries the `--disable-targets` row (15/15 flags) and the reworded `--status` (safe-CLI policy + saved exclusions); Configuration.md documents the `system_targets` key (8/8). Main-project files were NOT touched by this prepare; the payload is what `collect` (qqq) must integrate.
- **critical:** false
- **producer:** saiwiki
- **source_head:** e4e2b852970368a7697c1f72d34a0fd57148865a
- **source_tree_fingerprint:** git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195
- **role_revision:** sha256:54a42475a124ab0f27e83d600a284a9cc54d9668029c4828cfc48512b031df13
- **coverage:**
  pages updated:
    - CLI-Reference.md (`--disable-targets` row, `--status` reworded to safe-CLI-policy + saved exclusions)
    - Configuration.md (`system_targets` key with full-deviation mask semantics)
    - Safety.md (T-144 `..` canonicalized+confined wording, T-135 blacklist boundary)
  pages unchanged (verified current): Home.md, FAQ.md, Build-and-Install.md
  invariants checked against source:
    - CLI flags: every argparse `--flag` present in CLI-Reference table (15/15, incl. --disable-targets)
    - config keys: all 8 load_config() defaults documented in Configuration.md (8/8, incl. system_targets)
- **payload:**
  - payload/pages/CLI-Reference.md
  - payload/pages/Configuration.md
  - payload/pages/Safety.md
  - payload/pages/Home.md
  - payload/pages/FAQ.md
  - payload/pages/Build-and-Install.md
- **verified:**
  - argparse flag cross-check clean (15/15)
  - config-key cross-check clean (8/8)
  - Safety.md `..` canonicalized/confined wording + blacklist boundary present
  - main project files were NOT touched by this prepare (tree clean at produce time)
- **instructions:**
  - On collect (qqq): replace docs/CLI-Reference.md, docs/Configuration.md, docs/Safety.md, docs/Home.md, docs/FAQ.md, docs/Build-and-Install.md with the payload pages, re-run pytest + ruff, commit + tag as a normal Core release. Do not edit the payload to force ready over incomplete coverage -- the 15/15 + 8/8 invariant checks are the gate.

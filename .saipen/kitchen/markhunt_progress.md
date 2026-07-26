# MARKHUNT progress cursor (overwrite-only, not history)

run: 2026-07-26T04:20Z | agent: claude-opus
trigger: user `/goal` -- "избавиться от логических дыр вообще, чтобы не стыдно было показать на reddit"

head_start: c3933df
head_end: c3933df
cursor: done

## vectors (all 5 of phases/markhunt.md's scope categories)

1. HUNT's own six, uncapped -- DONE
   - failing tests: `tools/validate.py` PASS (13 checks), `tests/validate.sh` PASS
   - stale TODO/FIXME/HACK: none in real code (the 3 grep hits are `## TODO`
     heading literals inside the validators themselves)
   - python parse check: all 3 files in `tools/` parse clean
   - silent failures: `|| true` in validate.sh are deliberate `set -e` guards on
     greps that legitimately match nothing, not swallowed errors
   - symmetry gaps: install/uninstall pair present in both languages; export has no
     import counterpart by design (plain untar). FOUND a doc-level asymmetry -> F4
   - dead code / orphans: `extensions/adapters/` all 9 present and referenced from
     README; `tofix/` empty (git doesn't track empty dirs, local-only); 0 broken
     relative markdown links across the entire doc surface
2. Cross-file consistency / doc drift -- DONE
   - GUIDE.md covers all 12 RFC § 1.10 commands (T-153's old concern is satisfied)
   - CONFORMANCE.md: all 34 named fixtures exist on disk
   - RFC phase enum <-> phases/ docs: 16/16 both directions (validator-enforced)
   - FOUND -> F4, F5
3. Security posture -- DONE
   - secret scan across every tracked file: 0 real hits (2 regex false positives on
     Swedish/German prose containing the literal "sk-")
   - `.gitignore` covers .bak / .freebuff / .saipen/recovery / export archives
   - the generated pre-commit hook interpolates only paths derived from `__file__`
     plus one quoted STATE.md field -- no unquoted expansion, no injection surface
   - FOUND -> F3 (author's absolute local path shipped inside a public template)
4. Architectural debt -- DONE
   - FOUND -> F2 (validator is blind to the shipped library subs, which is the root
     cause of F3), F6 (BOARD.md has no size discipline while LOG.md has three,
     although BOOT.md reads both on every single cold start)
5. Familiarity blindness -- DONE
   - the repo's own `.saipen/BOARD.md` has grown to 23.6 KB of closed-ticket prose
     and nobody registers it, because it's "just our board" -- it is the first file
     a visitor opens and the second file every cold agent loads (F6)
   - `bootstrap/uninstall.*` exists and works but is invisible from the front door,
     normalized because the maintainer never needs to run it (F4)

## surface swept

saipen/{RFC,BOOT,SKILL,STYLE,CONFORMANCE,UI}.md, saipen/phases/*.md (16),
tools/*.py (3), tests/validate.{sh,ps1}, tests/scenarios/*/README.md,
bootstrap/*.{sh,ps1,bat} (8), extensions/{templates,schemas,subs,adapters}/**,
README.md, GUIDE.md, SPEC.md, SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md,
.gitignore, .github/**, plus a whole-tracked-tree grep for secrets and for absolute
machine paths.
Out of scope this pass: guides/GUIDE_XX.md (33 hand-maintained translations),
.saipen/saitranslate/** (T-168's own surface), .saipen/logs/** (sealed, immutable),
.saipen/recovery/** (gitignored backups).

## findings

findings: 6
tickets written: 4 -- grouped per this phase's own grouping rule, each naming its count:
  T-178 x1  F1  inject.sh destroys the pristine backup on re-run (reproduced live)
  T-179 x2  F2+F3  library subs unvalidated -> shipped example carries a dead
                   machine-specific saipen_home (root cause + symptom, one fix)
  T-180 x2  F4+F5  front-door doc gaps: no uninstall path, 2 commands unlisted
  T-181 x1  F6  BOARD.md unbounded while LOG.md is capped, both read at cold start

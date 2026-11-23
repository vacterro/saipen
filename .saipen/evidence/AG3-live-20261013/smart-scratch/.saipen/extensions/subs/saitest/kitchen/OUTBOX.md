# OUTBOX

## ST-001: dead i18n keys — REPRODUCED
- **status:** reviewed
- **summary:** 4 keys in DEFAULT_STRINGS (en/ru/et) are never referenced in source — dead from removed Find-New-Junk scanner (T-043)
- **main_project_refs:** [_SMART_VAC_CLEANER.py, strings/ru.json, strings/et.json]
- **critical:** false
- **producer:** saitest
- **source_head:** 41cee44159ef4e6ecbcb311ffd63fcbcf86641b6
- **verdict:** REPRODUCED
- **scenario_family:** symmetry (i18n keys defined vs used) + adversarial-content family-7 adjacency (leftover dead surface)
- **minimal_input:**
  ```python
  import re
  from pathlib import Path
  import _SMART_VAC_CLEANER as vac
  src = Path(vac.__file__).read_text(encoding="utf-8")
  refs = set(re.findall(r'self\.T\[["\'](\w+)["\']\]', src))
  dead = set(vac.DEFAULT_STRINGS) - refs
  assert not dead, dead
  ```
- **command:** `python -c "<above>"` (run from repo root)
- **observed:** `AssertionError: {'find_new_junk', 'junk_window_title', 'scanning', 'nothing_found'}`
- **bound:** 1 file, 1 regex pass, < 1 s
- **details:**
  T-043 removed the Find-New-Junk GUI button but left its 4 i18n keys (`find_new_junk`, `junk_window_title`, `scanning`, `nothing_found`) in `DEFAULT_STRINGS` and both `strings/ru.json` + `strings/et.json`. No `self.T[...]` reference survives. Cross-checked: `T['window_title']` IS used (line 2225), so window_title is NOT dead. The registered regression guard: a symmetry test asserting `DEFAULT_STRINGS` keys ⊆ source refs and ru/et key-sets == DEFAULT_STRINGS key-set.

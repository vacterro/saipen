<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: new engine modules, CLI refusal codes, printed commands, subprocess calls, declared core-unit family, SHIP evidence
trigger: adding a module under tools/saipen_engine, a refusal code, a string literal that starts with the command word, or a subprocess call, before paying for the declared family
status: active
evidence: T-1658, .saipen/evidence/core-unit/2872ccee763faa9f-20261007T095004Z.json, tools/test_refusal_registry.py, tools/test_canonical_command_reachability.py, tools/test_subprocess_utf8.py
supersedes: none

# Ask the whole-source contracts before the declared family

Run `python -B -m unittest test_refusal_registry test_canonical_command_reachability test_subprocess_utf8` in `tools/` before the declared family whenever a change adds engine code, because a ticket's own module and its neighbours never ask the contracts every production source must meet, and the family takes about twenty minutes to say so.

Why:
T-1658 passed its own module, 401 neighbouring tests, ruff and the validator, and the family then went red on four tests of that delta alone. Three contracts were unmet. A `{"ok": False, "code": ...}` literal must carry a code registered in REGISTRY `error_codes`; reuse a registered code and name the cause in another field, since registering costs bytes the `command_resolution` budget does not have. A string literal in the engine that starts with the command word must classify as one canonical command after placeholder substitution, so a usage line is a list of runnable forms, never alternatives joined in one string. A subprocess call must name its keyword arguments, never spread a computed mapping. The three modules above take under a minute and caught all four reds; every module that reads the whole production source (found by `grep -l 'rglob(\|ast\.parse(' tools/test_*.py`, 74 modules) takes about seventeen minutes and found nothing more.

# RAPORT — SAIPEN guard canonical-line token bound (12) and quote bound

- **Report id:** RAPORT-SAIPEN-CANONICAL-LINE-BOUNDS-20260918
- **Date:** 2026-09-18
- **Reporter:** agent `opencode`, host opencode (`SAIFREN`)
- **Reporter project:** `V:\___VAC\__K\__CODE\_PY\_LIMISAW`
- **Protocol version:** 8.0.1
- **Bound saipen_home:** `C:\Users\vac34\AppData\Local\saipen\scheduled-source`
- **Protocol home:** `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
- **Defect class:** guard-canonical-classification / token-bound + quote-bound
- **Severity:** P2
- **Origin:** improve cycle `imp-vacterro-limisaw-20260918-2` RUN-1/IMP-001 (CONFIRMED -> T-54)

## TL;DR

`_saipen_cli_tokens` abandons the canonical `saipen <verb>` grammar in two
ordinary, documented cases, after which the line is classified `action="shell"`
and refused `NO_ACTIVE_WORK` on an idle project:

1. **Token bound** — `_SAIPEN_MAX_TOKENS = 12` (guard_events.py:200,
   guard_events.py:1102). The documented `saipen improve sweep` grammar is
   already 12 tokens before any global option, so appending the documented
   `--json` (13) is refused.
2. **Quote bound** — `_SHELL_SYNTAX_CHARS` (guard_events.py:184) contains `"`
   and `'`, so any quoted argument drops the whole line from the grammar.

## Reproduction

```
saipen status x1 x2 x3 x4 x5 x6 x7 x8 x9 x10        (12 tokens)
 -> admitted; engine answers VALIDATION_FAILED
saipen status x1 x2 x3 x4 x5 x6 x7 x8 x9 x10 x11    (13 tokens)
 -> SAIPEN_GUARD_REFUSAL: NO_ACTIVE_WORK  (guard; engine never reached)

saipen improve sweep <cycle> RUN-1/IMP-001 CONFIRMED --ticket T-53 \
  --report opencode-01/saipen_improve_SAIPEN.md --reproduced y --json
 -> SAIPEN_GUARD_REFUSAL: NO_ACTIVE_WORK
 (same line without --json: 12 tokens -> admitted, disposition committed)

saipen source disp SRC-011 R001 VERIFIED --evidence ".saipen/evidence/<path>"
 -> SAIPEN_GUARD_REFUSAL: PROTECTED_CANONICAL_NAMESPACE
saipen source status "SRC-011" --json
 -> SAIPEN_GUARD_REFUSAL: NO_ACTIVE_WORK
 (both admitted when the differing argument is unquoted)
```

## Root cause

- `guard_events.py:200` `_SAIPEN_MAX_TOKENS = 12`; `guard_events.py:1102` the
  bound.
- `guard_events.py:184` `_SHELL_SYNTAX_CHARS` includes `"` and `'`; consumed at
  `guard_events.py:1093`.
- `guard_events.py:1304` fallthrough `action = "shell"`.
- `admission.py:778-786` `NO_ACTIVE_WORK` on an idle project.

## Impact

- Documented canonical commands with their own required arguments are unreachable
  through the guard on an idle project; the model must discover the unquoted,
  shortened spelling by trial.
- Cross-project; only the shared engine can fix it.

## Repair candidates

1. Exclude global options from the token count, or raise the bound for known
   canonical verbs.
2. Admit shell-quoted argument tokens within the canonical `saipen` grammar.
3. Never fall through a line whose first token is exactly `saipen` into
   `action="shell"` while a canonical verb matches; emit a grammar diagnostic.

## Related

`SAI-DEFECT-20260918-routeless-finish-source-gate`,
`SAI-DEFECT-20260917-wintage-guard-filepath`,
`SAI-DEFECT-20260918-guard-readonly-probe-gap` (protocol_incidents/inbox);
`RAPORT-SAIPEN-GUARD-20260917` (home).

— end of report —

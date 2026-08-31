# SAIPEN Command Surface

This document owns command semantics. `REGISTRY.json` owns the closed machine
facts consumed by the engine; no runtime parses this prose. CORE owns only the
global authority and deterministic priority rules.

## Shortcut table

<!-- RULE-OWNER: CMD-ROUTING-01 -->

| Input | Routes to | Rule ref | Notes |
|-------|-----------|-----------------|-------|
| `gg` | `saipen goal` | CMD-ROUTING-01 | New goal; payload is the objective |
| `hh` | `saipen hunt` | CMD-ROUTING-01 | Autonomous defect/improvement scan |
| `ff` | `saipen focus` | CMD-ROUTING-01 | Read-only closer inspection |
| `xx` | `saipen cut` | CMD-ROUTING-01 | `xx confirm <CUT-ID>` authorizes the planned mutation |
| `vv` | `saipen build` | CMD-ROUTING-01 | Bounded foreground Work |
| `zz` | `saipen undo` | CMD-ROUTING-01 | Restore the last safe milestone |
| `cc` | `saipen continue` | CMD-CONTINUE-01 | Resume the active intent through deterministic routing |
| `ccc` | `saipen continue` | CMD-CONTINUE-01 | Converge target `ship`, then refresh stages J-M |
| `ss` | `saipen stop` | CMD-ROUTING-01 | Checkpoint and return control |
| `sss` | `saipen status` | CMD-ROUTING-01 | Read-only status |
| `dd` | `saipen plan` | CMD-ROUTING-01 | Plan; payload supplies user items |
| `aa` | `saipen markhunt` | CMD-ROUTING-01 | Dry audit; records, never fixes |
| `qq` | `saipen prepare saiwiki` | CMD-ROUTING-01 | Force-fresh wiki package |
| `qqq` | `saipen collect saiwiki` | CMD-ROUTING-01 | Integrate ready wiki package, then ship |
| `ee` | `saipen prepare saitranslate` | CMD-ROUTING-01 | Force-fresh translation package |
| `eee` | `saipen collect saitranslate` | CMD-ROUTING-01 | Integrate ready translation package, then ship |
| `pp` | `saipen sub spawn saipython` | CMD-ROUTING-01 | Python tooling role |
| `tt` | `saipen test` | CMD-ROUTING-01 | Run the declared suite, read-only |
| `sc` | `saipen crew` | CMD-ROUTING-01 | Serial full-platoon convergence circuit |

## Canonical commands (non-shortcut)

| Command | Phase / Action | Rule ID |
|---------|---------------|---------|
| `saipen set` | INIT | CMD-ROUTING-01 |
| `saipen init` | INIT | CMD-ROUTING-01 |
| `saipen continue` | router | CMD-CONTINUE-01 |
| `saipen goal <text>` | PLAN | CMD-ROUTING-01 |
| `saipen clean` | CLEAN | CMD-ROUTING-01 |
| `saipen translate` | TRANSLATE | CMD-ROUTING-01 |
| `saipen validate` | VALIDATE | CMD-ROUTING-01 |
| `saipen prepare <producer>` | PREPARE | CMD-ROUTING-01 |
| `saipen collect <producer>` | router | CMD-ROUTING-01 |
| `saipen ship` | SHIP | CMD-ROUTING-01 |
| `saipen push` | SHIP | CMD-ROUTING-01 |
| `saipen improve [action]` | meta | CMD-CONTINUE-01 |
| `saipen status` | read-only | CMD-ROUTING-01 |
| `saipen runtime` | read-only | CMD-ROUTING-01 |
| `saipen source` | intake | CMD-ROUTING-01 |
| `saipen userperson` | meta | CMD-ROUTING-01 |
| `saipen sub <verb> <name>` | sub | CMD-ROUTING-01 |

## Compound parsing

<!-- RULE-OWNER: CMD-COMPOUND-01 -->

- Segments separated by ` + ` (space-plus-space) or newlines.
- Quoted payload (`"..."`) is opaque and never split.
- STOP_ON_FAILURE by default: a later segment after an earlier REFUSED/FAILED
  becomes NOT_RUN unless provably independent.
- `saipen push + build ccc` executes both segments in order.
- `hush <task>` applies execution policy `EXEC-HUSH-01`; `hush` is syntax,
  never a lifecycle or style owner.

## Unicode twin normalization

Cyrillic shortcuts are the same as Latin. Codepoint substitution:
`а→a е→e о→o р→p с→c у→y х→x`. Latin `ss`/`sss` have no Cyrillic twin.
Cyrillic `сс` → Latin `cc` (continue), never `[ss]` (stop).

## Continue→improve fallthrough

<!-- RULE-OWNER: CMD-CONTINUE-01 -->

`saipen continue` falls through to `saipen improve` ONCE after recovery,
blocked, queued, and required-follow-up routing is exhausted. An already-active
prepared cycle is resumed, never duplicated. A completed/archived cycle allows
fresh discovery. No unbounded improve carousel.

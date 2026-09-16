# T-1379 -- the ticket the entry command creates could not be finished

## What was measured

2026-09-17, installed generation `gen-sha256:f3d2104a…`, the nine-condition
field matrix. Two independent sessions drove the whole protocol chain, edited
their target file, and then looped on the same refusal:

```
source coverage gate for T-1: {'ok': False, 'code': 'SOURCE_UNRESOLVED',
 'receipt': 'SRC-001', 'work': 'T-1',
 'coverage': {'receipt': 'SRC-001', 'requirements': 0, 'actionable': 0,
              'terminal': 0, 'dispositions': {}, 'unresolved': []}}
```

`safety_valve` (SRC-001 / T-1) and `already_done` (SRC-002 / T-8301). The
refusals were read from OpenCode's own session store, not from the models'
prose.

## Why it could never pass

* `intake.capture` writes the Contract with `"clauses": {}`.
* `coverage_complete` requires `actionable > 0`.
* `work_closure_gate` therefore answers `SOURCE_UNRESOLVED` for that receipt
  for the rest of its life, and `ticket done` refuses.
* The two functions that could have changed it — `intake.add_requirement` and
  `intake.set_disposition` — have no CLI surface at all, so nothing a field
  session can type leads anywhere.

The same empty-contract hole is on this repository's own `SRC-046` and
`SRC-051`: the documents that define T-1367's acceptance derive zero clauses,
so their text constrains nothing.

## The fix

`REQUEST-CLAUSE-01` (SOURCES.md, registered in REGISTRY.json). A request is not
zero requirements — it is exactly one, the text the operator wrote. At closure,
each linked `user_instruction` receipt gets that clause if it has none, and it
is settled from the SAME verification evidence the Work gate already demands:
one proof, not two.

Guardrails, each with a control:

* nothing is settled when the Work has no verification evidence;
* a clause an agent DERIVED is never settled from here — it keeps the gate red
  until that agent settles it with its own evidence;
* "the request's own clause" is read from bytes: its text equals the request
  body's `## Request` section (`is_request_clause`), so it cannot be forged by
  writing a different clause.

## Evidence

| file | what it is |
|---|---|
| `green-post-fix.txt` | 7 controls, current bytes |
| `red_subject.py` | copies the tree, reverts ONLY `discharge_request_clauses`, runs the byte-identical oracle |
| `red-final-oracle-vs-pre-fix-subject.txt` | that run: the closure classes go red |
| `verify-adjacent.txt` | focused + intake/source/closure/retirement families |
| `verify-validate.txt` | `tools/validate.py` |

The canonical chain now closes through the CLI alone:

```
saipen start '<task>'
saipen transition BUILD T-1 'scout done'
saipen checkpoint RUN T-1 'build -> …'
saipen transition VERIFY T-1 'build done'
saipen checkpoint RUN T-1 'verify -> PASS [target: T-1] conf: high -- …'
saipen transition REVIEW T-1 'verify green'
saipen transition SHIP T-1 'review passed'
saipen ticket done T-1 --closure-mode own_patch   ->  FINISHED
```

# SubSaipen

Read-only scoped workers and producers. Extension, not Core (CORE § 1.9).

## Protocol

Each subSaipen lives in `.saipen/extensions/subs/<name>/` with:
- STATE.md (own phase/task/next_action, mode: read-only)
- BOARD.md (own tickets: SUB-###)
- LOG.md (own event graph: S-###)
- kitchen/OUTBOX.md (findings for main agent)

**Key rules:**
- Read-only: never write to main project. Findings only via OUTBOX.
- One write path: main agent collects OUTBOX -> creates tickets -> works them.
- OUTBOX validated by `tools/validate.py`: needs status/summary/critical on `ready`.
- Patch support: a fixer-type sub (saipython) emits patches with `base_head:` + `verified:`.
- **Backpressure** (v7.98.0+): sub pauses own work if >10 `ready` entries pile up unreviewed.
- **Boundary check on collect** (v7.98.0+): main agent runs `git status` against whole tree before folding findings. A confused sub that wrote outside its folder gets caught.

## Active sub-agents

| Agent | Role | Status |
|---|---|---|
| **saiwiki** | Wiki producer | FORCE-FRESH maintains all 9 wiki pages. W-033 prepared against the current v7.226.0 source tree; 256 scenarios reverified by canonical ID digest. |
| **saihunt** | HUNT sweeper | Runs the six-signal audit and packages reproducible findings; latest crew sweep isolated the final locale-parity gate before Core cleared it. |
| **saitest** | Independent verifier | Reproduces another role's claims with the declared harness; latest crew run independently pinned each gate before intake. |
| **saiui** | UI fixer | First-class built-in fixer SubSaipen for UI work (v7.201.0): Vintage Golden palette, projection-driven |
| **saitranslate** | Translation producer | Builds complete locale packages in its own namespace. The current v7.226.0 parity package refreshed all 32 kitchen locale badges and was integrated by Core. |
| **saipython** | Python fixer | Fixer-type: emits tested kitchen patches. PY-7/PY-8 cleared 89 Ruff diagnostics plus the formatting-sensitive admission check; PY-9 verified the current Python surface clean. |

**Charters are machine-readable** (v7.213.0): every shipped sai*.md opens with a YAML block — role_kind, write_scope, trigger, collect_policy, done_condition, freshness_inputs, output_contract, role_revision. **Role freshness is recorded and compared** (v7.214.0): `role_revision` is derived from the charter, recorded at spawn/adopt and in every ready OUTBOX package; a mismatch makes the package stale, never collected. `saipen sub sync` refreshes charters and never a live sub's STATE/BOARD/LOG/kitchen.

## Spawning

```
> saipen sub spawn saiwiki
> saipen sub spawn saihunt
> saipen sub spawn saipython
```

A bare sub name — `saiwiki`, `saihunt`, `saitranslate`, anything `sai*` — is a role-adopt command: the agent spawns it if missing, becomes it, starts its own cycle. No second command needed. `saipen sub sync` refreshes the shared protocol files (PROTOCOL/README/crew/TEMPLATE) from the SAIPEN home without touching any sub's own history.

The main agent stays the single writer. Sub-agents research and report. No write races by construction.

## Producer prepare parallelism (v7.226.0)

PRODUCER roles (`saitranslate`, `saiwiki`) may prepare in parallel without creating a second Core writer. Each namespace has its own `ProducerLock`, monotonic epoch, non-READY staging generations, and authenticated READY records. A package binds source head/tree, charter revision, exact read/write dependencies, payload bytes, requested scope, and deterministic package identity. Same-role writers serialize; cross-role writers may overlap. Core alone collects, integrates, dispositions, commits, tags, and pushes. Integration is CURRENT when the full identity matches, COMPATIBLE_DRIFT when declared dependencies still hash identically, and STALE only when a declared input or write precondition moved.

## Collecting OUTBOX

```
Main agent: reads <sub>/kitchen/OUTBOX.md
            validates package shape, policy, freshness, and boundary
            creates one Core review-hypothesis ticket
            journals ticket + LOG + MANIFEST linkage atomically
            leaves OUTBOX ready until Core disposition
            logs: RUN: collect <name>-### -> T-###
```

INTAKE is not REVIEW. Collection leaves the package `ready` and derives `REVIEW_PENDING`; only `saipen sub dispose` marks it `reviewed` after the linked Core ticket reaches a terminal verdict. Structured receipt + MANIFEST identity provide dedup; prose alone never proves collection.

Every eligible finding becomes an ordinary Core review hypothesis. `critical` and severity affect priority, never truth status or the intake path. Explicit producers are skipped by autonomous sub collection and consumed only by their named `saipen collect <producer>` command.

## Key distinction: read-only scope vs capability (v7.111.0)

`mode: read-only` means two different things:

- **Core read-only** = *capability* lock: filesystem write unavailable, bans all 7 phases whose product is a file write (INIT, PLAN, ADD, BUILD, SHIP, CLEAN, TRANSLATE).
- **SubSaipen read-only** = *scope* lock: writes its own STATE/BOARD/LOG/kitchen freely, banned from shared tree. Only 4 phases banned (BUILD, SHIP, CLEAN, TRANSLATE). PLAN and ADD are reachable and expected — sub plans own backlog.

This means `HUNT -> DONE` is legal for a subSaipen (v7.111.0): a reporting sub's deliverable is its OUTBOX, the "add" step happens during main-agent collect. `saihunt` had been in that state truthfully since its first sweep.

Sub STATE.md now validated against Core's full rule set: 9th required field, transition legality, ISO-8601 `updated`, command vocabulary (v7.111.0).

## Validation guards (v7.98.0+)

`tools/validate.py` enforces these subSaipen invariants on every invocation:

- **Sub next_action format**: every sub STATE.md `next_action` must follow CORE § 1.2 prefix rules — `WAIT:` with category token, `RESUME:`, `PHASE`, or `saipen` command. Bare prose rejected.
- **Self-transition enum check**: if sub's `transition_from` equals its `phase`, the phase must be one of 16 known enum values.
- **Adapter path existence**: every `saipen/` path in `extensions/adapters/*.md` must be a real file.
- **Liveness check** (v7.99.0): sub with open tickets, zero done, empty OUTBOX WARNs as never-run. `ready` entries WARN as findings waiting on `collect`.
- **TEMPLATE validated** (v7.101.0): the shipped TEMPLATE/STATE.md was previously exempted by name — hid a prefix-less `next_action`. Every spawned sub was born non-conformant. Fixed.
- **Sub STATE parity** (v7.111.0): sub STATE.md held to Core's rules — 9th required field, transition table, ISO-8601 `updated`, command vocabulary. Was previously checking a fraction.

saipython (fixer-type) also has:
- **Capability gate**: missing Python/pytest/ruff on host -> degrades to finding-only (saihunt-style), never fakes a `verified:` result.
- **Scope discipline**: one fix per patch, minimal diff. P2/P3 only — anything large or architectural goes to `critical` finding for the main agent.

## ДED Voice

> "Под-агенты? Как бригада. Один ищет баги, второй чинит Python, третий переводит документацию. Главный агент собирает результаты и делает тикеты. Никто не мешает друг другу. Каждый в своей песочнице. И никаких 'я случайно переписал твой файл'. Потому что читать можно всем, писать — только одному."

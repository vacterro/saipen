# FUTURE GATE — GREENFIELD BIRTH HAS NO MECHANICAL OPERATION

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Recorded: 2026-09-17 by a claude session binding the greenfield project
`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\__SAIMAIL__`
(lineage `lineage-3172dbca95fc4945955bdee3acff8d75`), reproduced live against
installed protocol `8.0.1` and `_SAIPEN/tools/saipen.py` at
`source_head 10a298979f9c8050ff82551d5870339350b9c1a9`.

This document records an externally reproduced contract/engine divergence. It
is not a claim that anything here is fixed, and it must not be cited as
evidence for any coverage disposition. Do not implement it while an active
ticket holds this repository DOING seat.

## DEFECT A — `saipen init` / `saipen set` ARE DECLARED BUT UNREACHABLE (P1)

Birth is the only lifecycle event with no canonical operation. The command
whose entire job is to create `.saipen/` refuses because `.saipen/` does not
exist yet.

Declared:

- `saipen/REGISTRY.json` -> `commands.saipen` contains `"init"` and `"set"`.
- `saipen/COMMANDS.md` lines 37-38: `saipen set` -> INIT, `saipen init` -> INIT,
  both under `CMD-ROUTING-01`.
- `saipen/BOOT.md` step 2: "A root without `.saipen/` routes to INIT."
- The user-facing global instruction in this installation advertises
  `saipen set` as the entry point for a new project.

Engine, reproduced on an empty project root:

```
$ python tools/saipen.py init --json          # cwd = the new root
  "code": "NOT_SAIPEN_PROJECT",
  "detail": "cwd has no owning .saipen/; refusing to guess or create one. Run from the intended project or pass --project-root PATH"

$ python tools/saipen.py init --json --project-root "V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\__SAIMAIL__"
  "code": "PROJECT_BINDING_INVALID",
  "detail": "explicit --project-root has no .saipen/ directory: V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\__SAIMAIL__"
```

`saipen set` returns the same pair. The `--help` usage string exposes no `init`
and no `set` verb at all, so the refusal is the binding guard firing ahead of a
dispatch target that does not exist. Following the advice inside the first
detail (`pass --project-root PATH`) lands on the second refusal: the guard
names the exact flag that cannot help.

This is the `SRC-053` WEAK-MODEL UX failure verbatim — the engine should return
one exact operation, and here it returns two refusals and no route. A weak seat
at this point either invents `.saipen/` freehand or asks the user to do the
protocol job.

## DEFECT B — `phases/init.md` PRIMARY BOOTSTRAP PATH POINTS AT MISSING FILES (P2)

`saipen/phases/init.md`, Bootstrap, first sentence:

> Copy `extensions/templates/STATE.md`, `BOARD.md`, and `LOG.md` from the bound
> SAIPEN home; do not freehand schemas.

Reproduced:

```
$ find _SAIPEN/saipen -iname "*template*"                       # 0 hits
$ find <installed protocol snapshot> -iname "*template*"        # 0 hits
$ ls _SAIPEN/saipen/extensions/templates
  No such file or directory
```

The installed snapshot has no `extensions/` directory at all. Every greenfield
project is therefore born through the "If templates are unavailable" fallback —
freehand — which is the exact thing the same paragraph forbids. The nearest
skeleton in the tree is a test fixture, `tools/audit_floor.py:41` `GOOD_STATE`,
and it is stale for this purpose: `schema_version: 1`, no `style_contract`, no
`saipen_home`. A seat that copies the only skeleton it can find writes legacy
state.

## DEFECT C — DUPLICATE MEMBER IN A CLOSED SET (P3)

`REGISTRY.json` -> `commands.saipen` lists `validate` twice (51 entries, 50
distinct). A machine-owned closed set with a duplicate member is a hygiene
defect wherever that list is length-checked or diffed.

## WHAT A CORRECT HAND-BIRTH LOOKS LIKE

Written by hand this session from `CORE.md` 1.2 + `REGISTRY.json.state` +
`STYLE.md`, then proven:

```
$ python tools/saipen.py validate --json --project-root <__SAIMAIL__>
  "ok": true, "code": "VALID", "error_count": 0

$ python tools/saipen.py continue --json --project-root <__SAIMAIL__>
  "ok": true, "action": "WAIT: init -- provide the first project goal or raw backlog", "reason": "wait"
```

STATE carried `phase: PLAN`, `task: none`, the `WAIT: init` next_action
(`init` is a registry `wait_categories` member), `blocker: none`,
`transition_from: INIT`, `saipen_version: 8`, `schema_version: 3`,
`style_contract: ded-4ae736e4`, absolute `saipen_home`, `agent: claude`,
`mode: full`, `execution_intent: normal`, UTC `updated`, and no `last_event`
(no history yet). BOARD carried the four required headings and no tickets; LOG
was `# Log` and empty; `IDENTITY.md` carried a fresh `project_lineage`.

That shape is what a birth verb should emit. Deriving it took a full protocol
read; the point of this gate is that it should have taken one command.

## BOUNDED FOLLOW-UP OPTION

Three independent, separately red-controlled changes:

1. Admit `init`/`set` in the binding guard as the single birth-exempt verb, and
   only with an explicit root: no `.saipen/` plus explicit `--project-root`
   -> create the canonical memory, write the first journaled event, return
   `STARTED` with `WAIT: init`. Every other verb keeps refusing exactly as now.
2. Either ship `saipen/extensions/templates/{STATE,BOARD,LOG}.md` at the current
   schema so the `init.md` copy path is real, or delete that sentence and name
   the birth verb instead. A routinely loaded phase document must not point at
   a path that does not ship.
3. De-duplicate `validate` in `commands.saipen`.

Required hostile controls:

- On an empty directory, `saipen init --project-root <dir>` creates `.saipen/`
  and a following `saipen validate` returns `VALID`; the red control proves the
  pre-fix code returns `PROJECT_BINDING_INVALID`.
- Guard non-weakening: every non-birth verb against a root without `.saipen/`
  still returns `PROJECT_BINDING_INVALID` / `NOT_SAIPEN_PROJECT`; a bare cwd
  with no explicit root still refuses to guess.
- Idempotence: `init` against a root that already carries `IDENTITY.md` refuses
  instead of minting a second lineage.
- Template control: each path named by `init.md` exists in the installed tree;
  the red control on the current install finds none.

NON-GOALS: do not let `init` create memory from a bare cwd (the "refusing to
guess" rule is correct and stays); do not weaken `PROJECT_BINDING_INVALID` for
any other verb; do not promote the audit fixture into the shipped template
without first lifting it to the current schema.

## ADJACENT OBSERVATION — EMPTY NAMED SOURCE (NOT A PROVEN DEFECT)

The originating session was told to read `idea.md`, and `idea.md` measured 0
bytes (`wc -c` -> `0`). The binding refusals above fired first, so no source
path was exercised and nothing here is proven. Recorded only because the shape
is the same weak-model trap: a named source artifact carrying no content has no
deterministic route, and the cheapest wrong move available to a weak seat is to
invent the content. If triage finds this interesting, the question for
`SOURCES.md` is whether a zero-content receipt should refuse with a `WAIT:`
naming the empty path instead of being captured as a valid source.

## ORIGINATING MISSION

Greenfield bind of `__SAIMAIL__` on 2026-09-17. The user asked for a new
project organized so that it could later interlock with SAIPEN; the interlock
seam itself turned out to be the unmechanized part. The fix belongs to the
protocol tree, which is a different repository than the bound project, so this
record is the established cross-project handoff rather than an edit of
unrelated protocol code.

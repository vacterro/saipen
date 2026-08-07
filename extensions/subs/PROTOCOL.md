# SubSaipen Protocol

Isolated, read-only agents that research the main project in parallel and
hand back structured findings -- never a second write-path into the
project. Extension, not Core (CORE.md §1.9): nothing here is read by the
SAIPEN home on its own behalf, and it never relaxes what Core requires.

## 0. Root path

Single root: **`.saipen/extensions/subs/`**, inside the project's `.saipen/` (v7.35.0; a project bootstrapped before then MAY still carry this at root-level `extensions/subs/` -- equivalent, migrate when convenient).

```
.saipen/extensions/subs/
├── MANIFEST.md            # list of active subSaipen names
├── PROTOCOL.md             # this file
├── _shared/
│   └── inbox.md            # non-critical findings, reviewed next round
├── TEMPLATE/                # copy this to start a new subSaipen
│   ├── STATE.md
│   ├── BOARD.md
│   ├── LOG.md
│   └── kitchen/
│       └── OUTBOX.md
└── <name>/                  # one folder per subSaipen (saiwiki, saihunt, ...)
    ├── STATE.md
    ├── BOARD.md
    ├── LOG.md
    └── kitchen/
        ├── OUTBOX.md
        └── _*.md            # scratch, ignored by the main agent
```

## 1. What a subSaipen is

A subSaipen is a normal SAIPEN instance -- same `STATE.md`/`BOARD.md`/`LOG.md`
shape, same `phase` enum (CORE.md §1.6), same LOG skeleton (CORE.md §1.2) -- living
in its own folder instead of the project's `.saipen/`, permanently locked to
`mode: read-only`. No separate state machine, no lifecycle field: CORE.md §1.3
already defines the behavior wanted here -- "the agent MAY still read,
analyze, and report; it advises, it does not act" -- MUST NOT touch any file
outside its own `.saipen/extensions/subs/<name>/`.

**The value is reused; the contract is NOT identical, and saying it was cost
this protocol two contradicting phase bans.** Core's `read-only` is a
*capability* lock: filesystem write is unavailable, so CORE.md §1.3 bans all
seven phases whose work product is a file write -- including `PLAN` (it writes
tickets) and `ADD`. A subSaipen's `read-only` is a *scope* lock: it writes its
own `STATE.md`, `BOARD.md`, `LOG.md` and `kitchen/` freely -- § 8's fixer even
edits copies in `kitchen/pen/` -- and is forbidden only from the shared tree.
So the ban here is the phases whose work product lands OUTSIDE its own folder:

> **A subSaipen MUST NOT transition to `BUILD`, `SHIP`, `CLEAN` or
> `TRANSLATE`.** Four, not CORE.md §1.3's seven. `PLAN` and `ADD` are reachable
> and expected -- § 5's backpressure note and `TEMPLATE/STATE.md`'s default
> `next_action` both have a subSaipen planning its own backlog, which is
> unreachable under the capability reading. `INIT` is moot: `saipen sub spawn`
> creates the folder, the subSaipen never bootstraps itself.

The two lists were always different in `tools/validate.py` and identical in
this sentence, which is drift in the worst direction -- the document said the
stricter thing and the tool did the workable thing, so a conformant reader and
a conformant run disagreed about `PLAN`. Both lists are now named constants and
the drift detector compares them against this paragraph.

**One transition-table addition, for the same reason.** CORE.md §1.6 routes
`HUNT` to `ADD`/`PLAN`/`SCOUT`/`BLOCKED`, because for Core a clean sweep still
has to decide what work it creates. A reporting subSaipen's deliverable is its
OUTBOX, not tickets: the "add" step happens in the MAIN project, during
`collect` (§ 4). **`HUNT -> DONE` is therefore legal for a subSaipen** whose
findings went to `kitchen/OUTBOX.md`, and only for a subSaipen. `saihunt` had
been sitting in exactly that state, truthfully, since its first sweep.

**Enforcement is procedural, same footing as CORE.md §1.1's destructive-op
rule** -- there is no universal technical lock. The subSaipen's own
instructions (this file) are the contract; if the platform running it
offers real isolation (a separate working directory, a git worktree scoped
to `.saipen/extensions/subs/<name>/`), use it. Don't claim automated enforcement
that isn't there.

**Your own `BOARD.md` uses the checkbox ticket shape, never the OUTBOX
shape.** "Same STATE.md/BOARD.md/LOG.md shape" above means exactly CORE.md
§ 1.2's board shape -- read it there; this file states only the one
sub-specific delta, which is that your own ID prefix (§ 3) stands in place
of `T-###`. Everything else about the line (checkbox states, the
`| field: value` tail, the four section headings, escaping) is Core's rule
unchanged, and is deliberately not re-described here:
```markdown
## TODO
- [ ] HUNT-001 short description of what to check
## DONE
- [x] HUNT-000 already finished, checkbox closed
```
This is a *different* shape from `OUTBOX.md`'s bold-field markdown (§ 2) --
the board is where you track your own work-in-progress; the OUTBOX is the
finished deliverable leaving through the one door. Don't reuse one shape
for the other just because `TEMPLATE/BOARD.md` ships empty (that emptiness
is a starting point, not license to invent a shape).

## 2. OUTBOX format

File: `<name>/kitchen/OUTBOX.md`. The only channel back to the main agent.

```markdown
# OUTBOX

## WIKI-001: short description
- **status:** ready | draft | blocked | reviewed | stale
- **summary:** one line, what was found or produced
- **main_project_refs:** [src/foo.py, ...]
- **critical:** true | false
- **severity:** P0 | P1 | P2 (optional -- matches `phases/review.md`'s own taxonomy; helps the main agent pick what to collect first when several are `critical: true`)
- **producer:** saiwiki (required for a complete package consumed by Core `saipen collect <producer>`)
- **source_head:** full Git HEAD or `no-git` (required for a complete package)
- **coverage:** exact surfaces completed (required for a complete package)
- **payload:** exact files/artifacts to integrate (required for a complete package)
- **verified:** checks already run and their results (required for a complete package)
- **instructions:** ordered integration steps (required for a complete package)
- **details:**
  What was found, what's proposed, why it matters.
```

| Status | Meaning |
|---|---|
| `ready` | Done, main agent may act on it |
| `draft` | Still in progress, main agent ignores |
| `blocked` | Waiting on something external, reason in `details` -- **and this is also how a subSaipen says "I do not have enough information", which is the one case it will otherwise get wrong** (see below) |
| `reviewed` | Collected already (§ 4) -- kept as history, not deleted; safe to leave, gets swept whenever `saipen sub clean` or a `HUNT` pass (`phases/hunt.md`) touches this subSaipen's `kitchen/` like any other stale content |
| `stale` | The finding no longer matches HEAD -- a renamed file, a bug already fixed by another route (§ 4). Collect skips it rather than ticketing a ghost. This row was missing from this table until v7.101.0 while § 4 and § 9 both instructed agents to write it, and both `outbox.schema.json` and `tools/validate.py` already accepted it |

`critical: true` = bug, broken behavior, data loss, security issue.
`critical: false` = improvement, docs, refactor, cosmetic.

**Not enough information is a `blocked` entry, never a guess.** CORE.md §1.11
requires a Core agent short of a fact to stop and write a `WAIT:` naming it.
A subSaipen cannot do that -- it has no `WAIT:` any human reads; its own
`STATE.md` is nobody's dashboard, and its single door out is this OUTBOX. So
the same rule lands here: when the finding depends on something you cannot
determine from the project's own files, write the entry with `status:
blocked` and put the exact missing fact in `details`. Do not infer the
project's intent, do not pick a plausible default, do not write `ready` on
a finding you had to assume your way into.

This is the failure mode a read-only worker is *most* prone to and the main
agent is *least* able to catch. Everything else a sub gets wrong shows up as
a boundary violation, a stale ref, or a patch that will not apply -- all
mechanically detectable at collect (§ 4). A guess arrives looking exactly
like knowledge: correctly formatted, confidently worded, `status: ready`,
and wrong. The main agent then tickets it as fact. `blocked` costs one round
trip; a swallowed guess costs however long it takes someone to notice the
project was built on it.

**Backpressure**: this is manually invoked, not a daemon (§ 4) -- but a subSaipen that self-planned its own backlog (bare PLAN, TEMPLATE's default `next_action`) can still grind through many tickets unsupervised before anyone runs `collect`. If more than 10 `ready` entries would accumulate unreviewed, the subSaipen SHOULD pause further ticket completion and set its own `phase: BLOCKED` with `blocker: OUTBOX awaiting main agent collect` rather than continuing to pile up findings nobody's seen yet -- the same `BLOCKED` phase every subSaipen already has legally available (§ 8), no new lifecycle state.

## 3. Ticket ID namespace

| Prefix | Owner |
|---|---|
| `SYS-` | Cross-cutting / protocol-level tickets |
| `WIKI-` | saiwiki |
| `HUNT-` | saihunt |
| `UI-` | saiui (fixer, § 9) |
| `PY-` | saipython (fixer, § 9) |
| `<NAME>-` | any other subSaipen (first 4 letters, uppercase) |

Each subSaipen numbers its own tickets independently; the prefix is what
keeps them unambiguous once folded into the main board.

**Folding onto the main board**: a subSaipen ID (`WIKI-001`, `HUNT-003`, ...)
is never written directly onto the main `BOARD.md` as a ticket ID -- CORE.md
§ 1.2 requires the `T-###` shape there, no exceptions for extension-sourced
tickets. Collecting a finding always creates a normal new `T-###` ticket;
the original subSaipen ID is preserved in that ticket's own description or
`| blocker:` text (e.g. `T-057 [from saiwiki HUNT-003] ...`), never
repurposed as the ticket ID itself.

### 3.1 Built-in role charters

Built-in role charters are first-class, version-controlled identity documents
for fixer and reporter subSaipens. They live in the shipped library as
`extensions/subs/sai*.md` and are inherited by every project at bootstrap
and sync.

A charter defines the subSaipen's:
- identity and design roles (always all of them, never one picked from a menu);
- authority boundary (what it may touch, what it must not);
- required read order on every adoption;
- deterministic design or analysis method;
- output contract (OUTBOX shape, fields, verification requirements);
- non-goals (what it is not and must not become).

**Inheritance, not duplication.** Charters are loaded by reference from the
project-local copy, never copied into the subSaipen's own instance folder.
A copied charter would become a second source of truth and drift.

**Precedent.** `extensions/subs/saitest.md` was the first built-in role
charter (T-492). `saiui.md` is the second. Both follow this contract.

**Custom roles.** A `sai*` name with no shipped charter is a valid generic
SubSaipen governed only by PROTOCOL.md and its own BOARD. Do not fabricate
a charter for a name that has none.

## 4. Handoff

**Main agent -> subSaipen**: writes tickets into `<name>/BOARD.md`'s
`## TODO`. The subSaipen reads its own board, picks the next ticket, same
Pick Rule as Core (CORE.md §1.6).

**SubSaipen -> main agent**: finishes a ticket, and runs `saipen prepare` to package the result. `PREPARE` instructs the subSaipen to:
1. Re-verify the findings against current HEAD (freshness).
2. Write comprehensive injection instructions for the main agent.
3. Write the combined result into `kitchen/OUTBOX.md` as `status: ready`, and move the ticket to its own `## DONE`.

**Targeted complete-package path.** Core `saipen collect <producer>` is stricter than the backlog-oriented `saipen sub collect`: it consumes exactly one producer and requires one complete `status: ready` package carrying `producer`, `source_head`, `coverage`, `payload`, `verified`, and `instructions`. `saipen prepare saiwiki` must cover the whole maintained wiki, not one sampled page or a quick scan. If the package is missing, incomplete, non-ready, stale, or already reviewed, Core performs no main-project write and replies exactly `Not ready: run qq first.` Targeted collection then applies only the declared payload, creates/claims a normal Core ticket, and enters Core `VERIFY -> REVIEW -> SHIP`; it inherits the boundary check and crash-safe ordering below. The tripled `qqq` macro adds SHIP after collection. The doubled `qq` never integrates, commits, tags, or pushes.

Whenever the main agent chooses to check (during `HUNT`, at the top of `saipen continue`, or via `saipen sub collect`):
0. **Boundary check first, before trusting anything an OUTBOX claims.** § 1
   says a subSaipen MUST NOT touch a file outside its own
   `.saipen/extensions/subs/<name>/` -- but that rule has no technical
   lock (§ 1 says so plainly), so a weak or confused model can and does
   violate it. A real incident: a subSaipen wrote fabricated-looking
   tickets and draft files directly into the *main project's own*
   `BOARD.md`/`kitchen/` -- not through OUTBOX at all -- while its own
   OUTBOX and kitchen sat untouched and stale. Before folding anything in,
   run `git status` (or, no git, compare mtimes against your own last
   checkpoint) against the **whole working tree, not just `.saipen/`** --
   the rule in § 1 is "any file outside its own folder," and a confused
   sub can just as easily edit real source (`src/`, config, anything) as
   it can the main project's own `BOARD.md`/`kitchen/`/`LOG.md`/`STATE.md`;
   checking only the `.saipen/` metadata files would miss exactly that
   wider case. Anything changed you did not make yourself -> that is a
   boundary violation, not a finding: do NOT silently merge it (it may be
   fabricated) and do NOT silently revert it either (it may be someone's
   real work) -- set `STATE.phase: BLOCKED` with `next_action: WAIT: blocked -- ...`
   (CORE.md §1.2's category vocabulary) naming the exact files and asking the
   user how to proceed, same as any other
   destructive-adjacent surprise (CORE.md §1.1) -- surfacing it in chat alone
   is not enough, the session MUST actually halt on it, not quietly move on
   to other work while a corrupted tree sits unresolved. Only once the main
   tree's own files are confirmed untouched by anyone but you does the
   normal OUTBOX-based collect below apply.
1. Read every active subSaipen's `OUTBOX.md`. An entry that's sat unreviewed
   a while may have gone stale (file renamed, bug already fixed by another
   route) -- spot-check `main_project_refs` still make sense against current
   HEAD before ticketing. Clearly stale -> mark `status: stale` in the
   entry and skip it, don't ticket a ghost. This is the same freshness
   discipline `PREPARE` already applies to one ticket, just extended to a
   backlog that may have waited days for `collect` to run.
2. For each `ready` entry: `critical: true` -> ticket on the main `BOARD.md` immediately; `critical: false` -> append to `_shared/inbox.md` (shape defined below) for the next planning round. The main agent MAY skip any individual entry and leave it `ready` for a later collect -- nothing requires swallowing the whole OUTBOX in one pass.
3. **Write order matters for crash safety**: create the main ticket and
   append the main `LOG.md` line (below) FIRST, THEN mark the OUTBOX entry
   `reviewed` (or clear it) LAST -- same asymmetric-safety principle as
   CORE.md §1.5's checkpoint ordering. A crash between the two leaves a
   worst case of one duplicate ticket on retry (annoying, safe, easy to
   spot and merge) rather than a silently lost finding, which is the
   failure mode the reverse order would risk.
   That main-`LOG.md` line is an ordinary CORE.md §1.2 log line -- its shape
   is defined there and is not restated here (an earlier copy of the
   skeleton lived in this spot and showed every optional bracket as if it
   were mandatory). The only sub-specific parts: set `[agent: <subSaipen
   name>]`, and write the taxonomy text as `RUN: collect <name>-### ->
   T-###`. Naming the subSaipen's own ID in that free text IS the
   traceability link between the two event graphs, because § 1.2's
   `[parent: E-###]` cannot reach across files into the subSaipen's
   separate `LOG.md` -- the text reference does that job instead, no RFC
   change needed.
   The subSaipen's own `LOG.md` MAY also get a mirrored one-line note when
   collected (`RUN: collected by main agent -> T-###`) for a complete
   trail on both sides -- optional, since the subSaipen's ticket already
   reached `## DONE` at `PREPARE` time regardless of what collect does
   with it (§ 4 above); this is symmetry, not a dependency.

No ACK ceremony, no timers, no lifecycle states -- this is a manually
invoked agent, not a daemon; nothing here needs liveness detection.

**`_shared/inbox.md` shape and ownership**:
```markdown
# Inbox

- DATE | source: <name>-### | <one-line summary> | ref: [src/foo.py]
```
Main-agent-owned: it's the one deciding what to do with these at the next
`PLAN`, so it's the one that prunes. SubSaipens are append-only against
this file -- add a new line, never edit an existing one, which sidesteps
any write race between two subSaipens collecting at once without needing
CORE.md §1.4's full claim machinery (this is a shared append log, not a
claimed ticket). Prune rule: an entry older than 30 days, or superseded by
a later entry with the same `ref:`, MAY be deleted -- `saipen sub clean`
or a `HUNT` pass are the natural moments, not a standalone job. Bare
`saipen plan` (Proposal Mode, `phases/plan.md`) SHOULD read this file
before generating tickets -- that's the "next planning round" § 4 above
refers to.

## 5. MANIFEST.md

File: `.saipen/extensions/subs/MANIFEST.md`. Just the list of subSaipen the main
agent should remember to check -- their own `STATE.md` already carries
`phase`/`task`/`next_action`, no need to duplicate it here.

```markdown
# SubSaipen Manifest

- saiwiki -- .saipen/extensions/subs/saiwiki/ | last_collect: ISO8601 UTC
- saihunt -- .saipen/extensions/subs/saihunt/ | last_collect: ISO8601 UTC
```

`| last_collect:` is OPTIONAL, updated by `saipen sub collect` each time it
touches that subSaipen -- a way to notice one's gone quiet (an old
timestamp next to an otherwise-fresh manifest), not a second status field
to keep in sync; staleness is read off the date itself, nothing stored
twice. Add a line on `spawn`, remove it on `clean`. That's the whole
lifecycle.

## 6. Staleness

A subSaipen that's finished and folded in is stale kitchen content by
definition (CORE.md §1.2's kitchen rule, `phases/clean.md`) -- `HUNT`'s
existing kitchen-staleness check (v7.23.0) already covers it. No separate
staleness machinery needed here.

## 7. `saipen sub` commands (extension-defined, CORE.md §1.9)

Legal only while `.saipen/extensions/subs/` (or legacy root `extensions/subs/`) exists in the project.

| Command | Does |
|---|---|
| `saipen sub list` | Read `MANIFEST.md`; for each entry, read its `STATE.md` and report `phase`/`task`. Any entry showing `phase: BLOCKED` gets an explicit WARNING appended to the output, not just a quiet status line -- a subSaipen can't escalate itself to a human on its own, so `list` is what surfaces it. |
| `saipen sub status <name>` | Read-only peek: report `<name>`'s `kitchen/OUTBOX.md` counts (ready/draft/blocked/reviewed, how many critical) without modifying anything or running collect. |
| `saipen sub spawn <name>` | **First-run bootstrap, then spawn.** If this project has no `.saipen/extensions/subs/` yet: verify `<saipen_home>/extensions/subs/PROTOCOL.md` actually exists first -- `saipen_home` stale or the clone moved/deleted? `BLOCKED` with `blocker: saipen_home stale: <path>`, never copy from a path that didn't check out. Otherwise copy `PROTOCOL.md`, `README.md`, `crew.md`, `TEMPLATE/`, an empty `_shared/inbox.md`, and all built-in `sai*.md` role charters from there (the SAIPEN home's own copy of this extension -- unaffected by where a consuming project attaches it; the home path is already in `STATE.md`'s `saipen_home` field, CORE.md §1.7 -- no manual copy needed, this IS the explicit ask that makes copying it in appropriate, unlike `saipen set`'s general no-auto-populate rule in CORE.md §1.9). Then, every run: if `.saipen/extensions/subs/<name>/` already exists, refuse and report it -- point at `saipen sub clean <name>` first if replacement is actually intended, never silently overwrite an existing subSaipen's history. Otherwise copy `TEMPLATE/` to `.saipen/extensions/subs/<name>/`, set `agent: <name>` (replacing TEMPLATE's placeholder), `saipen_home: <path>` (copied from the main project's own `STATE.md`), **and `updated:` to the real current UTC timestamp** (TEMPLATE's `2026-01-01T00:00:00Z` is a placeholder like the other two, not a value to partially edit -- CORE.md §1.2 requires this field genuinely current at every checkpoint, spawn included; §8 below says this file's shape is identical to Core's own for exactly this reason) in its `STATE.md`, add a line to `MANIFEST.md` (creating it first if this was also the bootstrap run). Two agents spawning concurrently is CORE.md §1.4's existing concurrency boundary (one writer at a time), not a new problem this command invents. |
| `saipen sub pause <name>` | Set `<name>`'s own `STATE.phase: BLOCKED` with `blocker: paused by main agent` -- freezes it (no new findings, no ticket work) without destroying its board/log/outbox, unlike `clean`. Useful right before a `SHIP` to avoid a subSaipen producing findings mid-ship. |
| `saipen sub resume <name>` | Set `<name>`'s `STATE.phase` back to whatever it was doing before `pause` (its own `LOG.md` tail says what that was). |
| `saipen sub collect` | Run the Handoff procedure (§ 4) against every active subSaipen. |
| `saipen sub clean <name>` | **MUST check before removing, not just describe the precondition**: read `<name>/BOARD.md` and `<name>/kitchen/OUTBOX.md` first. Any `TODO`/`DOING` ticket, or any `ready` OUTBOX entry, still there -> refuse and report exactly what's outstanding, do not remove. Only once `BOARD.md` is empty (`DONE` tickets don't count against this) and nothing sits `ready` unreviewed does it remove the `MANIFEST.md` line and the `.saipen/extensions/subs/<name>/` folder. |
| `saipen sub sync` | **Refresh the shared protocol files, never a subSaipen's own history.** A project's `PROTOCOL.md`/`README.md`/`crew.md`/`TEMPLATE/` and all built-in `sai*.md` role charters are copied once, at first `spawn` (§ above) -- they do NOT auto-update when `<saipen_home>`'s own copy gains new vocabulary later (a real incident: a project spawned before v7.56.0 had a frozen `PROTOCOL.md` missing this very command table, and bare-name role-adopt silently stopped being recognized). `sync` re-copies exactly those shared items plus all built-in `sai*.md` role charters from `<saipen_home>/extensions/subs/` -- same freshness check as `spawn`'s own bootstrap step (`saipen_home` stale or moved -> `BLOCKED`, never copy from a path that didn't check out. Overwriting these four is always safe: they are inherited reference material, never a subSaipen's own live data. `sync` MUST NOT touch any `.saipen/extensions/subs/<name>/` folder's `STATE.md`/`BOARD.md`/`LOG.md`/`kitchen/` -- that is exactly the live, per-agent history `spawn`'s own "refuse if already exists" rule already protects, and `sync` protects it too, by construction (it never looks inside a `<name>/` folder at all). LOG one line noting what changed (or `RUN: sub sync -> no drift` if the copies were already current). |
| `<subname>` (bare -- any name, not just the 3 shipped examples) -- also `<subname> init`/`<subname> start`, identical meaning | **Role-adopt shortcut (crew, `crew.md`), generalized to every subSaipen, not a saiwiki/saihunt/saipython special case.** Recognized in any of three cases: (1) `subs/<subname>/` already exists -- ANY name, once spawned once, gets this same one-word shortcut forever after, no special-casing; (2) `<subname>` is a shipped example (saihunt/saipython/saiwiki); (3) `<subname>` matches the `sai`-prefix naming convention every real subSaipen in this system already uses (saiwiki, saihunt, saipython, and any future one) -- a mechanical, zero-guess signal, not free-form word matching, so an unrelated unrecognized word does NOT spin up a phantom subSaipen. A custom name that does NOT fit the `sai*` shape (e.g. README's own `myagent` example) still needs one explicit `saipen sub spawn <name>` the first time -- after that its folder exists and case (1) covers it identically. The trailing `init`/`start` is optional decoration, not a different command -- same reuse of "init" as `saipen set`/`saipen init` at the top level (CORE.md §1.7), so don't require the inferential leap twice. Not spawned yet (cases 2/3)? Spawning is the agent's own first internal step, invisible to the human, same one-word response -- not a separate command the user types first (the `saipen sub spawn <name>` row below is the same action named explicitly, for a human who wants to trigger it directly, or a name outside `sai*`). Then *become* that subSaipen: if `.saipen/extensions/subs/<subname>.md` exists locally (a built-in role charter), load it after PROTOCOL.md and before anything else -- it defines the subSaipen's identity, authority boundary, read order, and method; a subSaipen whose built-in charter is present but was not read is running as a generic worker and is not conformant. If the built-in charter exists in `<saipen_home>/extensions/subs/` but NOT locally (old project, stale sync), stop with the exact recovery instruction `run saipen sub sync` and do not proceed as a generic worker. A custom `sai*` name with no built-in charter remains a valid generic SubSaipen governed only by PROTOCOL.md and its own BOARD. Read its OWN `STATE.md`/`BOARD.md`/`LOG.md` (never the main project's `.saipen/`), and execute its `next_action` immediately -- its default is to start its own cycle. One word -> the agent is that worker and already working, in its own factory, never the main project's. Spawning a single example alone (just `saiwiki`, no crew) is a complete, valid, standalone flow -- the "three roles" in `crew.md` are one documented way to combine them, not a requirement to spawn together. For an unattended run, follow with `saipen goal "<its loop>"` so it flows between tickets to its own valve. |
| `saipen crew` | Print the 3-window crew layout (Core writer + saihunt sensor + saipython fixer) and the single command per window, pointing at `crew.md` and the `bootstrap/saipen_crew.*` launcher. Read-only: it explains/launches, it never spawns or writes -- each window's own bare-name command does that. |

`saipen sub spawn` requires a project that already has `.saipen/` (i.e. `saipen set` already ran) -- a subSaipen attaches to a main project's continuation state, it isn't one on its own. No `.saipen/` at all yet? Tell the user to run `saipen set` first; don't silently trigger `INIT` as a side effect of an unrelated command.

First `saipen sub spawn` in a project no `saipen_home` was ever recorded for (state written before v7.25.0, or a manual/degraded bootstrap)? Ask once -- `WAIT: blocked -- path to the saipen clone to bootstrap subs from` -- never guess a path.

A `BLOCKED` subSaipen sitting unreviewed indefinitely is a silent rot risk -- the main agent MUST check `saipen sub list`'s output for `BLOCKED` warnings at least once per autonomous `HUNT` pass (MAINTENANCE.md §2.1), piggybacking on a cadence that already runs on its own rather than inventing a new dedicated timer.

## 8. File shape for a subSaipen

Identical to Core's own `.saipen/` shape -- **CORE.md §1.2's required set,
whatever it currently says, plus exactly one sub-specific constraint:
`mode` is always `read-only`** (§ 1). "Identical" is the whole rule, so the
field list is deliberately NOT reproduced here. It used to be, as a
convenience, and it did what every convenience copy does: between v7.82.0
and v7.88.0 it claimed "no extra required fields" while `tools/validate.py`
had been requiring two more for six releases, so a subSaipen built to this
file was born non-conformant. v7.92.0 removed the copy rather than fixing
it again, for the same reason Core collapsed its own five copies of that
list into one.

Two places carry the truth, both of which are checked and therefore cannot
drift silently: CORE.md §1.2 (normative), and `TEMPLATE/STATE.md` (executable
-- `saipen sub spawn` copies it verbatim and `tools/validate.py` validates
it every run). Read either. If this file ever appears to disagree with
CORE.md on the shared shape, CORE.md wins (CORE.md §1.9) and this file has a
bug worth reporting.

**Core's determinism invariants (CORE.md §1.11) bind a subSaipen too** -- it is
a SAIPEN instance, not a lesser thing. One ticket in its own `## DOING` at a
time; every run leaves a trace in its own `LOG.md`, including "found nothing";
the same fixed action priority. The one that needs translating is the last --
see § 2's `blocked` status for how a sub stops instead of guessing, since it
has no `WAIT:` a human ever reads.

## 9. Fixer-type subSaipen (the OUTBOX carries a tested patch, not just a finding)

saiwiki and saihunt *report*: a finding, a draft page, a proposed change
in prose. A **fixer-type** subSaipen (saipython is the first) goes one
step further -- its OUTBOX deliverable is a **ready, already-tested
patch**. This does NOT weaken the one rule that matters (§ 1): a fixer
still never writes to the main project, and its `STATE.phase` still never
enters `BUILD`/`SHIP` (unreachable under `mode: read-only`, CORE.md §1.3,
enforced by `tools/validate.py`). The reconciliation is the same one
`phases/translate.md` uses for a parallel TRANSLATE instance -- write
freely, but only inside your own sandbox; never touch the shared tree.

**The pen (own-kitchen sandbox).** A fixer does its work in
`kitchen/pen/` -- a *copy* of exactly the target file(s), cloned from the
main tree read-only. It edits the copy, never the original. This is the
same move saiwiki already makes when it drafts a finished page into its
own `kitchen/` -- producing a concrete artifact there is not a project
write and needs no `BUILD` phase. Cloning is read; editing the clone is a
kitchen write; the main tree is untouched throughout.

**Verify in the sandbox (phase `VERIFY`, which IS reachable for a sub).**
Run the repo's own harness -- `pytest`, `ruff`, `mypy`, whatever the
project already uses -- against the patched copy in the pen, never
inventing a harness. A fix with no green evidence is a `draft`, not
`ready`. `VERIFY` is a legal sub phase (`tools/validate.py` forbids only
`BUILD`/`SHIP`/`CLEAN`/`TRANSLATE`), so a fixer records its test run
honestly under it.

**Capability gate.** A fixer needs shell + the language toolchain
(for saipython: `python`, and whatever of `pytest`/`ruff`/`mypy` the repo
uses). Missing on this host -> degrade, don't fake: fall back to
saihunt-style behavior -- describe the proposed fix as an ordinary
`critical`-tagged finding, mark it plainly `unverified: no toolchain`, and
let the main agent build and verify it the normal way. Never mark a patch
`ready` that was never actually run.

**OUTBOX shape for a patch.** The § 2 format, with the fix carried
explicitly:
```markdown
## PY-001: short description
- **status:** ready
- **summary:** one line -- what was broken, what the patch does
- **main_project_refs:** [src/foo.py]
- **critical:** true | false
- **severity:** P2 | P3
- **base_head:** <git short hash the patch was cut against>
- **verified:** pytest PASS (N passed) / ruff clean / mypy clean -- quote the real result
- **patch:**
  ```diff
  <unified diff, applies from repo root>
  ```
- **details:** root cause, why the diff is minimal, any sibling issue spotted but deliberately left for a separate ticket.
```

**Freshness on the way out and the way in.** The patch is cut against one
`base_head`. `PREPARE` (§ 4) MUST re-check it still applies against
current HEAD before writing `status: ready`; moved on -> re-cut against
the new HEAD or mark it `stale`, never hand over a diff that won't apply.
On `collect`, the main agent applies the patch, then runs it through Core
`VERIFY -> REVIEW -> SHIP` like any other change -- the sub's own green
run is *evidence that saves the main agent time*, never a substitute for
Core's own gates (CORE.md §1.6). The fixer proposes a finished, tested piece;
the main agent still decides and still acts.

**Scope discipline (the reverse-end contract).** A fixer exists to clear
the *tail* -- the low-severity, mechanically-fixable bugs the main flow
keeps deprioritizing (P2/P3, a missing error path, a lint/type nit, a
small off-by-one, dead code). One fix per patch, minimal diff, same design
language as the surrounding code. Anything large, risky, or architectural
is NOT a fixer's job -- report it as a `critical` finding and leave it for
the main agent, exactly as saihunt would. Clearing the tail from the
opposite end is the whole point: the main agent stays on the heavy work,
the fixer keeps the small stuff from ever piling up.

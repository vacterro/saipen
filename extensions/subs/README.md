# SubSaipen -- EXAMPLE, copy into your project

Isolated, read-only research agents that run alongside the main agent on
the same project -- they find things and propose things, they never edit
the project themselves. Same role as `extensions/security/`,
`extensions/performance/`: a reference example under RFC § 1.9, not
something the SAIPEN home reads on its own behalf.

**Not yet field-tested.** Design is sound, nothing has run for real. Same
policy as `extensions/multi-agent/` was under until proven live: usable,
not advertised.

## The one rule that matters

```text
A subSaipen reads the main project. It never writes to it.
Findings leave through kitchen/OUTBOX.md -- the only door out.
```

## Structure

```
.saipen/extensions/subs/
├── MANIFEST.md         # which subSaipen exist
├── PROTOCOL.md          # the actual rules -- read this first
├── _shared/inbox.md     # non-critical findings, next round
├── TEMPLATE/            # copy this to start one
└── <name>/              # saiwiki, saihunt, ...
```

Everything protocol-shaped a project carries lives under one `.saipen/`
roof (v7.35.0). A project bootstrapped earlier may still carry this at
root-level `extensions/subs/` -- equivalent, migrate when convenient.

## Quick start

No manual copying -- one command, even in a project that has never seen
`.saipen/extensions/subs/` before:

```bash
saipen sub spawn myagent
# first time in this project: bootstraps .saipen/extensions/subs/ itself from
# saipen_home (STATE.md, RFC § 1.7) -- PROTOCOL.md, README.md, crew.md, TEMPLATE/, MANIFEST.md
# every time: .saipen/extensions/subs/myagent/ created from TEMPLATE/, added to MANIFEST.md
# open its STATE.md, set next_action; open BOARD.md, write first tickets
```

Then open that folder in whichever agent you want running as `myagent`
(Claude, Antigravity, Codex, OpenCode -- the protocol doesn't care which)
and point it at `.saipen/extensions/subs/myagent/PROTOCOL.md`. It works its own
board, writes findings to its own `kitchen/OUTBOX.md`.

One of the three shipped examples, spawned alone, no crew required:

```bash
saiwiki
# bare name, first time in this project -> spawns saiwiki from TEMPLATE/ then
# adopts it immediately: reads its own STATE.md/BOARD.md, executes next_action.
# "saiwiki init" or "saiwiki start" work the same way -- init/start is decoration.
```

`mode: read-only` is a contract the subSaipen is told to follow, not a
technical wall (`PROTOCOL.md` § 1) -- if you want a real one, run it in
its own worktree or a directory-restricted session, not just the same
full-access agent on its honor.

Back in the main session:

```bash
saipen sub collect
# critical findings -> ticket on the main BOARD.md immediately
# everything else -> _shared/inbox.md for the next planning round
```

## Three examples included

- **saiwiki** -- reads the project, drafts wiki/documentation pages into
  its own `kitchen/`, hands off page-ready content via OUTBOX.
- **saihunt** -- reads the project for bugs (null safety, exception
  handling, race conditions, resource leaks), tickets each finding.
- **saipython** -- a **fixer** (PROTOCOL.md § 9), not just a researcher:
  works the tail of a Python project (low-severity bugs, lint/type nits,
  small correctness fixes), clones targets into its own `kitchen/pen/`,
  fixes and tests the copy, and hands back a ready, already-verified patch.
  Still never writes to the main tree -- the patch leaves through OUTBOX and
  the main agent lands it through the normal gates.

## Commands

| Command | Does |
|---|---|
| `saipen sub list` | Show active subSaipen and their current phase. |
| `saipen sub spawn <name>` | Create a new subSaipen from `TEMPLATE/`. |
| `saipen sub collect` | Process every subSaipen's `OUTBOX.md`. |
| `saipen sub clean <name>` | Remove a finished subSaipen. |
| `<subname>` (bare, e.g. `saihunt`, or any `sai*`-named subSaipen) | Adopt that role and start working, spawning it first if needed -- one word (crew, `crew.md`, PROTOCOL.md § 7). |
| `saipen crew` | Show the 3-window crew layout + the one command per window. |

## Crew -- run three at once (`crew.md`)

You dig the tunnel (the Core agent); two workers set the beams behind you
(saihunt finds bugs, saipython fixes tails). One command per window:

```
window 1:  saipen continue      # Core, the writer
window 2:  saihunt              # sensor -- spawns+adopts, hunts on loop
window 3:  saipython            # fixer -- spawns+adopts, patches via OUTBOX
```

One-click launcher: `bootstrap/saipen_crew.bat` (Windows) /
`bootstrap/saipen_crew.sh` (Unix) opens all three. Collect the workers from
the Core window any time with `saipen sub collect`. Full contract, roles,
pitfall->mechanism table, and the zone/handoff conventions: **`crew.md`**.

Full rules, OUTBOX format, ticket namespace -- `PROTOCOL.md`.

# T-1367 field acceptance -- what is measured, and by what

SRC-051 §10 and §11 in one place, with the harness facts that make the numbers
arguable instead of decorative.

## The runner

`tools/t1363_field_polygon.py` drives the INSTALLED OpenCode runtime against
nine project conditions with models from the local 9Router free pool
(`sairoute/SAIFREN`). Every fixture is a real git worktree in a disposable
directory, and the child's environment is bound to it (`cwd` AND `PWD`),
because a sandbox whose boundary the host cannot see is not a sandbox.

## Where a session's facts come from

Two sources, in this order, and the session records which one answered:

| `measurement_source` | meaning |
|---|---|
| `stdout_events` | the host's `--format json` NDJSON stream was readable |
| `host_session_store` | stdout gave nothing; the facts came from OpenCode's own session store (`opencode.db`, read-only) |
| `none` | neither -- the session is `UNMEASURED_NO_EVENT_STREAM` and every transcript metric is `None` |

The second source exists because of a measured failure, not a hypothetical:
on `long_file_task` a session ran the entire protocol chain and closed `T-1` at
`E-13` -- its own fixture ledger proves it -- while `--format json` put nothing
parseable on stdout. The metrics then read `protocol_commands_before_productive:
0`, which IS the strong acceptance number, so an unreadable transcript scored a
perfect run.

Binding is by identity, never by recency: the session id the stdout stream
named, or else only a session whose own `directory` IS this fixture and which
began after this run started. `tools/test_field_fixture_isolation.py` pins both
traps (another project's newer session; a session older than this run) plus the
known-good / known-blind pair.

A timed-out session is measured from the store too: the work it did before the
wall clock ran out is a measurement, and only an empty store makes it
`UNMEASURED`.

## The bars

`matrix_verdict.py` states them, per condition, from a `polygon.json`:

* executable conditions -- `saipen start` FIRST, at most ONE ordinary entry
  command before a productive action, and the requested target bytes actually
  change;
* `operator_decision` -- START, ONE exact question, resume, then productive
  action;
* never -- a seat/role/intake/auth/recovery/cc/protocol-grep detour, or the
  same refusal repeating with nothing changed;
* looking is not doing: status/read/git-status/test-only shell never scores a
  session productive (`productive_shell`).

## Isolation

Per session, MAIN and fixture are hashed over all four canonical carriers
(`STATE.md`, `BOARD.md`, `LOG.md`, `intake/index.json`) before and after.
`PASS` needs the fixture to have moved and this repository not to hold any id
the session minted; `FAIL` means this repository's own ledger holds one;
`INCONCLUSIVE_CONCURRENT_MAIN_WRITE` is the honest answer when MAIN moved but
holds none of them.

**Operating constraint, recorded because it cost a verdict once: no MAIN ledger
writes while a matrix runs.**

## Files here

| file | what it is |
|---|---|
| `matrix_verdict.py` | the bars above, as a re-runnable verdict over a `polygon.json` |
| `run1-crashed-console-codec.log` | run 1, killed by a cp1251 console at session 5; kept as the reason `force_utf8_console` and per-session report writes exist |
| `polygon-smoke-paraphrase-finding.json` | the smoke run that found T-1372: the session was refused on transport and started its own 179-byte paraphrase |
